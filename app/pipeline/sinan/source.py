"""Inspeção e cache do arquivo Parquet remoto do SINAN via PySUS."""

from __future__ import annotations

import asyncio
import fcntl
import hashlib
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pysus

BASE_DIR = Path(os.environ.get("PIPELINE_DATA_DIR", "/data"))
SOURCE_DIR = BASE_DIR / "source" / "sinan"


class SinanSourceUnavailable(RuntimeError):
    """O catálogo remoto não possui Parquet para o recorte solicitado."""


@contextmanager
def _pysus_cache_lock():
    """Serializa o acesso ao catálogo DuckLake compartilhado pelo PySUS."""
    cache_path = Path(pysus.CACHEPATH)
    cache_path.mkdir(parents=True, exist_ok=True)
    lock_path = cache_path / ".nss-sinan-cache.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            # PySUS may leave a replay WAL after refreshing its remote DuckDB
            # catalog.  A later read then fails with "schema pysus already
            # exists" even though the catalog itself is valid.  Access is
            # serialized here, so stale WALs can be discarded safely before
            # the next catalog operation.
            for wal in cache_path.glob("ducklake/*.duckdb.wal"):
                wal.unlink(missing_ok=True)
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


@dataclass(frozen=True)
class RemoteSinanFile:
    disease: str
    year: int
    path: str
    size_bytes: int
    sha256: str | None = None

    @property
    def local_path(self) -> Path:
        return (
            SOURCE_DIR
            / f"disease={self.disease.lower()}"
            / f"source_year={self.year}"
            / "data.parquet"
        )


def inspect_remote_file(disease: str, year: int) -> RemoteSinanFile:
    disease = disease.upper()
    with _pysus_cache_lock():
        files = pysus.ftp.sinan(disease=disease, year=year, download=False)
    parquet_files = [item for item in files if str(item.path).lower().endswith(".parquet")]
    if not parquet_files:
        raise SinanSourceUnavailable(
            f"Nenhum Parquet SINAN disponível para {disease}/{year}"
        )
    if len(parquet_files) != 1:
        raise RuntimeError(
            f"Esperado exatamente um Parquet SINAN para {disease}/{year}; "
            f"encontrados {len(parquet_files)}"
        )
    item = parquet_files[0]
    if item.size is None or int(item.size) < 0:
        raise RuntimeError(f"Tamanho remoto inválido para {item.path}: {item.size!r}")
    sha256 = getattr(item, "sha256", None)
    if sha256 is not None:
        sha256 = str(sha256).strip().lower() or None
        if sha256 is not None and len(sha256) != 64:
            raise RuntimeError(f"Checksum SHA-256 remoto inválido para {item.path}")
        if sha256 is not None:
            try:
                int(sha256, 16)
            except ValueError as exc:
                raise RuntimeError(f"Checksum SHA-256 remoto inválido para {item.path}") from exc
    return RemoteSinanFile(disease, year, str(item.path), int(item.size), sha256)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_changed(remote: RemoteSinanFile) -> bool:
    try:
        if remote.local_path.stat().st_size != remote.size_bytes:
            return True
        return remote.sha256 is not None and sha256_file(remote.local_path) != remote.sha256
    except FileNotFoundError:
        return True


def download_remote_file(remote: RemoteSinanFile) -> Path:
    destination = remote.local_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=destination.parent, prefix=".download-", suffix=".parquet", delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with _pysus_cache_lock():
            files = pysus.ftp.sinan(disease=remote.disease, year=remote.year, download=False)
            parquet_files = [item for item in files if str(item.path) == remote.path]
            if len(parquet_files) != 1:
                raise RuntimeError(f"Arquivo remoto mudou durante o download: {remote.path}")
            asyncio.run(parquet_files[0].download(output=temporary_path))
        downloaded_size = temporary_path.stat().st_size
        if downloaded_size != remote.size_bytes:
            raise RuntimeError(
                f"Tamanho baixado divergente para {remote.path}: "
                f"esperado={remote.size_bytes}, obtido={downloaded_size}"
            )
        downloaded_sha256 = sha256_file(temporary_path)
        if remote.sha256 is not None and downloaded_sha256 != remote.sha256:
            raise RuntimeError(
                f"Checksum SHA-256 baixado divergente para {remote.path}: "
                f"esperado={remote.sha256}, obtido={downloaded_sha256}"
            )
        os.replace(temporary_path, destination)
        return destination
    finally:
        temporary_path.unlink(missing_ok=True)


def read_remote_cache(remote: RemoteSinanFile) -> pd.DataFrame:
    if not remote.local_path.exists():
        raise FileNotFoundError(remote.local_path)
    return pd.read_parquet(remote.local_path)
