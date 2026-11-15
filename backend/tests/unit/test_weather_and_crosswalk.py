"""Unit tests for the 64-District Spatial Crosswalk and Open-Meteo Bronze/Silver Client."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

from cleanpulse.bronze.weather_client import (
    OpenMeteoWeatherClient,
    WeatherDailySilverSchema,
    WeatherFetchError,
)
from cleanpulse.silver.firewall import CANONICAL_ZONES
from cleanpulse.silver.spatial_crosswalk import (
    DEFAULT_CROSSWALK_PATH,
    DistrictCrosswalkSilverSchema,
    get_district_by_id,
    get_districts_for_zone,
    load_district_crosswalk,
)
from tests.synthetic_weather import generate_synthetic_weather


def test_spatial_crosswalk_structure_and_coverage() -> None:
    """Verify that the crosswalk contains exactly 64 unique districts covering all 10 DGHS zones."""
    assert DEFAULT_CROSSWALK_PATH.exists()
    df = load_district_crosswalk(DEFAULT_CROSSWALK_PATH)

    assert len(df) == 64
    assert df["district_id"].nunique() == 64
    assert df["district_name"].nunique() == 64
    DistrictCrosswalkSilverSchema.validate(df, lazy=True)

    unique_zones: set[str] = set()
    for zones in df["dghs_reporting_zones"]:
        if isinstance(zones, (list, np.ndarray)):
            unique_zones.update(zones)
        elif isinstance(zones, str):
            unique_zones.update([z.strip() for z in zones.split(",")])
    assert set(CANONICAL_ZONES).issubset(unique_zones)
    assert len(unique_zones) == 10

    assert get_districts_for_zone("DNCC", df) == ["dhaka"]
    assert get_districts_for_zone("DSCC", df) == ["dhaka"]
    out_of_cc = get_districts_for_zone("Dhaka (Out of CC)", df)
    assert "madaripur" in out_of_cc
    assert len(out_of_cc) == 12

    for dist_id in ("dhaka", "madaripur", "shariatpur"):
        rec = get_district_by_id(dist_id, df)
        assert 20.5 <= rec["latitude"] <= 26.8
        assert 88.0 <= rec["longitude"] <= 92.8


def test_synthetic_weather_test_helper_schema_and_properties() -> None:
    """Verify the test-only synthetic weather helper satisfies Silver schema & invariants."""
    cw = load_district_crosswalk()
    df = generate_synthetic_weather(cw.to_dict(orient="records"))
    WeatherDailySilverSchema.validate(df, lazy=True)

    assert df["district_id"].nunique() == 64
    assert not df.duplicated(subset=["date", "district_id"]).any()
    dates = sorted(df["date"].unique())
    expected_span = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days + 1
    assert len(dates) == expected_span
    assert (df["precipitation_sum"] >= 0.0).all()


def test_weather_ingest_bronze_and_build_silver_from_bronze(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify live weather ingestion writes immutable Bronze + sidecars and builds Silver."""
    cw = load_district_crosswalk().head(4).copy()
    dates = ["2026-10-12", "2026-10-13", "2026-10-14"]

    captured_params: list[dict[str, str]] = []

    def mock_get(url: str, params: dict[str, str], timeout: float) -> httpx.Response:
        captured_params.append(dict(params))
        payload = [
            {
                "daily": {
                    "time": dates,
                    "temperature_2m_mean": [28.1, 28.4, 27.9],
                    "precipitation_sum": [0.0, 12.3, 4.1],
                    "relative_humidity_2m_mean": [78.0, 84.0, 81.0],
                }
            }
            for _ in range(len(cw))
        ]
        req = httpx.Request("GET", url, params=params)
        return httpx.Response(200, request=req, json=payload)

    monkeypatch.setattr(httpx, "get", mock_get)

    client = OpenMeteoWeatherClient(batch_size=4)
    bronze_dir = tmp_path / "bronze" / "weather"
    silver_parquet = tmp_path / "silver" / "weather_districts_daily.parquet"

    df = client.fetch_climate_data(
        crosswalk_df=cw,
        start_date="2026-10-12",
        end_date="2026-10-14",
        bronze_dir=bronze_dir,
        output_parquet=silver_parquet,
    )

    assert silver_parquet.exists()
    raw_files = [p for p in bronze_dir.rglob("*.json") if not p.name.endswith(".sidecar.json")]
    assert len(raw_files) == 1
    sidecar_path = raw_files[0].with_name(f"{raw_files[0].stem}.sidecar.json")
    assert sidecar_path.exists()

    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert len(captured_params) == 1
    assert captured_params[0]["models"] == "era5"
    assert sidecar["models"] == "era5"
    assert sidecar["sha256"] == hashlib.sha256(raw_files[0].read_bytes()).hexdigest()
    assert sidecar["fetch_source"] == "live"
    assert "request_params" in sidecar
    assert "git_commit" in sidecar
    assert "git_dirty" in sidecar

    loaded = pd.read_parquet(silver_parquet)
    assert len(loaded) == len(df) == 4 * 3
    WeatherDailySilverSchema.validate(loaded, lazy=True)


def test_weather_fails_loudly_without_partial_silver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify HTTP 404 or mid-run batch failure raises WeatherFetchError and writes no Silver."""
    cw = load_district_crosswalk().head(4).copy()
    call_count = 0

    def mock_get(url: str, params: dict[str, str], timeout: float) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        req = httpx.Request("GET", url, params=params)
        if call_count == 1:
            payload = [
                {
                    "daily": {
                        "time": ["2026-10-14"],
                        "temperature_2m_mean": [28.0],
                        "precipitation_sum": [1.0],
                        "relative_humidity_2m_mean": [80.0],
                    }
                }
                for _ in range(2)
            ]
            return httpx.Response(200, request=req, json=payload)
        return httpx.Response(404, request=req, text="Not Found")

    monkeypatch.setattr(httpx, "get", mock_get)

    client = OpenMeteoWeatherClient(batch_size=2, max_retries=2)
    bronze_dir = tmp_path / "bronze" / "weather"
    silver_parquet = tmp_path / "silver" / "weather_districts_daily.parquet"

    with pytest.raises(WeatherFetchError, match="404"):
        client.fetch_climate_data(
            crosswalk_df=cw,
            start_date="2026-10-14",
            end_date="2026-10-14",
            bronze_dir=bronze_dir,
            output_parquet=silver_parquet,
        )

    assert not silver_parquet.exists()
    assert not list(bronze_dir.rglob("*.json")) if bronze_dir.exists() else True
