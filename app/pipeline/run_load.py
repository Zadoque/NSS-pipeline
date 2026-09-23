from __future__ import annotations

import argparse
from datetime import UTC, datetime

import pandas as pd

from .sinan.columns import CANONICAL_GOLD_COLUMNS
from .sinan.gold import aggregate_file
from .load import get_engine, load_gold_to_postgres
from .sinan.silver import transform_file
from .sinan.bronze import fetch_sinan, write_bronze


def run_load(disease: str, year: int) -> None:
    disease = disease.upper()
    run_at = datetime.now(UTC)

    bronze_df = fetch_sinan(disease, year)
    if bronze_df.empty:
        raise RuntimeError("PySUS retornou um DataFrame vazio")

    bronze = write_bronze(bronze_df, disease, year, run_at=run_at)
    silver = transform_file(bronze, disease, year, run_at=run_at)

    gold_path = aggregate_file(
        silver, disease, year, selected_columns=CANONICAL_GOLD_COLUMNS, run_at=run_at
    )

    gold_df = pd.read_parquet(gold_path)
    batch_id = run_at.strftime("%Y%m%dT%H%M%SZ")

    engine = get_engine()
    load_gold_to_postgres(engine, gold_df, disease, batch_id)

    print(f"Bronze: {bronze}")
    print(f"Silver: {silver}")
    print(f"Gold:   {gold_path}")
    print(f"Postgres: carregado (disease={disease}, year={year}, batch_id={batch_id}, rows={len(gold_df)})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Roda a pipeline SINAN completa (grão fixo) e carrega o resultado no Postgres"
    )
    parser.add_argument("--disease", required=True, help="Ex.: DENG, TOXC, ZIKA")
    parser.add_argument("--year", required=True, type=int)
    args = parser.parse_args()
    run_load(args.disease, args.year)


if __name__ == "__main__":
    main()
