"""Integration tests for the DGHS-CleanPulse FastAPI REST Service."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from cleanpulse.api.main import app


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """Provide a TestClient instance with startup lifespan context entered."""
    with TestClient(app) as test_client:
        yield test_client


def test_surveillance_summary_endpoint(client: TestClient) -> None:
    """Verify GET /v1/surveillance/summary returns valid KPIs, zones, and age cohorts."""
    response = client.get("/v1/surveillance/summary")
    assert response.status_code == 200

    data = response.json()
    assert data["report_date"] == "2026-10-14"
    assert data["total_admitted"] == 105316
    assert data["total_deaths"] == 452
    assert data["anomalies_caught_count"] == 6
    assert data["optimal_lag_days"] in range(12, 20)

    # 10 official zones
    zones = data["zones_summary"]
    assert len(zones) == 10
    zone_names = {z["zone_name"] for z in zones}
    assert "Chattogram" in zone_names
    assert "DNCC" in zone_names
    assert "DSCC" in zone_names
    assert "Dhaka (Out of CC)" in zone_names

    # 17 sanitized age cohorts
    age_groups = data["age_groups"]
    assert len(age_groups) == 17
    cohort_21_25 = next(c for c in age_groups if c["age_group"] == "21-25")
    assert cohort_21_25["reported_total"] == 5390
    assert cohort_21_25["reconciled_total"] == 5380
    assert cohort_21_25["arithmetic_delta"] == 10


def test_surveillance_lags_endpoint(client: TestClient) -> None:
    """Verify GET /v1/surveillance/lags returns 29 correlation points and aligned series."""
    # 1. Default National query
    resp = client.get("/v1/surveillance/lags")
    assert resp.status_code == 200

    data = resp.json()
    assert data["zone_name"] == "National"
    assert data["selected_lag_days"] == 16
    assert len(data["lag_correlations"]) == 29
    assert len(data["aligned_time_series"]) == 180

    # Verify lag offsets 0 to 28
    lags = [item["lag_days"] for item in data["lag_correlations"]]
    assert lags == list(range(29))

    # 2. Specific zone query (e.g. Chattogram)
    resp_ctg = client.get("/v1/surveillance/lags?zone=Chattogram&lag_days=14")
    assert resp_ctg.status_code == 200
    data_ctg = resp_ctg.json()
    assert data_ctg["zone_name"] == "Chattogram"
    assert data_ctg["selected_lag_days"] == 14
    assert len(data_ctg["aligned_time_series"]) == 180

    # 3. Invalid zone name -> 400 Bad Request
    resp_invalid_zone = client.get("/v1/surveillance/lags?zone=Atlantis")
    assert resp_invalid_zone.status_code == 400
    assert "is invalid" in resp_invalid_zone.json()["detail"]

    # 4. Out-of-bounds lag_days (> 28) -> 422 Unprocessable Entity
    resp_high_lag = client.get("/v1/surveillance/lags?lag_days=50")
    assert resp_high_lag.status_code == 422

    # 5. Negative lag_days (< 0) -> 422 Unprocessable Entity
    resp_neg_lag = client.get("/v1/surveillance/lags?lag_days=-1")
    assert resp_neg_lag.status_code == 422


def test_audit_anomalies_endpoint(client: TestClient) -> None:
    """Verify GET /v1/audit/anomalies returns filtered and aggregated anomaly records."""
    # 1. Retrieve all anomalies
    resp = client.get("/v1/audit/anomalies")
    assert resp.status_code == 200

    data = resp.json()
    assert data["total_anomalies"] == 6
    assert len(data["anomalies"]) == 6
    assert "CRITICAL" in data["severity_counts"]
    assert "WARNING" in data["severity_counts"]

    # 2. Filter by severity
    resp_crit = client.get("/v1/audit/anomalies?severity=CRITICAL")
    assert resp_crit.status_code == 200
    crit_data = resp_crit.json()
    for anom in crit_data["anomalies"]:
        assert anom["severity"] == "CRITICAL"

    # 3. Filter by anomaly_type
    resp_type = client.get("/v1/audit/anomalies?anomaly_type=EXCEL_SERIAL_DATE_CAST")
    assert resp_type.status_code == 200
    type_data = resp_type.json()
    assert len(type_data["anomalies"]) == 2
    for anom in type_data["anomalies"]:
        assert anom["anomaly_type"] == "EXCEL_SERIAL_DATE_CAST"


def test_pipeline_health_endpoint(client: TestClient) -> None:
    """Verify GET /v1/health/pipeline reports exact Medallion layer counts and latency."""
    resp = client.get("/v1/health/pipeline")
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "healthy"
    assert data["schemas_validated"] is True
    assert data["duckdb_latency_ms"] >= 0.0

    counts = data["layer_counts"]
    assert counts["silver_dengue_rows"] == 1800
    assert counts["silver_weather_rows"] == 11520
    assert counts["silver_anomaly_rows"] == 6
    assert counts["gold_daily_rows"] == 1800
    assert counts["gold_lag_rows"] == 319
