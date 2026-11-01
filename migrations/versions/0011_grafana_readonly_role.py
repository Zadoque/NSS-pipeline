"""Cria a role somente leitura usada pelo datasource do Grafana."""

from __future__ import annotations

import os
import re

from alembic import op
from sqlalchemy import text

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

_ROLE_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


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
    if not _ROLE_NAME.fullmatch(user):
        raise ValueError("GRAFANA_DB_USER deve ser um identificador PostgreSQL simples")
    return user, password


def upgrade() -> None:
    credentials = _credentials()
    if credentials is None:
        return
    user, password = credentials
    role_literal = _quote_literal(user)
    password_literal = _quote_literal(password)
    role_identifier = _quote_identifier(user)
    connection = op.get_bind()
    database = connection.execute(text("SELECT current_database()")).scalar_one()

    op.execute(f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {role_literal}) THEN
                EXECUTE format(
                    'CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD %L',
                    {role_literal}, {password_literal}
                );
            ELSE
                EXECUTE format(
                    'ALTER ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD %L',
                    {role_literal}, {password_literal}
                );
            END IF;
        END
        $$;
    """)
    op.execute(f"GRANT CONNECT ON DATABASE {_quote_identifier(database)} TO {role_identifier}")
    op.execute(f"GRANT USAGE ON SCHEMA analytics TO {role_identifier}")
    op.execute(
        "GRANT SELECT ON TABLE analytics.pipeline_execution_metrics, "
        f"analytics.pipeline_publications TO {role_identifier}"
    )


def downgrade() -> None:
    credentials = _credentials()
    if credentials is None:
        return
    user, _ = credentials
    role_identifier = _quote_identifier(user)
    op.execute(f"REVOKE ALL PRIVILEGES ON TABLE analytics.pipeline_execution_metrics, analytics.pipeline_publications FROM {role_identifier}")
    op.execute(f"REVOKE ALL PRIVILEGES ON SCHEMA analytics FROM {role_identifier}")
    op.execute(f"DROP ROLE IF EXISTS {role_identifier}")
