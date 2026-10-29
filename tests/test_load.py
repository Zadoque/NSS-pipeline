from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import call

import pandas as pd
import pytest

from app.pipeline.load import (
    CODIGO_NAO_INFORMADO,
    UNIDADE_NAO_IDENTIFICADA,
    _clean_code_series,
    _integer_series,
    _prepare_fact_frame,
    _scope_statement,
    _validate_snapshot,
    _upsert,
    get_engine,
    insert_fato_casos,
    load_gold_to_postgres,
    upsert_dim_classificacao,
    upsert_dim_doenca,
    upsert_dim_evolucao,
    upsert_dim_municipio,
    upsert_dim_unidade_saude,
)


def test_clean_code_series_trata_string_vazia_como_ausente():
    # Regressão: o SINAN grava campo ausente como "" literal, não NaN —
    # um .fillna() sozinho não pega esse caso (bug real já visto em
    # produção, ver ForeignKeyViolation de cd_classificacao='').
    serie = pd.Series(["10", "", None, "8"])
    result = _clean_code_series(serie, default="NI")
    assert list(result) == ["10", "NI", "NI", "8"]


def _gold_minima(**overrides) -> pd.DataFrame:
    base = {
        "year": [2026],
        "month": [1],
        "cd_mun": ["3301009"],
        "nm_mun": ["Campos dos Goytacazes"],
        "cd_uf": ["33"],
        "nm_uf": ["Rio de Janeiro"],
        "cases_total": [5],
    }
    base.update(overrides)
    return pd.DataFrame(base)


def test_prepare_fact_frame_usa_sentinela_quando_dimensao_ausente():
    # Gold gerada sem unidade_notificacao/classificacao_final/evolucao
    # selecionadas — as três colunas de código devem cair no "não
    # informado" em vez de erro ou nulo.
    df = _gold_minima()
    fact_df = _prepare_fact_frame(df, disease_codigo="DENG", batch_id="20260101T000000Z")

    assert (fact_df["cd_unidade"] == UNIDADE_NAO_IDENTIFICADA).all()
    assert (fact_df["cd_classificacao"] == CODIGO_NAO_INFORMADO).all()
    assert (fact_df["cd_evolucao"] == CODIGO_NAO_INFORMADO).all()
    assert (fact_df["disease_codigo"] == "DENG").all()


def test_prepare_fact_frame_normaliza_string_vazia_quando_dimensao_presente():
    df = _gold_minima(ID_UNIDADE=["0729884"], CLASSI_FIN=[""], EVOLUCAO=["1"])
    fact_df = _prepare_fact_frame(df, disease_codigo="DENG", batch_id="20260101T000000Z")

    assert fact_df.loc[0, "cd_unidade"] == "0729884"
    assert fact_df.loc[0, "cd_classificacao"] == CODIGO_NAO_INFORMADO
    assert fact_df.loc[0, "cd_evolucao"] == "1"


def test_prepare_fact_frame_preserva_cases_total():
    df = _gold_minima(cases_total=[42])
    fact_df = _prepare_fact_frame(df, disease_codigo="DENG", batch_id="b")
    assert fact_df.loc[0, "cases_total"] == 42


def _validate(gold_df, **overrides):
    options = dict(year=2026, municipios=["3301009"], expected_cases_total=5,
                   snapshot_complete=True, source_extracted_at=datetime(2026, 1, 1, tzinfo=UTC),
                   allow_empty=False, batch_id="b1")
    options.update(overrides)
    batch_id = options.pop("batch_id")
    return _validate_snapshot(gold_df, "DENG", batch_id, **options)


def test_semana_aaaass_e_preservada_sem_overflow():
    facts = _prepare_fact_frame(_gold_minima(SEM_NOT=["202602"]), "DENG", "b1")
    assert facts.loc[0, "semana_notif"] == 202602


@pytest.mark.parametrize("value", ["5994", "202600", "202654", "202602.5", "invalido"])
def test_semana_invalida_e_rejeitada(value):
    with pytest.raises(ValueError):
        _validate(_gold_minima(SEM_NOT=[value]))


@pytest.mark.parametrize("overrides", [
    {"year": [2025]}, {"cd_mun": ["3302403"]}, {"disease": ["CHIK"]},
    {"month": [13]}, {"cases_total": [-1]}, {"cases_total": [1.5]},
    {"cases_total": [None]}, {"CS_SEXO": ["X"]},
])
def test_snapshot_invalido_e_rejeitado(overrides):
    with pytest.raises(ValueError):
        _validate(_gold_minima(**overrides))


