from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd
import pyarrow as pa

from ..reference.ibge.models import MunicipalityCatalog
from .columns import CATALOG


def read_source_metadata(source: Path) -> dict:
    path = source.with_name("metadata.json")
    if not path.exists():
        raise FileNotFoundError(f"metadata.json não encontrado ao lado de {source}")
    metadata = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError(f"metadata.json deve conter um objeto: {path}")
    return metadata


def validate_source_matches(metadata: dict, disease: str, year: int, source: Path) -> None:
    if metadata.get("disease") != disease:
        raise ValueError(
            f"Silver de origem ({source}) foi gerada para disease={metadata.get('disease')!r}"
        )
    if metadata.get("source_year") != year:
        raise ValueError(
            f"Silver de origem ({source}) foi gerada para source_year={metadata.get('source_year')!r}"
        )


def read_cnes_metadata(path: Path) -> dict:
    metadata_path = path.with_name("metadata.json")
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.json não encontrado para lote CNES: {path.parent}")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"metadata.json CNES inválido: {metadata_path}") from exc
    if not isinstance(metadata, dict) or metadata.get("status") != "COMPLETED":
        raise ValueError("lote CNES não está COMPLETED; lotes parciais não podem enriquecer a Gold")
    if metadata.get("batch_id") != path.parent.name.removeprefix("batch_id="):
        raise ValueError("metadata CNES diverge do batch_id do artefato")
    municipios = metadata.get("municipios")
    if not isinstance(municipios, list) or not municipios or any(
        not isinstance(code, str) or not re.fullmatch(r"\d{7}", code) for code in municipios
    ) or len(set(municipios)) != len(municipios):
        raise ValueError("metadata CNES sem cobertura municipal válida")
    if not isinstance(metadata.get("rows"), int) or isinstance(metadata["rows"], bool):
        raise ValueError("metadata CNES sem contagem de linhas válida")
    version = metadata.get("manifest_version")
    if version is not None and (not isinstance(version, int) or isinstance(version, bool) or version < 1):
        raise ValueError("manifesto CNES com versão inválida")
    if version is not None and version >= 2:
        digest = metadata.get("parquet_sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            raise ValueError("manifesto CNES sem SHA-256 do Parquet válido")
        declared = set(municipios)
        for field in ("municipios_com_registros", "municipios_sem_registros"):
            values = metadata.get(field)
            if not isinstance(values, list) or any(
                not isinstance(code, str) or not re.fullmatch(r"\d{7}", code) for code in values
            ) or len(set(values)) != len(values):
                raise ValueError(f"manifesto CNES sem {field} válido")
        with_rows = set(metadata["municipios_com_registros"])
        without_rows = set(metadata["municipios_sem_registros"])
        if with_rows & without_rows or not with_rows | without_rows == declared:
            raise ValueError("manifesto CNES não reconcilia a cobertura declarada")
        if not with_rows.issubset(declared):
            raise ValueError("manifesto CNES contém município fora da declaração de cobertura")
    return metadata


def validate_cnes_metadata(
    metadata: dict,
    *,
    catalog: MunicipalityCatalog | None = None,
    expected_scope: set[str] | None = None,
) -> None:
    if catalog is not None and (
        metadata.get("ibge_catalog_id") != catalog.metadata.catalog_id
        or metadata.get("ibge_catalog_sha256") != catalog.metadata.sha256
    ):
        raise ValueError("lote CNES foi produzido com release IBGE incompatível")
    if catalog is None and any(metadata.get(key) is not None for key in ("ibge_catalog_id", "ibge_catalog_sha256")):
        raise ValueError("lote CNES versionado não pode ser usado sem a release IBGE esperada")
    available = set(metadata["municipios"])
    if expected_scope and not expected_scope.issubset(available):
        raise ValueError(f"lote CNES não cobre todo o escopo solicitado: {sorted(expected_scope - available)[:5]}")


def load_cnes_batch(path: Path, *, catalog=None, expected_scope=None) -> pd.DataFrame:
    metadata = read_cnes_metadata(path)
    validate_cnes_metadata(metadata, catalog=catalog, expected_scope=expected_scope)
    if metadata.get("manifest_version", 0) >= 2:
        if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["parquet_sha256"]:
            raise ValueError("Parquet CNES diverge do SHA-256 declarado no manifesto")
    lookup = pd.read_parquet(path)
    if not isinstance(lookup, pd.DataFrame) or len(lookup) != metadata["rows"]:
        raise ValueError("contagem de linhas do lote CNES diverge do metadata")
    if "cd_unidade" not in lookup.columns:
        raise ValueError("lote CNES sem cd_unidade")
    lookup.attrs["cnes_metadata"] = metadata
    return lookup


def gold_input_schema(source_schema: pa.Schema, keys: list[str]) -> pa.Schema:
    needed = {"DT_NOTIFIC", "ID_MUNICIP", "SG_UF_NOT", "NM_UF", "CS_SEXO", "ANO_NASC", "ID_UNIDADE", "NU_IDADE_N", "TP_IDADE"}
    needed.update(CATALOG[key].source_column for key in keys if CATALOG[key].groupable)
    return pa.schema([field for field in source_schema if field.name in needed], metadata=source_schema.metadata)


def merge_counts(total: pd.DataFrame, partial: pd.DataFrame) -> pd.DataFrame:
    dimensions = [column for column in total.columns if column != "cases_total"]
    combined = pd.concat([total, partial], ignore_index=True)
    return combined.groupby(dimensions, dropna=False, observed=True)["cases_total"].sum().reset_index()[total.columns]
