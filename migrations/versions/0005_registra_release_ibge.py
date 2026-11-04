"""Registra a release territorial usada em cada publicação.

Revision ID: 0006
Revises: 0005
"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE analytics.reference_catalog_releases (
            catalog_id VARCHAR(100) PRIMARY KEY,
            sha256 VARCHAR(64) NOT NULL,
            reference_year SMALLINT NOT NULL,
            source_name VARCHAR(200) NOT NULL,
            source_url VARCHAR(500) NOT NULL,
            retrieved_at TIMESTAMPTZ NOT NULL,
            registered_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        ALTER TABLE analytics.pipeline_publications
        ADD COLUMN ibge_catalog_id VARCHAR(100)
            REFERENCES analytics.reference_catalog_releases(catalog_id),
        ADD COLUMN ibge_catalog_sha256 VARCHAR(64),
        ADD COLUMN geographic_scope_type VARCHAR(30) NOT NULL DEFAULT 'MUNICIPALITIES'
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE analytics.pipeline_publications
        DROP COLUMN geographic_scope_type,
        DROP COLUMN ibge_catalog_sha256,
        DROP COLUMN ibge_catalog_id
    """)
    op.execute("DROP TABLE analytics.reference_catalog_releases")
