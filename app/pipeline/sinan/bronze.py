from __future__ import annotations
 
import argparse
import os
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
 
import pyarrow.parquet as pq
 
from ..atomic_io import write_json_atomic
from .source import download_remote_file, inspect_remote_file
 
BASE_DIR = Path("/data")
 
 
def fetch_sinan(disease: str, year: int) -> Path:
    try:
        remote = inspect_remote_file(disease, year)
        return download_remote_file(remote)
    except Exception as e:
        raise RuntimeError(f"Erro ao baixar SINAN via PySUS (disease={disease}, year={year})") from e
 
 
def write_bronze(source: Path, disease: str, year: int, run_at: datetime | None = None) -> Path:
    source = Path(source)
    with pq.ParquetFile(source) as original:
        rows = original.metadata.num_rows
        columns = original.schema_arrow.names
    if rows == 0:
        raise RuntimeError("SINAN retornou um Parquet vazio")

    now = run_at or datetime.now(UTC)
    batch_id = now.strftime("%Y%m%dT%H%M%SZ")
    directory = (
        BASE_DIR / "bronze" / "sinan" / f"disease={disease.lower()}"
        / f"source_year={year}" / f"ingestion_date={now.date()}" / f"batch_id={batch_id}"
    )
    parquet = directory / "data.parquet"
    directory.mkdir(parents=True, exist_ok=True)
    temporary = parquet.with_name(f".{parquet.name}.{uuid.uuid4().hex}.tmp")
    try:
        shutil.copyfile(source, temporary)
        os.replace(temporary, parquet)
    finally:
        temporary.unlink(missing_ok=True)

    metadata = {
        "disease": disease.upper(),
        "source_year": year,
        "batch_id": batch_id,
        "ingested_at": now.isoformat(),
        "rows": rows,
        "columns": columns,
        "source": "PySUS SINAN",
    }
    write_json_atomic(metadata, directory / "metadata.json")
    return parquet
 
def main() -> None:
    parser = argparse.ArgumentParser(description="Baixa SINAN via PySUS para a camada Bronze")
    parser.add_argument("--disease", required=True, help="Código SINAN aceito pelo PySUS, por exemplo DENG")
    parser.add_argument("--year", required=True, type=int)
    args = parser.parse_args()
 
    source = fetch_sinan(args.disease, args.year)
    print(write_bronze(source, args.disease, args.year))
 
 
if __name__ == "__main__":
    main()
