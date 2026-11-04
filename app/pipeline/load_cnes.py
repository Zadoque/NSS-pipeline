"""Publica o último snapshot Silver CNES no PostgreSQL."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd

from .load import get_engine, load_cnes_to_postgres
from .reference.ibge.storage import load_active_catalog

BASE_DIR = Path(os.environ.get("PIPELINE_DATA_DIR", "/data"))


def latest_cnes_snapshot() -> Path:
    snapshots = sorted((BASE_DIR / "silver" / "cnes").glob("batch_id=*/data.parquet"))
    if not snapshots:
        raise FileNotFoundError("nenhum snapshot Silver CNES encontrado")
    return snapshots[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Publica Silver CNES no PostgreSQL")
    parser.add_argument("--source", type=Path, help="Parquet Silver CNES; padrão: último batch")
    parser.add_argument("--catalog-root", type=Path, required=True)
    args = parser.parse_args()
    source = args.source or latest_cnes_snapshot()
    catalog = load_active_catalog(args.catalog_root)
    load_cnes_to_postgres(get_engine(), pd.read_parquet(source), catalog=catalog)
    print(source)


if __name__ == "__main__":
    main()
