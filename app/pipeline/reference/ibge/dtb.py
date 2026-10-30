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
    uf_code = _find_column(frame, "UF")
    uf_name = _find_column(frame, "Nome_UF", "Nome UF")
    code7 = _find_column(frame, "Código Município Completo", "Codigo Municipio Completo")
    name = _find_column(frame, "Nome_Município", "Nome Municipio")
    records = []
    for row in frame.to_dict(orient="records"):
        code = "".join(str(row[code7]).split())
        uf = "".join(str(row[uf_code]).split()).zfill(2)
        if len(code) != 7 or not code.isdigit() or uf not in UF_ABBR:
            continue
        records.append(Municipality(
            code7=code,
            code6=code[:6],
            name=str(row[name]).strip(),
            uf_code=uf,
            uf_abbr=UF_ABBR[uf],
            uf_name=str(row[uf_name]).strip(),
            reference_year=reference_year,
            source="IBGE_DTB",
        ))
    return validate_municipalities(records)


def parse_dtb_archive(path: Path, reference_year: int) -> tuple[Municipality, ...]:
    with ZipFile(path) as archive, tempfile.TemporaryDirectory(prefix="dtb-") as directory:
        candidates = [name for name in archive.namelist() if "MUNICIPIOS" in name.upper() and name.lower().endswith((".xls", ".xlsx", ".ods", ".csv"))]
        if not candidates:
            raise ValueError("arquivo DTB não contém tabela de municípios")
        candidate = next((name for name in candidates if name.lower().endswith(".xls")), candidates[0])
        extracted = Path(archive.extract(candidate, directory))
        return parse_dtb_table(extracted, reference_year)
