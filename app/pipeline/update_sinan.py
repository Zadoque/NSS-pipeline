"""Atualizador diário dos snapshots SINAN e publicação na Gold Serving."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from .run_load import run_load
from .reference.ibge.models import MunicipalityCatalog
from .sinan.source import RemoteSinanFile, download_remote_file, inspect_remote_file, is_changed

TRACKED_DISEASES = ("DENG", "CHIK", "ZIKA", "FMAC", "TOXC", "TOXG")
MANIFEST_PATH = Path("/data/source/sinan/manifest.json")
logger = logging.getLogger(__name__)


def _parse_years(raw: str | None) -> list[int]:
    if not raw:
        return [datetime.now(UTC).year]
    years = sorted({int(value.strip()) for value in raw.split(",") if value.strip()})
    if not years or any(year < 2000 or year > 9999 for year in years):
        raise ValueError("years deve conter anos entre 2000 e 9999")
    return years


def _load_manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Manifesto SINAN contém JSON inválido: {path}") from exc
    if not isinstance(manifest, dict) or any(
        not isinstance(value, dict) for value in manifest.values()
    ):
        raise ValueError(f"Manifesto SINAN deve conter um objeto por recorte: {path}")
    return manifest


def _save_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def update_one(remote: RemoteSinanFile, manifest: dict, catalog: MunicipalityCatalog | None = None) -> str:
    key = f"{remote.disease}:{remote.year}"
    catalog_id = catalog.metadata.catalog_id if catalog else None
    catalog_sha256 = catalog.metadata.sha256 if catalog else None
    known_snapshot = manifest.get(key, {}).get("remoteSizeBytes") == remote.size_bytes
    if catalog is not None:
        known_snapshot = known_snapshot and (
            manifest.get(key, {}).get("ibgeCatalogId") == catalog_id
            and manifest.get(key, {}).get("ibgeCatalogSha256") == catalog_sha256
        )
    if not is_changed(remote) and known_snapshot:
        manifest[key] = {
            "remotePath": remote.path,
            "remoteSizeBytes": remote.size_bytes,
            "localPath": str(remote.local_path),
            "localSizeBytes": remote.local_path.stat().st_size,
            "checkedAt": datetime.now(UTC).isoformat(),
            "status": "UNCHANGED",
            "ibgeCatalogId": catalog_id,
            "ibgeCatalogSha256": catalog_sha256,
        }
        return f"{key}: unchanged ({remote.size_bytes} bytes)"

    local_path = download_remote_file(remote)
    load_options = {"source_path": local_path, "allow_empty": True}
    if catalog is not None:
        load_options["catalog"] = catalog
    run_load(remote.disease, remote.year, **load_options)
    manifest[key] = {
        "remotePath": remote.path,
        "remoteSizeBytes": remote.size_bytes,
        "localPath": str(local_path),
        "localSizeBytes": local_path.stat().st_size,
        "updatedAt": datetime.now(UTC).isoformat(),
        "status": "UPDATED",
        "ibgeCatalogId": catalog_id,
        "ibgeCatalogSha256": catalog_sha256,
    }
    return f"{key}: updated ({remote.size_bytes} bytes)"


def update(
    diseases: list[str], years: list[int], manifest_path: Path = MANIFEST_PATH,
    catalog: MunicipalityCatalog | None = None,
) -> list[str]:
    manifest = _load_manifest(manifest_path)
    results: list[str] = []
    for disease in diseases:
        for year in years:
            logger.info("Verificando SINAN disease=%s year=%s", disease, year)
            try:
                remote = inspect_remote_file(disease, year)
                result = update_one(remote, manifest, catalog=catalog)
                _save_manifest(manifest_path, manifest)
            except Exception:
                logger.error("Falha na atualização SINAN disease=%s year=%s", disease, year)
                raise
            results.append(result)
            logger.info("%s", result)
    return results


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Verifica e publica atualizações diárias do SINAN")
    parser.add_argument(
        "--diseases", default=",".join(TRACKED_DISEASES),
        help="Códigos PySUS separados por vírgula",
    )
    parser.add_argument("--years", help="Anos separados por vírgula; padrão: ano UTC atual")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--catalog-root", type=Path, help="Diretório local da release IBGE ativa")
    args = parser.parse_args()
    diseases = [value.strip().upper() for value in args.diseases.split(",") if value.strip()]
    unknown = sorted(set(diseases) - set(TRACKED_DISEASES))
    if unknown:
        raise SystemExit(f"Doenças não acompanhadas: {', '.join(unknown)}")
    if not diseases:
        parser.error("Informe ao menos uma doença em --diseases")
    try:
        from .reference.ibge.storage import load_active_catalog
        catalog = load_active_catalog(args.catalog_root) if args.catalog_root else None
        update(diseases, _parse_years(args.years), args.manifest, catalog=catalog)
    except Exception:
        logger.exception("Falha no atualizador SINAN (manifesto=%s)", args.manifest)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
