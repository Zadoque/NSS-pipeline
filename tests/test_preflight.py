import pytest

from app.pipeline.preflight import validate_production_environment


def _environment(**overrides):
    values = {
        "POSTGRES_USER": "nss_prod",
        "POSTGRES_PASSWORD": "strong-db-secret",
        "POSTGRES_DB": "nss",
        "GRAFANA_ADMIN_USER": "grafana_ops",
        "GRAFANA_ADMIN_PASSWORD": "strong-grafana-secret",
        "GRAFANA_DB_USER": "grafana_ro",
        "GRAFANA_DB_PASSWORD": "strong-grafana-db-secret",
        "DATABASE_URL": "postgresql+psycopg2://nss_prod:secret@db:5432/nss",
        "PROMETHEUS_PUSHGATEWAY_URL": "http://pushgateway:9091",
        "NSS_PIPELINE_IMAGE": "registry.example/nss-pipeline@sha256:" + "a" * 64,
    }
    values.update(overrides)
    return values


def test_preflight_retorna_apenas_resumo_sem_secrets():
    result = validate_production_environment(_environment())

    assert result == {
        "database_host": "db",
        "database_name": "nss",
        "grafana_admin_user": "grafana_ops",
        "pipeline_image": "registry.example/nss-pipeline@sha256:" + "a" * 64,
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


def test_preflight_usa_os_environment_quando_mapa_nao_e_informado(monkeypatch):
    for name, value in _environment().items():
        monkeypatch.setenv(name, value)

    assert validate_production_environment()["database_host"] == "db"


@pytest.mark.parametrize("name", ["POSTGRES_PASSWORD", "GRAFANA_ADMIN_PASSWORD", "GRAFANA_DB_PASSWORD"])
def test_preflight_rejeita_cada_credencial_local(monkeypatch, name):
    values = _environment(**{name: "admin"})

    with pytest.raises(ValueError, match=f"{name} usa credencial local conhecida"):
        validate_production_environment(values)


@pytest.mark.parametrize("name", ["GRAFANA_DB_USER", "GRAFANA_DB_PASSWORD"])
def test_preflight_rejeita_reuso_de_credencial_administrativa(name):
    source = "POSTGRES_USER" if name.endswith("USER") else "POSTGRES_PASSWORD"
    values = _environment(**{name: _environment()[source]})

    with pytest.raises(ValueError, match=f"{name} não pode"):
        validate_production_environment(values)


@pytest.mark.parametrize("name", [
    "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB",
    "GRAFANA_ADMIN_USER", "GRAFANA_ADMIN_PASSWORD", "GRAFANA_DB_USER",
    "GRAFANA_DB_PASSWORD", "DATABASE_URL",
    "PROMETHEUS_PUSHGATEWAY_URL",
    "NSS_PIPELINE_IMAGE",
])
def test_preflight_rejeita_cada_variavel_obrigatoria(name):
    values = _environment()
    values.pop(name)

    with pytest.raises(ValueError) as error:
        validate_production_environment(values)

    assert str(error.value) == f"preflight de produção falhou: {name} ausente"


@pytest.mark.parametrize("database_url", [
    "sqlite:///local.db",
    "postgresql+psycopg2:///nss",
])
def test_preflight_rejeita_url_de_banco_invalida(database_url):
    with pytest.raises(ValueError) as error:
        validate_production_environment(_environment(DATABASE_URL=database_url))

    assert str(error.value) == (
        "preflight de produção falhou: "
        "DATABASE_URL deve usar postgresql+psycopg2 com host"
    )


@pytest.mark.parametrize("pushgateway_url", ["pushgateway:9091", "ftp://pushgateway:9091"])
def test_preflight_rejeita_url_do_pushgateway_invalida(pushgateway_url):
    with pytest.raises(ValueError) as error:
        validate_production_environment(
            _environment(PROMETHEUS_PUSHGATEWAY_URL=pushgateway_url)
        )

    assert str(error.value) == (
        "preflight de produção falhou: "
        "PROMETHEUS_PUSHGATEWAY_URL deve usar http(s) com host"
    )


@pytest.mark.parametrize("pipeline_image", [
    "nss pipeline:ci", "nss-pipeline:latest", "nss-pipeline:" + "a" * 40,
])
def test_preflight_rejeita_imagem_mutavel_ou_invalida(pipeline_image):
    with pytest.raises(ValueError, match="NSS_PIPELINE_IMAGE deve usar digest OCI SHA-256"):
        validate_production_environment(_environment(NSS_PIPELINE_IMAGE=pipeline_image))


def test_preflight_reconcilia_todos_os_erros_com_separador_estavel():
    values = _environment(POSTGRES_PASSWORD="admin")
    values.pop("DATABASE_URL")

    with pytest.raises(ValueError) as error:
        validate_production_environment(values)

    assert str(error.value) == (
        "preflight de produção falhou: "
        "DATABASE_URL ausente; POSTGRES_PASSWORD usa credencial local conhecida"
    )
