"""Reclassifica um lote CNES existente sem baixar os estabelecimentos novamente."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from hashlib import file_digest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from .atomic_io import write_json_atomic
from .reference.ibge.storage import load_active_catalog
from .sinan.gold import _load_cnes_batch
from .territory_assets import asset_directory
from .territory_mapping import enrich_cnes_territories


def reclassify(source: Path, catalog_root: Path, territories: Path) -> Path:
    catalog = load_active_catalog(catalog_root)
    frame = _load_cnes_batch(source, catalog=catalog)
    metadata = dict(frame.attrs["cnes_metadata"])
    metadata.pop("_contract_validated", None)
    parts = []
    for code, units in frame.groupby("cd_mun", dropna=False, sort=False):
        package = asset_directory(str(code), root=territories)
        if package is None:
            units = units.assign(
                notification_district_id=None, notification_neighborhood_id=None,
                notification_territory_status="UNAVAILABLE",
            )
        else:
            units = enrich_cnes_territories(units, package)
        parts.append(units)
    classified = pd.concat(parts).sort_index()
    timestamp = datetime.now(UTC)
    batch_id = timestamp.strftime("%Y%m%dT%H%M%SZ")
    parent = source.resolve().parent.parent
    destination = parent / f"batch_id={batch_id}"
    with TemporaryDirectory(prefix=".reclassify-cnes-", dir=parent) as temporary:
        staged = Path(temporary) / destination.name
        staged.mkdir()
        output = staged / "data.parquet"
        classified.to_parquet(output, index=False)
        with output.open("rb") as file:
            digest = file_digest(file, "sha256").hexdigest()
        metadata.update(
            reclassified_from_batch_id=metadata["batch_id"], batch_id=batch_id,
            reclassified_at=timestamp.isoformat(), parquet_sha256=digest,
        )
        write_json_atomic(metadata, staged / "metadata.json")
        staged.rename(destination)
    return destination / "data.parquet"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--catalog-root", type=Path, required=True)
    parser.add_argument("--territories", type=Path, default=Path("territories"))
    args = parser.parse_args()
    print(reclassify(args.source, args.catalog_root, args.territories))
