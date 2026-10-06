from app.pipeline import metrics


def test_publish_layer_metrics_is_disabled_without_gateway(monkeypatch) -> None:
    monkeypatch.delenv("PROMETHEUS_PUSHGATEWAY_URL", raising=False)
    monkeypatch.setattr(metrics, "push_to_gateway", lambda **_: (_ for _ in ()).throw(AssertionError()))

    metrics.publish_layer_metrics(layer="gold", disease="deng", year=2026, rows=8)


def test_publish_layer_metrics_uses_stable_job_and_labels(monkeypatch) -> None:
    captured = {}
    monkeypatch.setenv("PROMETHEUS_PUSHGATEWAY_URL", "http://pushgateway:9091")
    monkeypatch.setattr(
        metrics,
        "push_to_gateway",
        lambda gateway, **kwargs: captured.update(gateway=gateway, **kwargs),
    )

    metrics.publish_layer_metrics(layer="silver", disease="deng", year=2026, rows=7, dropped_rows=2)

    assert captured["gateway"] == "http://pushgateway:9091"
    assert captured["job"] == "nss_pipeline"
    assert captured["grouping_key"] == {"layer": "silver", "disease": "DENG", "year": "2026"}
