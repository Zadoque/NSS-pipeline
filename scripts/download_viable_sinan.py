"""Baixa Parquets SINAN publicados sem executar a carga Gold.

Use este comando para preparar um snapshot nacional antes de decidir quais
recortes têm volume viável para processamento. A ausência no catálogo é
registrada, nunca substituída por um arquivo vazio.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from app.pipeline.load import DISEASE_NAMES
from app.pipeline.sinan.source import (
    SinanSourceUnavailable,
    download_remote_file,
    inspect_remote_file,
    is_changed,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--diseases", default=",".join(DISEASE_NAMES))
    parser.add_argument("--summary", type=Path, default=Path("/data/source/sinan/download-summary.json"))
    args = parser.parse_args()
    diseases = [value.strip().upper() for value in args.diseases.split(",") if value.strip()]
    unknown = sorted(set(diseases) - set(DISEASE_NAMES))
    if unknown:
        parser.error(f"doenças desconhecidas: {', '.join(unknown)}")

    rows: list[dict[str, object]] = []
    for disease in diseases:
        try:
            remote = inspect_remote_file(disease, args.year)
            status = "UNCHANGED"
            if is_changed(remote):
                download_remote_file(remote)
                status = "DOWNLOADED"
            row = {
                "disease": disease,
                "year": args.year,
                "status": status,
                "remotePath": remote.path,
                "sizeBytes": remote.size_bytes,
                "localPath": str(remote.local_path),
            }
        except SinanSourceUnavailable as error:
            row = {"disease": disease, "year": args.year, "status": "UNAVAILABLE", "reason": str(error)}
        except Exception as error:  # keep the other diseases auditable
            row = {"disease": disease, "year": args.year, "status": "FAILED", "reason": f"{type(error).__name__}: {error}"}
        rows.append(row)
        print(f"{disease}/{args.year} {row['status']}", flush=True)

    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps({
        "generatedAt": datetime.now(UTC).isoformat(),
        "year": args.year,
        "totalDiseases": len(diseases),
        "rows": rows,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = {status: sum(row["status"] == status for row in rows) for status in ("DOWNLOADED", "UNCHANGED", "UNAVAILABLE", "FAILED")}
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == "__main__":
    main()
