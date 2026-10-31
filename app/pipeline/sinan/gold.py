from __future__ import annotations

import json
import hashlib
import re
from collections.abc import Mapping
from pathlib import Path
 
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
 
from ..atomic_io import write_json_atomic, write_parquet_atomic
from .columns import CATALOG, validate_keys
from datetime import UTC, datetime
from typing import Literal

from ..reference.ibge.models import MunicipalityCatalog
from ..scope import legacy_rj_mapping
from ..scope import scope_sha256
 
# Compatibilidade pública para consumidores legados; a definição vive em
# ``scope.py``. O processamento usa ``legacy_rj_mapping()`` diretamente para
# evitar que o catálogo legado seja a fonte operacional da Gold.
MUNICIPIOS_RJ = legacy_rj_mapping()

def decode_sinan_age_years(
    encoded_age: pd.Series,
    separate_type: pd.Series | None = None,
) -> pd.Series:
    raw = encoded_age.astype("string").str.extract(r"(\d+)")[0]
    numeric = pd.to_numeric(raw, errors="coerce")
    unit = raw.str[0]
    value = pd.to_numeric(raw.str[1:], errors="coerce")
    if separate_type is not None:
        separate = separate_type.astype("string").str.extract(r"([1-4])")[0]
        use_separate = separate.notna()
        unit = unit.mask(use_separate, separate)
        value = value.mask(use_separate, numeric)
    years = pd.Series(pd.NA, index=encoded_age.index, dtype="Float64")
    years = years.mask(unit.eq("1"), value / (24 * 365.25))
    years = years.mask(unit.eq("2"), value / 365.25)
    years = years.mask(unit.eq("3"), value / 12)
    years = years.mask(unit.eq("4"), value)
    return years

def age_band(
    year: pd.Series,
    birth_year: pd.Series,
    encoded_age: pd.Series | None = None,
    separate_type: pd.Series | None = None,
) -> pd.Series:
    age = decode_sinan_age_years(encoded_age, separate_type) if encoded_age is not None else pd.Series(pd.NA, index=year.index, dtype="Float64")
    fallback = year.astype("Int64") - birth_year.astype("Int64")
    age = age.fillna(fallback.astype("Float64"))
    conditions = [
        age.lt(1), age.between(1, 4), age.between(5, 9), age.between(10, 14),
        age.between(15, 19), age.between(20, 39), age.between(40, 59),
        age.between(60, 64), age.between(65, 69), age.between(70, 74),
        age.between(75, 79), age.ge(80),
    ]
    labels = [
        "LT1", "01_04", "05_09", "10_14", "15_19", "20_39",
        "40_59", "60_64", "65_69", "70_74", "75_79", "80_PLUS",
    ]
    result = pd.Series(pd.NA, index=year.index, dtype="string")
    for condition, label in zip(conditions, labels):
        result = result.mask(condition.fillna(False), label)
    return result

BASE_DIR = Path("/data")
DEFAULT_BATCH_SIZE = 50_000
GoldTarget = Literal["ad_hoc", "serving"]
CNES_METADATA_COLUMNS = ["nm_unidade", "razao_social_unidade", "tp_unidade"]
GOLD_REQUIRED_COLUMNS = {"DT_NOTIFIC", "ID_MUNICIP", "SG_UF_NOT", "NM_UF", "CS_SEXO", "ANO_NASC", "SEM_NOT"}

def normalize_municipality_codes(
    series: pd.Series, municipios: dict[str, str] | MunicipalityCatalog,
) -> pd.Series:
    raw = series.astype("string").str.extract(r"(\d+)")[0]
    municipality_key = raw.str.lstrip("0")
    mapping = municipios.as_mapping() if hasattr(municipios, "as_mapping") else municipios
    ibge_by_sinan_code = {
        **{code[:6]: code for code in mapping},
        **{code: code for code in mapping},
    }
    return municipality_key.map(ibge_by_sinan_code).fillna(raw)


