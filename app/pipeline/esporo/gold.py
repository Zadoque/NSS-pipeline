"""Prepara o conjunto analítico de esporotricose para consumo e carga."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from ..atomic_io import write_json_atomic, write_parquet_atomic

BASE_DIR = Path("/data")

COLUMN_MAP = {
    "Data da Notificação": "data_notificacao",
    "Espécie do animal": "especie",
    "Sexo do animal": "sexo_animal",
    "Idade do Animal": "idade_animal",
    "Castrado": "castrado",
}


def transform(source: Path) -> pd.DataFrame:
    """Retorna uma linha por notificação com colunas no contrato PostgreSQL."""
    df = pd.read_parquet(source)
    missing = set(COLUMN_MAP) - set(df.columns)
    if missing:
        raise ValueError(f"Colunas Silver ausentes para Gold: {sorted(missing)}")

    gold = df[list(COLUMN_MAP)].rename(columns=COLUMN_MAP).copy()
    gold["data_notificacao"] = pd.to_datetime(
        gold["data_notificacao"], errors="raise"
    ).dt.date

    for column in ("especie", "sexo_animal", "idade_animal", "castrado"):
        values = gold[column].astype("string").str.strip().replace("", pd.NA)
        gold[column] = values.fillna("nao informado")

    return gold


def transform_file(
    source: Path, run_at: datetime | None = None
) -> Path:
    if source is None:
        raise ValueError("Source path is required.")

    source = Path(source)
    metadata_path = source.with_name("metadata.json")
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Metadados Silver não encontrados: {metadata_path}")
    silver_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    for field in ("source_year", "batch_id"):
        if field not in silver_metadata:
            raise ValueError(f"Campo {field!r} ausente nos metadados Silver")

    now = run_at or datetime.now(UTC)
    source_year = int(silver_metadata["source_year"])
    batch_id = str(silver_metadata["batch_id"])
    directory = (
        BASE_DIR / "gold" / "serving" / "esporo"
        / f"source_year={source_year}"
        / f"ingestion_date={now.date()}"
        / f"batch_id={batch_id}"
    )
    parquet = directory / "data.parquet"

    df = transform(source)
    write_parquet_atomic(df, parquet)

    metadata = {
        "disease": "ESPORO",
        "gold_target": "serving",
        "source_year": source_year,
        "batch_id": batch_id,
        "created_at": now.isoformat(),
        "source_layer": "silver",
        "source_silver_path": str(source),
        "rows": len(df.index),
        "columns": df.columns.tolist(),
    }
    write_json_atomic(metadata, directory / "metadata.json")
    return parquet
