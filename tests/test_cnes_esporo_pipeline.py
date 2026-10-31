import json
from datetime import UTC, datetime

import pandas as pd
import pytest

from app.pipeline.cnes import bronze as cnes_bronze
from app.pipeline.cnes import silver as cnes_silver
from app.pipeline.esporo import bronze as esporo_bronze
from app.pipeline.esporo import run as esporo_run


def test_transform_cnes_normalizes_codes_and_keeps_last_duplicate():
    source = pd.DataFrame(
        {
            "codigo_cnes": [12, 12],
            "nome_fantasia": ["antigo", "atual"],
            "codigo_municipio": [3301009, 3301009],
            "codigo_tipo_unidade": [1, 2],
            "campo_ignorado": ["x", "y"],
        }
    )

    result = cnes_silver.transform_cnes(source)

    assert result.to_dict("records") == [
        {
            "cd_unidade": "0000012",
            "nm_unidade": "atual",
            "codigo_municipio": "3301009",
            "tp_unidade": 2,
        }
    ]


def test_transform_cnes_resolves_canonical_municipality_with_catalog():
    from app.pipeline.reference.ibge.catalog import InMemoryMunicipalityCatalog
    from app.pipeline.reference.ibge.models import CatalogMetadata, Municipality

    catalog = InMemoryMunicipalityCatalog(
        [Municipality("3301009", "330100", "Campos", "33", "RJ", "Rio", 2025)],
        CatalogMetadata("test", 2025, "fixture", "fixture://", "2026-01-01T00:00:00Z", "hash"),
    )
    result = cnes_silver.transform_cnes(
        pd.DataFrame({"codigo_cnes": [12], "codigo_municipio": ["330100"]}),
        catalog=catalog,
    )
    assert result.loc[0, "cd_mun"] == "3301009"
    assert result.loc[0, "municipality_resolution_status"] == "VALID"


def test_fetch_estabelecimentos_rejeita_limit_invalido(monkeypatch):
    with pytest.raises(ValueError, match="maior que zero"):
        cnes_bronze.fetch_estabelecimentos("3301009", limit=0)


def test_fetch_estabelecimentos_rejeita_timeout_invalido():
    with pytest.raises(ValueError, match="timeout CNES"):
        cnes_bronze.fetch_estabelecimentos("3301009", timeout=0)


def test_transform_cnes_file_publishes_metadata(tmp_path, monkeypatch):
    source = tmp_path / "bronze.parquet"
    pd.DataFrame({"codigo_cnes": [12], "codigo_municipio": [3301009]}).to_parquet(
        source, index=False
    )
    monkeypatch.setattr(cnes_silver, "BASE_DIR", tmp_path / "data")

    result = cnes_silver.transform_cnes_file(
        source, "3301009", run_at=datetime(2026, 10, 29, tzinfo=UTC)
    )

    metadata = json.loads(result.with_name("metadata.json").read_text(encoding="utf-8"))
    assert result.exists()
    assert metadata["rows"] == 1
    assert metadata["dropped_rows"] == 0


def test_fetch_estabelecimentos_paginates_until_empty(mocker):
    responses = [
        mocker.Mock(json=lambda: {"estabelecimentos": [{"id": 1}]}),
        mocker.Mock(json=lambda: {"estabelecimentos": [{"id": 2}]}),
        mocker.Mock(json=lambda: {"estabelecimentos": []}),
    ]
    for response in responses:
        response.raise_for_status = mocker.Mock()
    session = mocker.Mock()
    session.get.side_effect = responses
    mocker.patch.object(cnes_bronze, "_session_with_retries", return_value=session)

    result = cnes_bronze.fetch_estabelecimentos("3301009", limit=1)

    assert result.to_dict("records") == [{"id": 1}, {"id": 2}]
    assert [call.kwargs["params"]["offset"] for call in session.get.call_args_list] == [0, 1, 2]
    assert all(call.kwargs["timeout"] == 60 for call in session.get.call_args_list)


