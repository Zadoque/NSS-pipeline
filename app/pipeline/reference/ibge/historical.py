from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
import hashlib
import json
import re

import pandas as pd

from ...atomic_io import write_json_atomic
from .models import HistoricalReferenceValidationReport, Municipality

ADMINISTRATIVE_EVENT_TYPES = frozenset({
    "CREATION", "EXTINCTION", "SUCCESSION", "MERGER", "SPLIT", "RENAME",
})
CODE7_PATTERN = re.compile(r"^\d{7}$")


def _event_id(*parts: object) -> str:
    return hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:20]


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


def validate_event_references(
    events: Sequence[MunicipalityEvent],
    *,
    source_codes: Collection[str],
    target_codes: Collection[str],
) -> HistoricalReferenceValidationReport:
    """Verifica referências contra as edições de origem e destino declaradas.

    A função não tenta resolver nomes nem converter códigos. Ela somente prova
    que cada geocódigo explícito está presente no conjunto da edição adequada;
    assim, uma sucessão ambígua continua rejeitada em vez de ser aproximada.
    """
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
        raise ValueError(
            "referências históricas inválidas: " + "; ".join(report.errors)
        )


def parse_toponymic_events(
    source_path: Path,
    *,
    reference_year: int,
    source_url: str | None = None,
) -> list[MunicipalityEvent]:
    """Converte a planilha oficial de alterações toponímicas em eventos.

    A planilha registra mudanças de nome, não sucessão territorial. Portanto,
    o mesmo geocódigo é mantido nos campos de origem e destino e o evento é
    classificado como ``TOPONYMIC_CHANGE``.
    """
    suffix = source_path.suffix.lower()
    if suffix not in {".csv", ".xls", ".xlsx", ".ods"}:
        raise ValueError(f"formato de alterações toponímicas não suportado: {suffix}")
    frame = (
        pd.read_csv(source_path, dtype=str)
        if suffix == ".csv"
        else pd.read_excel(source_path, dtype=str)
    )
    required = {
        "UF", "MUN", "NOME_ANTERIOR", "NOME_ATUAL", "DATA_OCORRÊNCIA",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"colunas ausentes nas alterações toponímicas: {sorted(missing)}")

    events = []
    for index, row in frame.fillna("").iterrows():
        uf = str(row["UF"]).strip().zfill(2)
        mun = str(row["MUN"]).strip().zfill(5)
        old_name = str(row["NOME_ANTERIOR"]).strip()
        new_name = str(row["NOME_ATUAL"]).strip()
        effective = pd.to_datetime(row["DATA_OCORRÊNCIA"], errors="coerce")
        if not (uf.isdigit() and mun.isdigit() and len(uf + mun) == 7):
            raise ValueError(f"geocódigo inválido nas alterações toponímicas, linha {index + 2}")
        if not old_name or not new_name or pd.isna(effective):
            raise ValueError(f"evento toponímico incompleto, linha {index + 2}")
        code7 = uf + mun
        event_id = _event_id(reference_year, index, code7, old_name, new_name, effective.date())
        events.append(MunicipalityEvent(
            event_id=event_id,
            event_type="TOPONYMIC_CHANGE",
            effective_date=effective.date().isoformat(),
            source_code7=code7,
            target_code7=code7,
            source_name=old_name,
            target_name=new_name,
            source=source_url or f"IBGE_ALTERACOES_TOPONIMICAS_{reference_year}",
        ))
    if not events:
        raise ValueError("histórico toponímico vazio")
    return events


def derive_annual_events(
    previous: Sequence[Municipality],
    current: Sequence[Municipality],
    *,
    reference_year: int,
    effective_date: str,
    source_url: str | None = None,
) -> list[MunicipalityEvent]:
    """Deriva somente diferenças observáveis entre duas edições DTB.

    Ausência/presença de um código gera criação/extinção e mudança de nome
    gera alteração toponímica. A função deliberadamente não tenta associar um
    código removido a outro criado; sucessão e desmembramento exigem fonte
    histórica explícita.
    """
    previous_by_code = {item.code7: item for item in previous}
    current_by_code = {item.code7: item for item in current}
    source = source_url or f"IBGE_DTB_DIFF_{reference_year}"
    events: list[MunicipalityEvent] = []
    for code7 in sorted(set(current_by_code) - set(previous_by_code)):
        item = current_by_code[code7]
        events.append(MunicipalityEvent(
            event_id=_event_id(reference_year, effective_date, "CREATION", code7),
            event_type="CREATION", effective_date=effective_date,
            source_code7=None, target_code7=code7, target_name=item.name, source=source,
        ))
    for code7 in sorted(set(previous_by_code) - set(current_by_code)):
        item = previous_by_code[code7]
        events.append(MunicipalityEvent(
            event_id=_event_id(reference_year, effective_date, "EXTINCTION", code7),
            event_type="EXTINCTION", effective_date=effective_date,
            source_code7=code7, target_code7=None, source_name=item.name, source=source,
        ))
    for code7 in sorted(set(previous_by_code) & set(current_by_code)):
        old = previous_by_code[code7]
        new = current_by_code[code7]
        if old.name != new.name:
            events.append(MunicipalityEvent(
                event_id=_event_id(reference_year, effective_date, "TOPONYMIC_CHANGE", code7, old.name, new.name),
                event_type="TOPONYMIC_CHANGE", effective_date=effective_date,
                source_code7=code7, target_code7=code7,
                source_name=old.name, target_name=new.name, source=source,
            ))
    if not events:
        raise ValueError("nenhuma diferença territorial observável entre as edições")
    return events


