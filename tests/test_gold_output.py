from datetime import UTC, datetime
import json
from pathlib import Path

import pandas as pd
import pytest

from app.pipeline.sinan import gold


def test_gold_root_separa_destinos():
    assert gold.gold_root("ad_hoc") == Path("/data/gold/ad_hoc")
    assert gold.gold_root("serving") == Path("/data/gold/serving")


def test_gold_root_rejeita_destino_desconhecido():
    with pytest.raises(ValueError, match="Destino Gold inválido"):
        gold.gold_root("other")  # type: ignore[arg-type]


def test_aggregate_file_grava_ad_hoc_e_serving_em_arvores_distintas(
    tmp_path, monkeypatch
):
    source = tmp_path / "silver.parquet"
    source_metadata = source.with_name("metadata.json")
    source_metadata.write_text(
        '{"disease":"DENG","source_year":2026}', encoding="utf-8"
    )
    pd.DataFrame(
        {
            "DT_NOTIFIC": pd.to_datetime(["2026-01-05"]),
            "ID_MUNICIP": ["1234567"],
            "SG_UF_NOT": ["33"],
            "NM_UF": ["Rio de Janeiro"],
            "CS_SEXO": ["F"],
            "ANO_NASC": [2000],
            "SEM_NOT": [202601],
        }
    ).to_parquet(source)
    monkeypatch.setattr(gold, "BASE_DIR", tmp_path / "data")
    run_at = datetime(2026, 1, 6, tzinfo=UTC)

    ad_hoc = gold.aggregate_file(
        source, "DENG", 2026, municipios={"1234567": "Cidade Teste"}, run_at=run_at,
        target="ad_hoc",
    )
    with pytest.raises(ValueError, match="exige snapshot CNES"):
        gold.aggregate_file(source, "DENG", 2026, target="serving")
    serving = gold.aggregate_file(
        source, "DENG", 2026, municipios={"1234567": "Cidade Teste"}, run_at=run_at,
        target="serving", allow_unmapped=True,
    )

    assert "/gold/ad_hoc/sinan/" in str(ad_hoc)
    assert "/gold/serving/sinan/" in str(serving)
    assert ad_hoc != serving
    assert json.loads(ad_hoc.with_name("metadata.json").read_text())["gold_target"] == "ad_hoc"
    assert json.loads(serving.with_name("metadata.json").read_text())["gold_target"] == "serving"
