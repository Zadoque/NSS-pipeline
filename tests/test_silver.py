from __future__ import annotations

import pandas as pd
import pytest

from app.pipeline.sinan.silver import transform


def _sinan_bruto(**overrides) -> pd.DataFrame:
    """DataFrame mínimo no formato cru do SINAN, com valores padrão
    sobrescrevíveis via overrides (cada chave é uma coluna -> lista de
    valores)."""
    base = {
        "DT_NOTIFIC": ["20260110", "20260215", "20250101"],
        "ID_MUNICIP": ["3301009", "3301009", "3301009"],
        "SG_UF_NOT": ["33", "33", "33"],
        "NU_NOTIFIC": ["1", "2", "3"],
        "SEM_NOT": ["202602", "202607", "202501"],
        "NU_ANO": [2026, 2026, 2025],
        "CLASSI_FIN": ["10", "10", "10"],
        "EVOLUCAO": ["1", "1", "1"],
        "CS_SEXO": ["F", "M", "F"],
        "ANO_NASC": [1990, 1985, 2000],
    }
    base.update(overrides)
    return pd.DataFrame(base)


def test_transform_filtra_pelo_ano_de_notificacao():
    df = _sinan_bruto()
    result = transform(df, year=2026)
    # Só as duas primeiras linhas são de 2026; a terceira (2025) é descartada.
    assert len(result) == 2
    assert (result["DT_NOTIFIC"].dt.year == 2026).all()


def test_transform_levanta_erro_quando_falta_coluna_obrigatoria():
    df = _sinan_bruto().drop(columns=["ID_MUNICIP"])
    with pytest.raises(ValueError, match="Colunas obrigatórias"):
        transform(df, year=2026)


def test_transform_dedup_usa_nu_notific_quando_presente(recwarn):
    df = _sinan_bruto()
    transform(df, year=2026)
    # Não deve emitir o warning de fallback quando NU_NOTIFIC existe.
    avisos = [w for w in recwarn.list if issubclass(w.category, UserWarning)]
    assert not avisos


def test_transform_avisa_quando_cai_no_fallback_de_dedup():
    df = _sinan_bruto().drop(columns=["NU_NOTIFIC"])
    with pytest.warns(UserWarning, match="Chave de negócio"):
        transform(df, year=2026)


def test_transform_remove_duplicata_exata_no_fallback():
    df = _sinan_bruto().drop(columns=["NU_NOTIFIC"])
    # Duplica a primeira linha inteira — deve virar uma linha só após dedup.
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    with pytest.warns(UserWarning):
        result = transform(df, year=2026)
    assert len(result) == 2  # as duas linhas de 2026 originais, sem a duplicata
