"""Catálogo municipal versionado baseado em fontes oficiais do IBGE."""

from .catalog import InMemoryMunicipalityCatalog, ParquetMunicipalityCatalog
from .historical import (
    MunicipalityEvent,
    require_event_references,
    validate_event_references,
    derive_annual_events,
    download_historical_source,
    parse_administrative_events,
    parse_toponymic_events,
    promote_administrative_events,
    promote_historical_source,
    promote_toponymic_events,
)
from .models import (
    CatalogMetadata,
    CatalogValidationReport,
    Municipality,
    HistoricalReferenceValidationReport,
    MunicipalityCatalog,
    ResolutionResult,
    ResolutionStatus,
)
from .validation import validate_national_municipalities

__all__ = [
    "CatalogMetadata",
    "CatalogValidationReport",
    "InMemoryMunicipalityCatalog",
    "Municipality",
    "MunicipalityCatalog",
    "ParquetMunicipalityCatalog",
    "MunicipalityEvent",
    "HistoricalReferenceValidationReport",
    "derive_annual_events",
    "download_historical_source",
    "parse_administrative_events",
    "promote_administrative_events",
    "promote_historical_source",
    "parse_toponymic_events",
    "promote_toponymic_events",
    "require_event_references",
    "validate_event_references",
    "ResolutionResult",
    "ResolutionStatus",
    "validate_national_municipalities",
]
