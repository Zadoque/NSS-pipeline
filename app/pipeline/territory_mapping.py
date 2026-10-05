"""Mapeia a unidade notificadora CNES para a malha territorial oficial.

O SINAN fornece ``ID_UNIDADE``. O bairro textual do cadastro CNES é mantido
como evidência, mas não é usado como geometria. A classificação territorial
usa exclusivamente o ponto geocodificado do estabelecimento e os GeoJSONs
oficiais versionados em ``territories/``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from shapely.geometry import Point, shape

UNMAPPED = "UNMAPPED_NOTIFICATION_UNIT"
DISTRICT_ONLY = "NOTIFICATION_DISTRICT_ONLY"
NEIGHBORHOOD = "NOTIFICATION_NEIGHBORHOOD"


class TerritoryMapper:
    def __init__(self, assets_dir: Path) -> None:
        self.assets_dir = Path(assets_dir)
        self.districts = self._load("campos-districts.geojson")
        self.neighborhoods = self._load("campos-neighborhoods.geojson")

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


def enrich_cnes_territories(df: pd.DataFrame, assets_dir: Path) -> pd.DataFrame:
    mapper = TerritoryMapper(assets_dir)
    out = df.copy()
    classifications = [
        mapper.classify(row.get("longitude"), row.get("latitude"))
        for _, row in out.iterrows()
    ]
    out[["notification_district_id", "notification_neighborhood_id", "notification_territory_status"]] = pd.DataFrame(
        classifications, index=out.index
    )
    return out
