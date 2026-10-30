from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class ResolutionStatus(StrEnum):
    VALID = "VALID"
    INVALID_FORMAT = "INVALID_FORMAT"
    UNKNOWN_CODE = "UNKNOWN_CODE"
    HISTORICAL_UNRESOLVED = "HISTORICAL_UNRESOLVED"
    UF_MISMATCH = "UF_MISMATCH"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


@dataclass(frozen=True)
class Municipality:
    code7: str
    code6: str
    name: str
    uf_code: str
    uf_abbr: str
    uf_name: str
    reference_year: int
    source: str = "IBGE_DTB"
    administrative_type: str = "MUNICIPALITY"


@dataclass(frozen=True)
class CatalogMetadata:
    catalog_id: str
    reference_year: int
    source_name: str
    source_url: str
    retrieved_at: str
    sha256: str
    schema_version: str = "1.0"
    validation_status: str = "VALIDATED"


@dataclass(frozen=True)
class CatalogValidationReport:
    valid: bool
    municipality_count: int
    uf_count: int
    code6_count: int
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolutionResult:
    original_code: str
    input_format: str | None
    status: ResolutionStatus
    municipality: Municipality | None = None
    reason: str | None = None


class MunicipalityCatalog(Protocol):
    metadata: CatalogMetadata

    def get_municipality(self, code7: str) -> Municipality | None: ...

    def resolve(self, value: object, declared_uf: str | None = None) -> ResolutionResult: ...

    def municipalities(self) -> tuple[Municipality, ...]: ...

    def validate(self) -> CatalogValidationReport: ...