def derive_annual_event_series(
    editions: Mapping[int, Sequence[Municipality]],
    *,
    source_urls: Mapping[int, str] | None = None,
) -> list[MunicipalityEvent]:
    """Compara uma série de edições DTB oficiais em anos consecutivos.

    A série só promove diferenças observáveis entre códigos presentes nas
    edições adjacentes. Um código que desaparece e outro que surge no mesmo
    intervalo gera eventos independentes de extinção e criação; nenhuma
    sucessão, fusão ou desmembramento é inferida sem uma fonte explícita.
    """
    years = sorted(editions)
    if len(years) < 2 or years != list(range(years[0], years[-1] + 1)):
        raise ValueError("série DTB exige pelo menos dois anos consecutivos")
    events: list[MunicipalityEvent] = []
    for previous_year, current_year in zip(years, years[1:]):
        try:
            events.extend(derive_annual_events(
                editions[previous_year], editions[current_year],
                reference_year=current_year,
                effective_date=f"{current_year}-01-01",
                source_url=(source_urls or {}).get(current_year),
            ))
        except ValueError as error:
            if str(error) != "nenhuma diferença territorial observável entre as edições":
                raise
    by_id: dict[str, MunicipalityEvent] = {}
    for event in events:
        previous = by_id.get(event.event_id)
        if previous is not None and previous != event:
            raise ValueError(f"event_id conflitante na série DTB: {event.event_id}")
        by_id[event.event_id] = event
    return list(by_id.values())


def write_events(path: Path, events: list[MunicipalityEvent] | tuple[MunicipalityEvent, ...]) -> Path:
    if not events:
        raise ValueError("histórico municipal vazio")
    frame = pd.DataFrame([asdict(event) for event in events])
    if frame["event_id"].duplicated().any():
        raise ValueError("event_id duplicado no histórico municipal")
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
            if code is not None and not pd.isna(code) and (not str(code).isdigit() or len(str(code)) != 7):
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


def _promote_events(
    root: Path,
    events: list[MunicipalityEvent],
    *,
    source_path: Path,
    reference_year: int,
    source_url: str | None,
) -> Path:
    result_path = root / "historical" / "municipality_events.parquet"
    existing = {event.event_id: event for event in _read_events(result_path)}
    for event in events:
        previous = existing.get(event.event_id)
        if previous is not None and previous != event:
            raise ValueError(f"event_id conflitante no histórico municipal: {event.event_id}")
        existing[event.event_id] = event
    merged = list(existing.values())
    result = write_events(result_path, merged)
    manifest = {
        "reference_year": reference_year,
        "source_url": source_url,
        "source_path": str(source_path),
        "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "rows": len(merged),
        "event_types": sorted({event.event_type for event in merged}),
    }
    write_json_atomic(manifest, result.parent / "municipality_events.manifest.json")
    return result


