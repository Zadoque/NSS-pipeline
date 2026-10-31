from pathlib import Path

import pandas as pd
import pytest

from app.pipeline import run_load as runner
from app.pipeline.load import load_gold_to_postgres
from app.pipeline.sinan.gold import MUNICIPIOS_RJ
from app.pipeline.scope import scope_sha256


@pytest.mark.parametrize("arguments", [
    ["--municipios", "3301009", "--ufs", "RJ"],
    ["--municipios", "3301009", "--all-brazil"],
    ["--ufs", "RJ", "--all-brazil"],
])
def test_cli_run_load_rejeita_selecao_geografica_ambigua(arguments):
    with pytest.raises(SystemExit):
        runner._build_parser().parse_args(arguments)


def test_cli_run_load_preserva_contrato_dos_argumentos_geograficos():
    parser = runner._build_parser()
    args = parser.parse_args([
        "--disease", "DENG", "--year", "2026", "--allow-empty",
        "--catalog-root", "/tmp/ibge", "--ufs", "RJ",
        "--cnes-batch-id", "batch-1",
    ])

    assert "pipeline SINAN" in parser.description
    assert args.disease == "DENG"
    assert args.year == 2026
    assert args.allow_empty is True
    assert args.catalog_root == Path("/tmp/ibge")
    assert args.ufs == "RJ"
    assert args.municipios is None
    assert args.all_brazil is False
    assert args.cnes_batch_id == "batch-1"


@pytest.mark.parametrize(
    "missing",
    [
        [],
        ["--year", "2026"],
        ["--disease", "DENG"],
    ],
)
def test_cli_run_load_exige_doenca_e_ano(missing):
    with pytest.raises(SystemExit) as exc_info:
        runner._build_parser().parse_args(missing)

    assert exc_info.value.code == 2


def test_cli_run_load_converte_ano_e_catalogo_e_preserva_defaults():
    args = runner._build_parser().parse_args(["--disease", "DENG", "--year", "2026"])

    assert args.year == 2026
    assert isinstance(args.year, int)
    assert args.allow_empty is False
    assert args.catalog_root is None
    assert args.municipios is None
    assert args.ufs is None
    assert args.all_brazil is False
    assert args.cnes_batch_id is None


def test_cli_run_load_rejeita_ano_nao_numerico():
    with pytest.raises(SystemExit) as exc_info:
        runner._build_parser().parse_args(["--disease", "DENG", "--year", "abc"])

    assert exc_info.value.code == 2


def test_cli_run_load_documenta_opcoes_de_operacao():
    help_text = runner._build_parser().format_help()

    assert "Roda a pipeline SINAN completa (grão fixo)" in help_text
    assert "Ex.: DENG, TOXC, ZIKA" in help_text
    assert "Permite publicar zero no recorte" in help_text
    assert "Diretório local de releases IBGE" in help_text
    assert "Códigos municipais separados por vírgula" in help_text
    assert "UFs ou códigos de UF separados por vírgula" in help_text
    assert "Seleciona todos os municípios da release IBGE" in help_text
    assert "Lote CNES fixado para o enriquecimento da Gold" in help_text


def test_main_exige_catalogo_para_selecao_geografica(mocker):
    mocker.patch.object(
        runner,
        "_build_parser",
        return_value=runner._build_parser(),
    )
    mocker.patch(
        "sys.argv",
        ["run_load", "--disease", "DENG", "--year", "2026", "--ufs", "RJ"],
    )
    execute = mocker.patch.object(runner, "run_load")

    with pytest.raises(SystemExit) as exc_info:
        runner.main()

    assert exc_info.value.code == 1
    execute.assert_not_called()


def test_main_encaminha_escopo_e_lote_cnes(mocker, tmp_path):
    catalog = mocker.Mock()
    scope = mocker.Mock()
    mocker.patch.object(runner, "load_active_catalog", return_value=catalog)
    select = mocker.patch.object(runner, "select_scope", return_value=scope)
    execute = mocker.patch.object(runner, "run_load")
    mocker.patch(
        "sys.argv",
        [
            "run_load",
            "--disease", "deng",
            "--year", "2026",
            "--catalog-root", str(tmp_path),
            "--all-brazil",
            "--allow-empty",
            "--cnes-batch-id", "cnes-2026",
        ],
    )

    runner.main()

    select.assert_called_once_with(
        catalog,
        municipalities=None,
        ufs=None,
        all_brazil=True,
        require_national=True,
    )
    execute.assert_called_once_with(
        "deng",
        2026,
        allow_empty=True,
        catalog=catalog,
        geographic_scope=scope,
        cnes_batch_id="cnes-2026",
    )


