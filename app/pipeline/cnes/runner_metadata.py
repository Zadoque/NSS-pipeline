from __future__ import annotations

from pathlib import Path
from time import monotonic

import pyarrow.parquet as pq

from ..atomic_io import write_json_atomic


def publish_cnes_artifacts(
    *,
    directory: Path,
    parquet: Path,
    rows: int,
    run_at,
    municipios: dict[str, str],
    catalog,
    page_size: int,
    request_timeout: float,
    continue_on_error: bool,
    workers: int,
    geocoder_identity: str | None,
    failed: dict,
    completed: dict,
    checkpoint_path: Path | None,
    stage_started: float,
    export_metrics,
    sha256_file,
    consolidated_municipalities,
    geocoding_status_counts,
    write_json,
    logger,
) -> None:
    status = "COMPLETED" if not failed else "PARTIAL"
    metadata = {
        "manifest_version": 2, "status": status,
        "batch_id": run_at.strftime("%Y%m%dT%H%M%SZ"), "ingested_at": run_at.isoformat(),
        "rows": rows, "municipios": list(municipios),
        "ibge_catalog_id": catalog.metadata.catalog_id if catalog else None,
        "ibge_catalog_sha256": catalog.metadata.sha256 if catalog else None,
        "cnes_page_size": page_size, "cnes_request_timeout": request_timeout,
        "continue_on_error": continue_on_error, "cnes_workers": workers,
        "cnes_geocoder": geocoder_identity, "failed_municipalities": failed,
        "columns": pq.ParquetFile(parquet).schema.names,
        "parquet_sha256": sha256_file(parquet),
        "municipios_com_registros": consolidated_municipalities(parquet),
        "geocoding_status_counts": geocoding_status_counts(parquet),
    }
    metadata["municipios_sem_registros"] = sorted(set(municipios) - set(metadata["municipios_com_registros"]))
    write_json(metadata, directory / "metadata.json")
    export_metrics(
        pipeline="cnes", layer="silver", disease="CNES", year=run_at.year,
        rows=rows, duration_seconds=monotonic() - stage_started,
        status="success" if status == "COMPLETED" else "failure",
        dropped_rows=len(failed), extra={"scope": "CATALOG" if catalog is not None else "LEGACY", "batch_status": status},
    )
    if checkpoint_path is not None:
        write_json({
            "status": status, "ingested_at": run_at.isoformat(), "municipios": list(municipios),
            "ibge_catalog_id": catalog.metadata.catalog_id if catalog else None,
            "ibge_catalog_sha256": catalog.metadata.sha256 if catalog else None,
            "cnes_page_size": page_size, "cnes_request_timeout": request_timeout,
            "continue_on_error": continue_on_error, "cnes_workers": workers,
            "cnes_geocoder": geocoder_identity, "completed": completed,
            "failed": failed, "output_path": str(parquet),
        }, checkpoint_path)
    logger.info("CNES concluído: %s (linhas=%s)", parquet, rows)
