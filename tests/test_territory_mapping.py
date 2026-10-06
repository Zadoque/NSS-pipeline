import pandas as pd
import pytest
from pathlib import Path
from app.pipeline.territory_mapping import TerritoryMapper, UNMAPPED, DISTRICT_ONLY, NEIGHBORHOOD

from app.pipeline.sinan.gold import age_band, decode_sinan_age_years


@pytest.mark.parametrize('lon,lat', [(None, None), (float('nan'), 0), (0, float('inf')), (181, 0), (0, 91), ('bad', 0), (0, 0)])
def test_invalid_or_outside_coordinates_are_unmapped(lon, lat):
    mapper = TerritoryMapper(Path('territories'))
    assert mapper.classify(lon, lat) == (None, None, UNMAPPED)


def test_point_inside_neighborhood_matches_parent():
    mapper = TerritoryMapper(Path('territories'))
    for props, geometry in mapper.neighborhoods:
        point = geometry.representative_point()
        district, neighborhood, status = mapper.classify(point.x, point.y)
        if neighborhood == props['territoryId']:
            assert district == props['parentDistrictId']
            assert status == NEIGHBORHOOD
            break
    else:
        pytest.fail('Nenhum ponto interno de bairro foi classificado')


def test_district_without_neighborhood_geometry():
    mapper = TerritoryMapper(Path('territories'))
    mapper.neighborhoods = []
    point = mapper.districts[0][1].representative_point()
    assert mapper.classify(point.x, point.y)[2] == DISTRICT_ONLY


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
