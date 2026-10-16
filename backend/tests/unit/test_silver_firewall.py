"""Unit tests for the Silver Layer Sanitization and Pandera Validation Firewall."""

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from cleanpulse.bronze.dghs_scraper import DEFAULT_FIXTURE_PATH, DGHSBronzeScraper
from cleanpulse.silver.firewall import (
    CANONICAL_AGE_GROUPS,
    CANONICAL_ZONES,
    AuditAnomalySilverSchema,
    DGHSAgeGroupSilverSchema,
    DGHSDivisionSilverSchema,
    SilverSanitizerFirewall,
)


@pytest.fixture
def raw_bronze_payload() -> dict[str, object]:
    """Provide raw Bronze data parsed from the standard test fixture."""
    scraper = DGHSBronzeScraper(offline_mode=True, fixture_path=DEFAULT_FIXTURE_PATH)
    html, source_hash, source_type = scraper.fetch_html(force_offline=True)
    return scraper.parse_dashboard(html, source_hash, source_type)


@pytest.fixture
def firewall(tmp_path: Path) -> SilverSanitizerFirewall:
    """Provide a SilverSanitizerFirewall configured with a temporary output directory."""
    return SilverSanitizerFirewall(output_dir=tmp_path)


def test_stage_2a_raw_audit_scan_collects_all_failures(
    firewall: SilverSanitizerFirewall,
    raw_bronze_payload: dict[str, object],
) -> None:
    """Verify that Stage 2A lazy validation collects ALL raw schema/arithmetic failures

    in a single diagnostic pass without crashing on the first failure.
    """
    raw_age_df = pd.DataFrame(raw_bronze_payload["age_groups"])
    failure_cases = firewall.run_raw_audit_scan(raw_age_df)

    assert failure_cases is not None, "Expected failure cases from raw audit scan"
    assert len(failure_cases) >= 6

    # Verify that Pandera captured the invalid age group strings
    failed_values = failure_cases["failure_case"].astype(str).tolist()
    assert "42309" in failed_values
    assert "46301" in failed_values
    assert "6-10" in failed_values
    assert "0-10" in failed_values
    assert "" in failed_values

    # Verify that the gender sum check failure was captured
    checks_triggered = failure_cases["check"].tolist()
    assert any(
        "Row sum mismatch" in str(chk) or "gender_sum_check" in str(chk) for chk in checks_triggered
    )


def test_excel_serial_date_decoding_and_quarantine(
    firewall: SilverSanitizerFirewall,
    raw_bronze_payload: dict[str, object],
) -> None:
    """Verify that 5-digit Excel serial dates (42309, 46301) are decoded to ISO dates,

    quarantined out of the primary cohort table, and logged into audit_anomalies.
    """
    # Test formula directly: date(1899, 12, 30) + timedelta(days=int(val))
    assert (
        firewall.decode_excel_serial_date("42309")
        == (date(1899, 12, 30) + timedelta(days=42309)).isoformat()
    )
    assert (
        firewall.decode_excel_serial_date("46301")
        == (date(1899, 12, 30) + timedelta(days=46301)).isoformat()
    )
    assert firewall.decode_excel_serial_date("46301") == "2026-10-06"

    raw_age_df = pd.DataFrame(raw_bronze_payload["age_groups"])
    sanitized_df, anomalies = firewall.repair_and_quarantine_age_groups(raw_age_df, "2026-10-14")

    # Verify rows are quarantined from sanitized table
    active_groups = sanitized_df["age_group"].tolist()
    assert "42309" not in active_groups
    assert "46301" not in active_groups

    # Verify logged anomaly entries
    excel_anomalies = [a for a in anomalies if a["anomaly_type"] == "EXCEL_SERIAL_DATE_CAST"]
    assert len(excel_anomalies) == 2
    row_keys = [a["row_key"] for a in excel_anomalies]
    assert "42309" in row_keys
    assert "46301" in row_keys
    for anom in excel_anomalies:
        assert anom["severity"] == "CRITICAL"
        assert "QUARANTINED_EXCEL_DATE" in anom["repaired_value"]


def test_zero_pad_canonicalizer_merges_counts(
    firewall: SilverSanitizerFirewall,
    raw_bronze_payload: dict[str, object],
) -> None:
    """Verify that '6-10' is mapped to '06-10', its counts are absorbed into '06-10',

    '6-10' is removed from the table, and an anomaly is logged.
    """
    raw_age_df = pd.DataFrame(raw_bronze_payload["age_groups"])
    sanitized_df, anomalies = firewall.repair_and_quarantine_age_groups(raw_age_df, "2026-10-14")

    # '6-10' must not exist in sanitized output
    assert "6-10" not in sanitized_df["age_group"].tolist()

    # '06-10' must have absorbed the 1 male case from '6-10'
    row_06_10 = sanitized_df[sanitized_df["age_group"] == "06-10"].iloc[0]
    # Original 06-10 had male=3020, female=2296, total=5316; 6-10 had male=1, total=1
    assert row_06_10["male_cases"] == 3021
    assert row_06_10["female_cases"] == 2296
    assert row_06_10["reconciled_total"] == 5317

    zero_pad_anom = next(a for a in anomalies if a["anomaly_type"] == "ZERO_PAD_DRIFT")
    assert zero_pad_anom["row_key"] == "6-10"
    assert zero_pad_anom["severity"] == "WARNING"
    assert "06-10" in zero_pad_anom["repaired_value"]


