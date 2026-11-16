from __future__ import annotations

import argparse
from pathlib import Path

from .client import DEFAULT_MUNICIPALITIES_URL
from . import refresh as service


def main() -> None:
    parser = argparse.ArgumentParser(description="Atualiza e promove uma release local do catálogo IBGE")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--catalog-id", required=True)
    parser.add_argument("--reference-year", type=int, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--dtb-url")
    source.add_argument("--dtb-archive", type=Path)
    source.add_argument("--localidades", action="store_true")
    parser.add_argument("--source-url")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    if args.dtb_archive is not None and not args.source_url:
        parser.error("--dtb-archive exige --source-url")
    if args.dtb_url:
        result = service.refresh_from_dtb_url(
            args.root, url=args.dtb_url, catalog_id=args.catalog_id,
            reference_year=args.reference_year, expected_sha256=args.expected_sha256,
            timeout=args.timeout,
        )
    elif args.dtb_archive is not None:
        result = service.refresh_from_dtb_archive(
            args.root, args.dtb_archive, catalog_id=args.catalog_id,
            source_url=args.source_url, reference_year=args.reference_year,
        )
    else:
        result = service.refresh_from_localidades(
            args.root, catalog_id=args.catalog_id,
            source_url=args.source_url or DEFAULT_MUNICIPALITIES_URL,
            reference_year=args.reference_year,
        )
    print(result)
