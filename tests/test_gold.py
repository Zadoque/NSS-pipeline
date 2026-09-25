from __future__ import annotations

import pandas as pd
import pytest

from app.pipeline.sinan.gold import aggregate

MUNICIPIOS_TESTE = {"1234567": "Cidade Teste"}


def _silver_minima(**overrides) -> pd.DataFrame:
    base = {
        "DT_NOTIFIC": pd.to_datetime(["2026-01-05", "2026-01-20", "2026-02-01"]),
        "ID_MUNICIP": ["1234567", "1234567", "9999999"],  # a última fica fora do recorte
        "SG_UF_NOT": ["33", "33", "33"],
        "NM_UF": ["Rio de Janeiro", "Rio de Janeiro", "Rio de Janeiro"],
        "CS_SEXO": ["F", "M", "F"],
    }
    base.update(overrides)
    return pd.DataFrame(base)


def test_aggregate_levanta_erro_quando_falta_coluna_obrigatoria():
    df = _silver_minima().drop(columns=["NM_UF"])
    with pytest.raises(ValueError, match="Colunas Silver ausentes"):
        aggregate(df, disease="DENG", municipios=MUNICIPIOS_TESTE)


def test_aggregate_retorna_vazio_quando_nenhum_municipio_bate():
    df = _silver_minima(ID_MUNICIP=["9999999", "9999999", "9999999"])
    result = aggregate(df, disease="DENG", municipios=MUNICIPIOS_TESTE)
    assert result.empty
    assert "cases_total" in result.columns
    assert "disease" in result.columns


def test_aggregate_soma_casos_por_mes_e_municipio():
    df = _silver_minima()
    result = aggregate(df, disease="DENG", municipios=MUNICIPIOS_TESTE)

    # As duas primeiras linhas (município 1234567, ambas em janeiro/2026)
    # devem virar uma linha só com cases_total = 2. A terceira linha, de
    # município fora do recorte, não aparece.
    assert len(result) == 1
    row = result.iloc[0]
    assert row["cases_total"] == 2
    assert row["year"] == 2026
    assert row["month"] == 1
    assert row["cd_mun"] == "1234567"


def test_aggregate_inclui_disease_como_primeira_coluna():
    df = _silver_minima()
    result = aggregate(df, disease="deng", municipios=MUNICIPIOS_TESTE)
    assert result.columns[0] == "disease"
    assert (result["disease"] == "DENG").all()  # sempre maiúsculo


def test_aggregate_com_dimensao_extra_abre_grupos_por_sexo():
    df = _silver_minima()
    result = aggregate(
        df, disease="DENG", selected_columns=["sexo"], municipios=MUNICIPIOS_TESTE
    )
    # Janeiro/2026 tem uma notificação CS_SEXO=F e outra CS_SEXO=M —
    # com a dimensão extra, isso vira duas linhas em vez de uma.
    assert len(result) == 2
    assert "CS_SEXO" in result.columns
    assert set(result["CS_SEXO"]) == {"F", "M"}
