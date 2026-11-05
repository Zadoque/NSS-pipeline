from __future__ import annotations

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
    if _has_complete_assets(ibge):
        return ibge

    official = root / "rj-official" / municipality
    if _has_complete_assets(official):
        return official

    osm = root / "rj-osm" / municipality
    return osm if _has_complete_assets(osm) else None


def _has_complete_assets(directory: Path) -> bool:
    return all(
        (directory / filename).is_file()
        for filename in ("districts.geojson", "neighborhoods.geojson")
    )
