from __future__ import annotations

from collections.abc import Collection, Sequence

from .models import HistoricalReferenceValidationReport
from .history_events import MunicipalityEvent


def validate_event_references(
    events: Sequence[MunicipalityEvent],
    *,
    source_codes: Collection[str],
    target_codes: Collection[str],
) -> HistoricalReferenceValidationReport:
    source_set = {str(code) for code in source_codes}
    target_set = {str(code) for code in target_codes}
    errors: list[str] = []
    for event in events:
        if event.source_code7 and event.source_code7 not in source_set:
            errors.append(
                f"{event.event_id}: source_code7 ausente na edição de origem: "
                f"{event.source_code7}"
            )
        if event.target_code7 and event.target_code7 not in target_set:
            errors.append(
                f"{event.event_id}: target_code7 ausente na edição de destino: "
                f"{event.target_code7}"
            )
    return HistoricalReferenceValidationReport(
        valid=not errors, event_count=len(events), errors=tuple(errors)
    )


def require_event_references(
    events: Sequence[MunicipalityEvent],
    *,
    source_codes: Collection[str],
    target_codes: Collection[str],
) -> None:
    report = validate_event_references(
        events, source_codes=source_codes, target_codes=target_codes
    )
    if not report.valid:
        raise ValueError("referências históricas inválidas: " + "; ".join(report.errors))
