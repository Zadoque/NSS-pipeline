"""Provisionamento idempotente da role de leitura usada pelo Grafana."""

from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.engine import Connection

_ROLE_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def validate_role_name(user: str) -> str:
    user = user.strip()
    if not _ROLE_NAME.fullmatch(user):
        raise ValueError("GRAFANA_DB_USER deve ser um identificador PostgreSQL simples")
    return user


def provision_grafana_role(connection: Connection, user: str, password: str) -> None:
    """Cria ou reconcilia a role e seus grants, sem depender do Alembic."""
    user = validate_role_name(user)
    role_literal = _quote_literal(user)
    password_literal = _quote_literal(password)
    role_identifier = _quote_identifier(user)
    database = connection.execute(text("SELECT current_database()" )).scalar_one()

    connection.execute(text(f"""
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
    """))
    connection.execute(text(f"GRANT CONNECT ON DATABASE {_quote_identifier(database)} TO {role_identifier}"))
    connection.execute(text(f"GRANT USAGE ON SCHEMA analytics TO {role_identifier}"))
    connection.execute(text(
        "GRANT SELECT ON TABLE analytics.pipeline_execution_metrics, "
        f"analytics.pipeline_publications TO {role_identifier}"
    ))
