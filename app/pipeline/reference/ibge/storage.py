from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from .models import CatalogMetadata, Municipality
from .validation import validate_municipalities


def write_catalog(path: Path, records: list[Municipality] | tuple[Municipality, ...]) -> Path:
    values = validate_municipalities(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        pd.DataFrame([asdict(item) for item in values]).to_parquet(temporary_path, index=False)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return path


def write_manifest(path: Path, metadata: CatalogMetadata) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(asdict(metadata), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return path


def promote_active(active_path: Path, catalog_id: str) -> Path:
    active_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = active_path.with_name(f".{active_path.name}.tmp")
    temporary.write_text(json.dumps({"catalog_id": catalog_id}, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, active_path)
    return active_path
