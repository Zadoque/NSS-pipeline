from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .reference.ibge.models import Municipality, MunicipalityCatalog, ResolutionStatus

LEGACY_RJ_CODES = (
    "3301009",  # Campos dos Goytacazes
    "3305000",  # São João da Barra
    "3302205",  # Itaperuna
    "3302403",  # Macaé
)

LEGACY_RJ_MAPPING = {
    "3301009": "Campos dos Goytacazes",
    "3305000": "São João da Barra",
    "3302205": "Itaperuna",
    "3302403": "Macaé",
}


def legacy_rj_mapping() -> dict[str, str]:
    """Retorna uma cópia do recorte legado, sem expor estado mutável global."""
    return dict(LEGACY_RJ_MAPPING)


@dataclass(frozen=True)
class GeographicScope:
    municipalities: tuple[Municipality, ...]
    kind: str = "MUNICIPALITIES"

    @property
    def codes7(self) -> frozenset[str]:
        return frozenset(item.code7 for item in self.municipalities)

    @property
    def count(self) -> int:
        return len(self.municipalities)

    @property
    def sha256(self) -> str:
        return scope_sha256(self.codes7)


def validate_scope_catalog(catalog: MunicipalityCatalog, scope: GeographicScope) -> None:
    """Garante que o escopo foi materializado pela mesma identidade do catálogo."""
    for selected in scope.municipalities:
        canonical = catalog.get_municipality(selected.code7)
        if canonical is None or canonical != selected:
            raise ValueError(
                "escopo geográfico não corresponde ao catálogo IBGE: "
                f"{selected.code7}"
            )


def scope_sha256(codes: object) -> str:
    """Calcula um identificador estável para o conjunto municipal selecionado."""
    values = sorted({str(code) for code in codes})
    if not values or any(
        len(code) != 7 or not code.isascii() or not code.isdigit()
        for code in values
    ):
        raise ValueError("escopo deve conter códigos municipais IBGE de 7 dígitos")
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def legacy_rj_scope(catalog: MunicipalityCatalog) -> GeographicScope:
    selected = []
    for code in LEGACY_RJ_CODES:
        municipality = catalog.get_municipality(code)
        if municipality is None:
            raise ValueError(f"município legado ausente no catálogo: {code}")
        selected.append(municipality)
    return GeographicScope(tuple(selected))


def select_scope(
    catalog: MunicipalityCatalog,
    *,
    municipalities: list[str] | tuple[str, ...] | None = None,
    ufs: list[str] | tuple[str, ...] | None = None,
    all_brazil: bool = False,
) -> GeographicScope:
    options = sum(value is not None for value in (municipalities, ufs)) + int(all_brazil)
    if options > 1:
        raise ValueError("selecione apenas uma entre municípios, UFs ou Brasil inteiro")
    if options == 0:
        return legacy_rj_scope(catalog)
    if all_brazil:
        return GeographicScope(catalog.municipalities(), kind="BRAZIL")
    if ufs is not None:
        wanted = {str(value).strip().upper() for value in ufs}
        selected = tuple(
            item for item in catalog.municipalities()
            if item.uf_code in wanted or item.uf_abbr.upper() in wanted
        )
        if not selected:
            raise ValueError("nenhuma UF selecionada existe no catálogo")
        return GeographicScope(selected, kind="UFs")

    selected = []
    seen: set[str] = set()
    for value in municipalities or ():
        result = catalog.resolve(value)
        if result.status is not ResolutionStatus.VALID or result.municipality is None:
            raise ValueError(f"município inválido no escopo: {value} ({result.status})")
        if result.municipality.code7 in seen:
            raise ValueError(f"município duplicado no escopo: {result.municipality.code7}")
        seen.add(result.municipality.code7)
        selected.append(result.municipality)
    if not selected:
        raise ValueError("o escopo municipal não pode ser vazio")
    return GeographicScope(tuple(selected))
