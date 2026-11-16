from __future__ import annotations

import argparse
import logging
from pathlib import Path

from . import run_cnes as service


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Ingere estabelecimentos CNES para um escopo geográfico")
    parser.add_argument("--catalog-root", type=Path)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--municipios")
    scope.add_argument("--ufs")
    scope.add_argument("--all-brazil", action="store_true")
    parser.add_argument("--page-size", type=int, default=service.DEFAULT_CNES_PAGE_SIZE)
    parser.add_argument("--request-timeout", type=float, default=service.DEFAULT_CNES_REQUEST_TIMEOUT)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--geocoder-url")
    parser.add_argument("--geocoder-cache", type=Path, default=service.BASE_DIR / "reference" / "cnes-geocoding.sqlite")
    parser.add_argument("--geocoder-timeout", type=float, default=20.0)
    parser.add_argument("--geocoder-user-agent", default="nss-pipeline-cnes/1.0")
    args = parser.parse_args()
    try:
        catalog = service.load_active_catalog(args.catalog_root) if args.catalog_root else None
        if (args.municipios or args.ufs or args.all_brazil) and catalog is None:
            raise ValueError("seleção geográfica exige --catalog-root")
        geographic_scope = None
        if catalog is not None:
            options = {
                "municipalities": args.municipios.split(",") if args.municipios else None,
                "ufs": args.ufs.split(",") if args.ufs else None,
                "all_brazil": args.all_brazil,
            }
            if args.all_brazil:
                options["require_national"] = True
            geographic_scope = service.select_scope(catalog, **options)
        run_kwargs = dict(
            catalog=catalog, geographic_scope=geographic_scope,
            page_size=args.page_size, request_timeout=args.request_timeout,
            continue_on_error=args.continue_on_error, workers=args.workers,
        )
        if args.geocoder_url:
            run_kwargs["geocoder"] = service.NominatimGeocoder(
                args.geocoder_url, cache_path=args.geocoder_cache,
                user_agent=args.geocoder_user_agent, timeout=args.geocoder_timeout,
            )
        if args.checkpoint is not None:
            run_kwargs["checkpoint_path"] = args.checkpoint
        service.run_cnes(**run_kwargs)
    except Exception:
        service.logger.exception("Falha na pipeline CNES")
        raise SystemExit(1) from None
