from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from ..reference.ibge.models import MunicipalityCatalog
from ..scope import legacy_rj_mapping
from .columns import CATALOG, validate_keys
from .gold_rules import (
    age_band,
    cnes_municipality_map,
    normalize_municipality_codes,
    normalize_notification_week,
    normalize_unit_codes,
    resolve_catalog_municipality_codes,
)

GOLD_REQUIRED_COLUMNS = {"DT_NOTIFIC", "ID_MUNICIP", "SG_UF_NOT", "NM_UF"}
CNES_METADATA_COLUMNS = ["nm_unidade", "razao_social_unidade", "tp_unidade"]


def sort_gold(result: pd.DataFrame, extra_group_cols: list[str]) -> pd.DataFrame:
    columns = ["disease", "year", "month", "cd_uf", "cd_mun", "sex", "birth_year", "not_week", *extra_group_cols]
    return result.sort_values(columns).reset_index(drop=True)


def aggregate(
    df: pd.DataFrame,
    disease: str,
    selected_columns: list[str] | None = None,
    municipios: Mapping[str, str] | MunicipalityCatalog | None = None,
    cnes_lookup: pd.DataFrame | None = None,
    catalog: MunicipalityCatalog | None = None,
    allow_uf_mismatch: bool = False,
) -> pd.DataFrame:
    selected_columns = validate_keys(selected_columns)
    municipios = municipios or (catalog.as_mapping() if catalog is not None else legacy_rj_mapping())
    municipios = municipios.as_mapping() if hasattr(municipios, "as_mapping") else municipios
    disease = disease.upper()
    missing = GOLD_REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Colunas Silver ausentes para Gold: {sorted(missing)}")
    extra = [CATALOG[key].source_column for key in selected_columns if CATALOG[key].groupable and CATALOG[key].source_column in df.columns]
    work = df.copy()
    if catalog is not None:
        work["cd_mun"] = resolve_catalog_municipality_codes(work["ID_MUNICIP"], catalog, work.get("SG_UF_NOT"), allow_uf_mismatch=allow_uf_mismatch or cnes_lookup is not None)
    else:
        work["cd_mun"] = normalize_municipality_codes(work["ID_MUNICIP"], municipios)
    work = work[work["cd_mun"].isin(municipios)]
    if catalog is not None and not work.empty:
        canonical = work["cd_mun"].map(catalog.get_municipality)
        work["_ibge_uf_code"] = canonical.map(lambda item: item.uf_code if item else pd.NA)
        work["_ibge_uf_name"] = canonical.map(lambda item: item.uf_name if item else pd.NA)

    territory = ["notification_district_id", "notification_neighborhood_id", "notification_territory_status"]
    if cnes_lookup is not None and "cd_unidade" in cnes_lookup:
        lookup = cnes_lookup.copy()
        lookup["cd_unidade"] = normalize_unit_codes(lookup["cd_unidade"])
        join = ["cd_unidade", *( ["cd_mun"] if "cd_mun" in lookup else []), *[c for c in territory if c in lookup]]
        work["_cd_unidade"] = work.get("ID_UNIDADE", pd.Series(pd.NA, index=work.index)).astype("string").str.extract(r"(\d+)")[0].str.zfill(7)
        renamed = lookup[join].rename(columns={c: f"_mapped_{c}" for c in join if c != "cd_unidade"})
        work = work.merge(renamed, how="left", left_on="_cd_unidade", right_on="cd_unidade", validate="many_to_one")
        for column in territory:
            mapped = f"_mapped_{column}"
            work[column] = work[mapped] if mapped in work else pd.NA
            if mapped in work:
                work = work.drop(columns=[mapped])
        work["cd_mun_unidade"] = work.get("_mapped_cd_mun", pd.Series(pd.NA, index=work.index))
        if "_mapped_cd_mun" in work:
            work = work.drop(columns=["_mapped_cd_mun"])
        work["notification_territory_status"] = work["notification_territory_status"].fillna("UNMAPPED_NOTIFICATION_UNIT")
        if catalog is not None and not work.empty:
            mismatch = work["cd_mun_unidade"].notna() & work["cd_mun"].notna() & work["cd_mun_unidade"].ne(work["cd_mun"])
            declared = work["SG_UF_NOT"].astype("string").str.zfill(2)
            uf_without_confirmation = declared.ne(work["_ibge_uf_code"].astype("string")) & work["cd_mun"].notna() & work["cd_mun_unidade"].ne(work["cd_mun"])
            work = work.loc[~(mismatch | uf_without_confirmation)].copy()
        if "ID_UNIDADE" in work:
            work["ID_UNIDADE"] = work["_cd_unidade"]
        work = work.drop(columns=["_cd_unidade", "cd_unidade"])
    else:
        work["cd_mun_unidade"] = pd.NA
        for column in territory:
            work[column] = "UNMAPPED_NOTIFICATION_UNIT" if column == "notification_territory_status" else pd.NA

    base = ["disease", "year", "month", "cd_uf", "nm_uf", "cd_mun", "nm_mun", "sex", "birth_year", "not_week"]
    if work.empty:
        return pd.DataFrame(columns=base + extra + ["cases_total"])
    work["year"] = work["DT_NOTIFIC"].dt.year.astype("int64")
    work["month"] = work["DT_NOTIFIC"].dt.month.astype("int64")
    work["cd_uf"] = (work["_ibge_uf_code"] if catalog is not None else work["SG_UF_NOT"].astype("string").str.zfill(2)).astype("string")
    work["NM_UF"] = work["_ibge_uf_name"] if catalog is not None else work["NM_UF"]
    work["nm_mun"] = work["cd_mun"].map(municipios)
    work["sex"] = work.get("CS_SEXO", pd.Series("I", index=work.index, dtype="string")).astype("string").fillna("I")
    work["birth_year"] = pd.to_numeric(work.get("ANO_NASC", pd.Series(0, index=work.index)), errors="coerce").fillna(0).astype("Int64")
    work["age_band"] = age_band(work["year"], work["birth_year"], work.get("NU_IDADE_N"), work.get("TP_IDADE"))
    work["not_week"] = normalize_notification_week(work.get("SEM_NOT", pd.Series(pd.NA, index=work.index)), work["DT_NOTIFIC"])
    groups = ["year", "month", "cd_uf", "NM_UF", "cd_mun", "nm_mun", "sex", "age_band", "birth_year", "not_week", *extra, *territory, "cd_mun_unidade"]
    result = work.groupby(groups, dropna=False, observed=True).size().reset_index(name="cases_total").rename(columns={"NM_UF": "nm_uf"})
    if "ID_UNIDADE" in groups and cnes_lookup is not None:
        metadata = [c for c in CNES_METADATA_COLUMNS if c in cnes_lookup.columns and c not in result.columns]
        if metadata:
            lookup = cnes_lookup[["cd_unidade", *metadata]].copy()
            lookup["cd_unidade"] = normalize_unit_codes(lookup["cd_unidade"])
            lookup = lookup.drop_duplicates("cd_unidade", keep="last")
            result["_cd_unidade"] = normalize_unit_codes(result["ID_UNIDADE"])
            result = result.merge(lookup, how="left", left_on="_cd_unidade", right_on="cd_unidade", validate="many_to_one").drop(columns=["_cd_unidade", "cd_unidade"])
    result.insert(0, "disease", disease)
    return sort_gold(result, extra)


