from __future__ import annotations

import json
import hashlib
import os
import re
import tempfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from .catalog import ParquetMunicipalityCatalog
from .models import CatalogMetadata, Municipality
from .validation import validate_municipalities

SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


def _temporary_path(path: Path) -> Path:
    """Cria um nome temporário exclusivo no mesmo diretório do destino."""
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False,
    ) as temporary:
        return Path(temporary.name)


def catalog_content_sha256(records: list[Municipality] | tuple[Municipality, ...]) -> str:
    values = [asdict(item) for item in sorted(records, key=lambda item: item.code7)]
    payload = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_metadata(metadata: CatalogMetadata) -> None:
    if not metadata.catalog_id or not SHA256_PATTERN.fullmatch(metadata.sha256):
        raise ValueError("manifesto IBGE exige SHA-256 hexadecimal de 64 caracteres")
    if (
        not isinstance(metadata.reference_year, int)
        or isinstance(metadata.reference_year, bool)
        or metadata.reference_year <= 0
        or not isinstance(metadata.source_name, str)
        or not metadata.source_name.strip()
        or not isinstance(metadata.source_url, str)
        or not metadata.source_url.strip()
    ):
        raise ValueError(
            "manifesto IBGE exige ano, source_name, source_url e retrieved_at"
        )
    if not isinstance(metadata.retrieved_at, str) or not metadata.retrieved_at.strip():
        raise ValueError("manifesto IBGE exige retrieved_at ISO-8601")
    try:
        retrieved_at = datetime.fromisoformat(metadata.retrieved_at)
    except ValueError as exc:
        raise ValueError("manifesto IBGE exige retrieved_at ISO-8601") from exc
    if retrieved_at.tzinfo is None:
        raise ValueError("manifesto IBGE exige retrieved_at ISO-8601 com timezone")
    if metadata.content_sha256 is not None and not SHA256_PATTERN.fullmatch(metadata.content_sha256):
        raise ValueError("manifesto IBGE exige hash lógico hexadecimal de 64 caracteres")
    if metadata.promoted_at is not None:
        if not isinstance(metadata.promoted_at, str):
            raise ValueError("manifesto IBGE exige promoted_at ISO-8601")
        try:
            promoted_at = datetime.fromisoformat(metadata.promoted_at)
        except ValueError as exc:
            raise ValueError("manifesto IBGE exige promoted_at ISO-8601") from exc
        if promoted_at.tzinfo is None:
            raise ValueError("manifesto IBGE exige promoted_at ISO-8601 com timezone")
    if metadata.validation_status != "VALIDATED":
        raise ValueError("release IBGE não está validada")


def write_catalog(path: Path, records: list[Municipality] | tuple[Municipality, ...]) -> Path:
    values = tuple(sorted(validate_municipalities(records), key=lambda item: item.code7))
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        pd.DataFrame([asdict(item) for item in values]).to_parquet(temporary_path, index=False)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return path


def write_ufs(path: Path, records: list[Municipality] | tuple[Municipality, ...]) -> Path:
    values = validate_municipalities(records)
    frame = pd.DataFrame([
        {"uf_code": item.uf_code, "uf_abbr": item.uf_abbr, "uf_name": item.uf_name}
        for item in values
    ]).drop_duplicates(subset=["uf_code"]).sort_values("uf_code")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(path)
    try:
        frame.to_parquet(temporary, index=False)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def write_crosswalk(path: Path, records: list[Municipality] | tuple[Municipality, ...]) -> Path:
    values = validate_municipalities(records)
    frame = pd.DataFrame([
        {"code6": item.code6, "code7": item.code7, "reference_year": item.reference_year}
        for item in values
    ]).sort_values("code6")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(path)
    try:
        frame.to_parquet(temporary, index=False)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def write_release(path: Path, records: list[Municipality] | tuple[Municipality, ...]) -> Path:
    """Escreve os artefatos canônicos de uma release municipal."""
    values = tuple(sorted(validate_municipalities(records), key=lambda item: item.code7))
    parquet = write_catalog(path / "municipalities.parquet", values)
    write_ufs(path / "ufs.parquet", values)
    write_crosswalk(path / "code_crosswalk.parquet", values)
    return parquet


