"""Inspeção e cache do arquivo Parquet remoto do SINAN via PySUS."""

from __future__ import annotations

import asyncio
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pysus

BASE_DIR = Path(os.environ.get("PIPELINE_DATA_DIR", "/data"))
SOURCE_DIR = BASE_DIR / "source" / "sinan"


@dataclass(frozen=True)
class RemoteSinanFile:
    disease: str
    year: int
    path: str
    size_bytes: int

    @property
    def local_path(self) -> Path:
        return (
            SOURCE_DIR
            / f"disease={self.disease.lower()}"
            / f"source_year={self.year}"
            / "data.parquet"
        )


def inspect_remote_file(disease: str, year: int) -> RemoteSinanFile:
    """Consulta o catálogo FTP/PySUS sem baixar o conteúdo."""
    disease = disease.upper()
    files = pysus.ftp.sinan(disease=disease, year=year, download=False)
    parquet_files = [item for item in files if str(item.path).lower().endswith(".parquet")]
    if len(parquet_files) != 1:
        raise RuntimeError(
            f"Esperado exatamente um Parquet SINAN para {disease}/{year}; "
            f"encontrados {len(parquet_files)}"
        )
    item = parquet_files[0]
    if item.size is None or int(item.size) < 0:
        raise RuntimeError(f"Tamanho remoto inválido para {item.path}: {item.size!r}")
    return RemoteSinanFile(disease, year, str(item.path), int(item.size))


def is_changed(remote: RemoteSinanFile) -> bool:
    """Compara somente o tamanho, conforme a política de atualização."""
    try:
        return remote.local_path.stat().st_size != remote.size_bytes
    except FileNotFoundError:
        return True


def download_remote_file(remote: RemoteSinanFile) -> Path:
    """Baixa o Parquet remoto atomicamente para o cache canônico local."""
    destination = remote.local_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=destination.parent, prefix=".download-", suffix=".parquet", delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
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
        os.replace(temporary_path, destination)
        return destination
    finally:
        temporary_path.unlink(missing_ok=True)


def read_remote_cache(remote: RemoteSinanFile) -> pd.DataFrame:
    if not remote.local_path.exists():
        raise FileNotFoundError(remote.local_path)
    return pd.read_parquet(remote.local_path)
