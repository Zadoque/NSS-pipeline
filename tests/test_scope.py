import pytest

from app.pipeline.scope import GeographicScope, scope_sha256, select_scope
from app.pipeline.reference.ibge.catalog import InMemoryMunicipalityCatalog
from app.pipeline.reference.ibge.models import CatalogMetadata, Municipality


def _municipality(code7: str) -> Municipality:
    return Municipality(code7, code7[:6], "Município", code7[:2], "RJ", "Rio", 2025)


def test_scope_hash_is_order_independent_and_canonical():
    first = scope_sha256(["3550308", "3301009"])
    second = scope_sha256(["3301009", "3550308", "3301009"])
    assert first == second
    assert len(first) == 64


def test_geographic_scope_exposes_hash_of_its_codes():
    scope = GeographicScope((_municipality("3550308"), _municipality("3301009")))
    assert scope.sha256 == scope_sha256(scope.codes7)


def test_scope_hash_rejects_non_municipal_codes():
    with pytest.raises(ValueError, match="7 dígitos"):
        scope_sha256(["330100"])


def test_select_scope_rejects_duplicate_municipalities():
    catalog = InMemoryMunicipalityCatalog(
        [_municipality("3301009")],
        CatalogMetadata("test", 2025, "fixture", "fixture://", "2026-01-01T00:00:00Z", "a" * 64),
    )
    with pytest.raises(ValueError, match="duplicado"):
        select_scope(catalog, municipalities=["3301009", "3301009"])
