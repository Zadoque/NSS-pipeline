"""Promove o pacote cartográfico nacional do front para o layout do pipeline.

O front já mantém a malha municipal/distrital oficial do IBGE. Este comando
reaproveita essa fonte versionada sem classificar bairros OSM como oficiais:
os distritos ficam em ``territories/ibge`` e os bairros identificados no
catálogo como OpenStreetMap ficam em ``territories/osm``.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

if __package__:
    from .territory_geojson import normalize_neighborhoods, read_features, write_features
else:
    from territory_geojson import normalize_neighborhoods, read_features, write_features


def _write_empty(path: Path) -> None:
    path.write_text('{"type":"FeatureCollection","features":[]}\n', encoding="utf-8")


def _municipality_as_district(source: Path, code: str, name: str) -> dict:
    payload = json.loads(source.read_text(encoding="utf-8"))
    features = []
    for feature in payload.get("features", []):
        properties = feature.get("properties") or {}
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "territoryId": f"IBGE_MUN_{code}",
                    "name": name,
                    "type": "MUNICIPALITY_FALLBACK",
                    "municipalityCode": code,
                    "parentDistrictId": None,
                    "geometryStatus": "POLYGON_MUNICIPALITY",
                    "source": "IBGE",
                    "sourceMunicipalityCode": properties.get("code_muni", code),
                },
                "geometry": feature["geometry"],
            }
        )
    return {"type": "FeatureCollection", "features": features}


def import_assets(front_root: Path, output: Path) -> dict[str, int]:
    catalog = json.loads(
        (front_root / "municipalities.index.json").read_text(encoding="utf-8")
    )
    ibge_count = 0
    osm_count = 0
    for item in catalog["items"]:
        code = str(item["code"])
        ibge = output / "ibge" / code
        ibge.mkdir(parents=True, exist_ok=True)
        district_source = front_root / "districts" / f"{code}.geojson"
        municipality_source = front_root / "municipalities" / f"{code}.geojson"
        if district_source.is_file():
            shutil.copyfile(district_source, ibge / "districts.geojson")
        elif municipality_source.is_file():
            (ibge / "districts.geojson").write_text(
                json.dumps(
                    _municipality_as_district(municipality_source, code, item["name"]),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
        else:
            raise FileNotFoundError(f"malha municipal ausente para {code}: {municipality_source}")
        neighborhood_source = front_root / "neighborhoods" / f"{code}.geojson"
        if neighborhood_source.is_file() and item.get("neighborhoodSource") != "OpenStreetMap":
            write_features(
                ibge / "neighborhoods.geojson",
                normalize_neighborhoods(read_features(neighborhood_source), read_features(ibge / "districts.geojson")),
            )
        else:
            _write_empty(ibge / "neighborhoods.geojson")
        ibge_count += 1

        if item.get("neighborhoodSource") == "OpenStreetMap" and neighborhood_source.is_file():
            osm = output / "osm" / code
            osm.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ibge / "districts.geojson", osm / "districts.geojson")
            write_features(
                osm / "neighborhoods.geojson",
                normalize_neighborhoods(read_features(neighborhood_source), read_features(osm / "districts.geojson")),
            )
            osm_count += 1

    manifest = {
        "source": "NSS-front-end public/maps/national",
        "ibgeMunicipalities": ibge_count,
        "osmMunicipalities": osm_count,
        "precedence": ["ibge", "official", "osm"],
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--front-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("territories"))
    args = parser.parse_args()
    print(json.dumps(import_assets(args.front_root, args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
