from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

import requests

from .catalog import InMemoryMunicipalityCatalog
from .client import IbgeLocalidadesClient
from .dtb import parse_dtb_archive
from .models import CatalogMetadata
from .storage import promote_active, write_catalog, write_manifest


def download_dtb_archive(
    root: Path,
    *,
    url: str,
    reference_year: int,
    expected_sha256: str | None = None,
    session: requests.Session | None = None,
    timeout: float = 120,
) -> Path:
    """Baixa uma DTB para o cache bruto, validando-a antes da promoção."""
    destination_dir = root / "raw" / f"dtb_{reference_year}"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"DTB_{reference_year}.zip"
    client = session or requests.Session()
    response = client.get(url, stream=True, timeout=timeout)
    response.raise_for_status()
    digest = hashlib.sha256()
    with tempfile.NamedTemporaryFile(
        dir=destination_dir, prefix=f".{destination.name}.", suffix=".tmp", delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        try:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    digest.update(chunk)
                    temporary.write(chunk)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
    actual_sha256 = digest.hexdigest()
    if expected_sha256 and actual_sha256 != expected_sha256:
        temporary_path.unlink(missing_ok=True)
        raise ValueError(
            f"SHA-256 da DTB diverge: esperado {expected_sha256}, obtido {actual_sha256}"
        )
    os.replace(temporary_path, destination)
    return destination


def refresh_from_dtb_url(
    root: Path,
    *,
    url: str,
    catalog_id: str,
    reference_year: int,
    expected_sha256: str | None = None,
    session: requests.Session | None = None,
) -> Path:
    """Baixa, valida e promove uma edição DTB em uma única operação controlada."""
    archive = download_dtb_archive(
        root, url=url, reference_year=reference_year,
        expected_sha256=expected_sha256, session=session,
    )
    return refresh_from_dtb_archive(
        root, archive, catalog_id=catalog_id, source_url=url,
        reference_year=reference_year,
    )


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
