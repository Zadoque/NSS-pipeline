"""Reprovisiona a role read-only do Grafana após restore de PostgreSQL."""

from __future__ import annotations

import os

from sqlalchemy import create_engine

from .grafana_role import provision_grafana_role


def main() -> int:
    url = os.environ.get("DATABASE_URL", "").strip()
    user = os.environ.get("GRAFANA_DB_USER", "").strip()
    password = os.environ.get("GRAFANA_DB_PASSWORD", "")
    if not url or not user or not password:
        raise SystemExit("DATABASE_URL, GRAFANA_DB_USER e GRAFANA_DB_PASSWORD são obrigatórios")
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            provision_grafana_role(connection, user, password)
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
