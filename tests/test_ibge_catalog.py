from app.pipeline.reference.ibge.catalog import InMemoryMunicipalityCatalog
from app.pipeline.reference.ibge.models import CatalogMetadata, Municipality, ResolutionStatus
from app.pipeline.reference.ibge.validation import validate_municipalities
from app.pipeline.reference.ibge.client import IbgeLocalidadesClient
from app.pipeline.reference.ibge.storage import promote_active, write_catalog
from app.pipeline.reference.ibge.refresh import download_dtb_archive
from app.pipeline.scope import legacy_rj_scope, select_scope


METADATA = CatalogMetadata("test", 2025, "fixture", "fixture://dtb", "2026-01-01T00:00:00Z", "hash")


def municipality(code7, name, uf_code="33", uf_abbr="RJ"):
    return Municipality(code7, code7[:6], name, uf_code, uf_abbr, uf_abbr, 2025)


def catalog():
    return InMemoryMunicipalityCatalog(
        [
            municipality("3301009", "Campos"),
            municipality("3305000", "São João da Barra"),
            municipality("3302205", "Itaperuna"),
            municipality("3302403", "Macaé"),
            municipality("3550308", "São Paulo", "35", "SP"),
        ],
        METADATA,
    )


def test_resolve_codes_and_rejects_invalid_code():
    value = catalog()
    assert value.resolve("330100").municipality.code7 == "3301009"
    assert value.resolve("3301009").status is ResolutionStatus.VALID
    assert value.resolve("0330100").municipality.code7 == "3301009"
    assert value.resolve("3301008").status is ResolutionStatus.UNKNOWN_CODE
    assert value.resolve("Bom Jesus").status is ResolutionStatus.INVALID_FORMAT


def test_resolve_detects_uf_mismatch():
    result = catalog().resolve("330100", declared_uf="35")
    assert result.status is ResolutionStatus.UF_MISMATCH


def test_legacy_scope_preserves_four_rj_municipalities():
    scope = legacy_rj_scope(catalog())
    assert scope.codes7 == {"3301009", "3305000", "3302205", "3302403"}


def test_scope_can_select_uf_or_municipalities_but_not_both():
    value = catalog()
    assert select_scope(value, ufs=["SP"]).codes7 == {"3550308"}
    assert select_scope(value, municipalities=["330100"]).codes7 == {"3301009"}
    try:
        select_scope(value, ufs=["RJ"], all_brazil=True)
    except ValueError as error:
        assert "apenas uma" in str(error)
    else:
        raise AssertionError("escopo ambíguo deveria falhar")


def test_catalog_rejects_ambiguous_crosswalk():
    records = [municipality("3301009", "Campos"), municipality("3301008", "Outro")]
    try:
        validate_municipalities(records)
    except ValueError as error:
        assert "code6" in str(error)
    else:
        raise AssertionError("crosswalk ambíguo deveria falhar")


def test_storage_writes_parquet_and_active_pointer(tmp_path):
    destination = write_catalog(tmp_path / "municipalities.parquet", [municipality("3301009", "Campos")])
    assert destination.exists()
    promote_active(tmp_path / "active.json", "test")
    assert '"catalog_id": "test"' in (tmp_path / "active.json").read_text()


def test_localidades_client_validates_and_parses_response(mocker):
    session = mocker.Mock()
    session.get.return_value.json.return_value = [{
        "id": 3301009,
        "nome": "Campos",
        "microrregiao": {"mesorregiao": {"UF": {"id": 33, "sigla": "RJ", "nome": "Rio"}}},
    }]
    result = IbgeLocalidadesClient(session=session).fetch_municipalities()
    assert result[0].code7 == "3301009"
    session.get.assert_called_once()


def test_download_dtb_archive_promotes_only_matching_hash(tmp_path, mocker):
    response = mocker.Mock()
    response.iter_content.return_value = [b"DTB", b"-2025"]
    session = mocker.Mock()
    session.get.return_value = response
    expected = __import__("hashlib").sha256(b"DTB-2025").hexdigest()

    result = download_dtb_archive(
        tmp_path, url="https://example.invalid/DTB_2025.zip",
        reference_year=2025, expected_sha256=expected, session=session,
    )

    assert result.read_bytes() == b"DTB-2025"
    assert not list(result.parent.glob("*.tmp"))


def test_download_dtb_archive_rejects_hash_without_replacing_previous(tmp_path, mocker):
    destination = tmp_path / "raw" / "dtb_2025" / "DTB_2025.zip"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"previous")
    response = mocker.Mock()
    response.iter_content.return_value = [b"new"]
    session = mocker.Mock()
    session.get.return_value = response

    try:
        download_dtb_archive(
            tmp_path, url="https://example.invalid/DTB_2025.zip",
            reference_year=2025, expected_sha256="0" * 64, session=session,
        )
    except ValueError as error:
        assert "SHA-256" in str(error)
    else:
        raise AssertionError("hash divergente deveria rejeitar a DTB")
    assert destination.read_bytes() == b"previous"