@pytest.fixture
def pipeline(mocker):
    mocker.patch.object(runner, "fetch_sinan", return_value=Path("source.parquet"))
    mocker.patch.object(runner, "write_bronze", return_value=Path("bronze.parquet"))
    mocker.patch.object(runner, "transform_file", return_value=Path("silver.parquet"))
    aggregate = mocker.patch.object(runner, "aggregate_file", return_value=Path("gold.parquet"))
    engine = mocker.Mock()
    get_engine = mocker.patch.object(runner, "get_engine", return_value=engine)
    load = mocker.patch.object(runner, "load_gold_to_postgres")
    return aggregate, engine, get_engine, load


@pytest.mark.parametrize("gold_cases_total", [1, 3, 5])
def test_orquestrador_declara_recorte_e_total_independente_da_gold(
    mocker, pipeline, gold_cases_total,
):
    aggregate, engine, _, load = pipeline
    # O total esperado vem das notificações Silver, incluindo apenas o recorte.
    silver = pd.DataFrame({
        "ID_MUNICIP": ["330100", "3301009", "0330240", "9999999", None, "inválido"],
    })
    gold = pd.DataFrame({"cases_total": [gold_cases_total]})
    mocker.patch.object(runner.pd, "read_parquet", side_effect=[silver, gold])
    runner.run_load("deng", 2026)
    options = load.call_args.kwargs
    assert load.call_args.args[2] == "DENG"
    assert runner.write_bronze.call_args.args[1] == "DENG"
    assert options["expected_cases_total"] == 3
    assert options["municipios"] == list(MUNICIPIOS_RJ)
    assert options["year"] == 2026
    assert options["snapshot_complete"] is True
    assert options["allow_empty"] is False
    assert options["geographic_scope_sha256"] == scope_sha256(MUNICIPIOS_RJ)
    assert options["source_extracted_at"] == aggregate.call_args.kwargs["run_at"]
    assert aggregate.call_args.args[1] == "DENG"
    assert aggregate.call_args.args[:3] == (Path("silver.parquet"), "DENG", 2026)
    assert aggregate.call_args.kwargs["municipios"] == MUNICIPIOS_RJ
    assert aggregate.call_args.kwargs["selected_columns"] == runner.CANONICAL_GOLD_COLUMNS
    assert aggregate.call_args.kwargs["target"] == "serving"
    assert aggregate.call_args.kwargs["geographic_scope_type"] == "MUNICIPALITIES"
    assert options["quality_metrics"] == {}
    engine.dispose.assert_called_once()


@pytest.mark.parametrize("gold_cases_total", [0, 1, 3])
def test_orquestrador_bloqueia_total_divergente_antes_de_abrir_transacao(
    mocker, pipeline, gold_cases_total,
):
    _, engine, _, load = pipeline
    silver = pd.DataFrame({"ID_MUNICIP": ["330100", "3301009", "9999999"]})
    gold = pd.DataFrame({
        "year": [2026], "month": [1], "cd_mun": ["3301009"],
        "nm_mun": ["Campos dos Goytacazes"], "cd_uf": ["33"],
        "nm_uf": ["Rio de Janeiro"], "cases_total": [gold_cases_total],
    })
    if gold_cases_total == 0:
        gold = gold.iloc[:0]
    mocker.patch.object(runner.pd, "read_parquet", side_effect=[silver, gold])
    # Executa a validação real; a conexão fictícia não deve abrir transação.
    load.side_effect = load_gold_to_postgres

    with pytest.raises(ValueError, match="diverge"):
        runner.run_load("DENG", 2026, allow_empty=True)

    assert load.call_args.kwargs["expected_cases_total"] == 2
    engine.begin.assert_not_called()
    engine.dispose.assert_called_once()


