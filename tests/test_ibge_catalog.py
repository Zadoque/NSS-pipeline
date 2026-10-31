from dataclasses import replace
import sys

import pytest

from app.pipeline.reference.ibge.catalog import (
    InMemoryMunicipalityCatalog,
    ParquetMunicipalityCatalog,
    _as_municipality,
)
from app.pipeline.reference.ibge.models import (
    CatalogMetadata, Municipality, ResolutionResult, ResolutionStatus,
)
from app.pipeline.reference.ibge.validation import (
    inspect_municipalities,
    validate_municipalities,
    validate_national_municipalities,
)
from app.pipeline.reference.ibge.client import DEFAULT_MUNICIPALITIES_URL, IbgeLocalidadesClient
from app.pipeline.reference.ibge.storage import (
    catalog_content_sha256,
    load_active_catalog,
    promote_active,
    write_catalog,
    write_manifest,
    write_release,
)
from app.pipeline.reference.ibge.refresh import (
    download_dtb_archive,
    refresh_from_dtb_url,
    refresh_from_dtb_archive,
    refresh_from_localidades,
    main as refresh_main,
)
from app.pipeline.scope import legacy_rj_mapping, legacy_rj_scope, select_scope


METADATA = CatalogMetadata("test", 2025, "fixture", "fixture://dtb", "2026-01-01T00:00:00Z", "a" * 64)


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
    resolved_code6 = value.resolve("330100")
    assert resolved_code6.status is ResolutionStatus.VALID
    assert resolved_code6.input_format == "CODE6"
    assert resolved_code6.municipality == municipality("3301009", "Campos")
    resolved_code7 = value.resolve("3301009")
    assert resolved_code7.status is ResolutionStatus.VALID
    assert resolved_code7.input_format == "CODE7"
    assert resolved_code7.municipality == municipality("3301009", "Campos")
    legacy = value.resolve("0330100")
    assert legacy.municipality.code7 == "3301009"
    assert legacy.input_format == "LEGACY_CODE6"
    assert value.resolve("1330100").status is ResolutionStatus.UNKNOWN_CODE
    assert value.resolve("3301008").status is ResolutionStatus.UNKNOWN_CODE
    assert value.resolve("Bom Jesus").status is ResolutionStatus.INVALID_FORMAT


def test_resolve_detects_uf_mismatch():
    result = catalog().resolve("330100", declared_uf="35")
    assert result.status is ResolutionStatus.UF_MISMATCH
    assert catalog().resolve("330100", declared_uf=" rj ").status is ResolutionStatus.VALID


def test_resolve_does_not_apply_current_release_to_another_year():
    result = catalog().resolve("330100", reference_year=2024)
    assert result.status is ResolutionStatus.HISTORICAL_UNRESOLVED
    assert result.municipality.code7 == "3301009"
    assert "2024" in result.reason


@pytest.mark.parametrize("value", [None, "", "33010", "33010099", "33A100", "３３０１００"])
def test_resolve_rejects_missing_or_malformed_codes(value):
    result = catalog().resolve(value)
    assert result.status is ResolutionStatus.INVALID_FORMAT
    assert result.reason in {"código não numérico", "formato esperado: 6 ou 7 dígitos"}


def test_resolve_none_keeps_empty_original_and_format_reason():
    result = catalog().resolve(None)
    assert result.original_code == ""
    assert result.input_format is None
    assert result.reason == "código não numérico"

    text = catalog().resolve("Bom Jesus")
    assert text.status is ResolutionStatus.INVALID_FORMAT
    assert text.input_format is None
    assert text.reason == "código não numérico"


def test_resolve_preserva_contexto_completo_em_cada_status():
    value = catalog()

    valid = value.resolve("330100")
    assert (valid.original_code, valid.input_format, valid.reason) == (
        "330100", "CODE6", None,
    )

    legacy = value.resolve("0330100")
    assert (legacy.original_code, legacy.input_format, legacy.reason) == (
        "0330100", "LEGACY_CODE6", None,
    )

    unknown = value.resolve("999999")
    assert (unknown.original_code, unknown.input_format, unknown.reason) == (
        "999999", "CODE6", "código ausente no catálogo",
    )

    invalid = value.resolve("33010099")
    assert (invalid.original_code, invalid.input_format, invalid.reason) == (
        "33010099", None, "formato esperado: 6 ou 7 dígitos",
    )

    mismatch = value.resolve("330100", declared_uf="35")
    assert mismatch.original_code == "330100"
    assert mismatch.input_format == "CODE6"
    assert mismatch.municipality.code7 == "3301009"
    assert mismatch.reason == "UF declarada diverge do catálogo"

    historical = value.resolve("330100", reference_year=2024)
    assert historical.original_code == "330100"
    assert historical.input_format == "CODE6"
    assert historical.municipality.code7 == "3301009"
    assert historical.reason == "release 2025 não resolve referência 2024"


