from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from .models import CatalogMetadata, Municipality
from .validation import validate_municipalities


def write_catalog(path: Path, records: list[Municipality] | tuple[Municipality, ...]) -> Path:
    values = validate_municipalities(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([asdict(item) for item in values]).to_parquet(path, index=False)
    return path


def write_manifest(path: Path, metadata: CatalogMetadata) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(metadata), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
