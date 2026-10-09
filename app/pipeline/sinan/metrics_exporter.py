import pandas as pd
from prometheus_client import CollectorRegistry, Gauge, pushadd_to_gateway

PUSHGATEWAY_URL = "pushgateway:9091"

def export_layer_metrics(layer: str, disease: str, year: int, rows: int, dropped_rows: int = 0) -> None:
    """Envia métricas de auditoria de uma camada ETL."""
    registry = CollectorRegistry()

    g_rows = Gauge('sinan_pipeline_rows', 'Quantidade total de linhas da camada', ['layer', 'disease', 'year'], registry=registry)
    g_dropped = Gauge('sinan_pipeline_dropped_rows', 'Linhas descartadas/deduplicadas na camada', ['layer', 'disease', 'year'], registry=registry)

    g_rows.labels(layer=layer, disease=disease.upper(), year=str(year)).set(rows)
    g_dropped.labels(layer=layer, disease=disease.upper(), year=str(year)).set(dropped_rows)

    pushadd_to_gateway(
        PUSHGATEWAY_URL, 
        job=f'sinan_etl_{disease.lower()}_{year}', 
        grouping_key={'layer': layer},
        registry=registry
    )

def export_gold_business_metrics(df_gold: pd.DataFrame, disease: str, year: int) -> None:
    """Envia as agregacoes epidemiologicas da camada Gold para o Pushgateway."""
    if df_gold.empty:
        return

    registry = CollectorRegistry()

    g_cases = Gauge(
        'sinan_casos_totais',
        'Total de casos notificados no SINAN por recorte epidemiológico',
        ['disease', 'year', 'municipio', 'sexo', 'faixa_etaria', 'semana_epidemica'],
        registry=registry
    )

    # Agrupa por dimensão relevante para não sobrecarregar o Prometheus com cardinalidade excessiva
    aggregated = df_gold.groupby(
        ['disease', 'year', 'nm_mun', 'sex', 'age_band', 'not_week'], 
        dropna=False
    )['cases_total'].sum().reset_index()

    for _, row in aggregated.iterrows():
        g_cases.labels(
            disease=str(row['disease']).upper(),
            year=str(row['year']),
            municipio=str(row['nm_mun']),
            sexo=str(row['sex']),
            faixa_etaria=str(row['age_band']),
            semana_epidemica=str(row['not_week'])
        ).set(float(row['cases_total']))

    pushadd_to_gateway(
        PUSHGATEWAY_URL,
        job=f'sinan_etl_{disease.lower()}_{year}',
        grouping_key={'layer': 'gold_business'},
        registry=registry
    )