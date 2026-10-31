"""Instrumentação opcional da pipeline para Prometheus/Grafana."""

from .metrics import export_stage_metrics

__all__ = ["export_stage_metrics"]
