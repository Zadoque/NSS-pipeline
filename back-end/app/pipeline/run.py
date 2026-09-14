from __future__ import annotations
 
import argparse
from datetime import UTC, datetime
from pathlib import Path
 
from .columns import CATALOG
from .gold import aggregate_file
from .sinan import fetch_sinan, write_bronze 
from .silver import transform_file
 
BASE_DIR = Path("/data")
 
 
def run(disease: str, year: int, selected_columns: list[str] | None = None) -> None:
    disease = disease.upper()
    bronze_df = fetch_sinan(disease, year)
    if bronze_df.empty:
        raise RuntimeError("PySUS retornou um DataFrame vazio")

    bronze = write_bronze(bronze_df, disease, year)
    silver = transform_file(bronze, disease, year)
    gold = aggregate_file(silver, disease, year, selected_columns)

    print(f"Bronze: {bronze}")
    print(f"Silver: {silver}")
    print(f"Gold: {gold}")
 
def main() -> None:
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
    run(args.disease, args.year, selected)
 
 
if __name__ == "__main__":
    main()
 