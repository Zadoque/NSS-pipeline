from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event

import pandas as pd
# pyrefly: ignore [missing-import]
import pytest
# pyrefly: ignore [missing-import]
from alembic import command
# pyrefly: ignore [missing-import]
from alembic.config import Config
# pyrefly: ignore [missing-import]
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.pipeline import load as load_module
from app.pipeline.load import load_gold_to_postgres
from app.pipeline.sinan.columns import CANONICAL_GOLD_COLUMNS
from app.pipeline.sinan.gold import aggregate
from app.pipeline.sinan.silver import transform

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def postgres_engine():
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip(
            "TEST_DATABASE_URL não definida — testes de integração pulados. "
            "Ver README (seção de testes) para configurar o banco de testes."
        )

    # A fixture reseta o schema: nunca aceitar URL de desenvolvimento/produção.
    if not (make_url(database_url).database or "").endswith("_test"):
        raise RuntimeError("TEST_DATABASE_URL deve apontar para banco com sufixo _test")
    engine = create_engine(database_url)

    # Este banco não é descartável (é um serviço Postgres persistente, não
    # um container efêmero) — reseta o schema manualmente antes de rodar
    # as migrations, para garantir estado limpo independente de execuções
    # anteriores.
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS analytics CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))

    # env.py lê DATABASE_URL do ambiente, não do Config do Alembic —
    # setar aqui garante que a migration rode contra o banco de TESTE,
    # não o de desenvolvimento.
    previous_url = os.environ.get("DATABASE_URL")
    try:
        os.environ["DATABASE_URL"] = database_url
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url

    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def _limpar_fato_entre_testes(postgres_engine):
    """Cada teste começa com fato_casos vazio, mas preserva as dimensões
    (incluindo as linhas sentinela) — evita interferência entre testes
    sem precisar recriar o schema inteiro a cada um (lento)."""
    yield
    with postgres_engine.begin() as conn:
        conn.execute(text("TRUNCATE analytics.fato_casos, analytics.pipeline_publications"))


def _gold_exemplo(cases_total: int = 5) -> pd.DataFrame:
    return pd.DataFrame({
        "year": [2026],
        "month": [1],
        "cd_mun": ["3301009"],
        "nm_mun": ["Campos dos Goytacazes"],
        "cd_uf": ["33"],
        "nm_uf": ["Rio de Janeiro"],
        "cases_total": [cases_total],
    })


def _publish(engine, gold_df, disease_codigo="DENG", batch_id="b1", **overrides):
    options = dict(year=2026, municipios=["3301009"],
                   expected_cases_total=int(gold_df["cases_total"].sum()),
                   snapshot_complete=True, source_extracted_at=datetime(2026, 1, 1, tzinfo=UTC))
    options.update(overrides)
    return load_gold_to_postgres(engine, gold_df, disease_codigo, batch_id, **options)


def test_load_gold_to_postgres_cria_linha_no_fato(postgres_engine):
    gold_df = _gold_exemplo(cases_total=5)
    _publish(postgres_engine, gold_df, disease_codigo="DENG", batch_id="b1")

    with postgres_engine.connect() as conn:
        row = conn.execute(
            text("SELECT cases_total FROM analytics.fato_casos WHERE disease_codigo = 'DENG'")
        ).fetchone()

    assert row is not None
    assert row.cases_total == 5


def test_missing_territories_are_sql_null(postgres_engine):
    _publish(postgres_engine, _gold_exemplo())
    with postgres_engine.connect() as conn:
        assert conn.execute(text("SELECT notification_district_id IS NULL AND notification_neighborhood_id IS NULL FROM analytics.fato_casos")).scalar_one()


