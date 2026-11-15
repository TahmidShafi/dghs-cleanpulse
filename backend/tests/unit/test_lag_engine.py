"""Unit tests for the Gold Layer DuckDB Spatiotemporal Lag Engine using in-test synthetic data."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from cleanpulse.gold.lag_engine import (
    GOLD_ZONES_LIST,
    DuckDBLagEngine,
    GoldDailySchema,
    GoldLagCorrelationSchema,
)
from cleanpulse.silver.spatial_crosswalk import load_district_crosswalk
from tests.synthetic_weather import generate_synthetic_weather


def test_lag_engine_with_in_test_synthetic_data(tmp_path: Path) -> None:
    """Verify DuckDBLagEngine computes valid Gold tables on tiny in-test synthetic inputs."""
    silver_dir = tmp_path / "silver"
    gold_dir = tmp_path / "gold"
    silver_dir.mkdir(parents=True)

    cw = load_district_crosswalk()
    start = date(2026, 9, 1)
    num_days = 45
    dates = [(start + timedelta(days=i)).isoformat() for i in range(num_days)]

    # 1. Generate small in-test synthetic weather
    weather_df = generate_synthetic_weather(
        cw.to_dict(orient="records"),
        start_date=dates[0],
        end_date=dates[-1],
        seed=7,
    )
    weather_df.to_parquet(silver_dir / "weather_districts_daily.parquet", index=False)

    # 2. Generate small in-test synthetic dengue zone series for all 10 zones
    zones = [z for z in GOLD_ZONES_LIST if z != "National"]
    dengue_rows: list[dict[str, object]] = []
    for z_idx, zone_name in enumerate(zones):
        cum_adm = 0
        cum_deaths = 0
        for d_idx, d_str in enumerate(dates):
            daily_adm = 10 + z_idx + (d_idx % 7)
            daily_dth = 1 if d_idx % 10 == 0 else 0
            cum_adm += daily_adm
            cum_deaths += daily_dth
            dengue_rows.append(
                {
                    "report_date": d_str,
                    "zone_name": zone_name,
                    "daily_admitted": daily_adm,
                    "daily_deaths": daily_dth,
                    "total_admitted": cum_adm,
                    "total_deaths": cum_deaths,
                    "total_discharged": max(cum_adm - cum_deaths - 5, 0),
                }
            )
    pd.DataFrame(dengue_rows).to_parquet(silver_dir / "dengue_zones_daily.parquet", index=False)

    # 3. Run DuckDBLagEngine in tmp_path
    engine = DuckDBLagEngine(silver_dir=silver_dir, gold_dir=gold_dir)
    daily_df, lags_df = engine.build_gold_tables(save_parquet=True)

    assert (gold_dir / "zone_daily_climate_dengue.parquet").exists()
    assert (gold_dir / "zone_lag_correlations.parquet").exists()

    GoldDailySchema.validate(daily_df)
    GoldLagCorrelationSchema.validate(lags_df)

    assert sorted(lags_df["zone_name"].unique().tolist()) == sorted(GOLD_ZONES_LIST)
    for zone in GOLD_ZONES_LIST:
        offsets = sorted(lags_df[lags_df["zone_name"] == zone]["lag_days"].tolist())
        assert offsets == list(range(29))
