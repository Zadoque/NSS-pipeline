from __future__ import annotations

import pandas as pd
from sqlalchemy.engine import Connection, Engine

from .helpers import _SENTINELAS, upsert
from .diseases import DISEASE_NAMES

_upsert = upsert

FACT_INSERT_BATCH_SIZE = 10_000

def upsert_dim_doenca(conn: Connection, disease_codigo: str) -> None:
    nome = DISEASE_NAMES.get(disease_codigo, disease_codigo)
    _upsert(
        conn,
        "analytics.dim_doenca",
        [{"codigo": disease_codigo, "nome": nome}],
        conflict_cols=["codigo"],
    )


def upsert_dim_municipio(
    conn: Connection,
    fact_df: pd.DataFrame,
    *,
    catalog=None,
    require_unit_municipalities: bool = False,
    scope_municipalities: Sequence[str] | None = None,
) -> None:
    required = {"cd_mun", "nm_mun", "cd_uf", "nm_uf"}
    if not required.issubset(fact_df.columns):
        return

    rows = (
        fact_df[["cd_mun", "nm_mun", "cd_uf", "nm_uf"]]
        .dropna(subset=["cd_mun"])
        .drop_duplicates(subset=["cd_mun"])
        .to_dict(orient="records")
    )
    notification_codes = {row["cd_mun"] for row in rows}
    unit_codes = set(
        fact_df.get("cd_mun_unidade", pd.Series(dtype="string"))
        .dropna()
        .astype("string")
    )
    missing_unit_codes = unit_codes - notification_codes
    if missing_unit_codes and catalog is not None:
        for code in sorted(missing_unit_codes):
            municipality = catalog.get_municipality(code)
            if municipality is None:
                raise ValueError(
                    f"município da unidade CNES ausente no catálogo IBGE: {code}"
                )
            rows.append({
                "cd_mun": municipality.code7,
                "nm_mun": municipality.name,
                "cd_uf": municipality.uf_code,
                "nm_uf": municipality.uf_name,
            })
    elif missing_unit_codes and require_unit_municipalities:
        raise ValueError(
            "Gold referencia municípios CNES fora do recorte de notificações; "
            "publique com uma release IBGE para cadastrar a dimensão canônica"
        )
    if catalog is not None and scope_municipalities is not None:
        existing_codes = {row["cd_mun"] for row in rows}
        for code in scope_municipalities:
            if code in existing_codes:
                continue
            municipality = catalog.get_municipality(code)
            if municipality is None:
                raise ValueError(f"município do escopo ausente no catálogo IBGE: {code}")
            rows.append({
                "cd_mun": municipality.code7,
                "nm_mun": municipality.name,
                "cd_uf": municipality.uf_code,
                "nm_uf": municipality.uf_name,
            })
    rows = list({row["cd_mun"]: row for row in rows}.values())
    _upsert(conn, "analytics.dim_municipio", rows, conflict_cols=["cd_mun"])


