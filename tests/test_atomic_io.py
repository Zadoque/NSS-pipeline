from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

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


def test_write_parquet_atomic_remove_temporario_quando_gravacao_falha(tmp_path, monkeypatch):
    destino = tmp_path / "data.parquet"

    def fail(*args, **kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", fail)

    with pytest.raises(OSError, match="disco cheio"):
        write_parquet_atomic(pd.DataFrame({"a": [1]}), destino)

    assert not destino.exists()
    assert list(tmp_path.iterdir()) == []


def test_write_json_atomic_preserva_destino_se_substituicao_falha(tmp_path, monkeypatch):
    destino = tmp_path / "metadata.json"
    destino.write_text('{"versao": 1}', encoding="utf-8")

    def fail_replace(source, target):
        raise OSError("permissão negada")

    monkeypatch.setattr("app.pipeline.atomic_io.os.replace", fail_replace)

    with pytest.raises(OSError, match="permissão"):
        write_json_atomic({"versao": 2}, destino)

    assert destino.read_text(encoding="utf-8") == '{"versao": 1}'
    assert [p for p in tmp_path.iterdir() if p.name.startswith(".metadata.json.")] == []


def test_write_json_atomic_cria_diretorios_aninhados(tmp_path):
    destino = tmp_path / "nested" / "deep" / "metadata.json"

    write_json_atomic({"ok": True}, destino)

    assert json.loads(destino.read_text(encoding="utf-8")) == {"ok": True}


def test_write_parquet_atomic_nao_persiste_indice_customizado(tmp_path):
    destino = tmp_path / "data.parquet"
    frame = pd.DataFrame({"valor": [10, 20]}, index=["a", "b"])

    write_parquet_atomic(frame, destino)

    loaded = pd.read_parquet(destino)
    assert list(loaded.columns) == ["valor"]
    assert list(loaded.index) == [0, 1]
