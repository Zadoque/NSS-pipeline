from __future__ import annotations

import argparse
import json
import os
import re
from zipfile import ZipFile
from threading import Lock
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..atomic_io import write_json_atomic, write_parquet_atomic
from ..reference.ibge.models import MunicipalityCatalog, ResolutionStatus

API_BASE = "https://apidadosabertos.saude.gov.br/cnes/estabelecimentos"
BASE_DIR = Path(os.environ.get("PIPELINE_DATA_DIR", "/data"))
_NATIONAL_CNES_LOCK = Lock()
_NATIONAL_CNES: pd.DataFrame | None = None


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


def session_with_retries() -> requests.Session:
    """Cria uma sessão CNES reutilizável por uma execução do pipeline."""
    return _session_with_retries()


def _normalize_code(value: object, width: int) -> str:
    """Normaliza códigos CNES/IBGE sem perder zeros à esquerda."""
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(width) if text.isdigit() else text


def _load_national_cnes() -> pd.DataFrame:
    """Baixa uma única cópia do cadastro nacional através do PySUS.

    O cache é compartilhado pelos workers da execução. Isso evita 5.571
    downloads e usa a mesma fotografia oficial para todos os municípios.
    """
    global _NATIONAL_CNES
    if _NATIONAL_CNES is not None:
        return _NATIONAL_CNES
    with _NATIONAL_CNES_LOCK:
        if _NATIONAL_CNES is not None:
            return _NATIONAL_CNES
        try:
            import pysus
        except ImportError as error:
            raise RuntimeError("PySUS é obrigatório para a carga CNES") from error
        pysus.set_cache(BASE_DIR / "pysus")
        source = pysus.saude.cnes(download=False)
        if isinstance(source, pd.DataFrame):
            frame = source
        else:
            try:
                downloaded = source.download()
                archive = Path(downloaded.paths[0])
                with ZipFile(archive) as bundle:
                    csv_name = next(
                        name for name in bundle.namelist()
                        if name.lower().endswith(".csv")
                    )
                    with bundle.open(csv_name) as csv_file:
                        frame = pd.read_csv(
                            csv_file, sep=";", encoding="latin1", low_memory=False
                        )
            except (AttributeError, IndexError, StopIteration, OSError, ValueError, UnicodeError) as error:
                raise RuntimeError(
                    "não foi possível baixar ou ler o ZIP CNES pelo PySUS"
                ) from error
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            raise RuntimeError("PySUS CNES retornou um cadastro nacional vazio")
        required = {"CO_CNES", "CO_IBGE"}
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"cadastro CNES PySUS sem colunas obrigatórias: {missing}")
        rename = {
            "CO_CNES": "codigo_cnes",
            "CO_IBGE": "codigo_municipio",
            "NO_RAZAO_SOCIAL": "nome_razao_social",
            "NO_FANTASIA": "nome_fantasia",
            "TP_UNIDADE": "codigo_tipo_unidade",
            "NO_BAIRRO": "bairro_estabelecimento",
            "NU_LATITUDE": "latitude_estabelecimento_decimo_grau",
            "NU_LONGITUDE": "longitude_estabelecimento_decimo_grau",
        }
        frame = frame.rename(columns=rename)
        frame["codigo_cnes"] = frame["codigo_cnes"].map(lambda value: _normalize_code(value, 7))
        frame["codigo_municipio"] = frame["codigo_municipio"].map(
            lambda value: _normalize_code(value, 6)
        )
        _NATIONAL_CNES = frame
        return frame


def _extract_page(payload: object) -> list[dict]:
    if not isinstance(payload, dict):
        raise ValueError("resposta CNES inválida: o JSON deve ser um objeto")
    records = payload.get("estabelecimentos")
    if not isinstance(records, list):
        raise ValueError("resposta CNES inválida: estabelecimentos deve ser uma lista")
    if not all(isinstance(record, dict) for record in records):
        raise ValueError("resposta CNES inválida: cada estabelecimento deve ser um objeto")
    return records


def fetch_estabelecimentos(
    codigo_municipio_7: str,
    limit: int = 10,
    *,
    catalog: MunicipalityCatalog | None = None,
    session: requests.Session | None = None,
    timeout: float = 60,
) -> pd.DataFrame:
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        raise ValueError("limit CNES deve ser um inteiro maior que zero")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("timeout CNES deve ser maior que zero")
    if catalog is not None:
        resolved = catalog.resolve(codigo_municipio_7)
        if resolved.status is not ResolutionStatus.VALID or resolved.municipality is None:
            raise ValueError(f"município CNES inválido no catálogo: {codigo_municipio_7}")
        codigo_municipio_7 = resolved.municipality.code7
        codigo_municipio_6 = resolved.municipality.code6
    else:
        if not isinstance(codigo_municipio_7, str) or not re.fullmatch(r"[0-9]{7}", codigo_municipio_7):
            raise ValueError("CNES exige código municipal IBGE de 7 dígitos")
        codigo_municipio_6 = codigo_municipio_7[:6]
    national = _load_national_cnes()
    return national.loc[national["codigo_municipio"] == codigo_municipio_6].copy()


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
        "source": "PySUS SAUDE CNES",
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