def test_resolve_distinguishes_unknown_code_and_preserves_input_context():
    result = catalog().resolve("999999")
    assert result.status is ResolutionStatus.UNKNOWN_CODE
    assert result.original_code == "999999"
    assert result.input_format == "CODE6"
    assert result.reason == "código ausente no catálogo"


def test_legacy_scope_preserves_four_rj_municipalities():
    scope = legacy_rj_scope(catalog())
    assert scope.codes7 == {"3301009", "3305000", "3302205", "3302403"}


def test_legacy_scope_reports_the_missing_code_explicitly():
    incomplete = InMemoryMunicipalityCatalog(
        [
            municipality("3301009", "Campos"),
            municipality("3305000", "São João da Barra"),
            municipality("3302205", "Itaperuna"),
        ],
        METADATA,
    )

    with pytest.raises(ValueError, match="3302403"):
        legacy_rj_scope(incomplete)


def test_legacy_rj_mapping_is_owned_by_scope_and_isolated():
    mapping = legacy_rj_mapping()
    mapping.pop("3301009")
    assert "3301009" in legacy_rj_mapping()


def test_scope_can_select_uf_or_municipalities_but_not_both():
    value = catalog()
    selected_uf = select_scope(value, ufs=["SP"])
    assert selected_uf.codes7 == {"3550308"}
    assert selected_uf.kind == "UFs"
    assert select_scope(value, municipalities=["330100"]).codes7 == {"3301009"}
    with pytest.raises(ValueError) as error:
        select_scope(value, ufs=["RJ"], all_brazil=True)
    assert str(error.value) == "selecione apenas uma entre municípios, UFs ou Brasil inteiro"


def test_scope_can_select_all_brazil_with_explicit_kind():
    selected = select_scope(catalog(), all_brazil=True)
    assert selected.kind == "BRAZIL"
    assert selected.count == 5
    assert selected.codes7 == {"3301009", "3305000", "3302205", "3302403", "3550308"}


def test_scope_rejects_unknown_uf_and_empty_municipal_selection():
    with pytest.raises(ValueError) as unknown_uf:
        select_scope(catalog(), ufs=["AC"])
    assert str(unknown_uf.value) == "nenhuma UF selecionada existe no catálogo"

    with pytest.raises(ValueError) as empty_municipalities:
        select_scope(catalog(), municipalities=[])
    assert str(empty_municipalities.value) == "o escopo municipal não pode ser vazio"


def test_scope_rejects_invalid_municipality_with_complete_reason():
    with pytest.raises(ValueError) as error:
        select_scope(catalog(), municipalities=["999999"])
    assert str(error.value) == (
        "município inválido no escopo: 999999 "
        "(UNKNOWN_CODE)"
    )


def test_scope_rejects_non_valid_resolution_even_with_candidate(monkeypatch):
    value = catalog()
    candidate = municipality("3301009", "Campos")
    monkeypatch.setattr(
        value,
        "resolve",
        lambda code: ResolutionResult(
            str(code), "CODE6", ResolutionStatus.UNKNOWN_CODE, candidate,
            "código ausente no catálogo",
        ),
    )

    with pytest.raises(ValueError) as error:
        select_scope(value, municipalities=["330100"])
    assert str(error.value) == "município inválido no escopo: 330100 (UNKNOWN_CODE)"


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


def test_catalog_validation_report_exposes_quality_counts():
    report = catalog().validate()
    assert report.valid is True
    assert report.municipality_count == 5
    assert report.uf_count == 2
    assert report.code6_count == 5


def test_catalog_validation_report_preserves_error_without_throwing():
    report = inspect_municipalities((replace(municipality("3301009", "Campos"), code6="330101"),))
    assert report.valid is False
    assert report.municipality_count == 1
    assert report.errors == ("crosswalk inconsistente: 3301009/330101",)


def test_catalog_validation_report_preserves_error_text_for_empty_catalog():
    report = inspect_municipalities(())

    assert report.valid is False
    assert report.municipality_count == 0
    assert report.uf_count == 0
    assert report.code6_count == 0
    assert report.errors == ("catálogo municipal vazio",)


def test_national_validation_rejects_missing_uf():
    with pytest.raises(ValueError, match="UFs ausentes"):
        validate_national_municipalities([municipality("3301009", "Campos")])


def test_national_validation_rejects_catalog_truncated_with_all_ufs():
    records = [
        Municipality(
            f"{uf}00001", f"{uf}0000", f"Município {uf}", uf, f"U{uf}",
            f"UF {uf}", 2025,
        )
        for uf in sorted({
            "11", "12", "13", "14", "15", "16", "17", "21", "22", "23",
            "24", "25", "26", "27", "28", "29", "31", "32", "33", "35",
            "41", "42", "43", "50", "51", "52", "53",
        })
    ]

    with pytest.raises(ValueError) as error:
        validate_national_municipalities(records)
    assert str(error.value) == (
        "catálogo nacional incompleto; quantidade de municípios abaixo do "
        "mínimo esperado (5500): 27"
    )


