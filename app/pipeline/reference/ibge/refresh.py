from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
import tempfile
from dataclasses import asdict, replace
from pathlib import Path

import requests

from .catalog import InMemoryMunicipalityCatalog
from .client import DEFAULT_MUNICIPALITIES_URL, IbgeLocalidadesClient
from .dtb import parse_dtb_archive
from .models import CatalogMetadata
from .storage import promote_active, write_manifest, write_release


def download_dtb_archive(
    root: Path,
    *,
    url: str,
    reference_year: int,
    expected_sha256: str | None = None,
    session: requests.Session | None = None,
    timeout: float = 120,
) -> Path:
    """Baixa uma DTB para o cache bruto, validando-a antes da promoção."""
    destination_dir = root / "raw" / f"dtb_{reference_year}"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"DTB_{reference_year}.zip"
    client = session or requests.Session()
    response = client.get(url, stream=True, timeout=timeout)
    response.raise_for_status()
    digest = hashlib.sha256()
    with tempfile.NamedTemporaryFile(
        dir=destination_dir, prefix=f".{destination.name}.", suffix=".tmp", delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        try:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    digest.update(chunk)
                    temporary.write(chunk)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
    actual_sha256 = digest.hexdigest()
    if expected_sha256 and actual_sha256 != expected_sha256:
        temporary_path.unlink(missing_ok=True)
        raise ValueError(
            f"SHA-256 da DTB diverge: esperado {expected_sha256}, obtido {actual_sha256}"
        )
    os.replace(temporary_path, destination)
    return destination


def refresh_from_dtb_url(
    root: Path,
    *,
    url: str,
    catalog_id: str,
    reference_year: int,
    expected_sha256: str | None = None,
    session: requests.Session | None = None,
) -> Path:
    """Baixa, valida e promove uma edição DTB em uma única operação controlada."""
    archive = download_dtb_archive(
        root, url=url, reference_year=reference_year,
        expected_sha256=expected_sha256, session=session,
    )
    return refresh_from_dtb_archive(
        root, archive, catalog_id=catalog_id, source_url=url,
        reference_year=reference_year,
    )


def _records_sha256(records) -> str:
    payload = json.dumps(
        [asdict(record) for record in sorted(records, key=lambda item: item.code7)],
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _reuse_immutable_release(release: Path, metadata: CatalogMetadata) -> Path | None:
    """Reutiliza uma release idêntica ou rejeita colisão de identidade."""
    if not release.exists():
        return None
    manifest_path = release / "manifest.json"
    catalog_path = release / "municipalities.parquet"
    if not manifest_path.exists() or not catalog_path.exists():
        raise ValueError(f"release incompleta não pode ser reutilizada: {release.name}")
    try:
        current = CatalogMetadata(**json.loads(manifest_path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"manifesto inválido na release existente: {release.name}") from exc
    if current.sha256 != metadata.sha256:
        raise ValueError(
            f"catalog_id imutável já associado a outro SHA-256: {metadata.catalog_id}"
        )
    return catalog_path


def refresh_from_localidades(
    root: Path,
    *,
    catalog_id: str,
    source_url: str,
    reference_year: int,
    client: IbgeLocalidadesClient | None = None,
) -> Path:
    records = tuple(
        replace(record, reference_year=reference_year)
        for record in (client or IbgeLocalidadesClient()).fetch_municipalities()
    )
    release = root / "releases" / catalog_id
    metadata = CatalogMetadata(
        catalog_id=catalog_id,
        reference_year=reference_year,
        source_name="IBGE - API de Localidades",
        source_url=source_url,
        retrieved_at=datetime.now(UTC).isoformat(),
        sha256=_records_sha256(records),
    )
    existing = _reuse_immutable_release(release, metadata)
    if existing is not None:
        promote_active(root / "active.json", catalog_id)
        return existing
    parquet = write_release(release, records)
    write_manifest(release / "manifest.json", metadata)
    promote_active(root / "active.json", catalog_id)
    return parquet


def refresh_from_dtb_archive(
    root: Path,
    archive: Path,
    *,
    catalog_id: str,
    source_url: str,
    reference_year: int,
) -> Path:
    records = parse_dtb_archive(archive, reference_year)
    release = root / "releases" / catalog_id
    sha256 = hashlib.sha256(archive.read_bytes()).hexdigest()
    metadata = CatalogMetadata(
        catalog_id=catalog_id,
        reference_year=reference_year,
        source_name="IBGE - Divisão Territorial Brasileira",
        source_url=source_url,
        retrieved_at=datetime.now(UTC).isoformat(),
        sha256=sha256,
    )
    existing = _reuse_immutable_release(release, metadata)
    if existing is not None:
        promote_active(root / "active.json", catalog_id)
        return existing
    parquet = write_release(release, records)
    write_manifest(release / "manifest.json", metadata)
    promote_active(root / "active.json", catalog_id)
    return parquet


def main() -> None:
    parser = argparse.ArgumentParser(description="Atualiza e promove uma release local do catálogo IBGE")
    parser.add_argument("--root", type=Path, required=True, help="Diretório do catálogo IBGE")
    parser.add_argument("--catalog-id", required=True, help="Identificador imutável da release")
    parser.add_argument("--reference-year", type=int, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--dtb-url", help="URL oficial do ZIP DTB")
    source.add_argument("--dtb-archive", type=Path, help="ZIP DTB já baixado")
    source.add_argument("--localidades", action="store_true", help="Usa a API de Localidades do IBGE")
    parser.add_argument("--source-url", help="URL de proveniência para um arquivo local")
    parser.add_argument("--expected-sha256", help="SHA-256 esperado do ZIP DTB")
    args = parser.parse_args()
    if args.dtb_archive is not None and not args.source_url:
        parser.error("--dtb-archive exige --source-url")
    if args.dtb_url:
        result = refresh_from_dtb_url(
            args.root, url=args.dtb_url, catalog_id=args.catalog_id,
            reference_year=args.reference_year, expected_sha256=args.expected_sha256,
        )
    elif args.dtb_archive is not None:
        result = refresh_from_dtb_archive(
            args.root, args.dtb_archive, catalog_id=args.catalog_id,
            source_url=args.source_url, reference_year=args.reference_year,
        )
    else:
        result = refresh_from_localidades(
            args.root, catalog_id=args.catalog_id,
            source_url=args.source_url or DEFAULT_MUNICIPALITIES_URL,
            reference_year=args.reference_year,
        )
    print(result)


if __name__ == "__main__":
    main()
