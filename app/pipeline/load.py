from __future__ import annotations

import os
import re
from collections.abc import Sequence
from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import Connection, Engine

DISEASE_NAMES: dict[str, str] = {
    "DENG": "Dengue",
    "CHIK": "Chikungunya",
    "ZIKA": "Zika",
    "TUBE": "Tuberculose",
    "HANS": "Hanseníase",
    "HEPA": "Hepatites virais",
    "SIFA": "Sífilis adquirida",
    "SIFC": "Sífilis congênita",
    "LEPT": "Leptospirose",
    "MENI": "Meningite",
    "FMAC": "Febre maculosa",
}

UNIDADE_NAO_IDENTIFICADA = "0000000"
CODIGO_NAO_INFORMADO = "NI"

_SENTINELAS = {UNIDADE_NAO_IDENTIFICADA, CODIGO_NAO_INFORMADO}

FACT_KEY_COLUMNS = [
    "disease_codigo", "year", "month", "cd_mun", "cd_unidade",
    "cd_classificacao", "cd_evolucao", "cd_sexo", "semana_notif", "ano_nascimento",
    "age_band", "notification_district_id", "notification_neighborhood_id",
    "notification_territory_status",
]


def get_engine() -> Engine:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL não definida. Configure-a no .env "
            "(usado via env_file no docker-compose.yml)."
        )
    return create_engine(url)


def _upsert(conn: Connection, table: str, rows: list[dict], conflict_cols: list[str]) -> None:
    if not rows:
        return

    cols = list(rows[0].keys())
    placeholders = ", ".join(f":{c}" for c in cols)
    update_cols = [c for c in cols if c not in conflict_cols]

    if update_cols:
        set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
        conflict_clause = f"DO UPDATE SET {set_clause}"
    else:
        conflict_clause = "DO NOTHING"

    stmt = text(f"""
        INSERT INTO {table} ({", ".join(cols)})
        VALUES ({placeholders})
        ON CONFLICT ({", ".join(conflict_cols)})
        {conflict_clause}
    """)

    conn.execute(stmt, rows)


def _clean_code_series(series: pd.Series, default: str) -> pd.Series:
    return series.astype("string").str.strip().replace("", pd.NA).fillna(default)


def _integer_series(series: pd.Series, column: str, minimum: int, maximum: int) -> pd.Series:
    cleaned = series.astype("string").str.strip().replace("", pd.NA)
    try:
        numbers = pd.to_numeric(cleaned, errors="raise").fillna(0)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{column} contém valor não numérico") from exc
    if ((numbers % 1 != 0) | ~numbers.between(minimum, maximum)).any():
        raise ValueError(f"{column} contém inteiro fora da faixa permitida")
    return numbers.astype("int64")


def _prepare_fact_frame(gold_df: pd.DataFrame, disease_codigo: str, batch_id: str) -> pd.DataFrame:
    df = gold_df.copy()
    df["disease_codigo"] = disease_codigo
    df["batch_id"] = batch_id

    if "ID_UNIDADE" in df.columns:
        df["cd_unidade"] = _clean_code_series(df["ID_UNIDADE"], UNIDADE_NAO_IDENTIFICADA)
    else:
        df["cd_unidade"] = UNIDADE_NAO_IDENTIFICADA

    if "CLASSI_FIN" in df.columns:
        df["cd_classificacao"] = _clean_code_series(df["CLASSI_FIN"], CODIGO_NAO_INFORMADO)
    else:
        df["cd_classificacao"] = CODIGO_NAO_INFORMADO

    if "EVOLUCAO" in df.columns:
        df["cd_evolucao"] = _clean_code_series(df["EVOLUCAO"], CODIGO_NAO_INFORMADO)
    else:
        df["cd_evolucao"] = CODIGO_NAO_INFORMADO

    # Novas dimensões adicionadas em CANONICAL_GOLD_COLUMNS
    sex_column = "CS_SEXO" if "CS_SEXO" in df.columns else "sex"
    df["cd_sexo"] = _clean_code_series(df[sex_column], "I") if sex_column in df.columns else "I"
    week_column = "SEM_NOT" if "SEM_NOT" in df.columns else "not_week"
    df["semana_notif"] = (
        _integer_series(df[week_column], week_column, 0, 999953).astype("int32")
        if week_column in df.columns else 0
    )
    weeks = df["semana_notif"]
    if ((weeks != 0) & ((weeks < 100001) | ~(weeks % 100).between(1, 53))).any():
        raise ValueError("SEM_NOT deve usar AAAASS com semana entre 01 e 53, ou 0 para ausente")
    birth_column = "ANO_NASC" if "ANO_NASC" in df.columns else "birth_year"
    df["ano_nascimento"] = (
        _integer_series(df[birth_column], birth_column, 0, 9999).astype("int16")
        if birth_column in df.columns else 0
    )
    df["age_band"] = _clean_code_series(df.get("age_band", pd.Series(pd.NA, index=df.index)), "NI")
    df["notification_district_id"] = df.get("notification_district_id", pd.Series(pd.NA, index=df.index))
    df["notification_neighborhood_id"] = df.get("notification_neighborhood_id", pd.Series(pd.NA, index=df.index))
    df["notification_territory_status"] = _clean_code_series(
        df.get("notification_territory_status", pd.Series(pd.NA, index=df.index)),
        "UNMAPPED_NOTIFICATION_UNIT",
    )

    return df


