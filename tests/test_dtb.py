from pathlib import Path

from app.pipeline.reference.ibge.dtb import parse_dtb_table
from app.pipeline.reference.ibge.refresh import refresh_from_dtb_archive
from app.pipeline.reference.ibge.refresh import refresh_from_localidades


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


def test_dtb_marks_distrito_federal_as_special_administrative_type(tmp_path):
    path = tmp_path / "df.csv"
    path.write_text(
        "a,b,c,d,e,f,g,h,i\n" * 6
        + "UF,Nome_UF,x,x,x,x,Município,Código Município Completo,Nome_Município\n"
        + "53,Distrito Federal,1,1,1,1,00010,5300108,Brasília\n",
        encoding="utf-8",
    )
    records = parse_dtb_table(path, 2025)
    assert records[0].administrative_type == "FEDERAL_DISTRICT"


def test_parse_dtb_rejeita_linha_municipal_com_geocodigo_invalido(tmp_path):
    path = tmp_path / "invalid.csv"
    path.write_text(
        "a,b,c,d,e,f,g,h,i\n" * 6
        + "UF,Nome_UF,x,x,x,x,Município,Código Município Completo,Nome_Município\n"
        + "33,Rio de Janeiro,1,1,1,1,00010,33010X9,Campos\n",
        encoding="utf-8",
    )

    import pytest

    with pytest.raises(ValueError, match="geocódigo municipal inválido"):
        parse_dtb_table(path, 2025)


def test_parse_dtb_rejeita_geocodigo_unicode(tmp_path):
    path = tmp_path / "unicode.csv"
    path.write_text(
        "a,b,c,d,e,f,g,h,i\n" * 6
        + "UF,Nome_UF,x,x,x,x,Município,Código Município Completo,Nome_Município\n"
        + "３３,Rio de Janeiro,1,1,1,1,００１００,３３００１００９,Campos\n",
        encoding="utf-8",
    )

    import pytest

    with pytest.raises(ValueError, match="geocódigo municipal inválido"):
        parse_dtb_table(path, 2025)


def test_refresh_dtb_writes_release_and_active_pointer(tmp_path, monkeypatch):
    import app.pipeline.reference.ibge.refresh as refresh

    monkeypatch.setattr(refresh, "parse_dtb_archive", lambda archive, year: parse_dtb_table(FIXTURE, year))
    archive = tmp_path / "DTB_2025.zip"
    archive.write_bytes(b"official-fixture")
    result = refresh_from_dtb_archive(
        tmp_path / "reference", archive, catalog_id="ibge-dtb-2025",
        source_url="https://example.invalid/DTB_2025.zip", reference_year=2025,
        require_national=False,
    )
    assert result.exists()
    assert (tmp_path / "reference/active.json").exists()
    assert "ibge-dtb-2025" in (tmp_path / "reference/releases/ibge-dtb-2025/manifest.json").read_text()


def test_refresh_dtb_rejeita_candidata_nacional_incompleta(tmp_path, monkeypatch):
    import pytest
    import app.pipeline.reference.ibge.refresh as refresh

    monkeypatch.setattr(refresh, "parse_dtb_archive", lambda archive, year: parse_dtb_table(FIXTURE, year))
    archive = tmp_path / "DTB_2025.zip"
    archive.write_bytes(b"official-fixture")

    with pytest.raises(ValueError, match="catálogo nacional incompleto"):
        refresh_from_dtb_archive(
            tmp_path / "reference", archive, catalog_id="ibge-dtb-2025",
            source_url="https://example.invalid/DTB_2025.zip", reference_year=2025,
        )


def test_refresh_api_release_has_logical_hash(tmp_path, mocker):
    client = mocker.Mock()
    client.fetch_municipalities.return_value = parse_dtb_table(FIXTURE, 2025)
    refresh_from_localidades(
        tmp_path / "reference", catalog_id="ibge-api-test", source_url="https://example.invalid",
        reference_year=2025, client=client,
        require_national=False,
    )
    manifest = (tmp_path / "reference/releases/ibge-api-test/manifest.json").read_text()
    assert '"sha256": ""' not in manifest