def resolve_catalog_municipality_codes(
    series: pd.Series,
    catalog: MunicipalityCatalog,
    declared_ufs: pd.Series | None = None,
) -> pd.Series:
    """Resolve códigos pela identidade IBGE, sem truncar códigos completos."""
    ufs = declared_ufs.tolist() if declared_ufs is not None else [None] * len(series)
    resolved_codes = []
    for value, declared_uf in zip(series.tolist(), ufs):
        if declared_uf is not None and pd.isna(declared_uf):
            declared_uf = None
        result = catalog.resolve(value, declared_uf=declared_uf)
        resolved_codes.append(
            result.municipality.code7
            if result.status.value == "VALID" and result.municipality is not None
            else pd.NA
        )
    return pd.Series(resolved_codes, index=series.index, dtype="string")

def gold_root(target: GoldTarget) -> Path:
    if target not in {"ad_hoc", "serving"}:
        raise ValueError(f"Destino Gold inválido: {target!r}")
    return BASE_DIR / "gold" / target
 
def aggregate(
    df: pd.DataFrame,
    disease: str,
    selected_columns: list[str] | None = None,
    municipios: dict[str, str] | MunicipalityCatalog | None = None,
    cnes_lookup: pd.DataFrame | None = None,
    catalog: MunicipalityCatalog | None = None,
) -> pd.DataFrame:
    selected_columns = validate_keys(selected_columns)
    if municipios is None:
        municipios = catalog.as_mapping() if catalog is not None else legacy_rj_mapping()
    if hasattr(municipios, "as_mapping"):
        municipios = municipios.as_mapping()
    disease = disease.upper()

    missing = GOLD_REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Colunas Silver ausentes para Gold: {sorted(missing)}")

    extra_group_cols = [
        CATALOG[key].source_column
        for key in selected_columns
        if CATALOG[key].groupable and CATALOG[key].source_column in df.columns
    ]

    work = df.copy()
    if catalog is not None:
        work["cd_mun"] = resolve_catalog_municipality_codes(
            work["ID_MUNICIP"], catalog, work.get("SG_UF_NOT")
        )
    else:
        work["cd_mun"] = normalize_municipality_codes(work["ID_MUNICIP"], municipios)
    work = work[work["cd_mun"].isin(municipios)]
    if catalog is not None and not work.empty:
        canonical = work["cd_mun"].map(catalog.get_municipality)
        work["_ibge_uf_code"] = canonical.map(lambda item: item.uf_code if item else pd.NA)
        work["_ibge_uf_name"] = canonical.map(lambda item: item.uf_name if item else pd.NA)

    territory_cols = [
        "notification_district_id",
        "notification_neighborhood_id",
        "notification_territory_status",
    ]
    if cnes_lookup is not None and "cd_unidade" in cnes_lookup:
        lookup = cnes_lookup.copy()
        lookup["cd_unidade"] = lookup["cd_unidade"].astype("string").str.extract(r"(\d+)")[0].str.zfill(7)
        join_cols = [
            "cd_unidade",
            *(["cd_mun"] if "cd_mun" in lookup.columns else []),
            *[c for c in territory_cols if c in lookup.columns],
        ]
        work["_cd_unidade"] = work.get("ID_UNIDADE", pd.Series(pd.NA, index=work.index)).astype("string").str.extract(r"(\d+)")[0].str.zfill(7)
        lookup_join = lookup[join_cols].rename(
            columns={column: f"_mapped_{column}" for column in join_cols if column != "cd_unidade"}
        )
        work = work.merge(
            lookup_join,
            how="left", left_on="_cd_unidade", right_on="cd_unidade",
            validate="many_to_one",
        )
        for column in territory_cols:
            mapped = f"_mapped_{column}"
            work[column] = work[mapped] if mapped in work else pd.NA
            if mapped in work:
                work = work.drop(columns=[mapped])
        work["cd_mun_unidade"] = work.get("_mapped_cd_mun", pd.Series(pd.NA, index=work.index))
        if "_mapped_cd_mun" in work:
            work = work.drop(columns=["_mapped_cd_mun"])
        work["notification_territory_status"] = work["notification_territory_status"].fillna("UNMAPPED_NOTIFICATION_UNIT")
        if "ID_UNIDADE" in work:
            work["ID_UNIDADE"] = work["_cd_unidade"]
        work = work.drop(columns=["_cd_unidade", "cd_unidade"])
    else:
        work["cd_mun_unidade"] = pd.NA
        for column in territory_cols:
            work[column] = "UNMAPPED_NOTIFICATION_UNIT" if column == "notification_territory_status" else pd.NA

    base_cols = ["disease", "year", "month", "cd_uf", "nm_uf", "cd_mun", "nm_mun", "sex", "birth_year", "not_week"]
    if work.empty:
        return pd.DataFrame(columns=base_cols + extra_group_cols + ["cases_total"])

    work["year"] = work["DT_NOTIFIC"].dt.year.astype("int64")
    work["month"] = work["DT_NOTIFIC"].dt.month.astype("int64")
    work["source_cd_uf"] = work["SG_UF_NOT"].astype("string").str.zfill(2)
    work["cd_uf"] = (
        work["_ibge_uf_code"] if catalog is not None else work["source_cd_uf"]
    ).astype("string")
    work["NM_UF"] = (
        work["_ibge_uf_name"] if catalog is not None else work["NM_UF"]
    )
    work["nm_mun"] = work["cd_mun"].map(municipios)
    work["sex"] = work["CS_SEXO"].astype("string")
    work["birth_year"] = pd.to_numeric(work["ANO_NASC"], errors="coerce").astype("Int64")
    work["age_band"] = age_band(
        work["year"], work["birth_year"],
        work.get("NU_IDADE_N"), work.get("TP_IDADE"),
    )
    work["not_week"] = pd.to_numeric(work["SEM_NOT"], errors="coerce").astype("Int64")

    group_cols = [
        "year", "month", "cd_uf", "NM_UF", "cd_mun", "nm_mun", "sex",
        "age_band", "birth_year", "not_week", *extra_group_cols, *territory_cols,
        "cd_mun_unidade",
    ]

    result = (
        work.groupby(group_cols, dropna=False, observed=True)
        .size()
        .reset_index(name="cases_total")
        .rename(columns={"NM_UF": "nm_uf"})
    )

    if "ID_UNIDADE" in group_cols and cnes_lookup is not None:
        metadata_columns = [
            column
            for column in CNES_METADATA_COLUMNS
            if column in cnes_lookup.columns and column not in result.columns
        ]
        if metadata_columns:
            metadata_lookup = cnes_lookup[["cd_unidade", *metadata_columns]].copy()
            metadata_lookup["cd_unidade"] = metadata_lookup["cd_unidade"].astype("string").str.extract(r"(\d+)")[0].str.zfill(7)
            metadata_lookup = metadata_lookup.drop_duplicates(subset=["cd_unidade"], keep="last")
            result["_cd_unidade"] = result["ID_UNIDADE"].astype("string").str.extract(r"(\d+)")[0].str.zfill(7)
            result = result.merge(
                metadata_lookup,
                how="left",
                left_on="_cd_unidade",
                right_on="cd_unidade",
                validate="many_to_one",
            ).drop(columns=["_cd_unidade", "cd_unidade"])

    result.insert(0, "disease", disease)

    return _sort_gold(result, extra_group_cols)


