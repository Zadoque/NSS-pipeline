"""Rebuild a published scope from preserved Silver; never refetch SINAN."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from .atomic_io import write_json_atomic, write_parquet_atomic
from .load import get_engine, load_gold_to_postgres
from .sinan.columns import CANONICAL_GOLD_COLUMNS
from .sinan.gold import MUNICIPIOS_RJ, _latest_cnes_lookup, aggregate_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--silver', required=True, type=Path)
    parser.add_argument('--database', required=True)
    parser.add_argument('--expected-total', required=True, type=int)
    parser.add_argument('--publish', action='store_true', help='Default is dry-run')
    args = parser.parse_args()
    metadata = json.loads(args.silver.with_name('metadata.json').read_text())
    disease, year = metadata['disease'], int(metadata['source_year'])
    extracted = datetime.fromisoformat(metadata['ingested_at'])
    if _latest_cnes_lookup() is None:
        raise ValueError('CNES obrigatório para reprocessamento territorial')
    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text('SET TRANSACTION READ ONLY'))
            if conn.execute(text('SELECT current_database()')).scalar_one() != args.database:
                raise ValueError('Banco inesperado')
            source_dates = conn.execute(text('SELECT DISTINCT source_extracted_at FROM analytics.pipeline_publications WHERE disease_codigo=:d AND ano=:y'), {'d': disease, 'y': year}).scalars().all()
            if not source_dates or max(source_dates) != extracted:
                raise ValueError('Silver não corresponde à origem da última publicação')
        path = aggregate_file(args.silver, disease, year, selected_columns=CANONICAL_GOLD_COLUMNS, target='ad_hoc')
        frame = pd.read_parquet(path)
        if int(frame.cases_total.sum()) != args.expected_total:
            raise ValueError('Total reprocessado diverge do total aprovado')
        gold_meta = json.loads(path.with_name('metadata.json').read_text())
        gold_meta.update(source_silver=str(args.silver), source_extracted_at=extracted.isoformat())
        write_json_atomic(gold_meta, path.with_name('metadata.json'))
        print(json.dumps({'disease': disease, 'rows': len(frame), 'total': int(frame.cases_total.sum()), 'coverage': frame.groupby('notification_territory_status').cases_total.sum().to_dict(), 'staging_gold': str(path)}))
        if args.publish:
            if not gold_meta.get('cnes_snapshot'):
                raise ValueError('Proveniência CNES ausente')
            load_gold_to_postgres(engine, frame, disease, gold_meta['batch_id'], year=year,
                                 municipios=list(MUNICIPIOS_RJ), expected_cases_total=args.expected_total,
                                 snapshot_complete=True, source_extracted_at=extracted)
            serving = Path(str(path).replace('/gold/ad_hoc/', '/gold/serving/', 1))
            write_parquet_atomic(frame, serving)
            gold_meta['gold_target'] = 'serving'
            write_json_atomic(gold_meta, serving.with_name('metadata.json'))
            print('Published:', serving)
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
