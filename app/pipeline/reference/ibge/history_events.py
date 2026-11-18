from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from collections.abc import Mapping, Sequence
import hashlib
import re

import pandas as pd

from .history_source import ADMINISTRATIVE_EVENT_TYPES, CODE7_PATTERN, SHA256_PATTERN, _event_id
from .models import Municipality
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
        if not CODE7_PATTERN.fullmatch(uf + mun):
            raise ValueError(f"geocódigo inválido nas alterações toponímicas, linha {index + 2}")
        if not old_name or not new_name or pd.isna(effective):
            raise ValueError(f"evento toponímico incompleto, linha {index + 2}")
        code7 = uf + mun
        event_id = _event_id(
            reference_year, "TOPONYMIC_CHANGE", effective.date(), code7,
        )
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
def _workbook_code7(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text if CODE7_PATTERN.fullmatch(text) else None


def parse_historical_municipality_workbook(
    source_path: Path,
    *,
    source_url: str | None = None,
) -> list[MunicipalityEvent]:
    """Extrai apenas alterações toponímicas explicitamente observáveis.

    A planilha histórica do IBGE contém, para vários anos censitários, o
    código e o nome do município. Quando o mesmo código aparece em dois anos
    consecutivos com nomes diferentes, a mudança pode ser promovida sem
    resolver genealogia por nome. Textos como ``desmembrado de`` não são
    convertidos em sucessões, pois não trazem um código de origem inequívoco.
    """
    suffix = source_path.suffix.lower()
    if suffix not in {".xls", ".xlsx", ".ods"}:
        raise ValueError(f"formato de planilha histórica não suportado: {suffix}")
    frame = pd.read_excel(source_path, dtype=str)
    code_columns: dict[int, str] = {}
    name_columns: dict[int, str] = {}
    for column in frame.columns:
        text = str(column).strip()
        code_match = re.fullmatch(r"cod\.(\d{4})", text, flags=re.IGNORECASE)
        name_match = re.fullmatch(r"Município\s+(\d{4})", text, flags=re.IGNORECASE)
        if code_match:
            code_columns[int(code_match.group(1))] = column
        if name_match:
            name_columns[int(name_match.group(1))] = column
    years = sorted(set(code_columns) & set(name_columns))
    if len(years) < 2:
        raise ValueError("planilha histórica sem pares de código e nome por ano")

    events: list[MunicipalityEvent] = []
    for previous_year, current_year in zip(years, years[1:]):
        for index, row in frame.iterrows():
            previous_code = _workbook_code7(row[code_columns[previous_year]])
            current_code = _workbook_code7(row[code_columns[current_year]])
            if previous_code is None or previous_code != current_code:
                continue
            previous_name = str(row[name_columns[previous_year]]).strip()
            current_name = str(row[name_columns[current_year]]).strip()
            if not previous_name or previous_name.lower() == "nan":
                continue
            if not current_name or current_name.lower() == "nan" or previous_name == current_name:
                continue
            events.append(MunicipalityEvent(
                event_id=_event_id(
                    current_year, "TOPONYMIC_CHANGE", f"{current_year}-01-01",
                    previous_code,
                ),
                event_type="TOPONYMIC_CHANGE",
                effective_date=f"{current_year}-01-01",
                source_code7=previous_code,
                target_code7=current_code,
                source_name=previous_name,
                target_name=current_name,
                source=source_url or "IBGE_EVOLUCAO_MUNICIPAL_1872_2010",
            ))
    if not events:
        raise ValueError("nenhuma alteração toponímica observável na planilha histórica")
    return events
def promote_historical_municipality_workbook(
    root: Path,
    source_path: Path,
    *,
    source_url: str | None = None,
) -> Path:
    """Promove mudanças de nome observáveis da planilha histórica do IBGE."""
    events = parse_historical_municipality_workbook(
        source_path, source_url=source_url,
    )
    from .history_promotion import _promote_events

    return _promote_events(
        root, events, source_path=source_path, reference_year=2010,
        source_url=source_url,
    )


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
