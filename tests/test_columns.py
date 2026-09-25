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


def test_required_keys_inclui_campos_obrigatorios():
    assert set(required_keys()) == {"data_notificacao", "municipio", "uf"}


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
