import pytest

from app.pipeline.reference.ibge.historical import (
    MunicipalityEvent,
    parse_toponymic_events,
    promote_toponymic_events,
    write_events,
)


def test_historical_events_are_explicit_and_versionable(tmp_path):
    result = write_events(tmp_path / "events.parquet", [
        MunicipalityEvent("event-1", "CREATION", "2025-01-01", None, "5101837"),
    ])
    assert result.exists()


def test_historical_events_reject_duplicates(tmp_path):
    event = MunicipalityEvent("event-1", "RENAME", "2025-01-01", "1", "1")
    with pytest.raises(ValueError, match="duplicado"):
        write_events(tmp_path / "events.parquet", [event, event])


def test_parse_toponymic_events_preserves_code_and_names(tmp_path):
    source = tmp_path / "alteracoes.csv"
    source.write_text(
        "UF,MUN,ALT,NOME_ANTERIOR,NOME_ATUAL,DATA_OCORRÊNCIA\n"
        "33,01009,2,Campos dos Goitacazes,Campos dos Goytacazes,1988-10-24\n",
        encoding="utf-8",
    )
    events = parse_toponymic_events(
        source, reference_year=2025, source_url="https://example.invalid/ibge.xls"
    )
    assert len(events) == 1
    assert events[0].event_type == "TOPONYMIC_CHANGE"
    assert events[0].source_code7 == events[0].target_code7 == "3301009"
    assert events[0].source_name == "Campos dos Goitacazes"
    assert events[0].target_name == "Campos dos Goytacazes"
    assert events[0].effective_date == "1988-10-24"


def test_promote_toponymic_events_writes_manifest(tmp_path):
    source = tmp_path / "alteracoes.csv"
    source.write_text(
        "UF,MUN,ALT,NOME_ANTERIOR,NOME_ATUAL,DATA_OCORRÊNCIA\n"
        "24,00100,1,Amparo de São Francisco,Amparo do São Francisco,2020-07-14\n",
        encoding="utf-8",
    )
    result = promote_toponymic_events(tmp_path / "catalog", source, reference_year=2025)
    assert result.exists()
    assert result.with_name("municipality_events.manifest.json").exists()
