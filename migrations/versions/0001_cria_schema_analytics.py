"""
Revision ID: 0001
Revises:
Create Date: 2026-09-21

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS analytics")

    op.execute("""
        CREATE TABLE analytics.dim_doenca (
            codigo      VARCHAR(4)   PRIMARY KEY,
            nome        VARCHAR(50)  NOT NULL
        )
    """)
 
    op.execute("""
        CREATE TABLE analytics.dim_municipio (
            cd_mun      CHAR(7)      PRIMARY KEY,
            nm_mun      VARCHAR(100) NOT NULL,
            cd_uf       CHAR(2)      NOT NULL,
            nm_uf       VARCHAR(50)  NOT NULL
        )
    """)
 
    op.execute("""
        CREATE TABLE analytics.dim_unidade_saude (
            cd_unidade      CHAR(7)      PRIMARY KEY,
            nm_unidade      VARCHAR(200),
            razao_social    VARCHAR(200),
            tp_unidade      SMALLINT,
            cd_mun          CHAR(7)      REFERENCES analytics.dim_municipio(cd_mun)
        )
    """)
 
    op.execute("""
        CREATE TABLE analytics.dim_classificacao (
            codigo      VARCHAR(2)   PRIMARY KEY,
            descricao   VARCHAR(100) NOT NULL
        )
    """)
 
    op.execute("""
        CREATE TABLE analytics.dim_evolucao (
            codigo      VARCHAR(2)   PRIMARY KEY,
            descricao   VARCHAR(100) NOT NULL
        )
    """)
    
    op.execute("""
        INSERT INTO analytics.dim_unidade_saude (cd_unidade, nm_unidade)
        VALUES ('0000000', 'Não identificado')
    """)
    op.execute("""
        INSERT INTO analytics.dim_classificacao (codigo, descricao)
        VALUES ('NI', 'Não informado')
    """)
    op.execute("""
        INSERT INTO analytics.dim_evolucao (codigo, descricao)
        VALUES ('NI', 'Não informado')
    """)

    op.execute("""
        CREATE TABLE analytics.fato_casos (
            id                  BIGSERIAL    PRIMARY KEY,
            disease_codigo      VARCHAR(4)   NOT NULL REFERENCES analytics.dim_doenca(codigo),
            ano                 SMALLINT     NOT NULL,
            mes                 SMALLINT     NOT NULL,
            cd_mun              CHAR(7)      NOT NULL REFERENCES analytics.dim_municipio(cd_mun),
            cd_unidade          CHAR(7)      NOT NULL REFERENCES analytics.dim_unidade_saude(cd_unidade) DEFAULT '0000000',
            cd_classificacao    VARCHAR(2)   NOT NULL REFERENCES analytics.dim_classificacao(codigo) DEFAULT 'NI',
            cd_evolucao         VARCHAR(2)   NOT NULL REFERENCES analytics.dim_evolucao(codigo) DEFAULT 'NI',
            cases_total         INTEGER      NOT NULL,
            batch_id            VARCHAR(20)  NOT NULL,
            loaded_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),
 
            UNIQUE (disease_codigo, ano, mes, cd_mun, cd_unidade, cd_classificacao, cd_evolucao)
        )
    """)
 
    op.execute("""
        CREATE INDEX idx_fato_casos_municipio_ano_mes
        ON analytics.fato_casos (cd_mun, ano, mes)
    """)
    op.execute("""
        CREATE INDEX idx_fato_casos_doenca
        ON analytics.fato_casos (disease_codigo)
    """)
 
 
def downgrade() -> None:
    op.execute("DROP SCHEMA analytics CASCADE")
 