from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .atomic_io import write_json_atomic, write_parquet_atomic
from .cnes.bronze import fetch_estabelecimentos, write_bronze_cnes
from .cnes.silver import transform_cnes
from .sinan.gold import MUNICIPIOS_RJ

BASE_DIR = Path("/data")


def run_cnes(municipios: dict[str, str] | None = None) -> Path:
    municipios = municipios if municipios is not None else MUNICIPIOS_RJ
    run_at = datetime.now(UTC)

    silvers = []
    for cod_municipio in municipios:
        bronze_df = fetch_estabelecimentos(cod_municipio)
        if bronze_df.empty:
            raise RuntimeError(f"API CNES retornou vazio para município {cod_municipio}")

        write_bronze_cnes(bronze_df, cod_municipio, run_at=run_at)
        silvers.append(transform_cnes(bronze_df))

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
        "columns": list(consolidated.columns),
    }
    write_json_atomic(metadata, directory / "metadata.json")
    return parquet


if __name__ == "__main__":
    print(run_cnes())