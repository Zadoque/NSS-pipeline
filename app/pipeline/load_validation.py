from __future__ import annotations

import json
from pathlib import Path

from .scope import GeographicScope, scope_sha256

GOLD_QUALITY_METRICS = (
    "source_rows", "resolved_rows", "discarded_rows", "aggregation_reduction",
    "invalid_municipality_rows", "out_of_scope_rows", "uf_mismatch_rows",
)


def validate_gold_for_publication(
    gold_path: Path,
    *,
    catalog,
    disease: str,
    year: int,
    municipios: dict[str, str],
    geographic_scope: GeographicScope | None,
    expected_cases_total: int,
) -> tuple[dict, dict, int]:
    metadata_path = gold_path.with_name("metadata.json")
    metadata = {}
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    quality = {key: int(metadata[key]) for key in GOLD_QUALITY_METRICS if key in metadata}
    if catalog is None:
        return metadata, quality, expected_cases_total
    missing = [key for key in GOLD_QUALITY_METRICS if key not in metadata]
    if missing:
        raise ValueError(
            "Publicação bloqueada: metadata.json da Gold não contém métricas obrigatórias "
            f"({', '.join(missing)})"
        )
    invalid = [
        key for key in GOLD_QUALITY_METRICS
        if not isinstance(metadata[key], int) or isinstance(metadata[key], bool) or metadata[key] < 0
    ]
    if invalid:
        raise ValueError(f"Publicação bloqueada: métricas Gold inválidas ({', '.join(invalid)})")
    if metadata["resolved_rows"] + metadata["discarded_rows"] != metadata["source_rows"]:
        raise ValueError("Publicação bloqueada: métricas Gold não reconciliam")
    if metadata["aggregation_reduction"] > metadata["resolved_rows"]:
        raise ValueError("Publicação bloqueada: redução da Gold não reconcilia")
    if (
        metadata.get("ibge_catalog_id") != catalog.metadata.catalog_id
        or metadata.get("ibge_catalog_sha256") != catalog.metadata.sha256
    ):
        raise ValueError("Publicação bloqueada: release IBGE da Gold diverge da release selecionada")
    if (
        metadata.get("disease") != disease
        or metadata.get("source_year") != year
        or metadata.get("gold_target") != "serving"
    ):
        raise ValueError("Publicação bloqueada: identidade da Gold diverge da execução")
    expected_type = geographic_scope.kind if geographic_scope else "MUNICIPALITIES"
    actual_scope = metadata.get("geographic_scope")
    if (
        not isinstance(actual_scope, dict)
        or actual_scope.get("type") != expected_type
        or actual_scope.get("municipality_count") != len(municipios)
        or actual_scope.get("scope_sha256") != scope_sha256(municipios)
    ):
        raise ValueError("Publicação bloqueada: escopo geográfico da Gold diverge do escopo selecionado")
    return metadata, quality, int(metadata["resolved_rows"])
