from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class MunicipalityEvent:
    event_id: str
    event_type: str
    effective_date: str
    source_code7: str | None
    target_code7: str | None
    source_name: str | None = None
    target_name: str | None = None
    source: str = "IBGE"


def write_events(path: Path, events: list[MunicipalityEvent] | tuple[MunicipalityEvent, ...]) -> Path:
    if not events:
        raise ValueError("histórico municipal vazio")
    frame = pd.DataFrame([asdict(event) for event in events])
    if frame["event_id"].duplicated().any():
        raise ValueError("event_id duplicado no histórico municipal")
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return path