def _sort_gold(result: pd.DataFrame, extra_group_cols: list[str]) -> pd.DataFrame:
    sort_cols = ["disease", "year", "month", "cd_uf", "cd_mun", "sex", "birth_year", "not_week", *extra_group_cols]
    return result.sort_values(sort_cols).reset_index(drop=True)


def _resolution_metrics(
    series: pd.Series,
    municipios: dict[str, str],
    catalog: MunicipalityCatalog | None,
    declared_ufs: pd.Series | None = None,
) -> dict[str, int]:
    metrics = {
        "scope_matched_rows": 0,
        "invalid_municipality_rows": 0,
        "out_of_scope_rows": 0,
        "uf_mismatch_rows": 0,
    }
    if catalog is None:
        normalized = normalize_municipality_codes(series, municipios)
        metrics["scope_matched_rows"] = int(normalized.isin(municipios).sum())
        return metrics
    values = series.tolist()
    ufs = declared_ufs.tolist() if declared_ufs is not None else [None] * len(values)
    for value, declared_uf in zip(values, ufs):
        if declared_uf is not None and pd.isna(declared_uf):
            declared_uf = None
        resolution = catalog.resolve(value, declared_uf=declared_uf)
        if resolution.status.value == "VALID" and resolution.municipality is not None:
            if resolution.municipality.code7 in municipios:
                metrics["scope_matched_rows"] += 1
            else:
                metrics["out_of_scope_rows"] += 1
        elif resolution.status.value == "UF_MISMATCH":
            metrics["uf_mismatch_rows"] += 1
        else:
            metrics["invalid_municipality_rows"] += 1
    return metrics