def test_national_validation_accepts_exact_minimum_boundary():
    uf_codes = sorted({
        "11", "12", "13", "14", "15", "16", "17", "21", "22", "23",
        "24", "25", "26", "27", "28", "29", "31", "32", "33", "35",
        "41", "42", "43", "50", "51", "52", "53",
    })
    records = []
    for index in range(5500):
        uf = uf_codes[index % len(uf_codes)]
        local = index // len(uf_codes) + 1
        code6 = f"{uf}{local:04d}"
        code7 = f"{code6}{index % 10}"
        records.append(
            Municipality(
                code7, code6, f"Município {index}", uf, f"U{uf}",
                f"UF {uf}", 2025,
            )
        )

    result = validate_national_municipalities(records)

    assert len(result) == 5500


def test_validation_rejects_duplicate_code7():
    record = municipality("3301009", "Campos")
    with pytest.raises(ValueError, match="code7 duplicado"):
        validate_municipalities([record, record])


def test_validation_rejects_conflicting_uf_identity():
    records = [
        Municipality("3301009", "330100", "Campos", "33", "RJ", "Rio de Janeiro", 2025),
        Municipality("3302205", "330220", "Itaperuna", "33", "XX", "Rio de Janeiro", 2025),
    ]
    with pytest.raises(ValueError, match="identidade da UF"):
        validate_municipalities(records)


def test_validation_compares_uf_abbreviation_case_insensitively():
    records = [
        Municipality("3301009", "330100", "Campos", "33", "RJ", "Rio de Janeiro", 2025),
        Municipality("3302205", "330220", "Itaperuna", "33", "rj", "Rio de Janeiro", 2025),
    ]

    assert validate_municipalities(records) == tuple(records)


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
    release = tmp_path / "releases" / "test"
    destination = write_catalog(release / "municipalities.parquet", [municipality("3301009", "Campos")])
    write_manifest(release / "manifest.json", METADATA)
    assert destination.exists()
    loaded = ParquetMunicipalityCatalog(destination, METADATA)
    assert loaded.get_municipality("3301009").name == "Campos"
    promote_active(tmp_path / "active.json", "test")
    assert '"catalog_id": "test"' in (tmp_path / "active.json").read_text()


def test_catalog_converte_mapping_em_municipio_com_atributos_opcionais():
    result = _as_municipality({
        "code7": "3301009",
        "code6": "330100",
        "name": "Campos",
        "uf_code": "33",
        "uf_abbr": "RJ",
        "uf_name": "Rio de Janeiro",
        "reference_year": "2025",
    })

    assert result == Municipality(
        "3301009", "330100", "Campos", "33", "RJ", "Rio de Janeiro", 2025,
    )


def test_catalog_preserva_fonte_e_tipo_administrativo_do_mapping():
    result = _as_municipality({
        "code7": "5300108",
        "code6": "530010",
        "name": "Brasília",
        "uf_code": "53",
        "uf_abbr": "DF",
        "uf_name": "Distrito Federal",
        "reference_year": 2025,
        "source": "IBGE_API_LOCALIDADES",
        "administrative_type": "FEDERAL_DISTRICT",
    })

    assert result.source == "IBGE_API_LOCALIDADES"
    assert result.administrative_type == "FEDERAL_DISTRICT"


def test_catalog_content_hash_is_canonical_and_sensitive_to_attributes():
    records = [
        municipality("3550308", "São Paulo", "35", "SP"),
        municipality("3301009", "Campos"),
    ]

    digest = catalog_content_sha256(records)

    assert digest == "10c4dca16a710a069ee83021506c75f6be1bafb923e899fd5b2378055ad1a500"
    assert digest == catalog_content_sha256(list(reversed(records)))
    assert digest != catalog_content_sha256([
        replace(records[0], name="São Paulo alterado"), records[1],
    ])


def test_promote_active_rejeita_release_inexistente_sem_trocar_ponteiro(tmp_path):
    active = tmp_path / "active.json"
    active.write_text('{"catalog_id": "old"}', encoding="utf-8")

    with pytest.raises(ValueError, match="manifesto da release ausente"):
        promote_active(active, "missing")

    assert active.read_text(encoding="utf-8") == '{"catalog_id": "old"}'
    assert not list(tmp_path.glob(".active.json.tmp"))


