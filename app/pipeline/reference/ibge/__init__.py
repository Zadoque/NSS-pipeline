"""Catálogo municipal versionado baseado em fontes oficiais do IBGE."""

from .catalog import InMemoryMunicipalityCatalog, ParquetMunicipalityCatalog
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
    "ResolutionResult",
    "ResolutionStatus",
]
