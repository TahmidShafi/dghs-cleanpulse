"""Unit tests for the 64-District Spatial Crosswalk, Open-Meteo Batch Client,
and 180-Day Silver Backfill.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from cleanpulse.bronze.weather_client import (
    DEFAULT_SILVER_WEATHER_PARQUET,
    OpenMeteoWeatherClient,
    WeatherDailySilverSchema,
)
from cleanpulse.silver.firewall import CANONICAL_ZONES, DGHSDivisionSilverSchema
from cleanpulse.silver.spatial_crosswalk import (
    DEFAULT_CROSSWALK_PATH,
    DistrictCrosswalkSilverSchema,
    get_district_by_id,
    get_districts_for_zone,
    load_district_crosswalk,
)
from cleanpulse.silver.timeseries_backfill import (
    DEFAULT_SILVER_ZONES_PARQUET,
    ZONE_TARGET_ADMISSIONS,
    EpidemiologicalBackfillGenerator,
)


def test_spatial_crosswalk_structure_and_coverage() -> None:
    """Verify that the crosswalk contains exactly 64 unique districts covering all 10 DGHS zones."""
    assert DEFAULT_CROSSWALK_PATH.exists()
    df = load_district_crosswalk(DEFAULT_CROSSWALK_PATH)

    # 1. Row count and uniqueness
    assert len(df) == 64
    assert df["district_id"].nunique() == 64
    assert df["district_name"].nunique() == 64

    # 2. Schema compliance
    DistrictCrosswalkSilverSchema.validate(df, lazy=True)

    # 3. All 10 DGHS surveillance reporting zones must be present
    unique_zones = set(df["dghs_reporting_zone"].unique())
    assert set(CANONICAL_ZONES).issubset(unique_zones)
    assert len(unique_zones) == 10

    # 4. Dhaka Metro split validation
    dncc_districts = get_districts_for_zone("DNCC", df)
    dscc_districts = get_districts_for_zone("DSCC", df)
    out_of_cc_districts = get_districts_for_zone("Dhaka (Out of CC)", df)

    assert dncc_districts == ["dhaka_north"]
    assert dscc_districts == ["dhaka_south"]
    assert "madaripur_shariatpur" in out_of_cc_districts
    assert len(out_of_cc_districts) == 11

    # 5. Coordinate integrity within Bangladesh geographical envelope
    dhaka_north = get_district_by_id("dhaka_north", df)
    dhaka_south = get_district_by_id("dhaka_south", df)

    assert 20.5 <= dhaka_north["latitude"] <= 26.8
    assert 88.0 <= dhaka_north["longitude"] <= 92.8
    assert 20.5 <= dhaka_south["latitude"] <= 26.8
    assert 88.0 <= dhaka_south["longitude"] <= 92.8

    # Ensure Dhaka North and South have distinct coordinates
    assert dhaka_north["latitude"] != dhaka_south["latitude"]


def test_weather_batch_client_deterministic_offline_fallback(tmp_path: Path) -> None:
    """Verify that offline climate generator produces 11,520 valid rows passing schema."""
    crosswalk_df = load_district_crosswalk()
    client = OpenMeteoWeatherClient(batch_size=16)

    # Run in force_offline mode to test deterministic generator
    output_parquet = tmp_path / "test_weather.parquet"
    df = client.fetch_climate_data(
        crosswalk_df=crosswalk_df,
        force_offline=True,
        output_parquet=output_parquet,
    )

    # 1. Validate file creation
    assert output_parquet.exists()

    # 2. Validate dimensions: 64 districts * 180 days = 11,520 rows
    assert len(df) == 64 * 180
    assert df["district_id"].nunique() == 64
    assert df["date"].nunique() == 180
    assert df["date"].min() == "2026-04-18"
    assert df["date"].max() == "2026-10-14"

    # 3. Strict schema validation
    WeatherDailySilverSchema.validate(df, lazy=True)

    # 4. Value boundaries
    assert df["temperature_2m_mean"].min() >= -5.0
    assert df["temperature_2m_mean"].max() <= 55.0
    assert df["precipitation_sum"].min() >= 0.0
    assert df["relative_humidity_2m_mean"].min() >= 0.0
    assert df["relative_humidity_2m_mean"].max() <= 100.0


def test_silver_weather_parquet_persisted_dataset() -> None:
    """Verify that data/silver/weather_districts_daily.parquet contains 11,520 valid rows."""
    assert DEFAULT_SILVER_WEATHER_PARQUET.exists()
    df = pd.read_parquet(DEFAULT_SILVER_WEATHER_PARQUET)

    assert len(df) == 11520
    assert df["district_id"].nunique() == 64
    assert df["date"].nunique() == 180
    assert set(df["dghs_reporting_zone"].unique()) == set(CANONICAL_ZONES)

    WeatherDailySilverSchema.validate(df, lazy=True)


def test_timeseries_backfill_generator_reproducibility_and_targets(tmp_path: Path) -> None:
    """Verify that 180-day backfill produces 1,800 rows ending on 105,316 cumulative cases."""
    assert DEFAULT_SILVER_WEATHER_PARQUET.exists()
    weather_df = pd.read_parquet(DEFAULT_SILVER_WEATHER_PARQUET)

    generator = EpidemiologicalBackfillGenerator(
        weather_parquet_path=DEFAULT_SILVER_WEATHER_PARQUET
    )
    out_parquet = tmp_path / "test_zones_daily.parquet"

    df = generator.generate_180_day_series(
        weather_df_or_path=weather_df,
        random_seed=42,
        output_parquet=out_parquet,
    )

    # 1. Output file and row count (10 zones * 180 days = 1,800 rows)
    assert out_parquet.exists()
    assert len(df) == 1800
    assert df["zone_name"].nunique() == 10
    assert df["report_date"].nunique() == 180

    # 2. Strict Silver Schema
    DGHSDivisionSilverSchema.validate(df, lazy=True)

    # 3. Final day (2026-10-14) anchors
    final_day = df[df["report_date"] == "2026-10-14"]
    assert len(final_day) == 10

    # National cumulative admissions must equal exactly 105,316
    national_admissions = final_day["total_admitted"].sum()
    assert national_admissions == 105316

    # Verify each individual zone target matches the 2026 DGHS ground truth
    for zone_name, expected_total in ZONE_TARGET_ADMISSIONS.items():
        zone_final = final_day[final_day["zone_name"] == zone_name].iloc[0]
        assert zone_final["total_admitted"] == expected_total

    # 4. Monotonicity checks
    for zone_name in CANONICAL_ZONES:
        zone_series = df[df["zone_name"] == zone_name].sort_values("report_date")

        # total_admitted is monotonically non-decreasing
        admitted = zone_series["total_admitted"].to_numpy()
        assert (np.diff(admitted) >= 0).all()

        # total_deaths is monotonically non-decreasing
        deaths = zone_series["total_deaths"].to_numpy()
        assert (np.diff(deaths) >= 0).all()

        # Discharges physical constraint: total_discharged <= total_admitted - total_deaths
        discharged = zone_series["total_discharged"].to_numpy()
        assert (discharged <= (admitted - deaths)).all()

    # 5. Deterministic reproducibility: calling with same seed produces identical results
    df_repeat = generator.generate_180_day_series(
        weather_df_or_path=weather_df,
        random_seed=42,
        output_parquet=None,
    )
    pd.testing.assert_frame_equal(df, df_repeat)


def test_silver_dengue_zones_persisted_dataset() -> None:
    """Verify that data/silver/dengue_zones_daily.parquet contains 1,800 valid rows."""
    assert DEFAULT_SILVER_ZONES_PARQUET.exists()
    df = pd.read_parquet(DEFAULT_SILVER_ZONES_PARQUET)

    assert len(df) == 1800
    assert df["zone_name"].nunique() == 10
    assert df["report_date"].nunique() == 180

    DGHSDivisionSilverSchema.validate(df, lazy=True)

    final_day = df[df["report_date"] == "2026-10-14"]
    assert final_day["total_admitted"].sum() == 105316
