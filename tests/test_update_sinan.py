from pathlib import Path

from app.pipeline.sinan.source import RemoteSinanFile
import json

import pytest

from app.pipeline.update_sinan import _load_manifest, _parse_years, _save_manifest, update, update_one


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


@pytest.mark.parametrize("raw,expected", [(None, None), ("2026, 2024,2026", [2024, 2026])])
def test_parse_years_normalizes_and_defaults_to_current_year(raw, expected, monkeypatch):
    if expected is None:
        monkeypatch.setattr("app.pipeline.update_sinan.datetime", type("Clock", (), {"now": staticmethod(lambda _: type("Year", (), {"year": 2026})())}))
        assert _parse_years(raw) == [2026]
    else:
        assert _parse_years(raw) == expected


@pytest.mark.parametrize("raw", ["1999", "10000", "abc"])
def test_parse_years_rejects_invalid_values(raw):
    with pytest.raises((ValueError, OverflowError)):
        _parse_years(raw)


def test_manifest_round_trip_and_invalid_payload(tmp_path):
    path = tmp_path / "manifest.json"
    manifest = {"DENG:2026": {"status": "UPDATED"}}

    _save_manifest(path, manifest)

    assert _load_manifest(path) == manifest
    path.write_text(json.dumps(["not-an-object"]), encoding="utf-8")
    with pytest.raises(ValueError, match="objeto por recorte"):
        _load_manifest(path)


def test_update_inspects_each_slice_and_persists_manifest(tmp_path, mocker, monkeypatch):
    monkeypatch.setattr("app.pipeline.sinan.source.SOURCE_DIR", tmp_path / "source")
    remote = RemoteSinanFile("DENG", 2026, "remote", 4)
    remote.local_path.parent.mkdir(parents=True)
    remote.local_path.write_bytes(b"1234")
    inspect = mocker.patch("app.pipeline.update_sinan.inspect_remote_file", return_value=remote)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"DENG:2026": {"remoteSizeBytes": 4}}), encoding="utf-8")

    results = update(["DENG"], [2026], manifest_path)

    assert results == ["DENG:2026: unchanged (4 bytes)"]
    inspect.assert_called_once_with("DENG", 2026)
    assert _load_manifest(manifest_path)["DENG:2026"]["status"] == "UNCHANGED"
