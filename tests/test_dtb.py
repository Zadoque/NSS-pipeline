from pathlib import Path

from app.pipeline.reference.ibge.dtb import parse_dtb_table
from app.pipeline.reference.ibge.refresh import refresh_from_dtb_archive


FIXTURE = Path(__file__).parent / "fixtures/ibge/dtb_2025_municipalities_sample.csv"


def test_parse_dtb_official_shape_and_codes():
    records = parse_dtb_table(FIXTURE, 2025)

    assert len(records) == 6
    campos = next(item for item in records if item.code7 == "3301009")
    assert campos.code6 == "330100"
    assert campos.uf_abbr == "RJ"
    assert campos.source == "IBGE_DTB"


def test_dtb_names_are_not_identity_keys():
    records = parse_dtb_table(FIXTURE, 2025)
    bom_jesus = [item for item in records if item.name == "Bom Jesus"]
    assert {item.code7 for item in bom_jesus} == {"2401701", "2502201"}


def test_refresh_dtb_writes_release_and_active_pointer(tmp_path, monkeypatch):
    import app.pipeline.reference.ibge.refresh as refresh

    monkeypatch.setattr(refresh, "parse_dtb_archive", lambda archive, year: parse_dtb_table(FIXTURE, year))
    archive = tmp_path / "DTB_2025.zip"
    archive.write_bytes(b"official-fixture")
    result = refresh_from_dtb_archive(
        tmp_path / "reference", archive, catalog_id="ibge-dtb-2025",
        source_url="https://example.invalid/DTB_2025.zip", reference_year=2025,
    )
    assert result.exists()
    assert (tmp_path / "reference/active.json").exists()
    assert "ibge-dtb-2025" in (tmp_path / "reference/releases/ibge-dtb-2025/manifest.json").read_text()