def test_storage_writes_ufs_and_crosswalk_artifacts(tmp_path):
    records = [municipality("3301009", "Campos"), municipality("3550308", "São Paulo", "35", "SP")]
    release = tmp_path / "release"
    write_release(release, records)

    assert len(__import__("pandas").read_parquet(release / "ufs.parquet")) == 2
    crosswalk = __import__("pandas").read_parquet(release / "code_crosswalk.parquet")
    assert set(crosswalk["code6"]) == {"330100", "355030"}


def test_release_artifacts_are_sorted_by_canonical_keys(tmp_path):
    records = [municipality("3550308", "São Paulo", "35", "SP"), municipality("3301009", "Campos")]
    release = tmp_path / "release"
    write_release(release, records)

    municipalities = __import__("pandas").read_parquet(release / "municipalities.parquet")
    ufs = __import__("pandas").read_parquet(release / "ufs.parquet")
    crosswalk = __import__("pandas").read_parquet(release / "code_crosswalk.parquet")
    assert municipalities["code7"].tolist() == ["3301009", "3550308"]
    assert ufs["uf_code"].tolist() == ["33", "35"]
    assert crosswalk["code6"].tolist() == ["330100", "355030"]


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


def test_active_catalog_rejects_reference_year_mismatch(tmp_path):
    release = tmp_path / "releases" / "test"
    write_catalog(release / "municipalities.parquet", [
        Municipality("3301009", "330100", "Campos", "33", "RJ", "Rio", 2024),
    ])
    write_manifest(release / "manifest.json", METADATA)
    (tmp_path / "active.json").write_text('{"catalog_id": "test"}', encoding="utf-8")

    with pytest.raises(ValueError, match="reference_year"):
        load_active_catalog(tmp_path)


def test_active_catalog_rejects_tampered_parquet_content_hash(tmp_path):
    records = [municipality("3301009", "Campos")]
    release = tmp_path / "releases" / "test"
    write_catalog(release / "municipalities.parquet", records)
    write_manifest(
        release / "manifest.json",
        replace(METADATA, content_sha256=catalog_content_sha256(records)),
    )
    promote_active(tmp_path / "active.json", "test")
    frame = __import__("pandas").read_parquet(release / "municipalities.parquet")
    frame.loc[0, "name"] = "Nome adulterado"
    frame.to_parquet(release / "municipalities.parquet", index=False)

    with pytest.raises(ValueError, match="hash lógico"):
        load_active_catalog(tmp_path)


def test_load_active_catalog_rejects_pointer_without_release_id(tmp_path):
    (tmp_path / "active.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="catalog_id"):
        load_active_catalog(tmp_path)


@pytest.mark.parametrize("payload", ["null", "[]", '"release"'])
def test_load_active_catalog_rejects_pointer_with_non_object_root(tmp_path, payload):
    (tmp_path / "active.json").write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match="ponteiro ativo inválido"):
        load_active_catalog(tmp_path)


def test_storage_atomic_metadata_cleanup_on_replace_failure(tmp_path, mocker):
    release = tmp_path / "releases" / "test"
    write_catalog(release / "municipalities.parquet", [municipality("3301009", "Campos")])
    write_manifest(release / "manifest.json", METADATA)
    manifest = tmp_path / "manifest.json"
    mocker.patch("app.pipeline.reference.ibge.storage.os.replace", side_effect=OSError("disk full"))
    with pytest.raises(OSError, match="disk full"):
        write_manifest(manifest, METADATA)
    assert not list(tmp_path.glob("*.tmp"))
    active = tmp_path / "active.json"
    with pytest.raises(OSError, match="disk full"):
        promote_active(active, "test")
    assert not list(tmp_path.glob("*.tmp"))


def test_storage_rejects_non_sha256_manifest(tmp_path):
    with pytest.raises(ValueError, match="SHA-256"):
        write_manifest(
            tmp_path / "manifest.json",
            CatalogMetadata("test", 2025, "fixture", "fixture://", "2026-01-01T00:00:00Z", "hash"),
        )


@pytest.mark.parametrize(
    ("metadata", "message"),
    [
        (replace(METADATA, catalog_id=""), "manifesto IBGE exige SHA-256 hexadecimal de 64 caracteres"),
        (replace(METADATA, sha256="a" * 63), "manifesto IBGE exige SHA-256 hexadecimal de 64 caracteres"),
        (replace(METADATA, sha256="g" * 64), "manifesto IBGE exige SHA-256 hexadecimal de 64 caracteres"),
        (replace(METADATA, content_sha256="b" * 63), "manifesto IBGE exige hash lógico hexadecimal de 64 caracteres"),
        (replace(METADATA, content_sha256="G" * 64), "manifesto IBGE exige hash lógico hexadecimal de 64 caracteres"),
        (replace(METADATA, validation_status="PENDING"), "release IBGE não está validada"),
    ],
)
def test_storage_rejeita_metadados_de_release_invalidos(tmp_path, metadata, message):
    with pytest.raises(ValueError, match=f"^{message}$"):
        write_manifest(tmp_path / "manifest.json", metadata)


