"""Unit tests for pinned Mendeley Bronze ingestion (no network; mocked httpx)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx
import pytest

from cleanpulse.bronze.mendeley_client import (
    PINNED_DATASETS,
    MendeleyIngestionError,
    PinnedDatasetSpec,
    PinnedFileSpec,
    ingest_mendeley_dataset,
)


def test_ingest_mendeley_verifies_hashes_and_excludes_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"Date,effected\n01-01-22,5\n"
    payload_sha = hashlib.sha256(payload).hexdigest()
    test_spec = PinnedDatasetSpec(
        key="A",
        dataset_id="z5mvwrfgsz",
        version=1,
        doi="10.17632/z5mvwrfgsz.1",
        licence="CC BY 4.0",
        files=(PinnedFileSpec("Dhaka.csv", payload_sha),),
    )
    monkeypatch.setitem(PINNED_DATASETS, "A", test_spec)

    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if "public-api/datasets" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "files": [
                        {
                            "filename": "Dhaka.csv",
                            "content_details": {
                                "download_url": "https://data.mendeley.com/files/dhaka",
                                "sha256": payload_sha,
                            },
                        },
                        {
                            "filename": "Transaction receipt.pdf",
                            "content_details": {
                                "download_url": "https://data.mendeley.com/files/receipt",
                                "sha256": "deadbeef",
                            },
                        },
                    ]
                },
            )
        if str(request.url) == "https://data.mendeley.com/files/dhaka":
            return httpx.Response(200, content=payload)
        raise AssertionError(f"Unexpected URL requested: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    written = ingest_mendeley_dataset("A", bronze_root=tmp_path, client=client)

    assert len(written) == 1
    assert written[0].name == "Dhaka.csv"
    assert written[0].read_bytes() == payload
    assert not any("receipt" in u for u in requested_urls)

    sidecar = json.loads((written[0].with_suffix(".json")).read_text(encoding="utf-8"))
    assert sidecar["doi"] == "10.17632/z5mvwrfgsz.1"
    assert sidecar["version"] == 1
    assert sidecar["licence"] == "CC BY 4.0"
    assert sidecar["sha256"] == payload_sha
    assert sidecar["mendeley_sha256"] == payload_sha
    assert "fetched_at_utc" in sidecar
    assert "git_commit" in sidecar
    assert "git_dirty" in sidecar


def test_ingest_mendeley_fails_loudly_on_hash_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected_sha = hashlib.sha256(b"expected").hexdigest()
    test_spec = PinnedDatasetSpec(
        key="B",
        dataset_id="cgwjshkx5k",
        version=2,
        doi="10.17632/cgwjshkx5k.2",
        licence="CC BY 4.0",
        files=(PinnedFileSpec("dataset.xlsx", expected_sha),),
    )
    monkeypatch.setitem(PINNED_DATASETS, "B", test_spec)

    def handler(request: httpx.Request) -> httpx.Response:
        if "public-api/datasets" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "files": [
                        {
                            "filename": "dataset.xlsx",
                            "content_details": {
                                "download_url": "https://data.mendeley.com/files/xlsx",
                                "sha256": expected_sha,
                            },
                        }
                    ]
                },
            )
        return httpx.Response(200, content=b"corrupted-bytes")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(MendeleyIngestionError, match="Downloaded SHA-256 mismatch"):
        ingest_mendeley_dataset("B", bronze_root=tmp_path, client=client)
    assert not (tmp_path / "B" / "v2" / "dataset.xlsx").exists()
