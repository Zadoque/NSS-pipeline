from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import hashlib
import json

from ...atomic_io import write_json_atomic
from .history_events import derive_annual_event_series, MunicipalityEvent
from .history_source import _validate_manifest_sources
from .history_storage import _read_events, write_events


def promote_annual_dtb_events(
    root: Path,
    archives: Mapping[int, Path],
    *,
    source_urls: Mapping[int, str] | None = None,
) -> Path:
    """Promove eventos observáveis derivados de edições anuais oficiais da DTB."""
    from .dtb import parse_dtb_archive

    editions = {
        year: parse_dtb_archive(path, reference_year=year)
        for year, path in sorted(archives.items())
    }
    events = derive_annual_event_series(editions, source_urls=source_urls)
    result_path = root / "historical" / "municipality_events.parquet"
    existing = {event.event_id: event for event in _read_events(result_path)}
    for event in events:
        previous = existing.get(event.event_id)
        if previous is not None and previous != event:
            raise ValueError(f"event_id conflitante no histórico municipal: {event.event_id}")
        existing[event.event_id] = event
    write_events(result_path, list(existing.values()))
    manifest_path = result_path.with_name("municipality_events.manifest.json")
    previous_manifest: dict[str, object] = {}
    if manifest_path.exists():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"manifesto histórico inválido: {manifest_path}") from exc
        if not isinstance(loaded, dict):
            raise ValueError(f"manifesto histórico inválido: {manifest_path}")
        previous_manifest = loaded
    sources = _validate_manifest_sources(previous_manifest.get("sources", []))
    source_keys = {
        (item.get("reference_year"), item.get("source_path"), item.get("sha256"))
        for item in sources
    }
    for year, path in sorted(archives.items()):
        entry = {
            "reference_year": year,
            "source_path": str(path),
            "source_url": (source_urls or {}).get(year),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        key = (entry["reference_year"], entry["source_path"], entry["sha256"])
        if key not in source_keys:
            sources.append(entry)
            source_keys.add(key)
    prior_policy = previous_manifest.get("inference_policy")
    raw_policies = previous_manifest.get("inference_policies", [])
    if not isinstance(raw_policies, list) or any(
        not isinstance(policy, str) or not policy.strip() for policy in raw_policies
    ):
        raise ValueError("manifesto histórico inválido: inference_policies deve ser uma lista de textos")
    policies = set(raw_policies)
    if prior_policy:
        policies.add(str(prior_policy))
    policies.add("OBSERVABLE_ANNUAL_DIFF_ONLY")
    inference_policy = next(iter(policies)) if len(policies) == 1 else "MIXED_EXPLICIT_AND_OBSERVABLE"
    manifest = {
        "reference_year_start": min(editions),
        "reference_year_end": max(editions),
        "rows": len(existing),
        "event_types": sorted({event.event_type for event in existing.values()}),
        "inference_policy": inference_policy,
        "inference_policies": sorted(policies),
        "sources": sorted(sources, key=lambda item: (
            str(item.get("reference_year")), str(item.get("source_path"))
        )),
    }
    write_json_atomic(manifest, manifest_path)
    return result_path
