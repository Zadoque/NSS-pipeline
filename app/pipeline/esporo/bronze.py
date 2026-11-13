from app.pipeline.atomic_io import write_parquet_atomic
from app.pipeline.atomic_io import write_json_atomic
from datetime import UTC, datetime
from pathlib import Path
import pandas as pd

BASE_DIR = Path("/data")

def write_bronze_esporo(df, year):
    now = datetime.now(UTC)
    batch_id = now.strftime("%Y%m%dT%H%M%SZ")
    directory = (
        BASE_DIR / "bronze" / "esporo" / f"source_year={year}" 
        / f"ingestion_date={now.date()}" / f"batch_id={batch_id}"
    )
    parquet = directory / "data.parquet"
    write_parquet_atomic(df, parquet)

    metadata = {
        "source_year": year,
        "batch_id": batch_id,
        "ingested_at": now.isoformat(),
        "rows": len(df),
        "columns": list(df.columns),
        "source": "PySUS SINAN",
    }
    write_json_atomic(metadata, directory / "metadata.json")
    return parquet

def injestion_esporo(path) -> Path:
    try:
        df = pd.read_csv(path)
        parquet = write_bronze_esporo(df, 2026)
        return parquet
    except Exception as e:
        raise e

def main() -> None:
    path = injestion_esporo(BASE_DIR / "esporotricose" / "banco_sivs_esporo_animal_campos_23_09_26 - Folha1.csv")
    if not path.exists():
        raise RuntimeError("Path not found: %s", path)
    print(path)
 
if __name__ == "__main__":
    main()
    