from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import logging
import os
import tempfile
from time import monotonic
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow.parquet as pq
import requests

import fcntl

from .atomic_io import write_json_atomic, write_parquet_atomic
from .cnes.bronze import fetch_estabelecimentos, session_with_retries, write_bronze_cnes
from .cnes.geocoding import (
    Geocoder,
    NominatimGeocoder,
    enrich_missing_coordinates,
    load_municipality_geometry,
)
from .cnes.silver import transform_cnes
from .territory_mapping import enrich_cnes_territories
from .territory_assets import asset_directory
from .reference.ibge.models import MunicipalityCatalog, ResolutionStatus
from .reference.ibge.storage import load_active_catalog
from .scope import GeographicScope, legacy_rj_mapping, select_scope, validate_scope_catalog
from .observability import export_stage_metrics
from .cnes.runner_support import (
    canonicalize_municipalities as _canonicalize_municipalities,
    classify_error as _classify_cnes_error,
    consolidated_municipalities as _consolidated_municipalities,
    geocoder_identity as _geocoder_identity,
    geocoding_status_counts as _geocoding_status_counts,
    parallel_fetch_batches as _parallel_fetch_batches,
    sha256_file as _sha256_file,
    validate_checkpoint_completed as _validate_checkpoint_completed,
    validate_checkpoint_failed as _validate_checkpoint_failed,
    validate_municipality_resolution as _validate_cnes_municipality_resolution,
    write_consolidated as _write_cnes_consolidated,
)

BASE_DIR = Path(os.environ.get("PIPELINE_DATA_DIR", "/data"))
TERRITORY_ASSETS_DIR = Path(__file__).resolve().parents[2] / "territories"
logger = logging.getLogger(__name__)
DEFAULT_CNES_PAGE_SIZE = 100
DEFAULT_CNES_REQUEST_TIMEOUT = 60.0
_SHA256_LENGTH = 64
























from .cnes.runner_core import execute as _run_cnes


def run_cnes(
    municipios: dict[str, str] | None = None,
    *,
    catalog: MunicipalityCatalog | None = None,
    geographic_scope: GeographicScope | None = None,
    page_size: int = DEFAULT_CNES_PAGE_SIZE,
    session=None,
    request_timeout: float = DEFAULT_CNES_REQUEST_TIMEOUT,
    checkpoint_path: Path | None = None,
    continue_on_error: bool = False,
    workers: int = 1,
    geocoder: Geocoder | None = None,
) -> Path:
    """Executa CNES e publica falha fatal no Pushgateway quando necessário."""
    stage_started = monotonic()
    scope = (
        geographic_scope.kind
        if geographic_scope is not None
        else "CATALOG" if catalog is not None else "LEGACY"
    )
    try:
        return _run_cnes(
            municipios,
            catalog=catalog,
            geographic_scope=geographic_scope,
            page_size=page_size,
            session=session,
            request_timeout=request_timeout,
            checkpoint_path=checkpoint_path,
            continue_on_error=continue_on_error,
            workers=workers,
            geocoder=geocoder,
        )
    except Exception:
        try:
            export_stage_metrics(
                pipeline="cnes",
                layer="silver",
                disease="CNES",
                year=datetime.now(UTC).year,
                rows=0,
                duration_seconds=monotonic() - stage_started,
                status="failure",
                extra={"scope": scope, "batch_status": "FATAL"},
            )
        except Exception:  # noqa: BLE001 - nunca mascarar a falha original
            logger.warning("Falha ao registrar erro fatal do CNES", exc_info=True)
        raise


def main() -> None:
    from .run_cnes_cli import main as run_cli
    run_cli()


if __name__ == "__main__":
    main()
