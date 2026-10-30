from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .atomic_io import write_json_atomic, write_parquet_atomic
from .cnes.bronze import fetch_estabelecimentos, write_bronze_cnes
from .cnes.silver import transform_cnes
from .sinan.gold import MUNICIPIOS_RJ
from .territory_mapping import enrich_cnes_territories
from .territory_assets import asset_directory
from .reference.ibge.models import MunicipalityCatalog
from .scope import GeographicScope, select_scope

BASE_DIR = Path("/data")
TERRITORY_ASSETS_DIR = Path(__file__).resolve().parents[2] / "territories"
logger = logging.getLogger(__name__)


def run_cnes(
    municipios: dict[str, str] | None = None,
    *,
    catalog: MunicipalityCatalog | None = None,
    geographic_scope: GeographicScope | None = None,
) -> Path:
    if geographic_scope is not None:
        municipios = {item.code7: item.name for item in geographic_scope.municipalities}
    elif catalog is not None:
        municipios = {item.code7: item.name for item in select_scope(catalog).municipalities}
    else:
        municipios = municipios if municipios is not None else MUNICIPIOS_RJ
    if not municipios:
        raise ValueError("Informe ao menos um município para a carga CNES")
    run_at = datetime.now(UTC)
    logger.info("Iniciando CNES municipios=%s", len(municipios))

    silvers = []
    for cod_municipio in municipios:
        logger.info("Processando CNES municipio=%s", cod_municipio)
        bronze_df = (
            fetch_estabelecimentos(cod_municipio, catalog=catalog)
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
        "columns": list(consolidated.columns),
    }
    write_json_atomic(metadata, directory / "metadata.json")
    logger.info("CNES concluído: %s (linhas=%s)", parquet, len(consolidated))
    return parquet


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        run_cnes()
    except Exception:
        logger.exception("Falha na pipeline CNES")
        raise SystemExit(1) from None
