from __future__ import annotations

import argparse
import json
import logging
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

_GOLD_QUALITY_METRICS = (
    "source_rows", "resolved_rows", "discarded_rows", "aggregation_reduction",
    "invalid_municipality_rows", "out_of_scope_rows", "uf_mismatch_rows",
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
) -> None:
    disease = disease.upper()
    if catalog is not None and geographic_scope is not None:
        validate_scope_catalog(catalog, geographic_scope)
    run_at = datetime.now(UTC)
    logger.info("Iniciando carga SINAN disease=%s year=%s", disease, year)

    source = source_path if source_path is not None else fetch_sinan(disease, year)
    bronze = write_bronze(source, disease, year, run_at=run_at)
    logger.info("Bronze concluída: %s", bronze)
    silver = transform_file(bronze, disease, year, run_at=run_at)
    logger.info("Silver concluída: %s", silver)

    if geographic_scope is not None:
        municipios = {item.code7: item.name for item in geographic_scope.municipalities}
    elif catalog is not None:
        municipios = {item.code7: item.name for item in select_scope(catalog).municipalities}
    else:
        municipios = legacy_rj_mapping()
    silver_scope = pd.read_parquet(silver, columns=["ID_MUNICIP", "SG_UF_NOT"])
    if silver_scope.empty:
        raise RuntimeError("Silver sem notificações válidas: publicação bloqueada")
    if catalog is None:
        expected_cases_total = int(
            normalize_municipality_codes(silver_scope["ID_MUNICIP"], municipios)
            .isin(municipios).sum()
        )
    else:
        resolved_codes = resolve_catalog_municipality_codes(
            silver_scope["ID_MUNICIP"], catalog, silver_scope.get("SG_UF_NOT")
        )
        expected_cases_total = int(resolved_codes.isin(municipios).sum())

    gold_path = aggregate_file(
        silver, disease, year, selected_columns=CANONICAL_GOLD_COLUMNS,
        municipios=municipios, catalog=catalog, run_at=run_at, target="serving",
        cnes_batch_id=cnes_batch_id,
        geographic_scope_type=geographic_scope.kind if geographic_scope else "MUNICIPALITIES",
    )

    gold_df = pd.read_parquet(gold_path)
    quality_metrics = {}
    metadata_path = gold_path.with_name("metadata.json")
    if metadata_path.exists():
        gold_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        quality_metrics = {
            key: int(gold_metadata[key])
            for key in (
                "source_rows", "resolved_rows", "discarded_rows", "aggregation_reduction",
                "invalid_municipality_rows", "out_of_scope_rows", "uf_mismatch_rows",
            )
            if key in gold_metadata
        }
    else:
        gold_metadata = {}
    if catalog is not None:
        missing_metrics = [key for key in _GOLD_QUALITY_METRICS if key not in gold_metadata]
        if missing_metrics:
            raise ValueError(
                "Publicação bloqueada: metadata.json da Gold não contém métricas obrigatórias "
                f"({', '.join(missing_metrics)})"
            )
        invalid_metrics = [
            key for key in _GOLD_QUALITY_METRICS
            if not isinstance(gold_metadata[key], int)
            or isinstance(gold_metadata[key], bool)
            or gold_metadata[key] < 0
        ]
        if invalid_metrics:
            raise ValueError(
                "Publicação bloqueada: métricas Gold inválidas "
                f"({', '.join(invalid_metrics)})"
            )
        if (
            gold_metadata["resolved_rows"] + gold_metadata["discarded_rows"]
            != gold_metadata["source_rows"]
            or gold_metadata["aggregation_reduction"] > gold_metadata["resolved_rows"]
        ):
            raise ValueError(
                "Publicação bloqueada: métricas Gold não reconciliam "
                "(source_rows, resolved_rows, discarded_rows, aggregation_reduction)"
            )
        expected_catalog_id = catalog.metadata.catalog_id
        expected_catalog_sha256 = catalog.metadata.sha256
        if (
            gold_metadata.get("ibge_catalog_id") != expected_catalog_id
            or gold_metadata.get("ibge_catalog_sha256") != expected_catalog_sha256
        ):
            raise ValueError(
                "Publicação bloqueada: release IBGE da Gold diverge da release "
                f"selecionada ({gold_metadata.get('ibge_catalog_id')!r}/"
                f"{gold_metadata.get('ibge_catalog_sha256')!r})"
            )
        if (
            gold_metadata.get("disease") != disease
            or gold_metadata.get("source_year") != year
            or gold_metadata.get("gold_target") != "serving"
        ):
            raise ValueError(
                "Publicação bloqueada: identidade da Gold diverge da execução "
                f"(disease={gold_metadata.get('disease')!r}, "
                f"source_year={gold_metadata.get('source_year')!r}, "
                f"gold_target={gold_metadata.get('gold_target')!r})"
            )
        expected_scope_type = geographic_scope.kind if geographic_scope else "MUNICIPALITIES"
        expected_scope_sha256 = scope_sha256(municipios)
        gold_scope = gold_metadata.get("geographic_scope")
        if (
            not isinstance(gold_scope, dict)
            or gold_scope.get("type") != expected_scope_type
            or gold_scope.get("municipality_count") != len(municipios)
            or gold_scope.get("scope_sha256") != expected_scope_sha256
        ):
            raise ValueError(
                "Publicação bloqueada: escopo geográfico da Gold diverge do escopo "
                "selecionado"
            )
        invalid_rows = int(gold_metadata.get("invalid_municipality_rows", 0))
        uf_mismatch_rows = int(gold_metadata.get("uf_mismatch_rows", 0))
        if invalid_rows or uf_mismatch_rows:
            raise ValueError(
                "Publicação bloqueada: Gold contém resoluções municipais inválidas "
                f"(invalid={invalid_rows}, uf_mismatch={uf_mismatch_rows})"
            )
    logger.info("Gold concluída: %s (linhas=%s)", gold_path, len(gold_df))
    batch_id = run_at.strftime("%Y%m%dT%H%M%SZ")

    engine = get_engine()
    try:
        logger.info("Publicando snapshot disease=%s year=%s batch_id=%s", disease, year, batch_id)
        load_gold_to_postgres(
            engine, gold_df, disease, batch_id, year=year, municipios=list(municipios),
            expected_cases_total=expected_cases_total, snapshot_complete=True,
            source_extracted_at=run_at, allow_empty=allow_empty,
            ibge_catalog=catalog,
            geographic_scope_type=geographic_scope.kind if geographic_scope else "MUNICIPALITIES",
            geographic_scope_sha256=scope_sha256(municipios),
            quality_metrics=quality_metrics,
        )
    finally:
        engine.dispose()

    logger.info(
        "Postgres: snapshot publicado disease=%s year=%s batch_id=%s cases=%s",
        disease, year, batch_id, expected_cases_total,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Roda a pipeline SINAN completa (grão fixo) e carrega o resultado no Postgres"
    )
    parser.add_argument("--disease", required=True, help="Ex.: DENG, TOXC, ZIKA")
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--allow-empty", action="store_true",
                        help="Permite publicar zero no recorte; usar após validar a ausência na origem")
    parser.add_argument("--catalog-root", type=Path, help="Diretório local de releases IBGE")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--municipios", help="Códigos municipais separados por vírgula")
    scope.add_argument("--ufs", help="UFs ou códigos de UF separados por vírgula")
    scope.add_argument(
        "--all-brazil", action="store_true",
        help="Seleciona todos os municípios da release IBGE",
    )
    parser.add_argument("--cnes-batch-id", help="Lote CNES fixado para o enriquecimento da Gold")
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = _build_parser()
    args = parser.parse_args()
    try:
        catalog = load_active_catalog(args.catalog_root) if args.catalog_root else None
        if (args.municipios or args.ufs or args.all_brazil) and catalog is None:
            raise ValueError("seleção geográfica exige --catalog-root")
        scope = None
        if catalog is not None:
            scope_kwargs = {
                "municipalities": args.municipios.split(",") if args.municipios else None,
                "ufs": args.ufs.split(",") if args.ufs else None,
                "all_brazil": args.all_brazil,
            }
            if args.all_brazil:
                scope_kwargs["require_national"] = True
            scope = select_scope(catalog, **scope_kwargs)
        run_load(
            args.disease, args.year, allow_empty=args.allow_empty,
            catalog=catalog, geographic_scope=scope,
            cnes_batch_id=args.cnes_batch_id,
        )
    except Exception:
        logger.exception("Falha na carga SINAN disease=%s year=%s", args.disease, args.year)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
