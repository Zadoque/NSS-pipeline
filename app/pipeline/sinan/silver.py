from __future__ import annotations

import os
import tempfile
import warnings
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ..atomic_io import write_json_atomic
from .columns import CATALOG, present_keys, required_keys, resolve_dedup_strategy

BASE_DIR = Path("/data")
DEFAULT_BATCH_SIZE = 50_000
DEFAULT_MEMORY_LIMIT = "512MB"
SOURCE_ROW_COLUMN = "_source_row"

UF_CODES = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP",
    "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB",
    "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
    "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
    "51": "MT", "52": "GO", "53": "DF",
}
UF_NAMES = {
    "RO": "Rondônia", "AC": "Acre", "AM": "Amazonas", "RR": "Roraima", "PA": "Pará",
    "AP": "Amapá", "TO": "Tocantins", "MA": "Maranhão", "PI": "Piauí", "CE": "Ceará",
    "RN": "Rio Grande do Norte", "PB": "Paraíba", "PE": "Pernambuco", "AL": "Alagoas",
    "SE": "Sergipe", "BA": "Bahia", "MG": "Minas Gerais", "ES": "Espírito Santo",
    "RJ": "Rio de Janeiro", "SP": "São Paulo", "PR": "Paraná", "SC": "Santa Catarina",
    "RS": "Rio Grande do Sul", "MS": "Mato Grosso do Sul", "MT": "Mato Grosso",
    "GO": "Goiás", "DF": "Distrito Federal",
}


def _validated_keys(available: set[str]) -> list[str]:
    missing_required = [
        CATALOG[key].source_column for key in required_keys()
        if CATALOG[key].source_column not in available
    ]
    if missing_required:
        raise ValueError(
            "Colunas obrigatórias do SINAN ausentes neste dataset: "
            f"{missing_required}. Colunas realmente disponíveis: {sorted(available)}"
        )

    return present_keys(available)


def _clean_and_filter(df: pd.DataFrame, year: int) -> tuple[pd.DataFrame, int, int]:
    keys = _validated_keys(set(df.columns))
    source_columns = [CATALOG[key].source_column for key in keys]

    out = df[source_columns].copy()

    for key in keys:
        spec = CATALOG[key]
        if spec.transform is not None:
            out[spec.source_column] = spec.transform(out[spec.source_column])

    valid_date = out["DT_NOTIFIC"].notna()
    in_year = out["DT_NOTIFIC"].dt.year.eq(year)
    invalid_dates = int((~valid_date).sum())
    outside_year = int((valid_date & ~in_year).sum())
    out = out[valid_date & in_year].copy()

    out["UF"] = out["SG_UF_NOT"].map(UF_CODES)
    out["NM_UF"] = out["UF"].map(UF_NAMES)
    return out, invalid_dates, outside_year


def _warn_dedup_fallback(dedup_cols: list[str], used_primary_key: bool) -> None:
    if not used_primary_key:
        warnings.warn(
            "Chave de negócio (NU_NOTIFIC) ausente neste dataset SINAN; "
            f"deduplicando por correspondência exata em {dedup_cols}. "
            "Isso é mais fraco que uma chave real: notificações distintas "
            "porém idênticas em todos os campos capturados serão tratadas "
            "como duplicata.",
            stacklevel=3,
        )


def transform(df: pd.DataFrame, year: int) -> pd.DataFrame:
    out, _, _ = _clean_and_filter(df, year)
    dedup_cols, used_primary_key = resolve_dedup_strategy(set(df.columns))
    _warn_dedup_fallback(dedup_cols, used_primary_key)
    return out.drop_duplicates(subset=dedup_cols, keep="last")


def _silver_schema(source_schema: pa.Schema, keys: list[str]) -> pa.Schema:
    fields = []
    for key in keys:
        spec = CATALOG[key]
        if spec.source_column == "DT_NOTIFIC":
            data_type = pa.timestamp("ns")
        elif spec.transform is not None:
            data_type = pa.string()
        else:
            data_type = source_schema.field(spec.source_column).type
        fields.append(pa.field(spec.source_column, data_type))
    # Preserva também os dtypes pandas (string e inteiros anuláveis) sem ler
    # registros. Os tipos Arrow explícitos cobrem colunas vazias ou nulas.
    empty_source_schema = pa.schema(
        [source_schema.field(CATALOG[key].source_column) for key in keys],
        metadata=source_schema.metadata,
    )
    empty_source = pa.Table.from_batches([], schema=empty_source_schema).to_pandas()
    empty_result, _, _ = _clean_and_filter(empty_source, year=2000)
    metadata = pa.Schema.from_pandas(empty_result, preserve_index=False).metadata
    return pa.schema(
        [*fields, pa.field("UF", pa.string()), pa.field("NM_UF", pa.string())],
        metadata=metadata,
    )


def _quote_column(column: str) -> str:
    return '"' + column.replace('"', '""') + '"'