def upsert_dim_doenca(conn: Connection, disease_codigo: str) -> None:
    nome = DISEASE_NAMES.get(disease_codigo, disease_codigo)
    _upsert(
        conn,
        "analytics.dim_doenca",
        [{"codigo": disease_codigo, "nome": nome}],
        conflict_cols=["codigo"],
    )


def upsert_dim_municipio(conn: Connection, fact_df: pd.DataFrame) -> None:
    required = {"cd_mun", "nm_mun", "cd_uf", "nm_uf"}
    if not required.issubset(fact_df.columns):
        return

    rows = (
        fact_df[["cd_mun", "nm_mun", "cd_uf", "nm_uf"]]
        .dropna(subset=["cd_mun"])
        .drop_duplicates(subset=["cd_mun"])
        .to_dict(orient="records")
    )
    _upsert(conn, "analytics.dim_municipio", rows, conflict_cols=["cd_mun"])


def upsert_dim_unidade_saude(conn: Connection, fact_df: pd.DataFrame) -> None:
    """Deriva as linhas de dim_unidade_saude a partir do MESMO cd_unidade
    já normalizado em fact_df — garante que todo código referenciado pelo
    fato exista na dimensão antes do INSERT do fato acontecer.

    O código sentinela (UNIDADE_NAO_IDENTIFICADA) é ignorado aqui: ele já
    foi seedado com descrição curada pela migration e não deve ser
    sobrescrito com nomes nulos.
    """
    # Nomes aqui devem bater EXATAMENTE com as colunas de
    # analytics.dim_unidade_saude (migration 0001) — "razao_social",
    # não "razao_social_unidade" (esse é o nome vindo do silver_cnes.py).
    #
    # cd_mun (FK para dim_municipio) NÃO é populado aqui de propósito:
    # o "codigo_municipio" retornado pela API do CNES tem 6 dígitos,
    # enquanto dim_municipio.cd_mun usa o padrão IBGE de 7 dígitos do
    # SINAN. Converter exigiria calcular o dígito verificador — não é
    # um simples zero à esquerda. Até isso ser implementado com cuidado,
    # cd_mun de dim_unidade_saude fica nulo (coluna é opcional no schema).
    source_to_db = {
        "nm_unidade": "nm_unidade",
        "razao_social_unidade": "razao_social",
        "tp_unidade": "tp_unidade",
    }
    present_source_cols = [c for c in source_to_db if c in fact_df.columns]

    subset = (
        fact_df[["cd_unidade", *present_source_cols]]
        .drop_duplicates(subset=["cd_unidade"])
        .copy()
        .rename(columns=source_to_db)
    )
    subset = subset[~subset["cd_unidade"].isin(_SENTINELAS)]

    db_cols = ["nm_unidade", "razao_social", "tp_unidade"]
    for col in db_cols:
        if col not in subset.columns:
            subset[col] = None

    rows = subset[["cd_unidade", *db_cols]].to_dict(orient="records")
    _upsert(conn, "analytics.dim_unidade_saude", rows, conflict_cols=["cd_unidade"])


def upsert_dim_classificacao(conn: Connection, fact_df: pd.DataFrame) -> None:
    codigos = [c for c in fact_df["cd_classificacao"].unique() if c not in _SENTINELAS]
    rows = [{"codigo": c, "descricao": f"Código {c} (ver dicionário SINAN)"} for c in codigos]
    _upsert(conn, "analytics.dim_classificacao", rows, conflict_cols=["codigo"])


