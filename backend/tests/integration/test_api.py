"""Integration tests for the DGHS-CleanPulse FastAPI REST Service."""

from __future__ import annotations

from collections.abc import Generator
from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import cleanpulse.api.main as api_main
from cleanpulse.silver.spatial_crosswalk import load_district_crosswalk
from tests.synthetic_weather import generate_synthetic_weather


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> Generator[TestClient, None, None]:
    """Provide an isolated TestClient backed by tmp_path (never mutates data/)."""
    tmp_root = tmp_path_factory.mktemp("api_data")
    silver_dir = tmp_root / "silver"
    gold_dir = tmp_root / "gold"
    bronze_dir = tmp_root / "bronze"
    silver_dir.mkdir(parents=True)
    gold_dir.mkdir(parents=True)
    bronze_dir.mkdir(parents=True)

    # Populate only weather parquet in isolated tmp silver_dir
    cw = load_district_crosswalk()
    weather_df = generate_synthetic_weather(
        cw.to_dict(orient="records"),
        start_date="2026-10-01",
        end_date="2026-10-14",
        seed=11,
    )
    weather_parquet = silver_dir / "weather_districts_daily.parquet"
    weather_df.to_parquet(weather_parquet, index=False)

    dengue_daily_parquet = silver_dir / "dengue_division_daily.parquet"
    pd.DataFrame(
        {
            "report_date": ["2022-01-01", "2022-01-02"],
            "division": ["Dhaka", "Dhaka"],
            "cases": [10, 15],
            "source_label": ["secondary", "secondary"],
        }
    ).to_parquet(dengue_daily_parquet, index=False)

    gold_weekly_parquet = gold_dir / "weekly_scope_climate_cases.parquet"
    pd.DataFrame(
        {
            "scope": ["National", "Dhaka"],
            "iso_year": [2022, 2022],
            "iso_week": [1, 1],
            "week_start_date": ["2022-01-03", "2022-01-03"],
            "week_end_date": ["2022-01-09", "2022-01-09"],
            "weekly_cases": [100, 60],
            "weekly_precip_mm": [12.5, 10.0],
            "weekly_temp_c": [22.1, 22.5],
            "weekly_humidity_pct": [75.0, 74.0],
        }
    ).to_parquet(gold_weekly_parquet, index=False)

    gold_weekly_lags_parquet = gold_dir / "lag_correlations_weekly.parquet"
    lag_rows = []
    for tr in ("raw", "diff_log"):
        for k in range(9):
            lag_rows.append(
                {
                    "scope": "National",
                    "variable": "weekly_precip_mm",
                    "transform": tr,
                    "lag_weeks": k,
                    "rho": 0.25 if tr == "raw" else None,
                    "n": 156 - k if tr == "raw" else 155 - k,
                    "null_reason": None if tr == "raw" else "constant series",
                }
            )
    pd.DataFrame(lag_rows).to_parquet(gold_weekly_lags_parquet, index=False)

    orig_attrs = {
        "DATA_DIR": api_main.DATA_DIR,
        "SILVER_DIR": api_main.SILVER_DIR,
        "GOLD_DIR": api_main.GOLD_DIR,
        "BRONZE_DIR": api_main.BRONZE_DIR,
        "ZONES_PARQUET": api_main.ZONES_PARQUET,
        "AGE_PARQUET": api_main.AGE_PARQUET,
        "WEATHER_PARQUET": api_main.WEATHER_PARQUET,
        "ANOMALIES_PARQUET": api_main.ANOMALIES_PARQUET,
        "GOLD_DAILY_PARQUET": api_main.GOLD_DAILY_PARQUET,
        "GOLD_LAGS_PARQUET": api_main.GOLD_LAGS_PARQUET,
        "SILVER_DENGUE_DAILY_PARQUET": api_main.SILVER_DENGUE_DAILY_PARQUET,
        "GOLD_WEEKLY_PARQUET": api_main.GOLD_WEEKLY_PARQUET,
        "GOLD_WEEKLY_LAGS_PARQUET": api_main.GOLD_WEEKLY_LAGS_PARQUET,
    }
    api_main.reset_db()
    api_main.DATA_DIR = tmp_root
    api_main.SILVER_DIR = silver_dir
    api_main.GOLD_DIR = gold_dir
    api_main.BRONZE_DIR = bronze_dir
    api_main.ZONES_PARQUET = silver_dir / "dengue_zones_daily.parquet"
    api_main.AGE_PARQUET = silver_dir / "dengue_age_groups.parquet"
    api_main.WEATHER_PARQUET = weather_parquet
    api_main.ANOMALIES_PARQUET = silver_dir / "audit_anomalies.parquet"
    api_main.GOLD_DAILY_PARQUET = gold_dir / "zone_daily_climate_dengue.parquet"
    api_main.GOLD_LAGS_PARQUET = gold_dir / "zone_lag_correlations.parquet"
    api_main.SILVER_DENGUE_DAILY_PARQUET = dengue_daily_parquet
    api_main.GOLD_WEEKLY_PARQUET = gold_weekly_parquet
    api_main.GOLD_WEEKLY_LAGS_PARQUET = gold_weekly_lags_parquet

    try:
        with TestClient(api_main.app) as test_client:
            yield test_client
    finally:
        api_main.reset_db()
        for k, v in orig_attrs.items():
            setattr(api_main, k, v)


