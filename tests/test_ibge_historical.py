import pytest

from app.pipeline.reference.ibge.historical import (
    MunicipalityEvent,
    _read_events,
    _event_id,
    derive_annual_events,
    derive_annual_event_series,
    download_historical_source,
    parse_administrative_events,
    parse_historical_municipality_workbook,
    parse_toponymic_events,
    promote_administrative_events,
    promote_annual_dtb_events,
    promote_historical_source,
    promote_historical_municipality_workbook,
    promote_toponymic_events,
    validate_event_references,
    write_events,
)


def test_historical_events_are_explicit_and_versionable(tmp_path):
    result = write_events(tmp_path / "events.parquet", [
        MunicipalityEvent("event-1", "CREATION", "2025-01-01", None, "5101837"),
    ])
    assert result.exists()
    frame = __import__("pandas").read_parquet(result)
    assert frame.loc[0, "target_code7"] == "5101837"


def test_read_events_preserves_optional_fields_and_empty_missing_file(tmp_path):
    path = tmp_path / "events.parquet"
    event = MunicipalityEvent(
        "event-1", "RENAME", "2025-01-01", "3301009", "3301009",
        source_name="Nome antigo", target_name="Nome atual", source="fixture://history",
    )
    write_events(path, [event])

    assert _read_events(path) == [event]
    assert _read_events(tmp_path / "missing.parquet") == []


def test_write_events_materializes_order_deterministic(tmp_path):
    events = [
        MunicipalityEvent("later", "CREATION", "2025-01-02", None, "5101837"),
        MunicipalityEvent("earlier", "CREATION", "2025-01-01", None, "3301009"),
    ]
    first = write_events(tmp_path / "first.parquet", events)
    second = write_events(tmp_path / "second.parquet", list(reversed(events)))

    first_frame = __import__("pandas").read_parquet(first)
    second_frame = __import__("pandas").read_parquet(second)
    __import__("pandas").testing.assert_frame_equal(first_frame, second_frame)
    assert first_frame["event_id"].tolist() == ["earlier", "later"]


@pytest.mark.parametrize(
    "event",
    [
        MunicipalityEvent("", "CREATION", "2025-01-01", None, "5101837"),
        MunicipalityEvent("event-1", "CREATION", "2025-01-01", None, "5101837", source=""),
    ],
)
def test_write_events_exige_identidade_e_fonte(tmp_path, event):
    with pytest.raises(ValueError, match="(event_id obrigatório|fonte obrigatória)"):
        write_events(tmp_path / "events.parquet", [event])


def test_event_id_is_deterministic_delimited_and_fixed_width():
    assert _event_id("2025", "CREATION", "5101837") == "9287a6172fd94922cf52"
    assert _event_id("a", "bc") != _event_id("ab", "c")
    assert len(_event_id("2025", "CREATION", "5101837")) == 20


def test_parse_historical_workbook_promove_apenas_mudanca_com_mesmo_codigo(
    tmp_path, monkeypatch
):
    source = tmp_path / "pop_mun_TUR_1872_a_2010.xls"
    source.write_bytes(b"fixture")
    frame = __import__("pandas").DataFrame([
        {
            "cod.1991": "3301009", "Município 1991": "Campos",
            "cod.2000": "3301009", "Município 2000": "Campos dos Goytacazes",
            "cod.2010": "5101837", "Município 2010": "Novo município",
        },
        {
            "cod.1991": "3302008", "Município 1991": "Outro",
            "cod.2000": "3302008", "Município 2000": "Outro Novo",
            "cod.2010": "3302008", "Município 2010": "Outro Novo",
        },
    ])
    monkeypatch.setattr(
        "app.pipeline.reference.ibge.historical.pd.read_excel",
        lambda *args, **kwargs: frame,
    )

    events = parse_historical_municipality_workbook(source, source_url="fixture://history")

    assert [(event.event_type, event.source_code7, event.target_code7) for event in events] == [
        ("TOPONYMIC_CHANGE", "3301009", "3301009"),
        ("TOPONYMIC_CHANGE", "3302008", "3302008"),
    ]
    assert all(event.source == "fixture://history" for event in events)


