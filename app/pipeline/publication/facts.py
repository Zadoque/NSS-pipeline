from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

from ..scope import scope_sha256
from .dimensions import FACT_INSERT_BATCH_SIZE
from .helpers import integer_series, prepare_fact_frame, upsert

_integer_series = integer_series
_prepare_fact_frame = prepare_fact_frame
_upsert = upsert

FACT_KEY_COLUMNS = [
    "disease_codigo", "year", "month", "cd_mun", "cd_unidade",
    "cd_classificacao", "cd_evolucao", "cd_sexo", "semana_notif", "ano_nascimento",
    "age_band", "notification_district_id", "notification_neighborhood_id",
    "notification_territory_status",
]

def insert_fato_casos(conn: Connection, fact_df: pd.DataFrame) -> None:
    if fact_df.empty:
        return
    frame = fact_df[FACT_KEY_COLUMNS + ["cases_total", "batch_id"]].rename(
        columns={"year": "ano", "month": "mes"}
    )
    columns = list(frame.columns)
    if len(frame) > FACT_INSERT_BATCH_SIZE:
        raw = conn.connection.driver_connection
        from psycopg2.extensions import connection as PsycopgConnection
        if isinstance(raw, PsycopgConnection):
            from psycopg2.extras import execute_values

            statement = (
                f"INSERT INTO analytics.fato_casos ({', '.join(columns)}) VALUES %s"
            )
            values = frame.astype(object).where(pd.notna(frame), None)
            with raw.cursor() as cursor:
                execute_values(
                    cursor,
                    statement,
                    values.itertuples(index=False, name=None),
                    page_size=FACT_INSERT_BATCH_SIZE,
                )
            return
    statement = text(
        f"INSERT INTO analytics.fato_casos ({', '.join(columns)}) "
        f"VALUES ({', '.join(':' + column for column in columns)})"
    )
    for start in range(0, len(frame), FACT_INSERT_BATCH_SIZE):
        batch = frame.iloc[start:start + FACT_INSERT_BATCH_SIZE]
        conn.execute(statement, batch.to_dict(orient="records"))