def test_dimension_corruption_rolls_back(postgres_engine, monkeypatch):
    _publish(postgres_engine, _gold_exemplo(), batch_id="before")
    original = load_module.insert_fato_casos
    def corrupt(conn, facts):
        original(conn, facts)
        conn.execute(text("UPDATE analytics.fato_casos SET notification_district_id = 'NaN'"))
    monkeypatch.setattr(load_module, "insert_fato_casos", corrupt)
    with pytest.raises(RuntimeError, match="Dimensões"):
        _publish(postgres_engine, _gold_exemplo(), batch_id="after")
    with postgres_engine.connect() as conn:
        assert conn.execute(text("SELECT batch_id FROM analytics.fato_casos")).scalar_one() == "before"


def test_snapshot_substitui_contagem_em_vez_de_duplicar(postgres_engine):
    # Simula o SINAN "corrigindo" o número de um período já carregado
    # anteriormente (atualização retroativa) — não deve duplicar a linha.
    _publish(postgres_engine, _gold_exemplo(cases_total=5), "DENG", "b1")
    _publish(postgres_engine, _gold_exemplo(cases_total=8), "DENG", "b2")

    with postgres_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT cases_total FROM analytics.fato_casos "
                "WHERE disease_codigo = 'DENG' AND ano = 2026 AND mes = 1"
            )
        ).fetchall()

    assert len(rows) == 1
    assert rows[0].cases_total == 8


def test_load_gold_to_postgres_popula_unidade_saude_quando_presente(postgres_engine):
    gold_df = _gold_exemplo()
    gold_df["ID_UNIDADE"] = "0729884"
    gold_df["nm_unidade"] = "BEDALAB"
    gold_df["razao_social_unidade"] = "INSTITUTO DE MEDICINA NUCLEAR E ENDOCRINOLOGIA LTDA"
    gold_df["tp_unidade"] = 39

    _publish(postgres_engine, gold_df, "DENG", "b1")

    with postgres_engine.connect() as conn:
        row = conn.execute(
            text("SELECT nm_unidade FROM analytics.dim_unidade_saude WHERE cd_unidade = '0729884'")
        ).fetchone()

    assert row is not None
    assert row.nm_unidade == "BEDALAB"


def test_sentinela_unidade_nao_identificada_preserva_descricao_curada(postgres_engine):
    # Gold sem ID_UNIDADE -> cai no código sentinela ('0000000'). A
    # descrição "Não identificado", seedada pela migration, não pode ser
    # sobrescrita por um upsert que não a conheça.
    _publish(postgres_engine, _gold_exemplo(), "DENG", "b1")

    with postgres_engine.connect() as conn:
        row = conn.execute(
            text("SELECT nm_unidade FROM analytics.dim_unidade_saude WHERE cd_unidade = '0000000'")
        ).fetchone()

    assert row is not None
    assert row.nm_unidade == "Não identificado"


def test_upsert_dim_municipio_preserva_dados_ja_existentes(postgres_engine):
    _publish(postgres_engine, _gold_exemplo(), "DENG", "b1")

    with postgres_engine.connect() as conn:
        row = conn.execute(
            text("SELECT nm_mun, nm_uf FROM analytics.dim_municipio WHERE cd_mun = '3301009'")
        ).fetchone()

    assert row is not None
    assert row.nm_mun == "Campos dos Goytacazes"
    assert row.nm_uf == "Rio de Janeiro"


def test_snapshot_remove_grupo_que_mudou_de_classificacao(postgres_engine):
    previous = _gold_exemplo(10)
    previous["CLASSI_FIN"] = "9"
    confirmed = _gold_exemplo(5)
    confirmed["CLASSI_FIN"] = "10"
    _publish(postgres_engine, pd.concat([previous, confirmed], ignore_index=True))
    current = _gold_exemplo(15)
    current["CLASSI_FIN"] = "10"
    _publish(postgres_engine, current, batch_id="b2")
    with postgres_engine.connect() as conn:
        rows = conn.execute(text("SELECT cd_classificacao, cases_total FROM analytics.fato_casos")).all()
    assert [tuple(row) for row in rows] == [("10", 15)]


