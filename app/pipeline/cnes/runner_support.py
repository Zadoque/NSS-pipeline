from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import tempfile

import duckdb
import pandas as pd
import pyarrow.parquet as pq
import requests
import fcntl

from ..reference.ibge.models import MunicipalityCatalog, ResolutionStatus

SHA256_LENGTH = 64


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def geocoder_identity(geocoder) -> str | None:
    if geocoder is None:
        return None
    return str(getattr(geocoder, "identity", geocoder.name))


def consolidated_municipalities(path: Path) -> list[str]:
    if "cd_mun" not in pq.ParquetFile(path).schema.names:
        return []
    connection = duckdb.connect()
    try:
        rows = connection.execute(
            "SELECT DISTINCT lpad(trim(CAST(cd_mun AS VARCHAR)), 7, '0') "
            "FROM read_parquet(?) WHERE cd_mun IS NOT NULL "
            "AND trim(CAST(cd_mun AS VARCHAR)) <> '' ORDER BY 1", [str(path)]
        ).fetchall()
    finally:
        connection.close()
    return [row[0] for row in rows]


def geocoding_status_counts(path: Path) -> dict[str, int]:
    if "geocoding_status" not in pq.ParquetFile(path).schema.names:
        return {}
    connection = duckdb.connect()
    try:
        rows = connection.execute(
            "SELECT coalesce(CAST(geocoding_status AS VARCHAR), 'MISSING'), count(*) "
            "FROM read_parquet(?) GROUP BY 1 ORDER BY 1", [str(path)]
        ).fetchall()
    finally:
        connection.close()
    return {status: int(count) for status, count in rows}


def validate_checkpoint_completed(completed: object, municipios: dict[str, str]) -> dict:
    if not isinstance(completed, dict):
        raise ValueError("checkpoint CNES com completed inválido")
    if not set(completed).issubset(municipios):
        raise ValueError("checkpoint CNES contém município fora do escopo")
    for code, entry in completed.items():
        if not isinstance(code, str) or not isinstance(entry, dict):
            raise ValueError("checkpoint CNES com completed inválido")
        path, digest, rows = entry.get("bronze_path"), entry.get("bronze_sha256"), entry.get("rows")
        if (not isinstance(path, str) or not path or not isinstance(digest, str)
                or len(digest) != SHA256_LENGTH
                or any(char not in "0123456789abcdefABCDEF" for char in digest)
                or not isinstance(rows, int) or isinstance(rows, bool) or rows < 0):
            raise ValueError("checkpoint CNES com completed inválido")
    return completed


def validate_checkpoint_failed(failed: object, municipios: dict[str, str]) -> dict:
    if not isinstance(failed, dict):
        raise ValueError("checkpoint CNES com failed inválido")
    if not set(failed).issubset(municipios):
        raise ValueError("checkpoint CNES contém falha fora do escopo")
    for code, entry in failed.items():
        if (not isinstance(code, str) or not isinstance(entry, dict)
                or not isinstance(entry.get("error_type"), str)
                or not isinstance(entry.get("error_message"), str)
                or not entry["error_type"] or not entry["error_message"]):
            raise ValueError("checkpoint CNES com failed inválido")
    return failed


def classify_error(error: Exception) -> str:
    if isinstance(error, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return "NETWORK_ERROR"
    if isinstance(error, requests.exceptions.HTTPError):
        return "HTTP_ERROR"
    if isinstance(error, ValueError):
        return "VALIDATION_ERROR"
    if isinstance(error, RuntimeError):
        return "API_ERROR"
    return "PROCESSING_ERROR"


def parallel_fetch_batches(municipalities, *, page_size, catalog, request_timeout, workers):
    from .. import run_cnes as service
    for start in range(0, len(municipalities), workers * 4):
        batch = municipalities[start:start + workers * 4]

        def fetch_one(code):
            worker_session = service.session_with_retries()
            try:
                return service.fetch_estabelecimentos(
                    code, limit=page_size, catalog=catalog,
                    session=worker_session, timeout=request_timeout,
                )
            except Exception as error:
                return error
            finally:
                worker_session.close()

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {code: executor.submit(fetch_one, code) for code in batch}
            for code in batch:
                yield code, futures[code].result()


def canonicalize_municipalities(requested: dict[str, str], catalog: MunicipalityCatalog) -> dict[str, str]:
    canonical = {}
    for code7, supplied_name in requested.items():
        result = catalog.resolve(code7)
        if result.status is not ResolutionStatus.VALID or result.municipality is None:
            raise ValueError(f"município CNES inválido no catálogo: {code7}")
        if supplied_name and supplied_name != result.municipality.name:
            raise ValueError(f"nome municipal diverge do catálogo IBGE: {code7} ({supplied_name!r} != {result.municipality.name!r})")
        canonical[result.municipality.code7] = result.municipality.name
    return canonical


def validate_municipality_resolution(silver: pd.DataFrame, *, catalog, municipality_code7: str) -> None:
    if catalog is None:
        return
    column = "municipality_resolution_status"
    if column not in silver.columns:
        raise ValueError(f"CNES sem status de resolução municipal para {municipality_code7}")
    statuses = silver[column].astype("string").fillna("MISSING")
    invalid = statuses.ne("VALID")
    if invalid.any():
        values = sorted(set(statuses[invalid]))
        if "OUT_OF_SCOPE" in values:
            raise ValueError(f"CNES retornou estabelecimento fora do município solicitado: {municipality_code7}")
        raise ValueError(f"CNES retornou códigos municipais não resolvidos para {municipality_code7}: {values}")


def write_consolidated(silver_paths: list[Path], destination: Path) -> int:
    if not silver_paths:
        raise RuntimeError("CNES não produziu nenhum município com dados")
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock_path = destination.with_name(f".{destination.name}.lock")
    handle = tempfile.NamedTemporaryFile(prefix=f".{destination.name}.", suffix=".streaming.tmp", dir=destination.parent, delete=False)
    temporary = Path(handle.name)
    handle.close()
    paths = "[" + ", ".join(f"'{str(path).replace(chr(39), chr(39) * 2)}'" for path in silver_paths) + "]"
    query = f"""COPY (SELECT * EXCLUDE (_part_order, _row_number) FROM (SELECT *, row_number() OVER (PARTITION BY cd_unidade ORDER BY _part_order DESC) AS _row_number FROM read_parquet({paths}, union_by_name = true)) WHERE _row_number = 1) TO '{str(temporary).replace(chr(39), chr(39) * 2)}' (FORMAT PARQUET)"""
    try:
        with lock_path.open("w", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            connection = duckdb.connect()
            try:
                connection.execute(query)
            finally:
                connection.close()
            os.replace(temporary, destination)
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    finally:
        temporary.unlink(missing_ok=True)
    return int(pq.ParquetFile(destination).metadata.num_rows)
