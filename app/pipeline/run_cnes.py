from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .atomic_io import write_json_atomic, write_parquet_atomic
from .cnes.bronze import fetch_estabelecimentos, write_bronze_cnes
from .cnes.silver import transform_cnes
from .territory_mapping import enrich_cnes_territories
from .territory_assets import asset_directory
from .reference.ibge.models import MunicipalityCatalog
from .reference.ibge.storage import load_active_catalog
from .scope import GeographicScope, legacy_rj_mapping, select_scope

BASE_DIR = Path("/data")
TERRITORY_ASSETS_DIR = Path(__file__).resolve().parents[2] / "territories"
logger = logging.getLogger(__name__)
DEFAULT_CNES_PAGE_SIZE = 100


def run_cnes(
    municipios: dict[str, str] | None = None,
    *,
    catalog: MunicipalityCatalog | None = None,
    geographic_scope: GeographicScope | None = None,
    page_size: int = DEFAULT_CNES_PAGE_SIZE,
) -> Path:
    if not isinstance(page_size, int) or isinstance(page_size, bool) or page_size <= 0:
        raise ValueError("page_size CNES deve ser um inteiro maior que zero")
    if geographic_scope is not None:
        municipios = {item.code7: item.name for item in geographic_scope.municipalities}
    elif catalog is not None:
        municipios = {item.code7: item.name for item in select_scope(catalog).municipalities}
    else:
        municipios = municipios if municipios is not None else legacy_rj_mapping()
    if not municipios:
        raise ValueError("Informe ao menos um município para a carga CNES")
    run_at = datetime.now(UTC)
    logger.info("Iniciando CNES municipios=%s", len(municipios))

    silvers = []
    for cod_municipio in municipios:
        logger.info("Processando CNES municipio=%s", cod_municipio)
        bronze_df = (
            fetch_estabelecimentos(cod_municipio, limit=page_size, catalog=catalog)
            if catalog is not None
            else fetch_estabelecimentos(cod_municipio)
        )
        if bronze_df.empty:
            raise RuntimeError(f"API CNES retornou vazio para município {cod_municipio}")

        write_bronze_cnes(bronze_df, cod_municipio, run_at=run_at)
        silver = (
            transform_cnes(bronze_df, catalog=catalog)
            if catalog is not None
            else transform_cnes(bronze_df)
        )
        territory_assets = asset_directory(cod_municipio, root=TERRITORY_ASSETS_DIR)
        if territory_assets is not None:
            silver = enrich_cnes_territories(silver, territory_assets)
        else:
            silver["notification_district_id"] = pd.NA
            silver["notification_neighborhood_id"] = pd.NA
            silver["notification_territory_status"] = "UNAVAILABLE"
        silvers.append(silver)

    consolidated = pd.concat(silvers, ignore_index=True).drop_duplicates(
        subset=["cd_unidade"], keep="last"
    )

    batch_id = run_at.strftime("%Y%m%dT%H%M%SZ")
    directory = BASE_DIR / "silver" / "cnes" / f"batch_id={batch_id}"
    parquet = directory / "data.parquet"
    write_parquet_atomic(consolidated, parquet)

    metadata = {
        "batch_id": batch_id,
        "ingested_at": run_at.isoformat(),
        "rows": len(consolidated),
        "municipios": list(municipios),
        "ibge_catalog_id": catalog.metadata.catalog_id if catalog else None,
        "ibge_catalog_sha256": catalog.metadata.sha256 if catalog else None,
        "cnes_page_size": page_size,
        "columns": list(consolidated.columns),
    }
    write_json_atomic(metadata, directory / "metadata.json")
    logger.info("CNES concluído: %s (linhas=%s)", parquet, len(consolidated))
    return parquet


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(
        description="Ingere estabelecimentos CNES para um escopo geográfico"
    )
    parser.add_argument("--catalog-root", type=Path, help="Diretório local de releases IBGE")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--municipios", help="Códigos municipais separados por vírgula")
    scope.add_argument("--ufs", help="UFs ou códigos de UF separados por vírgula")
    scope.add_argument("--all-brazil", action="store_true", help="Seleciona todos os municípios da release IBGE")
    parser.add_argument(
        "--page-size", type=int, default=DEFAULT_CNES_PAGE_SIZE,
        help=f"Quantidade de registros por página da API CNES (padrão: {DEFAULT_CNES_PAGE_SIZE})",
    )
    args = parser.parse_args()
    try:
        catalog = load_active_catalog(args.catalog_root) if args.catalog_root else None
        if (args.municipios or args.ufs or args.all_brazil) and catalog is None:
            raise ValueError("seleção geográfica exige --catalog-root")
        geographic_scope = None
        if catalog is not None:
            geographic_scope = select_scope(
                catalog,
                municipalities=args.municipios.split(",") if args.municipios else None,
                ufs=args.ufs.split(",") if args.ufs else None,
                all_brazil=args.all_brazil,
            )
        run_cnes(
            catalog=catalog,
            geographic_scope=geographic_scope,
            page_size=args.page_size,
        )
    except Exception:
        logger.exception("Falha na pipeline CNES")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
