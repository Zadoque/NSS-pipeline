from __future__ import annotations

from pathlib import Path

TERRITORY_ASSETS: dict[str, Path] = {
    "3301009": Path("territories"),
}


def asset_directory(cod_municipio: str, *, root: Path) -> Path | None:
    relative = TERRITORY_ASSETS.get(cod_municipio)
    if relative is None:
        return None
    candidate = root.parent / relative if relative.parts[0] != root.name else root / Path(*relative.parts[1:])
    return candidate if candidate.exists() else None
