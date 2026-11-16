"""Interface de linha de comando do atualizador SINAN."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from . import update_sinan as service


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Verifica e publica atualizações diárias do SINAN")
    parser.add_argument("--diseases", default=",".join(service.TRACKED_DISEASES), help="Códigos PySUS separados por vírgula")
    parser.add_argument("--years", help="Anos separados por vírgula; padrão: ano UTC atual")
    parser.add_argument("--manifest", type=Path, default=service.MANIFEST_PATH)
    parser.add_argument("--catalog-root", type=Path, help="Diretório local da release IBGE ativa")
    parser.add_argument("--all-brazil", action="store_true", help="Publica no escopo nacional da release IBGE ativa")
    parser.add_argument("--cnes-batch-id", help="Lote CNES explícito usado pela Gold serving")
    parser.add_argument("--allow-unavailable", action="store_true", help="Conclui mesmo sem Parquet no ano")
    parser.add_argument("--continue-on-error", action="store_true", help="Continua após falhas de schema/processamento")
    parser.add_argument("--allow-uf-mismatch", action="store_true", help="Canoniza pelo código IBGE e preserva a qualidade")
    args = parser.parse_args()
    diseases = [value.strip().upper() for value in args.diseases.split(",") if value.strip()]
    unknown = sorted(set(diseases) - set(service.TRACKED_DISEASES))
    if unknown:
        raise SystemExit(f"Doenças não acompanhadas: {', '.join(unknown)}")
    if not diseases:
        parser.error("Informe ao menos uma doença em --diseases")
    try:
        from .reference.ibge.storage import load_active_catalog
        catalog = load_active_catalog(args.catalog_root) if args.catalog_root else None
        if args.all_brazil and catalog is None:
            raise ValueError("--all-brazil exige --catalog-root")
        geographic_scope = None
        if args.all_brazil:
            from .scope import select_scope
            geographic_scope = select_scope(catalog, all_brazil=True, require_national=True)
        results = service.update(
            diseases, service._parse_years(args.years), args.manifest,
            catalog=catalog, cnes_batch_id=args.cnes_batch_id,
            geographic_scope=geographic_scope,
            continue_on_error=args.continue_on_error,
            allow_uf_mismatch=args.allow_uf_mismatch,
        ) or []
        unavailable = [result for result in results if result.endswith(": unavailable")]
        if unavailable and not args.allow_unavailable:
            logger = logging.getLogger(__name__)
            logger.error("Fontes SINAN indisponíveis; manifesto preservado: %s", ", ".join(unavailable))
            raise SystemExit(3)
    except Exception:
        logging.getLogger(__name__).exception("Falha no atualizador SINAN (manifesto=%s)", args.manifest)
        raise SystemExit(1) from None
