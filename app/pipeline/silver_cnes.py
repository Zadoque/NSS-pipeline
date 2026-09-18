from __future__ import annotations

from pathlib import Path
import pandas as pd
from datetime import UTC, datetime
import argparse

from .bronze_cnes import fetch_estabelecimentos, write_bronze_cnes
from .atomic_io import write_parquet_atomic, write_json_atomic

BASE_DIR = BASE_DIR = Path("/data")

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

def write_silver_cnes(df: pd.Dataframe, code: str, run_at: datetime | None = None) -> Path:
    now = run_at or datetime.now(UTC)
    batch_id = now.strftime("%Y%m%dT%H%M%SZ")
    directory = (
        BASE_DIR / "silver" / "cnes" / f"code={code.lower()}"
        / f"ingestion_date={now.date()}" / f"batch_id={batch_id}"
    )
    parquet = directory / "data.parquet"
    write_parquet_atomic(df, parquet)

    metadata = {
        "code": code.upper(),
        "batch_id": batch_id,
        "ingested_at": now.isoformat(),
        "rows": len(df),
        "columns": list(df.columns),
        "source": "apiDadosAbertos",
    }
    write_json_atomic(metadata, directory / "metadata.json")
    return parquet


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transforma dados da camada bronze para silver")
    parser.add_argument("--code", required=True, help="Código CNES do município")
    args = parser.parse_args()

    run_at = datetime.now(UTC)          

    bronze_df = fetch_estabelecimentos(args.code, 10)
    if bronze_df.empty:
        raise RuntimeError("PySUS retornou um DataFrame vazio")

    bronze = write_bronze_cnes(bronze_df, args.code, run_at=run_at)
    
    silver = transform_cnes(bronze_df)
    parquet = write_silver_cnes(silver, args.code, run_at=run_at)

    print(write_bronze_cnes(silver, args.code))