def test_fetch_estabelecimentos_respeita_teto_da_api_sem_pular_registros(mocker):
    responses = [
        mocker.Mock(json=lambda: {"estabelecimentos": [{"id": value} for value in range(20)]}),
        mocker.Mock(json=lambda: {"estabelecimentos": [{"id": 20}]}),
        mocker.Mock(json=lambda: {"estabelecimentos": []}),
    ]
    for response in responses:
        response.raise_for_status = mocker.Mock()
    session = mocker.Mock()
    session.get.side_effect = responses
    mocker.patch.object(cnes_bronze, "_session_with_retries", return_value=session)

    result = cnes_bronze.fetch_estabelecimentos("3301009", limit=250)

    assert result["id"].tolist() == list(range(21))
    assert [call.kwargs["params"]["offset"] for call in session.get.call_args_list] == [0, 20, 21]


@pytest.mark.parametrize(
    "payload, message",
    [
        ([], "JSON deve ser um objeto"),
        ({}, "estabelecimentos deve ser uma lista"),
        ({"estabelecimentos": ["não é registro"]}, "cada estabelecimento deve ser um objeto"),
    ],
)
def test_fetch_estabelecimentos_rejeita_schema_de_resposta_invalido(mocker, payload, message):
    response = mocker.Mock(json=lambda: payload)
    response.raise_for_status = mocker.Mock()
    session = mocker.Mock()
    session.get.return_value = response

    with pytest.raises(ValueError, match=message):
        cnes_bronze.fetch_estabelecimentos("3301009", session=session)

    response.raise_for_status.assert_called_once_with()


def test_fetch_estabelecimentos_interrompe_pagina_repetida(mocker):
    page = {"estabelecimentos": [{"id": 1}]}
    responses = [mocker.Mock(json=lambda: page), mocker.Mock(json=lambda: page)]
    for response in responses:
        response.raise_for_status = mocker.Mock()
    session = mocker.Mock()
    session.get.side_effect = responses

    with pytest.raises(RuntimeError, match="repetiu uma página"):
        cnes_bronze.fetch_estabelecimentos("3301009", session=session)

    assert session.get.call_count == 2


def test_fetch_estabelecimentos_uses_validated_catalog_crosswalk(mocker):
    from app.pipeline.reference.ibge.catalog import InMemoryMunicipalityCatalog
    from app.pipeline.reference.ibge.models import CatalogMetadata, Municipality

    catalog = InMemoryMunicipalityCatalog(
        [Municipality("3301009", "330100", "Campos", "33", "RJ", "Rio", 2025)],
        CatalogMetadata("test", 2025, "fixture", "fixture://", "2026-01-01T00:00:00Z", "hash"),
    )
    response = mocker.Mock()
    response.json.return_value = {"estabelecimentos": []}
    response.raise_for_status = mocker.Mock()
    session = mocker.Mock()
    session.get.return_value = response
    mocker.patch.object(cnes_bronze, "_session_with_retries", return_value=session)

    cnes_bronze.fetch_estabelecimentos("3301009", catalog=catalog)

    assert session.get.call_args.kwargs["params"]["codigo_municipio"] == "330100"


def test_esporo_run_passes_same_run_timestamp_to_silver(mocker, tmp_path):
    bronze = tmp_path / "bronze.parquet"
    silver = tmp_path / "silver.parquet"
    mocker.patch.object(esporo_run, "injestion_esporo", return_value=bronze)
    transform = mocker.patch.object(esporo_run, "transform_file", return_value=silver)

    esporo_run.run(tmp_path / "source.csv")

    assert transform.call_args.args == (bronze,)
    assert transform.call_args.kwargs["run_at"].tzinfo is UTC


def test_write_bronze_esporo_writes_rows_and_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(esporo_bronze, "BASE_DIR", tmp_path / "data")

    result = esporo_bronze.write_bronze_esporo(pd.DataFrame({"animal": ["Mia"]}), 2026)

    metadata = json.loads(result.with_name("metadata.json").read_text(encoding="utf-8"))
    assert result.exists()
    assert metadata["rows"] == 1
    assert metadata["columns"] == ["animal"]
