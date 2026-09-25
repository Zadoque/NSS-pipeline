from __future__ import annotations

import pandas as pd

from app.pipeline.load import (
    CODIGO_NAO_INFORMADO,
    UNIDADE_NAO_IDENTIFICADA,
    _clean_code_series,
    _prepare_fact_frame,
)


def test_clean_code_series_trata_string_vazia_como_ausente():
    # Regressão: o SINAN grava campo ausente como "" literal, não NaN —
    # um .fillna() sozinho não pega esse caso (bug real já visto em
    # produção, ver ForeignKeyViolation de cd_classificacao='').
    serie = pd.Series(["10", "", None, "8"])
    result = _clean_code_series(serie, default="NI")
    assert list(result) == ["10", "NI", "NI", "8"]


def _gold_minima(**overrides) -> pd.DataFrame:
    base = {
        "year": [2026],
        "month": [1],
        "cd_mun": ["3301009"],
        "nm_mun": ["Campos dos Goytacazes"],
        "cd_uf": ["33"],
        "nm_uf": ["Rio de Janeiro"],
        "cases_total": [5],
    }
    base.update(overrides)
    return pd.DataFrame(base)


def test_prepare_fact_frame_usa_sentinela_quando_dimensao_ausente():
    # Gold gerada sem unidade_notificacao/classificacao_final/evolucao
    # selecionadas — as três colunas de código devem cair no "não
    # informado" em vez de erro ou nulo.
    df = _gold_minima()
    fact_df = _prepare_fact_frame(df, disease_codigo="DENG", batch_id="20260101T000000Z")

    assert (fact_df["cd_unidade"] == UNIDADE_NAO_IDENTIFICADA).all()
    assert (fact_df["cd_classificacao"] == CODIGO_NAO_INFORMADO).all()
    assert (fact_df["cd_evolucao"] == CODIGO_NAO_INFORMADO).all()
    assert (fact_df["disease_codigo"] == "DENG").all()


def test_prepare_fact_frame_normaliza_string_vazia_quando_dimensao_presente():
    df = _gold_minima(ID_UNIDADE=["0729884"], CLASSI_FIN=[""], EVOLUCAO=["1"])
    fact_df = _prepare_fact_frame(df, disease_codigo="DENG", batch_id="20260101T000000Z")

    assert fact_df.loc[0, "cd_unidade"] == "0729884"
    assert fact_df.loc[0, "cd_classificacao"] == CODIGO_NAO_INFORMADO
    assert fact_df.loc[0, "cd_evolucao"] == "1"


def test_prepare_fact_frame_preserva_cases_total():
    df = _gold_minima(cases_total=[42])
    fact_df = _prepare_fact_frame(df, disease_codigo="DENG", batch_id="b")
    assert fact_df.loc[0, "cases_total"] == 42
