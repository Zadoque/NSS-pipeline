from __future__ import annotations

import pytest

from app.pipeline.observability import metrics


def test_export_stage_metrics_desabilitado_por_padrao(monkeypatch):
    monkeypatch.delenv("PROMETHEUS_PUSHGATEWAY_URL", raising=False)
    assert metrics.export_stage_metrics(
        pipeline="sinan", layer="bronze", disease="DENG", year=2026,
        rows=10, duration_seconds=1.5,
    ) is False


def test_export_stage_metrics_sem_url_nao_tenta_push(monkeypatch):
    monkeypatch.delenv("PROMETHEUS_PUSHGATEWAY_URL", raising=False)
    calls = []
    monkeypatch.setattr(metrics, "pushadd_to_gateway", lambda *args, **kwargs: calls.append(args))

    assert metrics.export_stage_metrics(
        pipeline="sinan", layer="bronze", disease="DENG", year=2026,
        rows=0, duration_seconds=0,
    ) is False
    assert calls == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "unknown"},
        {"rows": -1},
        {"dropped_rows": -1},
        {"duration_seconds": -1},
    ],
)
def test_export_stage_metrics_rejeita_valores_invalidos(monkeypatch, overrides):
    monkeypatch.setenv("PROMETHEUS_PUSHGATEWAY_URL", "http://pushgateway:9091")
    arguments = {
        "pipeline": "sinan", "layer": "bronze", "disease": "DENG", "year": 2026,
        "rows": 0, "duration_seconds": 0, **overrides,
    }

    with pytest.raises(ValueError):
        metrics.export_stage_metrics(**arguments)


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
    assert samples["nss_pipeline_stage_last_execution_timestamp_seconds"] > 0


def test_export_stage_metrics_preserva_defaults_labels_e_chave_do_push(monkeypatch):
    monkeypatch.setenv("PROMETHEUS_PUSHGATEWAY_URL", "http://pushgateway:9091")
    calls = []
    monkeypatch.setattr(metrics, "pushadd_to_gateway", lambda *args, **kwargs: calls.append((args, kwargs)))

    assert metrics.export_stage_metrics(
        pipeline="sinan", layer="bronze", disease="deng", year=2026,
        rows=0, duration_seconds=0, status="failure", extra={"scope": "BRAZIL"},
    ) is True

    args, kwargs = calls[0]
    assert args[0] == "http://pushgateway:9091"
    assert kwargs["job"] == "nss_pipeline"
    assert kwargs["grouping_key"] == {"pipeline": "sinan", "disease": "deng", "year": "2026"}
    registry = kwargs["registry"]
    samples = {
        sample.name: (sample.value, sample.labels)
        for metric in registry.collect()
        for sample in metric.samples
    }
    assert samples["nss_pipeline_dropped_rows"][0] == 0
    assert samples["nss_pipeline_stage_status"][0] == 0
    assert samples["nss_pipeline_rows"][1] == {
        "pipeline": "sinan", "layer": "bronze", "disease": "DENG",
        "year": "2026", "scope": "BRAZIL",
    }


def test_export_stage_metrics_nao_bloqueia_quando_pushgateway_falha(monkeypatch):
    monkeypatch.setenv("PROMETHEUS_PUSHGATEWAY_URL", "http://pushgateway:9091")
    monkeypatch.setattr(metrics, "pushadd_to_gateway", lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("offline")))

    assert metrics.export_stage_metrics(
        pipeline="cnes", layer="silver", disease="DENG", year=2026,
        rows=1, duration_seconds=0.1,
    ) is False
