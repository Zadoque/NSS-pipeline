"""Public Gold API kept stable while implementation is split by responsibility."""

from ..scope import legacy_rj_mapping
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from .gold_aggregation import GOLD_REQUIRED_COLUMNS, aggregate, resolution_metrics, sort_gold
from .gold_file import (
    BASE_DIR,
    DEFAULT_BATCH_SIZE,
    aggregate_file as _aggregate_file_impl,
    gold_root,
    _cnes_lookup_for_batch as _batch_lookup_impl,
    _latest_cnes_lookup as _latest_lookup_impl,
)
from .gold_io import (
    gold_input_schema as _gold_input_schema,
    load_cnes_batch as _load_cnes_batch,
    merge_counts as _merge_counts,
    read_cnes_metadata as _read_cnes_metadata,
    read_source_metadata as _read_source_metadata,
    validate_cnes_metadata as _validate_cnes_metadata,
    validate_source_matches as _validate_source_matches,
)
from .gold_rules import (
    age_band,
    cnes_municipality_map as _cnes_municipality_map,
    decode_sinan_age_years,
    normalize_municipality_codes,
    normalize_notification_week,
    normalize_unit_codes as _normalize_unit_codes,
    resolve_catalog_municipality_codes,
)

MUNICIPIOS_RJ = legacy_rj_mapping()
_sort_gold = sort_gold
_resolution_metrics = resolution_metrics


def _latest_cnes_lookup():
    return _latest_lookup_impl(BASE_DIR)


def _cnes_lookup_for_batch(batch_id: str, *, catalog=None, expected_scope=None):
    return _batch_lookup_impl(batch_id, base_dir=BASE_DIR, catalog=catalog, expected_scope=expected_scope)


def aggregate_file(*args, **kwargs):
    kwargs.setdefault("_base_dir", BASE_DIR)
    kwargs.setdefault("_aggregate", aggregate)
    kwargs.setdefault("_latest_lookup", _latest_cnes_lookup)
    kwargs.setdefault("_batch_lookup", _cnes_lookup_for_batch)
    kwargs.setdefault("_now", lambda tz: datetime.now(tz))
    return _aggregate_file_impl(*args, **kwargs)