def _deduplicate_file(
    source: Path, destination: Path, schema: pa.Schema, dedup_cols: list[str],
    *, batch_size: int, memory_limit: str, temp_directory: Path,
) -> int:
    columns = ", ".join(f"data.{_quote_column(column)}" for column in schema.names)
    keys = ", ".join(_quote_column(column) for column in dedup_cols)
    # Agrupa apenas as chaves e a posição, evitando ordenar todas as colunas
    # para escolher keep="last". NULLs pertencem ao mesmo grupo.
    query = f"""
        WITH last_rows AS (
            SELECT max({_quote_column(SOURCE_ROW_COLUMN)}) AS {_quote_column(SOURCE_ROW_COLUMN)}
            FROM read_parquet(?, hive_partitioning = false)
            GROUP BY {keys}
        )
        SELECT {columns}
        FROM read_parquet(?, hive_partitioning = false) AS data
        SEMI JOIN last_rows USING ({_quote_column(SOURCE_ROW_COLUMN)})
        ORDER BY data.{_quote_column(SOURCE_ROW_COLUMN)}
    """
    rows = 0
    with duckdb.connect(config={
        "memory_limit": memory_limit,
        "threads": 1,
        "temp_directory": str(temp_directory),
        "preserve_insertion_order": False,
    }) as connection:
        relation = connection.sql(query, params=[str(source), str(source)])
        with relation.to_arrow_reader(batch_size=batch_size) as reader:
            with pq.ParquetWriter(destination, schema) as writer:
                for batch in reader:
                    # O DuckDB pode expor uma coluna totalmente nula como
                    # INTEGER. Recupera o schema original antes de escrever.
                    arrays = [
                        pa.nulls(batch.num_rows) if pa.types.is_null(field.type)
                        else batch.column(index).cast(field.type)
                        for index, field in enumerate(schema)
                    ]
                    writer.write_table(pa.Table.from_arrays(arrays, schema=schema))
                    rows += batch.num_rows
    return rows


def transform_file(
    source: Path, disease: str, year: int, run_at: datetime | None = None,
    *, batch_size: int = DEFAULT_BATCH_SIZE, memory_limit: str = DEFAULT_MEMORY_LIMIT,
) -> Path:
    if batch_size <= 0:
        raise ValueError("batch_size deve ser maior que zero")
    source = Path(source)
    now = run_at or datetime.now(UTC)
    batch_id = now.strftime("%Y%m%dT%H%M%SZ")
    directory = (
        BASE_DIR / "silver" / "sinan" / f"disease={disease.lower()}"
        / f"source_year={year}" / f"ingestion_date={now.date()}" / f"batch_id={batch_id}"
    )
    parquet = directory / "data.parquet"

    len_before = invalid_dates = outside_year = cleaned_rows = batches = 0
    with pq.ParquetFile(source) as original:
        available = set(original.schema_arrow.names)
        keys = _validated_keys(available)
        columns = [CATALOG[key].source_column for key in keys]
        schema = _silver_schema(original.schema_arrow, keys)
        stage_schema = schema.append(pa.field(SOURCE_ROW_COLUMN, pa.int64()))
        dedup_cols, used_primary_key = resolve_dedup_strategy(available)
        _warn_dedup_fallback(dedup_cols, used_primary_key)

        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".silver-", dir=directory) as temporary:
            work_dir = Path(temporary)
            staged = work_dir / "cleaned.parquet"
            final = work_dir / "deduplicated.parquet"
            with pq.ParquetWriter(staged, stage_schema) as writer:
                for batch in original.iter_batches(batch_size=batch_size, columns=columns):
                    df = batch.to_pandas()
                    df.index = pd.RangeIndex(len_before, len_before + len(df))
                    len_before += len(df)
                    batches += 1
                    result, invalid, outside = _clean_and_filter(df, year)
                    invalid_dates += invalid
                    outside_year += outside
                    cleaned_rows += len(result)
                    if not result.empty:
                        table = pa.Table.from_pandas(result, schema=schema, preserve_index=False)
                        table = table.append_column(SOURCE_ROW_COLUMN, pa.array(result.index, type=pa.int64()))
                        writer.write_table(table)
                        del table
                    del df, result, batch
                    if batches % 10 == 0:
                        print(f"Silver: lotes={batches}, lidas={len_before}, válidas={cleaned_rows}", flush=True)

            print(f"Silver: deduplicação global de {cleaned_rows} registros", flush=True)
            len_after = _deduplicate_file(
                staged, final, schema, dedup_cols, batch_size=batch_size,
                memory_limit=memory_limit, temp_directory=work_dir / "spill",
            )
            os.replace(final, parquet)

    metadata = {
        "disease": disease.upper(),
        "source_year": year,
        "batch_id": batch_id,
        "ingested_at": now.isoformat(),
        "rows": len_after,
        "dropped_rows": len_before - len_after,
        "columns": schema.names,
        "source_rows": len_before,
        "invalid_date_rows": invalid_dates,
        "outside_year_rows": outside_year,
        "duplicate_rows": cleaned_rows - len_after,
        "batch_size": batch_size,
        "batches_processed": batches,
    }
    write_json_atomic(metadata, directory / "metadata.json")
    return parquet


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Transforma SINAN da camada Bronze para Silver")
    parser.add_argument("--source", required=True, type=Path, help="Arquivo Parquet de entrada (Bronze)")
    parser.add_argument("--disease", required=True, help="Código SINAN, por exemplo DENG")
    parser.add_argument("--year", required=True, type=int, help="Ano de referência para filtrar DT_NOTIFIC")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--memory-limit", default=DEFAULT_MEMORY_LIMIT, help="Limite de memória do DuckDB, ex.: 512MB")
    args = parser.parse_args()
    print(transform_file(
        args.source, args.disease.upper(), args.year,
        batch_size=args.batch_size, memory_limit=args.memory_limit,
    ))


if __name__ == "__main__":
    main()
