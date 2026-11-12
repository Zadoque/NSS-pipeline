import json
from zipfile import ZipFile
from datetime import UTC, datetime

import pandas as pd
import pytest

from app.pipeline.cnes import bronze as cnes_bronze
from app.pipeline.cnes import silver as cnes_silver
from app.pipeline.esporo import bronze as esporo_bronze
from app.pipeline.esporo import run as esporo_run


def test_transform_cnes_normalizes_codes_and_keeps_last_duplicate():
    source = pd.DataFrame(
        {
            "codigo_cnes": [12, 12],
            "nome_fantasia": ["antigo", "atual"],
            "codigo_municipio": [3301009, 3301009],
            "codigo_tipo_unidade": [1, 2],
            "campo_ignorado": ["x", "y"],
        }
    )

    result = cnes_silver.transform_cnes(source)

    assert result.to_dict("records") == [
        {
            "cd_unidade": "0000012",
            "nm_unidade": "atual",
            "codigo_municipio": "3301009",
            "tp_unidade": 2,
        }
    ]


def test_transform_cnes_resolves_canonical_municipality_with_catalog():
    from app.pipeline.reference.ibge.catalog import InMemoryMunicipalityCatalog
    from app.pipeline.reference.ibge.models import CatalogMetadata, Municipality

    catalog = InMemoryMunicipalityCatalog(
        [Municipality("3301009", "330100", "Campos", "33", "RJ", "Rio", 2025)],
        CatalogMetadata("test", 2025, "fixture", "fixture://", "2026-01-01T00:00:00Z", "hash"),
    )
    result = cnes_silver.transform_cnes(
        pd.DataFrame({"codigo_cnes": [12], "codigo_municipio": ["330100"]}),
        catalog=catalog,
    )
    assert result.loc[0, "cd_mun"] == "3301009"
    assert result.loc[0, "municipality_resolution_status"] == "VALID"


def test_transform_cnes_sinaliza_municipio_retornado_fora_do_solicitado():
    from app.pipeline.reference.ibge.catalog import InMemoryMunicipalityCatalog
    from app.pipeline.reference.ibge.models import CatalogMetadata, Municipality

    catalog = InMemoryMunicipalityCatalog(
        [
            Municipality("3301009", "330100", "Campos", "33", "RJ", "Rio", 2025),
            Municipality("3305000", "330500", "São João da Barra", "33", "RJ", "Rio", 2025),
        ],
        CatalogMetadata("test", 2025, "fixture", "fixture://", "2026-01-01T00:00:00Z", "hash"),
    )
    result = cnes_silver.transform_cnes(
        pd.DataFrame({"codigo_cnes": [12], "codigo_municipio": ["330500"]}),
        catalog=catalog,
        municipality_code7="3301009",
    )

    assert pd.isna(result.loc[0, "cd_mun"])
    assert result.loc[0, "municipality_resolution_status"] == "OUT_OF_SCOPE"


def test_fetch_estabelecimentos_rejeita_limit_invalido(monkeypatch):
    with pytest.raises(ValueError, match="maior que zero"):
        cnes_bronze.fetch_estabelecimentos("3301009", limit=0)


def test_fetch_estabelecimentos_rejeita_geocodigo_unicode_sem_catalogo():
    with pytest.raises(ValueError, match="código municipal IBGE"):
        cnes_bronze.fetch_estabelecimentos("３３０１００９")


def test_fetch_estabelecimentos_rejeita_timeout_invalido():
    with pytest.raises(ValueError, match="timeout CNES"):
        cnes_bronze.fetch_estabelecimentos("3301009", timeout=0)


def test_transform_cnes_file_publishes_metadata(tmp_path, monkeypatch):
    source = tmp_path / "bronze.parquet"
    pd.DataFrame({"codigo_cnes": [12], "codigo_municipio": [3301009]}).to_parquet(
        source, index=False
    )
    monkeypatch.setattr(cnes_silver, "BASE_DIR", tmp_path / "data")

    result = cnes_silver.transform_cnes_file(
        source, "3301009", run_at=datetime(2026, 10, 29, tzinfo=UTC)
    )

    metadata = json.loads(result.with_name("metadata.json").read_text(encoding="utf-8"))
    assert result.exists()
    assert metadata["rows"] == 1
    assert metadata["dropped_rows"] == 0


