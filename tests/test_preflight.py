import pytest

from app.pipeline.preflight import validate_production_environment


def _environment(**overrides):
    values = {
        "POSTGRES_USER": "nss_prod",
        "POSTGRES_PASSWORD": "strong-db-secret",
        "POSTGRES_DB": "nss",
        "GRAFANA_ADMIN_USER": "grafana_ops",
        "GRAFANA_ADMIN_PASSWORD": "strong-grafana-secret",
        "DATABASE_URL": "postgresql+psycopg2://nss_prod:secret@db:5432/nss",
    }
    values.update(overrides)
    return values


def test_preflight_retorna_apenas_resumo_sem_secrets():
    result = validate_production_environment(_environment())

    assert result == {
        "database_host": "db",
        "database_name": "nss",
        "grafana_admin_user": "grafana_ops",
    }
    assert "secret" not in repr(result)


def test_preflight_agrega_variaveis_ausentes_e_credenciais_locais():
    with pytest.raises(ValueError, match="POSTGRES_USER ausente") as error:
        validate_production_environment(_environment(
            POSTGRES_USER="",
            POSTGRES_PASSWORD="postgres",
            GRAFANA_ADMIN_PASSWORD="admin",
            DATABASE_URL="sqlite:///local.db",
        ))

    message = str(error.value)
    assert "credencial local conhecida" in message
    assert "DATABASE_URL deve usar" in message


def test_preflight_rejeita_variavel_obrigatoria_ausente():
    values = _environment()
    del values["GRAFANA_ADMIN_PASSWORD"]

    with pytest.raises(ValueError, match="GRAFANA_ADMIN_PASSWORD ausente"):
        validate_production_environment(values)