@pytest.mark.parametrize("promoted_at", ["not-a-timestamp", 42])
def test_storage_rejeita_promoted_at_invalido(tmp_path, promoted_at):
    with pytest.raises(ValueError, match="^manifesto IBGE exige promoted_at ISO-8601$"):
        write_manifest(
            tmp_path / "manifest.json",
            replace(METADATA, promoted_at=promoted_at),
        )


def test_storage_aceita_hash_logico_ausente():
    from app.pipeline.reference.ibge.storage import _validate_metadata

    _validate_metadata(METADATA)


def test_localidades_client_validates_and_parses_response(mocker):
    session = mocker.Mock()
    session.get.return_value.json.return_value = [{
        "id": 3301009,
        "nome": "Campos",
        "microrregiao": {"mesorregiao": {"UF": {"id": 33, "sigla": "RJ", "nome": "Rio"}}},
    }]
    result = IbgeLocalidadesClient(session=session).fetch_municipalities()
    assert result[0].code7 == "3301009"
    assert result[0].code6 == "330100"
    assert result[0].uf_code == "33"
    assert result[0].uf_name == "Rio"
    assert result[0].reference_year == 0
    assert result[0].source == "IBGE_API_LOCALIDADES"
    parsed = IbgeLocalidadesClient._parse({
        "id": 3301009,
        "nome": "Campos",
        "microrregiao": {"mesorregiao": {"UF": {"id": 33, "sigla": "RJ", "nome": "Rio"}}},
    })
    assert parsed.uf_code == "33"
    assert parsed.reference_year == 0
    session.get.assert_called_once_with(
        "https://servicodados.ibge.gov.br/api/v1/localidades/municipios", timeout=60
    )


def test_localidades_client_faz_fallback_para_hierarquia_de_regiao_imediata(mocker):
    session = mocker.Mock()
    session.get.return_value.json.return_value = [{
        "id": 5101837,
        "nome": "Boa Esperança do Norte",
        "microrregiao": None,
        "regiao-imediata": {
            "regiao-intermediaria": {
                "UF": {"id": 51, "sigla": "MT", "nome": "Mato Grosso"},
            },
        },
    }]

    result = IbgeLocalidadesClient(session=session).fetch_municipalities()

    assert result[0].code7 == "5101837"
    assert result[0].uf_abbr == "MT"
    assert result[0].uf_name == "Mato Grosso"
    assert result[0].source == "IBGE_API_LOCALIDADES"


def test_localidades_client_normaliza_url_e_ownership_da_sessao(mocker):
    session = mocker.Mock()
    client = IbgeLocalidadesClient(session=session, base_url="https://example.invalid/X///")

    assert client.base_url == "https://example.invalid/X"
    assert client._owns_session is False
    client.close()
    session.close.assert_not_called()

    owned_session = mocker.Mock()
    mocker.patch("app.pipeline.reference.ibge.client.requests.Session", return_value=owned_session)
    owned = IbgeLocalidadesClient()
    assert owned._owns_session is True
    owned.close()
    owned_session.close.assert_called_once_with()


def test_localidades_client_rejects_non_array_payload(mocker):
    session = mocker.Mock()
    session.get.return_value.json.return_value = {}
    with pytest.raises(ValueError, match="^resposta IBGE inválida: esperado um array de municípios$"):
        IbgeLocalidadesClient(session=session).fetch_municipalities()


def test_localidades_client_rejects_non_object_record(mocker):
    session = mocker.Mock()
    session.get.return_value.json.return_value = [None]
    with pytest.raises(ValueError, match="^registro IBGE inválido$"):
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
    assert result.parent == tmp_path / "raw" / "dtb_2025"
    session.get.assert_called_once_with(
        "https://example.invalid/DTB_2025.zip", stream=True, timeout=120,
    )
    response.iter_content.assert_called_once_with(chunk_size=1024 * 1024)
    response.close.assert_called_once_with()
    assert not list(result.parent.glob("*.tmp"))


def test_download_dtb_archive_fecha_sessao_criada_internamente(tmp_path, mocker):
    response = mocker.Mock()
    response.iter_content.return_value = [b"DTB-2025"]
    session = mocker.Mock()
    session.get.return_value = response
    mocker.patch("app.pipeline.reference.ibge.refresh.requests.Session", return_value=session)
    expected = __import__("hashlib").sha256(b"DTB-2025").hexdigest()

    result = download_dtb_archive(
        tmp_path, url="https://example.invalid/DTB_2025.zip",
        reference_year=2025, expected_sha256=expected,
    )

    assert result.exists()
    session.close.assert_called_once_with()


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


