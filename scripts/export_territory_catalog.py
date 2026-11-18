"""Publica o mesmo catálogo territorial no mapa e na API."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from app.pipeline.territory_assets import asset_directory
from scripts.territory_geojson import read_features


def export(root: Path, front: Path, api: Path, coverage_index: Path) -> dict[str, int]:
    index_path = front / "municipalities.index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    rows = {}
    copies = []
    district_coverage = set()
    counts = {"districtCount": 0, "neighborhoodCount": 0, "neighborhoodFallbackCount": 0}
    for item in index["items"]:
        code = str(item["code"])
        source = asset_directory(code, root=root)
        if source is None:
            raise ValueError(f"Município sem malha territorial válida: {code}")
        municipality_path = front / "municipalities" / f"{code}.geojson"
        if not any(f["geometry"] for f in read_features(municipality_path)):
            raise ValueError(f"Município sem geometria no mapa: {code}")
        item.pop("geometryStatus", None)
        for layer, kind in (("districts", "DISTRICT"), ("neighborhoods", "NEIGHBORHOOD_OR_LOCALITY")):
            source_path = source / f"{layer}.geojson"
            destination = front / layer / f"{code}.geojson"
            copies.append((source_path, destination))
            features = read_features(source_path)
            for feature in features:
                p = feature["properties"]
                identifier = p["territoryId"]
                parent = p.get("parentDistrictId") or ""
                entry = (identifier, p["name"], kind, code, parent, p.get("geometryStatus") or "AVAILABLE")
                if identifier in rows and rows[identifier] != entry:
                    raise ValueError(f"ID territorial duplicado: {identifier}")
                rows[identifier] = entry
                if kind == "NEIGHBORHOOD_OR_LOCALITY":
                    district_coverage.add(parent)
            if kind == "DISTRICT":
                counts["districtCount"] += len({f["properties"]["territoryId"] for f in features})
            else:
                neighborhood_count = len({f["properties"]["territoryId"] for f in features})
                counts["neighborhoodCount"] += neighborhood_count
                item["neighborhoodCount"] = neighborhood_count
                item["neighborhoodsPath"] = f"neighborhoods/{code}.geojson"
                item["neighborhoodGeometryStatus"] = "AVAILABLE" if features else "UNAVAILABLE"
                if features:
                    item["neighborhoodSource"] = (
                        "OpenStreetMap" if source.parent.name in {"osm", "rj-osm"}
                        else "Oficial municipal ou estadual" if source.parent.name in {"official", "rj-official"}
                        else "IBGE"
                    )
                    counts["neighborhoodFallbackCount"] += item["neighborhoodSource"] == "OpenStreetMap"
                else:
                    item.pop("neighborhoodSource", None)
    for source_path, destination in copies:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination)
    index_path.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    manifest_path = front / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(counts)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    coverage_index.write_text(json.dumps(sorted(district_coverage), ensure_ascii=False) + "\n", encoding="utf-8")
    with api.open("w", encoding="utf-8", newline="") as output:
        output.write("territoryId\tname\ttype\tmunicipalityCode\tparentDistrictId\tgeometryStatus\n")
        for row in sorted(rows.values()):
            output.write("\t".join(value.replace("\t", " ").replace("\n", " ").replace("\r", " ") for value in row) + "\n")
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--territory-root", type=Path, default=Path("territories"))
    parser.add_argument("--front-root", type=Path, required=True)
    parser.add_argument("--api-catalog", type=Path, required=True)
    parser.add_argument("--coverage-index", type=Path, required=True)
    args = parser.parse_args()
    print(export(args.territory_root, args.front_root, args.api_catalog, args.coverage_index))
