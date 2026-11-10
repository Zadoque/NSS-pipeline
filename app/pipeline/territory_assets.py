from __future__ import annotations

import json
from pathlib import Path


def asset_directory(cod_municipio: str, *, root: Path) -> Path | None:
    """Resolve a malha pela precedência IBGE -> oficial -> OpenStreetMap.

    O layout nacional usa ``ibge/<codigo>``, ``official/<codigo>`` e
    ``osm/<codigo>``. Os diretórios legados ``rj``, ``rj-official`` e
    ``rj-osm`` continuam sendo aceitos para os ativos RJ já versionados.
    A camada de bairros só é selecionada quando seus IDs de distrito
    correspondem aos distritos entregues no mesmo pacote.
    """
    municipality = str(cod_municipio)
    if len(municipality) != 7 or not municipality.isdigit():
        return None

    candidates = [
        root / "ibge" / municipality,
        root / "official" / municipality,
        root / "osm" / municipality,
    ]
    if municipality.startswith("33"):
        candidates.extend(
            [
                root / "rj" / municipality,
                root / "rj-official" / municipality,
                root / "rj-osm" / municipality,
            ]
        )

    for candidate in candidates:
        if _has_complete_assets(candidate, require_neighborhoods=True):
            return candidate

    # Mesmo sem bairros, a malha de distritos permite a classificação
    # distrital e torna explícita a ausência de uma camada intramunicipal.
    for candidate in candidates:
        if _has_complete_assets(candidate):
            return candidate
    return None


def _has_complete_assets(directory: Path, *, require_neighborhoods: bool = False) -> bool:
    complete = all(
        (directory / filename).is_file()
        for filename in ("districts.geojson", "neighborhoods.geojson")
    )
    if not complete:
        return False
    try:
        districts = json.loads((directory / "districts.geojson").read_text(encoding="utf-8"))["features"]
        neighborhoods = json.loads(
            (directory / "neighborhoods.geojson").read_text(encoding="utf-8")
        )["features"]
        district_ids = {
            feature["properties"]["territoryId"] for feature in districts if feature.get("geometry")
        }
        if not district_ids or (require_neighborhoods and not neighborhoods):
            return False
        return all(
            feature.get("geometry")
            and feature["properties"]["territoryId"]
            and feature["properties"]["parentDistrictId"] in district_ids
            for feature in neighborhoods
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False
