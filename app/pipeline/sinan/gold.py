from __future__ import annotations

import json
from pathlib import Path
 
import pandas as pd
 
from ..atomic_io import write_json_atomic, write_parquet_atomic
from .columns import CATALOG, validate_keys
from datetime import UTC, datetime
from .metrics_exporter import export_layer_metrics
from typing import Literal

 
MUNICIPIOS_RJ = {
    "3301009": "Campos dos Goytacazes",
    "3305000": "São João da Barra",
    "3302205": "Itaperuna",
    "3302403": "Macaé",
    #"3304557": "Rio de Janeiro",
}


def decode_sinan_age_years(
    encoded_age: pd.Series,
    separate_type: pd.Series | None = None,
) -> pd.Series:
    """Converte a idade codificada do SINAN em anos.

    Na forma ``NU_IDADE_N``, o primeiro dígito é a unidade: 1 hora, 2 dia,
    3 mês e 4 ano; os três dígitos restantes são o valor. Alguns layouts
    antigos expõem a unidade separadamente em ``TP_IDADE``. Valores ausentes,
    inválidos ou sentinelas não são convertidos em zero.
    """
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
    """Deriva faixa usando a idade codificada SINAN, com fallback controlado."""
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
GoldTarget = Literal["ad_hoc", "serving"]
CNES_METADATA_COLUMNS = ["nm_unidade", "razao_social_unidade", "tp_unidade"]


def normalize_municipality_codes(
    series: pd.Series, municipios: dict[str, str],
) -> pd.Series:
    """Resolve códigos SINAN para o IBGE canônico do recorte.

    Aceita seis ou sete dígitos e zeros de preenchimento. Códigos fora
    do crosswalk são preservados para que o filtro do recorte os exclua.
    A mesma regra é usada pela Gold e pela contagem independente da Silver.
    """
    raw = series.astype("string").str.extract(r"(\d+)")[0]
    municipality_key = raw.str.lstrip("0")
    ibge_by_sinan_code = {
        **{code[:6]: code for code in municipios},
        **{code: code for code in municipios},
    }
    return municipality_key.map(ibge_by_sinan_code).fillna(raw)


def gold_root(target: GoldTarget) -> Path:
    """Retorna a raiz física da Gold conforme o contrato de consumo.

    ``ad_hoc`` é descartável e serve análises/reprocessamentos exploratórios.
    ``serving`` é a publicação canônica consumida pelo carregamento/API.
    Mantê-las em árvores diferentes impede que uma análise exploratória seja
    confundida com o snapshot publicado.
    """
    if target not in {"ad_hoc", "serving"}:
        raise ValueError(f"Destino Gold inválido: {target!r}")
    return BASE_DIR / "gold" / target
 
