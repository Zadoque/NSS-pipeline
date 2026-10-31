from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..atomic_io import write_json_atomic, write_parquet_atomic
from ..reference.ibge.models import MunicipalityCatalog, ResolutionStatus

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


def session_with_retries() -> requests.Session:
    """Cria uma sessão CNES reutilizável por uma execução do pipeline."""
    return _session_with_retries()


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
        if not isinstance(codigo_municipio_7, str) or not codigo_municipio_7.isdigit() or len(codigo_municipio_7) != 7:
            raise ValueError("CNES exige código municipal IBGE de 7 dígitos")
        codigo_municipio_6 = codigo_municipio_7[:6]
    client = session or _session_with_retries()
    owns_session = session is None
    registros = []
    offset = 0
    previous_page_signature: str | None = None
    try:
        while True:
            resp = client.get(
                API_BASE,
                params={"codigo_municipio": codigo_municipio_6, "limit": limit, "offset": offset},
                timeout=timeout,
            )
            resp.raise_for_status()
            pagina = _extract_page(resp.json())
            if not pagina:
                break
            page_signature = json.dumps(
                pagina, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            )
            if page_signature == previous_page_signature:
                raise RuntimeError(
                    "API CNES repetiu uma página; ingestão interrompida para evitar loop"
                )
            previous_page_signature = page_signature
            registros.extend(pagina)
            # A API pode aplicar um teto menor que ``limit`` sem sinalizá-lo.
            # Avançar pelo tamanho efetivo evita saltar registros nesse caso.
            offset += len(pagina)
        return pd.DataFrame(registros)
    finally:
        if owns_session:
            client.close()


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
