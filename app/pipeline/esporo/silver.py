from pathlib import Path
import re

import pandas as pd
from datetime import UTC, datetime

from ..atomic_io import write_json_atomic, write_parquet_atomic

BASE_DIR = Path("/data")

SELECTED_COLUMNS = [
    "Data da Notificação",
    "Espécie do animal",
    "Sexo do animal",
    "Idade do Animal",
    "Castrado",
    "Nome do animal:",
]

_CODIGO_SES = re.compile(
    r"(?<!\w)SES[\s/-]*(?:CCZ[\s/-]*)?(?P<numero>\d+)"
    r"(?:[\s/-]+(?P<ano>\d{4}|\d{2}))?\s*\)?\s*$",
    re.IGNORECASE,
)
_SOMENTE_CODIGO = re.compile(
    r"(?P<numero>\d+)(?:[\s/-]+(?P<ano>\d{4}|\d{2}))?"
)

def _separar_nome(valor: object) -> tuple:
    if pd.isna(valor):
        return pd.NA, pd.NA, pd.NA

    texto = re.sub(r"\s+", " ", str(valor)).strip()
    if not texto:
        return pd.NA, pd.NA, pd.NA

    codigo = _CODIGO_SES.search(texto) or _SOMENTE_CODIGO.fullmatch(texto)
    if codigo is None:
        return texto, pd.NA, pd.NA

    nome = texto[:codigo.start()].rstrip(" (-/") or pd.NA
    numero = int(codigo["numero"])
    ano = codigo["ano"]
    if ano is not None:
        ano = int(ano) + (2000 if len(ano) == 2 else 0)
    return nome, numero if numero > 0 else pd.NA, ano if ano is not None else pd.NA

def tratamento_nome(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["nome_animal_original"] = df["Nome do animal:"]
    partes = df["nome_animal_original"].map(_separar_nome)
    for indice, coluna, tipo in (
        (0, "nome_animal", "string"),
        (1, "numero_notificacao", "Int64"),
        (2, "ano_notificacao_nome", "Int64"),
    ):
        df[coluna] = pd.array([parte[indice] for parte in partes], dtype=tipo)
    return df

def transform(source: Path) -> pd.DataFrame:
    df = pd.read_parquet(source)
    df = df[SELECTED_COLUMNS]
    df = tratamento_nome(df)
    
    data_original = df["Data da Notificação"]
    data_parseada = pd.to_datetime(data_original, errors="coerce")
    preenchida = data_original.notna() & data_original.astype("string").str.strip().ne("")
    invalida = preenchida & data_parseada.isna()
    if invalida.any():
        raise ValueError(
            f"{int(invalida.sum())} valor(es) inválido(s) em 'Data da Notificação'"
        )
    df["Data da Notificação"] = data_parseada.dt.date

    df = df.drop(columns=["Nome do animal:", "nome_animal_original", "nome_animal"])

    colunas_categoricas = [
        "Espécie do animal",
        "Sexo do animal",
        "Idade do Animal",
        "Castrado",
    ]
    for coluna in colunas_categoricas:
        valores = df[coluna].astype("string").str.strip().replace("", pd.NA)
        df[coluna] = valores.fillna("nao informado")

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
