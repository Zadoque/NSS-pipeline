"""Stable facade for historical IBGE references."""

import pandas as pd
import requests

from .history_events import (
    MunicipalityEvent,
    derive_annual_events,
    derive_annual_event_series,
    parse_historical_municipality_workbook,
    parse_toponymic_events,
    promote_historical_municipality_workbook,
)
from .history_validation import require_event_references, validate_event_references
from .history_promotion import (
    parse_administrative_events,
    promote_administrative_events,
    promote_toponymic_events,
)
from .history_dtb import promote_annual_dtb_events
from .history_source import download_historical_source, _event_id
from .history_source import promote_historical_source
from .history_storage import _read_events, write_events

__all__ = [
    "MunicipalityEvent", "derive_annual_events", "derive_annual_event_series",
    "download_historical_source", "parse_administrative_events",
    "parse_historical_municipality_workbook", "parse_toponymic_events",
    "promote_administrative_events", "promote_annual_dtb_events",
    "promote_historical_municipality_workbook", "promote_historical_source",
    "promote_toponymic_events", "require_event_references",
    "validate_event_references", "write_events", "_event_id", "_read_events",
]
