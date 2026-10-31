from datetime import UTC, datetime
import json

import pandas as pd
import pyarrow.parquet as pq
import pytest

from app.pipeline.sinan import gold
from app.pipeline.scope import scope_sha256


RUN_AT = datetime(2026, 10, 14, tzinfo=UTC)
MUNICIPIOS = {"3301009": "Campos dos Goytacazes"}
SELECTED = ["unidade_notificacao", "classificacao_final", "sexo", "semana_notificacao"]


@pytest.fixture
def raw():
    return pd.DataFrame({
        "DT_NOTIFIC": pd.to_datetime(["2024-01-10"] * 8),
        "ID_MUNICIP": pd.Series(["9999999", "330100", "3301009", "330100", "330100", "330100", "0330100", "330100"], dtype="string"),
        "SG_UF_NOT": pd.Series(["33"] * 8, dtype="string"),
        "NM_UF": ["Rio de Janeiro"] * 8,
        "CS_SEXO": pd.Series(["F", "F", "F", None, None, "M", "F", "F"], dtype="string"),
        "ANO_NASC": pd.Series([1990, 1990, 1990, None, None, 2000, 1990, 1990], dtype="Int64"),
        "SEM_NOT": pd.Series([202402, 202402, 202402, None, None, 202402, 202402, 202402], dtype="Int64"),
        "ID_UNIDADE": pd.Series([None, "0729884.0", "0729884", None, None, "2298317", "0729884", "0729884"], dtype="string"),
        "CLASSI_FIN": pd.Series([None, "1", "1", None, None, "2", "1", "1"], dtype="string"),
        "NU_IDADE_N": pd.Series([None, "3006", "4040", None, None, "4024", "4040", "3006"], dtype="string"),
        "UNUSED_LARGE_COLUMN": ["ignorado"] * 8,
    })


@pytest.fixture
def lookup():
    return pd.DataFrame({
        "cd_unidade": ["0729884"],
        "nm_unidade": ["UBS TESTE"],
        "razao_social_unidade": ["UBS TESTE LTDA"],
        "tp_unidade": [2],
        "notification_district_id": ["DIST_SEDE"],
        "notification_neighborhood_id": ["BAIRRO_CENTRO"],
        "notification_territory_status": ["NOTIFICATION_NEIGHBORHOOD"],
    })


@pytest.fixture
def source(raw, tmp_path, monkeypatch):
    path = tmp_path / "silver.parquet"
    raw.to_parquet(path, index=False, row_group_size=2)
    path.with_name("metadata.json").write_text(
        json.dumps({"disease": "DENG", "source_year": 2024}), encoding="utf-8",
    )
    monkeypatch.setattr(gold, "BASE_DIR", tmp_path / "data")
    return path


@pytest.mark.parametrize("batch_size", [1, 2, 50_000])
@pytest.mark.parametrize("with_cnes", [False, True])
@pytest.mark.parametrize("target", ["ad_hoc", "serving"])
def test_lotes_equivalem_agregacao_completa(raw, source, lookup, monkeypatch, batch_size, with_cnes, target):
    cnes = lookup if with_cnes else None
    expected = gold.aggregate(raw, "DENG", SELECTED, MUNICIPIOS, cnes)
    monkeypatch.setattr(gold, "_latest_cnes_lookup", lambda: cnes)
    monkeypatch.setattr(gold.pd, "read_parquet", lambda *args, **kwargs: pytest.fail("leitura integral"))
    aggregate = gold.aggregate
    def check_batch(frame, *args, **kwargs):
        assert len(frame) <= batch_size
        assert "UNUSED_LARGE_COLUMN" not in frame
        return aggregate(frame, *args, **kwargs)
    monkeypatch.setattr(gold, "aggregate", check_batch)
    result = gold.aggregate_file(
        source, "DENG", 2024, SELECTED, MUNICIPIOS, RUN_AT, target,
        batch_size=batch_size,
    )
    actual = pq.ParquetFile(result).read().to_pandas()
    pd.testing.assert_frame_equal(actual, expected)
    assert actual["cases_total"].sum() == 7
    assert "UNUSED_LARGE_COLUMN" not in actual
    metadata = json.loads(result.with_name("metadata.json").read_text(encoding="utf-8"))
    assert metadata["source_rows"] == 8
    assert metadata["rows"] == len(expected)
    assert metadata["dropped_rows"] == 1
    assert metadata["batch_size"] == batch_size
    assert metadata["batches_processed"] == (8 + batch_size - 1) // batch_size
    assert metadata["gold_target"] == target
    assert metadata["resolved_rows"] == 7
    assert metadata["discarded_rows"] == 1
    assert metadata["aggregation_reduction"] == 7 - len(expected)
    assert metadata["geographic_scope"]["type"] == "MUNICIPALITIES"
    assert metadata["geographic_scope"]["scope_sha256"] == scope_sha256(MUNICIPIOS)


