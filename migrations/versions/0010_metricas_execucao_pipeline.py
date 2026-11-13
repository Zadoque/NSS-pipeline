"""Separa métricas globais do grão municipal de publicação."""
from alembic import op


revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE analytics.pipeline_execution_metrics (
            disease_codigo VARCHAR(4) NOT NULL REFERENCES analytics.dim_doenca(codigo),
            ano SMALLINT NOT NULL,
            batch_id VARCHAR(20) NOT NULL,
            source_extracted_at TIMESTAMPTZ NOT NULL,
            published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            geographic_scope_type VARCHAR(30) NOT NULL,
            geographic_scope_sha256 VARCHAR(64) NOT NULL,
            ibge_catalog_id VARCHAR(100),
            ibge_catalog_sha256 VARCHAR(64),
            source_rows BIGINT NOT NULL CHECK (source_rows >= 0),
            resolved_rows BIGINT NOT NULL CHECK (resolved_rows >= 0),
            discarded_rows BIGINT NOT NULL CHECK (discarded_rows >= 0),
            aggregation_reduction BIGINT NOT NULL CHECK (aggregation_reduction >= 0),
            invalid_municipality_rows BIGINT NOT NULL CHECK (invalid_municipality_rows >= 0),
            out_of_scope_rows BIGINT NOT NULL CHECK (out_of_scope_rows >= 0),
            uf_mismatch_rows BIGINT NOT NULL CHECK (uf_mismatch_rows >= 0),
            PRIMARY KEY (disease_codigo, ano, batch_id)
        )
    """)
    op.execute("""
        CREATE INDEX idx_pipeline_execution_metrics_recorte_data
        ON analytics.pipeline_execution_metrics
            (disease_codigo, ano, source_extracted_at DESC)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE analytics.pipeline_execution_metrics")
