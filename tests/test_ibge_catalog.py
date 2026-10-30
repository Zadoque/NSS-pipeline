from dataclasses import replace

import pytest

from app.pipeline.reference.ibge.catalog import InMemoryMunicipalityCatalog, ParquetMunicipalityCatalog
from app.pipeline.reference.ibge.models import CatalogMetadata, Municipality, ResolutionStatus
from app.pipeline.reference.ibge.validation import validate_municipalities
from app.pipeline.reference.ibge.client import IbgeLocalidadesClient
from app.pipeline.reference.ibge.storage import (
    load_active_catalog,
    promote_active,
    write_catalog,
    write_manifest,
)
from app.pipeline.reference.ibge.refresh import (
    download_dtb_archive,
    refresh_from_dtb_archive,
    refresh_from_localidades,
)
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
    assert catalog().resolve("330100", declared_uf=" rj ").status is ResolutionStatus.VALID


@pytest.mark.parametrize("value", [None, "", "33010", "33010099", "33A100"])
def test_resolve_rejects_missing_or_malformed_codes(value):
    result = catalog().resolve(value)
    assert result.status is ResolutionStatus.INVALID_FORMAT
    assert result.reason in {"código não numérico", "formato esperado: 6 ou 7 dígitos"}


def test_resolve_none_keeps_empty_original_and_format_reason():
    result = catalog().resolve(None)
    assert result.original_code == ""
    assert result.input_format is None
    assert result.reason == "código não numérico"


def test_resolve_distinguishes_unknown_code_and_preserves_input_context():
    result = catalog().resolve("999999")
    assert result.status is ResolutionStatus.UNKNOWN_CODE
    assert result.original_code == "999999"
    assert result.input_format == "CODE6"
    assert "ausente" in result.reason


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


def test_validation_rejects_empty_catalog_with_contract_message():
    with pytest.raises(ValueError, match="catálogo municipal vazio"):
        validate_municipalities([])


def test_validation_rejects_duplicate_code7():
    record = municipality("3301009", "Campos")
    with pytest.raises(ValueError, match="code7 duplicado"):
        validate_municipalities([record, record])


@pytest.mark.parametrize(
    "record, message",
    [
        (replace(municipality("3301009", "Campos"), code7="330100"), "código municipal inválido"),
        (replace(municipality("3301009", "Campos"), code6="33010"), "código municipal inválido"),
        (replace(municipality("3301009", "Campos"), code6="330101"), "crosswalk inconsistente"),
        (replace(municipality("3301009", "Campos"), uf_code="35"), "UF inconsistente"),
        (replace(municipality("3301009", "Campos"), name=""), "atributo obrigatório"),
        (replace(municipality("3301009", "Campos"), uf_abbr=""), "atributo obrigatório"),
    ],
)
def test_validation_rejects_invalid_canonical_attributes(record, message):
    with pytest.raises(ValueError, match=message):
        validate_municipalities([record])


def test_storage_writes_parquet_and_active_pointer(tmp_path):
    destination = write_catalog(tmp_path / "municipalities.parquet", [municipality("3301009", "Campos")])
    assert destination.exists()
    loaded = ParquetMunicipalityCatalog(destination, METADATA)
    assert loaded.get_municipality("3301009").name == "Campos"
    promote_active(tmp_path / "active.json", "test")
    assert '"catalog_id": "test"' in (tmp_path / "active.json").read_text()


def test_storage_round_trip_loads_active_catalog(tmp_path):
    release = tmp_path / "releases" / "test"
    write_catalog(release / "municipalities.parquet", [municipality("3301009", "Campos")])
    write_manifest(release / "manifest.json", METADATA)
    promote_active(tmp_path / "active.json", "test")

    loaded = load_active_catalog(tmp_path)
    assert loaded.metadata.catalog_id == "test"
    assert loaded.get_municipality("3301009").name == "Campos"


