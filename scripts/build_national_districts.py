"""Converte a malha nacional de distritos do Censo 2022 para o catálogo NSS."""

from __future__ import annotations

import argparse
import json
import tempfile
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile

import shapefile
from shapely import orient_polygons, set_precision
from shapely.geometry import mapping, shape

if __package__:
    from .territory_geojson import write_features
else:
    from territory_geojson import write_features


def build(archive_path: Path, root: Path) -> int:
    districts = defaultdict(list)
    with tempfile.TemporaryDirectory(prefix="nss-districts-") as directory:
        with ZipFile(archive_path) as archive:
            archive.extractall(directory)
        shp_path = next(Path(directory).glob("*.shp"))
        with shapefile.Reader(str(shp_path), encoding="utf-8") as source:
            for entry in source.iterShapeRecords(fields=["CD_MUN", "CD_DIST", "NM_DIST"]):
                row = entry.record.as_dict()
                code = str(row["CD_MUN"]).zfill(7)
                destination = root / code / "districts.geojson"
                if not destination.is_file() or code.startswith("33"):
                    continue
                geometry = shape(entry.shape.__geo_interface__).simplify(0.0002, preserve_topology=True)
                geometry = orient_polygons(set_precision(geometry, 0.000001, mode="pointwise"), exterior_cw=True)
                districts[code].append({
                    "type": "Feature",
                    "properties": {
                        "territoryId": f"IBGE_DIST_{row['CD_DIST']}",
                        "name": row["NM_DIST"],
                        "type": "DISTRICT",
                        "municipalityCode": code,
                        "source": "IBGE Censo 2022",
                    },
                    "geometry": mapping(geometry),
                })
    for code, features in districts.items():
        write_features(root / code / "districts.geojson", features)
    return sum(map(len, districts.values()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--root", type=Path, default=Path("territories/ibge"))
    args = parser.parse_args()
    print(build(args.archive, args.root))
