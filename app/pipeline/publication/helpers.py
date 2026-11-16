from __future__ import annotations

import os
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

UNIDADE_NAO_IDENTIFICADA = "0000000"
CODIGO_NAO_INFORMADO = "NI"
_SENTINELAS = {UNIDADE_NAO_IDENTIFICADA, CODIGO_NAO_INFORMADO}


def get_engine() -> Engine:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL não definida. Configure-a no .env (usado via env_file no docker-compose.yml).")
    return create_engine(url)


def upsert(conn: Connection, table: str, rows: list[dict], conflict_cols: list[str], *, preserve_existing_on_null: bool = False) -> None:
    if not rows:
        return
    cols = list(rows[0].keys())
    placeholders = ", ".join(f":{c}" for c in cols)
    update_cols = [c for c in cols if c not in conflict_cols]
    if update_cols:
        if preserve_existing_on_null:
            set_clause = ", ".join(f"{c} = COALESCE(EXCLUDED.{c}, {table}.{c})" for c in update_cols)
        else:
            set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
        conflict_clause = f"DO UPDATE SET {set_clause}"
    else:
        conflict_clause = "DO NOTHING"
    conn.execute(text(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) ON CONFLICT ({', '.join(conflict_cols)}) {conflict_clause}"), rows)


def insert_immutable(conn: Connection, table: str, rows: list[dict], conflict_cols: list[str]) -> None:
    if not rows:
        return
    cols = list(rows[0].keys())
    conn.execute(text(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(':' + col for col in cols)}) ON CONFLICT ({', '.join(conflict_cols)}) DO NOTHING"), rows)


def clean_code_series(series: pd.Series, default: str) -> pd.Series:
    return series.astype("string").str.strip().replace("", pd.NA).fillna(default)


def integer_series(series: pd.Series, column: str, minimum: int, maximum: int) -> pd.Series:
    cleaned = series.astype("string").str.strip().replace("", pd.NA)
    try:
        numbers = pd.to_numeric(cleaned, errors="raise").fillna(0)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{column} contém valor não numérico") from exc
    if ((numbers % 1 != 0) | ~numbers.between(minimum, maximum)).any():
        raise ValueError(f"{column} contém inteiro fora da faixa permitida")
    return numbers.astype("int64")


def normalize_sem_not(series: pd.Series, year: pd.Series | int) -> pd.Series:
    numbers = integer_series(series, "SEM_NOT", 0, 999953)
    years = pd.Series(year, index=series.index) if isinstance(year, int) else year
    integer_series(years, "year", 1, 9999)
    aass = numbers.between(1000, 9999) & numbers.mod(100).between(1, 53)
    normalized = numbers.copy()
    normalized.loc[aass] = (2000 + numbers.loc[aass] // 100) * 100 + numbers.loc[aass] % 100
    return normalized


def prepare_fact_frame(gold_df: pd.DataFrame, disease_codigo: str, batch_id: str) -> pd.DataFrame:
    df = gold_df.copy()
    df["disease_codigo"] = disease_codigo
    df["batch_id"] = batch_id
    df["cd_unidade"] = clean_code_series(df["ID_UNIDADE"], UNIDADE_NAO_IDENTIFICADA) if "ID_UNIDADE" in df else UNIDADE_NAO_IDENTIFICADA
    df["cd_classificacao"] = clean_code_series(df["CLASSI_FIN"], CODIGO_NAO_INFORMADO) if "CLASSI_FIN" in df else CODIGO_NAO_INFORMADO
    df["cd_evolucao"] = clean_code_series(df["EVOLUCAO"], CODIGO_NAO_INFORMADO) if "EVOLUCAO" in df else CODIGO_NAO_INFORMADO
    sex_column = "CS_SEXO" if "CS_SEXO" in df else "sex"
    df["cd_sexo"] = clean_code_series(df[sex_column], "I") if sex_column in df else "I"
    week_column = "not_week" if "not_week" in df else "SEM_NOT"
    df["semana_notif"] = normalize_sem_not(df[week_column], df["year"]).astype("int32") if week_column in df else 0
    if ((df["semana_notif"] != 0) & ((df["semana_notif"] < 100001) | ~(df["semana_notif"] % 100).between(1, 53))).any():
        raise ValueError("SEM_NOT deve usar AAAASS com semana entre 01 e 53, ou 0 para ausente")
    birth_column = "ANO_NASC" if "ANO_NASC" in df else "birth_year"
    df["ano_nascimento"] = integer_series(df[birth_column], birth_column, 0, 9999).astype("int16") if birth_column in df else 0
    df["age_band"] = clean_code_series(df.get("age_band", pd.Series(pd.NA, index=df.index)), "NI")
    df["notification_district_id"] = df.get("notification_district_id", pd.Series(pd.NA, index=df.index))
    df["notification_neighborhood_id"] = df.get("notification_neighborhood_id", pd.Series(pd.NA, index=df.index))
    df["notification_territory_status"] = clean_code_series(df.get("notification_territory_status", pd.Series(pd.NA, index=df.index)), "UNMAPPED_NOTIFICATION_UNIT")
    return df
