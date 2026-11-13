from __future__ import annotations

import logging
import os
from datetime import datetime
from collections.abc import Mapping
from time import time

from prometheus_client import CollectorRegistry, Gauge, pushadd_to_gateway

logger = logging.getLogger(__name__)

_STATUS_VALUES = {"success": 1, "failure": 0}


def _pushgateway_url() -> str | None:
    value = os.environ.get("PROMETHEUS_PUSHGATEWAY_URL", "").strip()
    return value or None


def export_stage_metrics(
    *,
    pipeline: str,
    layer: str,
    disease: str,
    year: int,
    rows: int,
    duration_seconds: float,
    status: str = "success",
    dropped_rows: int = 0,
    anomalous_dropped_rows: int = 0,
    extra: Mapping[str, str] | None = None,
) -> bool:
    """Publica o último estado de uma etapa sem bloquear a pipeline.

    O Pushgateway é uma dependência opcional de observabilidade. Ausência ou
    indisponibilidade dele nunca deve invalidar uma camada já gravada. Os
    labels são deliberadamente limitados a dimensões operacionais estáveis;
    município, semana e unidade não podem ser adicionados aqui.
    """
    if status not in _STATUS_VALUES:
        raise ValueError(f"status de métrica inválido: {status}")
    if rows < 0 or dropped_rows < 0 or anomalous_dropped_rows < 0 or duration_seconds < 0:
        raise ValueError("valores de métrica não podem ser negativos")
    url = _pushgateway_url()
    if url is None:
        return False

    registry = CollectorRegistry()
    labels = {"pipeline": pipeline, "layer": layer, "disease": disease.upper(), "year": str(year)}
    if extra:
        labels.update({str(key): str(value) for key, value in extra.items()})
    label_names = list(labels)
    rows_gauge = Gauge(
        "nss_pipeline_rows",
        "Quantidade de linhas observada na última execução da etapa",
        label_names,
        registry=registry,
    )
    dropped_gauge = Gauge(
        "nss_pipeline_dropped_rows",
        "Quantidade de linhas descartadas na última execução da etapa",
        label_names,
        registry=registry,
    )
    anomalous_dropped_gauge = Gauge(
        "nss_pipeline_anomalous_dropped_rows",
        "Linhas descartadas por anomalias de qualidade na última execução da etapa",
        label_names,
        registry=registry,
    )
    duration_gauge = Gauge(
        "nss_pipeline_stage_duration_seconds",
        "Duração da última execução da etapa em segundos",
        label_names,
        registry=registry,
    )
    status_gauge = Gauge(
        "nss_pipeline_stage_status",
        "Último estado da etapa (1=sucesso, 0=falha)",
        label_names,
        registry=registry,
    )
    execution_gauge = Gauge(
        "nss_pipeline_stage_last_execution_timestamp_seconds",
        "Instante Unix da última execução observada da etapa",
        label_names,
        registry=registry,
    )
    values = [labels[name] for name in label_names]
    rows_gauge.labels(*values).set(rows)
    dropped_gauge.labels(*values).set(dropped_rows)
    anomalous_dropped_gauge.labels(*values).set(anomalous_dropped_rows)
    duration_gauge.labels(*values).set(duration_seconds)
    status_gauge.labels(*values).set(_STATUS_VALUES[status])
    execution_gauge.labels(*values).set(time())

    try:
        pushadd_to_gateway(
            url,
            job="nss_pipeline",
            grouping_key={
                "pipeline": pipeline,
                "layer": layer,
                "disease": disease.lower(),
                "year": str(year),
            },
            registry=registry,
        )
    except Exception:  # observabilidade é best effort por contrato
        logger.warning("Falha ao exportar métricas para Pushgateway %s", url, exc_info=True)
        return False
    return True


def export_publication_metadata_metrics(
    *, pipeline: str, disease: str, year: int,
    source_extracted_at: datetime, added_at: datetime,
) -> bool:
    """Publica os dois instantes de linhagem da publicação atual."""
    url = _pushgateway_url()
    if url is None:
        return False
    registry = CollectorRegistry()
    labels = {"pipeline": pipeline, "disease": disease.upper(), "year": str(year)}
    source_gauge = Gauge(
        "nss_pipeline_source_extracted_timestamp_seconds",
        "Instante UTC em que a fonte da publicação foi extraída",
        list(labels), registry=registry,
    )
    added_gauge = Gauge(
        "nss_pipeline_added_timestamp_seconds",
        "Instante UTC em que a publicação foi adicionada ao PostgreSQL",
        list(labels), registry=registry,
    )
    values = [labels[name] for name in labels]
    source_gauge.labels(*values).set(source_extracted_at.timestamp())
    added_gauge.labels(*values).set(added_at.timestamp())
    try:
        pushadd_to_gateway(
            url, job="nss_pipeline", grouping_key={
                "pipeline": pipeline, "disease": disease.lower(), "year": str(year),
            }, registry=registry,
        )
    except Exception:
        logger.warning("Falha ao exportar metadados de publicação para %s", url, exc_info=True)
        return False
    return True
