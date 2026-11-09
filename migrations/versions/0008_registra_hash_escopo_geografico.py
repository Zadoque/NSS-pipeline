"""Registra o hash determinístico do recorte municipal publicado."""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE analytics.pipeline_publications
        ADD COLUMN geographic_scope_sha256 VARCHAR(64)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE analytics.pipeline_publications
        DROP COLUMN geographic_scope_sha256
    """)
