import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from app.pipeline import run as runner
from app.pipeline.sinan import bronze, gold, silver, source as sinan_source


RUN_AT = datetime(2026, 10, 9, 14, 30, tzinfo=UTC)


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr(bronze, "BASE_DIR", tmp_path / "data")
    path = tmp_path / "source.parquet"
    pq.write_table(pa.table({
        "ID_MUNICIP": ["330100", "330240"],
        "CAMPO_EXTRA": ["original", None],
    }), path)
    return path


def test_fetch_retorna_arquivo_sem_materializar_dataframe(mocker, source):
    original = source.read_bytes()

    async def download(*, output):
        output.write_bytes(original)

    remote = SimpleNamespace(
        path="DENGBR24.parquet", size=len(original),
        download=mocker.AsyncMock(side_effect=download),
    )
    catalog = mocker.patch.object(sinan_source.pysus.ftp, "sinan", return_value=[remote])
    mocker.patch.object(sinan_source, "SOURCE_DIR", source.parent / "cache")
    mocker.patch("pandas.read_parquet", side_effect=AssertionError("leitura em memória"))

    result = bronze.fetch_sinan("deng", 2024)
    assert result == sinan_source.SOURCE_DIR / "disease=deng/source_year=2024/data.parquet"
    assert result.read_bytes() == original
    assert catalog.call_args_list == [
        mocker.call(disease="DENG", year=2024, download=False),
        mocker.call(disease="DENG", year=2024, download=False),
    ]
    remote.download.assert_awaited_once()
    assert not list(result.parent.glob(".download-*"))


def test_fetch_preserva_causa_da_falha(mocker):
    failure = OSError("download interrompido")
    mocker.patch.object(bronze, "inspect_remote_file", side_effect=failure)
    with pytest.raises(RuntimeError, match="disease=DENG, year=2024") as error:
        bronze.fetch_sinan("DENG", 2024)
    assert error.value.__cause__ is failure


def test_bronze_preserva_bytes_e_metadados_sem_ler_registros(mocker, source):
    mocker.patch.object(pq.ParquetFile, "read", side_effect=AssertionError("leitura de registros"))
    mocker.patch("pandas.read_parquet", side_effect=AssertionError("leitura em memória"))
    result = bronze.write_bronze(source, "deng", 2024, run_at=RUN_AT)

    assert result == (
        bronze.BASE_DIR / "bronze/sinan/disease=deng/source_year=2024"
        / "ingestion_date=2026-10-09/batch_id=20261009T143000Z/data.parquet"
    )
    assert result.read_bytes() == source.read_bytes()
    assert json.loads(result.with_name("metadata.json").read_text(encoding="utf-8")) == {
        "disease": "DENG", "source_year": 2024, "batch_id": "20261009T143000Z",
        "ingested_at": RUN_AT.isoformat(), "rows": 2,
        "columns": ["ID_MUNICIP", "CAMPO_EXTRA"], "source": "PySUS SINAN",
    }


def test_atualizacao_do_cache_nao_altera_lote_anterior(source):
    first = bronze.write_bronze(source, "DENG", 2024, run_at=RUN_AT)
    original = first.read_bytes()
    pq.write_table(pa.table({"ID_MUNICIP": ["330100"]}), source)
    second = bronze.write_bronze(source, "DENG", 2024, run_at=RUN_AT + timedelta(seconds=1))

    assert first != second
    assert first.read_bytes() == original
    assert second.read_bytes() == source.read_bytes()
    assert second.read_bytes() != original


def test_falha_de_copia_preserva_arquivo_anterior_e_remove_temporario(source, monkeypatch):
    result = bronze.write_bronze(source, "DENG", 2024, run_at=RUN_AT)
    original = result.read_bytes()
    metadata = result.with_name("metadata.json").read_bytes()

    def fail_copy(source_path, temporary_path):
        temporary_path.write_bytes(b"copia incompleta")
        raise OSError("disco cheio")

    monkeypatch.setattr(bronze.shutil, "copyfile", fail_copy)
    with pytest.raises(OSError, match="disco cheio"):
        bronze.write_bronze(source, "DENG", 2024, run_at=RUN_AT)

    assert result.read_bytes() == original
    assert result.with_name("metadata.json").read_bytes() == metadata
    assert not list(result.parent.glob("*.tmp"))


def test_parquet_vazio_nao_cria_lote(source):
    pq.write_table(pa.table({"ID_MUNICIP": pa.array([], type=pa.string())}), source)
    with pytest.raises(RuntimeError, match="Parquet vazio"):
        bronze.write_bronze(source, "DENG", 2024, run_at=RUN_AT)
    assert not bronze.BASE_DIR.exists()


def test_write_bronze_sem_run_at_registra_timestamp_com_fuso(source):
    result = bronze.write_bronze(source, "DENG", 2024)

    metadata = json.loads(result.with_name("metadata.json").read_text(encoding="utf-8"))
    assert metadata["ingested_at"].endswith("+00:00")
    assert metadata["batch_id"].endswith("Z")


def test_main_delega_download_e_escrita(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["bronze", "--disease", "deng", "--year", "2024"])
    source_path = Path("source.parquet")
    monkeypatch.setattr(bronze, "fetch_sinan", lambda disease, year: source_path)
    monkeypatch.setattr(bronze, "write_bronze", lambda source, disease, year: Path("bronze.parquet"))

    bronze.main()

    assert capsys.readouterr().out.strip() == "bronze.parquet"


def test_arquivo_invalido_nao_cria_lote(source):
    source.write_bytes(b"download incompleto")
    with pytest.raises(pa.ArrowInvalid):
        bronze.write_bronze(source, "DENG", 2024, run_at=RUN_AT)
    assert not bronze.BASE_DIR.exists()


def test_parquet_bruto_continua_compativel_com_silver_e_gold(source, monkeypatch):
    pq.write_table(pa.table({
        "DT_NOTIFIC": ["2024-01-05", "2024-01-07"],
        "ID_MUNICIP": ["330100", "330240"],
        "SG_UF_NOT": ["33", "33"],
        "NU_NOTIFIC": ["1", "2"],
        "CS_SEXO": ["M", "F"],
        "ANO_NASC": ["1990", "2000"],
        "SEM_NOT": ["202401", "202401"],
    }), source)
    monkeypatch.setattr(runner, "fetch_sinan", lambda disease, year: source)
    monkeypatch.setattr(silver, "BASE_DIR", bronze.BASE_DIR)
    monkeypatch.setattr(gold, "BASE_DIR", bronze.BASE_DIR)

    runner.run("deng", 2024)

    bronze_path, = bronze.BASE_DIR.glob("bronze/sinan/**/data.parquet")
    silver_path, = bronze.BASE_DIR.glob("silver/sinan/**/data.parquet")
    gold_path, = bronze.BASE_DIR.glob("gold/ad_hoc/sinan/**/data.parquet")
    assert bronze_path.read_bytes() == source.read_bytes()
    result = pq.ParquetFile(gold_path).read().to_pandas()
    assert result["cases_total"].sum() == 2
    assert set(result["cd_mun"]) == {"3301009", "3302403"}
    assert set(result["year"]) == {2024}
    batches = {
        json.loads(path.with_name("metadata.json").read_text(encoding="utf-8"))["batch_id"]
        for path in (bronze_path, silver_path, gold_path)
    }
    assert len(batches) == 1
