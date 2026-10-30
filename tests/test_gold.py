from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
# pyrefly: ignore [missing-import]
import pytest

from app.pipeline.sinan.gold import (
    _merge_counts,
    _gold_input_schema,
    _validate_source_matches,
    decode_sinan_age_years,
    aggregate,
    normalize_municipality_codes,
)

MUNICIPIOS_TESTE = {"1234567": "Cidade Teste"}


def _silver_minima(**overrides) -> pd.DataFrame:
    base = {
        "DT_NOTIFIC": pd.to_datetime(["2026-01-05", "2026-01-20", "2026-02-01"]),
        "ID_MUNICIP": ["1234567", "1234567", "9999999"],  # a última fica fora do recorte
        "SG_UF_NOT": ["33", "33", "33"],
        "NM_UF": ["Rio de Janeiro", "Rio de Janeiro", "Rio de Janeiro"],
        "CS_SEXO": ["F", "M", "F"],
        "ANO_NASC": [2000, 1990, 1985],
        "SEM_NOT": [202601, 202602, 202603],
    }
    base.update(overrides)
    return pd.DataFrame(base)


@pytest.mark.parametrize("coluna", ["NM_UF", "CS_SEXO", "ANO_NASC", "SEM_NOT"])
def test_aggregate_levanta_erro_quando_falta_coluna_obrigatoria(coluna):
    df = _silver_minima().drop(columns=[coluna])
    with pytest.raises(ValueError, match="Colunas Silver ausentes"):
        aggregate(df, disease="DENG", municipios=MUNICIPIOS_TESTE)


def test_aggregate_retorna_vazio_quando_nenhum_municipio_bate():
    df = _silver_minima(ID_MUNICIP=["9999999", "9999999", "9999999"])
    result = aggregate(df, disease="DENG", municipios=MUNICIPIOS_TESTE)
    assert result.empty
    assert "cases_total" in result.columns
    assert "disease" in result.columns


def test_aggregate_soma_casos_por_mes_e_municipio():
    df = _silver_minima()
    result = aggregate(df, disease="DENG", municipios=MUNICIPIOS_TESTE)

    # As duas primeiras linhas (município 1234567, ambas em janeiro/2026)
    # têm ANO_NASC e SEM_NOT distintos — cada uma vira uma linha própria.
    # A terceira linha, de município fora do recorte, não aparece.
    assert len(result) == 2
    assert result["cases_total"].sum() == 2
    assert (result["year"] == 2026).all()
    assert (result["month"] == 1).all()
    assert (result["cd_mun"] == "1234567").all()


@pytest.mark.parametrize(
    ("sinan_code", "ibge_code"),
    [("330100", "3301009"), ("330220", "3302205"),
     ("330240", "3302403"), ("330500", "3305000"),
     ("0330100", "3301009")],
)
def test_aggregate_mapeia_codigo_sinan_para_ibge_canonico(sinan_code, ibge_code):
    df = _silver_minima(ID_MUNICIP=[sinan_code] * 3)
    result = aggregate(
        df,
        disease="DENG",
        municipios={
            "3301009": "Campos dos Goytacazes",
            "3302205": "Itaperuna",
            "3302403": "Macaé",
            "3305000": "São João da Barra",
        },
    )
    assert not result.empty
    assert set(result["cd_mun"]) == {ibge_code}


def test_aggregate_usa_uf_canonica_do_catalogo():
    from app.pipeline.reference.ibge.catalog import InMemoryMunicipalityCatalog
    from app.pipeline.reference.ibge.models import CatalogMetadata, Municipality

    catalog = InMemoryMunicipalityCatalog(
        [Municipality("3301009", "330100", "Campos", "33", "RJ", "Rio de Janeiro", 2025)],
        CatalogMetadata("test", 2025, "fixture", "fixture://", "2026-01-01T00:00:00Z", "hash"),
    )
    result = aggregate(
        _silver_minima(ID_MUNICIP=["330100"] * 3, SG_UF_NOT=["35"] * 3, NM_UF=["São Paulo"] * 3),
        "DENG", municipios=catalog, catalog=catalog,
    )
    assert result.loc[0, "cd_uf"] == "33"
    assert result.loc[0, "nm_uf"] == "Rio de Janeiro"


