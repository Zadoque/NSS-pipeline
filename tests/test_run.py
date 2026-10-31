import pytest

from app.pipeline import run as runner
from app.pipeline.reference.ibge.catalog import InMemoryMunicipalityCatalog
from app.pipeline.reference.ibge.models import CatalogMetadata, Municipality
from app.pipeline.scope import GeographicScope


@pytest.mark.parametrize("arguments", [
    ["--municipios", "3301009", "--ufs", "RJ"],
    ["--municipios", "3301009", "--all-brazil"],
    ["--ufs", "RJ", "--all-brazil"],
])
def test_cli_run_rejeita_selecao_geografica_ambigua(arguments):
    with pytest.raises(SystemExit):
        runner._build_parser().parse_args(arguments)


def test_run_rejeita_escopo_de_catalogo_diferente(mocker):
    catalog = InMemoryMunicipalityCatalog(
        [Municipality("3301009", "330100", "Campos", "33", "RJ", "Rio", 2025)],
        CatalogMetadata("test", 2025, "fixture", "fixture://", "2026-01-01T00:00:00Z", "a" * 64),
    )
    stale_scope = GeographicScope((Municipality(
        "3301009", "330100", "Nome antigo", "33", "RJ", "Rio", 2024,
    ),))
    fetch = mocker.patch.object(runner, "fetch_sinan")

    with pytest.raises(ValueError, match="não corresponde"):
        runner.run("DENG", 2026, catalog=catalog, geographic_scope=stale_scope)

    fetch.assert_not_called()
