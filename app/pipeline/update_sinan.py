"""Atualizador diário dos snapshots SINAN e publicação na Gold Serving."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from .atomic_io import write_json_atomic
from .run_load import run_load
from .load import DISEASE_NAMES
from .reference.ibge.models import MunicipalityCatalog
from .scope import GeographicScope
from .sinan.source import (
    RemoteSinanFile,
    SinanSourceUnavailable,
    download_remote_file,
    inspect_remote_file,
    is_changed,
    sha256_file,
)

# O catálogo operacional acompanha todos os grupos SINAN publicados pelo
# PySUS. A opção ``--diseases`` continua permitindo recortes menores, mas o
# padrão não pode silenciosamente deixar doenças nacionais de fora.
TRACKED_DISEASES = tuple(DISEASE_NAMES)
MANIFEST_PATH = Path("/data/source/sinan/manifest.json")
logger = logging.getLogger(__name__)


@contextmanager
def _manifest_lock(path: Path):
    """Serializa atualizações que compartilham o cache DuckDB do PySUS."""
    lock_path = path.with_name(f".{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)



def _parse_years(raw: str | None) -> list[int]:
    if not raw:
        return [datetime.now(UTC).year]
    values = [value.strip() for value in raw.split(",")]
    if any(not value for value in values):
        raise ValueError("years não pode conter valores vazios")
    years = sorted({int(value) for value in values})
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
    write_json_atomic(manifest, path)


def update_one(
    remote: RemoteSinanFile,
    manifest: dict,
    catalog: MunicipalityCatalog | None = None,
    cnes_batch_id: str | None = None,
    geographic_scope: GeographicScope | None = None,
    allow_uf_mismatch: bool = False,
) -> str:
    key = f"{remote.disease}:{remote.year}"
    catalog_id = catalog.metadata.catalog_id if catalog else None
    catalog_sha256 = catalog.metadata.sha256 if catalog else None
    previous = manifest.get(key, {})
    if remote.sha256 is not None:
        known_snapshot = previous.get("remoteSha256") == remote.sha256
    else:
        known_snapshot = previous.get("remoteSizeBytes") == remote.size_bytes
    if catalog is not None:
        known_snapshot = known_snapshot and (
            manifest.get(key, {}).get("ibgeCatalogId") == catalog_id
            and manifest.get(key, {}).get("ibgeCatalogSha256") == catalog_sha256
        )
    if not is_changed(remote) and known_snapshot:
        manifest[key] = {
            "remotePath": remote.path,
            "remoteSizeBytes": remote.size_bytes,
            "remoteSha256": remote.sha256,
            "localPath": str(remote.local_path),
            "localSizeBytes": remote.local_path.stat().st_size,
            "localSha256": sha256_file(remote.local_path),
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
    if cnes_batch_id is not None:
        load_options["cnes_batch_id"] = cnes_batch_id
    if geographic_scope is not None:
        load_options["geographic_scope"] = geographic_scope
    if allow_uf_mismatch:
        load_options["allow_uf_mismatch"] = True
    run_load(remote.disease, remote.year, **load_options)
    manifest[key] = {
        "remotePath": remote.path,
        "remoteSizeBytes": remote.size_bytes,
        "remoteSha256": remote.sha256,
        "localPath": str(local_path),
        "localSizeBytes": local_path.stat().st_size,
        "localSha256": sha256_file(local_path),
        "updatedAt": datetime.now(UTC).isoformat(),
        "status": "UPDATED",
        "ibgeCatalogId": catalog_id,
        "ibgeCatalogSha256": catalog_sha256,
    }
    return f"{key}: updated ({remote.size_bytes} bytes)"


def _update_unlocked(
    diseases: list[str], years: list[int], manifest_path: Path = MANIFEST_PATH,
    catalog: MunicipalityCatalog | None = None,
    cnes_batch_id: str | None = None,
    geographic_scope: GeographicScope | None = None,
    continue_on_error: bool = False,
    allow_uf_mismatch: bool = False,
) -> list[str]:
    manifest = _load_manifest(manifest_path)
    results: list[str] = []
    for disease in diseases:
        for year in years:
            logger.info("Verificando SINAN disease=%s year=%s", disease, year)
            try:
                remote = inspect_remote_file(disease, year)
                result = update_one(
                    remote, manifest, catalog=catalog, cnes_batch_id=cnes_batch_id,
                    geographic_scope=geographic_scope,
                    allow_uf_mismatch=allow_uf_mismatch,
                )
                _save_manifest(manifest_path, manifest)
            except SinanSourceUnavailable as exc:
                key = f"{disease}:{year}"
                manifest[key] = {
                    "remotePath": None,
                    "remoteSizeBytes": None,
                    "checkedAt": datetime.now(UTC).isoformat(),
                    "status": "UNAVAILABLE",
                    "reason": str(exc),
                    "ibgeCatalogId": catalog.metadata.catalog_id if catalog else None,
                    "ibgeCatalogSha256": catalog.metadata.sha256 if catalog else None,
                }
                _save_manifest(manifest_path, manifest)
                result = f"{key}: unavailable"
                logger.warning("%s: %s", result, exc)
            except Exception as exc:
                key = f"{disease}:{year}"
                manifest[key] = {
                    "remotePath": remote.path if "remote" in locals() else None,
                    "remoteSizeBytes": remote.size_bytes if "remote" in locals() else None,
                    "checkedAt": datetime.now(UTC).isoformat(),
                    "status": "FAILED",
                    "reason": str(exc),
                    "ibgeCatalogId": catalog.metadata.catalog_id if catalog else None,
                    "ibgeCatalogSha256": catalog.metadata.sha256 if catalog else None,
                }
                _save_manifest(manifest_path, manifest)
                logger.exception("Falha na atualização SINAN disease=%s year=%s", disease, year)
                if not continue_on_error:
                    raise
                result = f"{key}: failed"
            results.append(result)
            logger.info("%s", result)
    return results


def update(
    diseases: list[str], years: list[int], manifest_path: Path = MANIFEST_PATH,
    catalog: MunicipalityCatalog | None = None,
    cnes_batch_id: str | None = None,
    geographic_scope: GeographicScope | None = None,
    continue_on_error: bool = False,
    allow_uf_mismatch: bool = False,
) -> list[str]:
    with _manifest_lock(manifest_path):
        return _update_unlocked(
            diseases, years, manifest_path, catalog=catalog, cnes_batch_id=cnes_batch_id,
            geographic_scope=geographic_scope,
            continue_on_error=continue_on_error,
            allow_uf_mismatch=allow_uf_mismatch,
        )


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
    parser.add_argument(
        "--all-brazil", action="store_true",
        help="Publica no escopo nacional da release IBGE ativa",
    )
    parser.add_argument(
        "--cnes-batch-id",
        help="Lote CNES explícito usado pela Gold serving",
    )
    parser.add_argument(
        "--allow-unavailable", action="store_true",
        help="Conclui com sucesso mesmo quando algum grupo não possui Parquet no ano",
    )
    parser.add_argument(
        "--continue-on-error", action="store_true",
        help="Registra falhas de schema/processamento e continua nos demais grupos",
    )
    parser.add_argument(
        "--allow-uf-mismatch", action="store_true",
        help="Canoniza pelo código IBGE e preserva a contagem de UF inconsistente na qualidade",
    )
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
        if args.all_brazil and catalog is None:
            raise ValueError("--all-brazil exige --catalog-root")
        geographic_scope = None
        if args.all_brazil:
            from .scope import select_scope
            geographic_scope = select_scope(
                catalog, all_brazil=True, require_national=True,
            )
        results = update(
            diseases, _parse_years(args.years), args.manifest,
            catalog=catalog, cnes_batch_id=args.cnes_batch_id,
            geographic_scope=geographic_scope,
            continue_on_error=args.continue_on_error,
            allow_uf_mismatch=args.allow_uf_mismatch,
        ) or []
        unavailable = [result for result in results if result.endswith(": unavailable")]
        if unavailable and not args.allow_unavailable:
            logger.error(
                "Fontes SINAN indisponíveis; manifesto preservado: %s",
                ", ".join(unavailable),
            )
            raise SystemExit(3)
    except Exception:
        logger.exception("Falha no atualizador SINAN (manifesto=%s)", args.manifest)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
