"""Pinned Mendeley Data Bronze Ingestion Client.

Downloads allowlisted files for pinned Mendeley dataset versions, verifies each
file's SHA-256 against both Mendeley's published metadata hash and a hash pinned
in code, and stores raw bytes immutably with JSON provenance sidecars.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from cleanpulse.bronze.provenance import write_immutable_with_sidecar

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_BRONZE_MENDELEY_DIR = REPO_ROOT / "data" / "bronze" / "mendeley"
MENDELEY_API_BASE = "https://data.mendeley.com/public-api/datasets"


class MendeleyIngestionError(RuntimeError):
    """Raised when Mendeley dataset metadata or file verification fails."""


@dataclass(frozen=True)
class PinnedFileSpec:
    """Pinned filename and expected SHA-256 hex digest."""

    filename: str
    sha256: str


@dataclass(frozen=True)
class PinnedDatasetSpec:
    """Pinned Mendeley dataset version and explicit file allowlist."""

    key: str
    dataset_id: str
    version: int
    doi: str
    licence: str
    files: tuple[PinnedFileSpec, ...]


PINNED_DATASETS: dict[str, PinnedDatasetSpec] = {
    "A": PinnedDatasetSpec(
        key="A",
        dataset_id="z5mvwrfgsz",
        version=1,
        doi="10.17632/z5mvwrfgsz.1",
        licence="CC BY 4.0",
        # Explicit allowlist excludes 'Transaction receipt.pdf'.
        files=(
            PinnedFileSpec(
                "Barisal.csv",
                "d68191e734865ee91980c53dc4cb033287efb117726c69ce9b5544e22c03e2ef",
            ),
            PinnedFileSpec(
                "Chittagong.csv",
                "5f199d714b1ce1dd3c51f610589ac0c3f2a852956fbcd19c91b54e93871c9f76",
            ),
            PinnedFileSpec(
                "Dhaka.csv",
                "94807b29259a5dbe3860bc0f660716207fb7e5f0bd52de950f7646f586b24890",
            ),
            PinnedFileSpec(
                "khulna.csv",
                "78add3e329e9a6506c7cc4b0b0c54fe9b84c2d039bdf77046950cc96ce886a37",
            ),
            PinnedFileSpec(
                "Mymensingh.csv",
                "b84259d4bfb9b072c133bf7a664fa1cae11898c93e6a4d856882dfca2804a3bc",
            ),
            PinnedFileSpec(
                "Rajshahi.csv",
                "309200a849c6e6ded4a1263bc61c1ae4d3d67cf175a0c3c792a117f4bafa0d6e",
            ),
            PinnedFileSpec(
                "Rangpur.csv",
                "6a7efdef3d86a82c6375c312d003a07987b7fe37ecbaff21bc55eaa80d9d841d",
            ),
            PinnedFileSpec(
                "Sylhet.csv",
                "b9791cd2315c63738f3cbbf963ea16528d1f204290dacc5a02c6835ed4f0eb1c",
            ),
        ),
    ),
    "B": PinnedDatasetSpec(
        key="B",
        dataset_id="cgwjshkx5k",
        version=2,
        doi="10.17632/cgwjshkx5k.2",
        licence="CC BY 4.0",
        files=(
            PinnedFileSpec(
                "dataset.xlsx",
                "6c59b315619c828f3eb8ca96f396c4af6e93c01ab5007f3e1976bd360f2594a6",
            ),
        ),
    ),
}


def _extract_file_entry(files_payload: list[dict[str, Any]], filename: str) -> tuple[str, str]:
    """Return (download_url, mendeley_sha256) for an allowlisted filename."""
    for entry in files_payload:
        if entry.get("filename") != filename:
            continue
        content_details = entry.get("content_details") or {}
        download_url = str(content_details.get("download_url") or entry.get("download_url") or "")
        mendeley_sha256 = str(
            content_details.get("sha256_hash")
            or content_details.get("sha256")
            or entry.get("sha256_hash")
            or entry.get("sha256")
            or ""
        ).lower()
        if not download_url or not mendeley_sha256:
            raise MendeleyIngestionError(
                f"Missing download_url or sha256 in Mendeley metadata for {filename}"
            )
        return download_url, mendeley_sha256
    raise MendeleyIngestionError(
        f"Allowlisted file {filename!r} not found in Mendeley dataset metadata"
    )


def ingest_mendeley_dataset(
    dataset_key: str,
    bronze_root: Path | None = None,
    client: httpx.Client | None = None,
) -> list[Path]:
    """Download and verify allowlisted files for pinned Mendeley dataset A or B."""
    if dataset_key not in PINNED_DATASETS:
        raise ValueError(
            f"Unknown dataset key {dataset_key!r}; expected one of {sorted(PINNED_DATASETS)}"
        )

    spec = PINNED_DATASETS[dataset_key]
    target_dir = (bronze_root or DEFAULT_BRONZE_MENDELEY_DIR) / spec.key / f"v{spec.version}"
    meta_url = f"{MENDELEY_API_BASE}/{spec.dataset_id}/files?folder_id=root&version={spec.version}"

    owns_client = client is None
    http = client or httpx.Client(timeout=60.0, follow_redirects=True)
    written_paths: list[Path] = []

    try:
        meta_resp = http.get(meta_url)
        meta_resp.raise_for_status()
        meta_json = meta_resp.json()
        files_payload = meta_json.get("files") if isinstance(meta_json, dict) else meta_json
        if not isinstance(files_payload, list):
            raise MendeleyIngestionError(f"Unexpected Mendeley metadata format at {meta_url}")

        for file_spec in spec.files:
            download_url, mendeley_sha256 = _extract_file_entry(files_payload, file_spec.filename)
            if mendeley_sha256 != file_spec.sha256:
                raise MendeleyIngestionError(
                    f"Mendeley metadata hash mismatch for {file_spec.filename}: "
                    f"expected {file_spec.sha256}, got {mendeley_sha256}"
                )

            file_resp = http.get(download_url)
            file_resp.raise_for_status()
            raw_bytes = file_resp.content
            actual_sha256 = hashlib.sha256(raw_bytes).hexdigest()
            if actual_sha256 != file_spec.sha256:
                raise MendeleyIngestionError(
                    f"Downloaded SHA-256 mismatch for {file_spec.filename}: "
                    f"expected {file_spec.sha256}, got {actual_sha256}"
                )

            target_path = target_dir / file_spec.filename
            sidecar_meta: dict[str, Any] = {
                "url": download_url,
                "metadata_url": meta_url,
                "doi": spec.doi,
                "dataset_id": spec.dataset_id,
                "version": spec.version,
                "licence": spec.licence,
                "mendeley_sha256": mendeley_sha256,
                "pinned_sha256": file_spec.sha256,
                "http_status": file_resp.status_code,
                "fetched_at_utc": datetime.now(UTC).isoformat(),
                "fetch_source": "mendeley_public_api",
            }
            raw_path, _ = write_immutable_with_sidecar(
                raw_bytes=raw_bytes,
                target_path=target_path,
                sidecar_metadata=sidecar_meta,
            )
            written_paths.append(raw_path)
            logger.info("Ingested Mendeley %s v%d: %s", spec.key, spec.version, raw_path)
    finally:
        if owns_client:
            http.close()

    return written_paths
