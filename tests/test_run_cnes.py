from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.pipeline import run_cnes as pipeline


def _bronze(code: str) -> pd.DataFrame:
    return pd.DataFrame({"codigo_cnes": [code], "codigo_municipio": [3301009]})


def _silver(code: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "cd_unidade": [code],
            "nm_unidade": [f"Unidade {code}"],
        }
    )


def test_run_cnes_publishes_consolidated_snapshot_and_metadata(tmp_path, monkeypatch):
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(pipeline, "BASE_DIR", tmp_path)
    monkeypatch.setattr(pipeline, "fetch_estabelecimentos", lambda code: _bronze(code))
    monkeypatch.setattr(pipeline, "write_bronze_cnes", lambda df, code, run_at: calls.append(("bronze", code)))
    monkeypatch.setattr(pipeline, "transform_cnes", lambda df: _silver(str(df.iloc[0]["codigo_cnes"])))
    monkeypatch.setattr(pipeline, "enrich_cnes_territories", lambda df, assets: df.assign(notification_territory_status="MAPPED"))

    written: dict[str, object] = {}
    monkeypatch.setattr(pipeline, "write_parquet_atomic", lambda df, path: written.update(parquet=(df.copy(), path)))
    monkeypatch.setattr(pipeline, "write_json_atomic", lambda data, path: written.update(metadata=(data, path)))

    result = pipeline.run_cnes({"3301009": "Campos", "3302403": "Macaé"})

    assert isinstance(result, Path)
    assert [kind for kind, _ in calls] == ["bronze", "bronze"]
    consolidated, parquet = written["parquet"]
    assert len(consolidated) == 2
    assert set(consolidated["notification_territory_status"]) == {"MAPPED", "UNAVAILABLE"}
    metadata, _ = written["metadata"]
    assert metadata["rows"] == 2
    assert metadata["municipios"] == ["3301009", "3302403"]
    assert parquet == result


def test_run_cnes_rejects_empty_scope():
    with pytest.raises(ValueError, match="ao menos"):
        pipeline.run_cnes({})


def test_territory_asset_registry_only_maps_configured_municipalities(tmp_path):
    from app.pipeline.territory_assets import asset_directory

    assert asset_directory("3301009", root=tmp_path / "territories") is None
    assert asset_directory("9999999", root=tmp_path / "territories") is None


def test_run_cnes_rejects_empty_api_response(monkeypatch):
    monkeypatch.setattr(pipeline, "fetch_estabelecimentos", lambda code: pd.DataFrame())

    with pytest.raises(RuntimeError, match="retornou vazio"):
        pipeline.run_cnes({"3301009": "Campos"})