def test_download_dtb_archive_closes_response_after_http_error(tmp_path, mocker):
    response = mocker.Mock()
    response.raise_for_status.side_effect = RuntimeError("http failure")
    session = mocker.Mock()
    session.get.return_value = response

    with pytest.raises(RuntimeError, match="http failure"):
        download_dtb_archive(
            tmp_path, url="https://example.invalid/DTB_2025.zip",
            reference_year=2025, session=session,
        )

    response.close.assert_called_once_with()
    assert not list((tmp_path / "raw" / "dtb_2025").glob("*.tmp"))


def test_download_dtb_archive_cleans_temporary_after_stream_error(tmp_path, mocker):
    response = mocker.Mock()
    response.iter_content.side_effect = OSError("stream interrupted")
    session = mocker.Mock()
    session.get.return_value = response

    with pytest.raises(OSError, match="stream interrupted"):
        download_dtb_archive(
            tmp_path, url="https://example.invalid/DTB_2025.zip",
            reference_year=2025, session=session,
        )

    response.close.assert_called_once_with()
    assert not list((tmp_path / "raw" / "dtb_2025").glob("*.tmp"))


def test_download_dtb_archive_cleans_temporary_after_atomic_replace_error(tmp_path, mocker):
    import app.pipeline.reference.ibge.refresh as refresh

    response = mocker.Mock()
    response.iter_content.return_value = [b"archive"]
    session = mocker.Mock()
    session.get.return_value = response
    mocker.patch.object(refresh.os, "replace", side_effect=OSError("replace failed"))

    with pytest.raises(OSError, match="replace failed"):
        download_dtb_archive(
            tmp_path, url="https://example.invalid/DTB_2025.zip",
            reference_year=2025, session=session,
        )

    response.close.assert_called_once_with()
    assert not list((tmp_path / "raw" / "dtb_2025").glob("*.tmp"))