def _read_source_metadata(source: Path) -> dict:
    metadata_path = source.with_name("metadata.json")
    if not metadata_path.exists():
        raise FileNotFoundError(
            f"metadata.json não encontrado ao lado de {source}; "
            "não é possível validar a origem antes de agregar para Gold."
        )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError(f"metadata.json deve conter um objeto: {metadata_path}")
    return metadata

def _validate_source_matches(source_metadata: dict, disease: str, year: int, source: Path) -> None:
    source_disease = source_metadata.get("disease")
    source_year = source_metadata.get("source_year")

    if source_disease != disease:
        raise ValueError(
            f"Inconsistência detectada ao gerar Gold: solicitado disease={disease!r}, "
            f"mas a Silver de origem ({source}) foi gerada para disease={source_disease!r}. "
            "Abortando para evitar misturar doenças na mesma agregação."
        )
    if source_year != year:
        raise ValueError(
            f"Inconsistência detectada ao gerar Gold: solicitado year={year!r}, "
            f"mas a Silver de origem ({source}) foi gerada para source_year={source_year!r}. "
            "Abortando para evitar misturar anos na mesma agregação."
        )

def _read_cnes_metadata(path: Path) -> dict:
    metadata_path = path.with_name("metadata.json")
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.json não encontrado para lote CNES: {path.parent}")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"metadata.json CNES inválido: {metadata_path}") from exc
    if not isinstance(metadata, dict):
        raise ValueError(f"metadata.json CNES deve conter um objeto: {metadata_path}")
    if metadata.get("status") != "COMPLETED":
        raise ValueError("lote CNES não está COMPLETED; lotes parciais não podem enriquecer a Gold")
    if metadata.get("batch_id") != path.parent.name.removeprefix("batch_id="):
        raise ValueError("metadata CNES diverge do batch_id do artefato")
    municipios = metadata.get("municipios")
    if (
        not isinstance(municipios, list)
        or not municipios
        or any(not isinstance(code, str) or not re.fullmatch(r"\d{7}", code) for code in municipios)
        or len(set(municipios)) != len(municipios)
    ):
        raise ValueError("metadata CNES sem cobertura municipal válida")
    rows = metadata.get("rows")
    if not isinstance(rows, int) or isinstance(rows, bool) or rows < 0:
        raise ValueError("metadata CNES sem contagem de linhas válida")
    manifest_version = metadata.get("manifest_version")
    if manifest_version is not None and (
        not isinstance(manifest_version, int) or isinstance(manifest_version, bool) or manifest_version < 1
    ):
        raise ValueError("manifesto CNES com versão inválida")
    if manifest_version is not None and manifest_version >= 2:
        parquet_sha256 = metadata.get("parquet_sha256")
        if (
            not isinstance(parquet_sha256, str)
            or not re.fullmatch(r"[0-9a-fA-F]{64}", parquet_sha256)
        ):
            raise ValueError("manifesto CNES sem SHA-256 do Parquet válido")
        for field in ("municipios_com_registros", "municipios_sem_registros"):
            values = metadata.get(field)
            if (
                not isinstance(values, list)
                or any(not isinstance(code, str) or not re.fullmatch(r"\d{7}", code) for code in values)
                or len(set(values)) != len(values)
            ):
                raise ValueError(f"manifesto CNES sem {field} válido")
        if set(metadata["municipios_com_registros"]) & set(metadata["municipios_sem_registros"]):
            raise ValueError("manifesto CNES sobrepõe municípios com e sem registros")
        if not set(metadata["municipios_com_registros"]).issubset(set(municipios)):
            raise ValueError("manifesto CNES contém município fora da declaração de cobertura")
        if set(metadata["municipios"]) != (
            set(metadata["municipios_com_registros"]) | set(metadata["municipios_sem_registros"])
        ):
            raise ValueError("manifesto CNES não reconcilia a cobertura declarada")
    return metadata


