from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

from ..observability.metrics import export_publication_metadata_metrics
from ..scope import scope_sha256
from .dimensions import upsert_dim_doenca, upsert_dim_municipio, upsert_dim_unidade_saude
from .classification import upsert_dim_classificacao, upsert_dim_evolucao
from .facts import FACT_KEY_COLUMNS, _metadata_snapshot, _register_catalog_release, _scope_statement, _expanding_statement, _validate_snapshot, insert_fato_casos
from .helpers import get_engine, insert_immutable, upsert

_upsert = upsert
_insert_immutable = insert_immutable

from .diseases import DISEASE_NAMES
QUALITY_METRIC_COLUMNS = ("source_rows", "resolved_rows", "discarded_rows", "aggregation_reduction", "invalid_municipality_rows", "out_of_scope_rows", "uf_mismatch_rows")

def load_gold_to_postgres(
    engine: Engine, gold_df: pd.DataFrame, disease_codigo: str, batch_id: str, *,
    year: int, municipios: Sequence[str], expected_cases_total: int,
    snapshot_complete: bool, source_extracted_at: datetime, allow_empty: bool = False,
    ibge_catalog=None, geographic_scope_type: str = "MUNICIPALITIES",
    geographic_scope_sha256: str | None = None,
    quality_metrics: Mapping[str, int] | None = None,
) -> None:
    """Publica o snapshot completo somente no recorte declarado.

    snapshot_complete atesta a conclusão da ingestão, não a completude
    epidemiológica da fonte. expected_cases_total vem da Silver do recorte.
    """
    disease_codigo = disease_codigo.upper()
    fact_df, facts, scope = _validate_snapshot(
        gold_df, disease_codigo, batch_id, year=year, municipios=municipios,
        expected_cases_total=expected_cases_total, snapshot_complete=snapshot_complete,
        source_extracted_at=source_extracted_at, allow_empty=allow_empty,
    )
    params = {"disease": disease_codigo, "year": year, "municipios": scope}
    if geographic_scope_type not in {"MUNICIPALITIES", "UFs", "BRAZIL"}:
        raise ValueError("tipo de escopo geográfico inválido")
    expected_scope_sha256 = scope_sha256(scope)
    if geographic_scope_sha256 is not None and geographic_scope_sha256 != expected_scope_sha256:
        raise ValueError("hash do escopo geográfico diverge dos municípios publicados")
    geographic_scope_sha256 = expected_scope_sha256
    quality = {column: 0 for column in QUALITY_METRIC_COLUMNS}
    if quality_metrics is not None:
        if not isinstance(quality_metrics, Mapping):
            raise ValueError("quality_metrics deve ser um mapeamento")
        unknown = set(quality_metrics) - set(QUALITY_METRIC_COLUMNS)
        if unknown:
            raise ValueError(f"métricas Gold desconhecidas: {sorted(unknown)}")
        for column, value in quality_metrics.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"métrica Gold inválida: {column}")
            quality[column] = value
    publication_added_at = datetime.now(UTC)
    with engine.begin() as conn:
        # Serializa também recortes parcialmente sobrepostos da mesma doença/ano.
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                     {"key": f"nss:sinan:{disease_codigo}:{year}"})
        newest = conn.execute(_scope_statement("""
            SELECT max(source_extracted_at) FROM analytics.pipeline_publications
            WHERE disease_codigo = :disease AND ano = :year AND cd_mun IN :municipios
        """), params).scalar_one()
        if newest is not None and source_extracted_at < newest:
            raise ValueError("Snapshot antigo: já existe publicação mais recente no recorte")
        upsert_dim_doenca(conn, disease_codigo)
        _register_catalog_release(conn, ibge_catalog)
        upsert_dim_municipio(
            conn,
            fact_df,
            catalog=ibge_catalog,
            require_unit_municipalities=True,
            scope_municipalities=scope,
        )
        upsert_dim_unidade_saude(conn, fact_df)
        upsert_dim_classificacao(conn, fact_df)
        upsert_dim_evolucao(conn, fact_df)
        # Um escopo BRAZIL é autoritativo: municípios que desapareceram da
        # fonte deixam de ser fatos ativos. Publicações antigas continuam na
        # trilha de auditoria. Escopos parciais não removem dados fora deles.
        if geographic_scope_type == "BRAZIL":
            stale_result = conn.execute(_scope_statement("""
                SELECT cd_mun
                FROM analytics.pipeline_current_publication
                WHERE disease_codigo = :disease AND ano = :year
                  AND cd_mun NOT IN :municipios
            """), params)
            stale = stale_result.scalars().all() if stale_result is not None else []
            if stale:
                stale_params = {"disease": disease_codigo, "year": year, "stale": stale}
                conn.execute(_expanding_statement("""
                    DELETE FROM analytics.fato_casos
                    WHERE disease_codigo = :disease AND ano = :year
                      AND cd_mun IN :stale
                """, "stale"), stale_params)
                conn.execute(_expanding_statement("""
                    DELETE FROM analytics.pipeline_current_publication
                    WHERE disease_codigo = :disease AND ano = :year
                      AND cd_mun IN :stale
                """, "stale"), stale_params)
        conn.execute(_scope_statement("""
            DELETE FROM analytics.fato_casos
            WHERE disease_codigo = :disease AND ano = :year AND cd_mun IN :municipios
        """), params)
        insert_fato_casos(conn, facts)
        published = conn.execute(_scope_statement("""
            SELECT count(*) AS groups_total, coalesce(sum(cases_total), 0) AS cases_total
            FROM analytics.fato_casos
            WHERE disease_codigo = :disease AND ano = :year AND cd_mun IN :municipios
        """), params).one()
        if published.groups_total != len(facts) or published.cases_total != expected_cases_total:
            raise RuntimeError("Totais publicados divergem do snapshot; transação revertida")
        totals = facts.groupby("cd_mun")["cases_total"].agg(["size", "sum"])
        rows = [{
            "disease_codigo": disease_codigo, "ano": year, "cd_mun": code,
            "batch_id": batch_id, "source_extracted_at": source_extracted_at,
            "published_at": publication_added_at,
            "groups_total": int(totals.loc[code, "size"]) if code in totals.index else 0,
            "cases_total": int(totals.loc[code, "sum"]) if code in totals.index else 0,
            "ibge_catalog_id": ibge_catalog.metadata.catalog_id if ibge_catalog else None,
            "ibge_catalog_sha256": ibge_catalog.metadata.sha256 if ibge_catalog else None,
            "geographic_scope_type": geographic_scope_type,
            "geographic_scope_sha256": geographic_scope_sha256,
            # As métricas globais vivem em pipeline_execution_metrics. As
            # colunas legadas por município permanecem zeradas para impedir
            # que uma soma municipal conte a mesma execução repetidamente.
        } for code in scope]
        _upsert(conn, "analytics.pipeline_publications", rows,
                conflict_cols=["disease_codigo", "ano", "cd_mun", "batch_id"])
        _upsert(
            conn,
            "analytics.pipeline_current_publication",
            [{
                "disease_codigo": disease_codigo,
                "ano": year,
                "cd_mun": code,
                "batch_id": batch_id,
                "source_extracted_timestamp": source_extracted_at,
                "added_at": publication_added_at,
            } for code in scope],
            conflict_cols=["disease_codigo", "ano", "cd_mun"],
        )
        _upsert(
            conn,
            "analytics.pipeline_execution_metrics",
            [{
                "disease_codigo": disease_codigo,
                "ano": year,
                "batch_id": batch_id,
                "source_extracted_at": source_extracted_at,
                "published_at": publication_added_at,
                "geographic_scope_type": geographic_scope_type,
                "geographic_scope_sha256": geographic_scope_sha256,
                "ibge_catalog_id": ibge_catalog.metadata.catalog_id if ibge_catalog else None,
                "ibge_catalog_sha256": ibge_catalog.metadata.sha256 if ibge_catalog else None,
                **quality,
            }],
            conflict_cols=["disease_codigo", "ano", "batch_id"],
        )
        metadata = _metadata_snapshot(
            fact_df,
            disease_codigo=disease_codigo,
            year=year,
            batch_id=batch_id,
            source_extracted_at=source_extracted_at,
            published_at=publication_added_at,
        )
        _upsert(
            conn,
            "analytics.pipeline_metadata_current",
            [metadata],
            conflict_cols=["disease_codigo", "ano"],
        )
        _insert_immutable(
            conn,
            "analytics.pipeline_metadata_history",
            [metadata],
            conflict_cols=["disease_codigo", "ano", "batch_id"],
        )
    export_publication_metadata_metrics(
        pipeline="sinan", disease=disease_codigo, year=year,
        source_extracted_at=source_extracted_at, added_at=publication_added_at,
    )

