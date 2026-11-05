"""Converte as malhas intramunicipais oficiais do IBGE 2022 do RJ em GeoJSON.

O IBGE não publica bairros oficiais para todos os municípios. Por isso o
gerador cria distritos para os 92 municípios e um arquivo de bairros por
município, vazio quando a malha oficial não possui bairros naquele município.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from collections import defaultdict
from pathlib import Path

import shapefile


DISTRICT_ID = "IBGE_DIST_"
NEIGHBORHOOD_ID = "IBGE_BAIRRO_"


def _read_records(zip_path: Path) -> list[dict]:
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(zip_path.parent / zip_path.stem)
    directory = zip_path.parent / zip_path.stem
    shp_path = next(directory.glob("*.shp"))
    reader = shapefile.Reader(str(shp_path), encoding="utf-8")
    fields = [field[0] for field in reader.fields[1:]]
    return [
        {
            "attributes": dict(zip(fields, shape_record.record, strict=True)),
            "geometry": shape_record.shape.__geo_interface__,
        }
        for shape_record in reader.iterShapeRecords()
    ]


def _feature(territory_id: str, name: str, geometry: dict, **properties: object) -> dict:
    return {
        "type": "Feature",
        "properties": {"territoryId": territory_id, "name": name, **properties},
        "geometry": geometry,
    }


def _write(path: Path, features: list[dict]) -> None:
    path.write_text(
        json.dumps(
            {"type": "FeatureCollection", "features": features},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


def build(districts_zip: Path, neighborhoods_zip: Path, output: Path) -> None:
    districts = _read_records(districts_zip)
    neighborhoods = _read_records(neighborhoods_zip)
    municipalities: dict[str, dict[str, list[dict]]] = defaultdict(
        lambda: {"districts": [], "neighborhoods": []}
    )

    for row in districts:
        attrs = row["attributes"]
        municipality = str(attrs["CD_MUN"]).zfill(7)
        district = str(attrs["CD_DIST"]).zfill(9)
        municipalities[municipality]["districts"].append(
            _feature(
                DISTRICT_ID + district,
                str(attrs["NM_DIST"]),
                row["geometry"],
                type="DISTRICT",
                municipalityCode=municipality,
                parentDistrictId=None,
                geometryStatus="POLYGON_OFFICIAL",
            )
        )

    for row in neighborhoods:
        attrs = row["attributes"]
        municipality = str(attrs["CD_MUN"]).zfill(7)
        district = str(attrs["CD_DIST"]).zfill(9)
        neighborhood = str(attrs["CD_BAIRRO"]).zfill(10)
        municipalities[municipality]["neighborhoods"].append(
            _feature(
                NEIGHBORHOOD_ID + neighborhood,
                str(attrs["NM_BAIRRO"]),
                row["geometry"],
                type="NEIGHBORHOOD_OR_LOCALITY",
                municipalityCode=municipality,
                parentDistrictId=DISTRICT_ID + district,
                geometryStatus="POLYGON_OFFICIAL",
            )
        )

    if len(municipalities) != 92:
        raise RuntimeError(f"malha de distritos do RJ contém {len(municipalities)} municípios, esperado 92")

    output.mkdir(parents=True, exist_ok=True)
    for municipality, layers in sorted(municipalities.items()):
        directory = output / municipality
        directory.mkdir(parents=True, exist_ok=True)
        _write(directory / "districts.geojson", layers["districts"])
        _write(directory / "neighborhoods.geojson", layers["neighborhoods"])

    manifest = {
        "source": "IBGE Malha de Setores Censitários / Divisões Intramunicipais 2022",
        "districts": districts_zip.name,
        "neighborhoods": neighborhoods_zip.name,
        "municipalities": len(municipalities),
        "municipalitiesWithOfficialNeighborhoods": sum(
            bool(layers["neighborhoods"]) for layers in municipalities.values()
        ),
        "municipalitiesWithoutOfficialNeighborhoods": sum(
            not layers["neighborhoods"] for layers in municipalities.values()
        ),
        "districtFeatures": sum(len(layers["districts"]) for layers in municipalities.values()),
        "neighborhoodFeatures": sum(len(layers["neighborhoods"]) for layers in municipalities.values()),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--districts", type=Path, required=True)
    parser.add_argument("--neighborhoods", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.districts, args.neighborhoods, args.output)


if __name__ == "__main__":
    main()