def _validate_snapshot(
    gold_df: pd.DataFrame, disease_codigo: str, batch_id: str, *, year: int,
    municipios: Sequence[str], expected_cases_total: int, snapshot_complete: bool,
    source_extracted_at: datetime, allow_empty: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Valida antes de abrir a transação e agrega no grão final normalizado."""
    if snapshot_complete is not True:
        raise ValueError("Snapshot incompleto: publicação bloqueada")
    if not re.fullmatch(r"[A-Z0-9]{1,4}", disease_codigo):
        raise ValueError("Código de doença inválido")
    if not isinstance(year, int) or isinstance(year, bool) or not 1000 <= year <= 9999:
        raise ValueError("Ano do recorte inválido")
    if not batch_id or len(batch_id) > 20:
        raise ValueError("batch_id deve ter entre 1 e 20 caracteres")
    if not isinstance(source_extracted_at, datetime) or source_extracted_at.tzinfo is None or source_extracted_at.utcoffset() is None:
        raise ValueError("source_extracted_at precisa incluir fuso horário")
    if isinstance(municipios, str):
        raise ValueError("Municípios devem ser uma sequência de códigos")
    scope = list(municipios)
    if not scope or any(not isinstance(code, str) or not re.fullmatch(r"\d{7}", code) for code in scope):
        raise ValueError("Recorte deve declarar municípios com códigos de 7 dígitos")
    scope = sorted(set(scope))
    if not isinstance(expected_cases_total, int) or isinstance(expected_cases_total, bool) or expected_cases_total < 0:
        raise ValueError("Total esperado de notificações inválido")
    required = {"year", "month", "cd_mun", "nm_mun", "cd_uf", "nm_uf", "cases_total"}
    missing = required - set(gold_df.columns)
    if missing:
        raise ValueError(f"Colunas Gold obrigatórias ausentes: {sorted(missing)}")
    if gold_df.empty and not allow_empty:
        raise ValueError("Gold vazia: use allow_empty somente para um zero validado na origem")
    if "disease" in gold_df.columns and not gold_df["disease"].eq(disease_codigo).all():
        raise ValueError("Gold contém doença diferente do recorte")
    if not gold_df["year"].eq(year).all() or not gold_df["cd_mun"].isin(scope).all():
        raise ValueError("Gold contém ano ou município fora do recorte")
    if gold_df[list(required)].isna().any().any():
        raise ValueError("Gold contém valores obrigatórios nulos")
    # A Gold deve ser única no grão original. Ausências distintas só serão
    # reunidas depois da normalização; duplicatas da Gold não são somadas.
    original_keys = ["year", "month", "cd_mun", "cd_uf"]
    for primary, alias in [("CS_SEXO", "sex"), ("SEM_NOT", "not_week"), ("ANO_NASC", "birth_year")]:
        if primary in gold_df.columns or alias in gold_df.columns:
            original_keys.append(primary if primary in gold_df.columns else alias)
    original_keys += [c for c in ["ID_UNIDADE", "CLASSI_FIN", "EVOLUCAO", "age_band", "notification_district_id", "notification_neighborhood_id", "notification_territory_status"] if c in gold_df.columns]
    if gold_df.duplicated(subset=original_keys).any():
        raise ValueError("Gold possui chave de agregação duplicada")
    fact_df = _prepare_fact_frame(gold_df, disease_codigo, batch_id)
    fact_df["month"] = _integer_series(fact_df["month"], "month", 1, 12)
    fact_df["cases_total"] = _integer_series(fact_df["cases_total"], "cases_total", 1, 2147483647)
    for column, pattern in [("cd_unidade", r"\d{7}"), ("cd_uf", r"\d{2}"),
                            ("cd_classificacao", r"[A-Za-z0-9]{1,2}"), ("cd_evolucao", r"[A-Za-z0-9]{1,2}"),
                            ("cd_sexo", r"[MFI]")]:
        if not fact_df[column].astype("string").str.fullmatch(pattern).fillna(False).all():
            raise ValueError(f"{column} contém código inválido")
    if int(fact_df["cases_total"].sum()) != expected_cases_total:
        raise ValueError("Total da Gold diverge das notificações Silver no recorte")
    facts = fact_df.groupby(FACT_KEY_COLUMNS, dropna=False, sort=True)["cases_total"].sum().reset_index()
    if (facts["cases_total"] > 2147483647).any():
        raise ValueError("Contagem agregada excede a capacidade do banco")
    facts["batch_id"] = batch_id
    return fact_df, facts, scope


def _metadata_snapshot(
    fact_df: pd.DataFrame, *, disease_codigo: str, year: int, batch_id: str,
    source_extracted_at: datetime, published_at: datetime,
) -> dict:
    """Deriva o catálogo do mesmo DataFrame Gold já validado para publicação."""
    months = sorted({int(month) for month in fact_df["month"].tolist()})
    status = fact_df["notification_territory_status"].astype("string").fillna(
        "UNMAPPED_NOTIFICATION_UNIT"
    )
    municipality_only = bool(
        fact_df.empty
        or status.isin({"UNMAPPED_NOTIFICATION_UNIT", "UNAVAILABLE"}).all()
    )
    return {
        "disease_codigo": disease_codigo,
        "ano": year,
        "batch_id": batch_id,
        "available_months": months,
        "municipality_only": municipality_only,
        "source_extracted_at": source_extracted_at,
        "published_at": published_at,
    }


def _scope_statement(sql: str):
    return text(sql).bindparams(bindparam("municipios", expanding=True))


def _expanding_statement(sql: str, parameter: str):
    return text(sql).bindparams(bindparam(parameter, expanding=True))


def _register_catalog_release(conn: Connection, catalog) -> None:
    if catalog is None:
        return
    metadata = catalog.metadata
    if metadata.validation_status != "VALIDATED":
        raise ValueError("release IBGE não validada não pode ser publicada")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", metadata.sha256):
        raise ValueError("release IBGE sem SHA-256 válido não pode ser publicada")
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {
        "key": f"nss:ibge-release:{metadata.catalog_id}",
    })
    existing = conn.execute(text("""
        SELECT sha256, content_sha256
        FROM analytics.reference_catalog_releases
        WHERE catalog_id = :catalog_id
        FOR UPDATE
    """), {"catalog_id": metadata.catalog_id}).one_or_none()
    if existing is not None:
        if existing.sha256 != metadata.sha256 or existing.content_sha256 != metadata.content_sha256:
            raise ValueError(
                "catalog_id IBGE imutável já associado a outro SHA-256"
            )
        return
    conn.execute(text("""
        INSERT INTO analytics.reference_catalog_releases
            (catalog_id, sha256, content_sha256, reference_year, source_name, source_url, retrieved_at)
        VALUES (:catalog_id, :sha256, :content_sha256, :reference_year, :source_name, :source_url, :retrieved_at)
    """), {
        "catalog_id": metadata.catalog_id,
        "sha256": metadata.sha256,
        "content_sha256": metadata.content_sha256,
        "reference_year": metadata.reference_year,
        "source_name": metadata.source_name,
        "source_url": metadata.source_url,
        "retrieved_at": metadata.retrieved_at,
    })



