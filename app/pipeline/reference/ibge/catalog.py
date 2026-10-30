from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .models import CatalogMetadata, Municipality, ResolutionResult, ResolutionStatus
from .validation import CODE6, CODE7, validate_municipalities


def _as_municipality(row: object) -> Municipality:
    if isinstance(row, pd.Series):
        values = row.to_dict()
    else:
        values = dict(row)
    return Municipality(
        code7=str(values["code7"]),
        code6=str(values["code6"]),
        name=str(values["name"]),
        uf_code=str(values["uf_code"]),
        uf_abbr=str(values["uf_abbr"]),
        uf_name=str(values["uf_name"]),
        reference_year=int(values["reference_year"]),
        source=str(values.get("source", "IBGE_DTB")),
    )


class InMemoryMunicipalityCatalog:
    def __init__(self, records: list[Municipality] | tuple[Municipality, ...], metadata: CatalogMetadata):
        self._records = validate_municipalities(records)
        self.metadata = metadata
        self._by_code7 = {item.code7: item for item in self._records}
        self._by_code6 = {item.code6: item for item in self._records}

    def municipalities(self) -> tuple[Municipality, ...]:
        return self._records

    def get_municipality(self, code7: str) -> Municipality | None:
        return self._by_code7.get(str(code7))

    def resolve(self, value: object, declared_uf: str | None = None) -> ResolutionResult:
        original = "" if value is None else str(value).strip()
        raw = re.sub(r"\D", "", original)
        if not raw or raw != original:
            return ResolutionResult(original, None, ResolutionStatus.INVALID_FORMAT, reason="código não numérico")

        candidate: Municipality | None = None
        input_format: str | None = None
        if CODE6.fullmatch(raw):
            input_format = "CODE6"
            candidate = self._by_code6.get(raw)
        elif len(raw) == 7 and raw.startswith("0") and raw[1:] in self._by_code6:
            input_format = "LEGACY_CODE6"
            candidate = self._by_code6[raw[1:]]
        elif CODE7.fullmatch(raw):
            input_format = "CODE7"
            candidate = self._by_code7.get(raw)
        else:
            return ResolutionResult(original, None, ResolutionStatus.INVALID_FORMAT, reason="formato esperado: 6 ou 7 dígitos")

        if candidate is None:
            return ResolutionResult(original, input_format, ResolutionStatus.UNKNOWN_CODE, reason="código ausente no catálogo")
        if declared_uf and str(declared_uf).strip().upper() not in {candidate.uf_code, candidate.uf_abbr.upper()}:
            return ResolutionResult(original, input_format, ResolutionStatus.UF_MISMATCH, candidate, "UF declarada diverge do catálogo")
        return ResolutionResult(original, input_format, ResolutionStatus.VALID, candidate)


class ParquetMunicipalityCatalog(InMemoryMunicipalityCatalog):
    def __init__(self, path: Path, metadata: CatalogMetadata):
        frame = pd.read_parquet(path)
        records = [_as_municipality(row) for _, row in frame.iterrows()]
        super().__init__(records, metadata)
