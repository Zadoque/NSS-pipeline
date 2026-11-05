from __future__ import annotations

from pathlib import Path


def asset_directory(cod_municipio: str, *, root: Path) -> Path | None:
    # Os arquivos são separados por município para impedir que uma coordenada
    # limítrofe seja classificada no município vizinho.
    if not str(cod_municipio).startswith("33"):
        return None
    candidate = root / "rj" / str(cod_municipio)
    return candidate if candidate.exists() else None
