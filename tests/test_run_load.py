from pathlib import Path

import pandas as pd
import pytest

from app.pipeline import run_load as runner
from app.pipeline.sinan.gold import MUNICIPIOS_RJ


@pytest.fixture
def pipeline(mocker):
    mocker.patch.object(runner, "fetch_sinan", return_value=pd.DataFrame({"row": [1]}))
    mocker.patch.object(runner, "write_bronze", return_value=Path("bronze.parquet"))
    mocker.patch.object(runner, "transform_file", return_value=Path("silver.parquet"))
    aggregate = mocker.patch.object(runner, "aggregate_file", return_value=Path("gold.parquet"))
    engine = mocker.Mock()
    get_engine = mocker.patch.object(runner, "get_engine", return_value=engine)
    load = mocker.patch.object(runner, "load_gold_to_postgres")
    return aggregate, engine, get_engine, load


def test_orquestrador_declara_recorte_e_total_independente_da_gold(mocker, pipeline):
    aggregate, engine, _, load = pipeline
    # O total esperado vem das notificações Silver, incluindo apenas o recorte.
    silver = pd.DataFrame({"ID_MUNICIP": ["3301009", "3301009", "3302403", "9999999"]})
    gold = pd.DataFrame({"cases_total": [3]})
    mocker.patch.object(runner.pd, "read_parquet", side_effect=[silver, gold])
    runner.run_load("deng", 2026)
    options = load.call_args.kwargs
    assert options["expected_cases_total"] == 3
    assert options["municipios"] == list(MUNICIPIOS_RJ)
    assert options["year"] == 2026
    assert options["snapshot_complete"] is True
    assert options["allow_empty"] is False
    assert options["source_extracted_at"] == aggregate.call_args.kwargs["run_at"]
    assert aggregate.call_args.kwargs["municipios"] == MUNICIPIOS_RJ
    engine.dispose.assert_called_once()


def test_silver_vazia_nao_publica_mesmo_com_allow_empty(mocker, pipeline):
    aggregate, _, get_engine, load = pipeline
    mocker.patch.object(runner.pd, "read_parquet", return_value=pd.DataFrame(columns=["ID_MUNICIP"]))
    with pytest.raises(RuntimeError, match="Silver sem notificações válidas"):
        runner.run_load("DENG", 2026, allow_empty=True)
    aggregate.assert_not_called()
    get_engine.assert_not_called()
    load.assert_not_called()


def test_falha_de_ingestao_nao_abre_carga(pipeline, mocker):
    _, _, get_engine, load = pipeline
    mocker.patch.object(runner, "fetch_sinan", side_effect=RuntimeError("fonte indisponível"))
    with pytest.raises(RuntimeError, match="fonte indisponível"):
        runner.run_load("DENG", 2026)
    get_engine.assert_not_called()
    load.assert_not_called()


def test_publicacao_vazia_explicita_e_falha_liberam_conexao(mocker, pipeline):
    _, engine, _, load = pipeline
    silver = pd.DataFrame({"ID_MUNICIP": ["9999999"]})
    mocker.patch.object(runner.pd, "read_parquet", side_effect=[silver, pd.DataFrame()])
    load.side_effect = ValueError("publicação rejeitada")
    with pytest.raises(ValueError, match="publicação rejeitada"):
        runner.run_load("DENG", 2026, allow_empty=True)
    assert load.call_args.kwargs["expected_cases_total"] == 0
    assert load.call_args.kwargs["allow_empty"] is True
    engine.dispose.assert_called_once()