def upsert_dim_unidade_saude(conn: Connection, fact_df: pd.DataFrame) -> None:
    """Deriva as linhas de dim_unidade_saude a partir do MESMO cd_unidade
    já normalizado em fact_df — garante que todo código referenciado pelo
    fato exista na dimensão antes do INSERT do fato acontecer.

    O código sentinela (UNIDADE_NAO_IDENTIFICADA) é ignorado aqui: ele já
    foi seedado com descrição curada pela migration e não deve ser
    sobrescrito com nomes nulos.
    """
    # O município da notificação e o município cadastrado da unidade são
    # identidades distintas. Somente o segundo pode alimentar a FK da unidade;
    # sem ele, a dimensão permanece sem município.
    if "cd_mun_unidade" in fact_df.columns:
        fact_df = fact_df.drop(columns=["cd_mun"], errors="ignore").rename(
            columns={"cd_mun_unidade": "cd_mun"}
        )
    else:
        fact_df = fact_df.drop(columns=["cd_mun"], errors="ignore")
    # Nomes aqui devem bater EXATAMENTE com as colunas de
    # analytics.dim_unidade_saude (migration 0001) — "razao_social",
    # não "razao_social_unidade" (esse é o nome vindo do silver_cnes.py).
    #
    # cd_mun (FK para dim_municipio) é utilizado quando a Silver CNES foi
    # produzida com um MunicipalityCatalog IBGE. Sem esse catálogo, o caminho
    # legado mantém a FK nula: o código CNES de seis dígitos não deve ser
    # convertido por preenchimento ou cálculo heurístico do dígito verificador.
    source_to_db = {
        "nm_unidade": "nm_unidade",
        "razao_social_unidade": "razao_social",
        "tp_unidade": "tp_unidade",
    }
    present_source_cols = [c for c in source_to_db if c in fact_df.columns]

    subset = (
        fact_df[["cd_unidade", *present_source_cols, *(["cd_mun"] if "cd_mun" in fact_df.columns else [])]]
        .copy()
        .rename(columns=source_to_db)
    )
    subset = subset[~subset["cd_unidade"].isin(_SENTINELAS)]

    if "cd_mun" in subset.columns:
        municipality_counts = (
            subset.dropna(subset=["cd_mun"])
            .groupby("cd_unidade")["cd_mun"]
            .nunique()
        )
        conflicting = sorted(municipality_counts[municipality_counts > 1].index.tolist())
        if conflicting:
            raise ValueError(
                "unidade CNES associada a municípios distintos: "
                f"{', '.join(map(str, conflicting))}"
            )
        # Uma linha sem município não deve apagar uma associação válida da
        # mesma unidade apenas por aparecer primeiro no DataFrame.
        subset["_cd_mun_present"] = subset["cd_mun"].notna()
        subset = subset.sort_values(
            ["cd_unidade", "_cd_mun_present"],
            ascending=[True, False],
            kind="stable",
        ).drop_duplicates(subset=["cd_unidade"]).drop(columns=["_cd_mun_present"])
    else:
        subset = subset.drop_duplicates(subset=["cd_unidade"])

    db_cols = ["nm_unidade", "razao_social", "tp_unidade", "cd_mun"]
    for col in db_cols:
        if col not in subset.columns:
            subset[col] = None

    # O CNES não encontrado no snapshot SINAN pode deixar os atributos
    # descritivos como NaN (float) após o merge pandas. NaN não é um NULL
    # PostgreSQL válido para SMALLINT e acaba sendo rejeitado pelo driver
    # como "smallint out of range". Normalize o código para inteiro ou
    # NULL antes de enviar os parâmetros ao banco.
    subset["tp_unidade"] = pd.to_numeric(
        subset["tp_unidade"], errors="coerce"
    )
    invalid_type = subset["tp_unidade"].notna() & (
        (subset["tp_unidade"] % 1 != 0)
        | ~subset["tp_unidade"].between(-32768, 32767)
    )
    if invalid_type.any():
        raise ValueError("tp_unidade contém código inteiro fora da faixa SMALLINT")
    subset["tp_unidade"] = (
        subset["tp_unidade"]
        .astype("Int64")
        .astype(object)
        .where(lambda values: pd.notna(values), None)
    )

    rows = subset[["cd_unidade", *db_cols]].to_dict(orient="records")
    if len(rows) > 10_000:
        # SQLAlchemy's default psycopg2 executemany issues one round trip per
        # row for this dimension.  CNES national snapshots can exceed 600k
        # units, so use PostgreSQL's multi-values executor in bounded pages.
        from psycopg2.extras import execute_values

        columns = ["cd_unidade", *db_cols]
        update_columns = [column for column in columns if column != "cd_unidade"]
        update_clause = ", ".join(
            f"{column} = COALESCE(EXCLUDED.{column}, analytics.dim_unidade_saude.{column})"
            for column in update_columns
        )
        statement = f"""
            INSERT INTO analytics.dim_unidade_saude ({', '.join(columns)})
            VALUES %s
            ON CONFLICT (cd_unidade) DO UPDATE SET {update_clause}
        """
        values = [tuple(row.get(column) for column in columns) for row in rows]
        raw = conn.connection.driver_connection
        with raw.cursor() as cursor:
            execute_values(cursor, statement, values, page_size=10_000)
        return
    _upsert(
        conn,
        "analytics.dim_unidade_saude",
        rows,
        conflict_cols=["cd_unidade"],
        preserve_existing_on_null=True,
    )


def load_cnes_to_postgres(
    engine: Engine, cnes_df: pd.DataFrame, *, catalog=None,
) -> None:
    """Publica o snapshot Silver CNES na dimensão de unidades.

    A carga é separada da Gold do SINAN para que o catálogo nacional de
    estabelecimentos chegue ao PostgreSQL mesmo quando uma doença não possui
    notificações no recorte publicado.
    """
    required = {"cd_unidade", "cd_mun"}
    missing = required - set(cnes_df.columns)
    if missing:
        raise ValueError(f"Silver CNES sem colunas obrigatórias: {sorted(missing)}")
    if cnes_df.empty:
        raise ValueError("Silver CNES vazia: publicação bloqueada")
    if catalog is None:
        raise ValueError("carga CNES nacional exige o catálogo IBGE ativo")

    cnes_codes = set(cnes_df["cd_mun"].dropna().astype("string").str.strip())
    catalog_municipalities = catalog.municipalities()
    catalog_codes = {municipality.code7 for municipality in catalog_municipalities}
    missing_codes = sorted(cnes_codes - catalog_codes)
    if missing_codes:
        raise ValueError(f"CNES referencia município ausente no catálogo IBGE: {missing_codes[:5]}")
    municipalities = [
        {
            "cd_mun": municipality.code7,
            "nm_mun": municipality.name,
            "cd_uf": municipality.uf_code,
            "nm_uf": municipality.uf_name,
        }
        for municipality in catalog_municipalities
    ]
    with engine.begin() as conn:
        _upsert(conn, "analytics.dim_municipio", municipalities, conflict_cols=["cd_mun"])
        upsert_dim_unidade_saude(conn, cnes_df)





