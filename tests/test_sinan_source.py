from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from app.pipeline.sinan.source import RemoteSinanFile, is_changed
from app.pipeline.sinan import source


def test_remote_file_detects_missing_or_different_local_size(tmp_path, monkeypatch):
    monkeypatch.setattr("app.pipeline.sinan.source.SOURCE_DIR", tmp_path)
    remote = RemoteSinanFile("FMAC", 2026, "FMACBR26.parquet", 10)

    assert is_changed(remote) is True
    remote.local_path.parent.mkdir(parents=True)
    remote.local_path.write_bytes(b"1234567890")
    assert is_changed(remote) is False
    remote.local_path.write_bytes(b"different")
    assert is_changed(remote) is True


def test_remote_file_path_is_stable():
    remote = RemoteSinanFile("TOXC", 2026, "remote", 1)
    assert remote.local_path == Path("/data/source/sinan/disease=toxc/source_year=2026/data.parquet")


def test_inspect_remote_file_normaliza_doenca_e_ignora_nao_parquet(mocker):
    catalog = [
        SimpleNamespace(path="README.txt", size=2),
        SimpleNamespace(path="DENG.parquet", size=42),
    ]
    mocked = mocker.patch.object(source.pysus.ftp, "sinan", return_value=catalog)

    result = source.inspect_remote_file("deng", 2026)

    assert result == RemoteSinanFile("DENG", 2026, "DENG.parquet", 42)
    mocked.assert_called_once_with(disease="DENG", year=2026, download=False)


@pytest.mark.parametrize("catalog", [[], [SimpleNamespace(path="a.parquet", size=1), SimpleNamespace(path="b.parquet", size=2)]])
def test_inspect_remote_file_exige_um_unico_parquet(mocker, catalog):
    mocker.patch.object(source.pysus.ftp, "sinan", return_value=catalog)

    with pytest.raises(RuntimeError, match="exatamente um"):
        source.inspect_remote_file("DENG", 2026)


@pytest.mark.parametrize("size", [None, -1])
def test_inspect_remote_file_rejeita_tamanho_invalido(mocker, size):
    mocker.patch.object(
        source.pysus.ftp, "sinan",
        return_value=[SimpleNamespace(path="DENG.parquet", size=size)],
    )

    with pytest.raises(RuntimeError, match="Tamanho remoto inválido"):
        source.inspect_remote_file("DENG", 2026)


def test_inspect_remote_file_aceita_tamanho_zero(mocker):
    mocker.patch.object(
        source.pysus.ftp, "sinan",
        return_value=[SimpleNamespace(path="DENG.parquet", size=0)],
    )

    result = source.inspect_remote_file("DENG", 2026)

    assert result.size_bytes == 0


def test_download_remote_file_valida_tamanho_e_remove_temporario(tmp_path, monkeypatch):
    monkeypatch.setattr(source, "SOURCE_DIR", tmp_path / "cache")
    remote = RemoteSinanFile("DENG", 2026, "DENG.parquet", 10)

    async def download(*, output):
        output.write_bytes(b"short")

    monkeypatch.setattr(
        source.pysus.ftp, "sinan",
        lambda **kwargs: [SimpleNamespace(path="DENG.parquet", download=download)],
    )

    with pytest.raises(RuntimeError, match="Tamanho baixado divergente"):
        source.download_remote_file(remote)

    assert not remote.local_path.exists()
    assert not list(remote.local_path.parent.glob(".download-*.parquet"))


def test_download_remote_file_pode_ser_repetido_no_mesmo_diretorio(tmp_path, monkeypatch):
    monkeypatch.setattr(source, "SOURCE_DIR", tmp_path / "cache")
    payload = b"same-size"
    remote = RemoteSinanFile("DENG", 2026, "DENG.parquet", len(payload))

    async def download(*, output):
        output.write_bytes(payload)

    monkeypatch.setattr(
        source.pysus.ftp, "sinan",
        lambda **kwargs: [SimpleNamespace(path="DENG.parquet", download=download)],
    )

    first = source.download_remote_file(remote)
    second = source.download_remote_file(remote)

    assert first == second == remote.local_path
    assert second.read_bytes() == payload


def test_download_remote_file_mantem_temporario_apos_contexto_inicial(tmp_path, monkeypatch):
    monkeypatch.setattr(source, "SOURCE_DIR", tmp_path / "cache")
    payload = b"payload"
    remote = RemoteSinanFile("DENG", 2026, "DENG.parquet", len(payload))
    captured = {}
    original_named_temporary_file = source.tempfile.NamedTemporaryFile

    def named_temporary_file(*args, **kwargs):
        context = original_named_temporary_file(*args, **kwargs)

        class ContextWrapper:
            def __enter__(self):
                file = context.__enter__()
                captured["path"] = Path(file.name)
                return file

            def __exit__(self, exc_type, exc, traceback):
                result = context.__exit__(exc_type, exc, traceback)
                captured["exists_after_context"] = captured["path"].exists()
                return result

        return ContextWrapper()

    async def download(*, output):
        output.write_bytes(payload)

    monkeypatch.setattr(source.tempfile, "NamedTemporaryFile", named_temporary_file)
    monkeypatch.setattr(
        source.pysus.ftp, "sinan",
        lambda **kwargs: [SimpleNamespace(path="DENG.parquet", download=download)],
    )

    source.download_remote_file(remote)

    assert captured["exists_after_context"] is True
    assert captured["path"].parent == remote.local_path.parent
    assert not captured["path"].exists()


def test_is_changed_compara_tamanho_exato_e_diferente(tmp_path, monkeypatch):
    monkeypatch.setattr(source, "SOURCE_DIR", tmp_path)
    remote = RemoteSinanFile("DENG", 2026, "DENG.parquet", 5)
    remote.local_path.parent.mkdir(parents=True)

    remote.local_path.write_bytes(b"12345")
    assert source.is_changed(remote) is False

    remote.local_path.write_bytes(b"123456")
    assert source.is_changed(remote) is True


def test_read_remote_cache_retorna_parquet_existente(tmp_path, monkeypatch):
    monkeypatch.setattr(source, "SOURCE_DIR", tmp_path)
    remote = RemoteSinanFile("DENG", 2026, "DENG.parquet", 1)
    remote.local_path.parent.mkdir(parents=True)
    expected = pd.DataFrame({"id": [1]})
    expected.to_parquet(remote.local_path, index=False)

    result = source.read_remote_cache(remote)

    pd.testing.assert_frame_equal(result, expected)