def test_fetch_estabelecimentos_usa_cnes_nacional_pysus_e_normaliza_zero(
    mocker, tmp_path, monkeypatch
):
    monkeypatch.setattr(cnes_bronze, "BASE_DIR", tmp_path)
    monkeypatch.setattr(cnes_bronze, "_NATIONAL_CNES", None)
    pysus = mocker.Mock()
    pysus.saude.cnes.return_value = pd.DataFrame(
        {
            "CO_CNES": [729884, 6829538, 9999999],
            "CO_IBGE": [330100, 330100, 330500],
            "NO_FANTASIA": ["BEDALAB", "BEDALAB", "Outro"],
            "NO_BAIRRO": ["Centro", "Pelinca", "Centro"],
        }
    )
    mocker.patch.dict("sys.modules", {"pysus": pysus})

    result = cnes_bronze.fetch_estabelecimentos("3301009")

    assert result["codigo_cnes"].tolist() == ["0729884", "6829538"]
    assert result["codigo_municipio"].tolist() == ["330100", "330100"]
    pysus.saude.cnes.assert_called_once_with(download=False)


def test_fetch_estabelecimentos_reutiliza_snapshot_nacional(mocker, tmp_path, monkeypatch):
    monkeypatch.setattr(cnes_bronze, "BASE_DIR", tmp_path)
    monkeypatch.setattr(cnes_bronze, "_NATIONAL_CNES", None)
    pysus = mocker.Mock()
    pysus.saude.cnes.return_value = pd.DataFrame(
        {"CO_CNES": [1], "CO_IBGE": [330100]}
    )
    mocker.patch.dict("sys.modules", {"pysus": pysus})

    cnes_bronze.fetch_estabelecimentos("3301009")
    cnes_bronze.fetch_estabelecimentos("3302403")

    pysus.saude.cnes.assert_called_once()


def test_fetch_estabelecimentos_le_csv_zip_baixado_pelo_pysus(mocker, tmp_path, monkeypatch):
    monkeypatch.setattr(cnes_bronze, "BASE_DIR", tmp_path)
    monkeypatch.setattr(cnes_bronze, "_NATIONAL_CNES", None)
    cache = tmp_path / "pysus"
    archive_dir = cache / "downloads" / "saude" / "cnes"
    archive_dir.mkdir(parents=True)
    archive = archive_dir / "CNES Estabelecimentos.csv"
    payload = (
        "CO_CNES;CO_IBGE;NO_FANTASIA;NO_BAIRRO\n"
        "729884;330100;BEDALAB;Centro\n"
    ).encode("latin1")
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("cnes_estabelecimentos.csv", payload)

    pysus = mocker.Mock()
    source = mocker.Mock()
    source.download.return_value.paths = [archive]
    pysus.saude.cnes.return_value = source
    mocker.patch.dict("sys.modules", {"pysus": pysus})

    result = cnes_bronze.fetch_estabelecimentos("3301009")

    assert result.iloc[0]["codigo_cnes"] == "0729884"
    assert result.iloc[0]["bairro_estabelecimento"] == "Centro"


def test_fetch_estabelecimentos_uses_validated_catalog_crosswalk(mocker, tmp_path, monkeypatch):
    from app.pipeline.reference.ibge.catalog import InMemoryMunicipalityCatalog
    from app.pipeline.reference.ibge.models import CatalogMetadata, Municipality

    catalog = InMemoryMunicipalityCatalog(
        [Municipality("3301009", "330100", "Campos", "33", "RJ", "Rio", 2025)],
        CatalogMetadata("test", 2025, "fixture", "fixture://", "2026-01-01T00:00:00Z", "hash"),
    )
    monkeypatch.setattr(cnes_bronze, "BASE_DIR", tmp_path)
    monkeypatch.setattr(cnes_bronze, "_NATIONAL_CNES", None)
    pysus = mocker.Mock()
    pysus.saude.cnes.return_value = pd.DataFrame(
        {"CO_CNES": [1], "CO_IBGE": [330100]}
    )
    mocker.patch.dict("sys.modules", {"pysus": pysus})

    cnes_bronze.fetch_estabelecimentos("3301009", catalog=catalog)

    assert pysus.saude.cnes.call_count == 1


def test_esporo_run_passes_same_run_timestamp_to_silver(mocker, tmp_path):
    bronze = tmp_path / "bronze.parquet"
    silver = tmp_path / "silver.parquet"
    mocker.patch.object(esporo_run, "injestion_esporo", return_value=bronze)
    transform = mocker.patch.object(esporo_run, "transform_file", return_value=silver)

    esporo_run.run(tmp_path / "source.csv")

    assert transform.call_args.args == (bronze,)
    assert transform.call_args.kwargs["run_at"].tzinfo is UTC


def test_write_bronze_esporo_writes_rows_and_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(esporo_bronze, "BASE_DIR", tmp_path / "data")

    result = esporo_bronze.write_bronze_esporo(pd.DataFrame({"animal": ["Mia"]}), 2026)

    metadata = json.loads(result.with_name("metadata.json").read_text(encoding="utf-8"))
    assert result.exists()
    assert metadata["rows"] == 1
    assert metadata["columns"] == ["animal"]
