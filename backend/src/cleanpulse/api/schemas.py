"""Pydantic v2 Schemas for the DGHS-CleanPulse FastAPI REST Service."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# 1. Surveillance Summary Models
# ---------------------------------------------------------------------------
class ZoneSummaryItem(BaseModel):
    """Zone-level surveillance summary statistics."""

    model_config = ConfigDict(frozen=True)

    zone_name: str = Field(..., description="Canonical DGHS reporting zone name")
    daily_admitted: int = Field(..., ge=0, description="Admissions on latest report date")
    daily_deaths: int = Field(..., ge=0, description="Deaths on latest report date")
    total_admitted: int = Field(..., ge=0, description="Cumulative admissions")
    total_deaths: int = Field(..., ge=0, description="Cumulative deaths")
    total_discharged: int = Field(..., ge=0, description="Cumulative discharges")
    cfr_pct: float = Field(..., ge=0.0, le=100.0, description="Case Fatality Rate percentage")


class AgeCohortItem(BaseModel):
    """Sanitized 5-year age cohort surveillance record."""

    model_config = ConfigDict(frozen=True)

    report_date: str = Field(..., description="Report ISO date string")
    age_group: str = Field(..., description="Canonical 5-year age group")
    male_cases: int = Field(..., ge=0)
    female_cases: int = Field(..., ge=0)
    reported_total: int = Field(..., ge=0)
    reconciled_total: int = Field(..., ge=0)
    arithmetic_delta: int = Field(
        ...,
        description="Discrepancy (reported - reconciled). Row 21-25 is +10; clean is 0.",
    )
    deaths: int = Field(..., ge=0)


class SurveillanceSummaryResponse(BaseModel):
    """National and zone-level surveillance executive summary KPIs."""

    model_config = ConfigDict(frozen=True)

    report_date: str = Field(..., description="Latest surveillance report date (YYYY-MM-DD)")
    total_admitted: int = Field(..., ge=0, description="National cumulative admissions")
    total_discharged: int = Field(..., ge=0, description="National cumulative discharges")
    total_deaths: int = Field(..., ge=0, description="National cumulative deaths")
    cfr_pct: float = Field(..., ge=0.0, le=100.0, description="National Case Fatality Rate (%)")
    anomalies_caught_count: int = Field(..., ge=0, description="Count of upstream raw anomalies")
    optimal_lag_days: int = Field(
        ...,
        ge=0,
        le=28,
        description="Lag offset (days) with highest national climate-case correlation",
    )
    zones_summary: list[ZoneSummaryItem] = Field(..., description="Breakdown across 10 DGHS zones")
    age_groups: list[AgeCohortItem] = Field(..., description="17 sanitized age group cohorts")


# ---------------------------------------------------------------------------
# 2. Lag & Climate Correlation Models
# ---------------------------------------------------------------------------
class LagCorrelationItem(BaseModel):
    """Empirical Pearson correlation coefficient at a specific lag offset."""

    model_config = ConfigDict(frozen=True)

    lag_days: int = Field(..., ge=0, le=28)
    pearson_r_precip: float = Field(..., ge=-1.0, le=1.0)
    pearson_r_humidity: float = Field(..., ge=-1.0, le=1.0)
    pearson_r_temp: float = Field(..., ge=-1.0, le=1.0)
    sample_size: int = Field(..., gt=0)


class AlignedTimeSeriesItem(BaseModel):
    """Daily time series entry with climate features shifted by chosen lag."""

    model_config = ConfigDict(frozen=True)

    date: str = Field(..., description="Report date YYYY-MM-DD")
    daily_admitted: int = Field(..., ge=0)
    daily_deaths: int = Field(..., ge=0)
    total_admitted: int = Field(..., ge=0)
    lagged_precip_mm: float | None = Field(None, ge=0.0)
    lagged_humidity_pct: float | None = Field(None, ge=0.0, le=100.0)
    lagged_temp_c: float | None = Field(None, ge=-5.0, le=55.0)


class SurveillanceLagsResponse(BaseModel):
    """Spatiotemporal lag correlation response with aligned time series."""

    model_config = ConfigDict(frozen=True)

    zone_name: str = Field(..., description="Selected zone or 'National'")
    selected_lag_days: int = Field(..., ge=0, le=28)
    peak_lag_days: int = Field(..., ge=0, le=28)
    peak_correlation_r: float = Field(..., ge=-1.0, le=1.0)
    lag_correlations: list[LagCorrelationItem] = Field(
        ...,
        description="29 correlation points for lag offsets 0..28",
    )
    aligned_time_series: list[AlignedTimeSeriesItem] = Field(
        ...,
        description="180-day time series with climate indicators shifted by selected_lag_days",
    )


# ---------------------------------------------------------------------------
# 3. Audit Anomaly Models
# ---------------------------------------------------------------------------
class AnomalyItem(BaseModel):
    """Structured record of an upstream data anomaly flagged by Silver firewall."""

    model_config = ConfigDict(frozen=True)

    anomaly_id: str
    detected_at_utc: str
    table_name: str
    row_key: str
    raw_value: str
    repaired_value: str
    anomaly_type: str
    severity: str
    explanation: str


class AuditAnomaliesResponse(BaseModel):
    """Audit anomaly response containing logs and frequency aggregates."""

    model_config = ConfigDict(frozen=True)

    total_anomalies: int = Field(..., ge=0)
    severity_counts: dict[str, int] = Field(..., description="Counts grouped by severity")
    type_counts: dict[str, int] = Field(..., description="Counts grouped by anomaly type")
    anomalies: list[AnomalyItem] = Field(..., description="List of audit anomaly records")


# ---------------------------------------------------------------------------
# 4. Pipeline Health Models
# ---------------------------------------------------------------------------
class PipelineLayerCounts(BaseModel):
    """Row counts across Medallion architecture layers."""

    model_config = ConfigDict(frozen=True)

    bronze_snapshots: int = Field(..., ge=0)
    silver_dengue_rows: int = Field(..., ge=0)
    silver_weather_rows: int = Field(..., ge=0)
    silver_anomaly_rows: int = Field(..., ge=0)
    gold_daily_rows: int = Field(..., ge=0)
    gold_lag_rows: int = Field(..., ge=0)


class PipelineHealthResponse(BaseModel):
    """System and pipeline diagnostic health check response."""

    model_config = ConfigDict(frozen=True)

    status: str = Field(..., description="'healthy' or 'degraded'")
    timestamp: str = Field(..., description="Current UTC timestamp")
    layer_counts: PipelineLayerCounts
    schemas_validated: bool = Field(..., description="True if all schemas pass validation")
    duckdb_latency_ms: float = Field(..., ge=0.0, description="Live DuckDB query latency (ms)")
