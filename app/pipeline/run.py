from __future__ import annotations
 
import argparse
import logging
from datetime import UTC, datetime
from pathlib import Path
 
from .sinan.columns import CATALOG
from .sinan.gold import aggregate_file
from .sinan.bronze import fetch_sinan, write_bronze
from .sinan.silver import transform_file
from .reference.ibge.models import MunicipalityCatalog
from .reference.ibge.storage import load_active_catalog
from .scope import GeographicScope, select_scope, validate_scope_catalog
 
BASE_DIR = Path("/data")
logger = logging.getLogger(__name__)
 
 
def run(
    disease: str,
    year: int,
    selected_columns: list[str] | None = None,
    *,
    catalog: MunicipalityCatalog | None = None,
    geographic_scope: GeographicScope | None = None,
    cnes_batch_id: str | None = None,
) -> None:
    disease = disease.upper()
    if catalog is not None and geographic_scope is not None:
        validate_scope_catalog(catalog, geographic_scope)
    run_at = datetime.now(UTC)          
    logger.info("Iniciando SINAN disease=%s year=%s", disease, year)

    source = fetch_sinan(disease, year)
    bronze = write_bronze(source, disease, year, run_at=run_at)
    logger.info("Bronze concluída: %s", bronze)
    silver = transform_file(bronze, disease, year, run_at=run_at)
    logger.info("Silver concluída: %s", silver)
    if geographic_scope is not None:
        municipios = {item.code7: item.name for item in geographic_scope.municipalities}
    elif catalog is not None:
        municipios = {item.code7: item.name for item in select_scope(catalog).municipalities}
    else:
        municipios = None
    gold = aggregate_file(
        silver, disease, year, selected_columns, municipios=municipios, catalog=catalog,
        run_at=run_at, target="ad_hoc", cnes_batch_id=cnes_batch_id,
        geographic_scope_type=geographic_scope.kind if geographic_scope else "MUNICIPALITIES",
    )

    logger.info("Gold concluída: %s", gold)
 
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pipeline Medallion do SINAN")
    parser.add_argument("--disease", required=True, help="Ex.: DENG, TOXC, ZIKA")
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument(
        "--columns",
        default="",
        help=f"Chaves separadas por vírgula, dentre: {', '.join(CATALOG)}",
    )
    parser.add_argument("--catalog-root", type=Path, help="Diretório local de releases IBGE")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--municipios", help="Códigos municipais separados por vírgula")
    scope.add_argument("--ufs", help="UFs ou códigos de UF separados por vírgula")
    scope.add_argument("--all-brazil", action="store_true")
    parser.add_argument("--cnes-batch-id", help="Lote CNES fixado para o enriquecimento da Gold")
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = _build_parser()
    args = parser.parse_args()
    selected = [c.strip() for c in args.columns.split(",") if c.strip()]
    try:
        catalog = load_active_catalog(args.catalog_root) if args.catalog_root else None
        if catalog is None and (args.municipios or args.ufs or args.all_brazil):
            raise ValueError("seleção geográfica exige --catalog-root")
        scope = select_scope(
            catalog,
            municipalities=args.municipios.split(",") if args.municipios else None,
            ufs=args.ufs.split(",") if args.ufs else None,
            all_brazil=args.all_brazil,
        ) if catalog is not None else None
        run(
            args.disease, args.year, selected, catalog=catalog,
            geographic_scope=scope, cnes_batch_id=args.cnes_batch_id,
        )
    except Exception:
        logger.exception("Falha na pipeline SINAN disease=%s year=%s", args.disease, args.year)
        raise SystemExit(1) from None
 
if __name__ == "__main__":
    main()