def test_silver_vazia_nao_publica_mesmo_com_allow_empty(mocker, pipeline):
    aggregate, _, get_engine, load = pipeline
    mocker.patch.object(runner.pd, "read_parquet", return_value=pd.DataFrame(columns=["ID_MUNICIP"]))
    with pytest.raises(RuntimeError) as error:
        runner.run_load("DENG", 2026, allow_empty=True)
    assert str(error.value) == "Silver sem notificações válidas: publicação bloqueada"
    aggregate.assert_not_called()
    get_engine.assert_not_called()
    load.assert_not_called()


def test_falha_de_ingestao_nao_abre_carga(pipeline, mocker):
    _, _, get_engine, load = pipeline
    mocker.patch.object(runner, "fetch_sinan", side_effect=RuntimeError("fonte indisponível"))
    with pytest.raises(RuntimeError, match="fonte indisponível"):
        runner.run_load("DENG", 2026)
    get_engine.assert_not_called()
    load.assert_not_called()


def test_cache_local_passa_para_bronze_sem_leitura_em_memoria(mocker, pipeline):
    source = Path("cache.parquet")
    silver = pd.DataFrame({"ID_MUNICIP": ["330100"]})
    gold = pd.DataFrame({"cases_total": [1]})
    read = mocker.patch.object(runner.pd, "read_parquet", side_effect=[silver, gold])

    runner.run_load("DENG", 2024, source_path=source)

    runner.fetch_sinan.assert_not_called()
    assert runner.write_bronze.call_args.args == (source, "DENG", 2024)
    assert read.call_args_list == [
        mocker.call(Path("silver.parquet"), columns=["ID_MUNICIP", "SG_UF_NOT"]),
        mocker.call(Path("gold.parquet")),
    ]
    assert (
        runner.write_bronze.call_args.kwargs["run_at"]
        == runner.transform_file.call_args.kwargs["run_at"]
        == runner.aggregate_file.call_args.kwargs["run_at"]
    )
    assert runner.write_bronze.call_args.kwargs["run_at"].tzinfo is not None


def test_publicacao_vazia_explicita_e_falha_liberam_conexao(mocker, pipeline):
    _, engine, _, load = pipeline
    silver = pd.DataFrame({"ID_MUNICIP": ["9999999"]})
    mocker.patch.object(runner.pd, "read_parquet", side_effect=[silver, pd.DataFrame()])
    load.side_effect = ValueError("publicação rejeitada")
    with pytest.raises(ValueError, match="publicação rejeitada"):
        runner.run_load("DENG", 2026, allow_empty=True)
    assert load.call_args.kwargs["expected_cases_total"] == 0
    assert load.call_args.kwargs["allow_empty"] is True
    engine.dispose.assert_called_once()


def test_publicacao_vazia_bloqueia_por_padrao(mocker, pipeline):
    _, engine, _, load = pipeline
    silver = pd.DataFrame({"ID_MUNICIP": ["9999999"]})
    mocker.patch.object(runner.pd, "read_parquet", side_effect=[silver, pd.DataFrame()])

    runner.run_load("deng", 2026)

    assert load.call_args.kwargs["allow_empty"] is False
    engine.dispose.assert_called_once()


def test_run_load_encaminha_metricas_do_metadata_gold(tmp_path, mocker, pipeline):
    aggregate, engine, _, load = pipeline
    gold_path = tmp_path / "gold.parquet"
    aggregate.return_value = gold_path
    gold_path.with_name("metadata.json").write_text(
        '{"source_rows": 4, "resolved_rows": 1, "discarded_rows": 3, '
        '"aggregation_reduction": 0, "invalid_municipality_rows": 0, '
        '"out_of_scope_rows": 3, "uf_mismatch_rows": 0}',
        encoding="utf-8",
    )
    mocker.patch.object(
        runner.pd, "read_parquet",
        side_effect=[
            pd.DataFrame({"ID_MUNICIP": ["330100"]}),
            pd.DataFrame({"cases_total": [1]}),
        ],
    )

    runner.run_load("DENG", 2026)

    assert load.call_args.kwargs["quality_metrics"] == {
        "source_rows": 4,
        "resolved_rows": 1,
        "discarded_rows": 3,
        "aggregation_reduction": 0,
        "invalid_municipality_rows": 0,
        "out_of_scope_rows": 3,
        "uf_mismatch_rows": 0,
    }
    engine.dispose.assert_called_once()