def test_surveillance_summary_pending_real_source(client: TestClient) -> None:
    """Verify GET /v1/surveillance/summary returns 200 with pending_real_source."""
    resp = client.get("/v1/surveillance/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending_real_source"
    assert body["reason"] == "no_real_dengue_series"
    assert body["message"] == (
        "Live DGHS feed offline; historical secondary-source series available under 'historical'."
    )
    assert body["weather_available"] is True
    assert body["data"] is None
    assert body["historical"]["total_cases"] == 25
    assert body["historical"]["window"] == "2022-01-01 to 2022-01-02"


def test_surveillance_lags_pending_real_source_and_validation(client: TestClient) -> None:
    """Verify GET /v1/surveillance/lags returns pending_real_source and validates query params."""
    resp = client.get("/v1/surveillance/lags")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending_real_source"
    assert body["reason"] == "no_real_dengue_series"
    assert body["message"] == (
        "Live DGHS feed offline; historical secondary-source series available under 'historical'."
    )
    assert body["weather_available"] is True
    assert body["data"] is None

    resp_invalid_zone = client.get("/v1/surveillance/lags?zone=Atlantis")
    assert resp_invalid_zone.status_code == 400

    resp_high_lag = client.get("/v1/surveillance/lags?lag_days=50")
    assert resp_high_lag.status_code == 422


def test_weather_daily_endpoint_properties(client: TestClient) -> None:
    """Verify GET /v1/weather/daily returns contiguous dates and valid physical bounds."""
    resp = client.get("/v1/weather/daily?zone=National")
    assert resp.status_code == 200
    body = resp.json()
    assert body["zone_name"] == "National"
    assert body["district_count"] == 64
    series = body["series"]
    assert len(series) > 0

    dates = [pt["date"] for pt in series]
    assert dates == sorted(set(dates))
    expected_days = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days + 1
    assert len(dates) == expected_days

    for pt in series:
        assert pt["precip_mm"] >= 0.0
        assert 0.0 <= pt["humidity_pct"] <= 100.0
        assert -5.0 <= pt["temp_c"] <= 55.0


def test_audit_anomalies_empty_when_no_real_dghs_data(client: TestClient) -> None:
    """Verify GET /v1/audit/anomalies returns 0 anomalies (never synthetic fixture data)."""
    resp = client.get("/v1/audit/anomalies")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_anomalies"] == 0
    assert body["anomalies"] == []


def test_pipeline_health_endpoint_returns_200(client: TestClient) -> None:
    """Verify GET /v1/health/pipeline returns 200 and reports 0 dengue/gold rows."""
    resp = client.get("/v1/health/pipeline")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["schemas_validated"] is True
    counts = body["layer_counts"]
    assert counts["silver_dengue_rows"] == 0
    assert counts["gold_daily_rows"] == 0
    assert counts["gold_lag_rows"] == 0
    assert counts["silver_weather_rows"] > 0


def test_historical_weekly_and_lag_correlations_endpoints(client: TestClient) -> None:
    resp_w = client.get("/v1/historical/weekly?scope=National")
    assert resp_w.status_code == 200
    body_w = resp_w.json()
    assert body_w["scope"] == "National"
    assert body_w["dataset_doi"] == "10.17632/z5mvwrfgsz.1"
    assert len(body_w["series"]) == 1
    assert body_w["series"][0]["iso_week"] == "2022-W01"
    assert body_w["series"][0]["weekly_cases"] == 100

    assert client.get("/v1/historical/weekly?scope=Atlantis").status_code == 400

    resp_l = client.get("/v1/analytics/lag-correlations?scope=National&variable=weekly_precip_mm")
    assert resp_l.status_code == 200
    body_l = resp_l.json()
    assert len(body_l["rows"]) == 18
    assert (
        client.get("/v1/analytics/lag-correlations?scope=National&variable=bad").status_code == 400
    )
