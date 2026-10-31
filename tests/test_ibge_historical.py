import pytest

from app.pipeline.reference.ibge.historical import (
    MunicipalityEvent,
    derive_annual_events,
    derive_annual_event_series,
    parse_administrative_events,
    parse_toponymic_events,
    promote_administrative_events,
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


def test_parse_administrative_events_requires_explicit_codes(tmp_path):
    source = tmp_path / "administrative.csv"
    source.write_text(
        "EVENT_TYPE,EFFECTIVE_DATE,SOURCE_CODE7,TARGET_CODE7,SOURCE_NAME,TARGET_NAME\n"
        "SUCCESSION,2025-01-01,5101234,5101837,Origem,Novo\n",
        encoding="utf-8",
    )
    events = parse_administrative_events(source, reference_year=2025)
    assert events[0].event_type == "SUCCESSION"
    assert events[0].source_code7 == "5101234"
    assert events[0].target_code7 == "5101837"


@pytest.mark.parametrize(
    "content",
    [
        "EVENT_TYPE,EFFECTIVE_DATE,SOURCE_CODE7,TARGET_CODE7\nSUCCESSION,2025-01-01,5101234,\n",
        "EVENT_TYPE,EFFECTIVE_DATE,SOURCE_CODE7,TARGET_CODE7\nBOGUS,2025-01-01,5101234,5101837\n",
        "EVENT_TYPE,EFFECTIVE_DATE,SOURCE_CODE7,TARGET_CODE7\nCREATION,2025-01-01,,51018\n",
    ],
)
def test_parse_administrative_events_rejects_ambiguous_or_unknown_rows(tmp_path, content):
    source = tmp_path / "administrative.csv"
    source.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        parse_administrative_events(source, reference_year=2025)


def test_promote_administrative_events_writes_versioned_manifest(tmp_path):
    source = tmp_path / "administrative.csv"
    source.write_text(
        "EVENT_TYPE,EFFECTIVE_DATE,SOURCE_CODE7,TARGET_CODE7\n"
        "CREATION,2025-01-01,,5101837\n",
        encoding="utf-8",
    )
    result = promote_administrative_events(tmp_path / "catalog", source, reference_year=2025)
    assert result.exists()
    assert result.with_name("municipality_events.manifest.json").exists()


def test_promotions_merge_toponymic_and_administrative_events(tmp_path):
    root = tmp_path / "catalog"
    toponymic = tmp_path / "toponymic.csv"
    toponymic.write_text(
        "UF,MUN,ALT,NOME_ANTERIOR,NOME_ATUAL,DATA_OCORRÊNCIA\n"
        "33,01009,2,Nome antigo,Campos dos Goytacazes,1988-10-24\n",
        encoding="utf-8",
    )
    administrative = tmp_path / "administrative.csv"
    administrative.write_text(
        "EVENT_TYPE,EFFECTIVE_DATE,SOURCE_CODE7,TARGET_CODE7\n"
        "CREATION,2025-01-01,,5101837\n",
        encoding="utf-8",
    )
    promote_toponymic_events(root, toponymic, reference_year=2025)
    result = promote_administrative_events(root, administrative, reference_year=2025)

    frame = __import__("pandas").read_parquet(result)
    assert set(frame["event_type"]) == {"TOPONYMIC_CHANGE", "CREATION"}
    assert len(frame) == 2


def test_derive_annual_events_does_not_infer_succession():
    from app.pipeline.reference.ibge.models import Municipality

    previous = [Municipality("3301009", "330100", "Nome antigo", "33", "RJ", "Rio", 2024)]
    current = [
        Municipality("3301009", "330100", "Nome atual", "33", "RJ", "Rio", 2025),
        Municipality("5101837", "510183", "Novo município", "51", "MT", "Mato Grosso", 2025),
    ]

    events = derive_annual_events(
        previous, current, reference_year=2025,
        effective_date="2025-01-01", source_url="fixture://dtb-diff",
    )

    assert {(event.event_type, event.source_code7, event.target_code7) for event in events} == {
        ("TOPONYMIC_CHANGE", "3301009", "3301009"),
        ("CREATION", None, "5101837"),
    }


def test_derive_annual_event_series_requires_consecutive_editions():
    from app.pipeline.reference.ibge.models import Municipality

    item = Municipality("3301009", "330100", "Campos", "33", "RJ", "Rio", 2024)
    with pytest.raises(ValueError, match="anos consecutivos"):
        derive_annual_event_series({2022: [item], 2024: [item]})


def test_derive_annual_event_series_keeps_creation_and_extinction_separate():
    from app.pipeline.reference.ibge.models import Municipality

    previous = Municipality("3301009", "330100", "Origem", "33", "RJ", "Rio", 2024)
    current = Municipality("5101837", "510183", "Novo", "51", "MT", "Mato Grosso", 2025)
    events = derive_annual_event_series(
        {2024: [previous], 2025: [current]},
        source_urls={2025: "https://example.invalid/DTB_2025.zip"},
    )
    assert {(event.event_type, event.source_code7, event.target_code7) for event in events} == {
        ("EXTINCTION", "3301009", None),
        ("CREATION", None, "5101837"),
    }
    assert all(event.source == "https://example.invalid/DTB_2025.zip" for event in events)


def test_derive_annual_event_series_allows_unchanged_intervals():
    from app.pipeline.reference.ibge.models import Municipality

    item = Municipality("3301009", "330100", "Campos", "33", "RJ", "Rio", 2024)
    assert derive_annual_event_series({2024: [item], 2025: [item]}) == []