def test_snapshot_preserva_outros_anos_doencas_e_municipios(postgres_engine):
    _publish(postgres_engine, _gold_exemplo(5))
    _publish(postgres_engine, _gold_exemplo(7), "CHIK")
    older = _gold_exemplo(8)
    older["year"] = 2025
    _publish(postgres_engine, older, year=2025)
    other_city = _gold_exemplo(9)
    other_city["cd_mun"] = "3302403"
    other_city["nm_mun"] = "Macaé"
    _publish(postgres_engine, other_city, municipios=["3302403"])
    _publish(postgres_engine, _gold_exemplo(2), batch_id="b2")
    with postgres_engine.connect() as conn:
        rows = conn.execute(text("SELECT disease_codigo, ano, cd_mun, cases_total FROM analytics.fato_casos")).all()
    assert set(map(tuple, rows)) == {
        ("DENG", 2026, "3301009", 2), ("CHIK", 2026, "3301009", 7),
        ("DENG", 2025, "3301009", 8), ("DENG", 2026, "3302403", 9),
    }


def test_snapshot_remove_municipio_que_passou_a_zero(postgres_engine):
    cities = ["3301009", "3302403"]
    other = _gold_exemplo(3)
    other["cd_mun"] = "3302403"
    other["nm_mun"] = "Macaé"
    _publish(postgres_engine, pd.concat([_gold_exemplo(), other], ignore_index=True), municipios=cities)
    _publish(postgres_engine, _gold_exemplo(4), batch_id="b2", municipios=cities)
    with postgres_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM analytics.fato_casos WHERE cd_mun = '3302403'")).scalar_one() == 0
        row = conn.execute(text("SELECT cases_total, groups_total FROM analytics.pipeline_publications WHERE batch_id = 'b2' AND cd_mun = '3302403'")).one()
    assert tuple(row) == (0, 0)


def test_snapshot_repetido_nao_duplica_fatos_nem_publicacao(postgres_engine):
    _publish(postgres_engine, _gold_exemplo())
    _publish(postgres_engine, _gold_exemplo())
    with postgres_engine.connect() as conn:
        assert conn.execute(text("SELECT sum(cases_total) FROM analytics.fato_casos")).scalar_one() == 5
        assert conn.execute(text("SELECT count(*) FROM analytics.pipeline_publications")).scalar_one() == 1


def test_snapshot_vazio_bloqueado_preserva_dados(postgres_engine):
    _publish(postgres_engine, _gold_exemplo())
    with pytest.raises(ValueError, match="Gold vazia"):
        _publish(postgres_engine, _gold_exemplo().iloc[:0], batch_id="b2")
    with postgres_engine.connect() as conn:
        assert conn.execute(text("SELECT sum(cases_total) FROM analytics.fato_casos")).scalar_one() == 5


def test_snapshot_zero_validado_remove_fatos_e_bloqueia_snapshot_antigo(postgres_engine):
    initial = datetime(2026, 1, 1, tzinfo=UTC)
    _publish(postgres_engine, _gold_exemplo(), source_extracted_at=initial)
    _publish(postgres_engine, _gold_exemplo().iloc[:0], batch_id="b2", allow_empty=True,
             source_extracted_at=initial + timedelta(days=1))
    with pytest.raises(ValueError, match="antigo"):
        _publish(postgres_engine, _gold_exemplo(), batch_id="b3", source_extracted_at=initial)
    with postgres_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM analytics.fato_casos")).scalar_one() == 0
        assert conn.execute(text("SELECT count(*) FROM analytics.pipeline_publications")).scalar_one() == 2


