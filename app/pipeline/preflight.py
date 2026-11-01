"""Validações seguras antes de subir o overlay de produção.

O preflight não testa conectividade nem imprime secrets; ele apenas impede que
o overlay seja montado com variáveis ausentes ou com credenciais locais
conhecidas. Conectividade, migrations e healthchecks continuam sendo validados
pelos comandos do runbook e pelo smoke test do Compose.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from urllib.parse import urlparse

REQUIRED_VARIABLES = (
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "GRAFANA_ADMIN_USER",
    "GRAFANA_ADMIN_PASSWORD",
    "DATABASE_URL",
    "PROMETHEUS_PUSHGATEWAY_URL",
    "NSS_PIPELINE_IMAGE",
)

_KNOWN_LOCAL_PASSWORDS = frozenset({
    "postgres",
    "admin",
    "test_pass",
    "ci_password",
    "ci_grafana_password",
})


def validate_production_environment(
    environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Retorna um resumo sem secrets ou levanta erro com todos os problemas."""
    values = os.environ if environment is None else environment
    errors: list[str] = []

    for name in REQUIRED_VARIABLES:
        if not values.get(name, "").strip():
            errors.append(f"{name} ausente")

    for name in ("POSTGRES_PASSWORD", "GRAFANA_ADMIN_PASSWORD"):
        if name in values and values[name].strip() in _KNOWN_LOCAL_PASSWORDS:
            errors.append(f"{name} usa credencial local conhecida")

    database_url = values.get("DATABASE_URL", "").strip()
    parsed = urlparse(database_url)
    if database_url and (parsed.scheme != "postgresql+psycopg2" or not parsed.hostname):
        errors.append("DATABASE_URL deve usar postgresql+psycopg2 com host")

    pushgateway_url = values.get("PROMETHEUS_PUSHGATEWAY_URL", "").strip()
    parsed_pushgateway = urlparse(pushgateway_url)
    if pushgateway_url and (
        parsed_pushgateway.scheme not in {"http", "https"}
        or not parsed_pushgateway.hostname
    ):
        errors.append(
            "PROMETHEUS_PUSHGATEWAY_URL deve usar http(s) com host"
        )

    pipeline_image = values.get("NSS_PIPELINE_IMAGE", "").strip()
    if pipeline_image and any(character.isspace() for character in pipeline_image):
        errors.append("NSS_PIPELINE_IMAGE não pode conter espaços")

    if errors:
        raise ValueError("preflight de produção falhou: " + "; ".join(errors))

    assert parsed.hostname is not None  # garantido pela validação acima
    return {
        "database_host": parsed.hostname,
        "database_name": values["POSTGRES_DB"].strip(),
        "grafana_admin_user": values["GRAFANA_ADMIN_USER"].strip(),
        "pipeline_image": pipeline_image,
    }


def main() -> int:
    try:
        summary = validate_production_environment()
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(
        "preflight de produção aprovado: "
        f"database_host={summary['database_host']} "
        f"database_name={summary['database_name']} "
        f"grafana_admin_user={summary['grafana_admin_user']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
