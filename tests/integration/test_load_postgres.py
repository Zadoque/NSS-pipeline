from __future__ import annotations

import os

import pandas as pd
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.pipeline.load import load_gold_to_postgres

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def postgres_engine():
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip(
            "TEST_DATABASE_URL não definida — testes de integração pulados. "
            "Ver README (seção de testes) para configurar o banco de testes."
        )

    engine = create_engine(database_url)

    # Este banco não é descartável (é um serviço Postgres persistente, não
    # um container efêmero) — reseta o schema manualmente antes de rodar
    # as migrations, para garantir estado limpo independente de execuções
    # anteriores.
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS analytics CASCADE"))
        conn.execute(text("DELETE FROM alembic_version"))

    # env.py lê DATABASE_URL do ambiente, não do Config do Alembic —
    # setar aqui garante que a migration rode contra o banco de TESTE,
    # não o de desenvolvimento.
    os.environ["DATABASE_URL"] = database_url
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")

    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def _limpar_fato_entre_testes(postgres_engine):
    """Cada teste começa com fato_casos vazio, mas preserva as dimensões
    (incluindo as linhas sentinela) — evita interferência entre testes
    sem precisar recriar o schema inteiro a cada um (lento)."""
    yield
    with postgres_engine.begin() as conn:
        conn.execute(text("TRUNCATE analytics.fato_casos"))


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


def test_load_gold_to_postgres_cria_linha_no_fato(postgres_engine):
    gold_df = _gold_exemplo(cases_total=5)
    load_gold_to_postgres(postgres_engine, gold_df, disease_codigo="DENG", batch_id="b1")

    with postgres_engine.connect() as conn:
        row = conn.execute(
            text("SELECT cases_total FROM analytics.fato_casos WHERE disease_codigo = 'DENG'")
        ).fetchone()

    assert row is not None
    assert row.cases_total == 5


def test_load_gold_to_postgres_upsert_atualiza_em_vez_de_duplicar(postgres_engine):
    # Simula o SINAN "corrigindo" o número de um período já carregado
    # anteriormente (atualização retroativa) — não deve duplicar a linha.
    load_gold_to_postgres(postgres_engine, _gold_exemplo(cases_total=5), "DENG", "b1")
    load_gold_to_postgres(postgres_engine, _gold_exemplo(cases_total=8), "DENG", "b2")

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

    load_gold_to_postgres(postgres_engine, gold_df, "DENG", "b1")

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
    load_gold_to_postgres(postgres_engine, _gold_exemplo(), "DENG", "b1")

    with postgres_engine.connect() as conn:
        row = conn.execute(
            text("SELECT nm_unidade FROM analytics.dim_unidade_saude WHERE cd_unidade = '0000000'")
        ).fetchone()

    assert row is not None
    assert row.nm_unidade == "Não identificado"


def test_upsert_dim_municipio_preserva_dados_ja_existentes(postgres_engine):
    load_gold_to_postgres(postgres_engine, _gold_exemplo(), "DENG", "b1")

    with postgres_engine.connect() as conn:
        row = conn.execute(
            text("SELECT nm_mun, nm_uf FROM analytics.dim_municipio WHERE cd_mun = '3301009'")
        ).fetchone()

    assert row is not None
    assert row.nm_mun == "Campos dos Goytacazes"
    assert row.nm_uf == "Rio de Janeiro"
