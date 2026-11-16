from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
import hashlib
import json
import re

import pandas as pd

from ...atomic_io import write_json_atomic
from .history_events import (
    MunicipalityEvent,
    derive_annual_event_series,
    parse_toponymic_events,
)
from .history_validation import require_event_references
from .history_source import (
    ADMINISTRATIVE_EVENT_TYPES,
    CODE7_PATTERN,
    SHA256_PATTERN,
    _event_id,
    _validate_manifest_sources,
)
from .history_storage import _read_events, write_events

def _promote_events(
    root: Path,
    events: list[MunicipalityEvent],
    *,
    source_path: Path,
    reference_year: int,
    source_url: str | None,
) -> Path:
    result_path = root / "historical" / "municipality_events.parquet"
    existing = {event.event_id: event for event in _read_events(result_path)}
    for event in events:
        previous = existing.get(event.event_id)
        if previous is not None and previous != event:
            raise ValueError(f"event_id conflitante no histórico municipal: {event.event_id}")
        existing[event.event_id] = event
    merged = list(existing.values())
    result = write_events(result_path, merged)
    manifest_path = result.parent / "municipality_events.manifest.json"
    previous: dict[str, object] = {}
    if manifest_path.exists():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"manifesto histórico inválido: {manifest_path}") from exc
        if not isinstance(loaded, dict):
            raise ValueError(f"manifesto histórico inválido: {manifest_path}")
        previous = loaded

    sources: list[dict[str, object]] = []
    old_sources = previous.get("sources", [])
    sources.extend(_validate_manifest_sources(old_sources))
    # Compatibilidade com manifestos criados antes do campo ``sources``.
    if not sources and previous.get("source_path"):
        sources.append({
            "reference_year": previous.get("reference_year"),
            "source_path": previous.get("source_path"),
            "source_url": previous.get("source_url"),
            "sha256": previous.get("sha256"),
        })
    source_entry = {
        "reference_year": reference_year,
        "source_path": str(source_path),
        "source_url": source_url,
        "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
    }
    source_key = (source_entry["reference_year"], source_entry["source_path"], source_entry["sha256"])
    known_keys = {
        (item.get("reference_year"), item.get("source_path"), item.get("sha256"))
        for item in sources
    }
    if source_key not in known_keys:
        sources.append(source_entry)

    manifest = {
        "reference_year": reference_year,
        "rows": len(merged),
        "event_types": sorted({event.event_type for event in merged}),
        "inference_policy": "EXPLICIT_SOURCE_ONLY",
        "sources": sorted(
            sources,
            key=lambda item: (str(item.get("reference_year")), str(item.get("source_path"))),
        ),
    }
    write_json_atomic(manifest, manifest_path)
    return result


def parse_administrative_events(
    source_path: Path,
    *,
    reference_year: int,
    source_url: str | None = None,
) -> list[MunicipalityEvent]:
    """Lê eventos territoriais explicitamente declarados por uma fonte oficial.

    O arquivo precisa declarar ``EVENT_TYPE``, ``EFFECTIVE_DATE`` e os códigos
    ``SOURCE_CODE7``/``TARGET_CODE7`` quando aplicáveis. Nenhuma relação entre
    códigos é inferida por nome, prefixo ou proximidade geográfica.
    """
    suffix = source_path.suffix.lower()
    if suffix not in {".csv", ".xls", ".xlsx", ".ods"}:
        raise ValueError(f"formato de eventos administrativos não suportado: {suffix}")
    frame = pd.read_csv(source_path, dtype=str) if suffix == ".csv" else pd.read_excel(source_path, dtype=str)
    required = {"EVENT_TYPE", "EFFECTIVE_DATE"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"colunas ausentes nos eventos administrativos: {sorted(missing)}")
    events = []
    for index, row in frame.fillna("").iterrows():
        event_type = str(row["EVENT_TYPE"]).strip().upper()
        if event_type not in ADMINISTRATIVE_EVENT_TYPES:
            raise ValueError(f"tipo de evento administrativo inválido, linha {index + 2}")
        effective = pd.to_datetime(row["EFFECTIVE_DATE"], errors="coerce")
        if pd.isna(effective):
            raise ValueError(f"data de vigência inválida, linha {index + 2}")
        source_code = str(row.get("SOURCE_CODE7", "")).strip() or None
        target_code = str(row.get("TARGET_CODE7", "")).strip() or None
        for field, code in (("SOURCE_CODE7", source_code), ("TARGET_CODE7", target_code)):
            if code is not None and not CODE7_PATTERN.fullmatch(code):
                raise ValueError(f"{field} inválido, linha {index + 2}: esperado geocódigo de 7 dígitos")
        if event_type in {"CREATION", "SUCCESSION", "MERGER", "SPLIT"} and not target_code:
            raise ValueError(f"TARGET_CODE7 ausente, linha {index + 2}")
        if event_type in {"EXTINCTION", "SUCCESSION", "MERGER", "SPLIT"} and not source_code:
            raise ValueError(f"SOURCE_CODE7 ausente, linha {index + 2}")
        event_id = _event_id(
            reference_year, event_type, effective.date(), source_code, target_code,
        )
        events.append(MunicipalityEvent(
            event_id=event_id,
            event_type=event_type,
            effective_date=effective.date().isoformat(),
            source_code7=source_code,
            target_code7=target_code,
            source_name=str(row.get("SOURCE_NAME", "")).strip() or None,
            target_name=str(row.get("TARGET_NAME", "")).strip() or None,
            source=source_url or f"IBGE_EVENTOS_ADMINISTRATIVOS_{reference_year}",
        ))
    if not events:
        raise ValueError("histórico administrativo vazio")
    return events


def promote_administrative_events(
    root: Path,
    source_path: Path,
    *,
    reference_year: int,
    source_url: str | None = None,
    source_codes: Collection[str] | None = None,
    target_codes: Collection[str] | None = None,
) -> Path:
    """Promove eventos administrativos declarados, sem inferência territorial."""
    events = parse_administrative_events(
        source_path, reference_year=reference_year, source_url=source_url,
    )
    if source_codes is not None or target_codes is not None:
        if source_codes is None or target_codes is None:
            raise ValueError("source_codes e target_codes devem ser fornecidos juntos")
        require_event_references(
            events, source_codes=source_codes, target_codes=target_codes
        )
    return _promote_events(
        root, events, source_path=source_path, reference_year=reference_year,
        source_url=source_url,
    )


def promote_toponymic_events(
    root: Path,
    source_path: Path,
    *,
    reference_year: int,
    source_url: str | None = None,
) -> Path:
    """Promove uma edição oficial para o histórico local do catálogo."""
    events = parse_toponymic_events(
        source_path, reference_year=reference_year, source_url=source_url,
    )
    return _promote_events(
        root, events, source_path=source_path, reference_year=reference_year,
        source_url=source_url,
    )



