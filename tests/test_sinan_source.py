from pathlib import Path

from app.pipeline.sinan.source import RemoteSinanFile, is_changed


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
