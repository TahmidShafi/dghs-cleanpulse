"""Integration test suite for the CleanPulse Medallion CLI Orchestrator."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from cleanpulse.cli import main

REPO_ROOT = Path(__file__).resolve().parents[3]
SILVER_DIR = REPO_ROOT / "data" / "silver"
GOLD_DIR = REPO_ROOT / "data" / "gold"
SNAPSHOT_PATH = REPO_ROOT / "frontend" / "public" / "data" / "fallback_snapshot.json"


def test_cli_help_exit_zero(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that invoking CLI help returns exit code 0."""
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "DGHS-CleanPulse Medallion Pipeline CLI Orchestrator" in captured.out


def test_cli_no_args_exit_zero(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that invoking CLI with no arguments prints help and exits 0."""
    code = main([])
    assert code == 0
    captured = capsys.readouterr()
    assert "usage: cleanpulse" in captured.out


def test_cli_subcommands_sequential() -> None:
    """Verify running each subcommand sequentially."""
    assert main(["scrape-bronze", "--offline"]) == 0
    assert main(["run-silver"]) == 0
    assert main(["build-gold"]) == 0
    assert main(["export-snapshot"]) == 0


def test_cli_run_all_offline_verifies_all_medallion_artifacts() -> None:
    """Verify cleanpulse run-all --offline completes with code 0 and populates all layers."""
    exit_code = main(["run-all", "--offline"])
    assert exit_code == 0

    # 1. Verify Silver Parquet Artifacts
    weather_p = SILVER_DIR / "weather_districts_daily.parquet"
    assert weather_p.exists()
    df_weather = pd.read_parquet(weather_p)
    assert len(df_weather) == 11520  # 64 districts * 180 days

    age_p = SILVER_DIR / "dengue_age_groups.parquet"
    assert age_p.exists()
    df_age = pd.read_parquet(age_p)
    assert len(df_age) == 17  # 17 canonical age cohorts

    anom_p = SILVER_DIR / "audit_anomalies.parquet"
    assert anom_p.exists()
    df_anom = pd.read_parquet(anom_p)
    assert len(df_anom) == 6  # 6 intercepted anomalies

    zones_p = SILVER_DIR / "dengue_zones_daily.parquet"
    assert zones_p.exists()
    df_zones = pd.read_parquet(zones_p)
    assert len(df_zones) == 1800  # 10 zones * 180 days

    # 2. Verify Gold Parquet Artifacts
    gold_daily_p = GOLD_DIR / "zone_daily_climate_dengue.parquet"
    assert gold_daily_p.exists()
    df_gold_daily = pd.read_parquet(gold_daily_p)
    assert len(df_gold_daily) == 1800

    gold_lags_p = GOLD_DIR / "zone_lag_correlations.parquet"
    assert gold_lags_p.exists()
    df_gold_lags = pd.read_parquet(gold_lags_p)
    assert len(df_gold_lags) == 319  # 11 zones * 29 lags

    # 3. Verify Frontend Snapshot JSON
    assert SNAPSHOT_PATH.exists()
    with SNAPSHOT_PATH.open("r", encoding="utf-8") as f:
        snapshot_data = json.load(f)

    assert "surveillance_summary" in snapshot_data
    assert "lags_by_zone" in snapshot_data
    assert "audit_anomalies" in snapshot_data
    assert "pipeline_health" in snapshot_data
    assert len(snapshot_data["audit_anomalies"]["anomalies"]) == 6


def test_cli_export_report(tmp_path: Path) -> None:
    """Verify cleanpulse export-report generates valid markdown report."""
    report_file = tmp_path / "test_anomaly_report.md"
    assert main(["export-report", "--output", str(report_file)]) == 0
    assert report_file.exists()
    content = report_file.read_text(encoding="utf-8")
    assert "# DGHS Daily Surveillance Anomaly Audit Report" in content
    assert "Total Upstream Anomalies Intercepted" in content
