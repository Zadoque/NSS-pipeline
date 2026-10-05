from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from app.pipeline.load import (
    CODIGO_NAO_INFORMADO,
    UNIDADE_NAO_IDENTIFICADA,
    _clean_code_series,
    _prepare_fact_frame,
    _validate_snapshot,
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
                   allow_empty=False)
    options.update(overrides)
    return _validate_snapshot(gold_df, "DENG", "b1", **options)


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
