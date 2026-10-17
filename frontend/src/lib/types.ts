/**
 * DGHS-CleanPulse Type Definitions
 * Typed representations of the FastAPI REST Service schemas.
 */

export interface ZoneSummaryItem {
  zone_name: string;
  daily_admitted: number;
  daily_deaths: number;
  total_admitted: number;
  total_deaths: number;
  total_discharged: number;
  cfr_pct: number;
}

export interface AgeCohortItem {
  report_date: string;
  age_group: string;
  male_cases: number;
  female_cases: number;
  reported_total: number;
  reconciled_total: number;
  arithmetic_delta: number;
  deaths: number;
}

export interface SurveillanceSummaryResponse {
  report_date: string;
  total_admitted: number;
  total_discharged: number;
  total_deaths: number;
  cfr_pct: number;
  anomalies_caught_count: number;
  optimal_lag_days: number;
  zones_summary: ZoneSummaryItem[];
  age_groups: AgeCohortItem[];
}

export interface LagCorrelationItem {
  lag_days: number;
  pearson_r_precip: number;
  pearson_r_humidity: number;
  pearson_r_temp: number;
  sample_size: number;
}

export interface AlignedTimeSeriesItem {
  date: string;
  daily_admitted: number;
  daily_deaths: number;
  total_admitted: number;
  lagged_precip_mm: number | null;
  lagged_humidity_pct: number | null;
  lagged_temp_c: number | null;
}

export interface SurveillanceLagsResponse {
  zone_name: string;
  selected_lag_days: number;
  peak_lag_days: number;
  peak_correlation_r: number;
  lag_correlations: LagCorrelationItem[];
  aligned_time_series: AlignedTimeSeriesItem[];
}

export interface AnomalyItem {
  anomaly_id: string;
  detected_at_utc: string;
  table_name: string;
  row_key: string;
  raw_value: string;
  repaired_value: string;
  anomaly_type: string;
  severity: "CRITICAL" | "WARNING" | "INFO" | string;
  explanation: string;
}

export interface AuditAnomaliesResponse {
  total_anomalies: number;
  severity_counts: Record<string, number>;
  type_counts: Record<string, number>;
  anomalies: AnomalyItem[];
}

export interface PipelineHealthResponse {
  status: string;
  timestamp: string;
  layer_counts: {
    bronze_snapshots: number;
    silver_dengue_rows: number;
    silver_weather_rows: number;
    silver_anomaly_rows: number;
    gold_daily_rows: number;
    gold_lag_rows: number;
    [key: string]: number;
  };
  schemas_validated: boolean;
  duckdb_latency_ms: number;
}

export interface FallbackSnapshotData {
  metadata: {
    source: string;
    snapshot_version: string;
    extracted_at: string;
  };
  surveillance_summary: SurveillanceSummaryResponse;
  lags_by_zone: Record<string, SurveillanceLagsResponse>;
  audit_anomalies: AuditAnomaliesResponse;
  pipeline_health: PipelineHealthResponse;
}

export interface DashboardState {
  summary: SurveillanceSummaryResponse;
  lags: SurveillanceLagsResponse;
  anomalies: AuditAnomaliesResponse;
  health: PipelineHealthResponse;
  isLive: boolean;
  isFallback: boolean;
  lastUpdated: string;
}