def test_snapshot_incompleto_e_rejeitado():
    with pytest.raises(ValueError, match="incompleto"):
        _validate(_gold_minima(), snapshot_complete=False)


def test_snapshot_total_diferente_da_silver_e_rejeitado():
    with pytest.raises(ValueError, match="diverge"):
        _validate(_gold_minima(), expected_cases_total=6)


def test_snapshot_gold_duplicada_nao_e_somada():
    df = pd.concat([_gold_minima(), _gold_minima()], ignore_index=True)
    with pytest.raises(ValueError, match="duplicada"):
        _validate(df, expected_cases_total=10)


def test_snapshot_reagrupa_ausencias_normalizadas_preservando_total():
    df = pd.concat([_gold_minima(CLASSI_FIN=[""]), _gold_minima(CLASSI_FIN=[None])], ignore_index=True)
    _, facts, _ = _validate(df, expected_cases_total=10)
    assert len(facts) == 1
    assert facts.loc[0, "cd_classificacao"] == "NI"
    assert facts.loc[0, "cases_total"] == 10


def test_snapshot_preserva_municipios_sem_linhas_no_recorte():
    _, _, scope = _validate(_gold_minima(), municipios=["3301009", "3302403"])
    assert scope == ["3301009", "3302403"]


def test_snapshot_vazio_bloqueado_por_padrao():
    with pytest.raises(ValueError, match="Gold vazia"):
        _validate(_gold_minima().iloc[:0], expected_cases_total=0)


def test_snapshot_vazio_exige_total_zero_e_permissao_explicita():
    _, facts, scope = _validate(_gold_minima().iloc[:0], expected_cases_total=0, allow_empty=True)
    assert facts.empty
    assert scope == ["3301009"]
    with pytest.raises(ValueError, match="diverge"):
        _validate(_gold_minima().iloc[:0], expected_cases_total=5, allow_empty=True)


def test_get_engine_requires_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        get_engine()


def test_upsert_ignores_empty_rows_and_uses_do_nothing_for_only_key(mocker):
    conn = mocker.Mock()

    _upsert(conn, "analytics.dim_x", [], ["codigo"])
    _upsert(conn, "analytics.dim_x", [{"codigo": "A"}], ["codigo"])

    assert conn.execute.call_count == 1
    statement = str(conn.execute.call_args.args[0])
    assert "ON CONFLICT (codigo)" in statement
    assert "DO NOTHING" in statement


def test_upsert_updates_non_key_columns(mocker):
    conn = mocker.Mock()

    _upsert(conn, "analytics.dim_x", [{"codigo": "A", "nome": "Alpha"}], ["codigo"])

    statement = str(conn.execute.call_args.args[0])
    assert "ON CONFLICT (codigo)" in statement
    assert "nome = EXCLUDED.nome" in statement


def test_integer_series_rejects_fraction_and_text():
    with pytest.raises(ValueError, match="inteiro fora"):
        _integer_series(pd.Series([1.5]), "month", 1, 12)
    with pytest.raises(ValueError, match="não numérico"):
        _integer_series(pd.Series(["abc"]), "month", 1, 12)


def test_scope_statement_expands_municipios_parameter():
    statement = _scope_statement("SELECT 1 WHERE cd_mun IN :municipios")

    assert "municipios" in statement._bindparams
    assert statement._bindparams["municipios"].expanding is True


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"municipios": "3301009"}, "sequência"),
        ({"municipios": []}, "códigos"),
        ({"expected_cases_total": True}, "Total"),
        ({"source_extracted_at": datetime(2026, 1, 1)}, "fuso"),
        ({"batch_id": ""}, "batch_id"),
    ],
)
def test_snapshot_rejeita_metadados_de_publicacao_invalidos(overrides, message):
    with pytest.raises(ValueError, match=message):
        _validate(_gold_minima(), **overrides)


