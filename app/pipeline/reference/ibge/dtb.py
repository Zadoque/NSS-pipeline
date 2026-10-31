from __future__ import annotations

import csv
import io
import tempfile
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from .models import Municipality
from .validation import validate_municipalities

UF_ABBR = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP",
    "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB",
    "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
    "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
    "51": "MT", "52": "GO", "53": "DF",
}


def _read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        raw = path.read_bytes()
        for encoding in ("utf-8-sig", "cp1252", "latin1"):
            try:
                return pd.read_csv(io.BytesIO(raw), sep=None, engine="python", skiprows=6, encoding=encoding, dtype=str)
            except UnicodeDecodeError:
                continue
        raise ValueError(f"não foi possível decodificar a DTB: {path}")
    if suffix in {".xls", ".xlsx", ".ods"}:
        return pd.read_excel(path, header=6, dtype=str)
    raise ValueError(f"formato DTB não suportado: {path.suffix}")


def _find_column(frame: pd.DataFrame, *names: str) -> str:
    normalized = {str(column).strip().casefold(): column for column in frame.columns}
    for name in names:
        if name.casefold() in normalized:
            return normalized[name.casefold()]
    raise ValueError(f"coluna DTB não encontrada; esperadas: {names}")


def parse_dtb_table(path: Path, reference_year: int) -> tuple[Municipality, ...]:
    frame = _read_table(path)
    try:
        uf_code = _find_column(frame, "UF")
    except ValueError:
        # As edições legadas de 2011–2019 não possuem as seis linhas
        # institucionais usadas pelas DTBs recentes; a tabela começa na
        # primeira linha da planilha.
        if path.suffix.lower() not in {".xls", ".xlsx", ".ods"}:
            raise
        frame = pd.read_excel(path, header=0, dtype=str)
        uf_code = _find_column(frame, "UF")
    uf_name = _find_column(frame, "Nome_UF", "Nome UF")
    code7 = _find_column(
        frame, "Código Município Completo", "Codigo Municipio Completo",
        "Município", "Municipio", "Munic",
    )
    name = _find_column(
        frame, "Nome_Município", "Nome Municipio", "Nome_Munic",
    )
    records = []
    for index, row in enumerate(frame.to_dict(orient="records"), start=7):
        raw_code = row[code7]
        raw_uf = row[uf_code]
        if pd.isna(raw_code) or not str(raw_code).strip():
            continue
        code = "".join(str(raw_code).split())
        uf = "".join(str(raw_uf).split()).zfill(2) if not pd.isna(raw_uf) else ""
        if len(code) == 5 and len(uf) == 2 and uf.isdigit():
            code = uf + code
        if len(code) != 7 or not code.isdigit():
            raise ValueError(f"geocódigo municipal inválido na linha {index}: {raw_code!r}")
        if uf not in UF_ABBR:
            raise ValueError(f"UF inválida na linha {index}: {raw_uf!r}")
        records.append(Municipality(
            code7=code,
            code6=code[:6],
            name=str(row[name]).strip(),
            uf_code=uf,
            uf_abbr=UF_ABBR[uf],
            uf_name=str(row[uf_name]).strip(),
            reference_year=reference_year,
            source="IBGE_DTB",
            administrative_type="FEDERAL_DISTRICT" if uf == "53" else "MUNICIPALITY",
        ))
    # Algumas edições legadas repetem o município uma vez por distrito ou
    # subdistrito. Repetições idênticas são colapsadas; registros com o mesmo
    # código e atributos divergentes continuam sendo rejeitados pela validação.
    unique_by_code: dict[str, Municipality] = {}
    for record in records:
        previous = unique_by_code.get(record.code7)
        if previous is not None and previous != record:
            raise ValueError(f"registros conflitantes para o código municipal: {record.code7}")
        unique_by_code[record.code7] = record
    return validate_municipalities(tuple(unique_by_code.values()))


def parse_dtb_archive(path: Path, reference_year: int) -> tuple[Municipality, ...]:
    with ZipFile(path) as archive, tempfile.TemporaryDirectory(prefix="dtb-") as directory:
        candidates = [
            name for name in archive.namelist()
            if "MUNICIP" in name.upper()
            and name.lower().endswith((".xls", ".xlsx", ".ods", ".csv"))
        ]
        if not candidates:
            candidates = [
                name for name in archive.namelist()
                if name.lower().endswith((".xls", ".xlsx", ".ods", ".csv"))
            ]
        if not candidates:
            raise ValueError("arquivo DTB não contém tabela de municípios")
        candidate = next((name for name in candidates if name.lower().endswith(".xls")), candidates[0])
        extracted = Path(archive.extract(candidate, directory))
        return parse_dtb_table(extracted, reference_year)
