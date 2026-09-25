from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.pipeline.atomic_io import write_json_atomic, write_parquet_atomic


def test_write_parquet_atomic_grava_e_le_de_volta(tmp_path: Path):
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    destino = tmp_path / "sub" / "data.parquet"

    resultado = write_parquet_atomic(df, destino)

    assert resultado == destino
    assert destino.exists()
    pd.testing.assert_frame_equal(pd.read_parquet(destino), df)


def test_write_parquet_atomic_nao_deixa_arquivo_tmp_para_tras(tmp_path: Path):
    df = pd.DataFrame({"a": [1]})
    destino = tmp_path / "data.parquet"
    write_parquet_atomic(df, destino)

    arquivos = list(tmp_path.iterdir())
    assert arquivos == [destino]  # nenhum ".data.parquet.<uuid>.tmp" sobrando


def test_write_json_atomic_grava_e_le_de_volta(tmp_path: Path):
    obj = {"disease": "DENG", "rows": 10}
    destino = tmp_path / "metadata.json"

    write_json_atomic(obj, destino)

    assert json.loads(destino.read_text(encoding="utf-8")) == obj
