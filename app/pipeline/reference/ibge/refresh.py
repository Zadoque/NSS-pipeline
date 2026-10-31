from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import asdict, replace
from pathlib import Path

import requests

from .catalog import InMemoryMunicipalityCatalog
from .client import DEFAULT_MUNICIPALITIES_URL, IbgeLocalidadesClient
from .dtb import parse_dtb_archive
from .models import CatalogMetadata
from .storage import catalog_content_sha256, promote_active, write_manifest, write_release
from .validation import validate_national_municipalities


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
    owns_session = session is None
    response = None
    temporary_path: Path | None = None
    try:
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
        try:
            if expected_sha256 and actual_sha256 != expected_sha256:
                raise ValueError(
                    f"SHA-256 da DTB diverge: esperado {expected_sha256}, obtido {actual_sha256}"
                )
            os.replace(temporary_path, destination)
            return destination
        finally:
            temporary_path.unlink(missing_ok=True)
    finally:
        if response is not None:
            response.close()
        if owns_session:
            client.close()


def refresh_from_dtb_url(
    root: Path,
    *,
    url: str,
    catalog_id: str,
    reference_year: int,
    expected_sha256: str | None = None,
    session: requests.Session | None = None,
    timeout: float = 120,
    require_national: bool = True,
) -> Path:
    """Baixa, valida e promove uma edição DTB em uma única operação controlada."""
    archive = download_dtb_archive(
        root, url=url, reference_year=reference_year,
        expected_sha256=expected_sha256, session=session, timeout=timeout,
    )
    return refresh_from_dtb_archive(
        root, archive, catalog_id=catalog_id, source_url=url,
        reference_year=reference_year, require_national=require_national,
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
    if current.catalog_id != metadata.catalog_id:
        raise ValueError(
            f"catalog_id divergente no manifesto existente: {metadata.catalog_id}"
        )
    if current.validation_status != "VALIDATED":
        raise ValueError(f"release existente não está validada: {metadata.catalog_id}")
    if current.sha256 != metadata.sha256:
        raise ValueError(
            f"catalog_id imutável já associado a outro SHA-256: {metadata.catalog_id}"
        )
    if current.content_sha256 != metadata.content_sha256:
        raise ValueError(
            f"catalog_id imutável já associado a outro hash lógico: {metadata.catalog_id}"
        )
    return catalog_path


def _release_path(root: Path, catalog_id: str) -> Path:
    if not catalog_id or catalog_id in {".", ".."} or Path(catalog_id).name != catalog_id:
        raise ValueError("catalog_id inválido para uma release local")
    return root / "releases" / catalog_id


def _write_release_atomically(
    root: Path,
    catalog_id: str,
    records,
    metadata: CatalogMetadata,
) -> Path:
    """Materializa catálogo e manifesto juntos antes de trocar a release."""
    release = _release_path(root, catalog_id)
    release.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{catalog_id}.", dir=release.parent))
    try:
        write_release(staging, records)
        write_manifest(staging / "manifest.json", metadata)
        os.replace(staging, release)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return release / "municipalities.parquet"


def refresh_from_localidades(
    root: Path,
    *,
    catalog_id: str,
    source_url: str,
    reference_year: int,
    client: IbgeLocalidadesClient | None = None,
    require_national: bool = True,
) -> Path:
    release = _release_path(root, catalog_id)
    localidades_client = client or IbgeLocalidadesClient()
    try:
        records = tuple(
            replace(record, reference_year=reference_year)
            for record in localidades_client.fetch_municipalities()
        )
    finally:
        if client is None:
            localidades_client.close()
    if require_national:
        records = validate_national_municipalities(records)
    metadata = CatalogMetadata(
        catalog_id=catalog_id,
        reference_year=reference_year,
        source_name="IBGE - API de Localidades",
        source_url=source_url,
        retrieved_at=datetime.now(UTC).isoformat(),
        sha256=_records_sha256(records),
        content_sha256=catalog_content_sha256(records),
    )
    existing = _reuse_immutable_release(release, metadata)
    if existing is not None:
        promote_active(root / "active.json", catalog_id)
        return existing
    parquet = _write_release_atomically(root, catalog_id, records, metadata)
    promote_active(root / "active.json", catalog_id)
    return parquet


def refresh_from_dtb_archive(
    root: Path,
    archive: Path,
    *,
    catalog_id: str,
    source_url: str,
    reference_year: int,
    require_national: bool = True,
) -> Path:
    release = _release_path(root, catalog_id)
    records = parse_dtb_archive(archive, reference_year)
    if require_national:
        records = validate_national_municipalities(records)
    sha256 = hashlib.sha256(archive.read_bytes()).hexdigest()
    metadata = CatalogMetadata(
        catalog_id=catalog_id,
        reference_year=reference_year,
        source_name="IBGE - Divisão Territorial Brasileira",
        source_url=source_url,
        retrieved_at=datetime.now(UTC).isoformat(),
        sha256=sha256,
        content_sha256=catalog_content_sha256(records),
    )
    existing = _reuse_immutable_release(release, metadata)
    if existing is not None:
        promote_active(root / "active.json", catalog_id)
        return existing
    parquet = _write_release_atomically(root, catalog_id, records, metadata)
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
    parser.add_argument("--timeout", type=float, default=120, help="Timeout HTTP em segundos")
    args = parser.parse_args()
    if args.dtb_archive is not None and not args.source_url:
        parser.error("--dtb-archive exige --source-url")
    if args.dtb_url:
        result = refresh_from_dtb_url(
            args.root, url=args.dtb_url, catalog_id=args.catalog_id,
            reference_year=args.reference_year, expected_sha256=args.expected_sha256,
            timeout=args.timeout,
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
