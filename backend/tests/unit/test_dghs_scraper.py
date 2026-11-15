"""Unit tests for the DGHS Bronze Layer scraper and immutable raw snapshot ingestion."""

import hashlib
import json
import time
from pathlib import Path

import httpx
import pytest

from cleanpulse.bronze.dghs_scraper import (
    DEFAULT_FIXTURE_PATH,
    DGHSBronzeScraper,
    DGHSFetchError,
    DGHSParseError,
)
from cleanpulse.bronze.provenance import REPO_DATA_DIR


@pytest.fixture
def scraper() -> DGHSBronzeScraper:
    """Fixture providing an offline-configured DGHSBronzeScraper."""
    return DGHSBronzeScraper(offline_mode=True, fixture_path=DEFAULT_FIXTURE_PATH)


def test_fixture_exists_and_readable() -> None:
    """Verify that the synthetic HTML fixture exists and carries the synthetic header."""
    assert DEFAULT_FIXTURE_PATH.exists(), f"Fixture missing at {DEFAULT_FIXTURE_PATH}"
    assert DEFAULT_FIXTURE_PATH.name == "synthetic_dghs_fault_injection.html"
    content = DEFAULT_FIXTURE_PATH.read_text(encoding="utf-8")
    assert "SYNTHETIC TEST FIXTURE" in content
    assert "zone_distribution_table" in content
    assert "age_distribution_table" in content


def test_scraper_extracts_all_10_zones(scraper: DGHSBronzeScraper) -> None:
    """Verify that all 10 official reporting zones are extracted from the synthetic fixture."""
    raw_bytes, provenance = scraper.fetch_raw(force_offline=True)
    assert provenance["fetch_source"] == "synthetic_fixture"
    source_hash = scraper.compute_sha256(raw_bytes)
    assert len(source_hash) == 64

    data = scraper.parse_dashboard(
        raw_bytes.decode("utf-8"),
        source_hash=source_hash,
        fetch_source=str(provenance["fetch_source"]),
    )
    zones = data["zones"]

    expected_zones = [
        "Chattogram",
        "DSCC",
        "Barishal",
        "Dhaka (Out of CC)",
        "DNCC",
        "Khulna",
        "Rajshahi",
        "Mymensingh",
        "Rangpur",
        "Sylhet",
    ]

    extracted_zone_names = [z["zone_name"] for z in zones]
    assert extracted_zone_names == expected_zones

    dscc = next(z for z in zones if z["zone_name"] == "DSCC")
    assert dscc["daily_admitted"] == "320"
    assert dscc["daily_deaths"] == "3"
    assert dscc["total_admitted"] == "18,910"
    assert dscc["total_deaths"] == "112"


def test_scraper_preserves_corrupted_age_buckets_verbatim(scraper: DGHSBronzeScraper) -> None:
    """Verify that injected faults in the synthetic fixture are preserved verbatim."""
    raw_bytes, provenance = scraper.fetch_raw(force_offline=True)
    data = scraper.parse_dashboard(
        raw_bytes.decode("utf-8"),
        source_hash=scraper.compute_sha256(raw_bytes),
        fetch_source=str(provenance["fetch_source"]),
    )
    age_groups = data["age_groups"]

    row_42309 = next((r for r in age_groups if r["age_group"] == "42309"), None)
    assert row_42309 is not None
    assert row_42309["male"] == "44"
    assert row_42309["female"] == "19"
    assert row_42309["total"] == "63"

    row_46301 = next((r for r in age_groups if r["age_group"] == "46301"), None)
    assert row_46301 is not None
    assert row_46301["total"] == "67"

    assert any(r["age_group"] == "6-10" and r["total"] == "1" for r in age_groups)
    assert any(r["age_group"] == "06-10" and r["total"] == "5316" for r in age_groups)
    assert any(r["age_group"] == "0-10" and r["total"] == "1" for r in age_groups)
    assert any(r["age_group"] == "" and r["total"] == "7" for r in age_groups)

    row_mismatch = next((r for r in age_groups if r["age_group"] == "21-25"), None)
    assert row_mismatch is not None
    assert row_mismatch["male"] == "3005"
    assert row_mismatch["female"] == "2375"
    assert row_mismatch["total"] == "5390"


def test_save_raw_bronze_creates_immutable_html_and_sidecar(
    scraper: DGHSBronzeScraper,
    tmp_path: Path,
) -> None:
    """Verify immutable HTML + provenance sidecar creation and overwrite refusal."""
    data, html_path = scraper.run_pipeline(force_offline=True, output_dir=tmp_path)
    assert html_path.exists()
    assert html_path.suffix == ".html"

    sidecar_path = html_path.with_suffix(".json")
    assert sidecar_path.exists()

    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    raw_bytes = html_path.read_bytes()
    assert sidecar["sha256"] == hashlib.sha256(raw_bytes).hexdigest()
    assert sidecar["fetch_source"] == "synthetic_fixture"
    assert "fetched_at_utc" in sidecar
    assert "git_commit" in sidecar
    assert "git_dirty" in sidecar
    assert data["metadata"]["fetch_source"] == "synthetic_fixture"

    # Refuses to overwrite an existing bronze file
    with pytest.raises(FileExistsError):
        from cleanpulse.bronze.provenance import write_immutable_with_sidecar

        write_immutable_with_sidecar(raw_bytes, html_path, sidecar)


def test_offline_refuses_writing_into_repo_data(scraper: DGHSBronzeScraper) -> None:
    """Verify that synthetic_fixture outputs cannot be written inside data/."""
    with pytest.raises(ValueError, match="Refusing to write offline/synthetic output"):
        scraper.run_pipeline(force_offline=True, output_dir=REPO_DATA_DIR / "bronze" / "dghs")


def test_fail_loud_on_404_without_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify HTTP 404 raises DGHSFetchError immediately without retrying."""
    calls = 0

    def mock_get(self: httpx.Client, url: str, **kwargs: object) -> httpx.Response:
        nonlocal calls
        calls += 1
        req = httpx.Request("GET", url)
        return httpx.Response(404, request=req, text="Not Found")

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    online_scraper = DGHSBronzeScraper(max_retries=3, backoff_factor=2.0, offline_mode=False)
    with pytest.raises(DGHSFetchError, match="404"):
        online_scraper.run_pipeline(output_dir=tmp_path)
    assert calls == 1


def test_fail_loud_on_timeout_after_retries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify timeout retries max_retries times and raises DGHSFetchError."""
    calls = 0

    def mock_get(self: httpx.Client, url: str, **kwargs: object) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectTimeout("Connection timed out to DGHS")

    monkeypatch.setattr(httpx.Client, "get", mock_get)
    monkeypatch.setattr(time, "sleep", lambda _s: None)

    online_scraper = DGHSBronzeScraper(max_retries=3, backoff_factor=2.0, offline_mode=False)
    with pytest.raises(DGHSFetchError, match="exhausted 3 retries"):
        online_scraper.run_pipeline(output_dir=tmp_path)
    assert calls == 3


def test_fail_loud_on_zero_rows_parsed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify HTML with 0 zones / 0 age groups raises DGHSParseError."""

    def mock_get(self: httpx.Client, url: str, **kwargs: object) -> httpx.Response:
        req = httpx.Request("GET", url)
        return httpx.Response(200, request=req, text="<html><body><h1>Empty</h1></body></html>")

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    online_scraper = DGHSBronzeScraper(max_retries=1, offline_mode=False)
    with pytest.raises(DGHSParseError, match="0 zones"):
        online_scraper.run_pipeline(output_dir=tmp_path)
