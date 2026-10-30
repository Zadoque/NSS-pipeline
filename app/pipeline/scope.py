from __future__ import annotations

from dataclasses import dataclass

from .reference.ibge.models import Municipality, MunicipalityCatalog, ResolutionStatus

LEGACY_RJ_CODES = (
    "3301009",  # Campos dos Goytacazes
    "3305000",  # São João da Barra
    "3302205",  # Itaperuna
    "3302403",  # Macaé
)


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
    for value in municipalities or ():
        result = catalog.resolve(value)
        if result.status is not ResolutionStatus.VALID or result.municipality is None:
            raise ValueError(f"município inválido no escopo: {value} ({result.status})")
        selected.append(result.municipality)
    if not selected:
        raise ValueError("o escopo municipal não pode ser vazio")
    return GeographicScope(tuple(selected))
