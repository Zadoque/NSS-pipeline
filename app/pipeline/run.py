from __future__ import annotations
 
import argparse
import logging
from datetime import UTC, datetime
from pathlib import Path
 
from .sinan.columns import CATALOG
from .sinan.gold import aggregate_file
from .sinan.bronze import fetch_sinan, write_bronze
from .sinan.silver import transform_file
 
BASE_DIR = Path("/data")
logger = logging.getLogger(__name__)
 
 
def run(disease: str, year: int, selected_columns: list[str] | None = None) -> None:
    disease = disease.upper()
    run_at = datetime.now(UTC)          
    logger.info("Iniciando SINAN disease=%s year=%s", disease, year)

    source = fetch_sinan(disease, year)
    bronze = write_bronze(source, disease, year, run_at=run_at)
    logger.info("Bronze concluída: %s", bronze)
    silver = transform_file(bronze, disease, year, run_at=run_at)
    logger.info("Silver concluída: %s", silver)
    gold = aggregate_file(
        silver, disease, year, selected_columns, run_at=run_at, target="ad_hoc"
    )

    logger.info("Gold concluída: %s", gold)
 
def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Pipeline Medallion do SINAN")
    parser.add_argument("--disease", required=True, help="Ex.: DENG, TOXC, ZIKA")
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument(
        "--columns",
        default="",
        help=f"Chaves separadas por vírgula, dentre: {', '.join(CATALOG)}",
    )
    args = parser.parse_args()
    selected = [c.strip() for c in args.columns.split(",") if c.strip()]
    try:
        run(args.disease, args.year, selected)
    except Exception:
        logger.exception("Falha na pipeline SINAN disease=%s year=%s", args.disease, args.year)
        raise SystemExit(1) from None
 
if __name__ == "__main__":
    main()