def test_resolution_metrics_separa_escopo_e_codigo_invalido():
    from app.pipeline.reference.ibge.catalog import InMemoryMunicipalityCatalog
    from app.pipeline.reference.ibge.models import CatalogMetadata, Municipality
    from app.pipeline.sinan.gold import _resolution_metrics

    catalog = InMemoryMunicipalityCatalog(
        [
            Municipality("3301009", "330100", "Campos", "33", "RJ", "Rio de Janeiro", 2025),
            Municipality("3550308", "355030", "São Paulo", "35", "SP", "São Paulo", 2025),
        ],
        CatalogMetadata("test", 2025, "fixture", "fixture://", "2026-01-01T00:00:00Z", "hash"),
    )
    metrics = _resolution_metrics(pd.Series(["330100", "3550308", "9999999"]), {"3301009": "Campos"}, catalog)
    assert metrics == {
        "scope_matched_rows": 1,
        "invalid_municipality_rows": 1,
        "out_of_scope_rows": 1,
        "uf_mismatch_rows": 0,
    }


def test_aggregate_inclui_disease_como_primeira_coluna():
    df = _silver_minima()
    result = aggregate(df, disease="deng", municipios=MUNICIPIOS_TESTE)
    assert result.columns[0] == "disease"
    assert (result["disease"] == "DENG").all()  # sempre maiúsculo


def test_aggregate_com_dimensao_extra_abre_grupos_por_sexo():
    df = _silver_minima()
    result = aggregate(
        df, disease="DENG", selected_columns=["sexo"], municipios=MUNICIPIOS_TESTE
    )
    # Janeiro/2026 tem uma notificação CS_SEXO=F e outra CS_SEXO=M —
    # com a dimensão extra, isso vira duas linhas em vez de uma.
    assert len(result) == 2
    assert "CS_SEXO" in result.columns
    assert set(result["CS_SEXO"]) == {"F", "M"}


def test_aggregate_cnes_nao_duplica_colunas_territoriais_nem_cria_sufixos():
    df = _silver_minima(
        ID_UNIDADE=["0729884.0", "0729884.0", "9999999"],
    )
    cnes_lookup = pd.DataFrame(
        {
            "cd_unidade": ["0729884"],
            "nm_unidade": ["UBS DEMO"],
            "razao_social_unidade": ["UBS DEMO LTDA"],
            "tp_unidade": [2],
            "notification_district_id": ["CG_DIST_SEDE"],
            "notification_neighborhood_id": ["CG_LOC_SEDE_CENTRO"],
            "notification_territory_status": ["NOTIFICATION_NEIGHBORHOOD"],
        }
    )

    result = aggregate(
        df,
        disease="DENG",
        selected_columns=["unidade_notificacao"],
        municipios=MUNICIPIOS_TESTE,
        cnes_lookup=cnes_lookup,
    )

    assert not any(column.endswith(("_x", "_y")) for column in result.columns)
    assert result["ID_UNIDADE"].eq("0729884").any()
    assert result["notification_district_id"].eq("CG_DIST_SEDE").any()
    assert result["notification_neighborhood_id"].eq("CG_LOC_SEDE_CENTRO").any()
    assert result["nm_unidade"].eq("UBS DEMO").any()


def test_aggregate_rejeita_unidade_cnes_duplicada_antes_de_contar_casos():
    silver = _silver_minima(ID_UNIDADE=["0729884", "0729884", "9999999"])
    lookup = pd.DataFrame({
        "cd_unidade": ["0729884", "0729884.0"],
        "nm_unidade": ["Unidade A", "Unidade B"],
    })

    with pytest.raises(pd.errors.MergeError):
        aggregate(
            silver, "DENG", selected_columns=["unidade_notificacao"],
            municipios=MUNICIPIOS_TESTE, cnes_lookup=lookup,
        )


def test_decode_sinan_age_years_interpreta_unidades_e_tipo_separado():
    encoded = pd.Series(["1001", "2002", "3012", "4050", "x", None])
    result = decode_sinan_age_years(encoded)

    assert result.iloc[0] == pytest.approx(1 / (24 * 365.25))
    assert result.iloc[1] == pytest.approx(2 / 365.25)
    assert result.iloc[2] == pytest.approx(1)
    assert result.iloc[3] == pytest.approx(50)
    assert result.iloc[4:].isna().all()

    overridden = decode_sinan_age_years(
        pd.Series(["0010", "0010", "0010"]),
        pd.Series(["4", "2", "9"]),
    )
    assert overridden.iloc[0] == pytest.approx(10)
    assert overridden.iloc[1] == pytest.approx(10 / 365.25)
    assert pd.isna(overridden.iloc[2])


