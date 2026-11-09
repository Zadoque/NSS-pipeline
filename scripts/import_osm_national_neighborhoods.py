"""Importa localidades e bairros OSM para todos os municípios brasileiros.

O OSM é uma fonte complementar, nunca uma substituição da malha IBGE/oficial.
As consultas são feitas por UF, com checkpoint para retomada e limite de
requisições deliberadamente baixo para respeitar o Overpass.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests
from shapely.geometry import LineString, Point, Polygon, shape
from shapely.ops import polygonize, unary_union
from shapely.strtree import STRtree

DEFAULT_URLS = (
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
)
TAGS = "neighbourhood|suburb|quarter|town|village|hamlet"


def _geometry(element: dict):
    points = element.get("geometry") or []
    if element.get("type") == "way" and len(points) >= 4 and points[0] == points[-1]:
        return Polygon([(p["lon"], p["lat"]) for p in points])
    if element.get("type") != "relation":
        return None
    lines = []
    for member in element.get("members", []):
        if member.get("type") != "way" or member.get("role") not in ("", "outer", None):
            continue
        points = member.get("geometry") or []
        if len(points) >= 2:
            lines.append(LineString([(p["lon"], p["lat"]) for p in points]))
    polygons = list(polygonize(unary_union(lines))) if lines else []
    return unary_union(polygons) if polygons else None


def _query(uf: str) -> str:
    return f'''[out:json][timeout:180];
area["ISO3166-2"="BR-{uf}"][boundary=administrative]->.searchArea;
(
  way["place"~"^({TAGS})$"](area.searchArea);
  relation["place"~"^({TAGS})$"](area.searchArea);
  relation["boundary"="administrative"]["admin_level"="10"](area.searchArea);
);
out geom;'''


def _download(uf: str, urls: tuple[str, ...]) -> dict:
    last_error: Exception | None = None
    for attempt in range(4):
        for url in urls:
            try:
                response = requests.post(
                    url,
                    data={"data": _query(uf)},
                    headers={"User-Agent": "NSS-pipeline/1.0 OSM-national-import"},
                    timeout=240,
                )
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
        time.sleep(15 * (attempt + 1))
    raise RuntimeError(f"Overpass indisponível para {uf}: {last_error}")


def _municipalities(front_root: Path, uf: str):
    catalog = json.loads((front_root / "municipalities.index.json").read_text())
    rows = []
    for item in catalog["items"]:
        if item["uf"] != uf:
            continue
        path = front_root / "municipalities" / f"{item['code']}.geojson"
        if not path.is_file():
            continue
        payload = json.loads(path.read_text())
        geometry = unary_union([shape(feature["geometry"]) for feature in payload["features"]])
        rows.append((str(item["code"]), item["name"], geometry))
    return rows


def import_state(payload: dict, *, front_root: Path, output: Path, uf: str) -> int:
    municipalities = _municipalities(front_root, uf)
    geometries = [row[2] for row in municipalities]
    tree = STRtree(geometries)
    grouped: dict[str, list[dict]] = {}
    seen: set[tuple[str, int]] = set()
    for element in payload.get("elements", []):
        if element.get("type") not in ("way", "relation"):
            continue
        key = (element["type"], int(element["id"]))
        if key in seen:
            continue
        seen.add(key)
        name = (element.get("tags") or {}).get("name")
        geometry = _geometry(element)
        if not name or geometry is None or geometry.is_empty:
            continue
        point = geometry.representative_point()
        matches = tree.query(point)
        municipality = None
        for candidate in matches:
            candidate_geometry = geometries[int(candidate)] if hasattr(candidate, "__index__") else candidate
            if candidate_geometry.covers(point):
                municipality = municipalities[geometries.index(candidate_geometry)]
                break
        if municipality is None:
            continue
        code, municipality_name, _ = municipality
        grouped.setdefault(code, []).append({
            "type": "Feature",
            "properties": {
                "territoryId": f"OSM_BAIRRO_{element['type'].upper()}_{element['id']}",
                "name": name,
                "type": "NEIGHBORHOOD_OR_LOCALITY",
                "municipalityCode": code,
                "parentDistrictId": f"IBGE_MUN_{code}",
                "geometryStatus": "POLYGON_OSM",
                "source": "OpenStreetMap",
                "sourceLicense": "ODbL-1.0",
                "osmElementType": element["type"],
                "osmElementId": element["id"],
            },
            "geometry": geometry.__geo_interface__,
        })
    for code, features in grouped.items():
        destination = output / "osm" / code
        destination.mkdir(parents=True, exist_ok=True)
        ibge_districts = output / "ibge" / code / "districts.geojson"
        if ibge_districts.is_file():
            (destination / "districts.geojson").write_text(ibge_districts.read_text())
        (destination / "neighborhoods.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False)
        )
    return sum(len(features) for features in grouped.values())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--front-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("territories"))
    parser.add_argument("--checkpoint", type=Path, default=Path("territories/osm-national.checkpoint.json"))
    parser.add_argument("--ufs", nargs="*")
    args = parser.parse_args()
    catalog = json.loads((args.front_root / "municipalities.index.json").read_text())
    ufs = sorted(args.ufs or {item["uf"] for item in catalog["items"]})
    checkpoint = json.loads(args.checkpoint.read_text()) if args.checkpoint.is_file() else {"completed": {}}
    for uf in ufs:
        if uf in checkpoint["completed"]:
            print(f"{uf}: já concluído", flush=True)
            continue
        payload = _download(uf, DEFAULT_URLS)
        features = import_state(payload, front_root=args.front_root, output=args.output, uf=uf)
        checkpoint["completed"][uf] = {
            "features": features,
            "timestamp": payload.get("osm3s", {}).get("timestamp_osm_base"),
        }
        args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
        args.checkpoint.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n")
        print(f"{uf}: {features} polígonos", flush=True)
        time.sleep(2)


if __name__ == "__main__":
    main()
