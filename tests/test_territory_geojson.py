import pytest

from scripts.territory_geojson import deduplicate_neighborhoods, normalize_neighborhoods


def _feature(territory_id, name, coordinates, *, element_type, parent="D1"):
    return {
        "type": "Feature",
        "properties": {
            "territoryId": territory_id,
            "name": name,
            "parentDistrictId": parent,
            "osmElementType": element_type,
        },
        "geometry": {"type": "Polygon", "coordinates": [coordinates]},
    }


def test_deduplicate_prefers_relation_for_overlapping_way():
    square = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
    result, discarded = deduplicate_neighborhoods(
        [
            _feature("way-1", "Lourdes", square, element_type="way"),
            _feature("relation-1", "Lourdes", square, element_type="relation"),
        ]
    )

    assert [item["properties"]["territoryId"] for item in result] == ["relation-1"]
    assert discarded[0]["discardedTerritoryId"] == "way-1"
    assert discarded[0]["retainedTerritoryId"] == "relation-1"
    assert discarded[0]["overlapRatio"] == 1.0


def test_deduplicate_keeps_same_name_when_geometries_are_distinct():
    left = [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]
    right = [(3, 0), (4, 0), (4, 1), (3, 1), (3, 0)]
    result, discarded = deduplicate_neighborhoods(
        [
            _feature("a", "Centro", left, element_type="relation"),
            _feature("b", "Centro", right, element_type="relation"),
        ]
    )

    assert {item["properties"]["territoryId"] for item in result} == {"a", "b"}
    assert discarded == []


def test_deduplicate_rejects_empty_geometry():
    empty = _feature("empty", "Centro", [(0, 0), (0, 0), (0, 0)], element_type="way")
    with pytest.raises(ValueError, match="Geometria territorial vazia"):
        deduplicate_neighborhoods([empty])


def test_normalization_keeps_declared_district():
    district = _feature(
        "D1",
        "Distrito",
        [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)],
        element_type="relation",
    )
    district["properties"] = {"territoryId": "D1"}
    neighborhood = _feature(
        "N1",
        "Bairro",
        [(1, 1), (2, 1), (2, 2), (1, 2), (1, 1)],
        element_type="relation",
    )
    result = normalize_neighborhoods([neighborhood], [district])
    assert result[0]["properties"]["parentDistrictId"] == "D1"


def test_normalization_clips_neighborhood_to_parent_district():
    district = _feature(
        "D1",
        "Distrito",
        [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)],
        element_type="relation",
    )
    district["properties"] = {"territoryId": "D1"}
    neighborhood = _feature(
        "N1",
        "Bairro",
        [(-2, 2), (2, 2), (2, 4), (-2, 4), (-2, 2)],
        element_type="relation",
    )
    result = normalize_neighborhoods([neighborhood], [district])
    coordinates = result[0]["geometry"]["coordinates"][0]
    assert min(point[0] for point in coordinates) == 0