@pytest.mark.parametrize(
    ("active_id", "manifest_id", "validation_status", "message"),
    [
        ("release", "release", "PENDING", "não está validada"),
        ("release", "other", "VALIDATED", "diverge"),
        ("../outside", "../outside", "VALIDATED", "não informa"),
    ],
)
def test_active_catalog_rejects_untrusted_pointer_and_manifest(
    tmp_path, active_id, manifest_id, validation_status, message,
):
    release = tmp_path / "releases" / "release"
    release.mkdir(parents=True)
    (tmp_path / "active.json").write_text(
        __import__("json").dumps({"catalog_id": active_id}), encoding="utf-8"
    )
    (release / "manifest.json").write_text(__import__("json").dumps({
        "catalog_id": manifest_id,
        "reference_year": 2025,
        "source_name": "fixture",
        "source_url": "fixture://catalog",
        "retrieved_at": "2026-01-01T00:00:00Z",
        "sha256": "a" * 64,
        "validation_status": validation_status,
    }), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_active_catalog(tmp_path)


def test_load_active_catalog_rejects_pointer_without_release_id(tmp_path):
    (tmp_path / "active.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="catalog_id"):
        load_active_catalog(tmp_path)


def test_storage_atomic_metadata_cleanup_on_replace_failure(tmp_path, mocker):
    manifest = tmp_path / "manifest.json"
    mocker.patch("app.pipeline.reference.ibge.storage.os.replace", side_effect=OSError("disk full"))
    with pytest.raises(OSError, match="disk full"):
        write_manifest(manifest, METADATA)
    assert not list(tmp_path.glob("*.tmp"))

    active = tmp_path / "active.json"
    with pytest.raises(OSError, match="disk full"):
        promote_active(active, "test")
    assert not list(tmp_path.glob("*.tmp"))


def test_localidades_client_validates_and_parses_response(mocker):
    session = mocker.Mock()
    session.get.return_value.json.return_value = [{
        "id": 3301009,
        "nome": "Campos",
        "microrregiao": {"mesorregiao": {"UF": {"id": 33, "sigla": "RJ", "nome": "Rio"}}},
    }]
    result = IbgeLocalidadesClient(session=session).fetch_municipalities()
    assert result[0].code7 == "3301009"
    session.get.assert_called_once_with(
        "https://servicodados.ibge.gov.br/api/v1/localidades/municipios", timeout=60
    )


@pytest.mark.parametrize("payload", [{}, [None]])
def test_localidades_client_rejects_invalid_payload_or_record(mocker, payload):
    session = mocker.Mock()
    session.get.return_value.json.return_value = payload
    with pytest.raises(ValueError, match="IBGE|registro"):
        IbgeLocalidadesClient(session=session).fetch_municipalities()


def test_localidades_client_rejects_missing_administrative_fields(mocker):
    session = mocker.Mock()
    session.get.return_value.json.return_value = [{"id": 3301009, "nome": "Campos"}]
    with pytest.raises(ValueError, match="administrativos"):
        IbgeLocalidadesClient(session=session).fetch_municipalities()


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


def test_refresh_from_localidades_promotes_release_and_active_pointer(tmp_path):
    class Client:
        def fetch_municipalities(self):
            return (municipality("3301009", "Campos"),)

    result = refresh_from_localidades(
        tmp_path,
        catalog_id="ibge-api-test",
        source_url="https://example.invalid/municipios",
        reference_year=2025,
        client=Client(),
    )
    assert result.exists()
    loaded = load_active_catalog(tmp_path)
    assert loaded.metadata.catalog_id == "ibge-api-test"
    assert len(loaded.municipalities()) == 1
    assert len(loaded.metadata.sha256) == 64


def test_refresh_from_dtb_archive_hashes_raw_artifact(tmp_path, mocker):
    archive = tmp_path / "DTB_2025.zip"
    archive.write_bytes(b"official-dtb-fixture")
    mocker.patch(
        "app.pipeline.reference.ibge.refresh.parse_dtb_archive",
        return_value=[municipality("3301009", "Campos")],
    )
    result = refresh_from_dtb_archive(
        tmp_path,
        archive,
        catalog_id="ibge-dtb-test",
        source_url="https://example.invalid/DTB_2025.zip",
        reference_year=2025,
    )
    manifest = result.with_name("manifest.json").read_text(encoding="utf-8")
    assert result.exists()
    assert __import__("hashlib").sha256(b"official-dtb-fixture").hexdigest() in manifest
    assert load_active_catalog(tmp_path).metadata.catalog_id == "ibge-dtb-test"
from dataclasses import replace

import pytest
