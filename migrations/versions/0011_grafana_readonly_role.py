"""Cria a role somente leitura usada pelo datasource do Grafana."""

from __future__ import annotations

import os
from alembic import op

from app.pipeline.observability.grafana_role import provision_grafana_role

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

def _credentials() -> tuple[str, str] | None:
    user = os.environ.get("GRAFANA_DB_USER", "").strip()
    password = os.environ.get("GRAFANA_DB_PASSWORD", "")
    if not user and not password:
        # Local integration tests do not provision Grafana and may run the
        # migrations with only TEST_DATABASE_URL.
        return None
    if not user or not password:
        raise RuntimeError(
            "GRAFANA_DB_USER e GRAFANA_DB_PASSWORD devem ser fornecidos juntos"
        )
    return user, password


def upgrade() -> None:
    credentials = _credentials()
    if credentials is None:
        return
    provision_grafana_role(op.get_bind(), *credentials)


def downgrade() -> None:
    credentials = _credentials()
    if credentials is None:
        return
    user, _ = credentials
    role_identifier = '"' + user.replace('"', '""') + '"'
    op.execute(f"REVOKE ALL PRIVILEGES ON TABLE analytics.pipeline_execution_metrics, analytics.pipeline_publications FROM {role_identifier}")
    op.execute(f"REVOKE ALL PRIVILEGES ON SCHEMA analytics FROM {role_identifier}")
    op.execute(f"DROP ROLE IF EXISTS {role_identifier}")
