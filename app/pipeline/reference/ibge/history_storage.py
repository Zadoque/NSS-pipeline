from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import pandas as pd

from ...atomic_io import write_json_atomic
from .history_events import MunicipalityEvent
from .history_source import ADMINISTRATIVE_EVENT_TYPES, CODE7_PATTERN

def write_events(path: Path, events: list[MunicipalityEvent] | tuple[MunicipalityEvent, ...]) -> Path:
    if not events:
        raise ValueError("histórico municipal vazio")
    ordered_events = sorted(
        events,
        key=lambda event: (event.effective_date, event.event_id),
    )
    frame = pd.DataFrame([asdict(event) for event in ordered_events])
    if frame["event_id"].duplicated().any():
        raise ValueError("event_id duplicado no histórico municipal")
    for row in frame.itertuples(index=False):
        if not isinstance(row.event_id, str) or not row.event_id.strip():
            raise ValueError("event_id obrigatório no histórico municipal")
        if not isinstance(row.source, str) or not row.source.strip():
            raise ValueError(
                f"fonte obrigatória no histórico municipal: {row.event_id}"
            )
    unknown_types = sorted(set(frame["event_type"]) - ADMINISTRATIVE_EVENT_TYPES - {"TOPONYMIC_CHANGE"})
    if unknown_types:
        raise ValueError(f"tipo de evento municipal desconhecido: {unknown_types}")
    dates = pd.to_datetime(frame["effective_date"], errors="coerce")
    if dates.isna().any():
        raise ValueError("data de vigência inválida no histórico municipal")
    for row in frame.itertuples(index=False):
        event_type = str(row.event_type)
        source_code = None if pd.isna(row.source_code7) or str(row.source_code7) == "" else str(row.source_code7)
        target_code = None if pd.isna(row.target_code7) or str(row.target_code7) == "" else str(row.target_code7)
        for field in ("source_code7", "target_code7"):
            code = getattr(row, field)
            if code is not None and not pd.isna(code) and not CODE7_PATTERN.fullmatch(str(code)):
                raise ValueError(f"{field} inválido no histórico municipal: {code}")
        if event_type == "CREATION" and (source_code is not None or target_code is None):
            raise ValueError("evento CREATION exige somente target_code7")
        if event_type == "EXTINCTION" and (source_code is None or target_code is not None):
            raise ValueError("evento EXTINCTION exige somente source_code7")
        if event_type in {"SUCCESSION", "MERGER", "SPLIT"} and (
            source_code is None or target_code is None
        ):
            raise ValueError(f"evento {event_type} exige source_code7 e target_code7")
        if event_type in {"RENAME", "TOPONYMIC_CHANGE"} and (
            source_code is None or target_code is None or source_code != target_code
        ):
            raise ValueError(f"evento {event_type} exige o mesmo código na origem e no destino")
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return path


def _read_events(path: Path) -> list[MunicipalityEvent]:
    if not path.exists():
        return []
    frame = pd.read_parquet(path).fillna("")
    return [
        MunicipalityEvent(
            event_id=str(row["event_id"]),
            event_type=str(row["event_type"]),
            effective_date=str(row["effective_date"]),
            source_code7=str(row["source_code7"]) or None,
            target_code7=str(row["target_code7"]) or None,
            source_name=str(row["source_name"]) or None,
            target_name=str(row["target_name"]) or None,
            source=str(row["source"]),
        )
        for _, row in frame.iterrows()
    ]



