"""Mantém a publicação corrente de cada recorte para consumo transacional."""

from __future__ import annotations

import os

from alembic import op


revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def _identifier(value: str) -> str:
    if not value or not value.replace("_", "a").isalnum() or value[0].isdigit():
        raise RuntimeError("identificador de role Grafana inválido")
    return '"' + value.replace('"', '""') + '"'


def upgrade() -> None:
    op.execute("""
        CREATE TABLE analytics.pipeline_current_publication (
            disease_codigo VARCHAR(4) NOT NULL REFERENCES analytics.dim_doenca(codigo),
            ano SMALLINT NOT NULL,
            cd_mun CHAR(7) NOT NULL REFERENCES analytics.dim_municipio(cd_mun),
            batch_id VARCHAR(20) NOT NULL,
            source_extracted_timestamp TIMESTAMPTZ NOT NULL,
            added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (disease_codigo, ano, cd_mun)
        )
    """)
    op.execute("""
        CREATE INDEX idx_pipeline_current_publication_batch
        ON analytics.pipeline_current_publication (disease_codigo, ano, batch_id)
    """)
    role = os.environ.get("GRAFANA_DB_USER", "").strip()
    if role:
        op.execute(
            "GRANT SELECT ON TABLE analytics.pipeline_current_publication TO "
            + _identifier(role)
        )


def downgrade() -> None:
    role = os.environ.get("GRAFANA_DB_USER", "").strip()
    if role:
        op.execute(
            "REVOKE ALL PRIVILEGES ON TABLE analytics.pipeline_current_publication FROM "
            + _identifier(role)
        )
    op.execute("DROP TABLE analytics.pipeline_current_publication")
