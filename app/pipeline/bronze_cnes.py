from __future__ import annotations

import argparse

import requests
import pandas as pd
from pathlib import Path
from datetime import UTC, datetime

from .atomic_io import write_json_atomic, write_parquet_atomic

API_BASE = "https://apidadosabertos.saude.gov.br/cnes/estabelecimentos"
BASE_DIR = Path("/data")

def fetch_estabelecimentos(codigo_municipio_7: str, limit: int = 100) -> pd.DataFrame:
    codigo_municipio_6 = codigo_municipio_7[:6]
    registros = []
    offset = 0

    while True:
        resp = requests.get(
            API_BASE,
            params={"codigo_municipio": codigo_municipio_6, "limit": limit, "offset": offset},
            timeout=60,
        )
        resp.raise_for_status()
        pagina = resp.json().get("estabelecimentos", [])
        if not pagina:
            break
        registros.extend(pagina)
        offset += limit

    return pd.DataFrame(registros)

def write_bronze_cnes(df: pd.Dataframe, code: str, run_at: datetime | None = None) -> Path:
    now = run_at or datetime.now(UTC)
    batch_id = now.strftime("%Y%m%dT%H%M%SZ")
    directory = (
        BASE_DIR / "bronze" / "cnes" / f"code={code.lower()}"
        / f"ingestion_date={now.date()}" / f"batch_id={batch_id}"
    )
    parquet = directory / "data.parquet"
    write_parquet_atomic(df, parquet)

    metadata = {
        "code": code.upper(),
        "batch_id": batch_id,
        "ingested_at": now.isoformat(),
        "rows": len(df),
        "columns": list(df.columns),
        "source": "apiDadosAbertos",
    }
    write_json_atomic(metadata, directory / "metadata.json")
    return parquet
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Baixa dados do CNES via api de Dados Abertos")
    parser.add_argument("--code", required=True, help="Código CNES do município")
    args = parser.parse_args()

    #Ajustar o limite, quanto menor mais dados
    df = fetch_estabelecimentos(args.code, 10)
    if df.empty:
        raise RuntimeError("PySUS retornou um DataFrame vazio")
    print(write_bronze_cnes(df, args.code))