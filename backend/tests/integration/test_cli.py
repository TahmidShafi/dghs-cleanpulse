"""Integration test suite for the CleanPulse Medallion CLI Orchestrator."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import httpx
import pandas as pd
import pytest

import cleanpulse.api.main as api_main
import cleanpulse.cli as cli_mod
from cleanpulse.cli import main


def test_cli_help_exit_zero(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that invoking CLI help returns exit code 0."""
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "DGHS-CleanPulse Medallion Pipeline CLI Orchestrator" in capsys.readouterr().out


def test_cli_no_args_exit_zero(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that invoking CLI with no arguments prints help and exits 0."""
    code = main([])
    assert code == 0
    assert "usage: cleanpulse" in capsys.readouterr().out


def test_cli_run_all_exits_nonzero_when_dghs_404(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify run-all fails loudly (exit code != 0) when DGHS returns 404."""
    monkeypatch.setattr(cli_mod, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(cli_mod, "BRONZE_DIR", tmp_path / "data" / "bronze")
    monkeypatch.setattr(cli_mod, "SILVER_DIR", tmp_path / "data" / "silver")
    monkeypatch.setattr(cli_mod, "GOLD_DIR", tmp_path / "data" / "gold")
    monkeypatch.setattr(cli_mod, "FRONTEND_SNAPSHOT_PATH", tmp_path / "snapshot.json")

    def mock_get(self: httpx.Client, url: str, **kwargs: object) -> httpx.Response:
        req = httpx.Request("GET", url)
        return httpx.Response(404, request=req, text="Not Found")

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    assert main(["run-all"]) != 0


def test_cli_weather_only_pipeline_and_snapshot_in_tmp_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify ingest-weather, build-silver --weather-only, and export-snapshot in tmp_path."""
    data_dir = tmp_path / "data"
    bronze_dir = data_dir / "bronze"
    silver_dir = data_dir / "silver"
    gold_dir = data_dir / "gold"
    snapshot_path = tmp_path / "fallback_snapshot.json"

    monkeypatch.setattr(cli_mod, "DATA_DIR", data_dir)
    monkeypatch.setattr(cli_mod, "BRONZE_DIR", bronze_dir)
    monkeypatch.setattr(cli_mod, "SILVER_DIR", silver_dir)
    monkeypatch.setattr(cli_mod, "GOLD_DIR", gold_dir)
    monkeypatch.setattr(cli_mod, "FRONTEND_SNAPSHOT_PATH", snapshot_path)

    api_main.reset_db()
    monkeypatch.setattr(api_main, "DATA_DIR", data_dir)
    monkeypatch.setattr(api_main, "BRONZE_DIR", bronze_dir)
    monkeypatch.setattr(api_main, "SILVER_DIR", silver_dir)
    monkeypatch.setattr(api_main, "GOLD_DIR", gold_dir)
    monkeypatch.setattr(api_main, "ZONES_PARQUET", silver_dir / "dengue_zones_daily.parquet")
    monkeypatch.setattr(api_main, "AGE_PARQUET", silver_dir / "dengue_age_groups.parquet")
    monkeypatch.setattr(api_main, "WEATHER_PARQUET", silver_dir / "weather_districts_daily.parquet")
    monkeypatch.setattr(api_main, "ANOMALIES_PARQUET", silver_dir / "audit_anomalies.parquet")
    monkeypatch.setattr(
        api_main, "GOLD_DAILY_PARQUET", gold_dir / "zone_daily_climate_dengue.parquet"
    )
    monkeypatch.setattr(api_main, "GOLD_LAGS_PARQUET", gold_dir / "zone_lag_correlations.parquet")

    dates = ["2026-10-12", "2026-10-13", "2026-10-14"]

    def mock_httpx_get(url: str, params: dict[str, str], timeout: float) -> httpx.Response:
        lats = params["latitude"].split(",")
        payload = [
            {
                "daily": {
                    "time": dates,
                    "temperature_2m_mean": [28.1, 28.4, 27.9],
                    "precipitation_sum": [0.0, 5.2, 1.3],
                    "relative_humidity_2m_mean": [78.0, 82.0, 80.0],
                }
            }
            for _ in lats
        ]
        req = httpx.Request("GET", url, params=params)
        return httpx.Response(200, request=req, json=payload)

    monkeypatch.setattr(httpx, "get", mock_httpx_get)

    try:
        assert main(["ingest-weather", "--start", "2026-10-12", "--end", "2026-10-14"]) == 0
        assert main(["build-silver", "--weather-only"]) == 0
        assert main(["export-snapshot"]) == 0

        # Verify Bronze sidecar SHA-256 matches raw JSON bytes
        raw_batches = [
            p
            for p in (bronze_dir / "weather").rglob("*.json")
            if not p.name.endswith(".sidecar.json")
        ]
        assert len(raw_batches) > 0
        for raw_p in raw_batches:
            sidecar_p = raw_p.with_name(f"{raw_p.stem}.sidecar.json")
            assert sidecar_p.exists()
            sidecar = json.loads(sidecar_p.read_text(encoding="utf-8"))
            assert sidecar["sha256"] == hashlib.sha256(raw_p.read_bytes()).hexdigest()

        # Verify Silver weather properties
        df_w = pd.read_parquet(silver_dir / "weather_districts_daily.parquet")
        assert df_w["district_id"].nunique() == 64
        assert not df_w.duplicated(subset=["date", "district_id"]).any()
        u_dates = sorted(df_w["date"].unique())
        assert (
            len(u_dates)
            == (date.fromisoformat(u_dates[-1]) - date.fromisoformat(u_dates[0])).days + 1
        )
        assert (df_w["precipitation_sum"] >= 0.0).all()

        # Verify Snapshot structure
        assert snapshot_path.exists()
        snap = json.loads(snapshot_path.read_text(encoding="utf-8"))
        assert "generated_at_utc" in snap["metadata"]
        assert "git_commit" in snap["metadata"]
        assert snap["surveillance_summary"]["status"] == "pending_real_source"
        assert snap["audit_anomalies"]["total_anomalies"] == 0
        assert "National" in snap["weather_by_zone"]
    finally:
        api_main.reset_db()