def upsert_dim_evolucao(conn: Connection, fact_df: pd.DataFrame) -> None:
    codigos = [c for c in fact_df["cd_evolucao"].unique() if c not in _SENTINELAS]
    rows = [{"codigo": c, "descricao": f"Código {c} (ver dicionário SINAN)"} for c in codigos]
    _upsert(conn, "analytics.dim_evolucao", rows, conflict_cols=["codigo"])


def insert_fato_casos(conn: Connection, fact_df: pd.DataFrame) -> None:
    if fact_df.empty:
        return
    frame = fact_df[FACT_KEY_COLUMNS + ["cases_total", "batch_id"]].rename(
        columns={"year": "ano", "month": "mes"}
    )
    columns = list(frame.columns)
    conn.execute(text(
        f"INSERT INTO analytics.fato_casos ({', '.join(columns)}) "
        f"VALUES ({', '.join(':' + column for column in columns)})"
    ), frame.to_dict(orient="records"))


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


def _scope_statement(sql: str):
    return text(sql).bindparams(bindparam("municipios", expanding=True))


def load_gold_to_postgres(
    engine: Engine, gold_df: pd.DataFrame, disease_codigo: str, batch_id: str, *,
    year: int, municipios: Sequence[str], expected_cases_total: int,
    snapshot_complete: bool, source_extracted_at: datetime, allow_empty: bool = False,
) -> None:
    """Publica o snapshot completo somente no recorte declarado.

    snapshot_complete atesta a conclusão da ingestão, não a completude
    epidemiológica da fonte. expected_cases_total vem da Silver do recorte.
    """
    disease_codigo = disease_codigo.upper()
    fact_df, facts, scope = _validate_snapshot(
        gold_df, disease_codigo, batch_id, year=year, municipios=municipios,
        expected_cases_total=expected_cases_total, snapshot_complete=snapshot_complete,
        source_extracted_at=source_extracted_at, allow_empty=allow_empty,
    )
    params = {"disease": disease_codigo, "year": year, "municipios": scope}
    with engine.begin() as conn:
        # Serializa também recortes parcialmente sobrepostos da mesma doença/ano.
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                     {"key": f"nss:sinan:{disease_codigo}:{year}"})
        newest = conn.execute(_scope_statement("""
            SELECT max(source_extracted_at) FROM analytics.pipeline_publications
            WHERE disease_codigo = :disease AND ano = :year AND cd_mun IN :municipios
        """), params).scalar_one()
        if newest is not None and source_extracted_at < newest:
            raise ValueError("Snapshot antigo: já existe publicação mais recente no recorte")
        upsert_dim_doenca(conn, disease_codigo)
        upsert_dim_municipio(conn, fact_df)
        upsert_dim_unidade_saude(conn, fact_df)
        upsert_dim_classificacao(conn, fact_df)
        upsert_dim_evolucao(conn, fact_df)
        conn.execute(_scope_statement("""
            DELETE FROM analytics.fato_casos
            WHERE disease_codigo = :disease AND ano = :year AND cd_mun IN :municipios
        """), params)
        insert_fato_casos(conn, facts)
        published = conn.execute(_scope_statement("""
            SELECT count(*) AS groups_total, coalesce(sum(cases_total), 0) AS cases_total
            FROM analytics.fato_casos
            WHERE disease_codigo = :disease AND ano = :year AND cd_mun IN :municipios
        """), params).one()
        if published.groups_total != len(facts) or published.cases_total != expected_cases_total:
            raise RuntimeError("Totais publicados divergem do snapshot; transação revertida")
        totals = facts.groupby("cd_mun")["cases_total"].agg(["size", "sum"])
        rows = [{
            "disease_codigo": disease_codigo, "ano": year, "cd_mun": code,
            "batch_id": batch_id, "source_extracted_at": source_extracted_at,
            "published_at": datetime.now(UTC),
            "groups_total": int(totals.loc[code, "size"]) if code in totals.index else 0,
            "cases_total": int(totals.loc[code, "sum"]) if code in totals.index else 0,
        } for code in scope]
        _upsert(conn, "analytics.pipeline_publications", rows,
                conflict_cols=["disease_codigo", "ano", "cd_mun", "batch_id"])
