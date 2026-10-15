"""Atualizador diário dos snapshots SINAN e publicação na Gold Serving."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from .run_load import run_load
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


def update_one(remote: RemoteSinanFile, manifest: dict) -> str:
    key = f"{remote.disease}:{remote.year}"
    known_snapshot = manifest.get(key, {}).get("remoteSizeBytes") == remote.size_bytes
    if not is_changed(remote) and known_snapshot:
        manifest[key] = {
            "remotePath": remote.path,
            "remoteSizeBytes": remote.size_bytes,
            "localPath": str(remote.local_path),
            "localSizeBytes": remote.local_path.stat().st_size,
            "checkedAt": datetime.now(UTC).isoformat(),
            "status": "UNCHANGED",
        }
        return f"{key}: unchanged ({remote.size_bytes} bytes)"

    local_path = download_remote_file(remote)
    run_load(remote.disease, remote.year, source_path=local_path, allow_empty=True)
    manifest[key] = {
        "remotePath": remote.path,
        "remoteSizeBytes": remote.size_bytes,
        "localPath": str(local_path),
        "localSizeBytes": local_path.stat().st_size,
        "updatedAt": datetime.now(UTC).isoformat(),
        "status": "UPDATED",
    }
    return f"{key}: updated ({remote.size_bytes} bytes)"


def update(diseases: list[str], years: list[int], manifest_path: Path = MANIFEST_PATH) -> list[str]:
    manifest = _load_manifest(manifest_path)
    results: list[str] = []
    for disease in diseases:
        for year in years:
            logger.info("Verificando SINAN disease=%s year=%s", disease, year)
            try:
                remote = inspect_remote_file(disease, year)
                result = update_one(remote, manifest)
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
    args = parser.parse_args()
    diseases = [value.strip().upper() for value in args.diseases.split(",") if value.strip()]
    unknown = sorted(set(diseases) - set(TRACKED_DISEASES))
    if unknown:
        raise SystemExit(f"Doenças não acompanhadas: {', '.join(unknown)}")
    if not diseases:
        parser.error("Informe ao menos uma doença em --diseases")
    try:
        update(diseases, _parse_years(args.years), args.manifest)
    except Exception:
        logger.exception("Falha no atualizador SINAN (manifesto=%s)", args.manifest)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
