from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

import pandas as pd
import pyarrow.parquet as pq

from .. import run_cnes as service
from ..atomic_io import write_json_atomic
from .runner_metadata import publish_cnes_artifacts

def execute(
    municipios: dict[str, str] | None = None,
    *,
    catalog: MunicipalityCatalog | None = None,
    geographic_scope: GeographicScope | None = None,
    page_size: int = 100,
    session=None,
    request_timeout: float = 60.0,
    checkpoint_path: Path | None = None,
    continue_on_error: bool = False,
    workers: int = 1,
    geocoder: service.Geocoder | None = None,
) -> Path:
    stage_started = monotonic()
    if not isinstance(page_size, int) or isinstance(page_size, bool) or page_size <= 0:
        raise ValueError("page_size CNES deve ser um inteiro maior que zero")
    if not isinstance(request_timeout, (int, float)) or isinstance(request_timeout, bool) or request_timeout <= 0:
        raise ValueError("request_timeout CNES deve ser maior que zero")
    if not isinstance(workers, int) or isinstance(workers, bool) or workers <= 0:
        raise ValueError("workers CNES deve ser um inteiro maior que zero")
    if workers > 1 and session is not None:
        raise ValueError("workers CNES maior que um não aceita sessão compartilhada")
    if catalog is not None and geographic_scope is not None:
        service.validate_scope_catalog(catalog, geographic_scope)
    if geographic_scope is not None:
        municipios = {item.code7: item.name for item in geographic_scope.municipalities}
    elif catalog is not None:
        if municipios is not None:
            municipios = service._canonicalize_municipalities(municipios, catalog)
        else:
            municipios = {item.code7: item.name for item in service.select_scope(catalog).municipalities}
    else:
        municipios = municipios if municipios is not None else service.legacy_rj_mapping()
    if not municipios:
        raise ValueError("Informe ao menos um município para a carga CNES")
    checkpoint = None
    if checkpoint_path is not None and checkpoint_path.exists():
        try:
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"checkpoint CNES inválido: {checkpoint_path}") from exc
        if not isinstance(checkpoint, dict):
            raise ValueError(f"checkpoint CNES inválido: {checkpoint_path}")
        expected = {
            "municipios": list(municipios),
            "ibge_catalog_id": catalog.metadata.catalog_id if catalog else None,
            "ibge_catalog_sha256": catalog.metadata.sha256 if catalog else None,
            "cnes_page_size": page_size,
            "cnes_request_timeout": request_timeout,
            "continue_on_error": continue_on_error,
            "cnes_workers": workers,
            "cnes_geocoder": service._geocoder_identity(geocoder),
        }
        actual = {
            key: (
                checkpoint.get(key, False)
                if key == "continue_on_error"
                else checkpoint.get(key, 1)
                if key == "cnes_workers"
                else checkpoint.get(key)
            )
            for key in expected
        }
        if actual != expected:
            raise ValueError("checkpoint CNES não corresponde ao escopo ou parâmetros solicitados")
        try:
            run_at = datetime.fromisoformat(checkpoint["ingested_at"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("checkpoint CNES sem ingested_at válido") from exc
    else:
        run_at = datetime.now(UTC)
    completed = service._validate_checkpoint_completed((checkpoint or {}).get("completed", {}), municipios)
    failed = service._validate_checkpoint_failed((checkpoint or {}).get("failed", {}), municipios)
    if set(completed).intersection(failed):
        raise ValueError("checkpoint CNES classifica município como completed e failed")
    service.logger.info("Iniciando CNES municipios=%s", len(municipios))

    batch_id = run_at.strftime("%Y%m%dT%H%M%SZ")
    directory = service.BASE_DIR / "silver" / "cnes" / f"batch_id={batch_id}"
    silver_paths: list[Path] = []
    parts_directory_handle = tempfile.TemporaryDirectory(
        prefix=f".cnes-parts-{batch_id}-",
    )
    parts_directory = Path(parts_directory_handle.name)
    request_session = session or (service.session_with_retries() if workers == 1 else None)
    owns_session = session is None and request_session is not None
    pending_codes = [code for code in municipios if code not in completed]
    parallel_results = (
        iter(service._parallel_fetch_batches(
            pending_codes,
            page_size=page_size,
            catalog=catalog,
            request_timeout=request_timeout,
            workers=workers,
        ))
        if workers > 1
        else None
    )
    try:
        for cod_municipio in municipios:
            service.logger.info("Processando CNES municipio=%s", cod_municipio)
            if cod_municipio in failed:
                service.logger.info("Retentando município previamente classificado como falho: %s", cod_municipio)
                failed.pop(cod_municipio)
            checkpoint_entry = completed.get(cod_municipio)
            try:
                if checkpoint_entry is not None:
                    bronze_path = Path(checkpoint_entry.get("bronze_path", ""))
                    if not bronze_path.is_file():
                        raise ValueError(f"checkpoint CNES aponta para Bronze ausente: {bronze_path}")
                    expected_sha256 = checkpoint_entry.get("bronze_sha256")
                    actual_sha256 = hashlib.sha256(bronze_path.read_bytes()).hexdigest()
                    if expected_sha256 != actual_sha256:
                        raise ValueError(f"Bronze CNES adulterada ou incompatível: {bronze_path}")
                    bronze_df = pd.read_parquet(bronze_path)
                else:
                    if parallel_results is not None:
                        fetched_code, fetched = next(parallel_results)
                        if fetched_code != cod_municipio:
                            raise RuntimeError("resultado CNES paralelo fora de ordem")
                        if isinstance(fetched, Exception):
                            raise fetched
                        bronze_df = fetched
                    else:
                        bronze_df = service.fetch_estabelecimentos(
                            cod_municipio,
                            limit=page_size,
                            catalog=catalog,
                            session=request_session,
                            timeout=request_timeout,
                        )
                if bronze_df.empty:
                    raise RuntimeError(f"API CNES retornou vazio para município {cod_municipio}")

                bronze_path = (
                    Path(checkpoint_entry["bronze_path"])
                    if checkpoint_entry is not None
                    else service.write_bronze_cnes(bronze_df, cod_municipio, run_at=run_at)
                )
                silver = (
                    service.transform_cnes(bronze_df, catalog=catalog, municipality_code7=cod_municipio)
                    if catalog is not None
                    else service.transform_cnes(bronze_df, municipality_code7=cod_municipio)
                )
                service._validate_cnes_municipality_resolution(
                    silver, catalog=catalog, municipality_code7=cod_municipio,
                )
                territory_assets = service.asset_directory(cod_municipio, root=service.TERRITORY_ASSETS_DIR)
                municipality_geometry = (
                    service.load_municipality_geometry(territory_assets)
                    if territory_assets is not None
                    else None
                )
                municipality = catalog.get_municipality(cod_municipio) if catalog else None
                silver = service.enrich_missing_coordinates(
                    silver,
                    geocoder=geocoder,
                    municipality_geometry=municipality_geometry,
                    municipality_name=municipios[cod_municipio],
                    uf_abbr=municipality.uf_abbr if municipality else None,
                    attempted_at=run_at,
                )
                if territory_assets is not None:
                    silver = service.enrich_cnes_territories(silver, territory_assets)
                else:
                    silver["notification_district_id"] = pd.NA
                    silver["notification_neighborhood_id"] = pd.NA
                    silver["notification_territory_status"] = "UNAVAILABLE"
                silver["_part_order"] = len(silver_paths)
                silver_path = parts_directory / f"part-{len(silver_paths):06d}.parquet"
                silver.to_parquet(silver_path, index=False)
                silver_paths.append(silver_path)
                if checkpoint_path is not None and checkpoint_entry is None:
                    completed[cod_municipio] = {
                        "bronze_path": str(bronze_path),
                        "rows": len(bronze_df),
                        "bronze_sha256": hashlib.sha256(bronze_path.read_bytes()).hexdigest(),
                    }
            except Exception as error:
                if not continue_on_error:
                    raise
                failed[cod_municipio] = {
                    "error_type": service._classify_cnes_error(error),
                    "error_message": str(error),
                }
                service.logger.exception("Falha classificada no município CNES=%s", cod_municipio)
            if checkpoint_path is not None:
                write_json_atomic(
                    {
                        "status": "IN_PROGRESS",
                        "ingested_at": run_at.isoformat(),
                        "municipios": list(municipios),
                        "ibge_catalog_id": catalog.metadata.catalog_id if catalog else None,
                        "ibge_catalog_sha256": catalog.metadata.sha256 if catalog else None,
                        "cnes_page_size": page_size,
                        "cnes_request_timeout": request_timeout,
                        "continue_on_error": continue_on_error,
                        "cnes_workers": workers,
                        "cnes_geocoder": service._geocoder_identity(geocoder),
                        "completed": completed,
                        "failed": failed,
                    },
                    checkpoint_path,
                )
    finally:
        if owns_session and request_session is not None:
            request_session.close()

    parquet = directory / "data.parquet"
    try:
        rows = service._write_cnes_consolidated(silver_paths, parquet)
    finally:
        parts_directory_handle.cleanup()

    publish_cnes_artifacts(
        directory=directory, parquet=parquet, rows=rows, run_at=run_at,
        municipios=municipios, catalog=catalog, page_size=page_size,
        request_timeout=request_timeout, continue_on_error=continue_on_error,
        workers=workers, geocoder_identity=service._geocoder_identity(geocoder),
        failed=failed, completed=completed, checkpoint_path=checkpoint_path,
        stage_started=stage_started, export_metrics=service.export_stage_metrics,
        sha256_file=service._sha256_file,
        consolidated_municipalities=service._consolidated_municipalities,
        geocoding_status_counts=service._geocoding_status_counts,
        write_json=service.write_json_atomic,
        logger=service.logger,
    )
    return parquet

