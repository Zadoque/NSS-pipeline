from __future__ import annotations

import json
from pathlib import Path


def asset_directory(cod_municipio: str, *, root: Path) -> Path | None:
    """Resolve a malha territorial seguindo a precedência institucional.

    1. IBGE: malha intramunicipal oficial versionada em ``rj/<codigo>``;
    2. Prefeitura/órgão estadual: fallback versionado em
       ``rj-official/<codigo>``;
    3. OpenStreetMap: último fallback versionado em ``rj-osm/<codigo>``.

    O fallback precisa conter os dois arquivos GeoJSON (distritos e bairros).
    Isso evita combinar bairros de uma fonte com distritos de outra sem uma
    validação explícita dos identificadores dos distritos.
    """
    if not str(cod_municipio).startswith("33"):
        return None

    municipality = str(cod_municipio)
    ibge = root / "rj" / municipality
    if _has_complete_assets(ibge, require_neighborhoods=True):
        return ibge

    official = root / "rj-official" / municipality
    if _has_complete_assets(official, require_neighborhoods=True):
        return official

    osm = root / "rj-osm" / municipality
    if _has_complete_assets(osm, require_neighborhoods=True):
        return osm

    # Mesmo sem bairros, o IBGE ainda permite classificar o distrito.
    return ibge if _has_complete_assets(ibge) else None


def _has_complete_assets(directory: Path, *, require_neighborhoods: bool = False) -> bool:
    complete = all(
        (directory / filename).is_file()
        for filename in ("districts.geojson", "neighborhoods.geojson")
    )
    if not complete or not require_neighborhoods:
        return complete
    try:
        payload = json.loads(
            (directory / "neighborhoods.geojson").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return False
    return bool(payload.get("features"))
