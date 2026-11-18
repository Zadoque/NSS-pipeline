"""Compatibility facade for PostgreSQL publication services."""

from __future__ import annotations

import os
from sqlalchemy import create_engine

from .publication.helpers import (
    CODIGO_NAO_INFORMADO,
    UNIDADE_NAO_IDENTIFICADA,
    _SENTINELAS,
    clean_code_series as _clean_code_series,
    integer_series as _integer_series,
    normalize_sem_not as _normalize_sem_not,
    prepare_fact_frame as _prepare_fact_frame,
    upsert as _upsert,
)
from .publication.dimensions import (
    load_cnes_to_postgres,
    upsert_dim_doenca,
    upsert_dim_municipio,
    upsert_dim_unidade_saude,
)
from .publication.classification import upsert_dim_classificacao, upsert_dim_evolucao
from .publication.facts import (
    FACT_KEY_COLUMNS,
    _expanding_statement,
    _metadata_snapshot,
    _register_catalog_release,
    _scope_statement,
    _validate_snapshot,
    insert_fato_casos,
)
from .publication.publish import DISEASE_NAMES, load_gold_to_postgres


def get_engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL não definida. Configure-a no .env (usado via env_file no docker-compose.yml).")
    return create_engine(url)