def test_catalogo_ibge_bloqueia_publicacao_com_resolucao_invalida(mocker, pipeline, tmp_path):
    aggregate, engine, get_engine, load = pipeline
    from app.pipeline.reference.ibge.catalog import InMemoryMunicipalityCatalog
    from app.pipeline.reference.ibge.models import CatalogMetadata, Municipality

    catalog = InMemoryMunicipalityCatalog(
        [
            Municipality("3301009", "330100", "Campos", "33", "RJ", "Rio", 2025),
            Municipality("3305000", "330500", "São João da Barra", "33", "RJ", "Rio", 2025),
            Municipality("3302205", "330220", "Itaperuna", "33", "RJ", "Rio", 2025),
            Municipality("3302403", "330240", "Macaé", "33", "RJ", "Rio", 2025),
        ],
        CatalogMetadata("test", 2025, "fixture", "fixture://", "2026-01-01T00:00:00Z", "hash"),
    )
    silver = pd.DataFrame({"ID_MUNICIP": ["330100"]})
    mocker.patch.object(runner.pd, "read_parquet", side_effect=[silver, pd.DataFrame({"cases_total": [1]})])
    aggregate.return_value = Path("gold.parquet")
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        '{"invalid_municipality_rows": 1, "uf_mismatch_rows": 0}', encoding="utf-8"
    )
    mocker.patch.object(Path, "with_name", return_value=metadata_path)

    with pytest.raises(ValueError, match="resoluções municipais inválidas"):
        runner.run_load("DENG", 2026, catalog=catalog)

    load.assert_not_called()
    get_engine.assert_not_called()
    engine.dispose.assert_not_called()


def test_catalogo_ibge_bloqueia_publicacao_com_uf_divergente(
    mocker, pipeline, tmp_path,
):
    aggregate, engine, get_engine, load = pipeline
    from app.pipeline.reference.ibge.catalog import InMemoryMunicipalityCatalog
    from app.pipeline.reference.ibge.models import CatalogMetadata, Municipality

    catalog = InMemoryMunicipalityCatalog(
        [
            Municipality("3301009", "330100", "Campos", "33", "RJ", "Rio", 2025),
            Municipality("3305000", "330500", "São João", "33", "RJ", "Rio", 2025),
            Municipality("3302205", "330220", "Itaperuna", "33", "RJ", "Rio", 2025),
            Municipality("3302403", "330240", "Macaé", "33", "RJ", "Rio", 2025),
        ],
        CatalogMetadata("test", 2025, "fixture", "fixture://", "2026-01-01T00:00:00Z", "hash"),
    )
    mocker.patch.object(
        runner.pd,
        "read_parquet",
        side_effect=[
            pd.DataFrame({"ID_MUNICIP": ["330100"], "SG_UF_NOT": ["33"]}),
            pd.DataFrame({"cases_total": [1]}),
        ],
    )
    aggregate.return_value = Path("gold.parquet")
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        '{"invalid_municipality_rows": 0, "uf_mismatch_rows": 1}',
        encoding="utf-8",
    )
    mocker.patch.object(Path, "with_name", return_value=metadata_path)

    with pytest.raises(ValueError, match="resoluções municipais inválidas"):
        runner.run_load("DENG", 2026, catalog=catalog)

    load.assert_not_called()
    get_engine.assert_not_called()
    engine.dispose.assert_not_called()


def test_run_load_rejeita_escopo_de_catalogo_diferente(mocker, pipeline):
    from app.pipeline.reference.ibge.catalog import InMemoryMunicipalityCatalog
    from app.pipeline.reference.ibge.models import CatalogMetadata, Municipality
    from app.pipeline.scope import GeographicScope

    catalog = InMemoryMunicipalityCatalog(
        [Municipality("3301009", "330100", "Campos", "33", "RJ", "Rio", 2025)],
        CatalogMetadata("test", 2025, "fixture", "fixture://", "2026-01-01T00:00:00Z", "a" * 64),
    )
    stale_scope = GeographicScope((Municipality(
        "3301009", "330100", "Nome antigo", "33", "RJ", "Rio", 2024,
    ),))

    with pytest.raises(ValueError, match="não corresponde"):
        runner.run_load("DENG", 2026, catalog=catalog, geographic_scope=stale_scope)

    runner.fetch_sinan.assert_not_called()
    runner.get_engine.assert_not_called()