def resolution_metrics(series: pd.Series, municipios: Mapping[str, str], catalog: MunicipalityCatalog | None, declared_ufs=None, notification_units=None, cnes_lookup=None, allow_uf_mismatch=False) -> dict[str, int]:
    metrics = {"scope_matched_rows": 0, "invalid_municipality_rows": 0, "out_of_scope_rows": 0, "uf_mismatch_rows": 0, "cnes_mismatch_rows": 0}
    if catalog is None:
        metrics["scope_matched_rows"] = int(normalize_municipality_codes(series, municipios).isin(municipios).sum())
        return metrics
    cnes_by_unit = cnes_municipality_map(cnes_lookup)
    ufs = declared_ufs.tolist() if declared_ufs is not None else [None] * len(series)
    units = normalize_unit_codes(notification_units).tolist() if notification_units is not None else [None] * len(series)
    for value, declared_uf, unit in zip(series.tolist(), ufs, units):
        result = catalog.resolve(value, declared_uf=None if pd.isna(declared_uf) else declared_uf)
        if result.status.value not in {"VALID", "UF_MISMATCH"} or result.municipality is None:
            metrics["invalid_municipality_rows"] += 1
            continue
        if result.municipality.code7 not in municipios:
            metrics["out_of_scope_rows"] += 1
            continue
        mismatch = cnes_by_unit.get(unit) not in (None, result.municipality.code7)
        if result.status.value == "UF_MISMATCH":
            metrics["uf_mismatch_rows"] += 1
        if mismatch or (result.status.value == "UF_MISMATCH" and cnes_lookup is None and not allow_uf_mismatch):
            metrics["cnes_mismatch_rows"] += 1
            metrics["invalid_municipality_rows"] += 1
        else:
            metrics["scope_matched_rows"] += 1
    return metrics
