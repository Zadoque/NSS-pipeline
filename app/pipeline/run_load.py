from __future__ import annotations

import argparse
import logging
from time import monotonic
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .sinan.columns import CANONICAL_GOLD_COLUMNS
from .sinan.gold import (
    aggregate_file,
    normalize_municipality_codes,
    resolve_catalog_municipality_codes,
)
from .load import get_engine, load_gold_to_postgres
from .observability import export_stage_metrics
from .load_observability import export_failure, parquet_rows, stage_metadata
from .load_validation import validate_gold_for_publication
from .sinan.silver import transform_file
from .sinan.bronze import fetch_sinan, write_bronze
from .reference.ibge.models import MunicipalityCatalog
from .reference.ibge.storage import load_active_catalog
from .scope import (
    GeographicScope,
    legacy_rj_mapping,
    scope_sha256,
    select_scope,
    validate_scope_catalog,
)

logger = logging.getLogger(__name__)

def _export_stage_failure(*, layer: str, disease: str, year: int, started: float, extra=None) -> None:
    export_failure(
        exporter=export_stage_metrics, logger=logger, layer=layer,
        disease=disease, year=year, started=started, extra=extra,
    )

def run_load(
    disease: str,
    year: int,
    *,
    allow_empty: bool = False,
    source_path=None,
    catalog: MunicipalityCatalog | None = None,
    geographic_scope: GeographicScope | None = None,
    cnes_batch_id: str | None = None,
    allow_uf_mismatch: bool = False,
) -> None:
    disease = disease.upper()
    if catalog is not None and geographic_scope is not None:
        validate_scope_catalog(catalog, geographic_scope)
    run_at = datetime.now(UTC)
    logger.info("Iniciando carga SINAN disease=%s year=%s", disease, year)

    stage_started = monotonic()
    try:
        source = source_path if source_path is not None else fetch_sinan(disease, year)
        bronze = write_bronze(source, disease, year, run_at=run_at, allow_empty=allow_empty)
    except Exception:
        _export_stage_failure(layer="bronze", disease=disease, year=year, started=stage_started)
        raise
    export_stage_metrics(
        pipeline="sinan", layer="bronze", disease=disease, year=year,
        rows=parquet_rows(bronze, logger=logger),
        duration_seconds=monotonic() - stage_started,
    )
    logger.info("Bronze concluída: %s", bronze)
    stage_started = monotonic()
    try:
        silver = transform_file(bronze, disease, year, run_at=run_at)
    except Exception:
        _export_stage_failure(layer="silver", disease=disease, year=year, started=stage_started)
        raise
    silver_metadata = stage_metadata(silver)
    export_stage_metrics(
        pipeline="sinan", layer="silver", disease=disease, year=year,
        rows=int(silver_metadata.get("rows", 0)),
        dropped_rows=int(silver_metadata.get("dropped_rows", 0)),
        anomalous_dropped_rows=int(silver_metadata.get("invalid_date_rows", 0)),
        duration_seconds=monotonic() - stage_started,
    )
    logger.info("Silver concluída: %s", silver)

    if geographic_scope is not None:
        municipios = {item.code7: item.name for item in geographic_scope.municipalities}
    elif catalog is not None:
        municipios = {item.code7: item.name for item in select_scope(catalog).municipalities}
    else:
        municipios = legacy_rj_mapping()
    silver_scope = pd.read_parquet(silver, columns=["ID_MUNICIP", "SG_UF_NOT"])
    if silver_scope.empty and not allow_empty:
        raise RuntimeError("Silver sem notificações válidas: publicação bloqueada")
    if catalog is None:
        expected_cases_total = int(
            normalize_municipality_codes(silver_scope["ID_MUNICIP"], municipios)
            .isin(municipios).sum()
        )
    else:
        resolved_codes = resolve_catalog_municipality_codes(
            silver_scope["ID_MUNICIP"], catalog, silver_scope.get("SG_UF_NOT"),
            allow_uf_mismatch=allow_uf_mismatch,
        )
        expected_cases_total = int(resolved_codes.isin(municipios).sum())

    stage_started = monotonic()
    try:
        gold_path = aggregate_file(
            silver, disease, year, selected_columns=CANONICAL_GOLD_COLUMNS,
            municipios=municipios, catalog=catalog, run_at=run_at, target="serving",
            cnes_batch_id=cnes_batch_id,
            geographic_scope_type=geographic_scope.kind if geographic_scope else "MUNICIPALITIES",
            allow_uf_mismatch=allow_uf_mismatch,
        )

        gold_df = pd.read_parquet(gold_path)
        gold_metadata, quality_metrics, expected_cases_total = validate_gold_for_publication(
            gold_path, catalog=catalog, disease=disease, year=year,
            municipios=municipios, geographic_scope=geographic_scope,
            expected_cases_total=expected_cases_total,
        )
    except Exception:
        _export_stage_failure(
            layer="gold", disease=disease, year=year, started=stage_started,
            extra={"scope": geographic_scope.kind if geographic_scope else "MUNICIPALITIES"},
        )
        raise
    logger.info("Gold concluída: %s (linhas=%s)", gold_path, len(gold_df))
    export_stage_metrics(
        pipeline="sinan", layer="gold", disease=disease, year=year,
        rows=len(gold_df), dropped_rows=int(gold_metadata.get("discarded_rows", 0)),
        anomalous_dropped_rows=(
            int(gold_metadata.get("invalid_municipality_rows", 0))
            + int(gold_metadata.get("uf_mismatch_rows", 0))
        ),
        duration_seconds=monotonic() - stage_started,
        extra={"scope": geographic_scope.kind if geographic_scope else "MUNICIPALITIES"},
    )
    batch_id = run_at.strftime("%Y%m%dT%H%M%SZ")

    engine = get_engine()
    try:
        stage_started = monotonic()
        logger.info("Publicando snapshot disease=%s year=%s batch_id=%s", disease, year, batch_id)
        try:
            load_gold_to_postgres(
                engine, gold_df, disease, batch_id, year=year, municipios=list(municipios),
                expected_cases_total=expected_cases_total, snapshot_complete=True,
                source_extracted_at=run_at, allow_empty=allow_empty,
                ibge_catalog=catalog,
                geographic_scope_type=geographic_scope.kind if geographic_scope else "MUNICIPALITIES",
                geographic_scope_sha256=scope_sha256(municipios),
                quality_metrics=quality_metrics,
            )
        except Exception:
            _export_stage_failure(
                layer="postgresql", disease=disease, year=year, started=stage_started,
                extra={"scope": geographic_scope.kind if geographic_scope else "MUNICIPALITIES"},
            )
            raise
        export_stage_metrics(
            pipeline="sinan", layer="postgresql", disease=disease, year=year,
            rows=len(gold_df), duration_seconds=monotonic() - stage_started,
            extra={"scope": geographic_scope.kind if geographic_scope else "MUNICIPALITIES"},
        )
    finally:
        engine.dispose()

    logger.info(
        "Postgres: snapshot publicado disease=%s year=%s batch_id=%s cases=%s",
        disease, year, batch_id, expected_cases_total,
    )


def _build_parser() -> argparse.ArgumentParser:
    from .load_parser import build_parser
    return build_parser()


def main() -> None:
    from .run_load_cli import main as run_cli
    run_cli()


if __name__ == "__main__":
    main()
