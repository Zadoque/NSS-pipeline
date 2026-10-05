"""Atualizador diário dos snapshots SINAN e publicação na Gold Serving."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from .run_load import run_load
from .sinan.source import RemoteSinanFile, download_remote_file, inspect_remote_file, is_changed

TRACKED_DISEASES = ("DENG", "CHIK", "ZIKA", "FMAC", "TOXC", "TOXG")
MANIFEST_PATH = Path("/data/source/sinan/manifest.json")


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
    return json.loads(path.read_text(encoding="utf-8"))


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
    # O arquivo remoto não vazio pode não conter notificações do município
    # monitorado. Nesse caso o zero é validado pela origem e publicado como
    # snapshot vazio; um arquivo remoto realmente vazio continua bloqueado
    # pelo run_load.
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
            remote = inspect_remote_file(disease, year)
            results.append(update_one(remote, manifest))
            _save_manifest(manifest_path, manifest)
    return results


def main() -> None:
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
    for result in update(diseases, _parse_years(args.years), args.manifest):
        print(result)


if __name__ == "__main__":
    main()
