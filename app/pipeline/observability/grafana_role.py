"""Provisionamento idempotente da role de leitura usada pelo Grafana."""

from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.engine import Connection

_ROLE_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")


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
    role_identifier = _quote_identifier(user)
    database = connection.execute(text("SELECT current_database()")).scalar_one()
    password_literal = connection.execute(
        text("SELECT quote_literal(:password)"), {"password": password}
    ).scalar_one()
    role_exists = connection.execute(
        text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": user}
    ).first() is not None
    role_statement = "ALTER ROLE" if role_exists else "CREATE ROLE"
    connection.execute(text(
        f"{role_statement} {role_identifier} LOGIN NOSUPERUSER NOCREATEDB "
        f"NOCREATEROLE NOINHERIT PASSWORD {password_literal}"
    ))
    connection.execute(text(f"GRANT CONNECT ON DATABASE {_quote_identifier(database)} TO {role_identifier}"))
    connection.execute(text(f"GRANT USAGE ON SCHEMA analytics TO {role_identifier}"))
    connection.execute(text(
        "GRANT SELECT ON TABLE analytics.pipeline_execution_metrics, "
        f"analytics.pipeline_publications TO {role_identifier}"
    ))