def test_run_load_transmite_catalogo_e_escopo_ate_publicacao(mocker, pipeline):
    from app.pipeline.reference.ibge.catalog import InMemoryMunicipalityCatalog
    from app.pipeline.reference.ibge.models import CatalogMetadata, Municipality
    from app.pipeline.scope import GeographicScope

    municipalities = (
        Municipality("3301009", "330100", "Campos", "33", "RJ", "Rio", 2025),
        Municipality("3550308", "355030", "São Paulo", "35", "SP", "São Paulo", 2025),
    )
    catalog = InMemoryMunicipalityCatalog(
        municipalities,
        CatalogMetadata("ibge-dtb-test", 2025, "fixture", "fixture://dtb", "2026-01-01T00:00:00Z", "a" * 64),
    )
    scope = GeographicScope(municipalities, kind="UFs")
    aggregate, engine, _, load = pipeline
    silver = pd.DataFrame({"ID_MUNICIP": ["330100", "3550308"]})
    mocker.patch.object(runner.pd, "read_parquet", side_effect=[silver, pd.DataFrame({"cases_total": [2]})])

    runner.run_load(
        "DENG", 2026, catalog=catalog, geographic_scope=scope,
        cnes_batch_id="20260101T000000Z",
    )

    options = load.call_args.kwargs
    assert options["ibge_catalog"] is catalog
    assert options["municipios"] == ["3301009", "3550308"]
    assert options["geographic_scope_type"] == "UFs"
    assert options["geographic_scope_sha256"] == scope.sha256
    assert aggregate.call_args.kwargs["catalog"] is catalog
    assert aggregate.call_args.kwargs["cnes_batch_id"] == "20260101T000000Z"
    assert aggregate.call_args.kwargs["geographic_scope_type"] == "UFs"
    engine.dispose.assert_called_once()


def test_run_load_nao_conta_codigo_ibge_7_invalido_no_total_independente(
    mocker, pipeline,
):
    from app.pipeline.reference.ibge.catalog import InMemoryMunicipalityCatalog
    from app.pipeline.reference.ibge.models import CatalogMetadata, Municipality
    from app.pipeline.scope import GeographicScope

    catalog = InMemoryMunicipalityCatalog(
        [Municipality("3301009", "330100", "Campos", "33", "RJ", "Rio", 2025)],
        CatalogMetadata("ibge-test", 2025, "fixture", "fixture://", "2026-01-01T00:00:00Z", "a" * 64),
    )
    scope = GeographicScope(catalog.municipalities())
    aggregate, _, _, load = pipeline
    silver = pd.DataFrame({"ID_MUNICIP": ["3301008", "330100"]})
    mocker.patch.object(
        runner.pd, "read_parquet",
        side_effect=[silver, pd.DataFrame({"cases_total": [1]})],
    )

    runner.run_load("DENG", 2026, catalog=catalog, geographic_scope=scope)

    assert load.call_args.kwargs["expected_cases_total"] == 1
    assert aggregate.call_args.kwargs["catalog"] is catalog


def test_run_load_nao_conta_uf_divergente_no_total_independente(mocker, pipeline):
    from app.pipeline.reference.ibge.catalog import InMemoryMunicipalityCatalog
    from app.pipeline.reference.ibge.models import CatalogMetadata, Municipality
    from app.pipeline.scope import GeographicScope

    catalog = InMemoryMunicipalityCatalog(
        [Municipality("3301009", "330100", "Campos", "33", "RJ", "Rio", 2025)],
        CatalogMetadata("ibge-test", 2025, "fixture", "fixture://", "2026-01-01T00:00:00Z", "a" * 64),
    )
    scope = GeographicScope(catalog.municipalities())
    _, _, _, load = pipeline
    silver = pd.DataFrame({"ID_MUNICIP": ["330100"], "SG_UF_NOT": ["35"]})
    mocker.patch.object(
        runner.pd, "read_parquet",
        side_effect=[silver, pd.DataFrame({"cases_total": [0]})],
    )

    runner.run_load("DENG", 2026, catalog=catalog, geographic_scope=scope)

    assert load.call_args.kwargs["expected_cases_total"] == 0
