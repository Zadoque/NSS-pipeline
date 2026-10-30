from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import hashlib
import json

import pandas as pd

from ...atomic_io import write_json_atomic

ADMINISTRATIVE_EVENT_TYPES = frozenset({
    "CREATION", "EXTINCTION", "SUCCESSION", "MERGER", "SPLIT", "RENAME",
})


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
        if not (uf.isdigit() and mun.isdigit() and len(uf + mun) == 7):
            raise ValueError(f"geocódigo inválido nas alterações toponímicas, linha {index + 2}")
        if not old_name or not new_name or pd.isna(effective):
            raise ValueError(f"evento toponímico incompleto, linha {index + 2}")
        code7 = uf + mun
        event_id = hashlib.sha256(
            f"{reference_year}|{index}|{code7}|{old_name}|{new_name}|{effective.date()}".encode("utf-8")
        ).hexdigest()[:20]
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
        for field in ("source_code7", "target_code7"):
            code = getattr(row, field)
            if code is not None and not pd.isna(code) and (not str(code).isdigit() or len(str(code)) != 7):
                raise ValueError(f"{field} inválido no histórico municipal: {code}")
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return path


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
        if event_type in {"CREATION", "SUCCESSION", "MERGER", "SPLIT"} and not target_code:
            raise ValueError(f"TARGET_CODE7 ausente, linha {index + 2}")
        if event_type in {"EXTINCTION", "SUCCESSION", "MERGER", "SPLIT"} and not source_code:
            raise ValueError(f"SOURCE_CODE7 ausente, linha {index + 2}")
        event_id = hashlib.sha256(
            f"{reference_year}|{index}|{event_type}|{effective.date()}|{source_code}|{target_code}".encode("utf-8")
        ).hexdigest()[:20]
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
) -> Path:
    """Promove eventos administrativos declarados, sem inferência territorial."""
    events = parse_administrative_events(
        source_path, reference_year=reference_year, source_url=source_url,
    )
    result = write_events(root / "historical" / "municipality_events.parquet", events)
    manifest = {
        "reference_year": reference_year,
        "source_url": source_url,
        "source_path": str(source_path),
        "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "rows": len(events),
        "event_types": sorted({event.event_type for event in events}),
    }
    write_json_atomic(manifest, result.parent / "municipality_events.manifest.json")
    return result


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
    result = write_events(root / "historical" / "municipality_events.parquet", events)
    manifest = {
        "reference_year": reference_year,
        "source_url": source_url,
        "source_path": str(source_path),
        "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "rows": len(events),
        "event_types": sorted({event.event_type for event in events}),
    }
    write_json_atomic(manifest, result.parent / "municipality_events.manifest.json")
    return result
