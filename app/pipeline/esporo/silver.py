from pathlib import Path

import pandas as pd
from datetime import UTC, datetime

BASE_DIR = Path("/data")

#Inserir colunas desejadas aqui
SELECTED_COLUMNS = []

def transform(df: pd.DataFrame) -> pd.DataFrame:
    pass

def transform_file(
    source: Path, disease: str, year: int, run_at: datetime | None = None
) -> None:
    if source is None:
        raise ValueError("Source path is required.")

    source = Path(source)
    now = run_at or datetime.now(UTC)
    batch_id = now.strftime("%Y%m%dT%H%M%SZ")
    directory = (
        BASE_DIR / "silver" / "esporo" / f"source_year={year}" 
        / f"ingestion_date={now.date()}" / f"batch_id={batch_id}"
    )
    parquet = directory / "data.parquet"

    transform(source)
        