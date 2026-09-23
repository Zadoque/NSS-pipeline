from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .atomic_io import write_json_atomic, write_parquet_atomic

BASE_DIR = Path("/data")


def transform_cnes(df: pd.DataFrame) -> pd.DataFrame:
    out = df[["codigo_cnes", "nome_fantasia", "nome_razao_social",
              "codigo_municipio", "codigo_tipo_unidade"]].copy()

    out["codigo_cnes"] = out["codigo_cnes"].astype("string").str.zfill(7)
    out["codigo_municipio"] = out["codigo_municipio"].astype("string")

    out = out.drop_duplicates(subset=["codigo_cnes"], keep="last")
    return out.rename(columns={
        "codigo_cnes": "cd_unidade",
        "nome_fantasia": "nm_unidade",
        "nome_razao_social": "razao_social_unidade",
        "codigo_tipo_unidade": "tp_unidade",
    })


def transform_cnes_file(source: Path, municipio: str, run_at: datetime | None = None) -> Path:
    df = pd.read_parquet(source)
    len_before = len(df)

    result = transform_cnes(df)
    len_after = len(result)

    now = run_at or datetime.now(UTC)
    batch_id = now.strftime("%Y%m%dT%H%M%SZ")
    directory = (
        BASE_DIR / "silver" / "cnes" / f"municipio={municipio}"
        / f"ingestion_date={now.date()}" / f"batch_id={batch_id}"
    )
    parquet = directory / "data.parquet"
    write_parquet_atomic(result, parquet)

    metadata = {
        "municipio": municipio,
        "batch_id": batch_id,
        "ingested_at": now.isoformat(),
        "rows": len_after,
        "dropped_rows": len_before - len_after,
        "columns": list(result.columns),
    }
    write_json_atomic(metadata, directory / "metadata.json")
    return parquet


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transforma CNES Bronze -> Silver")
    parser.add_argument("--source", required=True, type=Path, help="Parquet de entrada (Bronze)")
    parser.add_argument("--municipio", required=True)
    args = parser.parse_args()
    print(transform_cnes_file(args.source, args.municipio))