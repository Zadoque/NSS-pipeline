"""Publica uma fixture cartográfica sintética em um banco de staging vazio."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from .load import get_engine, load_gold_to_postgres
from .reference.ibge.storage import load_active_catalog
from .territory_assets import asset_directory

DISEASE = "TST"
YEAR = 2026


def _properties(directory: Path, layer: str) -> dict[str, dict]:
    data = json.loads((directory / f"{layer}.geojson").read_text(encoding="utf-8"))
    result = {}
    for feature in data["features"]:
        props = feature["properties"]
        code = props["territoryId"]
        if not feature["geometry"]:
            raise ValueError(f"Território sem geometria: {directory}/{layer}/{code}")
        if code in result and props != result[code]:
            raise ValueError(f"Metadados divergentes para o território {code}")
        result[code] = props
    return result


def fixture_rows(catalog, root: Path) -> tuple[list[dict], int, int]:
    rows = []
    district_count = neighborhood_count = 0
    for municipality in catalog.municipalities():
        code = municipality.code7
        directory = asset_directory(code, root=root)
        if directory is None:
            raise ValueError(f"Município sem pacote territorial válido: {code}")
        districts = _properties(directory, "districts")
        neighborhoods = _properties(directory, "neighborhoods")
        parents = {props["parentDistrictId"] for props in neighborhoods.values()}
        if not parents <= districts.keys():
            raise ValueError(f"Bairro sem distrito no pacote {directory}")

        district_count += len(districts)
        neighborhood_count += len(neighborhoods)
        targets = [
            (props["parentDistrictId"], child) for child, props in neighborhoods.items()
        ]
        targets.extend((district, None) for district in districts.keys() - parents)
        for district, neighborhood in sorted(targets, key=lambda target: (target[0], target[1] or "")):
            rows.append({
                "disease": DISEASE,
                "year": YEAR,
                "month": 1,
                "cd_mun": code,
                "nm_mun": municipality.name,
                "cd_uf": municipality.uf_code,
                "nm_uf": municipality.uf_name,
                "notification_district_id": district,
                "notification_neighborhood_id": neighborhood,
                "notification_territory_status": (
                    "NOTIFICATION_NEIGHBORHOOD" if neighborhood else "NOTIFICATION_DISTRICT_ONLY"
                ),
                "cases_total": 1,
            })
    return rows, district_count, neighborhood_count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-root", required=True, type=Path)
    parser.add_argument("--territory-root", type=Path, default=Path("territories"))
    args = parser.parse_args()
    engine = get_engine()
    with engine.connect() as connection:
        if connection.scalar(text("SELECT current_database()")) != "nss_coverage_stage":
            raise ValueError("A fixture só pode ser criada em nss_coverage_stage")
        if connection.scalar(text("SELECT EXISTS (SELECT FROM analytics.fato_casos)")):
            raise ValueError("O staging precisa estar vazio")
    catalog = load_active_catalog(args.catalog_root)
    rows, districts, neighborhoods = fixture_rows(catalog, args.territory_root)
    timestamp = datetime.now(UTC)
    load_gold_to_postgres(
        engine, pd.DataFrame(rows), DISEASE, timestamp.strftime("%Y%m%dT%H%M%SZ"),
        year=YEAR, municipios=list(catalog.as_mapping()), expected_cases_total=len(rows),
        snapshot_complete=True, source_extracted_at=timestamp,
        ibge_catalog=catalog, geographic_scope_type="BRAZIL",
    )
    with engine.begin() as connection:
        connection.execute(text("""
            UPDATE analytics.dim_doenca SET nome = 'Teste sintético de cobertura'
            WHERE codigo = :code
        """), {"code": DISEASE})
    print(json.dumps({
        "municipalities": len(catalog.as_mapping()), "districts": districts,
        "neighborhoods": neighborhoods, "notifications": len(rows),
    }))


if __name__ == "__main__":
    main()
