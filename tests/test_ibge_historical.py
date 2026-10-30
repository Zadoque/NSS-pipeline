import pytest

from app.pipeline.reference.ibge.historical import MunicipalityEvent, write_events


def test_historical_events_are_explicit_and_versionable(tmp_path):
    result = write_events(tmp_path / "events.parquet", [
        MunicipalityEvent("event-1", "CREATION", "2025-01-01", None, "5101837"),
    ])
    assert result.exists()


def test_historical_events_reject_duplicates(tmp_path):
    event = MunicipalityEvent("event-1", "RENAME", "2025-01-01", "1", "1")
    with pytest.raises(ValueError, match="duplicado"):
        write_events(tmp_path / "events.parquet", [event, event])