def test_invalid_buckets_quarantine(
    firewall: SilverSanitizerFirewall,
    raw_bronze_payload: dict[str, object],
) -> None:
    """Verify that overlapping bucket '0-10' and empty bucket '' are quarantined."""
    raw_age_df = pd.DataFrame(raw_bronze_payload["age_groups"])
    sanitized_df, anomalies = firewall.repair_and_quarantine_age_groups(raw_age_df, "2026-10-14")

    active_groups = sanitized_df["age_group"].tolist()
    assert "0-10" not in active_groups
    assert "" not in active_groups

    invalid_bucket_anomalies = [a for a in anomalies if a["anomaly_type"] == "INVALID_AGE_BUCKET"]
    assert len(invalid_bucket_anomalies) == 2
    row_keys = [a["row_key"] for a in invalid_bucket_anomalies]
    assert "0-10" in row_keys
    assert "<EMPTY>" in row_keys


def test_cross_column_arithmetic_reconciler(
    firewall: SilverSanitizerFirewall,
    raw_bronze_payload: dict[str, object],
) -> None:
    """Verify that row '21-25' arithmetic delta (+10) is detected and reconciled."""
    raw_age_df = pd.DataFrame(raw_bronze_payload["age_groups"])
    sanitized_df, anomalies = firewall.repair_and_quarantine_age_groups(raw_age_df, "2026-10-14")

    row_21_25 = sanitized_df[sanitized_df["age_group"] == "21-25"].iloc[0]
    assert row_21_25["male_cases"] == 3005
    assert row_21_25["female_cases"] == 2375
    assert row_21_25["reported_total"] == 5390
    assert row_21_25["reconciled_total"] == 5380  # 3005 + 2375
    assert row_21_25["arithmetic_delta"] == 10

    # Ensure clean cohorts have zero delta
    clean_cohorts = sanitized_df[sanitized_df["age_group"] != "21-25"]
    assert (clean_cohorts["arithmetic_delta"] == 0).all()

    sum_anom = next(a for a in anomalies if a["anomaly_type"] == "GENDER_SUM_MISMATCH")
    assert sum_anom["row_key"] == "21-25"
    assert "+10" in sum_anom["explanation"]
    assert sum_anom["repaired_value"] == "reconciled_total=5380"


def test_final_silver_schemas_and_parquet_persistence(
    firewall: SilverSanitizerFirewall,
    raw_bronze_payload: dict[str, object],
    tmp_path: Path,
) -> None:
    """Verify end-to-end pipeline execution: schema validation and Parquet output generation."""
    # Write bronze payload to temporary JSON file to simulate realistic bronze reading
    bronze_path = tmp_path / "dghs_raw_sample.json"
    with open(bronze_path, "w", encoding="utf-8") as f:
        json.dump(raw_bronze_payload, f)

    result = firewall.process_bronze_snapshot(bronze_path, output_dir=tmp_path)

    # 1. Validate files exist on disk
    assert result.age_groups_parquet.exists()
    assert result.zones_parquet.exists()
    assert result.anomalies_parquet.exists()

    # 2. Read back Parquet tables
    df_age_read = pd.read_parquet(result.age_groups_parquet)
    df_zones_read = pd.read_parquet(result.zones_parquet)
    df_anom_read = pd.read_parquet(result.anomalies_parquet)

    # 3. Enforce that read-back DataFrames adhere strictly to Pandera schemas
    DGHSAgeGroupSilverSchema.validate(df_age_read, lazy=True)
    DGHSDivisionSilverSchema.validate(df_zones_read, lazy=True)
    AuditAnomalySilverSchema.validate(df_anom_read, lazy=True)

    # Validate arithmetic delta in read-back age table
    assert "arithmetic_delta" in df_age_read.columns
    assert df_age_read[df_age_read["age_group"] == "21-25"]["arithmetic_delta"].iloc[0] == 10
    assert (df_age_read[df_age_read["age_group"] != "21-25"]["arithmetic_delta"] == 0).all()

    # 4. Assert row counts and integrity
    # 10 official zones
    assert len(df_zones_read) == 10
    assert df_zones_read["zone_name"].tolist() == CANONICAL_ZONES

    # Canonical age groups (all 17 non-empty canonical cohorts retained)
    assert len(df_age_read) == len(CANONICAL_AGE_GROUPS)
    assert set(df_age_read["age_group"]) == set(CANONICAL_AGE_GROUPS)

    # Exactly 6 anomalies recorded: 2 serial dates + 1 zero pad + 2 invalid buckets + 1 sum mismatch
    assert len(df_anom_read) == 6
    expected_anomaly_types = {
        "EXCEL_SERIAL_DATE_CAST",
        "ZERO_PAD_DRIFT",
        "INVALID_AGE_BUCKET",
        "GENDER_SUM_MISMATCH",
    }
    assert set(df_anom_read["anomaly_type"]) == expected_anomaly_types
