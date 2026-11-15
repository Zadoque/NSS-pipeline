"""Enriquecimento de coordenadas CNES sem sobrescrever a evidência original."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import sqlite3
from typing import Protocol
from urllib.parse import urlparse

import pandas as pd
import requests
from shapely.geometry import Point, shape
from shapely.ops import unary_union


@dataclass(frozen=True)
class GeocodingCandidate:
    latitude: float
    longitude: float
    confidence: float | None = None


class Geocoder(Protocol):
    name: str

    def search(self, query: str) -> list[GeocodingCandidate]: ...


class NominatimGeocoder:
    """Cliente para uma instância Nominatim auto-hospedada.

    O endpoint público é recusado deliberadamente: esta carga é nacional e
    não deve depender de um serviço comunitário sujeito a política de uso.
    """

    name = "NOMINATIM_SELF_HOSTED"

    def __init__(
        self,
        base_url: str,
        *,
        cache_path: Path,
        user_agent: str,
        timeout: float = 20.0,
        session: requests.Session | None = None,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("URL do geocodificador deve usar http ou https")
        hostname = (parsed.hostname or "").rstrip(".").casefold()
        if hostname == "nominatim.openstreetmap.org":
            raise ValueError("a carga CNES não aceita o Nominatim público; use uma instância própria")
        if not user_agent.strip():
            raise ValueError("geocodificador exige user-agent identificável")
        if timeout <= 0:
            raise ValueError("timeout do geocodificador deve ser maior que zero")
        self.search_url = base_url.rstrip("/")
        self.identity = self.search_url
        if not self.search_url.endswith("/search"):
            self.search_url += "/search"
        self.cache_provider = f"{self.name}:{self.search_url}"
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.timeout = float(timeout)
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self._initialize_cache()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.cache_path, timeout=30)
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize_cache(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS geocoding_cache (
                    provider TEXT NOT NULL,
                    query TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    cached_at TEXT NOT NULL,
                    PRIMARY KEY (provider, query)
                )
                """
            )

    def search(self, query: str) -> list[GeocodingCandidate]:
        with self._connect() as connection:
            cached = connection.execute(
                "SELECT payload FROM geocoding_cache WHERE provider = ? AND query = ?",
                (self.cache_provider, query),
            ).fetchone()
        if cached is not None:
            payload = json.loads(cached[0])
        else:
            response = self.session.get(
                self.search_url,
                params={
                    "q": query,
                    "format": "jsonv2",
                    "limit": 5,
                    "countrycodes": "br",
                    "addressdetails": 1,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise ValueError("resposta Nominatim deve ser uma lista")
            encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO geocoding_cache(provider, query, payload, cached_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(provider, query) DO UPDATE SET
                        payload = excluded.payload,
                        cached_at = excluded.cached_at
                    """,
                    (self.cache_provider, query, encoded, datetime.now(UTC).isoformat()),
                )
        candidates = []
        for item in payload:
            try:
                latitude = float(item["lat"])
                longitude = float(item["lon"])
                importance = item.get("importance")
                confidence = float(importance) if importance is not None else None
            except (KeyError, TypeError, ValueError):
                continue
            candidates.append(GeocodingCandidate(latitude, longitude, confidence))
        return candidates


def load_municipality_geometry(assets_dir: Path):
    """Monta o limite municipal pela união dos distritos oficiais/versionados."""
    path = Path(assets_dir) / "districts.geojson"
    payload = json.loads(path.read_text(encoding="utf-8"))
    geometries = [
        shape(feature["geometry"])
        for feature in payload.get("features", [])
        if feature.get("geometry")
    ]
    if not geometries:
        raise ValueError(f"malha municipal sem distritos: {path}")
    return unary_union(geometries)


def _text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def _normalize_cep(value: object) -> str:
    text = _text(value)
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".", 1)[0]
    digits = re.sub(r"\D", "", text)
    return digits.zfill(8) if 0 < len(digits) <= 8 else digits


def build_address_query(row: pd.Series, *, municipality_name: str, uf_abbr: str | None) -> str | None:
    cep = _normalize_cep(row.get("cep"))
    street = _text(row.get("logradouro"))
    if len(cep) != 8 or not street:
        return None
    street_number = _text(row.get("numero"))
    street_address = ", ".join(part for part in (street, street_number) if part)
    parts = [street_address, _text(row.get("bairro_cnes")), municipality_name]
    if uf_abbr:
        parts.append(uf_abbr)
    parts.extend((cep, "Brasil"))
    return ", ".join(part for part in parts if part)


def enrich_missing_coordinates(
    df: pd.DataFrame,
    *,
    geocoder: Geocoder | None,
    municipality_geometry,
    municipality_name: str,
    uf_abbr: str | None = None,
    attempted_at: datetime | None = None,
) -> pd.DataFrame:
    """Geocodifica somente registros sem coordenada CNES válida.

    Um resultado só vira coordenada efetiva quando há exatamente uma posição
    distinta dentro do limite municipal. Coordenadas CNES válidas não são
    consultadas nem modificadas.
    """
    out = df.copy()
    if "coordinate_source" not in out:
        return out
    cnes = out["coordinate_source"].astype("string").eq("CNES")
    if municipality_geometry is not None:
        outside = pd.Series(False, index=out.index)
        for index, row in out.loc[cnes].iterrows():
            try:
                point = Point(float(row["longitude"]), float(row["latitude"]))
            except (KeyError, TypeError, ValueError):
                outside.at[index] = True
            else:
                outside.at[index] = not municipality_geometry.covers(point)
        out.loc[outside, ["latitude", "longitude"]] = pd.NA
        out.loc[outside, "coordinate_source"] = "UNRESOLVED"
        out.loc[outside, "geocoding_status"] = "CNES_OUTSIDE_MUNICIPALITY"

    target = out["coordinate_source"].astype("string").ne("CNES")
    if not target.any() or geocoder is None:
        return out
    if municipality_geometry is None:
        out.loc[target, "geocoding_status"] = "NO_MUNICIPALITY_GEOMETRY"
        return out

    timestamp = (attempted_at or datetime.now(UTC)).isoformat()
    for index, row in out.loc[target].iterrows():
        query = build_address_query(
            row, municipality_name=municipality_name, uf_abbr=uf_abbr
        )
        if query is None:
            out.at[index, "geocoding_status"] = "INSUFFICIENT_ADDRESS"
            continue
        out.at[index, "geocoding_provider"] = str(
            getattr(geocoder, "identity", geocoder.name)
        )
        out.at[index, "geocoded_at"] = timestamp
        try:
            candidates = geocoder.search(query)
        except (requests.RequestException, OSError, ValueError, sqlite3.Error, json.JSONDecodeError):
            out.at[index, "geocoding_status"] = "ERROR"
            continue
        inside: dict[tuple[float, float], GeocodingCandidate] = {}
        for candidate in candidates:
            if municipality_geometry.covers(Point(candidate.longitude, candidate.latitude)):
                inside.setdefault(
                    (round(candidate.latitude, 6), round(candidate.longitude, 6)), candidate
                )
        if not candidates:
            out.at[index, "geocoding_status"] = "NO_MATCH"
        elif not inside:
            out.at[index, "geocoding_status"] = "OUTSIDE_MUNICIPALITY"
        elif len(inside) > 1:
            out.at[index, "geocoding_status"] = "AMBIGUOUS"
        else:
            candidate = next(iter(inside.values()))
            out.at[index, "latitude_geocoded"] = candidate.latitude
            out.at[index, "longitude_geocoded"] = candidate.longitude
            out.at[index, "latitude"] = candidate.latitude
            out.at[index, "longitude"] = candidate.longitude
            out.at[index, "coordinate_source"] = "GEOCODED_ADDRESS"
            out.at[index, "geocoding_status"] = "RESOLVED"
            out.at[index, "geocoding_confidence"] = candidate.confidence
    return out
