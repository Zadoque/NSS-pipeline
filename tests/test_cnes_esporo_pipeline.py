import json
from datetime import UTC, datetime

import pandas as pd

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