def test_promote_historical_workbook_preserva_eventos_e_manifesto(tmp_path, monkeypatch):
    source = tmp_path / "history.xlsx"
    source.write_bytes(b"fixture")
    frame = __import__("pandas").DataFrame([
        {"cod.1991": "3301009", "Município 1991": "Campos",
         "cod.2000": "3301009", "Município 2000": "Campos dos Goytacazes"},
    ])
    monkeypatch.setattr(
        "app.pipeline.reference.ibge.historical.pd.read_excel",
        lambda *args, **kwargs: frame,
    )

    result = promote_historical_municipality_workbook(
        tmp_path / "catalog", source, source_url="fixture://history"
    )

    assert result.exists()
    manifest = __import__("json").loads(
        result.with_name("municipality_events.manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["reference_year"] == 2010
    assert manifest["sources"][0]["source_url"] == "fixture://history"


def test_promote_historical_source_preserves_raw_artifact_and_manifest(tmp_path):
    source = tmp_path / "genealogia.pdf"
    source.write_bytes(b"official genealogy")

    result = promote_historical_source(
        tmp_path / "catalog", source, source_id="genealogia-1872-2010.pdf",
        source_url="https://example.invalid/genealogia.pdf",
        reference_period="1872-2010",
    )

    assert result == tmp_path / "catalog" / "historical" / "sources" / "genealogia-1872-2010.pdf"
    assert result.read_bytes() == b"official genealogy"
    manifest = __import__("json").loads(
        (tmp_path / "catalog/historical/sources.manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["sources"]["genealogia-1872-2010.pdf"]["extraction_status"] == "RAW_ONLY"
    assert manifest["sources"]["genealogia-1872-2010.pdf"]["size_bytes"] == len(b"official genealogy")


def test_promote_historical_source_is_immutable(tmp_path):
    source = tmp_path / "genealogia.pdf"
    source.write_bytes(b"first")
    root = tmp_path / "catalog"
    kwargs = {
        "source_id": "genealogia.pdf",
        "source_url": "fixture://genealogia",
        "reference_period": "1872-2010",
    }
    first = promote_historical_source(root, source, **kwargs)
    assert promote_historical_source(root, source, **kwargs) == first
    source.write_bytes(b"second")

    with pytest.raises(ValueError, match="imutável"):
        promote_historical_source(root, source, **kwargs)


def test_download_historical_source_promotes_raw_artifact(tmp_path, mocker):
    response = mocker.Mock()
    response.iter_content.return_value = [b"official", b"-genealogy"]
    session = mocker.Mock()
    session.get.return_value = response

    result = download_historical_source(
        tmp_path / "catalog",
        url="https://example.invalid/genealogy.pdf",
        source_id="genealogy.pdf",
        reference_period="1872-2010",
        expected_sha256=__import__("hashlib").sha256(
            b"official-genealogy"
        ).hexdigest(),
        session=session,
        timeout=45,
    )

    assert result.read_bytes() == b"official-genealogy"
    manifest = __import__("json").loads(
        (tmp_path / "catalog/historical/sources.manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["sources"]["genealogy.pdf"]["extraction_status"] == "RAW_ONLY"
    session.get.assert_called_once_with(
        "https://example.invalid/genealogy.pdf", stream=True, timeout=45
    )
    response.close.assert_called_once_with()


def test_download_historical_source_fecha_sessao_criada_internamente(tmp_path, mocker):
    response = mocker.Mock()
    response.iter_content.return_value = [b"official"]
    session = mocker.Mock()
    session.get.return_value = response
    mocker.patch(
        "app.pipeline.reference.ibge.historical.requests.Session",
        return_value=session,
    )

    download_historical_source(
        tmp_path / "catalog", url="https://example.invalid/source.pdf",
        source_id="source.pdf", reference_period="1872-2010",
    )

    response.close.assert_called_once_with()
    session.close.assert_called_once_with()


@pytest.mark.parametrize("source_id", ["", "../source.pdf", "historical/source.pdf"])
def test_download_historical_source_rejeita_identificador_invalido(tmp_path, source_id):
    with pytest.raises(ValueError, match="source_id inválido"):
        download_historical_source(
            tmp_path / "catalog", url="fixture://source", source_id=source_id,
            reference_period="1872-2010",
        )


def test_download_historical_source_rejeita_hash_sem_promover(tmp_path, mocker):
    response = mocker.Mock()
    response.iter_content.return_value = [b"official"]
    session = mocker.Mock()
    session.get.return_value = response

    with pytest.raises(ValueError, match="SHA-256 da fonte histórica diverge"):
        download_historical_source(
            tmp_path / "catalog",
            url="https://example.invalid/genealogy.pdf",
            source_id="genealogy.pdf",
            reference_period="1872-2010",
            expected_sha256="0" * 64,
            session=session,
        )

    assert not (tmp_path / "catalog/historical/sources/genealogy.pdf").exists()
    response.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("url", "reference_period", "message"),
    [("", "1872-2010", "source_url obrigatório"),
     ("fixture://genealogy", "", "reference_period obrigatório")],
)
def test_download_historical_source_exige_proveniencia(tmp_path, url, reference_period, message):
    with pytest.raises(ValueError, match=message):
        download_historical_source(
            tmp_path / "catalog", url=url, source_id="genealogy.pdf",
            reference_period=reference_period,
        )


@pytest.mark.parametrize(
    "source_id", ["", "../genealogia.pdf", "historical/genealogia.pdf"]
)
def test_promote_historical_source_rejeita_identificador_invalido(tmp_path, source_id):
    source = tmp_path / "genealogia.pdf"
    source.write_bytes(b"source")
    with pytest.raises(ValueError) as error:
        promote_historical_source(
            tmp_path / "catalog", source, source_id=source_id,
            source_url="fixture://genealogia", reference_period="1872-2010",
        )
    assert str(error.value) == "source_id inválido para uma fonte histórica local"


@pytest.mark.parametrize(
    ("source_url", "reference_period", "message"),
    [("", "1872-2010", "source_url obrigatório"),
     ("fixture://genealogia", "", "reference_period obrigatório")],
)
def test_promote_historical_source_exige_proveniencia(tmp_path, source_url, reference_period, message):
    source = tmp_path / "genealogia.pdf"
    source.write_bytes(b"source")

    with pytest.raises(ValueError, match=message):
        promote_historical_source(
            tmp_path / "catalog", source, source_id="genealogia.pdf",
            source_url=source_url, reference_period=reference_period,
        )


def test_promote_historical_source_rejeita_manifesto_sources_invalido(tmp_path):
    root = tmp_path / "catalog"
    source = tmp_path / "genealogia.pdf"
    source.write_bytes(b"source")
    promote_historical_source(
        root, source, source_id="genealogia.pdf", source_url="fixture://genealogia",
        reference_period="1872-2010",
    )
    manifest = root / "historical" / "sources.manifest.json"
    manifest.write_text('{"sources": []}', encoding="utf-8")

    with pytest.raises(
        ValueError,
        match=r"^manifesto de fontes históricas inválido: sources deve ser um mapa:",
    ):
        promote_historical_source(
            root, source, source_id="other.pdf", source_url="fixture://other",
            reference_period="1872-2010",
        )


@pytest.mark.parametrize("raw_sources", [None, "not-a-map", ["not-an-entry"]])
def test_promote_historical_source_rejeita_sources_que_nao_sao_mapa(
    tmp_path, raw_sources
):
    root = tmp_path / "catalog"
    source = tmp_path / "genealogia.pdf"
    source.write_bytes(b"source")
    promote_historical_source(
        root, source, source_id="genealogia.pdf", source_url="fixture://genealogia",
        reference_period="1872-2010",
    )
    manifest = root / "historical" / "sources.manifest.json"
    manifest.write_text(
        __import__("json").dumps({"sources": raw_sources}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="sources deve ser um mapa"):
        promote_historical_source(
            root, source, source_id="other.pdf", source_url="fixture://other",
            reference_period="1872-2010",
        )


def test_promote_historical_source_rejeita_entrada_documental_incompleta(tmp_path):
    root = tmp_path / "catalog"
    source = tmp_path / "genealogia.pdf"
    source.write_bytes(b"source")
    promote_historical_source(
        root, source, source_id="genealogia.pdf", source_url="fixture://genealogia",
        reference_period="1872-2010",
    )
    manifest = root / "historical" / "sources.manifest.json"
    payload = __import__("json").loads(manifest.read_text(encoding="utf-8"))
    payload["sources"]["genealogia.pdf"].pop("source_url")
    manifest.write_text(__import__("json").dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="fonte incompleta"):
        promote_historical_source(
            root, source, source_id="other.pdf", source_url="fixture://other",
            reference_period="1872-2010",
        )


def test_promote_historical_source_rejeita_manifesto_sem_sha256(tmp_path):
    root = tmp_path / "catalog"
    source = tmp_path / "genealogia.pdf"
    source.write_bytes(b"source")
    promote_historical_source(
        root, source, source_id="genealogia.pdf", source_url="fixture://genealogia",
        reference_period="1872-2010",
    )
    manifest = root / "historical" / "sources.manifest.json"
    payload = __import__("json").loads(manifest.read_text(encoding="utf-8"))
    payload["sources"]["genealogia.pdf"].pop("sha256")
    manifest.write_text(__import__("json").dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="fonte incompleta"):
        promote_historical_source(
            root, source, source_id="other.pdf", source_url="fixture://other",
            reference_period="1872-2010",
        )


def test_promote_historical_source_rejeita_fonte_ausente_e_vazia(tmp_path):
    with pytest.raises(ValueError) as missing:
        promote_historical_source(
            tmp_path / "catalog", tmp_path / "missing.pdf",
            source_id="missing.pdf", source_url="fixture://missing",
            reference_period="1872-2010",
        )
    assert str(missing.value) == f"fonte histórica ausente: {tmp_path / 'missing.pdf'}"

    empty = tmp_path / "empty.pdf"
    empty.write_bytes(b"")
    with pytest.raises(ValueError) as blank:
        promote_historical_source(
            tmp_path / "catalog", empty, source_id="empty.pdf",
            source_url="fixture://empty", reference_period="1872-2010",
        )
    assert str(blank.value) == "fonte histórica vazia"


def test_historical_events_reject_duplicates(tmp_path):
    event = MunicipalityEvent("event-1", "RENAME", "2025-01-01", "1", "1")
    with pytest.raises(ValueError, match="duplicado"):
        write_events(tmp_path / "events.parquet", [event, event])


@pytest.mark.parametrize(
    ("events", "message"),
    [
        ([], "histórico municipal vazio"),
        ([MunicipalityEvent("duplicate", "CREATION", "2025-01-01", None, "5101837")] * 2,
         "event_id duplicado no histórico municipal"),
        ([MunicipalityEvent("unknown", "BOGUS", "2025-01-01", None, "5101837")],
         "tipo de evento municipal desconhecido: \\['BOGUS'\\]"),
        ([MunicipalityEvent("date", "CREATION", "not-a-date", None, "5101837")],
         "data de vigência inválida no histórico municipal"),
    ],
)
def test_write_events_preserves_structural_error_contract(tmp_path, events, message):
    with pytest.raises(ValueError, match=f"^{message}$"):
        write_events(tmp_path / "invalid.parquet", events)


@pytest.mark.parametrize(
    "event",
    [
        MunicipalityEvent("creation", "CREATION", "2025-01-01", "3301009", "5101837"),
        MunicipalityEvent("extinction", "EXTINCTION", "2025-01-01", None, "5101837"),
        MunicipalityEvent("succession", "SUCCESSION", "2025-01-01", "3301009", None),
        MunicipalityEvent("rename", "RENAME", "2025-01-01", "3301009", "3305000"),
    ],
)
def test_write_events_rejects_semantically_invalid_event_shapes(tmp_path, event):
    with pytest.raises(ValueError, match="evento"):
        write_events(tmp_path / f"{event.event_id}.parquet", [event])


def test_write_events_accepts_all_supported_event_shapes(tmp_path):
    events = [
        MunicipalityEvent("creation", "CREATION", "2025-01-01", None, "5101837"),
        MunicipalityEvent("extinction", "EXTINCTION", "2025-01-01", "3301009", None),
        MunicipalityEvent("succession", "SUCCESSION", "2025-01-01", "3301009", "5101837"),
        MunicipalityEvent("merger", "MERGER", "2025-01-01", "3301009", "5101837"),
        MunicipalityEvent("split", "SPLIT", "2025-01-01", "3301009", "5101837"),
        MunicipalityEvent("rename", "RENAME", "2025-01-01", "3301009", "3301009"),
        MunicipalityEvent("toponymic", "TOPONYMIC_CHANGE", "2025-01-01", "3301009", "3301009"),
    ]

    assert write_events(tmp_path / "valid.parquet", events).exists()


@pytest.mark.parametrize(
    "event",
    [
        MunicipalityEvent("extinction-empty", "EXTINCTION", "2025-01-01", None, None),
        MunicipalityEvent("succession-source-empty", "SUCCESSION", "2025-01-01", None, "5101837"),
        MunicipalityEvent("rename-source-empty", "RENAME", "2025-01-01", None, "3301009"),
    ],
)
def test_write_events_rejects_missing_required_event_codes(tmp_path, event):
    with pytest.raises(ValueError, match="evento"):
        write_events(tmp_path / f"{event.event_id}.parquet", [event])


def test_parse_toponymic_events_preserves_code_and_names(tmp_path):
    source = tmp_path / "alteracoes.csv"
    source.write_text(
        "UF,MUN,ALT,NOME_ANTERIOR,NOME_ATUAL,DATA_OCORRÊNCIA\n"
        "33,01009,2,Campos dos Goitacazes,Campos dos Goytacazes,1988-10-24\n",
        encoding="utf-8",
    )
    events = parse_toponymic_events(
        source, reference_year=2025, source_url="https://example.invalid/ibge.xls"
    )
    assert len(events) == 1
    assert events[0].event_type == "TOPONYMIC_CHANGE"
    assert events[0].source_code7 == events[0].target_code7 == "3301009"
    assert events[0].source_name == "Campos dos Goitacazes"
    assert events[0].target_name == "Campos dos Goytacazes"
    assert events[0].effective_date == "1988-10-24"


def test_parse_toponymic_events_accepts_official_2025_schema():
    fixture = __import__("pathlib").Path(
        "tests/fixtures/ibge/alteracoes_toponimicas_2025_schema_sample.csv"
    )

    events = parse_toponymic_events(fixture, reference_year=2025)

    assert len(events) == 1
    assert events[0].event_type == "TOPONYMIC_CHANGE"
    assert events[0].source_code7 == events[0].target_code7 == "2401206"
    assert events[0].source_name == "Arês"
    assert events[0].target_name == "Arez"
    assert events[0].effective_date == "2025-09-10"


def test_parse_toponymic_events_rejects_unsupported_format(tmp_path):
    source = tmp_path / "alteracoes.txt"
    source.write_text("UF,MUN,NOME_ANTERIOR,NOME_ATUAL,DATA_OCORRÊNCIA\n", encoding="utf-8")

    with pytest.raises(ValueError, match="formato de alterações toponímicas não suportado"):
        parse_toponymic_events(source, reference_year=2025)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("UF,MUN\n33,01009\n", "colunas ausentes"),
        (
            "UF,MUN,NOME_ANTERIOR,NOME_ATUAL,DATA_OCORRÊNCIA\n33,01009,Antigo,Novo,not-a-date\n",
            "evento toponímico incompleto, linha 2",
        ),
        (
            "UF,MUN,NOME_ANTERIOR,NOME_ATUAL,DATA_OCORRÊNCIA\n33,01009,,,2025-01-01\n",
            "evento toponímico incompleto, linha 2",
        ),
        (
            "UF,MUN,NOME_ANTERIOR,NOME_ATUAL,DATA_OCORRÊNCIA\n",
            "histórico toponímico vazio",
        ),
    ],
)
def test_parse_toponymic_events_rejects_incomplete_source(tmp_path, content, message):
    source = tmp_path / "alteracoes.csv"
    source.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        parse_toponymic_events(source, reference_year=2025)


def test_historical_codes_accept_only_ascii_digits(tmp_path):
    event = MunicipalityEvent("unicode", "CREATION", "2025-01-01", None, "１２３４５６７")
    with pytest.raises(ValueError, match="target_code7 inválido"):
        write_events(tmp_path / "invalid.parquet", [event])

    source = tmp_path / "unicode.csv"
    source.write_text(
        "UF,MUN,ALT,NOME_ANTERIOR,NOME_ATUAL,DATA_OCORRÊNCIA\n"
        "３３,０１００９,2,Nome antigo,Nome atual,1988-10-24\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="geocódigo inválido"):
        parse_toponymic_events(source, reference_year=2025)


def test_promote_toponymic_events_writes_manifest(tmp_path):
    source = tmp_path / "alteracoes.csv"
    source.write_text(
        "UF,MUN,ALT,NOME_ANTERIOR,NOME_ATUAL,DATA_OCORRÊNCIA\n"
        "24,00100,1,Amparo de São Francisco,Amparo do São Francisco,2020-07-14\n",
        encoding="utf-8",
    )
    result = promote_toponymic_events(tmp_path / "catalog", source, reference_year=2025)
    assert result.exists()
    assert result.with_name("municipality_events.manifest.json").exists()


def test_parse_administrative_events_requires_explicit_codes(tmp_path):
    source = tmp_path / "administrative.csv"
    source.write_text(
        "EVENT_TYPE,EFFECTIVE_DATE,SOURCE_CODE7,TARGET_CODE7,SOURCE_NAME,TARGET_NAME\n"
        "SUCCESSION,2025-01-01,5101234,5101837,Origem,Novo\n",
        encoding="utf-8",
    )
    events = parse_administrative_events(source, reference_year=2025)
    assert events[0].event_type == "SUCCESSION"
    assert events[0].source_code7 == "5101234"
    assert events[0].target_code7 == "5101837"


def test_parse_administrative_events_rejects_unsupported_format(tmp_path):
    source = tmp_path / "administrative.txt"
    source.write_text("EVENT_TYPE,EFFECTIVE_DATE\nCREATION,2025-01-01\n", encoding="utf-8")

    with pytest.raises(ValueError, match="formato de eventos administrativos não suportado"):
        parse_administrative_events(source, reference_year=2025)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("EVENT_TYPE\nCREATION\n", "colunas ausentes"),
        ("EVENT_TYPE,EFFECTIVE_DATE\nCREATION,not-a-date\n", "data de vigência inválida"),
        ("EVENT_TYPE,EFFECTIVE_DATE,SOURCE_CODE7,TARGET_CODE7\n", "histórico administrativo vazio"),
    ],
)
def test_parse_administrative_events_rejects_incomplete_source(tmp_path, content, message):
    source = tmp_path / "administrative.csv"
    source.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        parse_administrative_events(source, reference_year=2025)


def test_validate_event_references_checks_source_and_target_editions():
    event = MunicipalityEvent("event", "SUCCESSION", "2025-01-01", "3301009", "5101837")
    valid = validate_event_references(
        [event], source_codes={"3301009"}, target_codes={"5101837"}
    )
    assert valid.valid is True
    assert valid.event_count == 1

    invalid = validate_event_references(
        [event], source_codes={"3305000"}, target_codes={"5101837"}
    )
    assert invalid.valid is False
    assert "3301009" in invalid.errors[0]

    target_invalid = validate_event_references(
        [event], source_codes={"3301009"}, target_codes={"5100000"}
    )
    assert target_invalid.valid is False
    assert target_invalid.errors == (
        "event: target_code7 ausente na edição de destino: 5101837",
    )


def test_promote_administrative_events_rejects_unresolved_reference(tmp_path):
    source = tmp_path / "administrative.csv"
    source.write_text(
        "EVENT_TYPE,EFFECTIVE_DATE,SOURCE_CODE7,TARGET_CODE7\n"
        "SUCCESSION,2025-01-01,3301009,5101837\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="referências históricas inválidas"):
        promote_administrative_events(
            tmp_path / "catalog", source, reference_year=2025,
            source_codes={"3305000"}, target_codes={"5101837"},
        )


def test_require_event_references_preserves_all_reference_errors():
    from app.pipeline.reference.ibge.historical import require_event_references

    event = MunicipalityEvent("event", "SUCCESSION", "2025-01-01", "3301009", "5101837")
    with pytest.raises(
        ValueError,
        match=(
            r"^referências históricas inválidas: event: source_code7 ausente na edição de origem: "
            r"3301009; event: target_code7 ausente na edição de destino: 5101837$"
        ),
    ):
        require_event_references(
            [event], source_codes={"3305000"}, target_codes={"5100000"}
        )


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (
            "EVENT_TYPE,EFFECTIVE_DATE,SOURCE_CODE7,TARGET_CODE7\nSUCCESSION,2025-01-01,5101234,\n",
            "TARGET_CODE7 ausente",
        ),
        (
            "EVENT_TYPE,EFFECTIVE_DATE,SOURCE_CODE7,TARGET_CODE7\nBOGUS,2025-01-01,5101234,5101837\n",
            "tipo de evento administrativo inválido, linha 2",
        ),
        (
            "EVENT_TYPE,EFFECTIVE_DATE,SOURCE_CODE7,TARGET_CODE7\nCREATION,2025-01-01,,51018\n",
            "TARGET_CODE7 inválido, linha 2",
        ),
    ],
)
def test_parse_administrative_events_rejects_ambiguous_or_unknown_rows(tmp_path, content, message):
    source = tmp_path / "administrative.csv"
    source.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        parse_administrative_events(source, reference_year=2025)


def test_promote_administrative_events_writes_versioned_manifest(tmp_path):
    source = tmp_path / "administrative.csv"
    source.write_text(
        "EVENT_TYPE,EFFECTIVE_DATE,SOURCE_CODE7,TARGET_CODE7\n"
        "CREATION,2025-01-01,,5101837\n",
        encoding="utf-8",
    )
    result = promote_administrative_events(tmp_path / "catalog", source, reference_year=2025)
    assert result.exists()
    assert result.with_name("municipality_events.manifest.json").exists()


def test_promotions_merge_toponymic_and_administrative_events(tmp_path):
    root = tmp_path / "catalog"
    toponymic = tmp_path / "toponymic.csv"
    toponymic.write_text(
        "UF,MUN,ALT,NOME_ANTERIOR,NOME_ATUAL,DATA_OCORRÊNCIA\n"
        "33,01009,2,Nome antigo,Campos dos Goytacazes,1988-10-24\n",
        encoding="utf-8",
    )
    administrative = tmp_path / "administrative.csv"
    administrative.write_text(
        "EVENT_TYPE,EFFECTIVE_DATE,SOURCE_CODE7,TARGET_CODE7\n"
        "CREATION,2025-01-01,,5101837\n",
        encoding="utf-8",
    )
    promote_toponymic_events(root, toponymic, reference_year=2025)
    result = promote_administrative_events(root, administrative, reference_year=2025)

    frame = __import__("pandas").read_parquet(result)
    assert set(frame["event_type"]) == {"TOPONYMIC_CHANGE", "CREATION"}
    assert len(frame) == 2
    manifest = __import__("json").loads(
        result.with_name("municipality_events.manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["inference_policy"] == "EXPLICIT_SOURCE_ONLY"
    assert len(manifest["sources"]) == 2


def test_promote_administrative_events_is_idempotent(tmp_path):
    source = tmp_path / "administrative.csv"
    source.write_text(
        "EVENT_TYPE,EFFECTIVE_DATE,SOURCE_CODE7,TARGET_CODE7,TARGET_NAME\n"
        "CREATION,2025-01-01,,5101837,Novo\n",
        encoding="utf-8",
    )
    root = tmp_path / "catalog"

    first = promote_administrative_events(root, source, reference_year=2025)
    first_frame = __import__("pandas").read_parquet(first)
    first_manifest = __import__("json").loads(
        first.with_name("municipality_events.manifest.json").read_text(encoding="utf-8")
    )
    second = promote_administrative_events(root, source, reference_year=2025)
    second_frame = __import__("pandas").read_parquet(second)
    second_manifest = __import__("json").loads(
        second.with_name("municipality_events.manifest.json").read_text(encoding="utf-8")
    )

    assert len(first_frame) == len(second_frame) == 1
    assert first_manifest["sources"] == second_manifest["sources"]


def test_promote_administrative_events_rejeita_manifesto_sources_invalido(tmp_path):
    source = tmp_path / "administrative.csv"
    source.write_text(
        "EVENT_TYPE,EFFECTIVE_DATE,SOURCE_CODE7,TARGET_CODE7\n"
        "CREATION,2025-01-01,,5101837\n", encoding="utf-8",
    )
    root = tmp_path / "catalog"
    promote_administrative_events(root, source, reference_year=2025)
    manifest = root / "historical" / "municipality_events.manifest.json"
    payload = __import__("json").loads(manifest.read_text(encoding="utf-8"))
    payload["sources"] = {"invalid": True}
    manifest.write_text(__import__("json").dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="sources deve ser uma lista"):
        promote_administrative_events(root, source, reference_year=2025)


def test_promote_administrative_events_rejects_conflicting_event_identity(tmp_path):
    source = tmp_path / "administrative.csv"
    source.write_text(
        "EVENT_TYPE,EFFECTIVE_DATE,SOURCE_CODE7,TARGET_CODE7,TARGET_NAME\n"
        "CREATION,2025-01-01,,5101837,Novo\n",
        encoding="utf-8",
    )
    root = tmp_path / "catalog"
    promote_administrative_events(root, source, reference_year=2025)
    source.write_text(
        "EVENT_TYPE,EFFECTIVE_DATE,SOURCE_CODE7,TARGET_CODE7,TARGET_NAME\n"
        "CREATION,2025-01-01,,5101837,Novo alterado\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="event_id conflitante"):
        promote_administrative_events(root, source, reference_year=2025)


def test_derive_annual_events_does_not_infer_succession():
    from app.pipeline.reference.ibge.models import Municipality

    previous = [Municipality("3301009", "330100", "Nome antigo", "33", "RJ", "Rio", 2024)]
    current = [
        Municipality("3301009", "330100", "Nome atual", "33", "RJ", "Rio", 2025),
        Municipality("5101837", "510183", "Novo município", "51", "MT", "Mato Grosso", 2025),
    ]

    events = derive_annual_events(
        previous, current, reference_year=2025,
        effective_date="2025-01-01", source_url="fixture://dtb-diff",
    )

    assert {(event.event_type, event.source_code7, event.target_code7) for event in events} == {
        ("TOPONYMIC_CHANGE", "3301009", "3301009"),
        ("CREATION", None, "5101837"),
    }
    creation = next(event for event in events if event.event_type == "CREATION")
    rename = next(event for event in events if event.event_type == "TOPONYMIC_CHANGE")
    assert creation.event_id == "f6db97e219faee6e4a35"
    assert creation.target_name == "Novo município"
    assert rename.event_id == "f3151d3bb8646cbe293d"
    assert rename.source_name == "Nome antigo"
    assert rename.target_name == "Nome atual"


def test_derive_annual_event_series_requires_consecutive_editions():
    from app.pipeline.reference.ibge.models import Municipality

    item = Municipality("3301009", "330100", "Campos", "33", "RJ", "Rio", 2024)
    with pytest.raises(ValueError, match="anos consecutivos"):
        derive_annual_event_series({2022: [item], 2024: [item]})


def test_derive_annual_event_series_keeps_creation_and_extinction_separate():
    from app.pipeline.reference.ibge.models import Municipality

    previous = Municipality("3301009", "330100", "Origem", "33", "RJ", "Rio", 2024)
    current = Municipality("5101837", "510183", "Novo", "51", "MT", "Mato Grosso", 2025)
    events = derive_annual_event_series(
        {2024: [previous], 2025: [current]},
        source_urls={2025: "https://example.invalid/DTB_2025.zip"},
    )
    assert {(event.event_type, event.source_code7, event.target_code7) for event in events} == {
        ("EXTINCTION", "3301009", None),
        ("CREATION", None, "5101837"),
    }
    extinction = next(event for event in events if event.event_type == "EXTINCTION")
    creation = next(event for event in events if event.event_type == "CREATION")
    assert extinction.event_id == "8b0a6769bbe8869bb67f"
    assert extinction.source_name == "Origem"
    assert creation.target_name == "Novo"
    assert all(event.source == "https://example.invalid/DTB_2025.zip" for event in events)


def test_derive_annual_event_series_allows_unchanged_intervals():
    from app.pipeline.reference.ibge.models import Municipality

    item = Municipality("3301009", "330100", "Campos", "33", "RJ", "Rio", 2024)
    assert derive_annual_event_series({2024: [item], 2025: [item]}) == []


def test_promote_annual_dtb_events_writes_hashes_and_policy(tmp_path, monkeypatch):
    from app.pipeline.reference.ibge import dtb
    from app.pipeline.reference.ibge.models import Municipality

    previous = Municipality("3301009", "330100", "Origem", "33", "RJ", "Rio", 2024)
    current = Municipality("5101837", "510183", "Novo", "51", "MT", "Mato Grosso", 2025)
    archives = {2024: tmp_path / "DTB_2024.zip", 2025: tmp_path / "DTB_2025.zip"}
    for path in archives.values():
        path.write_bytes(b"official-fixture")
    monkeypatch.setattr(
        dtb, "parse_dtb_archive",
        lambda path, reference_year: [previous] if reference_year == 2024 else [current],
    )

    result = promote_annual_dtb_events(
        tmp_path / "catalog", archives,
        source_urls={year: f"fixture://DTB_{year}.zip" for year in archives},
    )
    manifest = __import__("json").loads(
        result.with_name("municipality_events.manifest.json").read_text(encoding="utf-8")
    )
    assert result.exists()
    assert manifest["rows"] == 2
    assert manifest["inference_policy"] == "OBSERVABLE_ANNUAL_DIFF_ONLY"
    assert len(manifest["sources"]) == 2


def test_promote_annual_dtb_events_rejeita_manifesto_sources_invalido(tmp_path, monkeypatch):
    from app.pipeline.reference.ibge import dtb
    from app.pipeline.reference.ibge.models import Municipality

    previous = Municipality("3301009", "330100", "Origem", "33", "RJ", "Rio", 2024)
    current = Municipality("5101837", "510183", "Novo", "51", "MT", "Mato Grosso", 2025)
    archives = {2024: tmp_path / "DTB_2024.zip", 2025: tmp_path / "DTB_2025.zip"}
    for path in archives.values():
        path.write_bytes(b"official-fixture")
    monkeypatch.setattr(
        dtb, "parse_dtb_archive",
        lambda path, reference_year: [previous] if reference_year == 2024 else [current],
    )
    root = tmp_path / "catalog"
    promote_annual_dtb_events(root, archives)
    manifest_path = root / "historical" / "municipality_events.manifest.json"
    payload = __import__("json").loads(manifest_path.read_text(encoding="utf-8"))
    payload["sources"] = {"invalid": True}
    manifest_path.write_text(__import__("json").dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="sources deve ser uma lista"):
        promote_annual_dtb_events(root, archives)


def test_promote_annual_dtb_events_rejeita_politicas_invalidas(tmp_path, monkeypatch):
    from app.pipeline.reference.ibge import dtb
    from app.pipeline.reference.ibge.models import Municipality

    previous = Municipality("3301009", "330100", "Origem", "33", "RJ", "Rio", 2024)
    current = Municipality("5101837", "510183", "Novo", "51", "MT", "Mato Grosso", 2025)
    archives = {2024: tmp_path / "DTB_2024.zip", 2025: tmp_path / "DTB_2025.zip"}
    for path in archives.values():
        path.write_bytes(b"official-fixture")
    monkeypatch.setattr(
        dtb, "parse_dtb_archive",
        lambda path, reference_year: [previous] if reference_year == 2024 else [current],
    )
    root = tmp_path / "catalog"
    promote_annual_dtb_events(root, archives)
    manifest_path = root / "historical" / "municipality_events.manifest.json"
    payload = __import__("json").loads(manifest_path.read_text(encoding="utf-8"))
    payload["inference_policies"] = "OBSERVABLE_ANNUAL_DIFF_ONLY"
    manifest_path.write_text(__import__("json").dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="inference_policies deve ser uma lista"):
        promote_annual_dtb_events(root, archives)


def test_promote_annual_dtb_events_rejeita_fonte_sem_linhagem(tmp_path, monkeypatch):
    from app.pipeline.reference.ibge import dtb
    from app.pipeline.reference.ibge.models import Municipality

    previous = Municipality("3301009", "330100", "Origem", "33", "RJ", "Rio", 2024)
    current = Municipality("5101837", "510183", "Novo", "51", "MT", "Mato Grosso", 2025)
    archives = {2024: tmp_path / "DTB_2024.zip", 2025: tmp_path / "DTB_2025.zip"}
    for path in archives.values():
        path.write_bytes(b"official-fixture")
    monkeypatch.setattr(
        dtb, "parse_dtb_archive",
        lambda path, reference_year: [previous] if reference_year == 2024 else [current],
    )
    root = tmp_path / "catalog"
    promote_annual_dtb_events(root, archives)
    manifest_path = root / "historical" / "municipality_events.manifest.json"
    payload = __import__("json").loads(manifest_path.read_text(encoding="utf-8"))
    payload["sources"][0].pop("sha256")
    manifest_path.write_text(__import__("json").dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="sem reference_year, source_path ou sha256"):
        promote_annual_dtb_events(root, archives)


def test_promote_annual_dtb_events_preserves_previous_source_lineage(tmp_path, monkeypatch):
    from app.pipeline.reference.ibge import dtb
    from app.pipeline.reference.ibge.models import Municipality

    previous = Municipality("3301009", "330100", "Origem", "33", "RJ", "Rio", 2024)
    current = Municipality("5101837", "510183", "Novo", "51", "MT", "Mato Grosso", 2025)
    toponymic = tmp_path / "alteracoes.csv"
    toponymic.write_text(
        "UF,MUN,ALT,NOME_ANTERIOR,NOME_ATUAL,DATA_OCORRÊNCIA\n"
        "33,01009,2,Origem,Origem Nova,2024-01-01\n", encoding="utf-8",
    )
    root = tmp_path / "catalog"
    promote_toponymic_events(root, toponymic, reference_year=2024, source_url="fixture://toponymic")
    archives = {2024: tmp_path / "DTB_2024.zip", 2025: tmp_path / "DTB_2025.zip"}
    for path in archives.values():
        path.write_bytes(b"official-fixture")
    monkeypatch.setattr(
        dtb, "parse_dtb_archive",
        lambda path, reference_year: [previous] if reference_year == 2024 else [current],
    )

    result = promote_annual_dtb_events(root, archives)
    manifest = __import__("json").loads(
        result.with_name("municipality_events.manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["inference_policy"] == "MIXED_EXPLICIT_AND_OBSERVABLE"
    assert len(manifest["sources"]) == 3
