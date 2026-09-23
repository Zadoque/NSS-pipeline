from __future__ import annotations

import os

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

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


def get_engine() -> Engine:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL não definida. Configure-a no .env "
            "(usado via env_file no docker-compose.yml)."
        )
    return create_engine(url)


def _upsert(engine: Engine, table: str, rows: list[dict], conflict_cols: list[str]) -> None:
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

    with engine.begin() as conn:
        conn.execute(stmt, rows)


def _clean_code_series(series: pd.Series, default: str) -> pd.Series:
    return series.astype("string").replace("", pd.NA).fillna(default)


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

    return df


def upsert_dim_doenca(engine: Engine, disease_codigo: str) -> None:
    nome = DISEASE_NAMES.get(disease_codigo, disease_codigo)
    _upsert(
        engine,
        "analytics.dim_doenca",
        [{"codigo": disease_codigo, "nome": nome}],
        conflict_cols=["codigo"],
    )


def upsert_dim_municipio(engine: Engine, fact_df: pd.DataFrame) -> None:
    required = {"cd_mun", "nm_mun", "cd_uf", "nm_uf"}
    if not required.issubset(fact_df.columns):
        return

    rows = (
        fact_df[["cd_mun", "nm_mun", "cd_uf", "nm_uf"]]
        .dropna(subset=["cd_mun"])
        .drop_duplicates(subset=["cd_mun"])
        .to_dict(orient="records")
    )
    _upsert(engine, "analytics.dim_municipio", rows, conflict_cols=["cd_mun"])


def upsert_dim_unidade_saude(engine: Engine, fact_df: pd.DataFrame) -> None:
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
    _upsert(engine, "analytics.dim_unidade_saude", rows, conflict_cols=["cd_unidade"])


def upsert_dim_classificacao(engine: Engine, fact_df: pd.DataFrame) -> None:
    codigos = [c for c in fact_df["cd_classificacao"].unique() if c not in _SENTINELAS]
    rows = [{"codigo": c, "descricao": f"Código {c} (ver dicionário SINAN)"} for c in codigos]
    _upsert(engine, "analytics.dim_classificacao", rows, conflict_cols=["codigo"])


def upsert_dim_evolucao(engine: Engine, fact_df: pd.DataFrame) -> None:
    codigos = [c for c in fact_df["cd_evolucao"].unique() if c not in _SENTINELAS]
    rows = [{"codigo": c, "descricao": f"Código {c} (ver dicionário SINAN)"} for c in codigos]
    _upsert(engine, "analytics.dim_evolucao", rows, conflict_cols=["codigo"])


def upsert_fato_casos(engine: Engine, fact_df: pd.DataFrame) -> None:
    rows = fact_df[
        [
            "disease_codigo",
            "year",
            "month",
            "cd_mun",
            "cd_unidade",
            "cd_classificacao",
            "cd_evolucao",
            "cases_total",
            "batch_id",
        ]
    ].rename(columns={"year": "ano", "month": "mes"}).to_dict(orient="records")

    _upsert(
        engine,
        "analytics.fato_casos",
        rows,
        conflict_cols=[
            "disease_codigo",
            "ano",
            "mes",
            "cd_mun",
            "cd_unidade",
            "cd_classificacao",
            "cd_evolucao",
        ],
    )


def load_gold_to_postgres(
    engine: Engine, gold_df: pd.DataFrame, disease_codigo: str, batch_id: str
) -> None:
    """Ordem importa: dimensões antes do fato (FKs). Todas as dimensões
    derivam do mesmo fact_df normalizado, nunca da Gold crua — ver
    _prepare_fact_frame().
    """
    if gold_df.empty:
        return

    fact_df = _prepare_fact_frame(gold_df, disease_codigo, batch_id)

    upsert_dim_doenca(engine, disease_codigo)
    upsert_dim_municipio(engine, fact_df)
    upsert_dim_unidade_saude(engine, fact_df)
    upsert_dim_classificacao(engine, fact_df)
    upsert_dim_evolucao(engine, fact_df)
    upsert_fato_casos(engine, fact_df)