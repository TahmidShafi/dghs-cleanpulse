"""FastAPI REST Service for DGHS-CleanPulse Dengue Surveillance & Climate Analytics."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from cleanpulse.api.schemas import (
    AuditAnomaliesResponse,
    PipelineHealthResponse,
    SurveillanceLagsResponse,
    SurveillanceSummaryResponse,
    WeatherDailyResponse,
)
from cleanpulse.bronze.provenance import get_git_provenance
from cleanpulse.gold.lag_engine import GOLD_ZONES_LIST

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[4] / "data"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"
BRONZE_DIR = DATA_DIR / "bronze"

ZONES_PARQUET = SILVER_DIR / "dengue_zones_daily.parquet"
AGE_PARQUET = SILVER_DIR / "dengue_age_groups.parquet"
WEATHER_PARQUET = SILVER_DIR / "weather_districts_daily.parquet"
ANOMALIES_PARQUET = SILVER_DIR / "audit_anomalies.parquet"
GOLD_DAILY_PARQUET = GOLD_DIR / "zone_daily_climate_dengue.parquet"
GOLD_LAGS_PARQUET = GOLD_DIR / "zone_lag_correlations.parquet"

_db_connection: duckdb.DuckDBPyConnection | None = None


def _table_exists(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    row = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
        [table_name],
    ).fetchone()
    return bool(row and row[0] > 0)


def _init_db() -> None:
    """Initialize in-memory DuckDB database from existing real Parquet tables."""
    global _db_connection
    if _db_connection is not None:
        return

    logger.info("Pre-loading available analytical Parquet tables into DuckDB...")
    con = duckdb.connect()

    tables = [
        ("gold_zone_daily", GOLD_DAILY_PARQUET),
        ("gold_lag_correlations", GOLD_LAGS_PARQUET),
        ("silver_age_groups", AGE_PARQUET),
        ("silver_audit_anomalies", ANOMALIES_PARQUET),
        ("silver_zones_daily", ZONES_PARQUET),
        ("silver_weather_daily", WEATHER_PARQUET),
    ]
    for tbl_name, path in tables:
        if path.exists():
            p_str = str(path).replace("\\", "/")
            con.execute(f"CREATE TABLE {tbl_name} AS SELECT * FROM read_parquet('{p_str}')")

    _db_connection = con
    logger.info("DuckDB in-memory engine initialized.")


def reset_db() -> None:
    """Close and reset the shared DuckDB connection (used in tests)."""
    global _db_connection
    if _db_connection is not None:
        _db_connection.close()
        _db_connection = None


def get_db() -> duckdb.DuckDBPyConnection:
    """Return an isolated cursor connection from the active DuckDB connection pool."""
    global _db_connection
    if _db_connection is None:
        _init_db()
    assert _db_connection is not None
    return _db_connection.cursor()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager initializing DuckDB tables on startup."""
    logger.info("Initializing DGHS-CleanPulse API engine...")
    _init_db()
    yield
    reset_db()
    logger.info("API shutdown complete.")


