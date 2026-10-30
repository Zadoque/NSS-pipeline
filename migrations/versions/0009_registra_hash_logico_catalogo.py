"""Registra o hash lógico dos registros da release IBGE."""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE analytics.reference_catalog_releases
        ADD COLUMN content_sha256 VARCHAR(64)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE analytics.reference_catalog_releases
        DROP COLUMN content_sha256
    """)
