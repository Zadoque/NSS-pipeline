from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from .catalog import InMemoryMunicipalityCatalog
from .client import IbgeLocalidadesClient
from .dtb import parse_dtb_archive
from .models import CatalogMetadata
from .storage import promote_active, write_catalog, write_manifest


def _records_sha256(records) -> str:
    payload = json.dumps(
        [asdict(record) for record in sorted(records, key=lambda item: item.code7)],
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def refresh_from_localidades(
    root: Path,
    *,
    catalog_id: str,
    source_url: str,
    reference_year: int,
    client: IbgeLocalidadesClient | None = None,
) -> Path:
    records = (client or IbgeLocalidadesClient()).fetch_municipalities()
    release = root / "releases" / catalog_id
    parquet = write_catalog(release / "municipalities.parquet", records)
    metadata = CatalogMetadata(
        catalog_id=catalog_id,
        reference_year=reference_year,
        source_name="IBGE - API de Localidades",
        source_url=source_url,
        retrieved_at=datetime.now(UTC).isoformat(),
        sha256=_records_sha256(records),
    )
    write_manifest(release / "manifest.json", metadata)
    promote_active(root / "active.json", catalog_id)
    return parquet


def refresh_from_dtb_archive(
    root: Path,
    archive: Path,
    *,
    catalog_id: str,
    source_url: str,
    reference_year: int,
) -> Path:
    records = parse_dtb_archive(archive, reference_year)
    release = root / "releases" / catalog_id
    parquet = write_catalog(release / "municipalities.parquet", records)
    sha256 = hashlib.sha256(archive.read_bytes()).hexdigest()
    metadata = CatalogMetadata(
        catalog_id=catalog_id,
        reference_year=reference_year,
        source_name="IBGE - Divisão Territorial Brasileira",
        source_url=source_url,
        retrieved_at=datetime.now(UTC).isoformat(),
        sha256=sha256,
    )
    write_manifest(release / "manifest.json", metadata)
    promote_active(root / "active.json", catalog_id)
    return parquet