def write_manifest(path: Path, metadata: CatalogMetadata) -> Path:
    _validate_metadata(metadata)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(path)
    try:
        temporary.write_text(json.dumps(asdict(metadata), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def promote_active(active_path: Path, catalog_id: str) -> Path:
    _load_release(active_path.parent, catalog_id)
    active_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(active_path)
    try:
        temporary.write_text(json.dumps({"catalog_id": catalog_id}, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, active_path)
    finally:
        temporary.unlink(missing_ok=True)
    return active_path


def _load_release(root: Path, catalog_id: str) -> ParquetMunicipalityCatalog:
    if not isinstance(catalog_id, str) or not catalog_id or Path(catalog_id).name != catalog_id:
        raise ValueError("catalog_id inválido")
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
    _validate_metadata(metadata)
    catalog = ParquetMunicipalityCatalog(release / "municipalities.parquet", metadata)
    mismatched_years = sorted({item.reference_year for item in catalog.municipalities() if item.reference_year != metadata.reference_year})
    if mismatched_years:
        raise ValueError(
            "reference_year dos municípios diverge do manifesto: "
            f"manifesto={metadata.reference_year}, registros={mismatched_years}"
        )
    _validate_auxiliary_artifacts(release, catalog.municipalities())
    if metadata.content_sha256 is not None:
        actual_content_sha256 = catalog_content_sha256(catalog.municipalities())
        if actual_content_sha256 != metadata.content_sha256:
            raise ValueError("hash lógico do catálogo diverge do manifesto")
    return catalog


def _validate_auxiliary_artifacts(
    release: Path,
    records: tuple[Municipality, ...],
) -> None:
    """Confere artefatos derivados quando presentes na release.

    Releases antigas podem conter apenas ``municipalities.parquet`` e continuam
    legíveis. Releases novas, porém, não podem carregar um catálogo e publicar
    UFs/crosswalk divergentes dos mesmos registros canônicos.
    """
    expected_ufs = pd.DataFrame([
        {"uf_code": item.uf_code, "uf_abbr": item.uf_abbr, "uf_name": item.uf_name}
        for item in records
    ]).drop_duplicates(subset=["uf_code"]).sort_values("uf_code").reset_index(drop=True)
    expected_crosswalk = pd.DataFrame([
        {"code6": item.code6, "code7": item.code7, "reference_year": item.reference_year}
        for item in records
    ]).sort_values("code6").reset_index(drop=True)
    expected = {
        "ufs.parquet": expected_ufs,
        "code_crosswalk.parquet": expected_crosswalk,
    }
    for filename, expected_frame in expected.items():
        path = release / filename
        if not path.exists():
            continue
        try:
            actual = pd.read_parquet(path).reset_index(drop=True)
        except Exception as exc:
            raise ValueError(f"artefato auxiliar IBGE inválido: {path}") from exc
        if list(actual.columns) != list(expected_frame.columns):
            raise ValueError(f"esquema divergente no artefato auxiliar IBGE: {path}")
        if not actual.equals(expected_frame):
            raise ValueError(f"conteúdo divergente no artefato auxiliar IBGE: {path}")


def load_active_catalog(root: Path) -> ParquetMunicipalityCatalog:
    active_path = root / "active.json"
    try:
        active = json.loads(active_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"ponteiro ativo ausente: {active_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"ponteiro ativo inválido: {active_path}") from exc
    if not isinstance(active, dict):
        raise ValueError(f"ponteiro ativo inválido: {active_path}")
    catalog_id = active.get("catalog_id")
    if not isinstance(catalog_id, str) or not catalog_id or Path(catalog_id).name != catalog_id:
        raise ValueError("active.json não informa catalog_id")
    return _load_release(root, catalog_id)
