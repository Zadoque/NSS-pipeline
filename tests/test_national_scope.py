from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

from app.pipeline import run_cnes as pipeline
from app.pipeline.reference.ibge.dtb import parse_dtb_archive
from app.pipeline.reference.ibge.models import CatalogMetadata
from app.pipeline.reference.ibge.catalog import InMemoryMunicipalityCatalog
from app.pipeline.scope import select_scope


pytestmark = pytest.mark.integration


def test_national_cnes_scope_resolves_every_dtb_municipality(tmp_path, monkeypatch):
    archive_path = os.environ.get("IBGE_DTB_ARCHIVE")
    if not archive_path:
        pytest.skip("IBGE_DTB_ARCHIVE não definida — homologação nacional pulada")

    archive = Path(archive_path)
    records = parse_dtb_archive(archive, reference_year=2025)
    catalog = InMemoryMunicipalityCatalog(
        records,
        CatalogMetadata(
            "ibge-dtb-national-test", 2025, "IBGE DTB fixture", str(archive),
            "2026-10-30T00:00:00Z", "a" * 64,
        ),
    )
    scope = select_scope(catalog, all_brazil=True)
    assert scope.count == 5571

    calls: list[tuple[str, object]] = []
    published: dict[str, object] = {}
    monkeypatch.setattr(pipeline, "BASE_DIR", tmp_path)
    monkeypatch.setattr(pipeline, "write_bronze_cnes", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "write_parquet_atomic", lambda frame, path: published.update(frame=frame, path=path))
    monkeypatch.setattr(pipeline, "write_json_atomic", lambda data, path: published.update(metadata=data))
    monkeypatch.setattr(pipeline, "asset_directory", lambda *args, **kwargs: None)

    def fake_fetch(code7, *, limit, catalog, session):
        calls.append((code7, session))
        municipality = catalog.get_municipality(code7)
        return pd.DataFrame({
            "codigo_cnes": [f"{len(calls):07d}"],
            "codigo_municipio": [municipality.code6],
        })

    monkeypatch.setattr(pipeline, "fetch_estabelecimentos", fake_fetch)

    pipeline.run_cnes(catalog=catalog, geographic_scope=scope, page_size=250)

    assert len(calls) == 5571
    assert len({session_id for _, session_id in calls}) == 1
    frame = published["frame"]
    assert len(frame) == 5571
    assert frame["cd_mun"].notna().all()
    assert frame["municipality_resolution_status"].eq("VALID").all()
    assert published["metadata"]["ibge_catalog_id"] == "ibge-dtb-national-test"
    assert published["metadata"]["cnes_page_size"] == 250
    assert published["metadata"]["cnes_request_timeout"] == 60.0