def _validate_cnes_metadata(
    metadata: dict,
    *,
    batch_path: Path,
    catalog: MunicipalityCatalog | None = None,
    expected_scope: set[str] | None = None,
) -> None:
    if catalog is not None:
        expected_id = catalog.metadata.catalog_id
        expected_sha = catalog.metadata.sha256
        if metadata.get("ibge_catalog_id") != expected_id or metadata.get("ibge_catalog_sha256") != expected_sha:
            raise ValueError("lote CNES foi produzido com release IBGE incompatível")
    elif metadata.get("ibge_catalog_id") is not None or metadata.get("ibge_catalog_sha256") is not None:
        raise ValueError("lote CNES versionado não pode ser usado sem a release IBGE esperada")
    available = set(metadata["municipios"])
    if expected_scope and not expected_scope.issubset(available):
        missing = sorted(expected_scope - available)
        raise ValueError(f"lote CNES não cobre todo o escopo solicitado: {missing[:5]}")
    metadata["_contract_validated"] = True


def _load_cnes_batch(path: Path, *, catalog=None, expected_scope=None) -> pd.DataFrame:
    metadata = _read_cnes_metadata(path)
    _validate_cnes_metadata(
        metadata, batch_path=path, catalog=catalog, expected_scope=expected_scope,
    )
    if metadata.get("manifest_version", 0) >= 2:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != metadata["parquet_sha256"]:
            raise ValueError("Parquet CNES diverge do SHA-256 declarado no manifesto")
    lookup = pd.read_parquet(path)
    if not isinstance(lookup, pd.DataFrame) or len(lookup) != metadata["rows"]:
        raise ValueError("contagem de linhas do lote CNES diverge do metadata")
    if "cd_unidade" not in lookup.columns:
        raise ValueError("lote CNES sem cd_unidade")
    if metadata.get("manifest_version", 0) >= 2:
        if "cd_mun" not in lookup.columns:
            actual_municipalities: set[str] = set()
        else:
            actual_municipalities = set(
                lookup["cd_mun"].dropna().astype("string").str.strip().str.zfill(7)
            )
        declared_municipalities = set(metadata["municipios_com_registros"])
        if actual_municipalities != declared_municipalities:
            raise ValueError("cobertura municipal do Parquet CNES diverge do manifesto")
    lookup.attrs["cnes_metadata"] = metadata
    return lookup


def _latest_cnes_lookup() -> pd.DataFrame | None:
    cnes_dir = BASE_DIR / "silver" / "cnes"
    if not cnes_dir.exists():
        return None
    batches = sorted(cnes_dir.glob("batch_id=*/data.parquet"))
    if not batches:
        return None
    return _load_cnes_batch(batches[-1])


def _cnes_lookup_for_batch(batch_id: str) -> pd.DataFrame:
    if not re.fullmatch(r"\d{8}T\d{6}Z", batch_id):
        raise ValueError("cnes_batch_id inválido")
    path = BASE_DIR / "silver" / "cnes" / f"batch_id={batch_id}" / "data.parquet"
    if not path.exists():
        raise FileNotFoundError(f"lote CNES não encontrado: {batch_id}")
    return _load_cnes_batch(path)

def _gold_input_schema(source_schema: pa.Schema, keys: list[str]) -> pa.Schema:
    needed = GOLD_REQUIRED_COLUMNS | {"ID_UNIDADE", "NU_IDADE_N", "TP_IDADE"}
    needed.update(CATALOG[key].source_column for key in keys if CATALOG[key].groupable)
    return pa.schema(
        [field for field in source_schema if field.name in needed],
        metadata=source_schema.metadata,
    )


def _merge_counts(total: pd.DataFrame, partial: pd.DataFrame) -> pd.DataFrame:
    dimensions = [column for column in total.columns if column != "cases_total"]
    combined = pd.concat([total, partial], ignore_index=True)
    return (
        combined.groupby(dimensions, dropna=False, observed=True)["cases_total"]
        .sum().reset_index()[total.columns]
    )


