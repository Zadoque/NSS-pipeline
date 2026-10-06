from pathlib import Path

from app.pipeline.sinan.source import RemoteSinanFile
from app.pipeline.update_sinan import update_one


def test_update_one_skips_same_size(tmp_path, monkeypatch):
    monkeypatch.setattr("app.pipeline.sinan.source.SOURCE_DIR", tmp_path)
    remote = RemoteSinanFile("DENG", 2026, "remote", 4)
    remote.local_path.parent.mkdir(parents=True)
    remote.local_path.write_bytes(b"1234")
    manifest = {"DENG:2026": {"remoteSizeBytes": 4}}

    result = update_one(remote, manifest)

    assert result == "DENG:2026: unchanged (4 bytes)"
    assert manifest["DENG:2026"]["status"] == "UNCHANGED"


def test_update_one_downloads_and_runs_when_size_changes(tmp_path, monkeypatch):
    monkeypatch.setattr("app.pipeline.sinan.source.SOURCE_DIR", tmp_path)
    remote = RemoteSinanFile("FMAC", 2026, "remote", 5)
    remote.local_path.parent.mkdir(parents=True)
    remote.local_path.write_bytes(b"old")
    manifest = {}
    loaded = []

    monkeypatch.setattr(
        "app.pipeline.update_sinan.download_remote_file",
        lambda item: item.local_path,
    )
    remote.local_path.write_bytes(b"12345")
    monkeypatch.setattr(
        "app.pipeline.update_sinan.run_load",
        lambda disease, year, source_path, allow_empty: loaded.append(
            (disease, year, source_path, allow_empty)
        ),
    )

    # Simulate a changed remote by changing the local file after the first check.
    remote = RemoteSinanFile("FMAC", 2026, "remote", 6)
    result = update_one(remote, manifest)

    assert result == "FMAC:2026: updated (6 bytes)"
    assert loaded == [("FMAC", 2026, remote.local_path, True)]
    assert manifest["FMAC:2026"]["status"] == "UPDATED"