def test_falha_apos_delete_reverte_fatos_dimensoes_e_publicacao(postgres_engine, monkeypatch):
    _publish(postgres_engine, _gold_exemplo())
    revised = _gold_exemplo(10)
    revised["ID_UNIDADE"] = "9999999"
    def fail(*args):
        raise RuntimeError("falha simulada depois do DELETE")
    monkeypatch.setattr(load_module, "insert_fato_casos", fail)
    with pytest.raises(RuntimeError, match="falha simulada"):
        _publish(postgres_engine, revised, batch_id="b2")
    with postgres_engine.connect() as conn:
        assert conn.execute(text("SELECT cases_total, batch_id FROM analytics.fato_casos")).one() == (5, "b1")
        assert conn.execute(text("SELECT count(*) FROM analytics.dim_unidade_saude WHERE cd_unidade = '9999999'")).scalar_one() == 0
        assert conn.execute(text("SELECT count(*) FROM analytics.pipeline_publications WHERE batch_id = 'b2'")).scalar_one() == 0


def test_totais_divergentes_bloqueiam_publicacao_sem_alterar_banco(postgres_engine):
    _publish(postgres_engine, _gold_exemplo())
    with pytest.raises(ValueError, match="diverge"):
        _publish(postgres_engine, _gold_exemplo(10), expected_cases_total=11, batch_id="b2")
    with postgres_engine.connect() as conn:
        assert conn.execute(text("SELECT cases_total FROM analytics.fato_casos")).scalar_one() == 5


def test_colisoes_normalizadas_sao_somadas_e_semana_preservada(postgres_engine):
    first = _gold_exemplo(2)
    first["CLASSI_FIN"] = ""
    first["SEM_NOT"] = "202602"
    second = first.copy()
    second["CLASSI_FIN"] = None
    second["cases_total"] = 3
    _publish(postgres_engine, pd.concat([first, second], ignore_index=True))
    with postgres_engine.connect() as conn:
        row = conn.execute(text("SELECT cases_total, semana_notif FROM analytics.fato_casos")).one()
    assert tuple(row) == (5, 202602)


def test_silver_gold_canonica_e_carga_preservam_notificacoes(postgres_engine):
    bronze = pd.DataFrame({
        "DT_NOTIFIC": ["20260110", "20260110"], "ID_MUNICIP": ["3301009", "3301009"],
        "SG_UF_NOT": ["33", "33"], "NU_NOTIFIC": ["1", "2"],
        "CS_SEXO": ["F", "F"], "ANO_NASC": ["1990", "1990"],
        "SEM_NOT": ["202602", "202602"], "CLASSI_FIN": ["", None], "EVOLUCAO": ["1", "1"],
    })
    silver = transform(bronze, 2026)
    gold = aggregate(silver, "DENG", CANONICAL_GOLD_COLUMNS)
    _publish(postgres_engine, gold, expected_cases_total=len(silver))
    with postgres_engine.connect() as conn:
        row = conn.execute(text("""
            SELECT cases_total, semana_notif, cd_classificacao, cd_sexo, ano_nascimento
            FROM analytics.fato_casos
        """)).one()
    assert tuple(row) == (2, 202602, "NI", "F", 1990)


def test_publicacao_mantem_snapshot_anterior_visivel_e_bloqueia_recorte(postgres_engine, monkeypatch):
    _publish(postgres_engine, _gold_exemplo())
    inserted = Event()
    release = Event()
    original_insert = load_module.insert_fato_casos
    def pause(conn, facts):
        original_insert(conn, facts)
        inserted.set()
        if not release.wait(10):
            raise RuntimeError("timeout do teste")
    monkeypatch.setattr(load_module, "insert_fato_casos", pause)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_publish, postgres_engine, _gold_exemplo(10), batch_id="b2")
        try:
            assert inserted.wait(10)
            with postgres_engine.begin() as conn:
                assert conn.execute(text("SELECT cases_total FROM analytics.fato_casos")).scalar_one() == 5
                assert conn.execute(text("SELECT pg_try_advisory_xact_lock(hashtext('nss:sinan:DENG:2026'))")).scalar_one() is False
        finally:
            release.set()
        future.result(timeout=10)
    with postgres_engine.connect() as conn:
        assert conn.execute(text("SELECT cases_total FROM analytics.fato_casos")).scalar_one() == 10
