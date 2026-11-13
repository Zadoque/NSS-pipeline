"""Publica no frontend os bairros OSM importados pelo pipeline."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-root", type=Path, required=True)
    parser.add_argument("--front-root", type=Path, required=True)
    args = parser.parse_args()

    index_path = args.front_root / "municipalities.index.json"
    catalog = json.loads(index_path.read_text(encoding="utf-8"))
    osm_root = args.pipeline_root / "territories" / "osm"
    published = 0
    for item in catalog["items"]:
        code = str(item["code"])
        source = osm_root / code / "neighborhoods.geojson"
        if not source.is_file():
            continue
        destination = args.front_root / "neighborhoods" / f"{code}.geojson"
        if destination.is_file() and item.get("neighborhoodSource") != "OpenStreetMap":
            existing = json.loads(destination.read_text(encoding="utf-8"))
            if existing.get("features"):
                continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        item["neighborhoodSource"] = "OpenStreetMap"
        published += 1
    index_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"osmMunicipalities": published, "catalogMunicipalities": len(catalog["items"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
