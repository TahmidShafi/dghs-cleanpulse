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
        description="Discrepancy (reported - reconciled).",
    )
    deaths: int = Field(..., ge=0)


class SurveillanceSummaryData(BaseModel):
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
    zones_summary: list[ZoneSummaryItem] = Field(..., description="Breakdown across DGHS zones")
    age_groups: list[AgeCohortItem] = Field(..., description="Sanitized age group cohorts")


class SurveillanceSummaryResponse(BaseModel):
    """Typed envelope for GET /v1/surveillance/summary."""

    model_config = ConfigDict(frozen=True)

    status: str = Field(..., description="'available' or 'pending_real_source'")
    reason: str | None = Field(None, description="Machine-readable reason when pending")
    message: str = Field(..., description="Human-readable status message")
    weather_available: bool = Field(..., description="Whether real weather data is available")
    data: SurveillanceSummaryData | None = Field(None)


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


class SurveillanceLagsData(BaseModel):
    """Spatiotemporal lag correlation payload with aligned time series."""

    model_config = ConfigDict(frozen=True)

    zone_name: str = Field(..., description="Selected zone or 'National'")
    selected_lag_days: int = Field(..., ge=0, le=28)
    peak_lag_days: int = Field(..., ge=0, le=28)
    peak_correlation_r: float = Field(..., ge=-1.0, le=1.0)
    lag_correlations: list[LagCorrelationItem]
    aligned_time_series: list[AlignedTimeSeriesItem]


class SurveillanceLagsResponse(BaseModel):
    """Typed envelope for GET /v1/surveillance/lags."""

    model_config = ConfigDict(frozen=True)

    status: str = Field(..., description="'available' or 'pending_real_source'")
    reason: str | None = Field(None, description="Machine-readable reason when pending")
    message: str = Field(..., description="Human-readable status message")
    weather_available: bool = Field(..., description="Whether real weather data is available")
    data: SurveillanceLagsData | None = Field(None)


# ---------------------------------------------------------------------------
# 3. Real Weather Daily Series Models
# ---------------------------------------------------------------------------
class WeatherDailyPoint(BaseModel):
    """Daily aggregated Open-Meteo weather record."""

    model_config = ConfigDict(frozen=True)

    date: str
    precip_mm: float = Field(..., ge=0.0)
    humidity_pct: float = Field(..., ge=0.0, le=100.0)
    temp_c: float = Field(..., ge=-5.0, le=55.0)


class WeatherDailyResponse(BaseModel):
    """Real Open-Meteo weather time series for National or a DGHS zone."""

    model_config = ConfigDict(frozen=True)

    zone_name: str
    source: str
    start_date: str
    end_date: str
    district_count: int = Field(..., ge=0)
    series: list[WeatherDailyPoint]


# ---------------------------------------------------------------------------
# 4. Audit Anomaly Models
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
    """Audit anomaly response containing real Silver logs and frequency aggregates."""

    model_config = ConfigDict(frozen=True)

    total_anomalies: int = Field(..., ge=0)
    severity_counts: dict[str, int] = Field(..., description="Counts grouped by severity")
    type_counts: dict[str, int] = Field(..., description="Counts grouped by anomaly type")
    anomalies: list[AnomalyItem] = Field(..., description="List of audit anomaly records")


# ---------------------------------------------------------------------------
# 5. Pipeline Health Models
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
    """Operational telemetry and DuckDB query latency response."""

    model_config = ConfigDict(frozen=True)

    status: str
    timestamp: str
    layer_counts: PipelineLayerCounts
    schemas_validated: bool
    duckdb_latency_ms: float = Field(..., ge=0.0)
