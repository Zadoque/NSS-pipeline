"""Best-effort Prometheus metrics for pipeline executions."""

from __future__ import annotations

import logging
import os
from time import time

from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

logger = logging.getLogger(__name__)


def publish_layer_metrics(
    *, layer: str, disease: str, year: int, rows: int, dropped_rows: int = 0
) -> None:
    """Publish cardinality after a successful layer write, if monitoring is enabled."""
    gateway = os.getenv("PROMETHEUS_PUSHGATEWAY_URL", "").strip()
    if not gateway:
        return

    registry = CollectorRegistry()
    labels = {"layer": layer, "disease": disease.upper(), "year": str(year)}
    Gauge("nss_pipeline_layer_rows", "Rows written by an NSS pipeline layer.", labels.keys(), registry=registry).labels(**labels).set(rows)
    Gauge("nss_pipeline_layer_dropped_rows", "Rows dropped or aggregated by an NSS pipeline layer.", labels.keys(), registry=registry).labels(**labels).set(dropped_rows)
    Gauge("nss_pipeline_layer_last_success_unixtime", "Latest successful NSS pipeline layer publication.", labels.keys(), registry=registry).labels(**labels).set(time())

    try:
        push_to_gateway(gateway, job="nss_pipeline", grouping_key=labels, registry=registry, timeout=5)
    except OSError:
        logger.warning("Could not publish pipeline metrics to %s", gateway, exc_info=True)
