from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..atomic_io import write_json_atomic, write_parquet_atomic

API_BASE = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
BASE_DIR = Path("/data")

def _session_with_retries() -> requests.session:
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        connect=5,
        allowed_methods=["GET"],
    )
    session.mount("http://", HTTPAdapter(max_retries=retries))
    return session

def fetch_municipios() -> pd.DataFrame:
    session = _session_with_retries()

    resp = session.get(API_BASE, timeout=60)
    resp.raise_for_status()
    municipios = resp.json()

    if not municipios:
        return pd.DataFrame()

    dados_processados = []
    for mun in municipios:
        micro = mun.get("microrregião") or {}
        meso = micro.get("mesorregião") or {}
        uf = meso.get("UF") or {}
        regiao = uf.get("regiao") or {}

        dados_processados.append({
            "id_municipio": mun.get("id"),
            "nome_municipio": mun.get("nome"),
            "microrregiao": micro.get("nome"),
            "mesorregiao": meso.get("nome"),
            "sigla_uf": 
        })



if __name__ == "__main__":
    df = fetch_municipios()
    if df.empty:
        raise RuntimeError("API CNES retornou um DataFrame vazio")
    print(write_bronze_cnes(df))