def test_dimension_upserts_filter_duplicates_and_sentinels(mocker):
    conn = mocker.Mock()
    fact = pd.DataFrame(
        {
            "cd_mun": ["3301009", "3301009", None],
            "nm_mun": ["Campos", "Campos", "ignored"],
            "cd_uf": ["33", "33", "33"],
            "nm_uf": ["RJ", "RJ", "RJ"],
            "cd_unidade": ["0000000", "0000001", "NI"],
            "nm_unidade": ["sentinela", "UBS", "NI"],
            "razao_social_unidade": [None, "UBS Ltda", None],
            "tp_unidade": [None, 1, None],
            "cd_classificacao": ["NI", "A", "A"],
            "cd_evolucao": ["NI", "1", "1"],
        }
    )

    upsert_dim_municipio(conn, fact)
    upsert_dim_unidade_saude(conn, fact)
    upsert_dim_classificacao(conn, fact)
    upsert_dim_evolucao(conn, fact)
    upsert_dim_doenca(conn, "DENG")

    calls = [call.args for call in conn.execute.call_args_list]
    assert len(calls) == 5
    assert any("dim_doenca" in str(args[0]) for args in calls)
    unidade_rows = next(args[1] for args in calls if "dim_unidade_saude" in str(args[0]))
    assert [row["cd_unidade"] for row in unidade_rows] == ["0000001"]


def test_unidade_rejects_non_smallint_type(mocker):
    conn = mocker.Mock()
    fact = pd.DataFrame({"cd_unidade": ["0000001"], "tp_unidade": [40000]})

    with pytest.raises(ValueError, match="SMALLINT"):
        upsert_dim_unidade_saude(conn, fact)

    conn.execute.assert_not_called()


def test_insert_fato_cases_handles_empty_and_renames_dimensions(mocker):
    conn = mocker.Mock()
    insert_fato_casos(conn, pd.DataFrame())
    assert conn.execute.call_count == 0

    fact = pd.DataFrame(
        {
            "disease_codigo": ["DENG"], "year": [2026], "month": [1],
            "cd_mun": ["3301009"], "cd_unidade": ["0000000"],
            "cd_classificacao": ["NI"], "cd_evolucao": ["NI"],
            "cd_sexo": ["I"], "semana_notif": [0], "ano_nascimento": [0],
            "age_band": ["NI"], "notification_district_id": [pd.NA],
            "notification_neighborhood_id": [pd.NA],
            "notification_territory_status": ["UNMAPPED_NOTIFICATION_UNIT"],
            "cases_total": [1], "batch_id": ["b1"],
        }
    )
    insert_fato_casos(conn, fact)
    statement, rows = conn.execute.call_args.args
    assert "INSERT INTO analytics.fato_casos" in str(statement)
    assert rows[0]["ano"] == 2026
    assert rows[0]["mes"] == 1


class _Result:
    def __init__(self, *, newest=None, groups_total=1, cases_total=5):
        self.newest = newest
        self.groups_total = groups_total
        self.cases_total = cases_total

    def scalar_one(self):
        return self.newest

    def one(self):
        return self


class _Connection:
    def __init__(self, *, newest=None, groups_total=1, cases_total=5):
        self.calls = []
        self.result = _Result(
            newest=newest, groups_total=groups_total, cases_total=cases_total
        )

    def execute(self, statement, *args):
        self.calls.append((str(statement), args))
        if "max(source_extracted_at)" in str(statement):
            return self.result
        if "count(*) AS groups_total" in str(statement):
            return self.result
        return None


class _Transaction:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc, traceback):
        return False


class _Engine:
    def __init__(self, connection):
        self.connection = connection

    def begin(self):
        return _Transaction(self.connection)


def test_load_publication_rejects_older_snapshot_before_mutation():
    extracted_at = datetime(2026, 1, 1, tzinfo=UTC)
    conn = _Connection(newest=datetime(2026, 1, 2, tzinfo=UTC))

    with pytest.raises(ValueError, match="Snapshot antigo"):
        load_gold_to_postgres(
            _Engine(conn), _gold_minima(), "DENG", "b1",
            year=2026, municipios=["3301009"], expected_cases_total=5,
            snapshot_complete=True, source_extracted_at=extracted_at,
        )

    assert not any("DELETE FROM" in statement for statement, _ in conn.calls)


def test_load_publication_rejects_database_total_mismatch():
    conn = _Connection(groups_total=2, cases_total=5)

    with pytest.raises(RuntimeError, match="Totais publicados divergem"):
        load_gold_to_postgres(
            _Engine(conn), _gold_minima(), "DENG", "b1",
            year=2026, municipios=["3301009"], expected_cases_total=5,
            snapshot_complete=True, source_extracted_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    assert any("DELETE FROM" in statement for statement, _ in conn.calls)
    assert not any("pipeline_publications" in statement and "INSERT" in statement for statement, _ in conn.calls)
