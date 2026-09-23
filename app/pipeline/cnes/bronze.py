from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .atomic_io import write_json_atomic, write_parquet_atomic

API_BASE = "https://apidadosabertos.saude.gov.br/cnes/estabelecimentos"
BASE_DIR = Path("/data")


def _session_with_retries() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        connect=5,
        allowed_methods=["GET"],
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


def fetch_estabelecimentos(codigo_municipio_7: str, limit: int = 10) -> pd.DataFrame:
    codigo_municipio_6 = codigo_municipio_7[:6]
    session = _session_with_retries()
    registros = []
    offset = 0

    while True:
        resp = session.get(
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


def write_bronze_cnes(df: pd.DataFrame, municipio: str, run_at: datetime | None = None) -> Path:
    now = run_at or datetime.now(UTC)
    batch_id = now.strftime("%Y%m%dT%H%M%SZ")
    directory = (
        BASE_DIR / "bronze" / "cnes" / f"municipio={municipio}"
        / f"ingestion_date={now.date()}" / f"batch_id={batch_id}"
    )
    parquet = directory / "data.parquet"
    write_parquet_atomic(df, parquet)

    metadata = {
        "municipio": municipio,
        "batch_id": batch_id,
        "ingested_at": now.isoformat(),
        "rows": len(df),
        "columns": list(df.columns),
        "source": "apiDadosAbertos",
    }
    write_json_atomic(metadata, directory / "metadata.json")
    return parquet


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Baixa estabelecimentos do CNES via API de Dados Abertos")
    parser.add_argument("--municipio", required=True, help="Código IBGE do município (7 dígitos)")
    args = parser.parse_args()

    df = fetch_estabelecimentos(args.municipio)
    if df.empty:
        raise RuntimeError("API CNES retornou um DataFrame vazio")
    print(write_bronze_cnes(df, args.municipio))