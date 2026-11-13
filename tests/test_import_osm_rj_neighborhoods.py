import json

from scripts.import_osm_rj_neighborhoods import import_osm


def test_import_osm_writes_only_polygon_inside_rj_municipality(tmp_path):
    root = tmp_path / "territories"
    districts = root / "rj" / "3301009"
    districts.mkdir(parents=True)
    feature = {
        "type": "Feature",
        "properties": {"territoryId": "IBGE_DIST_1"},
        "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]},
    }
    (districts / "districts.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [feature]}))

    result = import_osm(
        {"elements": [
            {"type": "way", "id": 1, "tags": {"name": "Centro", "place": "neighbourhood"},
             "geometry": [{"lon": 1, "lat": 1}, {"lon": 2, "lat": 1}, {"lon": 2, "lat": 2}, {"lon": 1, "lat": 1}]},
            {"type": "way", "id": 2, "tags": {"name": "Fora", "place": "neighbourhood"},
             "geometry": [{"lon": 20, "lat": 20}, {"lon": 21, "lat": 20}, {"lon": 21, "lat": 21}, {"lon": 20, "lat": 20}]},
        ]},
        root=root,
    )

    assert result == {"3301009": 1}
    output = json.loads((root / "rj-osm" / "3301009" / "neighborhoods.geojson").read_text())
    assert output["features"][0]["properties"]["geometryStatus"] == "POLYGON_OSM"
    assert output["features"][0]["properties"]["sourceLicense"] == "ODbL-1.0"