@pytest.mark.parametrize("empty_source", [False, True])
def test_saida_vazia_preserva_contrato(raw, source, monkeypatch, empty_source):
    raw = raw.iloc[:0] if empty_source else raw.assign(ID_MUNICIP="9999999")
    raw.to_parquet(source, index=False)
    monkeypatch.setattr(gold, "_latest_cnes_lookup", lambda: None)
    expected = gold.aggregate(raw, "DENG", SELECTED, MUNICIPIOS)
    result = gold.aggregate_file(source, "DENG", 2024, SELECTED, MUNICIPIOS, batch_size=1)
    actual = pq.ParquetFile(result).read().to_pandas()
    pd.testing.assert_frame_equal(actual, expected)


def test_coluna_obrigatoria_ausente_e_rejeitada_em_arquivo_vazio(raw, source):
    raw.iloc[:0].drop(columns="SEM_NOT").to_parquet(source, index=False)
    with pytest.raises(ValueError, match="Colunas Silver ausentes.*SEM_NOT"):
        gold.aggregate_file(source, "DENG", 2024)


def test_falha_entre_lotes_preserva_saida_anterior(source, monkeypatch):
    monkeypatch.setattr(gold, "_latest_cnes_lookup", lambda: None)
    result = gold.aggregate_file(source, "DENG", 2024, run_at=RUN_AT, batch_size=2)
    before = result.read_bytes()
    before_metadata = result.with_name("metadata.json").read_bytes()
    aggregate = gold.aggregate
    calls = 0
    def fail_in_later_batch(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("falha no segundo lote")
        return aggregate(*args, **kwargs)
    monkeypatch.setattr(gold, "aggregate", fail_in_later_batch)
    with pytest.raises(RuntimeError, match="segundo lote"):
        gold.aggregate_file(source, "DENG", 2024, run_at=RUN_AT, batch_size=2)
    assert result.read_bytes() == before
    assert result.with_name("metadata.json").read_bytes() == before_metadata


@pytest.mark.parametrize("batch_size", [0, -1])
def test_tamanho_de_lote_invalido(source, batch_size):
    with pytest.raises(ValueError, match="batch_size"):
        gold.aggregate_file(source, "DENG", 2024, batch_size=batch_size)


def test_tamanho_de_lote_zero_falha_antes_de_abrir_o_parquet(source, monkeypatch):
    monkeypatch.setattr(
        gold.pq, "ParquetFile", lambda *_args, **_kwargs: pytest.fail("leitura inesperada")
    )
    with pytest.raises(ValueError, match="maior que zero"):
        gold.aggregate_file(source, "DENG", 2024, batch_size=0)


def test_aggregate_file_valida_metadata_da_silver(source):
    source.with_name("metadata.json").write_text(
        json.dumps({"disease": "ZIKA", "source_year": 2024}), encoding="utf-8"
    )
    with pytest.raises(ValueError):
        gold.aggregate_file(source, "DENG", 2024)


def test_aggregate_file_exige_metadata_da_silver(source):
    source.with_name("metadata.json").unlink()
    with pytest.raises(FileNotFoundError):
        gold.aggregate_file(source, "DENG", 2024)


def test_latest_cnes_lookup_retorna_o_batch_mais_recente(tmp_path, monkeypatch):
    cnes_dir = tmp_path / "silver" / "cnes"
    older = cnes_dir / "batch_id=20260101" / "data.parquet"
    middle = cnes_dir / "batch_id=20260115" / "data.parquet"
    newer = cnes_dir / "batch_id=20260201" / "data.parquet"
    older.parent.mkdir(parents=True)
    middle.parent.mkdir(parents=True)
    newer.parent.mkdir(parents=True)
    older.write_bytes(b"old")
    middle.write_bytes(b"middle")
    newer.write_bytes(b"new")
    monkeypatch.setattr(gold, "BASE_DIR", tmp_path)
    monkeypatch.setattr(gold.pd, "read_parquet", lambda path: path.read_bytes())

    assert gold._latest_cnes_lookup() == b"new"


def test_gold_fixa_lote_cnes_explicitamente(source, lookup, tmp_path, monkeypatch):
    batch_id = "20261014T120000Z"
    batch_path = tmp_path / "data" / "silver" / "cnes" / f"batch_id={batch_id}"
    batch_path.mkdir(parents=True)
    lookup.to_parquet(batch_path / "data.parquet", index=False)
    monkeypatch.setattr(gold, "BASE_DIR", tmp_path / "data")
    monkeypatch.setattr(gold, "_latest_cnes_lookup", lambda: pytest.fail("lote implícito usado"))

    result = gold.aggregate_file(
        source, "DENG", 2024, SELECTED, MUNICIPIOS, RUN_AT,
        cnes_batch_id=batch_id,
    )
    metadata = json.loads(result.with_name("metadata.json").read_text(encoding="utf-8"))
    assert metadata["cnes_batch_id"] == batch_id
    assert "nm_unidade" in pq.ParquetFile(result).schema.names


def test_gold_rejeita_lote_cnes_inexistente(source, tmp_path, monkeypatch):
    monkeypatch.setattr(gold, "BASE_DIR", tmp_path / "data")
    with pytest.raises(FileNotFoundError, match="lote CNES"):
        gold.aggregate_file(source, "DENG", 2024, cnes_batch_id="20261014T120000Z")


def test_latest_cnes_lookup_retorna_none_sem_batches(tmp_path, monkeypatch):
    monkeypatch.setattr(gold, "BASE_DIR", tmp_path)
    assert gold._latest_cnes_lookup() is None


def test_latest_cnes_lookup_retorna_none_com_diretorio_vazio(tmp_path, monkeypatch):
    (tmp_path / "silver" / "cnes").mkdir(parents=True)
    monkeypatch.setattr(gold, "BASE_DIR", tmp_path)
    assert gold._latest_cnes_lookup() is None


def test_aggregate_file_publica_doenca_em_minusculas_e_utc_sem_run_at(
    raw, source, monkeypatch
):
    observed = []

    class FakeDateTime:
        @classmethod
        def now(cls, tz):
            observed.append(tz)
            return RUN_AT

    monkeypatch.setattr(gold, "datetime", FakeDateTime)
    monkeypatch.setattr(gold, "_latest_cnes_lookup", lambda: None)
    result = gold.aggregate_file(
        source, "deng", 2024, municipios={"3301009": "Campos"}, batch_size=2
    )

    assert observed == [UTC]
    assert "disease=deng" in result.as_posix()


def test_aggregate_com_cnes_sem_id_unidade_mantem_unidade_nao_mapeada(raw, lookup):
    raw = raw.drop(columns="ID_UNIDADE")
    result = gold.aggregate(
        raw, "DENG", SELECTED, MUNICIPIOS, lookup
    )

    assert result["notification_territory_status"].eq(
        "UNMAPPED_NOTIFICATION_UNIT"
    ).all()


def test_aggregate_com_status_cnes_nulo_aplica_default(raw, lookup):
    lookup = lookup.copy()
    lookup["notification_territory_status"] = None
    result = gold.aggregate(raw, "DENG", SELECTED, MUNICIPIOS, lookup)

    assert result["notification_territory_status"].eq(
        "UNMAPPED_NOTIFICATION_UNIT"
    ).any()


def test_aggregate_com_lookup_sem_dimensoes_territoriais_aplica_defaults(raw):
    lookup = pd.DataFrame({"cd_unidade": ["0729884"]})
    result = gold.aggregate(raw, "DENG", SELECTED, MUNICIPIOS, lookup)

    assert result["notification_territory_status"].eq(
        "UNMAPPED_NOTIFICATION_UNIT"
    ).all()


def test_aggregate_file_imprime_progresso_no_decimo_lote(raw, source, monkeypatch, capsys):
    raw = pd.concat([raw, raw], ignore_index=True)
    raw.to_parquet(source, index=False)
    monkeypatch.setattr(gold, "_latest_cnes_lookup", lambda: None)

    gold.aggregate_file(source, "DENG", 2024, municipios=MUNICIPIOS, batch_size=1)

    assert "Gold: lotes=10" in capsys.readouterr().out


def test_dimensao_categorica_nao_cria_grupos_sem_casos(raw, source, monkeypatch):
    raw["CLASSI_FIN"] = pd.Categorical(raw["CLASSI_FIN"], categories=["1", "2", "9"])
    raw.to_parquet(source, index=False)
    monkeypatch.setattr(gold, "_latest_cnes_lookup", lambda: None)
    expected = gold.aggregate(raw, "DENG", SELECTED, MUNICIPIOS)
    result = gold.aggregate_file(source, "DENG", 2024, SELECTED, MUNICIPIOS, batch_size=1)
    actual = pq.ParquetFile(result).read().to_pandas()
    pd.testing.assert_frame_equal(actual, expected)
    assert actual["cases_total"].gt(0).all()


def test_volume_maior_soma_grupo_entre_lotes(source, monkeypatch):
    import pyarrow as pa
    count = 200_000
    table = pa.table({
        "DT_NOTIFIC": pa.repeat(pa.scalar(pd.Timestamp("2024-01-10")), count),
        "ID_MUNICIP": pa.repeat(pa.scalar("330100"), count),
        "SG_UF_NOT": pa.repeat(pa.scalar("33"), count),
        "NM_UF": pa.repeat(pa.scalar("Rio de Janeiro"), count),
        "CS_SEXO": pa.repeat(pa.scalar("F"), count),
        "ANO_NASC": pa.repeat(pa.scalar(1990), count),
        "SEM_NOT": pa.repeat(pa.scalar(202402), count),
    })
    pq.write_table(table, source, row_group_size=10_000)
    monkeypatch.setattr(gold, "_latest_cnes_lookup", lambda: None)
    result = gold.aggregate_file(source, "DENG", 2024, batch_size=50_000)
    actual = pq.ParquetFile(result).read().to_pandas()
    assert actual["cases_total"].tolist() == [count]
    metadata = json.loads(result.with_name("metadata.json").read_text(encoding="utf-8"))
    assert metadata["batches_processed"] == 4
    assert metadata["source_rows"] == count
    assert metadata["resolved_rows"] == count
    assert metadata["discarded_rows"] == 0
    assert metadata["dropped_rows"] == 0
    assert metadata["aggregation_reduction"] == count - 1


def test_aggregate_file_catalogo_nacional_classifica_resolucoes(source, monkeypatch):
    from app.pipeline.reference.ibge.catalog import InMemoryMunicipalityCatalog
    from app.pipeline.reference.ibge.models import CatalogMetadata, Municipality

    catalog = InMemoryMunicipalityCatalog(
        [
            Municipality("3301009", "330100", "Campos", "33", "RJ", "Rio de Janeiro", 2025),
            Municipality("3550308", "355030", "São Paulo", "35", "São Paulo", "São Paulo", 2025),
        ],
        CatalogMetadata(
            "ibge-test", 2025, "fixture", "fixture://dtb", "2026-01-01T00:00:00Z", "a" * 64,
        ),
    )
    raw = pd.DataFrame({
        "DT_NOTIFIC": pd.to_datetime(["2024-01-10"] * 4),
        "ID_MUNICIP": pd.Series(["330100", "3301008", "3550308", "330100"], dtype="string"),
        "SG_UF_NOT": pd.Series(["33", "33", "35", "35"], dtype="string"),
        "NM_UF": ["Rio de Janeiro", "Rio de Janeiro", "São Paulo", "São Paulo"],
        "CS_SEXO": pd.Series(["F"] * 4, dtype="string"),
        "ANO_NASC": pd.Series([1990] * 4, dtype="Int64"),
        "SEM_NOT": pd.Series([202402] * 4, dtype="Int64"),
    })
    raw.to_parquet(source, index=False, row_group_size=2)
    monkeypatch.setattr(gold, "_latest_cnes_lookup", lambda: None)

    result = gold.aggregate_file(
        source,
        "DENG",
        2024,
        municipios={"3301009": "Campos"},
        catalog=catalog,
        batch_size=2,
    )

    actual = pq.ParquetFile(result).read().to_pandas()
    metadata = json.loads(result.with_name("metadata.json").read_text(encoding="utf-8"))
    assert actual["cd_mun"].tolist() == ["3301009"]
    assert actual["cases_total"].tolist() == [1]
    assert metadata["scope_matched_rows"] == 1
    assert metadata["invalid_municipality_rows"] == 1
    assert metadata["out_of_scope_rows"] == 1
    assert metadata["uf_mismatch_rows"] == 1
    assert metadata["discarded_rows"] == 3
    assert metadata["ibge_catalog_id"] == "ibge-test"
