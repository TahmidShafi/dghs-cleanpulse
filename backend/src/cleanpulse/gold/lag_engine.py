"""Gold Layer DuckDB Spatiotemporal Lag & Analytics Engine.

Computes 7-day rolling climate indicators, 0-to-28 day spatiotemporal window lags,
and empirical Pearson correlation coefficients linking lagged weather factors to daily
dengue admissions across all 10 DGHS zones and the National aggregate.

Materializes and validates two Gold Parquet tables:
  1. data/gold/zone_daily_climate_dengue.parquet (1,800 rows)
  2. data/gold/zone_lag_correlations.parquet (319 rows: 11 zones * 29 lag offsets)
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import pandas as pd  # type: ignore[import-untyped]
import pandera.pandas as pa

from cleanpulse.silver.firewall import CANONICAL_ZONES
from cleanpulse.silver.spatial_crosswalk import get_district_zone_bridge

logger = logging.getLogger(__name__)

DEFAULT_SILVER_DIR = Path(__file__).resolve().parents[4] / "data" / "silver"
DEFAULT_GOLD_DIR = Path(__file__).resolve().parents[4] / "data" / "gold"

GOLD_ZONES_LIST = [*CANONICAL_ZONES, "National"]

# ---------------------------------------------------------------------------
# Pandera Gold Validation Schemas
# ---------------------------------------------------------------------------
GoldDailySchema = pa.DataFrameSchema(
    columns={
        "report_date": pa.Column(str, nullable=False),
        "zone_name": pa.Column(
            str,
            pa.Check.isin(CANONICAL_ZONES),
            nullable=False,
        ),
        "daily_admitted": pa.Column(pa.Int64, pa.Check.ge(0), nullable=False),
        "daily_deaths": pa.Column(pa.Int64, pa.Check.ge(0), nullable=False),
        "total_admitted": pa.Column(pa.Int64, pa.Check.ge(0), nullable=False),
        "total_deaths": pa.Column(pa.Int64, pa.Check.ge(0), nullable=False),
        "total_discharged": pa.Column(pa.Int64, pa.Check.ge(0), nullable=False),
        "avg_temp_c": pa.Column(float, pa.Check.in_range(-5.0, 55.0), nullable=False),
        "total_precip_mm": pa.Column(float, pa.Check.ge(0.0), nullable=False),
        "avg_humidity_pct": pa.Column(float, pa.Check.in_range(0.0, 100.0), nullable=False),
        "avg_temp_7d_avg": pa.Column(float, pa.Check.in_range(-5.0, 55.0), nullable=False),
        "precip_7d_avg": pa.Column(float, pa.Check.ge(0.0), nullable=False),
        "humidity_7d_avg": pa.Column(float, pa.Check.in_range(0.0, 100.0), nullable=False),
    },
    strict=True,
    coerce=True,
)

GoldLagCorrelationSchema = pa.DataFrameSchema(
    columns={
        "zone_name": pa.Column(
            str,
            pa.Check.isin(GOLD_ZONES_LIST),
            nullable=False,
        ),
        "lag_days": pa.Column(pa.Int64, pa.Check.in_range(0, 28), nullable=False),
        "pearson_r_precip": pa.Column(float, pa.Check.in_range(-1.0, 1.0), nullable=False),
        "pearson_r_humidity": pa.Column(float, pa.Check.in_range(-1.0, 1.0), nullable=False),
        "pearson_r_temp": pa.Column(float, pa.Check.in_range(-1.0, 1.0), nullable=False),
        "sample_size": pa.Column(pa.Int64, pa.Check.gt(0), nullable=False),
    },
    strict=True,
    coerce=True,
)


class DuckDBLagEngine:
    """Spatiotemporal analytical engine computing rolling climate statistics and lag features."""

    def __init__(
        self,
        silver_dir: Path | str | None = None,
        gold_dir: Path | str | None = None,
    ) -> None:
        """Initialize the lag engine with source silver and destination gold directories."""
        self.silver_dir = Path(silver_dir) if silver_dir is not None else DEFAULT_SILVER_DIR
        self.gold_dir = Path(gold_dir) if gold_dir is not None else DEFAULT_GOLD_DIR
        self.weather_parquet = self.silver_dir / "weather_districts_daily.parquet"
        self.dengue_parquet = self.silver_dir / "dengue_zones_daily.parquet"
        self.gold_daily_parquet = self.gold_dir / "zone_daily_climate_dengue.parquet"
        self.gold_lags_parquet = self.gold_dir / "zone_lag_correlations.parquet"

    def build_gold_tables(
        self,
        save_parquet: bool = True,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Compute zone-level rolling weather features and 0..28 day lag correlation matrices.

        Args:
            save_parquet: If True, writes validated tables to data/gold/.

        Returns:
            Tuple of (zone_daily_df, zone_lag_correlations_df).
        """
        if not self.weather_parquet.exists():
            raise FileNotFoundError(f"Weather silver parquet not found at: {self.weather_parquet}")
        if not self.dengue_parquet.exists():
            raise FileNotFoundError(f"Dengue silver parquet not found at: {self.dengue_parquet}")

        self.gold_dir.mkdir(parents=True, exist_ok=True)

        bridge_df = get_district_zone_bridge()
        con = duckdb.connect()
        con.register("bridge", bridge_df)

        weather_p_str = str(self.weather_parquet).replace("\\", "/")
        dengue_p_str = str(self.dengue_parquet).replace("\\", "/")

        # 1. Zone-level daily weather aggregation and 7-day rolling window functions
        q_daily = f"""
        CREATE OR REPLACE TABLE gold_daily AS
        WITH zone_weather_daily AS (
            SELECT 
                w.date AS report_date,
                b.zone_name,
                ROUND(AVG(w.temperature_2m_mean), 2) AS avg_temp_c,
                ROUND(AVG(w.precipitation_sum), 2) AS total_precip_mm,
                ROUND(AVG(w.relative_humidity_2m_mean), 2) AS avg_humidity_pct
            FROM read_parquet('{weather_p_str}') w
            JOIN bridge b ON w.district_id = b.district_id
            GROUP BY w.date, b.zone_name
        ),
        zone_weather_rolling AS (
            SELECT 
                report_date,
                zone_name,
                avg_temp_c,
                total_precip_mm,
                avg_humidity_pct,
                ROUND(AVG(avg_temp_c) OVER (
                    PARTITION BY zone_name
                    ORDER BY report_date
                    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
                ), 2) AS avg_temp_7d_avg,
                ROUND(AVG(total_precip_mm) OVER (
                    PARTITION BY zone_name
                    ORDER BY report_date
                    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
                ), 2) AS precip_7d_avg,
                ROUND(AVG(avg_humidity_pct) OVER (
                    PARTITION BY zone_name
                    ORDER BY report_date
                    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
                ), 2) AS humidity_7d_avg
            FROM zone_weather_daily
        )
        SELECT 
            d.report_date,
            d.zone_name,
            CAST(d.daily_admitted AS BIGINT) AS daily_admitted,
            CAST(d.daily_deaths AS BIGINT) AS daily_deaths,
            CAST(d.total_admitted AS BIGINT) AS total_admitted,
            CAST(d.total_deaths AS BIGINT) AS total_deaths,
            CAST(d.total_discharged AS BIGINT) AS total_discharged,
            zw.avg_temp_c,
            zw.total_precip_mm,
            zw.avg_humidity_pct,
            zw.avg_temp_7d_avg,
            zw.precip_7d_avg,
            zw.humidity_7d_avg
        FROM read_parquet('{dengue_p_str}') d
        JOIN zone_weather_rolling zw 
            ON d.report_date = zw.report_date AND d.zone_name = zw.zone_name
        ORDER BY d.report_date, d.zone_name;
        """
        con.execute(q_daily)
        df_daily = con.execute("SELECT * FROM gold_daily ORDER BY report_date, zone_name").fetchdf()

        # 2. National daily aggregation
        q_national = """
        CREATE OR REPLACE TABLE national_daily AS
        SELECT 
            report_date,
            'National' AS zone_name,
            SUM(daily_admitted) AS daily_admitted,
            SUM(daily_deaths) AS daily_deaths,
            SUM(total_admitted) AS total_admitted,
            SUM(total_deaths) AS total_deaths,
            SUM(total_discharged) AS total_discharged,
            ROUND(AVG(avg_temp_c), 2) AS avg_temp_c,
            ROUND(AVG(total_precip_mm), 2) AS total_precip_mm,
            ROUND(AVG(avg_humidity_pct), 2) AS avg_humidity_pct,
            ROUND(AVG(avg_temp_7d_avg), 2) AS avg_temp_7d_avg,
            ROUND(AVG(precip_7d_avg), 2) AS precip_7d_avg,
            ROUND(AVG(humidity_7d_avg), 2) AS humidity_7d_avg
        FROM gold_daily
        GROUP BY report_date;
        """
        con.execute(q_national)

        con.execute("""
        CREATE OR REPLACE TABLE combined_daily AS
        SELECT * FROM gold_daily
        UNION ALL
        SELECT * FROM national_daily;
        """)

        # 3. Compute 0..28 lag offsets and empirical Pearson correlation coefficients
        lag_dfs: list[pd.DataFrame] = []
        for k in range(29):
            q_lag = f"""
            WITH lagged AS (
                SELECT 
                    zone_name,
                    daily_admitted,
                    LAG(precip_7d_avg, {k}) OVER (
                        PARTITION BY zone_name ORDER BY report_date
                    ) AS lag_precip,
                    LAG(humidity_7d_avg, {k}) OVER (
                        PARTITION BY zone_name ORDER BY report_date
                    ) AS lag_humidity,
                    LAG(avg_temp_7d_avg, {k}) OVER (
                        PARTITION BY zone_name ORDER BY report_date
                    ) AS lag_temp
                FROM combined_daily
            )
            SELECT 
                zone_name,
                CAST({k} AS BIGINT) AS lag_days,
                ROUND(COALESCE(corr(daily_admitted, lag_precip), 0.0), 4) AS pearson_r_precip,
                ROUND(COALESCE(corr(daily_admitted, lag_humidity), 0.0), 4) AS pearson_r_humidity,
                ROUND(COALESCE(corr(daily_admitted, lag_temp), 0.0), 4) AS pearson_r_temp,
                CAST(COUNT(*) FILTER (WHERE lag_precip IS NOT NULL) AS BIGINT) AS sample_size
            FROM lagged
            GROUP BY zone_name
            ORDER BY zone_name;
            """
            df_k = con.execute(q_lag).fetchdf()
            lag_dfs.append(df_k)

        df_lags = pd.concat(lag_dfs, ignore_index=True)

        # Ensure canonical zone sort order followed by lag_days
        zone_sort_order = {z: i for i, z in enumerate(GOLD_ZONES_LIST)}
        df_lags["zone_rank"] = df_lags["zone_name"].map(zone_sort_order)
        df_lags = df_lags.sort_values(by=["zone_rank", "lag_days"]).drop(columns=["zone_rank"])
        df_lags = df_lags.reset_index(drop=True)

        # 4. Strict Pandera Validation
        validated_daily = GoldDailySchema.validate(df_daily, lazy=True)
        validated_lags = GoldLagCorrelationSchema.validate(df_lags, lazy=True)

        if save_parquet:
            validated_daily.to_parquet(self.gold_daily_parquet, index=False)
            validated_lags.to_parquet(self.gold_lags_parquet, index=False)
            logger.info("Exported Gold daily table to: %s", self.gold_daily_parquet)
            logger.info("Exported Gold lag correlations table to: %s", self.gold_lags_parquet)

        con.close()
        return validated_daily, validated_lags

    def get_optimal_lag(self, zone_name: str = "National") -> int:
        """Find the lag offset with the highest positive humidity/rainfall correlation."""
        if not self.gold_lags_parquet.exists():
            self.build_gold_tables(save_parquet=True)

        con = duckdb.connect()
        p_str = str(self.gold_lags_parquet).replace("\\", "/")
        row = con.execute(
            f"""
            SELECT lag_days, pearson_r_humidity 
            FROM read_parquet('{p_str}')
            WHERE zone_name = ?
            ORDER BY pearson_r_humidity DESC
            LIMIT 1
            """,
            [zone_name],
        ).fetchone()
        con.close()
        return int(row[0]) if row else 16
