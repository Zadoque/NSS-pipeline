from datetime import UTC, datetime

import pandas as pd
import pytest
from shapely.geometry import box

from app.pipeline.cnes.geocoding import (
    GeocodingCandidate,
    NominatimGeocoder,
    build_address_query,
    enrich_missing_coordinates,
)
from app.pipeline.cnes.silver import transform_cnes


class FakeGeocoder:
    name = "FAKE"

    def __init__(self, candidates):
        self.candidates = candidates
        self.queries = []

    def search(self, query):
        self.queries.append(query)
        return self.candidates


def _source():
    return pd.DataFrame(
        {
            "codigo_cnes": [1, 2],
            "codigo_municipio": [330100, 330100],
            "latitude_estabelecimento_decimo_grau": [-21.75, None],
            "longitude_estabelecimento_decimo_grau": [-41.32, None],
            "bairro_estabelecimento": ["Centro", "Tijuca"],
            "CO_CEP": ["28000000", "28035100"],
            "NO_LOGRADOURO": ["Rua A", "Rua B"],
            "NU_ENDERECO": ["1", "20"],
        }
    )


def test_enrichment_only_queries_missing_coordinate_and_preserves_cnes():
    frame = transform_cnes(_source(), municipality_code7="3301009")
    geocoder = FakeGeocoder([GeocodingCandidate(-21.76, -41.31, 0.87)])

    result = enrich_missing_coordinates(
        frame,
        geocoder=geocoder,
        municipality_geometry=box(-42, -22, -41, -21),
        municipality_name="Campos dos Goytacazes",
        uf_abbr="RJ",
        attempted_at=datetime(2026, 11, 14, tzinfo=UTC),
    )

    assert len(geocoder.queries) == 1
    assert "28035100" in geocoder.queries[0]
    assert result.loc[0, "coordinate_source"] == "CNES"
    assert result.loc[0, "latitude"] == -21.75
    assert pd.isna(result.loc[0, "geocoding_provider"])
    assert result.loc[1, "coordinate_source"] == "GEOCODED_ADDRESS"
    assert result.loc[1, "geocoding_status"] == "RESOLVED"
    assert result.loc[1, "latitude"] == -21.76
    assert result.loc[1, "longitude"] == -41.31
    assert result.loc[1, "latitude_geocoded"] == -21.76
    assert result.loc[1, "geocoding_confidence"] == 0.87
    assert result.loc[1, "geocoded_at"] == "2026-11-14T00:00:00+00:00"


@pytest.mark.parametrize(
    ("raw_cep", "expected"),
    [(28035100.0, "28035100"), (1001000, "01001000"), ("28035-100", "28035100")],
)
def test_address_query_normalizes_numeric_and_formatted_cep(raw_cep, expected):
    query = build_address_query(
        pd.Series({"cep": raw_cep, "logradouro": "Rua A"}),
        municipality_name="Campos dos Goytacazes",
        uf_abbr="RJ",
    )

    assert expected in query


@pytest.mark.parametrize(
    ("candidates", "status"),
    [
        ([], "NO_MATCH"),
        ([GeocodingCandidate(-10, -50)], "OUTSIDE_MUNICIPALITY"),
        (
            [
                GeocodingCandidate(-21.7, -41.3),
                GeocodingCandidate(-21.8, -41.4),
            ],
            "AMBIGUOUS",
        ),
    ],
)
def test_enrichment_rejects_unreliable_candidates(candidates, status):
    frame = transform_cnes(_source().iloc[[1]], municipality_code7="3301009")
    result = enrich_missing_coordinates(
        frame,
        geocoder=FakeGeocoder(candidates),
        municipality_geometry=box(-42, -22, -41, -21),
        municipality_name="Campos dos Goytacazes",
    )

    assert result.iloc[0]["geocoding_status"] == status
    assert result.iloc[0]["coordinate_source"] == "UNRESOLVED"
    assert pd.isna(result.iloc[0]["latitude"])


def test_enrichment_requires_municipality_geometry_without_calling_provider():
    frame = transform_cnes(_source().iloc[[1]], municipality_code7="3301009")
    geocoder = FakeGeocoder([GeocodingCandidate(-21.7, -41.3)])

    result = enrich_missing_coordinates(
        frame,
        geocoder=geocoder,
        municipality_geometry=None,
        municipality_name="Campos dos Goytacazes",
    )

    assert geocoder.queries == []
    assert result.iloc[0]["geocoding_status"] == "NO_MUNICIPALITY_GEOMETRY"


def test_enrichment_invalidates_original_coordinate_outside_municipality():
    frame = transform_cnes(_source().iloc[[0]], municipality_code7="3301009")

    result = enrich_missing_coordinates(
        frame,
        geocoder=None,
        municipality_geometry=box(-40, -20, -39, -19),
        municipality_name="Campos dos Goytacazes",
    )

    assert result.iloc[0]["coordinate_source"] == "UNRESOLVED"
    assert result.iloc[0]["geocoding_status"] == "CNES_OUTSIDE_MUNICIPALITY"
    assert pd.isna(result.iloc[0]["latitude"])
    assert result.iloc[0]["latitude_cnes"] == -21.75


def test_nominatim_refuses_public_bulk_service(tmp_path):
    with pytest.raises(ValueError, match="Nominatim público"):
        NominatimGeocoder(
            "https://nominatim.openstreetmap.org",
            cache_path=tmp_path / "cache.sqlite",
            user_agent="nss-test",
        )


def test_nominatim_refuses_public_bulk_service_with_trailing_dns_dot(tmp_path):
    with pytest.raises(ValueError, match="Nominatim público"):
        NominatimGeocoder(
            "https://nominatim.openstreetmap.org./",
            cache_path=tmp_path / "cache.sqlite",
            user_agent="nss-test",
        )


def test_nominatim_reuses_sqlite_cache(tmp_path, mocker):
    session = mocker.Mock()
    response = session.get.return_value
    response.json.return_value = [{"lat": "-21.75", "lon": "-41.32", "importance": 0.5}]
    geocoder = NominatimGeocoder(
        "http://nominatim.internal",
        cache_path=tmp_path / "cache.sqlite",
        user_agent="nss-test",
        session=session,
    )

    first = geocoder.search("Rua A, Campos, Brasil")
    second = geocoder.search("Rua A, Campos, Brasil")

    assert first == second == [GeocodingCandidate(-21.75, -41.32, 0.5)]
    session.get.assert_called_once()


def test_nominatim_partitions_cache_by_endpoint(tmp_path, mocker):
    cache = tmp_path / "cache.sqlite"
    first_session = mocker.Mock()
    first_session.get.return_value.json.return_value = [{"lat": "-21", "lon": "-41"}]
    second_session = mocker.Mock()
    second_session.get.return_value.json.return_value = [{"lat": "-22", "lon": "-42"}]

    first = NominatimGeocoder(
        "http://nominatim-a.internal", cache_path=cache,
        user_agent="nss-test", session=first_session,
    )
    second = NominatimGeocoder(
        "http://nominatim-b.internal", cache_path=cache,
        user_agent="nss-test", session=second_session,
    )

    assert first.search("mesmo endereço")[0].latitude == -21
    assert second.search("mesmo endereço")[0].latitude == -22
    first_session.get.assert_called_once()
    second_session.get.assert_called_once()
