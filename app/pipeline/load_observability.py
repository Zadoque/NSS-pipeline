from __future__ import annotations

import json
from pathlib import Path
from time import monotonic

import pyarrow.parquet as pq


def parquet_rows(path: Path, *, logger) -> int:
    try:
        return int(pq.ParquetFile(path).metadata.num_rows)
    except (OSError, ValueError):
        logger.debug("Não foi possível ler contagem auxiliar de métricas: %s", path)
        return 0


def stage_metadata(path: Path) -> dict:
    try:
        value = json.loads(path.with_name("metadata.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def export_failure(*, exporter, logger, layer: str, disease: str, year: int, started: float, extra=None) -> None:
    try:
        exporter(
            pipeline="sinan", layer=layer, disease=disease, year=year, rows=0,
            duration_seconds=monotonic() - started, status="failure", extra=extra,
        )
    except Exception:  # noqa: BLE001 - nunca mascarar a falha operacional original
        logger.warning("Falha ao registrar erro da etapa %s", layer, exc_info=True)
