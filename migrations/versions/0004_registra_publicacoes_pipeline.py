"""Registra snapshots publicados, inclusive municípios sem notificações.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-05
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE analytics.pipeline_publications (
            disease_codigo VARCHAR(4) NOT NULL REFERENCES analytics.dim_doenca(codigo),
            ano SMALLINT NOT NULL,
            cd_mun CHAR(7) NOT NULL,
            batch_id VARCHAR(20) NOT NULL,
            source_extracted_at TIMESTAMPTZ NOT NULL,
            published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            groups_total BIGINT NOT NULL CHECK (groups_total >= 0),
            cases_total BIGINT NOT NULL CHECK (cases_total >= 0),
            PRIMARY KEY (disease_codigo, ano, cd_mun, batch_id)
        )
    """)
    op.execute("""
        CREATE INDEX idx_pipeline_publications_recorte_data
        ON analytics.pipeline_publications (disease_codigo, ano, cd_mun, source_extracted_at DESC)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE analytics.pipeline_publications")
