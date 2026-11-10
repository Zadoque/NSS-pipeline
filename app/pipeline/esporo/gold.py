"""Prepara o conjunto analítico de esporotricose para consumo e carga."""

from __future__ import annotations

import json
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from ..atomic_io import write_json_atomic, write_parquet_atomic

BASE_DIR = Path("/data")

COLUMN_MAP = {
    "Data da Notificação": "data_notificacao",
    "Espécie do animal": "especie_codigo",
    "Sexo do animal": "sexo_codigo",
    "Idade do Animal": "idade_faixa_codigo",
    "Castrado": "castrado_codigo",
}

AGE_BAND_CODES = {
    "i": 0,
    "nao informado": 0,
    "não informado": 0,
    "< 1 ano": 1,
    "<1 ano": 1,
    "1 - 3 anos": 2,
    "1-3 anos": 2,
    "4 - 6 anos": 3,
    "4-6 anos": 3,
    "7 - 10 anos": 4,
    "7-10 anos": 4,
    "> 10 anos": 5,
    ">10 anos": 5,
}

SEX_CODES = {
    "f": "F",
    "femea": "F",
    "feminino": "F",
    "m": "M",
    "macho": "M",
    "masculino": "M",
    "i": "i",
    "nao informado": "i",
}

CASTRATION_CODES = {
    "nao": 1,
    "nao castrado": 1,
    "n": 1,
    "sim": 2,
    "castrado": 2,
    "s": 2,
    "i": 0,
    "nao informado": 0,
}

SPECIES_CODES = {
    "felino": 1,
    "canino": 2,
    "i": 0,
    "nao informado": 0,
}


def _normalize_sex(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value).strip().casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    if not normalized:
        return "i"
    code = SEX_CODES.get(normalized)
    if code is None:
        raise ValueError(f"Sexo animal não reconhecido: {value!r}")
    return code


def _normalize_castration(value: object) -> int:
    normalized = unicodedata.normalize("NFKD", str(value).strip().casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    if not normalized:
        return 0
    code = CASTRATION_CODES.get(normalized)
    if code is None:
        raise ValueError(f"Status de castração não reconhecido: {value!r}")
    return code


def _normalize_species(value: object) -> int:
    normalized = unicodedata.normalize("NFKD", str(value).strip().casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    if not normalized:
        return 0
    code = SPECIES_CODES.get(normalized)
    if code is None:
        raise ValueError(f"Espécie animal não reconhecida: {value!r}")
    return code


def transform(source: Path) -> pd.DataFrame:
    df = pd.read_parquet(source)
    missing = set(COLUMN_MAP) - set(df.columns)
    if missing:
        raise ValueError(f"Colunas Silver ausentes para Gold: {sorted(missing)}")

    gold = df[list(COLUMN_MAP)].rename(columns=COLUMN_MAP).copy()
    gold["data_notificacao"] = pd.to_datetime(
        gold["data_notificacao"], errors="raise"
    ).dt.date

    gold["especie_codigo"] = pd.array(
        gold["especie_codigo"].map(_normalize_species), dtype="Int16"
    )
    gold["sexo_codigo"] = gold["sexo_codigo"].map(_normalize_sex).astype("string")
    gold["castrado_codigo"] = pd.array(
        gold["castrado_codigo"].map(_normalize_castration), dtype="Int16"
    )

    age_labels = (
        gold["idade_faixa_codigo"]
        .astype("string")
        .str.strip()
        .str.casefold()
        .str.replace(r"\s*[-–]\s*", " - ", regex=True)
        .str.replace(r"<\s*", "< ", regex=True)
        .str.replace(r">\s*", "> ", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .replace("", pd.NA)
        .fillna("i")
    )
    age_codes = age_labels.map(AGE_BAND_CODES)
    unknown_labels = sorted(age_labels[age_codes.isna()].unique().tolist())
    if unknown_labels:
        raise ValueError(f"Faixas etárias não reconhecidas na Silver: {unknown_labels}")
    gold["idade_faixa_codigo"] = pd.array(age_codes, dtype="Int16")

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
        "idade_nao_informada_rows": int(df["idade_faixa_codigo"].eq(0).sum()),
        "especie_nao_informada_rows": int(df["especie_codigo"].eq(0).sum()),
        "sexo_nao_informado_rows": int(df["sexo_codigo"].eq("i").sum()),
        "castracao_nao_informada_rows": int(df["castrado_codigo"].eq(0).sum()),
        "columns": df.columns.tolist(),
    }
    write_json_atomic(metadata, directory / "metadata.json")
    return parquet
