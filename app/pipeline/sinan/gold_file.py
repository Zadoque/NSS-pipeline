from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pyarrow as pa
import pyarrow.parquet as pq

from ..atomic_io import write_json_atomic, write_parquet_atomic
from ..reference.ibge.models import MunicipalityCatalog
from ..scope import legacy_rj_mapping, scope_sha256
from .columns import CATALOG, validate_keys
from .gold_aggregation import aggregate, resolution_metrics, sort_gold
from .gold_io import (
    gold_input_schema,
    load_cnes_batch,
    merge_counts,
    read_source_metadata,
    validate_source_matches,
)

BASE_DIR = Path(os.environ.get("PIPELINE_DATA_DIR", "/data"))
DEFAULT_BATCH_SIZE = 50_000
GoldTarget = Literal["ad_hoc", "serving"]


def gold_root(target: GoldTarget) -> Path:
    if target not in {"ad_hoc", "serving"}:
        raise ValueError(f"Destino Gold inválido: {target!r}")
    return BASE_DIR / "gold" / target


def _latest_cnes_lookup(base_dir: Path = BASE_DIR):
    batches = sorted((base_dir / "silver" / "cnes").glob("batch_id=*/data.parquet"))
    return load_cnes_batch(batches[-1]) if batches else None


def _cnes_lookup_for_batch(batch_id: str, *, base_dir: Path = BASE_DIR, catalog=None, expected_scope=None):
    import re
    if not re.fullmatch(r"\d{8}T\d{6}Z", batch_id):
        raise ValueError("cnes_batch_id inválido")
    path = base_dir / "silver" / "cnes" / f"batch_id={batch_id}" / "data.parquet"
    if not path.exists():
        raise FileNotFoundError(f"lote CNES não encontrado: {batch_id}")
    return load_cnes_batch(path, catalog=catalog, expected_scope=expected_scope)


def aggregate_file(
    source: Path,
    disease: str,
    year: int,
    selected_columns: list[str] | None = None,
    municipios: Mapping[str, str] | MunicipalityCatalog | None = None,
    run_at: datetime | None = None,
    target: GoldTarget = "ad_hoc",
    *,
    catalog: MunicipalityCatalog | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    cnes_batch_id: str | None = None,
    geographic_scope_type: str = "MUNICIPALITIES",
    allow_uf_mismatch: bool = False,
    _base_dir: Path | None = None,
    _now: datetime | None = None,
    _aggregate=aggregate,
    _latest_lookup=None,
    _batch_lookup=None,
) -> Path:
    if batch_size <= 0:
        raise ValueError("batch_size deve ser maior que zero")
    selected_columns = validate_keys(selected_columns)
    disease = disease.upper()
    if geographic_scope_type not in {"MUNICIPALITIES", "UFs", "BRAZIL"}:
        raise ValueError("tipo de escopo geográfico inválido")
    if target == "serving" and cnes_batch_id is None:
        raise ValueError("Gold serving exige --cnes-batch-id explícito para garantir reprodutibilidade da publicação")
    if municipios is None:
        municipios = catalog.as_mapping() if catalog is not None else legacy_rj_mapping()
    scope_codes = sorted(municipios if isinstance(municipios, Mapping) else [item.code7 for item in municipios.municipalities()])
    base_dir = _base_dir or BASE_DIR
    now = run_at or (_now(UTC) if _now is not None else datetime.now(UTC))
    batch_id = now.strftime("%Y%m%dT%H%M%SZ")
    directory = base_dir / "gold" / target / "sinan" / f"disease={disease.lower()}" / f"source_year={year}" / f"ingestion_date={now.date()}" / f"batch_id={batch_id}"
    parquet = directory / "data.parquet"
    source_metadata = read_source_metadata(source)
    validate_source_matches(source_metadata, disease, year, source)
    latest_lookup = _latest_lookup or (lambda: _latest_cnes_lookup(base_dir))
    batch_lookup = _batch_lookup or (lambda batch_id, **kwargs: _cnes_lookup_for_batch(batch_id, base_dir=base_dir, **kwargs))
    cnes_lookup = batch_lookup(cnes_batch_id, catalog=catalog, expected_scope=set(scope_codes)) if cnes_batch_id else latest_lookup()
    with pq.ParquetFile(source) as original:
        schema = gold_input_schema(original.schema_arrow, selected_columns)
        result = _aggregate(pa.Table.from_batches([], schema=schema).to_pandas(), disease, selected_columns, municipios, cnes_lookup=cnes_lookup, catalog=catalog, allow_uf_mismatch=allow_uf_mismatch)
        source_rows = original.metadata.num_rows
        metrics = {"scope_matched_rows": 0, "invalid_municipality_rows": 0, "out_of_scope_rows": 0, "uf_mismatch_rows": 0, "cnes_mismatch_rows": 0}
        batches = 0
        for batch in original.iter_batches(batch_size=batch_size, columns=schema.names):
            frame = batch.to_pandas()
            current = resolution_metrics(frame["ID_MUNICIP"], municipios, catalog, frame.get("SG_UF_NOT"), frame.get("ID_UNIDADE"), cnes_lookup, allow_uf_mismatch)
            for key, value in current.items():
                metrics[key] += value
            partial = _aggregate(frame, disease, selected_columns, municipios, cnes_lookup=cnes_lookup, catalog=catalog, allow_uf_mismatch=allow_uf_mismatch)
            result = partial if result.empty else (merge_counts(result, partial) if not partial.empty else result)
            batches += 1
            if batches % 10 == 0:
                print(f"Gold: lotes={batches}, grupos={len(result)}", flush=True)
    extra = [CATALOG[key].source_column for key in selected_columns if CATALOG[key].groupable and CATALOG[key].source_column in schema.names]
    result = sort_gold(result, extra)
    resolved_rows = metrics["scope_matched_rows"]
    write_parquet_atomic(result, parquet)
    discarded_rows = source_rows - resolved_rows
    metadata = {"disease": disease, "source_year": year, "batch_id": batch_id, "ingested_at": now.isoformat(), "rows": len(result), "columns": list(result.columns), "source_rows": source_rows, "resolved_rows": resolved_rows, "discarded_rows": discarded_rows, "dropped_rows": discarded_rows, "aggregation_reduction": resolved_rows - len(result), "gold_target": target, "batch_size": batch_size, "batches_processed": batches, "cnes_batch_id": cnes_batch_id, **metrics, "ibge_catalog_id": catalog.metadata.catalog_id if catalog else None, "ibge_catalog_sha256": catalog.metadata.sha256 if catalog else None, "geographic_scope": {"type": geographic_scope_type, "municipality_count": len(scope_codes), "scope_sha256": scope_sha256(scope_codes)}}
    write_json_atomic(metadata, directory / "metadata.json")
    return parquet