def parse_administrative_events(
    source_path: Path,
    *,
    reference_year: int,
    source_url: str | None = None,
) -> list[MunicipalityEvent]:
    """Lê eventos territoriais explicitamente declarados por uma fonte oficial.

    O arquivo precisa declarar ``EVENT_TYPE``, ``EFFECTIVE_DATE`` e os códigos
    ``SOURCE_CODE7``/``TARGET_CODE7`` quando aplicáveis. Nenhuma relação entre
    códigos é inferida por nome, prefixo ou proximidade geográfica.
    """
    suffix = source_path.suffix.lower()
    if suffix not in {".csv", ".xls", ".xlsx", ".ods"}:
        raise ValueError(f"formato de eventos administrativos não suportado: {suffix}")
    frame = pd.read_csv(source_path, dtype=str) if suffix == ".csv" else pd.read_excel(source_path, dtype=str)
    required = {"EVENT_TYPE", "EFFECTIVE_DATE"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"colunas ausentes nos eventos administrativos: {sorted(missing)}")
    events = []
    for index, row in frame.fillna("").iterrows():
        event_type = str(row["EVENT_TYPE"]).strip().upper()
        if event_type not in ADMINISTRATIVE_EVENT_TYPES:
            raise ValueError(f"tipo de evento administrativo inválido, linha {index + 2}")
        effective = pd.to_datetime(row["EFFECTIVE_DATE"], errors="coerce")
        if pd.isna(effective):
            raise ValueError(f"data de vigência inválida, linha {index + 2}")
        source_code = str(row.get("SOURCE_CODE7", "")).strip() or None
        target_code = str(row.get("TARGET_CODE7", "")).strip() or None
        for field, code in (("SOURCE_CODE7", source_code), ("TARGET_CODE7", target_code)):
            if code is not None and not CODE7_PATTERN.fullmatch(code):
                raise ValueError(f"{field} inválido, linha {index + 2}: esperado geocódigo de 7 dígitos")
        if event_type in {"CREATION", "SUCCESSION", "MERGER", "SPLIT"} and not target_code:
            raise ValueError(f"TARGET_CODE7 ausente, linha {index + 2}")
        if event_type in {"EXTINCTION", "SUCCESSION", "MERGER", "SPLIT"} and not source_code:
            raise ValueError(f"SOURCE_CODE7 ausente, linha {index + 2}")
        event_id = _event_id(reference_year, index, event_type, effective.date(), source_code, target_code)
        events.append(MunicipalityEvent(
            event_id=event_id,
            event_type=event_type,
            effective_date=effective.date().isoformat(),
            source_code7=source_code,
            target_code7=target_code,
            source_name=str(row.get("SOURCE_NAME", "")).strip() or None,
            target_name=str(row.get("TARGET_NAME", "")).strip() or None,
            source=source_url or f"IBGE_EVENTOS_ADMINISTRATIVOS_{reference_year}",
        ))
    if not events:
        raise ValueError("histórico administrativo vazio")
    return events


def promote_administrative_events(
    root: Path,
    source_path: Path,
    *,
    reference_year: int,
    source_url: str | None = None,
    source_codes: Collection[str] | None = None,
    target_codes: Collection[str] | None = None,
) -> Path:
    """Promove eventos administrativos declarados, sem inferência territorial."""
    events = parse_administrative_events(
        source_path, reference_year=reference_year, source_url=source_url,
    )
    if source_codes is not None or target_codes is not None:
        if source_codes is None or target_codes is None:
            raise ValueError("source_codes e target_codes devem ser fornecidos juntos")
        require_event_references(
            events, source_codes=source_codes, target_codes=target_codes
        )
    return _promote_events(
        root, events, source_path=source_path, reference_year=reference_year,
        source_url=source_url,
    )


def promote_toponymic_events(
    root: Path,
    source_path: Path,
    *,
    reference_year: int,
    source_url: str | None = None,
) -> Path:
    """Promove uma edição oficial para o histórico local do catálogo."""
    events = parse_toponymic_events(
        source_path, reference_year=reference_year, source_url=source_url,
    )
    return _promote_events(
        root, events, source_path=source_path, reference_year=reference_year,
        source_url=source_url,
    )


def promote_annual_dtb_events(
    root: Path,
    archives: Mapping[int, Path],
    *,
    source_urls: Mapping[int, str] | None = None,
) -> Path:
    """Promove eventos observáveis derivados de edições anuais oficiais da DTB."""
    from .dtb import parse_dtb_archive

    editions = {
        year: parse_dtb_archive(path, reference_year=year)
        for year, path in sorted(archives.items())
    }
    events = derive_annual_event_series(editions, source_urls=source_urls)
    result_path = root / "historical" / "municipality_events.parquet"
    existing = {event.event_id: event for event in _read_events(result_path)}
    for event in events:
        previous = existing.get(event.event_id)
        if previous is not None and previous != event:
            raise ValueError(f"event_id conflitante no histórico municipal: {event.event_id}")
        existing[event.event_id] = event
    write_events(result_path, list(existing.values()))
    manifest = {
        "reference_year_start": min(editions),
        "reference_year_end": max(editions),
        "rows": len(existing),
        "event_types": sorted({event.event_type for event in existing.values()}),
        "inference_policy": "OBSERVABLE_ANNUAL_DIFF_ONLY",
        "sources": [
            {
                "reference_year": year,
                "source_path": str(path),
                "source_url": (source_urls or {}).get(year),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for year, path in sorted(archives.items())
        ],
    }
    write_json_atomic(manifest, result_path.with_name("municipality_events.manifest.json"))
    return result_path
