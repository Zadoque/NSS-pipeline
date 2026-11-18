from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from ..atomic_io import write_json_atomic, write_parquet_atomic
from ..reference.ibge.models import MunicipalityCatalog, ResolutionStatus

BASE_DIR = Path(os.environ.get("PIPELINE_DATA_DIR", "/data"))

BRAZIL_LATITUDE_RANGE = (-34.0, 6.0)
# Inclui os municípios insulares, em especial Fernando de Noronha (~-32.4).
BRAZIL_LONGITUDE_RANGE = (-74.0, -28.0)


def _copy_legacy_address_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Aceita também Bronze anterior à normalização dos nomes de endereço."""
    out = df.copy()
    aliases = {
        "CO_CEP": "cep_estabelecimento",
        "NO_LOGRADOURO": "logradouro_estabelecimento",
        "NU_ENDERECO": "numero_estabelecimento",
        "codigo_cep_estabelecimento": "cep_estabelecimento",
        "endereco_estabelecimento": "logradouro_estabelecimento",
    }
    for legacy, canonical in aliases.items():
        if canonical not in out.columns and legacy in out.columns:
            out[canonical] = out[legacy]
    return out


def valid_brazil_coordinate_mask(df: pd.DataFrame) -> pd.Series:
    latitude = pd.to_numeric(df.get("latitude_cnes"), errors="coerce")
    longitude = pd.to_numeric(df.get("longitude_cnes"), errors="coerce")
    return (
        latitude.between(*BRAZIL_LATITUDE_RANGE)
        & longitude.between(*BRAZIL_LONGITUDE_RANGE)
    ).fillna(False)


def transform_cnes(
    df: pd.DataFrame,
    *,
    catalog: MunicipalityCatalog | None = None,
    municipality_code7: str | None = None,
) -> pd.DataFrame:
    df = _copy_legacy_address_columns(df)
    columns = [
        "codigo_cnes", "nome_fantasia", "nome_razao_social",
        "codigo_municipio", "codigo_tipo_unidade",
        "bairro_estabelecimento", "latitude_estabelecimento_decimo_grau",
        "longitude_estabelecimento_decimo_grau",
        "cep_estabelecimento", "logradouro_estabelecimento",
        "numero_estabelecimento",
    ]
    out = df[[column for column in columns if column in df.columns]].copy()

    out["codigo_cnes"] = out["codigo_cnes"].astype("string").str.zfill(7)
    out["codigo_municipio"] = out["codigo_municipio"].astype("string")

    if catalog is not None:
        resolutions = out["codigo_municipio"].map(catalog.resolve)
        expected = municipality_code7
        resolved_codes = resolutions.map(
            lambda result: result.municipality.code7
            if result.status is ResolutionStatus.VALID and result.municipality else pd.NA
        ).astype("string")
        if expected is not None:
            is_mismatch = resolved_codes.notna() & resolved_codes.ne(expected)
            out["cd_mun"] = resolved_codes.mask(is_mismatch, pd.NA).astype("string")
            out["municipality_resolution_status"] = resolutions.map(
                lambda result: result.status.value
            ).astype("string").mask(is_mismatch, "OUT_OF_SCOPE")
        else:
            out["cd_mun"] = resolved_codes
            out["municipality_resolution_status"] = resolutions.map(lambda result: result.status.value).astype("string")
    elif municipality_code7 is not None:
        out["cd_mun"] = municipality_code7
        out["municipality_resolution_status"] = "VALID_LEGACY_SCOPE"

    out = out.drop_duplicates(subset=["codigo_cnes"], keep="last")
    out = out.rename(columns={
        "codigo_cnes": "cd_unidade",
        "nome_fantasia": "nm_unidade",
        "nome_razao_social": "razao_social_unidade",
        "codigo_tipo_unidade": "tp_unidade",
        "bairro_estabelecimento": "bairro_cnes",
        "latitude_estabelecimento_decimo_grau": "latitude_cnes",
        "longitude_estabelecimento_decimo_grau": "longitude_cnes",
        "cep_estabelecimento": "cep",
        "logradouro_estabelecimento": "logradouro",
        "numero_estabelecimento": "numero",
    })
    for column in ("latitude_cnes", "longitude_cnes"):
        if column not in out:
            out[column] = pd.NA
    valid = valid_brazil_coordinate_mask(out)
    out["latitude"] = pd.to_numeric(out["latitude_cnes"], errors="coerce").where(valid)
    out["longitude"] = pd.to_numeric(out["longitude_cnes"], errors="coerce").where(valid)
    out["latitude_geocoded"] = pd.Series(pd.NA, index=out.index, dtype="Float64")
    out["longitude_geocoded"] = pd.Series(pd.NA, index=out.index, dtype="Float64")
    out["coordinate_source"] = pd.Series(
        valid.map({True: "CNES", False: "UNRESOLVED"}), dtype="string"
    )
    out["geocoding_status"] = pd.Series(
        valid.map({True: "CNES_VALID", False: "NOT_REQUESTED"}), dtype="string"
    )
    out["geocoding_provider"] = pd.Series(pd.NA, index=out.index, dtype="string")
    out["geocoding_confidence"] = pd.Series(pd.NA, index=out.index, dtype="Float64")
    out["geocoded_at"] = pd.Series(pd.NA, index=out.index, dtype="string")
    return out


def transform_cnes_file(
    source: Path,
    municipio: str,
    run_at: datetime | None = None,
    *,
    catalog: MunicipalityCatalog | None = None,
) -> Path:
    df = pd.read_parquet(source)
    len_before = len(df)

    result = transform_cnes(df, catalog=catalog, municipality_code7=municipio)
    len_after = len(result)

    now = run_at or datetime.now(UTC)
    batch_id = now.strftime("%Y%m%dT%H%M%SZ")
    directory = (
        BASE_DIR / "silver" / "cnes" / f"municipio={municipio}"
        / f"ingestion_date={now.date()}" / f"batch_id={batch_id}"
    )
    parquet = directory / "data.parquet"
    write_parquet_atomic(result, parquet)

    metadata = {
        "municipio": municipio,
        "batch_id": batch_id,
        "ingested_at": now.isoformat(),
        "rows": len_after,
        "dropped_rows": len_before - len_after,
        "columns": list(result.columns),
    }
    write_json_atomic(metadata, directory / "metadata.json")
    return parquet


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transforma CNES Bronze -> Silver")
    parser.add_argument("--source", required=True, type=Path, help="Parquet de entrada (Bronze)")
    parser.add_argument("--municipio", required=True)
    args = parser.parse_args()
    print(transform_cnes_file(args.source, args.municipio))
