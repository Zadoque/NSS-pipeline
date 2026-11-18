from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from ..reference.ibge.models import MunicipalityCatalog


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
    age = (
        decode_sinan_age_years(encoded_age, separate_type)
        if encoded_age is not None
        else pd.Series(pd.NA, index=year.index, dtype="Float64")
    )
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


def normalize_notification_week(
    week: pd.Series,
    notification_date: pd.Series,
) -> pd.Series:
    """Normalize SEM_NOT, falling back to the ISO week of DT_NOTIFIC."""
    raw = week.astype("string").str.strip().replace("", pd.NA)
    numeric = pd.to_numeric(raw, errors="coerce")
    normalized = numeric.copy()
    reduced = numeric.between(1000, 9999) & numeric.mod(100).between(1, 53)
    normalized.loc[reduced] = (
        (2000 + numeric.loc[reduced] // 100) * 100
        + numeric.loc[reduced] % 100
    )
    valid = (
        normalized.eq(0)
        | (normalized.ge(100001) & normalized.mod(100).between(1, 53))
    ).fillna(False)
    dates = pd.to_datetime(notification_date, errors="coerce")
    can_fallback = (~valid) & dates.notna()
    if ((~valid) & dates.isna()).any():
        raise ValueError(
            "SEM_NOT inválido e DT_NOTIFIC ausente ou inválida; "
            "não foi possível calcular a semana epidemiológica"
        )
    normalized.loc[can_fallback] = (
        dates.loc[can_fallback].dt.year * 100
        + dates.loc[can_fallback].dt.isocalendar().loc[can_fallback, "week"].astype("int64")
    )
    return normalized.astype("Int64")


def normalize_municipality_codes(
    series: pd.Series, municipios: Mapping[str, str] | MunicipalityCatalog,
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
    *,
    allow_uf_mismatch: bool = False,
) -> pd.Series:
    ufs = declared_ufs.tolist() if declared_ufs is not None else [None] * len(series)
    resolved_codes = []
    for value, declared_uf in zip(series.tolist(), ufs):
        if declared_uf is not None and pd.isna(declared_uf):
            declared_uf = None
        result = catalog.resolve(value, declared_uf=declared_uf)
        if allow_uf_mismatch and result.status.value == "UF_MISMATCH":
            result = catalog.resolve(value)
        resolved_codes.append(
            result.municipality.code7
            if result.status.value == "VALID" and result.municipality is not None
            else pd.NA
        )
    return pd.Series(resolved_codes, index=series.index, dtype="string")


def normalize_unit_codes(series: pd.Series) -> pd.Series:
    return series.astype("string").str.extract(r"(\d+)")[0].str.zfill(7)


def cnes_municipality_map(cnes_lookup: pd.DataFrame | None) -> dict[str, str]:
    if cnes_lookup is None or not {"cd_unidade", "cd_mun"}.issubset(cnes_lookup.columns):
        return {}
    lookup = cnes_lookup[["cd_unidade", "cd_mun"]].copy()
    lookup["cd_unidade"] = normalize_unit_codes(lookup["cd_unidade"])
    lookup["cd_mun"] = normalize_unit_codes(lookup["cd_mun"])
    return (
        lookup.dropna(subset=["cd_unidade", "cd_mun"])
        .drop_duplicates("cd_unidade", keep="last")
        .set_index("cd_unidade")["cd_mun"]
        .to_dict()
    )
