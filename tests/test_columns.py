from __future__ import annotations

import pytest

from app.pipeline.sinan.columns import (
    CATALOG,
    dedup_key_columns,
    present_keys,
    required_keys,
    resolve_dedup_strategy,
    validate_keys,
)
from app.pipeline.sinan.columns import (
    _clean_id,
    _clean_municip,
    _to_date,
    _zfill_unidade,
    _zfill_uf,
)
import pandas as pd


def test_required_keys_inclui_campos_obrigatorios():
    assert set(required_keys()) == {
        "data_notificacao",
        "municipio",
        "uf",
        "sexo",
        "ano_nascimento",
        "semana_notificacao",
    }


def test_validate_keys_aceita_chaves_conhecidas():
    assert validate_keys(["sexo", "evolucao"]) == ["sexo", "evolucao"]


def test_validate_keys_rejeita_chave_desconhecida():
    with pytest.raises(ValueError, match="Colunas desconhecidas"):
        validate_keys(["sexo", "campo_que_nao_existe"])


def test_validate_keys_aceita_none_como_lista_vazia():
    assert validate_keys(None) == []


def test_present_keys_so_retorna_o_que_existe_no_dataframe():
    disponiveis = {"DT_NOTIFIC", "ID_MUNICIP", "SG_UF_NOT"}
    chaves = present_keys(disponiveis)
    assert set(chaves) == {"data_notificacao", "municipio", "uf"}


def test_resolve_dedup_strategy_usa_chave_primaria_quando_disponivel():
    disponiveis = set(dedup_key_columns()) | {"DT_NOTIFIC", "ID_MUNICIP"}
    cols, usou_primaria = resolve_dedup_strategy(disponiveis)
    assert usou_primaria is True
    assert cols == dedup_key_columns()


def test_resolve_dedup_strategy_cai_no_fallback_sem_chave_primaria():
    # Simula um dataset SINAN antigo, sem NU_NOTIFIC (cenário real já visto
    # em execuções da pipeline — ver UserWarning em silver.transform()).
    disponiveis = {"DT_NOTIFIC", "ID_MUNICIP", "SG_UF_NOT", "SEM_NOT"}
    cols, usou_primaria = resolve_dedup_strategy(disponiveis)
    assert usou_primaria is False
    assert "NU_NOTIFIC" not in cols
    assert set(cols).issubset(disponiveis)


def test_catalog_nao_tem_chaves_duplicadas_por_source_column():
    # Duas chaves diferentes apontando pra mesma coluna SINAN seria um bug
    # silencioso (ex.: dois --columns diferentes fariam a mesma coisa).
    source_columns = [spec.source_column for spec in CATALOG.values()]
    assert len(source_columns) == len(set(source_columns))


def test_transformacoes_de_colunas_preservam_contratos_sinan():
    dates = _to_date(pd.Series(["20260110", "2026-02-03", "invalido"]))
    assert dates.iloc[0].year == 2026
    assert dates.iloc[1].year == 2026
    assert pd.isna(dates.iloc[2])
    pd.testing.assert_series_equal(
        _clean_municip(pd.Series(["330100.0", " 330240 ", None])),
        pd.Series(["330100", "330240", pd.NA], dtype="string"),
        check_names=False,
    )
    pd.testing.assert_series_equal(
        _zfill_uf(pd.Series([33, "7.0", None])),
        pd.Series(["33", "07", pd.NA], dtype="string"),
        check_names=False,
    )
    pd.testing.assert_series_equal(
        _zfill_unidade(pd.Series([729884, "12", None])),
        pd.Series(["0729884", "0000012", pd.NA], dtype="string"),
        check_names=False,
    )
    pd.testing.assert_series_equal(
        _clean_id(pd.Series(["123.0", " 4 ", None])),
        pd.Series(["123", " 4 ", pd.NA], dtype="string"),
        check_names=False,
    )


def test_validate_keys_copia_lista_e_preserva_ordem():
    selected = ["sexo", "evolucao"]

    result = validate_keys(selected)
    selected.append("idade_sinan")

    assert result == ["sexo", "evolucao"]