def aggregate(
    df: pd.DataFrame,
    disease: str,
    selected_columns: list[str] | None = None,
    municipios: dict[str, str] | None = None,
    cnes_lookup: pd.DataFrame | None = None,
) -> pd.DataFrame:
    selected_columns = validate_keys(selected_columns)
    municipios = municipios if municipios is not None else MUNICIPIOS_RJ
    disease = disease.upper()

    required = {"DT_NOTIFIC", "ID_MUNICIP", "SG_UF_NOT", "NM_UF", "CS_SEXO", "ANO_NASC", "SEM_NOT"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Colunas Silver ausentes para Gold: {sorted(missing)}")

    extra_group_cols = [
        CATALOG[key].source_column
        for key in selected_columns
        if CATALOG[key].groupable and CATALOG[key].source_column in df.columns
    ]

    work = df.copy()
    work["cd_mun"] = normalize_municipality_codes(work["ID_MUNICIP"], municipios)
    work = work[work["cd_mun"].isin(municipios)]

    # O total municipal continua sendo o universo completo. O vínculo
    # intramunicipal só existe quando ID_UNIDADE encontra CNES e sua posição
    # cai numa geometria oficial; ausência nunca vira zero.
    territory_cols = [
        "notification_district_id",
        "notification_neighborhood_id",
        "notification_territory_status",
    ]
    if cnes_lookup is not None and "cd_unidade" in cnes_lookup:
        lookup = cnes_lookup.copy()
        lookup["cd_unidade"] = lookup["cd_unidade"].astype("string").str.extract(r"(\d+)")[0].str.zfill(7)
        join_cols = ["cd_unidade", *[c for c in territory_cols if c in lookup.columns]]
        work["_cd_unidade"] = work.get("ID_UNIDADE", pd.Series(pd.NA, index=work.index)).astype("string").str.extract(r"(\d+)")[0].str.zfill(7)
        work = work.merge(
            lookup[join_cols].rename(columns={column: f"_mapped_{column}" for column in territory_cols if column in lookup}),
            how="left", left_on="_cd_unidade", right_on="cd_unidade",
            validate="many_to_one",
        )
        for column in territory_cols:
            mapped = f"_mapped_{column}"
            work[column] = work[mapped] if mapped in work else pd.NA
            if mapped in work:
                work = work.drop(columns=[mapped])
        work["notification_territory_status"] = work["notification_territory_status"].fillna("UNMAPPED_NOTIFICATION_UNIT")
        if "ID_UNIDADE" in work:
            # O Gold usa sempre o mesmo formato do código CNES. Isso evita
            # que valores como 0729884.0 deixem de casar com o lookup.
            work["ID_UNIDADE"] = work["_cd_unidade"]
        work = work.drop(columns=["_cd_unidade", "cd_unidade"])
    else:
        for column in territory_cols:
            work[column] = "UNMAPPED_NOTIFICATION_UNIT" if column == "notification_territory_status" else pd.NA

    base_cols = ["disease", "year", "month", "cd_uf", "nm_uf", "cd_mun", "nm_mun", "sex", "birth_year", "not_week"]
    if work.empty:
        return pd.DataFrame(columns=base_cols + extra_group_cols + ["cases_total"])

    work["year"] = work["DT_NOTIFIC"].dt.year.astype("int64")
    work["month"] = work["DT_NOTIFIC"].dt.month.astype("int64")
    work["cd_uf"] = work["SG_UF_NOT"].astype("string").str.zfill(2)
    work["nm_mun"] = work["cd_mun"].map(municipios)
    work["sex"] = work["CS_SEXO"].astype("string")
    work["birth_year"] = pd.to_numeric(work["ANO_NASC"], errors="coerce").astype("Int64")
    work["age_band"] = age_band(
        work["year"], work["birth_year"],
        work.get("NU_IDADE_N"), work.get("TP_IDADE"),
    )
    work["not_week"] = pd.to_numeric(work["SEM_NOT"], errors="coerce").astype("Int64")

    group_cols = ["year", "month", "cd_uf", "NM_UF", "cd_mun", "nm_mun", "sex", "age_band", "birth_year", "not_week", *extra_group_cols, *territory_cols]

    result = (
        work.groupby(group_cols, dropna=False)
        .size()
        .reset_index(name="cases_total")
        .rename(columns={"NM_UF": "nm_uf"})
    )

    if "ID_UNIDADE" in group_cols and cnes_lookup is not None:
        # O território já foi associado antes do groupby. Reunir o lookup
        # completo aqui repetia essas colunas e fazia o Pandas criar _x/_y.
        # Neste segundo passo entram somente os metadados necessários para a
        # dimensão de unidade de saúde.
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

    sort_cols = ["disease", "year", "month", "cd_uf", "cd_mun", "sex", "birth_year", "not_week", *extra_group_cols]
    return result.sort_values(sort_cols).reset_index(drop=True) 

def _read_source_metadata(source: Path) -> dict:
    metadata_path = source.with_name("metadata.json")
    if not metadata_path.exists():
        raise FileNotFoundError(
            f"metadata.json não encontrado ao lado de {source}; "
            "não é possível validar a origem antes de agregar para Gold."
        )
    return json.loads(metadata_path.read_text(encoding="utf-8"))

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

def _latest_cnes_lookup() -> pd.DataFrame | None:
    cnes_dir = BASE_DIR / "silver" / "cnes"
    if not cnes_dir.exists():
        return None
    batches = sorted(cnes_dir.glob("batch_id=*/data.parquet"))
    if not batches:
        return None
    return pd.read_parquet(batches[-1])

def aggregate_file(
    source: Path,
    disease: str,
    year: int,
    selected_columns: list[str] | None = None,
    municipios: dict[str, str] | None = None,
    run_at: datetime | None = None,
    target: GoldTarget = "ad_hoc",
) -> Path:
    disease = disease.upper()

    source_metadata = _read_source_metadata(source)
    _validate_source_matches(source_metadata, disease, year, source)

    df = pd.read_parquet(source)
    len_before = len(df)

    cnes_lookup = _latest_cnes_lookup()

    result = aggregate(df, disease, selected_columns, municipios, cnes_lookup=cnes_lookup)
    len_after = len(result)

    now = run_at or datetime.now(UTC)
    batch_id = now.strftime("%Y%m%dT%H%M%SZ")
    directory = (
        gold_root(target) / "sinan" / f"disease={disease.lower()}"
        / f"source_year={year}" / f"ingestion_date={now.date()}" / f"batch_id={batch_id}"
    )
    parquet = directory / "data.parquet"
    write_parquet_atomic(result, parquet)

    metadata = {
        "disease": disease,
        "source_year": year,
        "batch_id": batch_id,
        "ingested_at": now.isoformat(),
        "rows": len_after,
        "dropped_rows": len_before - len_after,
        "columns": list(result.columns),
        "gold_target": target,
    }
    write_json_atomic(metadata, directory / "metadata.json")

    export_layer_metrics(layer="gold", disease=disease, year=year, rows=len_after, dropped_rows=len_before - len_after)
    
    return parquet
