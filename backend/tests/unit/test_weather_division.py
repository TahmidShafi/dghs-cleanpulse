"""Unit tests for division-level Silver weather aggregation and chunked ERA5 ingest."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pandas as pd
import pytest

from cleanpulse.bronze.weather_client import OpenMeteoWeatherClient
from cleanpulse.cli import main as cli_main
from cleanpulse.silver.spatial_crosswalk import load_district_crosswalk
from cleanpulse.silver.weather_division import build_weather_divisions_daily


def test_ingest_weather_requires_explicit_start_and_end() -> None:
    with pytest.raises(SystemExit) as exc:
        cli_main(["ingest-weather"])
    assert exc.value.code != 0


def test_weather_ingest_chunks_date_range_and_records_era5_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cw = load_district_crosswalk().head(2).copy()
    captured: list[dict[str, str]] = []

    def mock_get(url: str, params: dict[str, str], timeout: float) -> httpx.Response:
        captured.append(dict(params))
        d_list = OpenMeteoWeatherClient.generate_dates(params["start_date"], params["end_date"])
        payload = [
            {
                "daily": {
                    "time": d_list,
                    "temperature_2m_mean": [26.0] * len(d_list),
                    "precipitation_sum": [2.0] * len(d_list),
                    "relative_humidity_2m_mean": [75.0] * len(d_list),
                }
            }
            for _ in range(len(cw))
        ]
        return httpx.Response(200, request=httpx.Request("GET", url, params=params), json=payload)

    monkeypatch.setattr(httpx, "get", mock_get)

    client = OpenMeteoWeatherClient(batch_size=2)
    bronze_dir = tmp_path / "bronze"
    paths = client.ingest_bronze_batches(
        start_date="2022-01-01",
        end_date="2022-01-05",
        crosswalk_df=cw,
        bronze_dir=bronze_dir,
        chunk_days=3,
    )
    assert len(paths) == 2
    assert len(captured) == 2
    assert captured[0]["models"] == "era5"
    assert (captured[0]["start_date"], captured[0]["end_date"]) == ("2022-01-01", "2022-01-03")
    assert (captured[1]["start_date"], captured[1]["end_date"]) == ("2022-01-04", "2022-01-05")

    sidecar = json.loads(
        paths[0].with_name(f"{paths[0].stem}.sidecar.json").read_text(encoding="utf-8")
    )
    assert sidecar["models"] == "era5"
    assert sidecar["start_date"] == "2022-01-01"
    assert sidecar["end_date"] == "2022-01-03"


def test_build_weather_divisions_daily_averages_per_division_and_national(
    tmp_path: Path,
) -> None:
    cw = load_district_crosswalk()
    rows = []
    for idx, rec in cw.iterrows():
        rows.append(
            {
                "date": "2022-01-01",
                "district_id": rec["district_id"],
                "district_name": rec["district_name"],
                "dghs_reporting_zone": rec["dghs_reporting_zone"],
                "temperature_2m_mean": 20.0 + float(idx % 4),
                "precipitation_sum": 1.0 if rec["division_name"] == "Sylhet" else 0.0,
                "relative_humidity_2m_mean": 80.0,
            }
        )
    dist_parquet = tmp_path / "weather_districts_daily.parquet"
    pd.DataFrame(rows).to_parquet(dist_parquet, index=False)

    out_parquet = tmp_path / "weather_divisions_daily.parquet"
    build_weather_divisions_daily(districts_parquet=dist_parquet, output_parquet=out_parquet)
    df_div = pd.read_parquet(out_parquet)

    assert len(df_div) == 9  # National + 8 divisions
    nat = df_div[df_div["scope"] == "National"].iloc[0]
    assert nat["district_count"] == 64
    syl = df_div[df_div["scope"] == "Sylhet"].iloc[0]
    assert syl["precipitation_sum"] == pytest.approx(1.0)
