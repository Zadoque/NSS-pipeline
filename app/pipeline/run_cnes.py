from __future__ import annotations

import argparse
import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests

from .atomic_io import write_json_atomic, write_parquet_atomic
from .cnes.bronze import fetch_estabelecimentos, session_with_retries, write_bronze_cnes
from .cnes.silver import transform_cnes
from .territory_mapping import enrich_cnes_territories
from .territory_assets import asset_directory
from .reference.ibge.models import MunicipalityCatalog, ResolutionStatus
from .reference.ibge.storage import load_active_catalog
from .scope import GeographicScope, legacy_rj_mapping, select_scope, validate_scope_catalog

BASE_DIR = Path("/data")
TERRITORY_ASSETS_DIR = Path(__file__).resolve().parents[2] / "territories"
logger = logging.getLogger(__name__)
DEFAULT_CNES_PAGE_SIZE = 100
DEFAULT_CNES_REQUEST_TIMEOUT = 60.0
_SHA256_LENGTH = 64


def _validate_checkpoint_completed(completed: object, municipios: dict[str, str]) -> dict:
    if not isinstance(completed, dict):
        raise ValueError("checkpoint CNES com completed inválido")
    expected_codes = set(municipios)
    if not set(completed).issubset(expected_codes):
        raise ValueError("checkpoint CNES contém município fora do escopo")
    for code, entry in completed.items():
        if not isinstance(code, str) or not isinstance(entry, dict):
            raise ValueError("checkpoint CNES com completed inválido")
        bronze_path = entry.get("bronze_path")
        bronze_sha256 = entry.get("bronze_sha256")
        rows = entry.get("rows")
        if (
            not isinstance(bronze_path, str) or not bronze_path
            or not isinstance(bronze_sha256, str)
            or len(bronze_sha256) != _SHA256_LENGTH
            or any(character not in "0123456789abcdefABCDEF" for character in bronze_sha256)
            or not isinstance(rows, int)
            or isinstance(rows, bool)
            or rows < 0
        ):
            raise ValueError("checkpoint CNES com completed inválido")
    return completed


def _validate_checkpoint_failed(failed: object, municipios: dict[str, str]) -> dict:
    if not isinstance(failed, dict):
        raise ValueError("checkpoint CNES com failed inválido")
    expected_codes = set(municipios)
    if not set(failed).issubset(expected_codes):
        raise ValueError("checkpoint CNES contém falha fora do escopo")
    for code, entry in failed.items():
        if not isinstance(code, str) or not isinstance(entry, dict):
            raise ValueError("checkpoint CNES com failed inválido")
        error_type = entry.get("error_type")
        error_message = entry.get("error_message")
        if (
            not isinstance(error_type, str) or not error_type
            or not isinstance(error_message, str) or not error_message
        ):
            raise ValueError("checkpoint CNES com failed inválido")
    return failed


