from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from .catalog import InMemoryMunicipalityCatalog
from .client import IbgeLocalidadesClient
from .models import CatalogMetadata
from .storage import promote_active, write_catalog, write_manifest


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
        sha256="",
    )
    write_manifest(release / "manifest.json", metadata)
    promote_active(root / "active.json", catalog_id)
    return parquet
