"""Registra métricas de reconciliação da Gold por publicação.

Revision ID: 0007
Revises: 0006
"""
from alembic import op


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE analytics.pipeline_publications
        ADD COLUMN source_rows BIGINT NOT NULL DEFAULT 0 CHECK (source_rows >= 0),
        ADD COLUMN resolved_rows BIGINT NOT NULL DEFAULT 0 CHECK (resolved_rows >= 0),
        ADD COLUMN discarded_rows BIGINT NOT NULL DEFAULT 0 CHECK (discarded_rows >= 0),
        ADD COLUMN aggregation_reduction BIGINT NOT NULL DEFAULT 0 CHECK (aggregation_reduction >= 0),
        ADD COLUMN invalid_municipality_rows BIGINT NOT NULL DEFAULT 0 CHECK (invalid_municipality_rows >= 0),
        ADD COLUMN out_of_scope_rows BIGINT NOT NULL DEFAULT 0 CHECK (out_of_scope_rows >= 0),
        ADD COLUMN uf_mismatch_rows BIGINT NOT NULL DEFAULT 0 CHECK (uf_mismatch_rows >= 0)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE analytics.pipeline_publications
        DROP COLUMN uf_mismatch_rows,
        DROP COLUMN out_of_scope_rows,
        DROP COLUMN invalid_municipality_rows,
        DROP COLUMN aggregation_reduction,
        DROP COLUMN discarded_rows,
        DROP COLUMN resolved_rows,
        DROP COLUMN source_rows
    """)