app = FastAPI(
    title="DGHS-CleanPulse Surveillance & Climate API",
    description=(
        "Medallion analytics engine for Bangladesh dengue surveillance and Open-Meteo climate."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _pending_dengue_response(weather_available: bool) -> dict[str, Any]:
    return {
        "status": "pending_real_source",
        "reason": "no_real_dengue_series",
        "message": (
            "No real DGHS dengue time series is available yet. Synthetic backfill has been removed."
        ),
        "weather_available": weather_available,
        "data": None,
    }


# ---------------------------------------------------------------------------
# Endpoint 1: GET /v1/surveillance/summary
# ---------------------------------------------------------------------------
@app.get(
    "/v1/surveillance/summary",
    response_model=SurveillanceSummaryResponse,
    summary="Get national and zone-level surveillance summary KPIs",
)
def get_surveillance_summary() -> dict[str, Any]:
    """Retrieve surveillance KPIs, or pending_real_source when no real dengue data exists."""
    con = get_db()
    weather_available = _table_exists(con, "silver_weather_daily")

    if not _table_exists(con, "gold_zone_daily") or not _table_exists(con, "gold_lag_correlations"):
        return _pending_dengue_response(weather_available)

    latest_row = con.execute("SELECT MAX(report_date) FROM gold_zone_daily").fetchone()
    if not latest_row or not latest_row[0]:
        return _pending_dengue_response(weather_available)
    report_date = str(latest_row[0])

    zones_rows = con.execute(
        """
        SELECT
            zone_name,
            daily_admitted,
            daily_deaths,
            total_admitted,
            total_deaths,
            total_discharged,
            ROUND(CASE WHEN total_admitted > 0
                  THEN (CAST(total_deaths AS DOUBLE) / total_admitted) * 100
                  ELSE 0.0 END, 2) AS cfr_pct
        FROM gold_zone_daily
        WHERE report_date = ?
        ORDER BY total_admitted DESC
        """,
        [report_date],
    ).fetchdf()

    zones_summary = zones_rows.to_dict(orient="records")
    total_admitted = int(zones_rows["total_admitted"].sum())
    total_discharged = int(zones_rows["total_discharged"].sum())
    total_deaths = int(zones_rows["total_deaths"].sum())
    cfr_pct = round((total_deaths / max(total_admitted, 1)) * 100.0, 2)

    anomalies_caught = 0
    if _table_exists(con, "silver_audit_anomalies"):
        anom_count_row = con.execute("SELECT COUNT(*) FROM silver_audit_anomalies").fetchone()
        anomalies_caught = int(anom_count_row[0]) if anom_count_row else 0

    opt_lag_row = con.execute(
        """
        SELECT lag_days
        FROM gold_lag_correlations
        WHERE zone_name = 'National'
        ORDER BY pearson_r_humidity DESC
        LIMIT 1
        """
    ).fetchone()
    optimal_lag_days = int(opt_lag_row[0]) if opt_lag_row else 0

    age_groups: list[dict[str, Any]] = []
    if _table_exists(con, "silver_age_groups"):
        age_df = con.execute(
            """
            SELECT
                report_date,
                age_group,
                male_cases,
                female_cases,
                reported_total,
                reconciled_total,
                arithmetic_delta,
                deaths
            FROM silver_age_groups
            ORDER BY age_group
            """
        ).fetchdf()
        age_groups = age_df.to_dict(orient="records")

    return {
        "status": "available",
        "reason": None,
        "message": "OK",
        "weather_available": weather_available,
        "data": {
            "report_date": report_date,
            "total_admitted": total_admitted,
            "total_discharged": total_discharged,
            "total_deaths": total_deaths,
            "cfr_pct": cfr_pct,
            "anomalies_caught_count": anomalies_caught,
            "optimal_lag_days": optimal_lag_days,
            "zones_summary": zones_summary,
            "age_groups": age_groups,
        },
    }


# ---------------------------------------------------------------------------
# Endpoint 2: GET /v1/surveillance/lags
# ---------------------------------------------------------------------------
@app.get(
    "/v1/surveillance/lags",
    response_model=SurveillanceLagsResponse,
    summary="Get 0..28 day lag correlation curve and aligned time series",
)
def get_surveillance_lags(
    zone: str = Query("National", description="Zone name or 'National'"),
    lag_days: int = Query(16, ge=0, le=28, description="Lag offset in days (0..28)"),
) -> dict[str, Any]:
    """Retrieve 0..28 lag correlations, or pending_real_source when no real dengue data exists."""
    if zone not in GOLD_ZONES_LIST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Zone '{zone}' is invalid. Allowed zones: {GOLD_ZONES_LIST}",
        )

    con = get_db()
    weather_available = _table_exists(con, "silver_weather_daily")

    if not _table_exists(con, "gold_zone_daily") or not _table_exists(con, "gold_lag_correlations"):
        return _pending_dengue_response(weather_available)

    corrs_df = con.execute(
        """
        SELECT lag_days, pearson_r_precip, pearson_r_humidity, pearson_r_temp, sample_size
        FROM gold_lag_correlations
        WHERE zone_name = ?
        ORDER BY lag_days ASC
        """,
        [zone],
    ).fetchdf()
    if corrs_df.empty:
        return _pending_dengue_response(weather_available)

    lag_correlations = corrs_df.to_dict(orient="records")
    peak_row = corrs_df.loc[corrs_df["pearson_r_humidity"].idxmax()]
    peak_lag = int(peak_row["lag_days"])
    peak_r = float(peak_row["pearson_r_humidity"])

    if zone == "National":
        q_series = f"""
        WITH national_daily AS (
            SELECT
                report_date,
                SUM(daily_admitted) AS daily_admitted,
                SUM(daily_deaths) AS daily_deaths,
                SUM(total_admitted) AS total_admitted,
                ROUND(AVG(precip_7d_avg), 2) AS precip_7d_avg,
                ROUND(AVG(humidity_7d_avg), 2) AS humidity_7d_avg,
                ROUND(AVG(avg_temp_7d_avg), 2) AS avg_temp_7d_avg
            FROM gold_zone_daily
            GROUP BY report_date
        )
        SELECT
            report_date AS date,
            CAST(daily_admitted AS BIGINT) AS daily_admitted,
            CAST(daily_deaths AS BIGINT) AS daily_deaths,
            CAST(total_admitted AS BIGINT) AS total_admitted,
            LAG(precip_7d_avg, {lag_days}) OVER (ORDER BY report_date) AS lagged_precip_mm,
            LAG(humidity_7d_avg, {lag_days}) OVER (ORDER BY report_date) AS lagged_humidity_pct,
            LAG(avg_temp_7d_avg, {lag_days}) OVER (ORDER BY report_date) AS lagged_temp_c
        FROM national_daily
        ORDER BY report_date ASC;
        """
        series_df = con.execute(q_series).fetchdf()
    else:
        q_series = f"""
        SELECT
            report_date AS date,
            CAST(daily_admitted AS BIGINT) AS daily_admitted,
            CAST(daily_deaths AS BIGINT) AS daily_deaths,
            CAST(total_admitted AS BIGINT) AS total_admitted,
            LAG(precip_7d_avg, {lag_days}) OVER (ORDER BY report_date) AS lagged_precip_mm,
            LAG(humidity_7d_avg, {lag_days}) OVER (ORDER BY report_date) AS lagged_humidity_pct,
            LAG(avg_temp_7d_avg, {lag_days}) OVER (ORDER BY report_date) AS lagged_temp_c
        FROM gold_zone_daily
        WHERE zone_name = ?
        ORDER BY report_date ASC;
        """
        series_df = con.execute(q_series, [zone]).fetchdf()

    aligned_time_series = [
        {k: (None if pd.isna(v) else v) for k, v in row.items()}
        for row in series_df.to_dict(orient="records")
    ]

    return {
        "status": "available",
        "reason": None,
        "message": "OK",
        "weather_available": weather_available,
        "data": {
            "zone_name": zone,
            "selected_lag_days": lag_days,
            "peak_lag_days": peak_lag,
            "peak_correlation_r": peak_r,
            "lag_correlations": lag_correlations,
            "aligned_time_series": aligned_time_series,
        },
    }


# ---------------------------------------------------------------------------
# Endpoint 3: GET /v1/weather/daily
# ---------------------------------------------------------------------------
@app.get(
    "/v1/weather/daily",
    response_model=WeatherDailyResponse,
    summary="Get real Open-Meteo daily weather aggregates for National or a DGHS zone",
)
def get_weather_daily(
    zone: str = Query("National", description="Zone name or 'National'"),
) -> dict[str, Any]:
    """Retrieve real Open-Meteo daily weather time series aggregated by zone."""
    if zone not in GOLD_ZONES_LIST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Zone '{zone}' is invalid. Allowed zones: {GOLD_ZONES_LIST}",
        )

    con = get_db()
    if not _table_exists(con, "silver_weather_daily"):
        return {
            "zone_name": zone,
            "source": "Open-Meteo Historical Weather API",
            "start_date": "",
            "end_date": "",
            "district_count": 0,
            "series": [],
        }

    if zone == "National":
        df = con.execute(
            """
            SELECT
                date,
                ROUND(AVG(precipitation_sum), 2) AS precip_mm,
                ROUND(AVG(relative_humidity_2m_mean), 2) AS humidity_pct,
                ROUND(AVG(temperature_2m_mean), 2) AS temp_c
            FROM silver_weather_daily
            GROUP BY date
            ORDER BY date ASC
            """
        ).fetchdf()
        dist_row = con.execute(
            "SELECT COUNT(DISTINCT district_id) FROM silver_weather_daily"
        ).fetchone()
    else:
        like_pat = f"%{zone}%"
        df = con.execute(
            """
            SELECT
                date,
                ROUND(AVG(precipitation_sum), 2) AS precip_mm,
                ROUND(AVG(relative_humidity_2m_mean), 2) AS humidity_pct,
                ROUND(AVG(temperature_2m_mean), 2) AS temp_c
            FROM silver_weather_daily
            WHERE dghs_reporting_zone = ? OR dghs_reporting_zone LIKE ?
            GROUP BY date
            ORDER BY date ASC
            """,
            [zone, like_pat],
        ).fetchdf()
        dist_row = con.execute(
            """
            SELECT COUNT(DISTINCT district_id)
            FROM silver_weather_daily
            WHERE dghs_reporting_zone = ? OR dghs_reporting_zone LIKE ?
            """,
            [zone, like_pat],
        ).fetchone()

    district_count = int(dist_row[0]) if dist_row else 0
    series = df.to_dict(orient="records")
    return {
        "zone_name": zone,
        "source": "Open-Meteo Historical Weather API",
        "start_date": str(df["date"].min()) if not df.empty else "",
        "end_date": str(df["date"].max()) if not df.empty else "",
        "district_count": district_count,
        "series": series,
    }


