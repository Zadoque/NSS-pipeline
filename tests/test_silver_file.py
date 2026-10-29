import json
from contextlib import nullcontext
from datetime import UTC, datetime

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from app.pipeline.sinan import silver


RUN_AT = datetime(2026, 10, 13, 12, tzinfo=UTC)


@pytest.fixture
def raw():
    return pd.DataFrame({
        "DT_NOTIFIC": ["20240110", "2024-02-15", "inválida", "20230101",
                       "2024-01-10", "20240320", "20240401", "20240501"],
        "ID_MUNICIP": ["330100", "330240", "330100", "330100", "330100", "330220", None, None],
        "SG_UF_NOT": ["33"] * 8,
        "NU_NOTIFIC": ["1", "2", "inválida", "fora", "1", "3", None, None],
        "SEM_NOT": ["202402", "202407", "202401", "202301", "202402", "202412", "202414", "202418"],
        "NU_ANO": [2024] * 8,
        "CLASSI_FIN": [None, None, None, None, "10", "20", None, None],
        "EVOLUCAO": [None] * 8,
        "CS_SEXO": ["F", "M", "F", "F", "F", "M", None, None],
        "ANO_NASC": pd.array([None, None, 1980, 1970, None, 2000, None, None], dtype="Int64"),
        "CAMPO_FORA_DO_CATALOGO": ["x" * 1000] * 8,
    })


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr(silver, "BASE_DIR", tmp_path / "data")
    return tmp_path / "bronze.parquet"


def read_result(path):
    return pq.ParquetFile(path).read().to_pandas()


@pytest.mark.parametrize("batch_size", [1, 2, 3, 50_000])
@pytest.mark.parametrize("has_id", [True, False])
def test_lotes_equivalem_ao_dataframe_com_dedup_global(raw, source, batch_size, has_id):
    if not has_id:
        raw = raw.drop(columns="NU_NOTIFIC")
        # As datas usam formatos distintos, mas são iguais depois da limpeza.
        raw.loc[4, "CLASSI_FIN"] = None
    raw.to_parquet(source, index=False, row_group_size=3)
    with pytest.warns(UserWarning) if not has_id else nullcontext():
        expected = silver.transform(raw, 2024).reset_index(drop=True)
        result = silver.transform_file(source, "DENG", 2024, run_at=RUN_AT, batch_size=batch_size)

    actual = read_result(result)
    pd.testing.assert_frame_equal(actual, expected)
    assert silver.SOURCE_ROW_COLUMN not in actual.columns
    assert "CAMPO_FORA_DO_CATALOGO" not in actual.columns
    if has_id:
        assert actual.loc[actual["NU_NOTIFIC"] == "1", "CLASSI_FIN"].item() == "10"
        assert actual.loc[actual["NU_NOTIFIC"].isna(), "DT_NOTIFIC"].item() == pd.Timestamp("2024-05-01")

    metadata = json.loads(result.with_name("metadata.json").read_text(encoding="utf-8"))
    assert metadata["source_rows"] == len(raw)
    assert metadata["rows"] == len(expected)
    assert metadata["invalid_date_rows"] == 1
    assert metadata["outside_year_rows"] == 1
    assert metadata["duplicate_rows"] == 6 - len(expected)
    assert metadata["dropped_rows"] == (
        metadata["invalid_date_rows"] + metadata["outside_year_rows"] + metadata["duplicate_rows"]
    )
    assert metadata["columns"] == list(actual.columns)
    assert metadata["batch_id"] == "20261013T120000Z"
    assert metadata["batches_processed"] == (len(raw) + batch_size - 1) // batch_size
    assert "disease=deng" in str(result)
    assert not list(result.parent.glob(".silver-*"))


def test_leitura_projeta_colunas_e_nao_carrega_parquet_inteiro(raw, source, mocker):
    raw.to_parquet(source, index=False)
    expected = silver.transform(raw, 2024).reset_index(drop=True)
    mocker.patch.object(pd, "read_parquet", side_effect=AssertionError("leitura integral"))
    mocker.patch.object(pq.ParquetFile, "read", side_effect=AssertionError("leitura integral"))
    original_iter = pq.ParquetFile.iter_batches
    calls = []

    def iter_batches(self, **kwargs):
        calls.append(kwargs)
        yield from original_iter(self, **kwargs)

    mocker.patch.object(pq.ParquetFile, "iter_batches", iter_batches)
    result = silver.transform_file(source, "DENG", 2024, batch_size=2)
    assert len(calls) == 1
    assert calls[0]["batch_size"] == 2
    assert "CAMPO_FORA_DO_CATALOGO" not in calls[0]["columns"]
    with pq.ParquetFile(result) as output:
        actual = pa.Table.from_batches(list(output.iter_batches(batch_size=2))).to_pandas()
    pd.testing.assert_frame_equal(actual, expected)


