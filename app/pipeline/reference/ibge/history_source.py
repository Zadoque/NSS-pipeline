from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from pathlib import Path
import hashlib
import json
import os
import re
import tempfile

import pandas as pd
import requests

from ...atomic_io import write_json_atomic
from .models import HistoricalReferenceValidationReport, Municipality

ADMINISTRATIVE_EVENT_TYPES = frozenset({"CREATION", "EXTINCTION", "SUCCESSION", "MERGER", "SPLIT", "RENAME"})
CODE7_PATTERN = re.compile(r"^[0-9]{7}$")
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")

def _event_id(*parts: object) -> str:
    return hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:20]


def _validate_manifest_sources(raw_sources: object) -> list[dict[str, object]]:
    if not isinstance(raw_sources, list) or any(
        not isinstance(item, dict) for item in raw_sources
    ):
        raise ValueError("manifesto histórico inválido: sources deve ser uma lista de objetos")
    required = {"reference_year", "source_path", "sha256"}
    for index, item in enumerate(raw_sources):
        if not required <= item.keys():
            raise ValueError(
                "manifesto histórico inválido: fonte sem reference_year, "
                f"source_path ou sha256 (índice {index})"
            )
        if (
            not isinstance(item["reference_year"], int)
            or isinstance(item["reference_year"], bool)
            or not isinstance(item["source_path"], str)
            or not item["source_path"].strip()
            or not isinstance(item["sha256"], str)
            or not SHA256_PATTERN.fullmatch(item["sha256"])
        ):
            raise ValueError(
                f"manifesto histórico inválido: fonte malformada (índice {index})"
            )
    return list(raw_sources)


def _validate_document_sources(raw_sources: object) -> dict[str, dict[str, object]]:
    if not isinstance(raw_sources, dict) or any(
        not isinstance(value, dict) for value in raw_sources.values()
    ):
        raise ValueError("manifesto de fontes históricas inválido: sources deve ser um mapa")
    required = {
        "source_id", "source_url", "source_path", "reference_period",
        "sha256", "size_bytes", "extraction_status",
    }
    for source_id, entry in raw_sources.items():
        if not isinstance(source_id, str) or not required <= entry.keys():
            raise ValueError("manifesto de fontes históricas inválido: fonte incompleta")
        if (
            entry["source_id"] != source_id
            or not isinstance(entry["source_url"], str)
            or not entry["source_url"].strip()
            or not isinstance(entry["source_path"], str)
            or not entry["source_path"].strip()
            or not isinstance(entry["reference_period"], str)
            or not entry["reference_period"].strip()
            or not isinstance(entry["sha256"], str)
            or not SHA256_PATTERN.fullmatch(entry["sha256"])
            or not isinstance(entry["size_bytes"], int)
            or isinstance(entry["size_bytes"], bool)
            or entry["size_bytes"] <= 0
            or entry["extraction_status"] != "RAW_ONLY"
        ):
            raise ValueError("manifesto de fontes históricas inválido: fonte malformada")
    return dict(raw_sources)


def promote_historical_source(
    root: Path,
    source_path: Path,
    *,
    source_id: str,
    source_url: str,
    reference_period: str,
) -> Path:
    """Preserva uma fonte histórica oficial sem convertê-la em crosswalk.

    A publicação de genealogia do IBGE é um artefato documental, não uma
    tabela tabular consumível pelo resolvedor. O registro explícito evita que
    a fonte seja perdida e deixa a extração futura sujeita a validação própria;
    nenhum evento municipal é criado por esta função.
    """
    if not source_id or Path(source_id).name != source_id:
        raise ValueError("source_id inválido para uma fonte histórica local")
    if not isinstance(source_url, str) or not source_url.strip():
        raise ValueError("source_url obrigatório para uma fonte histórica")
    if not isinstance(reference_period, str) or not reference_period.strip():
        raise ValueError("reference_period obrigatório para uma fonte histórica")
    if not source_path.is_file():
        raise ValueError(f"fonte histórica ausente: {source_path}")
    content = source_path.read_bytes()
    if not content:
        raise ValueError("fonte histórica vazia")

    sources_dir = root / "historical" / "sources"
    destination = sources_dir / source_id
    digest = hashlib.sha256(content).hexdigest()
    manifest_path = root / "historical" / "sources.manifest.json"
    existing: dict[str, dict[str, object]] = {}
    if manifest_path.exists():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"manifesto de fontes históricas inválido: {manifest_path}") from exc
        if not isinstance(loaded, dict):
            raise ValueError(f"manifesto de fontes históricas inválido: {manifest_path}")
        raw_sources = loaded.get("sources", {})
        try:
            existing = _validate_document_sources(raw_sources)
        except ValueError as exc:
            raise ValueError(f"{exc}: {manifest_path}") from exc

    entry = {
        "source_id": source_id,
        "source_url": source_url,
        "source_path": str(source_path),
        "reference_period": reference_period,
        "sha256": digest,
        "size_bytes": len(content),
        "extraction_status": "RAW_ONLY",
    }
    previous = existing.get(source_id)
    if previous is not None:
        if previous.get("sha256") != digest:
            raise ValueError(f"source_id imutável já associado a outro SHA-256: {source_id}")
        if not destination.exists():
            raise ValueError(f"fonte histórica registrada está ausente: {destination}")
        return destination

    sources_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=sources_dir, prefix=f".{source_id}.", suffix=".tmp", delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        temporary.write(content)
    try:
        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)

    existing[source_id] = entry
    write_json_atomic(
        {"schema_version": "1.0", "sources": dict(sorted(existing.items()))},
        manifest_path,
    )
    return destination


def download_historical_source(
    root: Path,
    *,
    url: str,
    source_id: str,
    reference_period: str,
    expected_sha256: str | None = None,
    session: requests.Session | None = None,
    timeout: float = 120,
) -> Path:
    """Baixa e preserva uma fonte histórica oficial como ``RAW_ONLY``.

    O conteúdo não é interpretado durante a aquisição. A promoção posterior
    continua responsável por registrar o artefato e sua proveniência, evitando
    que um PDF editorial seja confundido com uma tabela de sucessões.
    """
    if not source_id or Path(source_id).name != source_id:
        raise ValueError("source_id inválido para uma fonte histórica local")
    if not isinstance(url, str) or not url.strip():
        raise ValueError("source_url obrigatório para uma fonte histórica")
    if not isinstance(reference_period, str) or not reference_period.strip():
        raise ValueError("reference_period obrigatório para uma fonte histórica")

    sources_dir = root / "historical" / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    client = session or requests.Session()
    owns_session = session is None
    temporary_path: Path | None = None
    response = None
    try:
        response = client.get(url, stream=True, timeout=timeout)
        response.raise_for_status()
        digest = hashlib.sha256()
        with tempfile.NamedTemporaryFile(
            dir=sources_dir, prefix=f".{source_id}.", suffix=".tmp", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            try:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        digest.update(chunk)
                        temporary.write(chunk)
            except Exception:
                temporary_path.unlink(missing_ok=True)
                raise
        actual_sha256 = digest.hexdigest()
        if expected_sha256 and actual_sha256 != expected_sha256:
            raise ValueError(
                "SHA-256 da fonte histórica diverge: "
                f"esperado {expected_sha256}, obtido {actual_sha256}"
            )
        return promote_historical_source(
            root,
            temporary_path,
            source_id=source_id,
            source_url=url,
            reference_period=reference_period,
        )
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        if response is not None:
            response.close()
        if owns_session:
            client.close()