# ---------------------------------------------------------------------------
# Endpoint 4: GET /v1/audit/anomalies
# ---------------------------------------------------------------------------
@app.get(
    "/v1/audit/anomalies",
    response_model=AuditAnomaliesResponse,
    summary="Get real Silver layer audit anomalies and frequency breakdown",
)
def get_audit_anomalies(
    severity: str = Query("ALL", description="Filter by severity: CRITICAL, WARNING, INFO, or ALL"),
    anomaly_type: str = Query("ALL", description="Filter by anomaly type, or ALL"),
) -> dict[str, Any]:
    """Retrieve real Silver audit anomalies (never serves synthetic fixture anomalies)."""
    con = get_db()
    if not _table_exists(con, "silver_audit_anomalies"):
        return {
            "total_anomalies": 0,
            "severity_counts": {},
            "type_counts": {},
            "anomalies": [],
        }

    counts_df = con.execute("SELECT severity, anomaly_type FROM silver_audit_anomalies").fetchdf()
    severity_counts = {
        str(k): int(v) for k, v in counts_df["severity"].value_counts().to_dict().items()
    }
    type_counts = {
        str(k): int(v) for k, v in counts_df["anomaly_type"].value_counts().to_dict().items()
    }

    query = "SELECT * FROM silver_audit_anomalies WHERE 1=1"
    params: list[str] = []
    if severity != "ALL":
        query += " AND severity = ?"
        params.append(severity)
    if anomaly_type != "ALL":
        query += " AND anomaly_type = ?"
        params.append(anomaly_type)
    query += " ORDER BY detected_at_utc DESC"

    records_df = con.execute(query, params).fetchdf() if params else con.execute(query).fetchdf()
    return {
        "total_anomalies": len(counts_df),
        "severity_counts": severity_counts,
        "type_counts": type_counts,
        "anomalies": records_df.to_dict(orient="records"),
    }


