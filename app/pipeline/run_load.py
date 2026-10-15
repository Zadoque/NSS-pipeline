from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime

import pandas as pd

from .sinan.columns import CANONICAL_GOLD_COLUMNS
from .sinan.gold import MUNICIPIOS_RJ, aggregate_file, normalize_municipality_codes
from .load import get_engine, load_gold_to_postgres
from .sinan.silver import transform_file
from .sinan.bronze import fetch_sinan, write_bronze

logger = logging.getLogger(__name__)

def run_load(
    disease: str,
    year: int,
    *,
    allow_empty: bool = False,
    source_path=None,
) -> None:
    disease = disease.upper()
    run_at = datetime.now(UTC)
    logger.info("Iniciando carga SINAN disease=%s year=%s", disease, year)

    source = source_path if source_path is not None else fetch_sinan(disease, year)
    bronze = write_bronze(source, disease, year, run_at=run_at)
    logger.info("Bronze concluída: %s", bronze)
    silver = transform_file(bronze, disease, year, run_at=run_at)
    logger.info("Silver concluída: %s", silver)

    municipios = dict(MUNICIPIOS_RJ)
    silver_scope = pd.read_parquet(silver, columns=["ID_MUNICIP"])
    if silver_scope.empty:
        raise RuntimeError("Silver sem notificações válidas: publicação bloqueada")
    expected_cases_total = int(
        normalize_municipality_codes(silver_scope["ID_MUNICIP"], municipios)
        .isin(municipios).sum()
    )

    gold_path = aggregate_file(
        silver, disease, year, selected_columns=CANONICAL_GOLD_COLUMNS,
        municipios=municipios, run_at=run_at, target="serving",
    )

    gold_df = pd.read_parquet(gold_path)
    logger.info("Gold concluída: %s (linhas=%s)", gold_path, len(gold_df))
    batch_id = run_at.strftime("%Y%m%dT%H%M%SZ")

    engine = get_engine()
    try:
        logger.info("Publicando snapshot disease=%s year=%s batch_id=%s", disease, year, batch_id)
        load_gold_to_postgres(
            engine, gold_df, disease, batch_id, year=year, municipios=list(municipios),
            expected_cases_total=expected_cases_total, snapshot_complete=True,
            source_extracted_at=run_at, allow_empty=allow_empty,
        )
    finally:
        engine.dispose()

    logger.info(
        "Postgres: snapshot publicado disease=%s year=%s batch_id=%s cases=%s",
        disease, year, batch_id, expected_cases_total,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(
        description="Roda a pipeline SINAN completa (grão fixo) e carrega o resultado no Postgres"
    )
    parser.add_argument("--disease", required=True, help="Ex.: DENG, TOXC, ZIKA")
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--allow-empty", action="store_true",
                        help="Permite publicar zero no recorte; usar após validar a ausência na origem")
    args = parser.parse_args()
    try:
        run_load(args.disease, args.year, allow_empty=args.allow_empty)
    except Exception:
        logger.exception("Falha na carga SINAN disease=%s year=%s", args.disease, args.year)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
