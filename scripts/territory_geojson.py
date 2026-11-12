"""Normalização dos bairros para o contrato territorial do pipeline."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from shapely import make_valid
from shapely.geometry import mapping, shape


def read_features(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["features"]


def write_features(path: Path, features: list[dict]) -> None:
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features},
                   ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _normalized_name(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = " ".join(text.casefold().split())
    return re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)


def _source_priority(feature: dict) -> tuple[int, float, str]:
    properties = feature.get("properties") or {}
    geometry = make_valid(shape(feature["geometry"]))
    # Relations usually carry the complete administrative boundary. A way is
    # retained only when it is not a duplicate of a relation.
    relation_first = 0 if properties.get("osmElementType") == "relation" else 1
    return relation_first, -geometry.area, str(properties.get("territoryId", ""))


def deduplicate_neighborhoods(
    features: list[dict], *, overlap_ratio: float = 0.85
) -> tuple[list[dict], list[dict]]:
    """Remove deterministic OSM duplicates and return an audit trail.

    A duplicate is a same-named feature in the same district whose
    intersection covers at least ``overlap_ratio`` of the smaller geometry.
    This deliberately does not deduplicate by name alone: distinct localities
    may legitimately share a name.
    """
    if not 0 < overlap_ratio <= 1:
        raise ValueError("overlap_ratio deve estar entre 0 e 1")

    ordered = sorted(features, key=_source_priority)
    kept: list[tuple[dict, object]] = []
    discarded: list[dict] = []
    for feature in ordered:
        properties = feature.get("properties") or {}
        geometry = make_valid(shape(feature["geometry"]))
        if geometry.is_empty or geometry.area <= 0:
            raise ValueError(
                f"Geometria territorial vazia: {properties.get('territoryId')}"
            )
        duplicate_of = None
        for retained, retained_geometry in kept:
            retained_properties = retained.get("properties") or {}
            if properties.get("parentDistrictId") != retained_properties.get(
                "parentDistrictId"
            ):
                continue
            if _normalized_name(properties.get("name")) != _normalized_name(
                retained_properties.get("name")
            ):
                continue
            ratio = geometry.intersection(retained_geometry).area / min(
                geometry.area, retained_geometry.area
            )
            if ratio >= overlap_ratio:
                duplicate_of = (retained_properties, ratio)
                break
        if duplicate_of is None:
            kept.append((feature, geometry))
            continue
        retained_properties, ratio = duplicate_of
        discarded.append(
            {
                "discardedTerritoryId": properties.get("territoryId"),
                "retainedTerritoryId": retained_properties.get("territoryId"),
                "discardedName": properties.get("name"),
                "parentDistrictId": properties.get("parentDistrictId"),
                "overlapRatio": round(ratio, 8),
                "reason": "same_normalized_name_same_district_high_overlap",
            }
        )
    return [feature for feature, _ in kept], discarded


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
        geometry = make_valid(shape(feature["geometry"]))
        clipped = make_valid(geometry.intersection(district_geometries[props["parentDistrictId"]]))
        if clipped.is_empty or clipped.area <= 0:
            raise ValueError(
                f"Bairro sem área no distrito-pai: {props.get('territoryId')}"
            )
        normalized.append(
            {**feature, "properties": props, "geometry": mapping(clipped)}
        )
    return normalized