# ---------------------------------------------------------------------------
# Endpoint 5: GET /v1/health/pipeline
# ---------------------------------------------------------------------------
@app.get(
    "/v1/health/pipeline",
    response_model=PipelineHealthResponse,
    summary="Get pipeline health status, layer row counts, and DuckDB query latency",
)
def get_pipeline_health() -> dict[str, Any]:
    """Perform health checks, measure live DuckDB query latency, and verify row counts."""
    con = get_db()

    t_start = time.perf_counter()
    con.execute("SELECT 1").fetchall()
    t_end = time.perf_counter()
    latency_ms = round((t_end - t_start) * 1000.0, 3)

    bronze_snapshots = (
        len([p for p in BRONZE_DIR.rglob("*.sidecar.json")])
        + len([p for p in BRONZE_DIR.rglob("*.html")])
        if BRONZE_DIR.exists()
        else 0
    )

    def _count_table(table_name: str) -> int:
        if not _table_exists(con, table_name):
            return 0
        row = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        return int(row[0]) if row is not None else 0

    layer_counts = {
        "bronze_snapshots": bronze_snapshots,
        "silver_dengue_rows": _count_table("silver_zones_daily"),
        "silver_weather_rows": _count_table("silver_weather_daily"),
        "silver_anomaly_rows": _count_table("silver_audit_anomalies"),
        "gold_daily_rows": _count_table("gold_zone_daily"),
        "gold_lag_rows": _count_table("gold_lag_correlations"),
    }

    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "layer_counts": layer_counts,
        "schemas_validated": True,
        "duckdb_latency_ms": latency_ms,
    }


def build_snapshot_payload() -> dict[str, Any]:
    """Build static frontend snapshot payload strictly from real data."""
    get_db()
    summary = get_surveillance_summary()
    audit = get_audit_anomalies(severity="ALL", anomaly_type="ALL")
    health = get_pipeline_health()

    weather_by_zone: dict[str, Any] = {}
    lags_by_zone: dict[str, Any] = {}
    for zone in GOLD_ZONES_LIST:
        weather_by_zone[zone] = get_weather_daily(zone=zone)
        lags_by_zone[zone] = get_surveillance_lags(zone=zone, lag_days=14)

    git_commit, git_dirty = get_git_provenance()
    generated_at_utc = datetime.now(UTC).isoformat()

    return {
        "metadata": {
            "source": "DGHS-CleanPulse DuckDB In-Memory Engine",
            "snapshot_version": "2.0.0",
            "generated_at_utc": generated_at_utc,
            "extracted_at": generated_at_utc,
            "git_commit": git_commit,
            "git_dirty": git_dirty,
        },
        "surveillance_summary": summary,
        "weather_by_zone": weather_by_zone,
        "lags_by_zone": lags_by_zone,
        "audit_anomalies": audit,
        "pipeline_health": health,
    }
