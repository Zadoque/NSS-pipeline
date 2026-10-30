from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from .catalog import ParquetMunicipalityCatalog
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
    try:
        temporary.write_text(json.dumps(asdict(metadata), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def promote_active(active_path: Path, catalog_id: str) -> Path:
    active_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = active_path.with_name(f".{active_path.name}.tmp")
    try:
        temporary.write_text(json.dumps({"catalog_id": catalog_id}, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, active_path)
    finally:
        temporary.unlink(missing_ok=True)
    return active_path


def load_active_catalog(root: Path) -> ParquetMunicipalityCatalog:
    active_path = root / "active.json"
    try:
        active = json.loads(active_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"ponteiro ativo ausente: {active_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"ponteiro ativo inválido: {active_path}") from exc
    catalog_id = active.get("catalog_id")
    if not isinstance(catalog_id, str) or not catalog_id or Path(catalog_id).name != catalog_id:
        raise ValueError("active.json não informa catalog_id")
    release = root / "releases" / catalog_id
    manifest_path = release / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"manifesto da release ausente: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"manifesto da release inválido: {manifest_path}") from exc
    try:
        metadata = CatalogMetadata(**manifest)
    except TypeError as exc:
        raise ValueError(f"manifesto da release incompatível: {manifest_path}") from exc
    if metadata.catalog_id != catalog_id:
        raise ValueError("catalog_id do manifesto diverge do ponteiro ativo")
    if metadata.validation_status != "VALIDATED":
        raise ValueError("release IBGE ativa não está validada")
    return ParquetMunicipalityCatalog(release / "municipalities.parquet", metadata)
