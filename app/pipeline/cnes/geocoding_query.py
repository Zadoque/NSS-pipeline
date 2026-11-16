from __future__ import annotations

import json
from pathlib import Path
import re

import pandas as pd
from shapely.geometry import shape
from shapely.ops import unary_union


def load_municipality_geometry(assets_dir: Path):
    path = Path(assets_dir) / "districts.geojson"
    payload = json.loads(path.read_text(encoding="utf-8"))
    geometries = [shape(feature["geometry"]) for feature in payload.get("features", []) if feature.get("geometry")]
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
    address = ", ".join(part for part in (street, _text(row.get("numero"))) if part)
    parts = [address, _text(row.get("bairro_cnes")), municipality_name]
    if uf_abbr:
        parts.append(uf_abbr)
    return ", ".join(part for part in (*parts, cep, "Brasil") if part)
