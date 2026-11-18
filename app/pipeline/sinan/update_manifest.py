from __future__ import annotations

import json
from pathlib import Path

from ..atomic_io import write_json_atomic


def load_manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Manifesto SINAN contém JSON inválido: {path}") from exc
    if not isinstance(manifest, dict) or any(not isinstance(value, dict) for value in manifest.values()):
        raise ValueError(f"Manifesto SINAN deve conter um objeto por recorte: {path}")
    return manifest


def save_manifest(path: Path, manifest: dict) -> None:
    write_json_atomic(manifest, path)
