"""Importa polígonos de bairros do OpenStreetMap para o RJ.

O OSM é deliberadamente o último fallback: não substitui a malha do IBGE nem
uma fonte municipal/estadual oficial. O resultado deve ser distribuído sob a
licença ODbL do OpenStreetMap e nunca deve ser tratado como limite oficial.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests
from shapely.geometry import LineString, Polygon, shape
from shapely.ops import polygonize, unary_union

DEFAULT_URL = "https://overpass-api.de/api/interpreter"
QUERY = '''[out:json][timeout:180];
area["ISO3166-2"="BR-RJ"][boundary=administrative]->.searchArea;
(
  way["place"~"^(neighbourhood|suburb|quarter)$"](area.searchArea);
  relation["place"~"^(neighbourhood|suburb|quarter)$"](area.searchArea);
  relation["boundary"="administrative"]["admin_level"="10"](area.searchArea);
);
out geom;'''


def _load_districts(root: Path) -> list[tuple[str, dict, object]]:
    districts = []
    for path in sorted((root / "rj").glob("*/districts.geojson")):
        for feature in json.loads(path.read_text(encoding="utf-8"))["features"]:
            districts.append((path.parent.name, feature["properties"], shape(feature["geometry"])))
    return districts


def _osm_geometry(element: dict) -> object | None:
    geometry = element.get("geometry")
    if element.get("type") == "way" and geometry and geometry[0] == geometry[-1]:
        return Polygon([(p["lon"], p["lat"]) for p in geometry])
    if element.get("type") != "relation":
        return None
    lines = []
    for member in element.get("members", []):
        if member.get("role") not in ("", "outer", None) or member.get("type") != "way":
            continue
        points = member.get("geometry") or []
        if len(points) >= 2:
            lines.append(LineString([(p["lon"], p["lat"]) for p in points]))
    polygons = list(polygonize(unary_union(lines))) if lines else []
    return unary_union(polygons) if polygons else None


def _download(url: str) -> dict:
    response = requests.post(
        url,
        data={"data": QUERY},
        headers={"User-Agent": "NSS-pipeline/1.0 OSM-import"},
        timeout=240,
    )
    response.raise_for_status()
    return response.json()


def import_osm(payload: dict, *, root: Path) -> dict[str, int]:
    districts = _load_districts(root)
    output: dict[str, list[dict]] = {}
    seen: set[tuple[str, int]] = set()
    for element in payload.get("elements", []):
        if element.get("type") not in ("way", "relation"):
            continue
        key = (element["type"], int(element["id"]))
        if key in seen:
            continue
        seen.add(key)
        name = element.get("tags", {}).get("name")
        geometry = _osm_geometry(element)
        if not name or geometry is None or geometry.is_empty:
            continue
        point = geometry.representative_point()
        municipality = next((code for code, _, district in districts if district.covers(point)), None)
        if municipality is None:
            continue
        parent = next(
            (props["territoryId"] for code, props, district in districts
             if code == municipality and district.covers(point)),
            None,
        )
        if parent is None:
            continue
        output.setdefault(municipality, []).append({
            "type": "Feature",
            "properties": {
                "territoryId": f"OSM_BAIRRO_{element['type'].upper()}_{element['id']}",
                "name": name,
                "type": "NEIGHBORHOOD_OR_LOCALITY",
                "municipalityCode": municipality,
                "parentDistrictId": parent,
                "geometryStatus": "POLYGON_OSM",
                "source": "OpenStreetMap",
                "sourceLicense": "ODbL-1.0",
                "osmElementType": element["type"],
                "osmElementId": element["id"],
            },
            "geometry": geometry.__geo_interface__,
        })

    for municipality, features in output.items():
        destination = root / "rj-osm" / municipality
        destination.mkdir(parents=True, exist_ok=True)
        source_districts = root / "rj" / municipality / "districts.geojson"
        (destination / "districts.geojson").write_text(source_districts.read_text(encoding="utf-8"), encoding="utf-8")
        (destination / "neighborhoods.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False),
            encoding="utf-8",
        )
    return {municipality: len(features) for municipality, features in sorted(output.items())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("territories"))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--url", default=DEFAULT_URL)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8")) if args.input else _download(args.url)
    result = import_osm(payload, root=args.root)
    print(json.dumps({"municipalities": len(result), "features": sum(result.values()), "byMunicipality": result}, ensure_ascii=False))


if __name__ == "__main__":
    main()
