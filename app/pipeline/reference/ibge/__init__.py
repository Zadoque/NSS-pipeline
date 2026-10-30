"""Catálogo municipal versionado baseado em fontes oficiais do IBGE."""

from .catalog import InMemoryMunicipalityCatalog, ParquetMunicipalityCatalog
from .historical import (
    MunicipalityEvent,
    derive_annual_events,
    parse_administrative_events,
    parse_toponymic_events,
    promote_administrative_events,
    promote_toponymic_events,
)
from .models import (
    CatalogMetadata,
    Municipality,
    MunicipalityCatalog,
    ResolutionResult,
    ResolutionStatus,
)

__all__ = [
    "CatalogMetadata",
    "InMemoryMunicipalityCatalog",
    "Municipality",
    "MunicipalityCatalog",
    "ParquetMunicipalityCatalog",
    "MunicipalityEvent",
    "derive_annual_events",
    "parse_administrative_events",
    "promote_administrative_events",
    "parse_toponymic_events",
    "promote_toponymic_events",
    "ResolutionResult",
    "ResolutionStatus",
]
