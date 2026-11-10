"""Mapeia a unidade notificadora CNES para a malha territorial oficial.

O SINAN fornece ``ID_UNIDADE``. O bairro textual do cadastro CNES é mantido
como evidência, mas não é usado como geometria. A classificação territorial
usa exclusivamente o ponto geocodificado do estabelecimento e os GeoJSONs
oficiais versionados em ``territories/``.
"""

from __future__ import annotations

import json
from math import isfinite
from pathlib import Path

import pandas as pd
from shapely import STRtree, points
from shapely.geometry import Point, shape

UNMAPPED = "UNMAPPED_NOTIFICATION_UNIT"
DISTRICT_ONLY = "NOTIFICATION_DISTRICT_ONLY"
NEIGHBORHOOD = "NOTIFICATION_NEIGHBORHOOD"


class TerritoryMapper:
    def __init__(self, assets_dir: Path) -> None:
        self.assets_dir = Path(assets_dir)
        self.districts = self._load("districts.geojson")
        self.neighborhoods = self._load("neighborhoods.geojson")

    def _load(self, filename: str) -> list[tuple[dict, object]]:
        payload = json.loads((self.assets_dir / filename).read_text(encoding="utf-8"))
        return [
            (feature["properties"], shape(feature["geometry"]))
            for feature in payload["features"]
        ]

    def classify(self, longitude: object, latitude: object) -> tuple[str | None, str | None, str]:
        try:
            point = Point(float(longitude), float(latitude))
        except (TypeError, ValueError):
            return None, None, UNMAPPED

        district_id = next(
            (props["territoryId"] for props, geometry in self.districts if geometry.covers(point)),
            None,
        )
        if district_id is None:
            return None, None, UNMAPPED

        neighborhood_id = next(
            (
                props["territoryId"]
                for props, geometry in self.neighborhoods
                if props.get("parentDistrictId") == district_id and geometry.covers(point)
            ),
            None,
        )
        return district_id, neighborhood_id, NEIGHBORHOOD if neighborhood_id else DISTRICT_ONLY


    def classify_many(self, coordinates) -> list[tuple[str | None, str | None, str]]:
        coordinates = list(coordinates)
        result = [(None, None, UNMAPPED)] * len(coordinates)
        valid = []
        for index, (longitude, latitude) in enumerate(coordinates):
            try:
                x, y = float(longitude), float(latitude)
            except (TypeError, ValueError):
                continue
            if isfinite(x) and isfinite(y):
                valid.append((index, x, y))
        if not valid or not self.districts:
            return result

        row_ids, xs, ys = zip(*valid)
        locations = points(xs, ys)
        district_tree = STRtree([geometry for _, geometry in self.districts])
        districts = {}
        # A mesma ordem do GeoJSON usada por classify() resolve sobreposições.
        for point_id, match_id in sorted(zip(*district_tree.query(locations, predicate="covered_by"))):
            districts.setdefault(point_id, self.districts[match_id][0]["territoryId"])
        for point_id, district in districts.items():
            result[row_ids[point_id]] = (district, None, DISTRICT_ONLY)

        if self.neighborhoods:
            neighborhood_tree = STRtree([geometry for _, geometry in self.neighborhoods])
            for point_id, match_id in sorted(zip(*neighborhood_tree.query(locations, predicate="covered_by"))):
                district = districts.get(point_id)
                props = self.neighborhoods[match_id][0]
                if district is not None and props.get("parentDistrictId") == district:
                    row_id = row_ids[point_id]
                    if result[row_id][1] is None:
                        result[row_id] = (district, props["territoryId"], NEIGHBORHOOD)
        return result


def enrich_cnes_territories(df: pd.DataFrame, assets_dir: Path) -> pd.DataFrame:
    mapper = TerritoryMapper(assets_dir)
    out = df.copy()
    columns = ["notification_district_id", "notification_neighborhood_id", "notification_territory_status"]
    longitude = out.get("longitude", pd.Series(None, index=out.index))
    latitude = out.get("latitude", pd.Series(None, index=out.index))
    classifications = mapper.classify_many(zip(longitude, latitude))
    out[columns] = pd.DataFrame(classifications, index=out.index, columns=columns)
    return out
