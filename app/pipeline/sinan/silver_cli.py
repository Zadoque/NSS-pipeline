from __future__ import annotations

import argparse
from pathlib import Path

from . import silver as service


def main() -> None:
    parser = argparse.ArgumentParser(description="Transforma SINAN da camada Bronze para Silver")
    parser.add_argument("--source", required=True, type=Path, help="Arquivo Parquet de entrada (Bronze)")
    parser.add_argument("--disease", required=True, help="Código SINAN, por exemplo DENG")
    parser.add_argument("--year", required=True, type=int, help="Ano de referência para filtrar DT_NOTIFIC")
    parser.add_argument("--batch-size", type=int, default=service.DEFAULT_BATCH_SIZE)
    parser.add_argument("--memory-limit", default=service.DEFAULT_MEMORY_LIMIT, help="Limite de memória do DuckDB, ex.: 512MB")
    args = parser.parse_args()
    print(service.transform_file(
        args.source, args.disease.upper(), args.year,
        batch_size=args.batch_size, memory_limit=args.memory_limit,
    ))
