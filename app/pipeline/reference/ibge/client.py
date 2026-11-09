from __future__ import annotations

from collections.abc import Callable

import requests

from .models import Municipality
from .validation import validate_municipalities

DEFAULT_MUNICIPALITIES_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"


class IbgeLocalidadesClient:
    def __init__(self, session: requests.Session | None = None, base_url: str = DEFAULT_MUNICIPALITIES_URL):
        self.session = session or requests.Session()
        self._owns_session = session is None
        self.base_url = base_url.rstrip("/")

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def fetch_municipalities(self, *, timeout: float = 60) -> tuple[Municipality, ...]:
        response = self.session.get(self.base_url, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("resposta IBGE inválida: esperado um array de municípios")
        records = [self._parse(item) for item in payload]
        return validate_municipalities(records)

    @staticmethod
    def _parse(item: object) -> Municipality:
        if not isinstance(item, dict):
            raise ValueError("registro IBGE inválido")
        try:
            microregion = item.get("microrregiao")
            if microregion is not None:
                uf = microregion["mesorregiao"]["UF"]
            else:
                # Municípios recém-criados podem ainda não possuir
                # microrregião na API; a mesma UF está disponível na
                # hierarquia de região imediata/intermediária.
                uf = item["regiao-imediata"]["regiao-intermediaria"]["UF"]
            return Municipality(
                code7=str(item["id"]),
                code6=str(item["id"])[:6],
                name=str(item["nome"]),
                uf_code=str(uf["id"]),
                uf_abbr=str(uf["sigla"]),
                uf_name=str(uf["nome"]),
                reference_year=0,
                source="IBGE_API_LOCALIDADES",
            )
        except (KeyError, TypeError) as error:
            raise ValueError("registro IBGE sem campos administrativos obrigatórios") from error
