from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

from .models import Municipality
from .models import CatalogValidationReport

CODE7 = re.compile(r"^[0-9]{7}$")
CODE6 = re.compile(r"^[0-9]{6}$")
NATIONAL_UF_CODES = frozenset({
    "11", "12", "13", "14", "15", "16", "17", "21", "22", "23", "24",
    "25", "26", "27", "28", "29", "31", "32", "33", "35", "41", "42",
    "43", "50", "51", "52", "53",
})


def inspect_municipalities(records: Iterable[Municipality]) -> CatalogValidationReport:
    values = tuple(records)
    errors: list[str] = []
    try:
        validate_municipalities(values)
    except ValueError as error:
        errors.append(str(error))
    return CatalogValidationReport(
        valid=not errors,
        municipality_count=len(values),
        uf_count=len({item.uf_code for item in values}),
        code6_count=len({item.code6 for item in values}),
        errors=tuple(errors),
    )


def validate_municipalities(records: Iterable[Municipality]) -> tuple[Municipality, ...]:
    values = tuple(records)
    if not values:
        raise ValueError("catálogo municipal vazio")

    code7_counts = Counter(item.code7 for item in values)
    code6_counts = Counter(item.code6 for item in values)
    duplicate_code7 = sorted(code for code, count in code7_counts.items() if count > 1)
    duplicate_code6 = sorted(code for code, count in code6_counts.items() if count > 1)
    if duplicate_code7:
        raise ValueError(f"code7 duplicado no catálogo: {duplicate_code7}")
    if duplicate_code6:
        raise ValueError(f"code6 ambíguo no catálogo: {duplicate_code6}")

    uf_attributes: dict[str, tuple[str, str]] = {}
    for item in values:
        if not CODE7.fullmatch(item.code7) or not CODE6.fullmatch(item.code6):
            raise ValueError(f"código municipal inválido: {item.code7}/{item.code6}")
        if item.code7[:6] != item.code6:
            raise ValueError(f"crosswalk inconsistente: {item.code7}/{item.code6}")
        if item.uf_code != item.code7[:2] or len(item.uf_code) != 2:
            raise ValueError(f"UF inconsistente para {item.code7}")
        if not item.name.strip() or not item.uf_abbr.strip() or not item.uf_name.strip():
            raise ValueError(f"atributo obrigatório ausente para {item.code7}")
        attributes = (item.uf_abbr.strip().upper(), item.uf_name.strip())
        previous = uf_attributes.setdefault(item.uf_code, attributes)
        if previous != attributes:
            raise ValueError(f"identidade da UF inconsistente para {item.uf_code}")
    return values


def validate_national_municipalities(
    records: Iterable[Municipality],
) -> tuple[Municipality, ...]:
    """Valida uma candidata que será publicada como catálogo nacional.

    A validação estrutural comum aceita fixtures parciais. Os caminhos de
    atualização nacional precisam adicionalmente provar que a candidata cobre
    todas as 27 UFs; ausência de municípios específicos continua sendo tratada
    pela validação da fonte e pela reconciliação da edição oficial.
    """
    values = validate_municipalities(records)
    missing = sorted(NATIONAL_UF_CODES - {item.uf_code for item in values})
    if missing:
        raise ValueError(f"catálogo nacional incompleto; UFs ausentes: {missing}")
    return values
