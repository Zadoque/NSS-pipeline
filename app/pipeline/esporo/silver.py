from pathlib import Path

import pandas as pd
from datetime import UTC, datetime

from ..atomic_io import write_json_atomic, write_parquet_atomic

BASE_DIR = Path("/data")

#Inserir colunas desejadas aqui
SELECTED_COLUMNS = ["ID da resposta", "Data da Notificação", "Municípío de Notificação",]

def transform(source: Path) -> pd.DataFrame:
    df = pd.read_parquet(source)
    df = df[SELECTED_COLUMNS]

    return df                  

def transform_file(
    source: Path, run_at: datetime | None = None
) -> Path:
    if source is None:
        raise ValueError("Source path is required.")

    source = Path(source)
    now = run_at or datetime.now(UTC)
    batch_id = now.strftime("%Y%m%dT%H%M%SZ")
    directory = (
        BASE_DIR / "silver" / "esporo" / f"source_year={2026}" 
        / f"ingestion_date={now.date()}" / f"batch_id={batch_id}"
    )
    parquet = directory / "data.parquet"

    df = transform(source)
    write_parquet_atomic(df, parquet)

    metadata = {
        "disease": "ESPORO",
        "source_year": 2026,
        "batch_id": batch_id,
        "ingested_at": now.isoformat(),
        "rows": len(df.index),
        "columns": df.columns.tolist()
    }

    write_json_atomic(metadata, directory / "metadata.json")
    return parquet
        