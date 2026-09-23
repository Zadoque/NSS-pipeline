from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd

from ..atomic_io import write_json_atomic, write_parquet_atomic
from .columns import CATALOG, present_keys, required_keys, resolve_dedup_strategy
from datetime import UTC, datetime

BASE_DIR = Path("/data")

UF_CODES = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP",
    "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB",
    "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
    "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
    "51": "MT", "52": "GO", "53": "DF",
}
UF_NAMES = {
    "RO": "Rondônia", "AC": "Acre", "AM": "Amazonas", "RR": "Roraima", "PA": "Pará",
    "AP": "Amapá", "TO": "Tocantins", "MA": "Maranhão", "PI": "Piauí", "CE": "Ceará",
    "RN": "Rio Grande do Norte", "PB": "Paraíba", "PE": "Pernambuco", "AL": "Alagoas",
    "SE": "Sergipe", "BA": "Bahia", "MG": "Minas Gerais", "ES": "Espírito Santo",
    "RJ": "Rio de Janeiro", "SP": "São Paulo", "PR": "Paraná", "SC": "Santa Catarina",
    "RS": "Rio Grande do Sul", "MS": "Mato Grosso do Sul", "MT": "Mato Grosso",
    "GO": "Goiás", "DF": "Distrito Federal",
}


def transform(df: pd.DataFrame, year: int) -> pd.DataFrame:
    available = set(df.columns)

    missing_required = [
        CATALOG[key].source_column for key in required_keys()
        if CATALOG[key].source_column not in available
    ]
    if missing_required:
        raise ValueError(
            "Colunas obrigatórias do SINAN ausentes neste dataset: "
            f"{missing_required}. Colunas realmente disponíveis: {sorted(available)}"
        )

    keys = present_keys(available)
    source_columns = [CATALOG[key].source_column for key in keys]

    out = df[source_columns].copy()

    for key in keys:
        spec = CATALOG[key]
        if spec.transform is not None:
            out[spec.source_column] = spec.transform(out[spec.source_column])

    out = out.dropna(subset=["DT_NOTIFIC"])
    out = out[out["DT_NOTIFIC"].dt.year == year]

    out["UF"] = out["SG_UF_NOT"].map(UF_CODES)
    out["NM_UF"] = out["UF"].map(UF_NAMES)

    dedup_cols, used_primary_key = resolve_dedup_strategy(available)
    if not used_primary_key:
        warnings.warn(
            "Chave de negócio (NU_NOTIFIC) ausente neste dataset SINAN; "
            f"deduplicando por correspondência exata em {dedup_cols}. "
            "Isso é mais fraco que uma chave real: notificações distintas "
            "porém idênticas em todos os campos capturados serão tratadas "
            "como duplicata.",
            stacklevel=2,
        )
    out = out.drop_duplicates(subset=dedup_cols, keep="last")
    return out

def transform_file(source: Path, disease: str, year: int, run_at: datetime | None = None) -> Path:
    df = pd.read_parquet(source)
    len_before = len(df)

    result = transform(df, year)
    len_after = len(result)

    now = run_at or datetime.now(UTC)
    batch_id = now.strftime("%Y%m%dT%H%M%SZ")
    directory = (
        BASE_DIR / "silver" / "sinan" / f"disease={disease.lower()}"
        / f"source_year={year}" / f"ingestion_date={now.date()}" / f"batch_id={batch_id}"
    )
    parquet = directory / "data.parquet"
    write_parquet_atomic(result, parquet)

    metadata = {
        "disease": disease.upper(),
        "source_year": year,
        "batch_id": batch_id,
        "ingested_at": now.isoformat(),
        "rows": len_after,
        "dropped_rows": len_before - len_after,
        "columns": list(result.columns),
    }
    write_json_atomic(metadata, directory / "metadata.json")
    return parquet

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Transforma SINAN da camada Bronze para Silver")
    parser.add_argument("--source", required=True, type=Path, help="Arquivo Parquet de entrada (Bronze)")
    parser.add_argument("--destination", required=True, type=Path, help="Arquivo Parquet de saída (Silver)")
    parser.add_argument("--year", required=True, type=int, help="Ano de referência para filtrar DT_NOTIFIC")
    args = parser.parse_args()
    transform_file(source=args.source, destination=args.destination, year=args.year)