def _classify_cnes_error(error: Exception) -> str:
    if isinstance(error, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return "NETWORK_ERROR"
    if isinstance(error, requests.exceptions.HTTPError):
        return "HTTP_ERROR"
    if isinstance(error, ValueError):
        return "VALIDATION_ERROR"
    if isinstance(error, RuntimeError):
        return "API_ERROR"
    return "PROCESSING_ERROR"


def _canonicalize_municipalities(
    requested: dict[str, str],
    catalog: MunicipalityCatalog,
) -> dict[str, str]:
    """Resolve um mapa legado contra a identidade canônica da release IBGE."""
    canonical: dict[str, str] = {}
    for code7, supplied_name in requested.items():
        result = catalog.resolve(code7)
        if result.status is not ResolutionStatus.VALID or result.municipality is None:
            raise ValueError(f"município CNES inválido no catálogo: {code7}")
        if supplied_name and supplied_name != result.municipality.name:
            raise ValueError(
                "nome municipal diverge do catálogo IBGE: "
                f"{code7} ({supplied_name!r} != {result.municipality.name!r})"
            )
        canonical[result.municipality.code7] = result.municipality.name
    return canonical


def run_cnes(
    municipios: dict[str, str] | None = None,
    *,
    catalog: MunicipalityCatalog | None = None,
    geographic_scope: GeographicScope | None = None,
    page_size: int = DEFAULT_CNES_PAGE_SIZE,
    session=None,
    request_timeout: float = DEFAULT_CNES_REQUEST_TIMEOUT,
    checkpoint_path: Path | None = None,
    continue_on_error: bool = False,
) -> Path:
    if not isinstance(page_size, int) or isinstance(page_size, bool) or page_size <= 0:
        raise ValueError("page_size CNES deve ser um inteiro maior que zero")
    if not isinstance(request_timeout, (int, float)) or isinstance(request_timeout, bool) or request_timeout <= 0:
        raise ValueError("request_timeout CNES deve ser maior que zero")
    if catalog is not None and geographic_scope is not None:
        validate_scope_catalog(catalog, geographic_scope)
    if geographic_scope is not None:
        municipios = {item.code7: item.name for item in geographic_scope.municipalities}
    elif catalog is not None:
        if municipios is not None:
            municipios = _canonicalize_municipalities(municipios, catalog)
        else:
            municipios = {item.code7: item.name for item in select_scope(catalog).municipalities}
    else:
        municipios = municipios if municipios is not None else legacy_rj_mapping()
    if not municipios:
        raise ValueError("Informe ao menos um município para a carga CNES")
    checkpoint = None
    if checkpoint_path is not None and checkpoint_path.exists():
        try:
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"checkpoint CNES inválido: {checkpoint_path}") from exc
        if not isinstance(checkpoint, dict):
            raise ValueError(f"checkpoint CNES inválido: {checkpoint_path}")
        expected = {
            "municipios": list(municipios),
            "ibge_catalog_id": catalog.metadata.catalog_id if catalog else None,
            "ibge_catalog_sha256": catalog.metadata.sha256 if catalog else None,
            "cnes_page_size": page_size,
            "cnes_request_timeout": request_timeout,
            "continue_on_error": continue_on_error,
        }
        actual = {
            key: checkpoint.get(key, False) if key == "continue_on_error" else checkpoint.get(key)
            for key in expected
        }
        if actual != expected:
            raise ValueError("checkpoint CNES não corresponde ao escopo ou parâmetros solicitados")
        try:
            run_at = datetime.fromisoformat(checkpoint["ingested_at"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("checkpoint CNES sem ingested_at válido") from exc
    else:
        run_at = datetime.now(UTC)
    completed = _validate_checkpoint_completed((checkpoint or {}).get("completed", {}), municipios)
    failed = _validate_checkpoint_failed((checkpoint or {}).get("failed", {}), municipios)
    logger.info("Iniciando CNES municipios=%s", len(municipios))

    silvers = []
    request_session = session or session_with_retries()
    owns_session = session is None
    try:
        for cod_municipio in municipios:
            logger.info("Processando CNES municipio=%s", cod_municipio)
            if cod_municipio in failed:
                logger.warning("Ignorando município previamente classificado como falho: %s", cod_municipio)
                continue
            checkpoint_entry = completed.get(cod_municipio)
            try:
                if checkpoint_entry is not None:
                    bronze_path = Path(checkpoint_entry.get("bronze_path", ""))
                    if not bronze_path.is_file():
                        raise ValueError(f"checkpoint CNES aponta para Bronze ausente: {bronze_path}")
                    expected_sha256 = checkpoint_entry.get("bronze_sha256")
                    actual_sha256 = hashlib.sha256(bronze_path.read_bytes()).hexdigest()
                    if expected_sha256 != actual_sha256:
                        raise ValueError(f"Bronze CNES adulterada ou incompatível: {bronze_path}")
                    bronze_df = pd.read_parquet(bronze_path)
                else:
                    bronze_df = fetch_estabelecimentos(
                        cod_municipio,
                        limit=page_size,
                        catalog=catalog,
                        session=request_session,
                        timeout=request_timeout,
                    )
                if bronze_df.empty:
                    raise RuntimeError(f"API CNES retornou vazio para município {cod_municipio}")

                bronze_path = (
                    Path(checkpoint_entry["bronze_path"])
                    if checkpoint_entry is not None
                    else write_bronze_cnes(bronze_df, cod_municipio, run_at=run_at)
                )
                silver = (
                    transform_cnes(bronze_df, catalog=catalog, municipality_code7=cod_municipio)
                    if catalog is not None
                    else transform_cnes(bronze_df, municipality_code7=cod_municipio)
                )
                if (
                    "municipality_resolution_status" in silver
                    and silver["municipality_resolution_status"].eq("OUT_OF_SCOPE").any()
                ):
                    raise ValueError(
                        f"CNES retornou estabelecimento fora do município solicitado: {cod_municipio}"
                    )
                territory_assets = asset_directory(cod_municipio, root=TERRITORY_ASSETS_DIR)
                if territory_assets is not None:
                    silver = enrich_cnes_territories(silver, territory_assets)
                else:
                    silver["notification_district_id"] = pd.NA
                    silver["notification_neighborhood_id"] = pd.NA
                    silver["notification_territory_status"] = "UNAVAILABLE"
                silvers.append(silver)
                if checkpoint_path is not None and checkpoint_entry is None:
                    completed[cod_municipio] = {
                        "bronze_path": str(bronze_path),
                        "rows": len(bronze_df),
                        "bronze_sha256": hashlib.sha256(bronze_path.read_bytes()).hexdigest(),
                    }
            except Exception as error:
                if not continue_on_error:
                    raise
                failed[cod_municipio] = {
                    "error_type": _classify_cnes_error(error),
                    "error_message": str(error),
                }
                logger.exception("Falha classificada no município CNES=%s", cod_municipio)
            if checkpoint_path is not None:
                write_json_atomic(
                    {
                        "status": "IN_PROGRESS",
                        "ingested_at": run_at.isoformat(),
                        "municipios": list(municipios),
                        "ibge_catalog_id": catalog.metadata.catalog_id if catalog else None,
                        "ibge_catalog_sha256": catalog.metadata.sha256 if catalog else None,
                        "cnes_page_size": page_size,
                        "cnes_request_timeout": request_timeout,
                        "continue_on_error": continue_on_error,
                        "completed": completed,
                        "failed": failed,
                    },
                    checkpoint_path,
                )
    finally:
        if owns_session and request_session is not None:
            request_session.close()

    if not silvers:
        raise RuntimeError("CNES não produziu nenhum município com dados")
    consolidated = pd.concat(silvers, ignore_index=True).drop_duplicates(
        subset=["cd_unidade"], keep="last"
    )

    batch_id = run_at.strftime("%Y%m%dT%H%M%SZ")
    directory = BASE_DIR / "silver" / "cnes" / f"batch_id={batch_id}"
    parquet = directory / "data.parquet"
    write_parquet_atomic(consolidated, parquet)

    metadata = {
        "status": "COMPLETED" if not failed else "PARTIAL",
        "batch_id": batch_id,
        "ingested_at": run_at.isoformat(),
        "rows": len(consolidated),
        "municipios": list(municipios),
        "ibge_catalog_id": catalog.metadata.catalog_id if catalog else None,
        "ibge_catalog_sha256": catalog.metadata.sha256 if catalog else None,
        "cnes_page_size": page_size,
        "cnes_request_timeout": request_timeout,
        "continue_on_error": continue_on_error,
        "failed_municipalities": failed,
        "columns": list(consolidated.columns),
    }
    write_json_atomic(metadata, directory / "metadata.json")
    if checkpoint_path is not None:
        write_json_atomic(
            {
                "status": "COMPLETED" if not failed else "PARTIAL",
                "ingested_at": run_at.isoformat(),
                "municipios": list(municipios),
                "ibge_catalog_id": catalog.metadata.catalog_id if catalog else None,
                "ibge_catalog_sha256": catalog.metadata.sha256 if catalog else None,
                "cnes_page_size": page_size,
                "cnes_request_timeout": request_timeout,
                "continue_on_error": continue_on_error,
                "completed": completed,
                "failed": failed,
                "output_path": str(parquet),
            },
            checkpoint_path,
        )
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
    parser.add_argument(
        "--request-timeout", type=float, default=DEFAULT_CNES_REQUEST_TIMEOUT,
        help=f"Timeout de cada requisição CNES em segundos (padrão: {DEFAULT_CNES_REQUEST_TIMEOUT:g})",
    )
    parser.add_argument(
        "--checkpoint", type=Path,
        help="Arquivo JSON para retomar a ingestão CNES após falha ou interrupção",
    )
    parser.add_argument(
        "--continue-on-error", action="store_true",
        help="Processa o lote inteiro e registra erros por município no checkpoint",
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
        run_kwargs = dict(
            catalog=catalog,
            geographic_scope=geographic_scope,
            page_size=args.page_size,
            request_timeout=args.request_timeout,
            continue_on_error=args.continue_on_error,
        )
        if args.checkpoint is not None:
            run_kwargs["checkpoint_path"] = args.checkpoint
        run_cnes(**run_kwargs)
    except Exception:
        logger.exception("Falha na pipeline CNES")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
