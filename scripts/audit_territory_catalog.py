"""Audita o catálogo territorial nacional e os artefatos derivados.

O comando não altera nenhum arquivo. Ele produz métricas QA para um snapshot
e retorna código diferente de zero quando encontra uma violação estrutural.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from shapely import make_valid
from shapely.geometry import shape

from app.pipeline.territory_assets import asset_directory

try:
    from .territory_geojson import _normalized_name
except ImportError:
    from territory_geojson import _normalized_name


EXPECTED_REGIONS = 5
EXPECTED_STATES = 27
EXPECTED_MUNICIPALITIES = 5571
CONTAINMENT_TOLERANCE_DEGREES = 1e-6


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _features(path: Path) -> list[dict]:
    return _read(path).get("features", [])


def _identity(
    properties: dict, *, fallback_type: str
) -> tuple[str, str, str, str | None]:
    territory_type = properties.get("type") or fallback_type
    if territory_type == "MUNICIPALITY_FALLBACK" and fallback_type == "DISTRICT":
        # The API exposes a municipality fallback as its sole district-level
        # territory so that the catalog and endpoint remain compatible.
        territory_type = fallback_type
    return (
        str(properties.get("territoryId", "")),
        str(properties.get("name", "")),
        str(territory_type),
        properties.get("parentDistrictId"),
    )


def _municipality_codes(front_root: Path) -> list[str]:
    catalog = _read(front_root / "municipalities.index.json")
    return [str(item["code"]) for item in catalog.get("items", [])]


def _audit_package(
    municipality: str, package: Path, *, overlap_ratio: float
) -> tuple[list[dict], list[tuple[str, str, str, str | None]], dict[str, int]]:
    violations: list[dict] = []
    identities: list[tuple[str, str, str, str | None]] = []
    counts = Counter()
    districts_path = package / "districts.geojson"
    neighborhoods_path = package / "neighborhoods.geojson"
    if not districts_path.is_file() or not neighborhoods_path.is_file():
        violations.append({"municipalityCode": municipality, "reason": "missing_asset"})
        return violations, identities, counts

    districts = _features(districts_path)
    neighborhoods = _features(neighborhoods_path)
    district_map: dict[str, object] = {}
    seen_ids: set[str] = set()
    for feature, fallback_type in [
        *[(feature, "DISTRICT") for feature in districts],
        *[(feature, "NEIGHBORHOOD_OR_LOCALITY") for feature in neighborhoods],
    ]:
        properties = feature.get("properties") or {}
        territory_id = str(properties.get("territoryId", ""))
        identities.append(_identity(properties, fallback_type=fallback_type))
        if not territory_id:
            violations.append({"municipalityCode": municipality, "reason": "missing_id"})
            continue
        if territory_id in seen_ids:
            violations.append({"municipalityCode": municipality, "territoryId": territory_id, "reason": "duplicate_id"})
        seen_ids.add(territory_id)
        geometry_payload = feature.get("geometry")
        if not geometry_payload:
            violations.append({"municipalityCode": municipality, "territoryId": territory_id, "reason": "missing_geometry"})
            continue
        geometry = make_valid(shape(geometry_payload))
        if geometry.is_empty or geometry.area <= 0 or not geometry.is_valid:
            violations.append({"municipalityCode": municipality, "territoryId": territory_id, "reason": "invalid_geometry"})
            continue
        if fallback_type == "DISTRICT":
            district_map[territory_id] = geometry
    counts["districts"] = len(districts)
    counts["neighborhoods"] = len(neighborhoods)
    counts["geometries"] = len(districts) + len(neighborhoods)

    by_name: defaultdict[tuple[str, str | None], list[tuple[dict, object]]] = defaultdict(list)
    for feature in neighborhoods:
        properties = feature.get("properties") or {}
        parent = properties.get("parentDistrictId")
        if parent not in district_map:
            violations.append({"municipalityCode": municipality, "territoryId": properties.get("territoryId"), "reason": "missing_parent_district"})
            continue
        geometry = make_valid(shape(feature["geometry"]))
        if not district_map[parent].buffer(CONTAINMENT_TOLERANCE_DEGREES).covers(geometry):
            violations.append({"municipalityCode": municipality, "territoryId": properties.get("territoryId"), "reason": "outside_parent_district"})
        by_name[(_normalized_name(properties.get("name")), parent)].append((properties, geometry))
    for (name, parent), candidates in by_name.items():
        for index, (left_props, left_geometry) in enumerate(candidates):
            for right_props, right_geometry in candidates[index + 1 :]:
                overlap = left_geometry.intersection(right_geometry).area / min(left_geometry.area, right_geometry.area)
                if overlap >= overlap_ratio:
                    violations.append({
                        "municipalityCode": municipality,
                        "territoryId": left_props.get("territoryId"),
                        "otherTerritoryId": right_props.get("territoryId"),
                        "name": name,
                        "parentDistrictId": parent,
                        "overlapRatio": round(overlap, 8),
                        "reason": "duplicate_semantic_geometry",
                    })
    return violations, identities, counts


def audit(
    *, pipeline_root: Path, front_root: Path, java_root: Path | None = None, overlap_ratio: float = 0.85
) -> dict:
    municipalities = _municipality_codes(front_root)
    violations: list[dict] = []
    identities: list[tuple[str, str, str, str | None]] = []
    totals = Counter()
    by_uf: defaultdict[str, Counter] = defaultdict(Counter)
    missing_pipeline: list[str] = []
    for code in municipalities:
        package = asset_directory(code, root=pipeline_root / "territories")
        if package is None:
            missing_pipeline.append(code)
            continue
        package_violations, package_ids, counts = _audit_package(code, package, overlap_ratio=overlap_ratio)
        violations.extend(package_violations)
        identities.extend(package_ids)
        totals.update(counts)
        by_uf[code[:2]].update(counts)
    if missing_pipeline:
        violations.append({"reason": "missing_pipeline_municipalities", "count": len(missing_pipeline), "codes": missing_pipeline[:20]})

    identity_counts = Counter(identities)
    for identity, count in identity_counts.items():
        if count > 1:
            violations.append({"reason": "duplicate_identity_global", "identity": identity, "count": count})

    java_identities: set[tuple[str, str, str, str | None]] = set()
    if java_root is not None:
        path = java_root / "src/main/resources/territories/national-intramunicipal.tsv"
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines()[1:]:
                fields = line.split("\t")
                if len(fields) >= 6:
                    java_identities.add((fields[0], fields[1], fields[2], fields[4] or None))
        expected = set(identities)
        if expected != java_identities:
            violations.append({
                "reason": "java_pipeline_parity",
                "pipelineOnly": len(expected - java_identities),
                "javaOnly": len(java_identities - expected),
                "pipelineOnlySample": sorted(expected - java_identities)[:20],
                "javaOnlySample": sorted(java_identities - expected)[:20],
            })

    states = {code[:2] for code in municipalities}
    regions = {"N", "NE", "CO", "SE", "S"}
    metrics = {
        "regions": len(regions),
        "states": len(states),
        "municipalities": len(municipalities),
        "districts": totals["districts"],
        "neighborhoods": totals["neighborhoods"],
        "geometries": totals["geometries"],
        "pipelineMunicipalities": len(municipalities) - len(missing_pipeline),
        "violations": len(violations),
        "containmentToleranceDegrees": CONTAINMENT_TOLERANCE_DEGREES,
        "semanticOverlapRatio": overlap_ratio,
    }
    quality = {
        "completeness": len(municipalities) / EXPECTED_MUNICIPALITIES,
        "regionCountPass": len(regions) == EXPECTED_REGIONS,
        "stateCountPass": len(states) == EXPECTED_STATES,
        "municipalityCountPass": len(municipalities) == EXPECTED_MUNICIPALITIES,
        "structuralPass": not violations,
    }
    return {"metrics": metrics, "quality": quality, "byUf": {uf: dict(counter) for uf, counter in sorted(by_uf.items())}, "violations": violations}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-root", type=Path, required=True)
    parser.add_argument("--front-root", type=Path, required=True)
    parser.add_argument("--java-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overlap-ratio", type=float, default=0.85)
    args = parser.parse_args()
    result = audit(
        pipeline_root=args.pipeline_root,
        front_root=args.front_root,
        java_root=args.java_root,
        overlap_ratio=args.overlap_ratio,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["metrics"], ensure_ascii=False))
    return 0 if result["quality"]["structuralPass"] and all(
        result["quality"][key] for key in ("regionCountPass", "stateCountPass", "municipalityCountPass")
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
