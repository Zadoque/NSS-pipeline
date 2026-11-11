"""Publica o snapshot Gold de esporotricose no PostgreSQL."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine


TABLE = "analytics_animal.fato_esporo"
LOAD_COLUMNS = [
    "data_notificacao",
    "especie_codigo",
    "sexo_codigo",
    "idade_faixa_codigo",
    "castrado_codigo",
]
INSERT_BATCH_SIZE = 5_000


def _read_and_validate_gold(source: Path) -> pd.DataFrame:
    frame = pd.read_parquet(source)
    missing = set(LOAD_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Colunas ausentes na Gold ESPORO: {sorted(missing)}")
    if frame.empty:
        raise ValueError("Gold ESPORO vazia; publicação do snapshot foi bloqueada")

    frame = frame[LOAD_COLUMNS].copy()
    frame["data_notificacao"] = pd.to_datetime(
        frame["data_notificacao"], errors="raise"
    ).dt.date

    code_rules = {
        "especie_codigo": {0, 1, 2},
        "idade_faixa_codigo": {0, 1, 2, 3, 4, 5},
        "castrado_codigo": {0, 1, 2},
    }
    for column, allowed in code_rules.items():
        if frame[column].isna().any() or not frame[column].isin(allowed).all():
            raise ValueError(f"Código inválido na coluna Gold {column!r}")

    if frame["sexo_codigo"].isna().any() or not frame["sexo_codigo"].isin(
        {"F", "M", "i"}
    ).all():
        raise ValueError("Código inválido na coluna Gold 'sexo_codigo'")

    return frame


def load_gold_to_postgres(
    source: Path, *, engine: Engine | None = None
) -> int:
    """Substitui atomicamente o snapshot histórico pela Gold informada."""
    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(f"Gold ESPORO não encontrada: {source}")

    frame = _read_and_validate_gold(source)
    if engine is None:
        from ..load import get_engine

        engine = get_engine()
    db_engine = engine
    columns_sql = ", ".join(LOAD_COLUMNS)
    values_sql = ", ".join(f":{column}" for column in LOAD_COLUMNS)
    insert = text(f"INSERT INTO {TABLE} ({columns_sql}) VALUES ({values_sql})")

    with db_engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(72419831)"))
        conn.execute(text(f"DELETE FROM {TABLE}"))

        normalized = frame.astype(object).where(pd.notna(frame), None)
        records = normalized.to_dict(orient="records")
        for start in range(0, len(records), INSERT_BATCH_SIZE):
            conn.execute(insert, records[start : start + INSERT_BATCH_SIZE])

        inserted = conn.execute(text(f"SELECT count(*) FROM {TABLE}")).scalar_one()
        if inserted != len(frame):
            raise RuntimeError(
                f"Reconciliação ESPORO falhou: Gold tem {len(frame)} linhas, "
                f"banco ficou com {inserted}"
            )

    return int(inserted)
