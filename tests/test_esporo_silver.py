import json
from datetime import UTC, datetime

import pandas as pd
import pytest

from app.pipeline.esporo import silver


@pytest.mark.parametrize(
    "original,nome,numero,ano",
    [
        ("Mia (SES/30-2025)", "Mia", 30, 2025),
        ("SES 126/25", None, 126, 2025),
        ("COLIN ROBINSON (SES 08/2026)", "COLIN ROBINSON", 8, 2026),
        ("ses/02 - 2025", None, 2, 2025),
        ("Sans-SES/5-2025", "Sans", 5, 2025),
        ("Malu- SES/10-2025", "Malu", 10, 2025),
        ("Fiona (SES/39-2025", "Fiona", 39, 2025),
        ("IRELIA (SES116/25)", "IRELIA", 116, 2025),
        ("TOM TOM (SES/118)", "TOM TOM", 118, None),
        ("ses-ccz-61", None, 61, None),
        ("432/2025", None, 432, 2025),
        ("13//26", None, 13, 2026),
        ("417-26", None, 417, 2026),
        ("19", None, 19, None),
        ("0", None, None, None),
        ("  Félix   ", "Félix", None, None),
        ("Gato 2", "Gato 2", None, None),
        ("SES/abc", "SES/abc", None, None),
        ("", None, None, None),
        (None, None, None, None),
    ],
)
def test_separa_nome_preservando_original(original, nome, numero, ano):
    entrada = pd.DataFrame({"Nome do animal:": [original]}, index=[7])
    resultado = silver.tratamento_nome(entrada)

    pd.testing.assert_series_equal(resultado["Nome do animal:"], entrada["Nome do animal:"])
    pd.testing.assert_series_equal(
        resultado["nome_animal_original"], entrada["Nome do animal:"], check_names=False
    )
    for coluna, valor, tipo in (
        ("nome_animal", nome, "string"),
        ("numero_notificacao", numero, "Int64"),
        ("ano_notificacao_nome", ano, "Int64"),
    ):
        pd.testing.assert_series_equal(
            resultado[coluna], pd.Series([valor], index=[7], name=coluna, dtype=tipo)
        )
    assert entrada.columns.tolist() == ["Nome do animal:"]


@pytest.mark.parametrize(
    "valor,esperado",
    [
        ("  Gato   X (SES/1)", ("Gato X", 1, pd.NA)),
        ("F X(SES/2)", ("F X", 2, pd.NA)),
    ],
)
def test_separar_nome_preserva_normalizacao_e_caracteres_do_nome(valor, esperado):
    resultado = silver._separar_nome(valor)

    assert resultado[0] == esperado[0]
    assert resultado[1] == esperado[1]
    assert resultado[2] is esperado[2] or resultado[2] == esperado[2]


def test_separar_nome_preserva_notificacao_unica_e_ausencia_de_ano():
    nome, numero, ano = silver._separar_nome("SES/1")

    assert nome is pd.NA
    assert numero == 1
    assert ano is pd.NA


@pytest.mark.parametrize("vazio", [False, True])
def test_transform_file_grava_colunas_sem_perder_registros(tmp_path, monkeypatch, vazio):
    nomes = ["GARFIELD (SES 126/25)", "SHAYERA ( SES 126/25)"]
    entrada = pd.DataFrame({coluna: [None, None] for coluna in silver.SELECTED_COLUMNS})
    entrada["Nome do animal:"] = nomes
    if vazio:
        entrada = entrada.iloc[:0]
    origem = tmp_path / "bronze.parquet"
    entrada.to_parquet(origem, index=False)
    monkeypatch.setattr(silver, "BASE_DIR", tmp_path / "data")

    destino = silver.transform_file(origem, run_at=datetime(2026, 10, 27, tzinfo=UTC))
    resultado = pd.read_parquet(destino)
    metadata = json.loads(destino.with_name("metadata.json").read_text(encoding="utf-8"))

    assert len(resultado) == len(entrada) == metadata["rows"]
    assert metadata["columns"] == resultado.columns.tolist()
    assert resultado["numero_notificacao"].dtype == "Int64"
    assert resultado["ano_notificacao_nome"].dtype == "Int64"
    if not vazio:
        assert resultado["nome_animal"].tolist() == ["GARFIELD", "SHAYERA"]
        assert resultado["numero_notificacao"].tolist() == [126, 126]
        assert resultado["ano_notificacao_nome"].tolist() == [2025, 2025]
