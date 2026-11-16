from __future__ import annotations

import logging

from . import run_load as service


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = service._build_parser()
    args = parser.parse_args()
    try:
        catalog = service.load_active_catalog(args.catalog_root) if args.catalog_root else None
        if (args.municipios or args.ufs or args.all_brazil) and catalog is None:
            raise ValueError("seleção geográfica exige --catalog-root")
        scope = None
        if catalog is not None:
            options = {
                "municipalities": args.municipios.split(",") if args.municipios else None,
                "ufs": args.ufs.split(",") if args.ufs else None,
                "all_brazil": args.all_brazil,
            }
            if args.all_brazil:
                options["require_national"] = True
            scope = service.select_scope(catalog, **options)
        options = {"allow_uf_mismatch": True} if args.allow_uf_mismatch else {}
        service.run_load(
            args.disease, args.year, allow_empty=args.allow_empty,
            catalog=catalog, geographic_scope=scope,
            cnes_batch_id=args.cnes_batch_id,
            **options,
        )
    except Exception:
        service.logger.exception("Falha na carga SINAN disease=%s year=%s", args.disease, args.year)
        raise SystemExit(1) from None