def test_normalize_municipality_codes_remove_zero_a_esquerda():
    result = normalize_municipality_codes(
        pd.Series(["0330100", "330100", "9999999"]),
        {"3301009": "Campos"},
    )
    assert result.tolist() == ["3301009", "3301009", "9999999"]


def test_merge_counts_soma_grupos_iguais_e_preserva_grupos_distintos():
    total = pd.DataFrame({"sex": ["F"], "cases_total": [2]})
    partial = pd.DataFrame({"sex": ["F", "M"], "cases_total": [3, 1]})

    result = _merge_counts(total, partial).sort_values("sex").reset_index(drop=True)

    pd.testing.assert_frame_equal(
        result,
        pd.DataFrame({"sex": ["F", "M"], "cases_total": [5, 1]}),
    )


def test_merge_counts_nao_cria_categorias_sem_casos():
    total = pd.DataFrame({
        "sex": pd.Categorical(["F"], categories=["F", "M"]),
        "cases_total": [2],
    })
    partial = pd.DataFrame({
        "sex": pd.Categorical(["F"], categories=["F", "M"]),
        "cases_total": [3],
    })

    result = _merge_counts(total, partial)

    assert result["sex"].tolist() == ["F"]
    assert result["cases_total"].tolist() == [5]


def test_gold_input_schema_projeta_dimensoes_obrigatorias_e_preserva_metadata():
    source_schema = pa.schema(
        [
            pa.field("DT_NOTIFIC", pa.string()),
            pa.field("ID_MUNICIP", pa.string()),
            pa.field("SG_UF_NOT", pa.string()),
            pa.field("NM_UF", pa.string()),
            pa.field("CS_SEXO", pa.string()),
            pa.field("ANO_NASC", pa.int64()),
            pa.field("SEM_NOT", pa.int64()),
            pa.field("ID_UNIDADE", pa.string()),
            pa.field("NU_IDADE_N", pa.string()),
            pa.field("TP_IDADE", pa.string()),
            pa.field("CLASSI_FIN", pa.string()),
            pa.field("IGNORADA", pa.string()),
        ],
        metadata={b"source": b"silver"},
    )

    result = _gold_input_schema(source_schema, ["classificacao_final"])

    assert result.names == [
        "DT_NOTIFIC", "ID_MUNICIP", "SG_UF_NOT", "NM_UF", "CS_SEXO",
        "ANO_NASC", "SEM_NOT", "ID_UNIDADE", "NU_IDADE_N", "TP_IDADE",
        "CLASSI_FIN",
    ]
    assert result.metadata == {b"source": b"silver"}


@pytest.mark.parametrize(
    ("metadata", "disease", "year"),
    [({"disease": "ZIKA", "source_year": 2026}, "DENG", 2026),
     ({"disease": "DENG", "source_year": 2025}, "DENG", 2026)],
)
def test_validate_source_matches_rejeita_doenca_ou_ano_inconsistente(metadata, disease, year):
    with pytest.raises(ValueError):
        _validate_source_matches(metadata, disease, year, Path("silver.parquet"))


def test_aggregate_sem_cnes_publica_status_de_unidade_nao_mapeada():
    result = aggregate(_silver_minima(), "DENG", municipios=MUNICIPIOS_TESTE)

    assert set(result["notification_territory_status"]) == {"UNMAPPED_NOTIFICATION_UNIT"}


def test_aggregate_nao_cria_grupo_para_dimensao_nao_groupable():
    df = _silver_minima(
        DT_NOTIFIC=pd.to_datetime(["2026-01-05"] * 3),
        NU_NOTIFIC=["1", "2", "3"],
        ID_MUNICIP=["1234567"] * 3,
        CS_SEXO=["F"] * 3,
        ANO_NASC=[2000] * 3,
        SEM_NOT=[202601] * 3,
    )
    result = aggregate(
        df, "DENG", selected_columns=["notificacao_id"],
        municipios=MUNICIPIOS_TESTE,
    )

    assert len(result) == 1
    assert "NU_NOTIFIC" not in result.columns
