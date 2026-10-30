from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

from .models import Municipality

CODE7 = re.compile(r"^[0-9]{7}$")
CODE6 = re.compile(r"^[0-9]{6}$")


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

    for item in values:
        if not CODE7.fullmatch(item.code7) or not CODE6.fullmatch(item.code6):
            raise ValueError(f"código municipal inválido: {item.code7}/{item.code6}")
        if item.code7[:6] != item.code6:
            raise ValueError(f"crosswalk inconsistente: {item.code7}/{item.code6}")
        if item.uf_code != item.code7[:2] or len(item.uf_code) != 2:
            raise ValueError(f"UF inconsistente para {item.code7}")
        if not item.name.strip() or not item.uf_abbr.strip() or not item.uf_name.strip():
            raise ValueError(f"atributo obrigatório ausente para {item.code7}")
    return values
