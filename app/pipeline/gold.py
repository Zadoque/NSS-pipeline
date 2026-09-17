from __future__ import annotations

import json
from pathlib import Path
 
import pandas as pd
 
from .atomic_io import write_json_atomic, write_parquet_atomic
from .columns import CATALOG, validate_keys
from datetime import UTC, datetime
 
MUNICIPIOS_RJ = {
    "3301009": "Campos dos Goytacazes",
    "3305000": "São João da Barra",
    "3302205": "Itaperuna",
    "3302403": "Macaé",
}

BASE_DIR = Path("/data")
 
def aggregate(
    df: pd.DataFrame,
    disease: str,
    selected_columns: list[str] | None = None,
    municipios: dict[str, str] | None = None,
) -> pd.DataFrame:
    selected_columns = validate_keys(selected_columns)
    municipios = municipios if municipios is not None else MUNICIPIOS_RJ
    disease = disease.upper()

    required = {"DT_NOTIFIC", "ID_MUNICIP", "SG_UF_NOT", "NM_UF"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Colunas Silver ausentes para Gold: {sorted(missing)}")

    extra_group_cols = [
        CATALOG[key].source_column
        for key in selected_columns
        if CATALOG[key].groupable and CATALOG[key].source_column in df.columns
    ]

    work = df.copy()
    work["cd_mun"] = work["ID_MUNICIP"].astype("string").str.zfill(7)
    work = work[work["cd_mun"].isin(municipios)]

    base_cols = ["disease", "year", "month", "cd_uf", "nm_uf", "cd_mun", "nm_mun"]
    if work.empty:
        return pd.DataFrame(columns=base_cols + extra_group_cols + ["cases_total"])

    work["year"] = work["DT_NOTIFIC"].dt.year.astype("int64")
    work["month"] = work["DT_NOTIFIC"].dt.month.astype("int64")
    work["cd_uf"] = work["SG_UF_NOT"].astype("string").str.zfill(2)
    work["nm_mun"] = work["cd_mun"].map(municipios)

    group_cols = ["year", "month", "cd_uf", "NM_UF", "cd_mun", "nm_mun", *extra_group_cols]

    result = (
        work.groupby(group_cols, dropna=False)
        .size()
        .reset_index(name="cases_total")
        .rename(columns={"NM_UF": "nm_uf"})
    )

    result.insert(0, "disease", disease)   # <- coluna nova, primeira posição

    sort_cols = ["disease", "year", "month", "cd_uf", "cd_mun", *extra_group_cols]
    return result.sort_values(sort_cols).reset_index(drop=True) 

def _read_source_metadata(source: Path) -> dict:
    metadata_path = source.with_name("metadata.json")
    if not metadata_path.exists():
        raise FileNotFoundError(
            f"metadata.json não encontrado ao lado de {source}; "
            "não é possível validar a origem antes de agregar para Gold."
        )
    return json.loads(metadata_path.read_text(encoding="utf-8"))

def _validate_source_matches(source_metadata: dict, disease: str, year: int, source: Path) -> None:
    source_disease = source_metadata.get("disease")
    source_year = source_metadata.get("source_year")

    if source_disease != disease:
        raise ValueError(
            f"Inconsistência detectada ao gerar Gold: solicitado disease={disease!r}, "
            f"mas a Silver de origem ({source}) foi gerada para disease={source_disease!r}. "
            "Abortando para evitar misturar doenças na mesma agregação."
        )
    if source_year != year:
        raise ValueError(
            f"Inconsistência detectada ao gerar Gold: solicitado year={year!r}, "
            f"mas a Silver de origem ({source}) foi gerada para source_year={source_year!r}. "
            "Abortando para evitar misturar anos na mesma agregação."
        )

def aggregate_file(
    source: Path,
    disease: str,
    year: int,
    selected_columns: list[str] | None = None,
    municipios: dict[str, str] | None = None,
    run_at: datetime | None = None,
) -> Path:
    disease = disease.upper()

    source_metadata = _read_source_metadata(source)
    _validate_source_matches(source_metadata, disease, year, source)

    df = pd.read_parquet(source)
    len_before = len(df)

    result = aggregate(df, disease, selected_columns, municipios)
    len_after = len(result)

    now = run_at or datetime.now(UTC)
    batch_id = now.strftime("%Y%m%dT%H%M%SZ")
    directory = (
        BASE_DIR / "gold" / "sinan" / f"disease={disease.lower()}"
        / f"source_year={year}" / f"ingestion_date={now.date()}" / f"batch_id={batch_id}"
    )
    parquet = directory / "data.parquet"
    write_parquet_atomic(result, parquet)

    metadata = {
        "disease": disease,
        "source_year": year,
        "batch_id": batch_id,
        "ingested_at": now.isoformat(),
        "rows": len_after,
        "dropped_rows": len_before - len_after,
        "columns": list(result.columns),
    }
    write_json_atomic(metadata, directory / "metadata.json")
    return parquet