def test_refresh_from_localidades_promotes_release_and_active_pointer(tmp_path):
    class Client:
        def fetch_municipalities(self):
            return (municipality("3301009", "Campos"),)

    result = refresh_from_localidades(
        tmp_path,
        catalog_id="ibge-api-test",
        source_url="https://example.invalid/municipios",
        reference_year=2025,
        client=Client(), require_national=False,
    )
    assert result.exists()
    manifest = __import__("json").loads(
        result.with_name("manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["promoted_at"]
    assert (result.parent / "ufs.parquet").exists()
    assert (result.parent / "code_crosswalk.parquet").exists()
    loaded = load_active_catalog(tmp_path)
    assert loaded.metadata.catalog_id == "ibge-api-test"
    assert len(loaded.municipalities()) == 1
    assert loaded.municipalities()[0].reference_year == 2025
    assert len(loaded.metadata.sha256) == 64


def test_refresh_from_localidades_fecha_cliente_próprio(mocker, tmp_path):
    client = mocker.patch("app.pipeline.reference.ibge.refresh.IbgeLocalidadesClient")
    client.return_value.fetch_municipalities.return_value = (
        municipality("3301009", "Campos"),
    )

    refresh_from_localidades(
        tmp_path, catalog_id="ibge-api-test", source_url="fixture://localidades",
        reference_year=2025, require_national=False,
    )

    client.return_value.close.assert_called_once_with()


def test_refresh_from_localidades_fecha_cliente_próprio_quando_fetch_falha(mocker, tmp_path):
    client = mocker.patch("app.pipeline.reference.ibge.refresh.IbgeLocalidadesClient")
    client.return_value.fetch_municipalities.side_effect = RuntimeError("api failure")

    with pytest.raises(RuntimeError, match="api failure"):
        refresh_from_localidades(
            tmp_path, catalog_id="ibge-api-test", source_url="fixture://localidades",
            reference_year=2025, require_national=False,
        )

    client.return_value.close.assert_called_once_with()


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
        reference_year=2025, require_national=False,
    )
    manifest = result.with_name("manifest.json").read_text(encoding="utf-8")
    assert result.exists()
    assert __import__("hashlib").sha256(b"official-dtb-fixture").hexdigest() in manifest
    assert load_active_catalog(tmp_path).metadata.catalog_id == "ibge-dtb-test"


def test_refresh_from_dtb_url_downloads_then_promotes_with_same_contract(tmp_path, mocker):
    archive = tmp_path / "raw" / "dtb_2025" / "DTB_2025.zip"
    downloaded = mocker.patch(
        "app.pipeline.reference.ibge.refresh.download_dtb_archive",
        return_value=archive,
    )
    promoted = mocker.patch(
        "app.pipeline.reference.ibge.refresh.refresh_from_dtb_archive",
        return_value=tmp_path / "releases" / "ibge-dtb-2025" / "municipalities.parquet",
    )
    session = mocker.Mock()

    result = refresh_from_dtb_url(
        tmp_path,
        url="https://example.invalid/DTB_2025.zip",
        catalog_id="ibge-dtb-2025",
        reference_year=2025,
        expected_sha256="a" * 64,
        session=session,
        timeout=45,
    )

    assert result == promoted.return_value
    downloaded.assert_called_once_with(
        tmp_path,
        url="https://example.invalid/DTB_2025.zip",
        reference_year=2025,
        expected_sha256="a" * 64,
        session=session, timeout=45,
    )
    promoted.assert_called_once_with(
        tmp_path, archive, catalog_id="ibge-dtb-2025",
        source_url="https://example.invalid/DTB_2025.zip", reference_year=2025,
        require_national=True,
    )


def test_refresh_rejects_catalog_id_reuse_with_different_hash(tmp_path, mocker):
    archive = tmp_path / "DTB_2025.zip"
    archive.write_bytes(b"first")
    records = [municipality("3301009", "Campos")]
    mocker.patch("app.pipeline.reference.ibge.refresh.parse_dtb_archive", return_value=records)
    refresh_from_dtb_archive(
        tmp_path, archive, catalog_id="immutable", source_url="fixture://dtb",
        reference_year=2025,
        require_national=False,
    )
    archive.write_bytes(b"second")
    with pytest.raises(ValueError, match="imutável"):
        refresh_from_dtb_archive(
            tmp_path, archive, catalog_id="immutable", source_url="fixture://dtb",
            reference_year=2025,
            require_national=False,
        )
    assert load_active_catalog(tmp_path).metadata.sha256 == __import__("hashlib").sha256(b"first").hexdigest()


def test_refresh_does_not_reuse_unvalidated_existing_release(tmp_path, mocker):
    archive = tmp_path / "DTB_2025.zip"
    archive.write_bytes(b"first")
    mocker.patch(
        "app.pipeline.reference.ibge.refresh.parse_dtb_archive",
        return_value=[municipality("3301009", "Campos")],
    )
    refresh_from_dtb_archive(
        tmp_path, archive, catalog_id="pending", source_url="fixture://dtb",
        reference_year=2025,
        require_national=False,
    )
    manifest = tmp_path / "releases" / "pending" / "manifest.json"
    content = __import__("json").loads(manifest.read_text(encoding="utf-8"))
    content["validation_status"] = "PENDING"
    manifest.write_text(__import__("json").dumps(content), encoding="utf-8")

    with pytest.raises(ValueError, match="não está validada"):
        refresh_from_dtb_archive(
            tmp_path, archive, catalog_id="pending", source_url="fixture://dtb",
            reference_year=2025,
            require_national=False,
        )


@pytest.mark.parametrize("manifest_body", ["{", '{"catalog_id": "other"}'])
def test_refresh_rejeita_release_existente_com_manifesto_invalido(tmp_path, mocker, manifest_body):
    archive = tmp_path / "DTB_2025.zip"
    archive.write_bytes(b"first")
    mocker.patch(
        "app.pipeline.reference.ibge.refresh.parse_dtb_archive",
        return_value=[municipality("3301009", "Campos")],
    )
    release = tmp_path / "releases" / "broken"
    release.mkdir(parents=True)
    (release / "municipalities.parquet").write_bytes(b"placeholder")
    (release / "manifest.json").write_text(manifest_body, encoding="utf-8")

    with pytest.raises(ValueError, match="manifesto"):
        refresh_from_dtb_archive(
            tmp_path, archive, catalog_id="broken", source_url="fixture://dtb",
            reference_year=2025, require_national=False,
        )


def test_refresh_rejeita_release_existente_incompleta(tmp_path, mocker):
    archive = tmp_path / "DTB_2025.zip"
    archive.write_bytes(b"first")
    mocker.patch(
        "app.pipeline.reference.ibge.refresh.parse_dtb_archive",
        return_value=[municipality("3301009", "Campos")],
    )
    (tmp_path / "releases" / "incomplete").mkdir(parents=True)

    with pytest.raises(ValueError, match="release incompleta"):
        refresh_from_dtb_archive(
            tmp_path, archive, catalog_id="incomplete", source_url="fixture://dtb",
            reference_year=2025, require_national=False,
        )


def test_refresh_promotes_release_as_a_whole_and_cleans_staging_on_failure(tmp_path, mocker):
    archive = tmp_path / "DTB_2025.zip"
    archive.write_bytes(b"first")
    mocker.patch(
        "app.pipeline.reference.ibge.refresh.parse_dtb_archive",
        return_value=[municipality("3301009", "Campos")],
    )
    mocker.patch(
        "app.pipeline.reference.ibge.refresh.write_manifest",
        side_effect=OSError("disk full"),
    )

    with pytest.raises(OSError, match="disk full"):
        refresh_from_dtb_archive(
            tmp_path, archive, catalog_id="atomic", source_url="fixture://dtb",
            reference_year=2025,
            require_national=False,
        )

    releases = tmp_path / "releases"
    assert not (releases / "atomic").exists()
    assert not list(releases.glob(".atomic.*"))
    assert not (tmp_path / "active.json").exists()


def test_refresh_rejects_catalog_id_path_traversal(tmp_path):
    archive = tmp_path / "DTB_2025.zip"
    archive.write_bytes(b"fixture")
    with pytest.raises(ValueError, match="catalog_id inválido"):
        refresh_from_dtb_archive(
            tmp_path, archive, catalog_id="../outside", source_url="fixture://dtb",
            reference_year=2025,
            require_national=False,
        )


def test_refresh_cli_promotes_local_dtb_archive(tmp_path, monkeypatch, mocker, capsys):
    archive = tmp_path / "DTB_2025.zip"
    archive.write_bytes(b"fixture")
    mocker.patch(
        "app.pipeline.reference.ibge.refresh.refresh_from_dtb_archive",
        return_value=tmp_path / "releases" / "ibge-dtb-2025" / "municipalities.parquet",
    )
    monkeypatch.setattr(sys, "argv", [
        "refresh", "--root", str(tmp_path / "catalog"),
        "--catalog-id", "ibge-dtb-2025", "--reference-year", "2025",
        "--dtb-archive", str(archive), "--source-url", "fixture://dtb",
    ])

    refresh_main()

    assert "municipalities.parquet" in capsys.readouterr().out


def test_refresh_cli_exige_source_url_para_arquivo_local(tmp_path, monkeypatch, capsys):
    archive = tmp_path / "DTB_2025.zip"
    archive.write_bytes(b"fixture")
    monkeypatch.setattr(sys, "argv", [
        "refresh", "--root", str(tmp_path / "catalog"),
        "--catalog-id", "ibge-dtb-2025", "--reference-year", "2025",
        "--dtb-archive", str(archive),
    ])

    with pytest.raises(SystemExit) as error:
        refresh_main()

    assert error.value.code == 2
    assert "--dtb-archive exige --source-url" in capsys.readouterr().err


def test_refresh_cli_forwards_dtb_url_and_hash(tmp_path, monkeypatch, mocker, capsys):
    expected = tmp_path / "releases" / "ibge-dtb-2025" / "municipalities.parquet"
    refresh = mocker.patch(
        "app.pipeline.reference.ibge.refresh.refresh_from_dtb_url",
        return_value=expected,
    )
    monkeypatch.setattr(sys, "argv", [
        "refresh", "--root", str(tmp_path / "catalog"),
        "--catalog-id", "ibge-dtb-2025", "--reference-year", "2025",
        "--dtb-url", "https://example.invalid/DTB_2025.zip",
        "--expected-sha256", "b" * 64, "--timeout", "45",
    ])

    refresh_main()

    refresh.assert_called_once_with(
        tmp_path / "catalog", url="https://example.invalid/DTB_2025.zip",
        catalog_id="ibge-dtb-2025", reference_year=2025,
        expected_sha256="b" * 64, timeout=45,
    )
    assert str(expected) in capsys.readouterr().out


def test_refresh_cli_forwards_localidades(tmp_path, monkeypatch, mocker, capsys):
    expected = tmp_path / "releases" / "ibge-api-2025" / "municipalities.parquet"
    refresh = mocker.patch(
        "app.pipeline.reference.ibge.refresh.refresh_from_localidades",
        return_value=expected,
    )
    monkeypatch.setattr(sys, "argv", [
        "refresh", "--root", str(tmp_path / "catalog"),
        "--catalog-id", "ibge-api-2025", "--reference-year", "2025",
        "--localidades", "--source-url", "https://example.invalid/municipios",
    ])

    refresh_main()

    refresh.assert_called_once_with(
        tmp_path / "catalog", catalog_id="ibge-api-2025",
        source_url="https://example.invalid/municipios", reference_year=2025,
    )
    assert str(expected) in capsys.readouterr().out


def test_refresh_cli_usa_url_padrao_da_api_localidades(tmp_path, monkeypatch, mocker, capsys):
    expected = tmp_path / "releases" / "ibge-api-2025" / "municipalities.parquet"
    refresh = mocker.patch(
        "app.pipeline.reference.ibge.refresh.refresh_from_localidades",
        return_value=expected,
    )
    monkeypatch.setattr(sys, "argv", [
        "refresh", "--root", str(tmp_path / "catalog"),
        "--catalog-id", "ibge-api-2025", "--reference-year", "2025",
        "--localidades",
    ])

    refresh_main()

    refresh.assert_called_once()
    assert refresh.call_args.kwargs["source_url"] == DEFAULT_MUNICIPALITIES_URL
    assert str(expected) in capsys.readouterr().out
from dataclasses import replace

import pytest
