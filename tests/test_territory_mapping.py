import json

import pandas as pd

from app.pipeline.sinan.gold import age_band, decode_sinan_age_years
from app.pipeline.territory_mapping import (
    DISTRICT_ONLY,
    NEIGHBORHOOD,
    UNMAPPED,
    TerritoryMapper,
    enrich_cnes_territories,
)


def test_decode_sinan_age_uses_encoded_unit():
    encoded = pd.Series([1001, 2007, 3009, 4018])
    result = decode_sinan_age_years(encoded)

    assert result.iloc[0] == 1 / (24 * 365.25)
    assert result.iloc[1] == 7 / 365.25
    assert result.iloc[2] == 9 / 12
    assert result.iloc[3] == 18


def test_age_band_does_not_treat_encoded_age_as_years():
    result = age_band(
        pd.Series([2026, 2026, 2026]),
        pd.Series([pd.NA, pd.NA, pd.NA], dtype="Int64"),
        pd.Series([3009, 4018, 2000]),
    )

    assert result.tolist() == ["LT1", "15_19", "LT1"]


def _geojson(features):
    return {"type": "FeatureCollection", "features": features}


def _feature(territory_id, coordinates, **properties):
    return {
        "type": "Feature",
        "properties": {"territoryId": territory_id, **properties},
        "geometry": {"type": "Polygon", "coordinates": [coordinates]},
    }


def test_territory_mapper_classifies_neighborhood_district_and_invalid_point(tmp_path):
    square = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
    inner = [(1, 1), (4, 1), (4, 4), (1, 4), (1, 1)]
    (tmp_path / "campos-districts.geojson").write_text(
        json.dumps(_geojson([_feature("D1", square)])), encoding="utf-8"
    )
    (tmp_path / "campos-neighborhoods.geojson").write_text(
        json.dumps(_geojson([_feature("N1", inner, parentDistrictId="D1")])),
        encoding="utf-8",
    )

    mapper = TerritoryMapper(tmp_path)

    assert mapper.classify(2, 2) == ("D1", "N1", NEIGHBORHOOD)
    assert mapper.classify(8, 8) == ("D1", None, DISTRICT_ONLY)
    assert mapper.classify("longitude", 8) == (None, None, UNMAPPED)
    assert mapper.classify(20, 20) == (None, None, UNMAPPED)


def test_enrich_cnes_territories_preserves_index_and_adds_contract_columns(tmp_path):
    square = [(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)]
    for filename, features in (
        ("campos-districts.geojson", [_feature("D1", square)]),
        ("campos-neighborhoods.geojson", []),
    ):
        (tmp_path / filename).write_text(
            json.dumps(_geojson(features)), encoding="utf-8"
        )

    source = pd.DataFrame(
        {"cd_unidade": [123], "longitude": [1], "latitude": [1]}, index=[7]
    )
    result = enrich_cnes_territories(source, tmp_path)

    assert result.index.tolist() == [7]
    assert result.loc[7, "notification_district_id"] == "D1"
    assert result.loc[7, "notification_neighborhood_id"] is None
    assert result.loc[7, "notification_territory_status"] == DISTRICT_ONLY
