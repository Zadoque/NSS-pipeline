from __future__ import annotations

from app.pipeline.observability import metrics


def test_export_stage_metrics_desabilitado_por_padrao(monkeypatch):
    monkeypatch.delenv("PROMETHEUS_PUSHGATEWAY_URL", raising=False)
    assert metrics.export_stage_metrics(
        pipeline="sinan", layer="bronze", disease="DENG", year=2026,
        rows=10, duration_seconds=1.5,
    ) is False


def test_export_stage_metrics_eh_best_effort(monkeypatch):
    monkeypatch.setenv("PROMETHEUS_PUSHGATEWAY_URL", "http://pushgateway:9091")
    calls = []
    monkeypatch.setattr(metrics, "pushadd_to_gateway", lambda *args, **kwargs: calls.append((args, kwargs)))

    assert metrics.export_stage_metrics(
        pipeline="sinan", layer="gold", disease="deng", year=2026,
        rows=10, dropped_rows=2, duration_seconds=1.5, extra={"scope": "BRAZIL"},
    ) is True
    assert calls[0][0][0] == "http://pushgateway:9091"
    registry = calls[0][1]["registry"]
    samples = {sample.name: sample.value for metric in registry.collect() for sample in metric.samples}
    assert samples["nss_pipeline_rows"] == 10
    assert samples["nss_pipeline_dropped_rows"] == 2
    assert samples["nss_pipeline_stage_status"] == 1


def test_export_stage_metrics_nao_bloqueia_quando_pushgateway_falha(monkeypatch):
    monkeypatch.setenv("PROMETHEUS_PUSHGATEWAY_URL", "http://pushgateway:9091")
    monkeypatch.setattr(metrics, "pushadd_to_gateway", lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("offline")))

    assert metrics.export_stage_metrics(
        pipeline="cnes", layer="silver", disease="DENG", year=2026,
        rows=1, duration_seconds=0.1,
    ) is False
