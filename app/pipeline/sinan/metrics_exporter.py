from prometheus_client import CollectorRegistry, Gauge, pushadd_to_gateway

PUSHGATEWAY_URL = "pushgateway:9091"

def export_layer_metrics(layer: str, disease: str, year: int, rows: int, dropped_rows: int = 0) -> None:
    """Envia métricas de auditoria de uma camada ETL isolando cada camada por grouping_key."""
    registry = CollectorRegistry()

    # Define os medidores para a auditoria
    g_rows = Gauge(
        'sinan_pipeline_rows', 
        'Quantidade total de linhas da camada',
        ['layer', 'disease', 'year'], 
        registry=registry
    )
    g_dropped = Gauge(
        'sinan_pipeline_dropped_rows', 
        'Linhas descartadas/deduplicadas na camada',
        ['layer', 'disease', 'year'], 
        registry=registry
    )

    # Preenche os rótulos e os valores
    g_rows.labels(layer=layer, disease=disease.upper(), year=str(year)).set(rows)
    g_dropped.labels(layer=layer, disease=disease.upper(), year=str(year)).set(dropped_rows)

    # O grouping_key={'layer': layer} garante que cada camada tenha seu próprio subgrupo no Pushgateway
    pushadd_to_gateway(
        PUSHGATEWAY_URL, 
        job=f'sinan_etl_{disease.lower()}_{year}', 
        grouping_key={'layer': layer},
        registry=registry
    )