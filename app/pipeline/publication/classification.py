from __future__ import annotations

import pandas as pd
from sqlalchemy.engine import Connection

from .helpers import _SENTINELAS, upsert


def upsert_dim_classificacao(conn: Connection, fact_df: pd.DataFrame) -> None:
    codigos = [c for c in fact_df["cd_classificacao"].unique() if c not in _SENTINELAS]
    rows = [{"codigo": c, "descricao": f"Código {c} (ver dicionário SINAN)"} for c in codigos]
    upsert(conn, "analytics.dim_classificacao", rows, conflict_cols=["codigo"])


def upsert_dim_evolucao(conn: Connection, fact_df: pd.DataFrame) -> None:
    codigos = [c for c in fact_df["cd_evolucao"].unique() if c not in _SENTINELAS]
    rows = [{"codigo": c, "descricao": f"Código {c} (ver dicionário SINAN)"} for c in codigos]
    upsert(conn, "analytics.dim_evolucao", rows, conflict_cols=["codigo"])