@pytest.mark.parametrize("empty_source", [True, False])
def test_saida_vazia_preserva_schema_e_contadores(raw, source, empty_source):
    raw = raw.iloc[:0] if empty_source else raw.assign(DT_NOTIFIC="20230101")
    raw.to_parquet(source, index=False)
    result = silver.transform_file(source, "DENG", 2024, batch_size=2)

    with pq.ParquetFile(result) as output:
        assert output.metadata.num_rows == 0
        assert output.schema_arrow.field("DT_NOTIFIC").type == pa.timestamp("ns")
        assert output.schema_arrow.field("ID_MUNICIP").type == pa.string()
        assert "UF" in output.schema_arrow.names
        assert "NM_UF" in output.schema_arrow.names
        pandas_metadata = json.loads(output.schema_arrow.metadata[b"pandas"])
        assert pandas_metadata["index_columns"] == []
    metadata = json.loads(result.with_name("metadata.json").read_text(encoding="utf-8"))
    assert metadata["rows"] == metadata["duplicate_rows"] == metadata["invalid_date_rows"] == 0
    assert metadata["source_rows"] == metadata["outside_year_rows"] == metadata["dropped_rows"] == len(raw)


def test_tipos_estaveis_quando_primeiros_lotes_sao_nulos(raw, source):
    raw["SEM_NOT"] = pd.array([None, None, None, None, 202402, 202412, 202414, 202418], dtype="Int64")
    raw["CS_SEXO"] = pd.Categorical(raw["CS_SEXO"], categories=["F", "M", "I"])
    raw.to_parquet(source, index=False)
    result = silver.transform_file(source, "DENG", 2024, batch_size=1)
    with pq.ParquetFile(result) as output:
        assert output.schema_arrow.field("EVOLUCAO").type == pa.null()
        assert output.schema_arrow.field("SEM_NOT").type == pa.int64()
        assert pa.types.is_dictionary(output.schema_arrow.field("CS_SEXO").type)
    actual = read_result(result)
    assert actual.loc[actual["NU_NOTIFIC"] == "1", "SEM_NOT"].item() == 202402
    assert actual.loc[actual["NU_NOTIFIC"] == "2", "SEM_NOT"].isna().all()


def test_falha_na_dedup_preserva_lote_anterior_e_remove_temporarios(raw, source, monkeypatch):
    raw.to_parquet(source, index=False)
    result = silver.transform_file(source, "DENG", 2024, run_at=RUN_AT, batch_size=2)
    previous = result.read_bytes()
    previous_metadata = result.with_name("metadata.json").read_bytes()

    def fail(*args, **kwargs):
        args[1].write_bytes(b"arquivo incompleto")
        raise OSError("disco cheio")

    monkeypatch.setattr(silver, "_deduplicate_file", fail)
    with pytest.raises(OSError, match="disco cheio"):
        silver.transform_file(source, "DENG", 2024, run_at=RUN_AT, batch_size=2)
    assert result.read_bytes() == previous
    assert result.with_name("metadata.json").read_bytes() == previous_metadata
    assert not list(result.parent.glob(".silver-*"))


def test_falha_durante_leitura_nao_publica_parquet(raw, source, monkeypatch):
    raw.to_parquet(source, index=False)
    original_iter = pq.ParquetFile.iter_batches

    def fail_after_first(self, **kwargs):
        yield next(original_iter(self, **kwargs))
        raise OSError("leitura interrompida")

    monkeypatch.setattr(pq.ParquetFile, "iter_batches", fail_after_first)
    with pytest.raises(OSError, match="leitura interrompida"):
        silver.transform_file(source, "DENG", 2024, batch_size=1)
    assert not list(silver.BASE_DIR.rglob("data.parquet"))
    assert not list(silver.BASE_DIR.rglob(".silver-*"))


