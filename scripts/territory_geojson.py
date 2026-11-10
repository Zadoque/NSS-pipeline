"""Normalização dos bairros para o contrato territorial do pipeline."""

from __future__ import annotations

import json
from pathlib import Path

from shapely import make_valid
from shapely.geometry import shape


def read_features(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["features"]


def write_features(path: Path, features: list[dict]) -> None:
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features},
                   ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def normalize_neighborhoods(features: list[dict], districts: list[dict]) -> list[dict]:
    district_geometries = {
        item["properties"]["territoryId"]: shape(item["geometry"]) for item in districts
    }
    normalized = []
    for feature in features:
        props = dict(feature["properties"])
        if props.get("CD_BAIRRO"):
            props.setdefault("territoryId", f"IBGE_BAIRRO_{props['CD_BAIRRO']}")
            props.setdefault("name", props.get("NM_BAIRRO"))
            declared_parent = f"IBGE_DIST_{props.get('CD_DIST')}"
            if declared_parent in district_geometries:
                props["parentDistrictId"] = declared_parent
        if props.get("parentDistrictId") not in district_geometries:
            geometry = shape(feature["geometry"])
            point = geometry.representative_point()
            props["parentDistrictId"] = next(
                (code for code, geom in district_geometries.items() if geom.covers(point)), None
            )
            if props["parentDistrictId"] is None:
                geometry = make_valid(geometry)
                overlaps = [
                    (geometry.intersection(make_valid(district)).area, code)
                    for code, district in district_geometries.items()
                    if district.intersects(geometry)
                ]
                if overlaps and max(overlaps)[0] > 0:
                    props["parentDistrictId"] = max(overlaps)[1]
        if not props.get("territoryId") or not props.get("parentDistrictId"):
            raise ValueError(f"Bairro sem ID ou distrito compatível: {props}")
        normalized.append({**feature, "properties": props})
    return normalized
