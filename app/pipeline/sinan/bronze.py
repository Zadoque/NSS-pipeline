from __future__ import annotations
 
import argparse
from datetime import UTC, datetime
from pathlib import Path
 
import pandas as pd
import pysus
 
from ..atomic_io import write_json_atomic, write_parquet_atomic
 
BASE_DIR = Path("/data")
 
 
def fetch_sinan(disease: str, year: int) -> pd.DataFrame:
    try:
        result = pysus.ftp.sinan(
            disease=disease.upper(),
            year=year,
            as_dataframe=True,
            show_progress=True,
        )
        if not isinstance(result, pd.DataFrame):
            raise TypeError(f"PySUS retornou tipo inesperado: {type(result)!r}")
        return result
    except Exception as e:
        raise RuntimeError(f"Erro ao baixar SINAN via PySUS (disease={disease}, year={year})") from e
 
 
def write_bronze(df: pd.DataFrame, disease: str, year: int, run_at: datetime | None = None) -> Path:
    now = run_at or datetime.now(UTC)
    batch_id = now.strftime("%Y%m%dT%H%M%SZ")
    directory = (
        BASE_DIR / "bronze" / "sinan" / f"disease={disease.lower()}"
        / f"source_year={year}" / f"ingestion_date={now.date()}" / f"batch_id={batch_id}"
    )
    parquet = directory / "data.parquet"
    write_parquet_atomic(df, parquet)

    metadata = {
        "disease": disease.upper(),
        "source_year": year,
        "batch_id": batch_id,
        "ingested_at": now.isoformat(),
        "rows": len(df),
        "columns": list(df.columns),
        "source": "PySUS SINAN",
    }
    write_json_atomic(metadata, directory / "metadata.json")
    return parquet
 
def main() -> None:
    parser = argparse.ArgumentParser(description="Baixa SINAN via PySUS para a camada Bronze")
    parser.add_argument("--disease", required=True, help="Código SINAN aceito pelo PySUS, por exemplo DENG")
    parser.add_argument("--year", required=True, type=int)
    args = parser.parse_args()
 
    df = fetch_sinan(args.disease, args.year)
    if df.empty:
        raise RuntimeError("PySUS retornou um DataFrame vazio")
    print(write_bronze(df, args.disease, args.year))
 
 
if __name__ == "__main__":
    main()
 