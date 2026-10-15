"""Unit tests for the DGHS Bronze Layer scraper and raw snapshot ingestion."""

import json
from pathlib import Path

import httpx
import pytest

from cleanpulse.bronze.dghs_scraper import DEFAULT_FIXTURE_PATH, DGHSBronzeScraper


@pytest.fixture
def scraper() -> DGHSBronzeScraper:
    """Fixture providing an offline-configured DGHSBronzeScraper."""
    return DGHSBronzeScraper(offline_mode=True, fixture_path=DEFAULT_FIXTURE_PATH)


def test_fixture_exists_and_readable() -> None:
    """Verify that the test HTML fixture exists and contains DGHS HTML markup."""
    assert DEFAULT_FIXTURE_PATH.exists(), f"Fixture missing at {DEFAULT_FIXTURE_PATH}"
    content = DEFAULT_FIXTURE_PATH.read_text(encoding="utf-8")
    assert "DGHS Dengue Dynamic Dashboard" in content
    assert "zone_distribution_table" in content
    assert "age_distribution_table" in content


def test_scraper_extracts_all_10_zones(scraper: DGHSBronzeScraper) -> None:
    """Verify that all 10 official reporting zones are extracted without omission."""
    html_content, source_hash, fetch_source = scraper.fetch_html(force_offline=True)
    assert fetch_source == "fixture"
    assert len(source_hash) == 64

    data = scraper.parse_dashboard(html_content, source_hash, fetch_source)
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
    assert len(extracted_zone_names) == 10
    assert extracted_zone_names == expected_zones

    # Validate individual zone fields
    dscc = next(z for z in zones if z["zone_name"] == "DSCC")
    assert dscc["daily_admitted"] == "320"
    assert dscc["daily_deaths"] == "3"
    assert dscc["total_admitted"] == "18,910"
    assert dscc["total_deaths"] == "112"

    dncc = next(z for z in zones if z["zone_name"] == "DNCC")
    assert dncc["daily_admitted"] == "240"
    assert dncc["total_deaths"] == "68"


def test_scraper_preserves_corrupted_age_buckets_verbatim(scraper: DGHSBronzeScraper) -> None:
    """Verify that upstream Excel serial dates, unnormalized labels, and sum mismatches

    are preserved verbatim in the Bronze layer without silent dropping or premature cleaning.
    """
    html_content, source_hash, fetch_source = scraper.fetch_html(force_offline=True)
    data = scraper.parse_dashboard(html_content, source_hash, fetch_source)
    age_groups = data["age_groups"]

    # 1. Excel serial date integer labels: "42309" and "46301"
    row_42309 = next((r for r in age_groups if r["age_group"] == "42309"), None)
    assert row_42309 is not None, "Corrupted age group '42309' was silently dropped"
    assert row_42309["male"] == "44"
    assert row_42309["female"] == "19"
    assert row_42309["total"] == "63"

    row_46301 = next((r for r in age_groups if r["age_group"] == "46301"), None)
    assert row_46301 is not None, "Corrupted age group '46301' was silently dropped"
    assert row_46301["male"] == "36"
    assert row_46301["female"] == "31"
    assert row_46301["total"] == "67"

    # 2. Unnormalized string variants: "6-10", "06-10", "0-10", and empty string ""
    row_6_10 = next((r for r in age_groups if r["age_group"] == "6-10"), None)
    assert row_6_10 is not None, "'6-10' was dropped or modified"
    assert row_6_10["total"] == "1"

    row_06_10 = next((r for r in age_groups if r["age_group"] == "06-10"), None)
    assert row_06_10 is not None, "'06-10' was dropped or modified"
    assert row_06_10["total"] == "5316"

    row_0_10 = next((r for r in age_groups if r["age_group"] == "0-10"), None)
    assert row_0_10 is not None, "'0-10' was dropped or modified"
    assert row_0_10["total"] == "1"

    row_empty = next((r for r in age_groups if r["age_group"] == ""), None)
    assert row_empty is not None, "Empty string age group '' was silently dropped"
    assert row_empty["male"] == "4"
    assert row_empty["female"] == "3"
    assert row_empty["total"] == "7"

    # 3. Row-sum mismatch: Male 3005 + Female 2375 = 5380, but reported as 5390
    row_mismatch = next((r for r in age_groups if r["age_group"] == "21-25"), None)
    assert row_mismatch is not None
    assert row_mismatch["male"] == "3005"
    assert row_mismatch["female"] == "2375"
    assert row_mismatch["total"] == "5390"  # Verbatim reported sum mismatch preserved


def test_sha256_hash_reproducibility(scraper: DGHSBronzeScraper) -> None:
    """Verify that SHA-256 hash matches exact raw content bytes."""
    html_content = DEFAULT_FIXTURE_PATH.read_text(encoding="utf-8")
    hash_val = scraper.compute_sha256(html_content)
    assert len(hash_val) == 64
    # Re-computing yields identical result
    assert scraper.compute_sha256(html_content) == hash_val


def test_save_snapshot_creates_valid_json(scraper: DGHSBronzeScraper, tmp_path: Path) -> None:
    """Verify that save_snapshot writes a valid, complete JSON snapshot to disk."""
    data, saved_path = scraper.run_pipeline(force_offline=True, output_dir=tmp_path)
    assert saved_path.exists()
    assert saved_path.name == "dghs_raw_2026_10_14.json"

    # Verify JSON structure
    with open(saved_path, encoding="utf-8") as f:
        loaded = json.load(f)

    assert loaded["metadata"]["source_hash"] == data["metadata"]["source_hash"]
    assert len(loaded["zones"]) == 10
    assert len(loaded["age_groups"]) == 22


def test_offline_fallback_on_network_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that the scraper falls back to local fixture when live requests fail."""

    def mock_get(*args: object, **kwargs: object) -> httpx.Response:
        raise httpx.ConnectTimeout("Connection timed out to DGHS")

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    online_scraper = DGHSBronzeScraper(
        base_url="https://dashboard.dghs.gov.bd/pages/heoc_dengue_v1.php",
        fixture_path=DEFAULT_FIXTURE_PATH,
        timeout=1.0,
        max_retries=2,
        backoff_factor=0.01,
        offline_mode=False,
    )

    data, saved_path = online_scraper.run_pipeline(output_dir=tmp_path)
    assert data["metadata"]["fetch_source"] == "fixture_fallback"
    assert len(data["zones"]) == 10
    assert saved_path.exists()