@pytest.mark.parametrize("batch_size", [0, -1])
def test_tamanho_de_lote_invalido_falha_antes_da_leitura(source, batch_size):
    with pytest.raises(ValueError, match="batch_size"):
        silver.transform_file(source, "DENG", 2024, batch_size=batch_size)


def test_schema_incompleto_falha_antes_de_criar_lote(raw, source):
    raw.drop(columns="SEM_NOT").to_parquet(source, index=False)
    with pytest.raises(ValueError, match="Colunas obrigatórias.*SEM_NOT"):
        silver.transform_file(source, "DENG", 2024)
    assert not silver.BASE_DIR.exists()


def test_run_at_ausente_obtem_horario_em_utc(raw, source, monkeypatch):
    raw.to_parquet(source, index=False)
    observed = []

    class FakeDateTime:
        @classmethod
        def now(cls, tz):
            observed.append(tz)
            return RUN_AT

    monkeypatch.setattr(silver, "datetime", FakeDateTime)
    silver.transform_file(source, "DENG", 2024, batch_size=2)
    assert observed == [UTC]


def test_cli_normaliza_argumentos_e_aplica_defaults(monkeypatch, capsys):
    captured = {}

    def fake_transform_file(source, disease, year, *, batch_size, memory_limit):
        captured.update(
            source=source,
            disease=disease,
            year=year,
            batch_size=batch_size,
            memory_limit=memory_limit,
        )
        return source

    monkeypatch.setattr(silver, "transform_file", fake_transform_file)
    monkeypatch.setattr("sys.argv", ["silver", "--source", "bronze.parquet", "--disease", "deng", "--year", "2024"])
    silver.main()

    expected_source = silver.Path("bronze.parquet")
    assert captured == {
        "source": expected_source,
        "disease": "DENG",
        "year": 2024,
        "batch_size": silver.DEFAULT_BATCH_SIZE,
        "memory_limit": silver.DEFAULT_MEMORY_LIMIT,
    }
    assert str(expected_source) in capsys.readouterr().out


@pytest.mark.parametrize(
    "missing", ["--source", "--disease", "--year"]
)
def test_cli_rejeita_argumento_obrigatorio_ausente(missing, monkeypatch):
    values = {
        "--source": "bronze.parquet",
        "--disease": "DENG",
        "--year": "2024",
    }
    args = ["silver"]
    for option, value in values.items():
        if option != missing:
            args.extend([option, value])
    monkeypatch.setattr("sys.argv", args)
    with pytest.raises(SystemExit):
        silver.main()


def test_cli_processa_silver_isolada(raw, source, monkeypatch, capsys):
    raw.to_parquet(source, index=False)
    monkeypatch.setattr("sys.argv", [
        "silver", "--source", str(source), "--disease", "deng", "--year", "2024",
        "--batch-size", "2", "--memory-limit", "128MB",
    ])
    silver.main()
    result, = silver.BASE_DIR.rglob("data.parquet")
    assert str(result) in capsys.readouterr().out
    assert len(read_result(result)) == 4


@pytest.mark.parametrize("count,memory_limit", [(200_000, "32MB"), (1_000_000, "64MB")])
def test_dedup_global_com_volume_maior_e_memoria_reduzida(source, count, memory_limit):
    table = pa.table({
        "DT_NOTIFIC": pa.repeat(pa.scalar("20240110"), count),
        "ID_MUNICIP": pa.repeat(pa.scalar("330100"), count),
        "SG_UF_NOT": pa.repeat(pa.scalar("33"), count),
        "NU_NOTIFIC": [str(index % (count // 2)) for index in range(count)],
        "SEM_NOT": pa.repeat(pa.scalar("202402"), count),
        "CS_SEXO": ["F"] * (count // 2) + ["M"] * (count // 2),
        "ANO_NASC": pa.repeat(pa.scalar(2000), count),
    })
    pq.write_table(table, source, row_group_size=10_000)
    result = silver.transform_file(source, "DENG", 2024, batch_size=10_000, memory_limit=memory_limit)
    with pq.ParquetFile(result) as output:
        assert output.metadata.num_rows == count // 2
        assert output.read(columns=["CS_SEXO"]).column(0).unique().to_pylist() == ["M"]
