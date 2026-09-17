from __future__ import annotations

import requests
import pandas as pd

API_BASE = "https://apidadosabertos.saude.gov.br/cnes/estabelecimentos"

def fetch_estabelecimentos(codigo_municipio_7: str, limit: int = 100) -> pd.DataFrame:
    codigo_municipio_6 = codigo_municipio_7[:6]
    registros = []
    offset = 0

    while True:
        resp = requests.get(
            API_BASE,
            params={"codigo_municipio": codigo_municipio_6, "limit": limit, "offset": offset},
            timeout=30,
        )
        resp.raise_for_status()
        pagina = resp.json().get("estabelecimentos", [])
        if not pagina:
            break
        registros.extend(pagina)
        offset += limit

        print(registros)

    return pd.DataFrame(registros)

if __name__ == "__main__":
    fetch_estabelecimentos("330100")