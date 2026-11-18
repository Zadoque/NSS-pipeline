from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Roda a pipeline SINAN completa (grão fixo) e carrega o resultado no Postgres"
    )
    parser.add_argument("--disease", required=True, help="Ex.: DENG, TOXC, ZIKA")
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--allow-empty", action="store_true", help="Permite publicar zero no recorte")
    parser.add_argument("--catalog-root", type=Path, help="Diretório local de releases IBGE")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--municipios", help="Códigos municipais separados por vírgula")
    scope.add_argument("--ufs", help="UFs ou códigos de UF separados por vírgula")
    scope.add_argument("--all-brazil", action="store_true", help="Seleciona todos os municípios da release IBGE")
    parser.add_argument("--cnes-batch-id", help="Lote CNES fixado para o enriquecimento da Gold")
    parser.add_argument("--allow-uf-mismatch", action="store_true", help="Preserva a métrica de UF inconsistente")
    return parser
