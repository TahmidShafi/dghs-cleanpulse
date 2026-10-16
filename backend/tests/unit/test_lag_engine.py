"""Unit tests for the Gold Layer DuckDB Spatiotemporal Lag Engine."""

from __future__ import annotations

from pathlib import Path

import duckdb

from cleanpulse.gold.lag_engine import (
    GOLD_ZONES_LIST,
    DuckDBLagEngine,
    GoldDailySchema,
    GoldLagCorrelationSchema,
)

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
GOLD_DAILY_PARQUET = DATA_DIR / "gold" / "zone_daily_climate_dengue.parquet"
GOLD_LAGS_PARQUET = DATA_DIR / "gold" / "zone_lag_correlations.parquet"


def test_gold_parquet_artifacts_exist_and_schemas_valid() -> None:
    """Verify materialized Gold parquet files exist and validate against Pandera schemas."""
    assert GOLD_DAILY_PARQUET.exists(), f"Missing {GOLD_DAILY_PARQUET}"
    assert GOLD_LAGS_PARQUET.exists(), f"Missing {GOLD_LAGS_PARQUET}"

    con = duckdb.connect(":memory:")
    daily_df = con.execute(
        f"SELECT * FROM read_parquet('{GOLD_DAILY_PARQUET.as_posix()}')"
    ).fetchdf()
    lags_df = con.execute(f"SELECT * FROM read_parquet('{GOLD_LAGS_PARQUET.as_posix()}')").fetchdf()

    assert len(daily_df) == 1800, f"Expected 1800 daily rows, got {len(daily_df)}"
    assert len(lags_df) == 319, (
        f"Expected 319 lag correlation rows (11 zones * 29 offsets), got {len(lags_df)}"
    )

    GoldDailySchema.validate(daily_df)
    GoldLagCorrelationSchema.validate(lags_df)


def test_gold_zones_and_lag_coverage() -> None:
    """Verify all 10 DGHS zones plus 'National' have complete 0..28 lag coverage."""
    con = duckdb.connect(":memory:")
    lags_df = con.execute(f"SELECT * FROM read_parquet('{GOLD_LAGS_PARQUET.as_posix()}')").fetchdf()

    unique_zones = sorted(lags_df["zone_name"].unique().tolist())
    expected_zones = sorted(GOLD_ZONES_LIST)
    assert unique_zones == expected_zones, (
        f"Mismatch in zone list: {unique_zones} vs {expected_zones}"
    )

    for zone in GOLD_ZONES_LIST:
        zone_subset = lags_df[lags_df["zone_name"] == zone]
        assert len(zone_subset) == 29
        offsets = sorted(zone_subset["lag_days"].tolist())
        assert offsets == list(range(29))


def test_national_peak_correlation_in_biological_window() -> None:
    """Verify that empirical correlation peaks within the biological window (14..18 days)."""
    con = duckdb.connect(":memory:")
    lags_df = con.execute(
        f"""
        SELECT lag_days, pearson_r_humidity, pearson_r_precip
        FROM read_parquet('{GOLD_LAGS_PARQUET.as_posix()}')
        WHERE zone_name = 'National'
        ORDER BY pearson_r_humidity DESC
        """
    ).fetchdf()

    peak_lag_humidity = int(lags_df.iloc[0]["lag_days"])
    peak_r_humidity = float(lags_df.iloc[0]["pearson_r_humidity"])

    assert 14 <= peak_lag_humidity <= 18, (
        f"Expected national humidity peak lag between 14..18 days, got {peak_lag_humidity}"
    )
    assert peak_r_humidity > 0.5, f"Expected strong positive correlation, got {peak_r_humidity}"


def test_duckdb_lag_engine_idempotent_build() -> None:
    """Verify DuckDBLagEngine can execute end-to-end and idempotently re-materialize Gold tables."""
    engine = DuckDBLagEngine()
    daily_df, lags_df = engine.build_gold_tables()

    assert len(daily_df) == 1800
    assert len(lags_df) == 319
    assert "zone_name" in daily_df.columns
    assert "precip_7d_avg" in daily_df.columns