def aggregate_file(
    source: Path,
    disease: str,
    year: int,
    selected_columns: list[str] | None = None,
    municipios: dict[str, str] | MunicipalityCatalog | None = None,
    run_at: datetime | None = None,
    target: GoldTarget = "ad_hoc",
    *,
    catalog: MunicipalityCatalog | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    cnes_batch_id: str | None = None,
    geographic_scope_type: str = "MUNICIPALITIES",
) -> Path:
    if batch_size <= 0:
        raise ValueError("batch_size deve ser maior que zero")
    selected_columns = validate_keys(selected_columns)
    disease = disease.upper()
    if geographic_scope_type not in {"MUNICIPALITIES", "UFs", "BRAZIL"}:
        raise ValueError("tipo de escopo geográfico inválido")
    if target == "serving" and cnes_batch_id is None:
        raise ValueError(
            "Gold serving exige --cnes-batch-id explícito para garantir "
            "reprodutibilidade da publicação"
        )
    if municipios is None:
        municipios = catalog.as_mapping() if catalog is not None else legacy_rj_mapping()
        scope_codes = sorted(municipios)
    elif isinstance(municipios, Mapping):
        scope_codes = sorted(municipios)
    else:
        scope_codes = sorted(item.code7 for item in municipios.municipalities())

    now = run_at or datetime.now(UTC)
    batch_id = now.strftime("%Y%m%dT%H%M%SZ")
    directory = (
        gold_root(target) / "sinan" / f"disease={disease.lower()}"
        / f"source_year={year}" / f"ingestion_date={now.date()}" / f"batch_id={batch_id}"
    )
    parquet = directory / "data.parquet"

    source_metadata = _read_source_metadata(source)
    _validate_source_matches(source_metadata, disease, year, source)

    cnes_lookup = (
        _cnes_lookup_for_batch(cnes_batch_id)
        if cnes_batch_id is not None
        else _latest_cnes_lookup()
    )
    if cnes_lookup is not None:
        cnes_metadata = cnes_lookup.attrs.get("cnes_metadata")
        if cnes_metadata is not None:
            _validate_cnes_metadata(
                cnes_metadata,
                batch_path=Path("cnes/data.parquet"),
                catalog=catalog,
                expected_scope=set(scope_codes),
            )
    batches = 0
    resolution_metrics = {
        "scope_matched_rows": 0,
        "invalid_municipality_rows": 0,
        "out_of_scope_rows": 0,
        "uf_mismatch_rows": 0,
    }
    with pq.ParquetFile(source) as original:
        schema = _gold_input_schema(original.schema_arrow, selected_columns)
        empty = pa.Table.from_batches([], schema=schema).to_pandas()
        result = aggregate(empty, disease, selected_columns, municipios, cnes_lookup=cnes_lookup, catalog=catalog)
        len_before = original.metadata.num_rows
        for batch in original.iter_batches(batch_size=batch_size, columns=schema.names):
            batch_frame = batch.to_pandas()
            current_metrics = _resolution_metrics(
                batch_frame["ID_MUNICIP"], municipios or legacy_rj_mapping(), catalog,
                batch_frame.get("SG_UF_NOT"),
            )
            for key, value in current_metrics.items():
                resolution_metrics[key] += value
            partial = aggregate(
                batch_frame, disease, selected_columns, municipios,
                cnes_lookup=cnes_lookup, catalog=catalog,
            )
            batches += 1
            if not partial.empty:
                result = partial if result.empty else _merge_counts(result, partial)
            del partial, batch
            if batches % 10 == 0:
                print(f"Gold: lotes={batches}, grupos={len(result)}", flush=True)

    extra_group_cols = [
        CATALOG[key].source_column for key in selected_columns
        if CATALOG[key].groupable and CATALOG[key].source_column in schema.names
    ]
    result = _sort_gold(result, extra_group_cols)
    len_after = len(result)
    resolved_rows = resolution_metrics["scope_matched_rows"]
    discarded_rows = len_before - resolved_rows
    aggregation_reduction = resolved_rows - len_after


    write_parquet_atomic(result, parquet)

    metadata = {
        "disease": disease,
        "source_year": year,
        "batch_id": batch_id,
        "ingested_at": now.isoformat(),
        "rows": len_after,
        "dropped_rows": discarded_rows,
        "columns": list(result.columns),
        "gold_target": target,
        "source_rows": len_before,
        "resolved_rows": resolved_rows,
        "discarded_rows": discarded_rows,
        "aggregation_reduction": aggregation_reduction,
        "batch_size": batch_size,
        "batches_processed": batches,
        "cnes_batch_id": cnes_batch_id,
        **resolution_metrics,
        "ibge_catalog_id": catalog.metadata.catalog_id if catalog else None,
        "ibge_catalog_sha256": catalog.metadata.sha256 if catalog else None,
        "geographic_scope": {
            "type": geographic_scope_type,
            "municipality_count": len(scope_codes),
            "scope_sha256": scope_sha256(scope_codes),
        },
    }
    write_json_atomic(metadata, directory / "metadata.json")
    return parquet
