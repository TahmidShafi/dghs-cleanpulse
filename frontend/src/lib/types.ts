/**
 * DGHS-CleanPulse Type Definitions
 * Typed representations of the FastAPI REST Service schemas and static snapshots.
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

export interface SurveillanceSummaryData {
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

export interface SurveillanceSummaryResponse {
  status: "available" | "pending_real_source";
  reason: string | null;
  message: string;
  weather_available: boolean;
  data: SurveillanceSummaryData | null;
}

export interface WeatherDailyPoint {
  date: string;
  precip_mm: number;
  humidity_pct: number;
  temp_c: number;
}

export interface WeatherDailyResponse {
  zone_name: string;
  source: string;
  start_date: string;
  end_date: string;
  district_count: number;
  series: WeatherDailyPoint[];
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

export interface SyntheticDemoData {
  synthetic: boolean;
  fixture_path: string;
  fixture_sha256: string;
  git_commit: string | null;
  git_dirty: boolean | null;
  disclaimer: string;
  age_groups: AgeCohortItem[];
  audit_anomalies: AuditAnomaliesResponse;
}

export interface FallbackSnapshotData {
  metadata: {
    source: string;
    snapshot_version: string;
    generated_at_utc: string;
    extracted_at: string;
    git_commit: string | null;
    git_dirty: boolean | null;
  };
  surveillance_summary: SurveillanceSummaryResponse;
  weather_by_zone: Record<string, WeatherDailyResponse>;
  audit_anomalies: AuditAnomaliesResponse;
  pipeline_health: PipelineHealthResponse;
}

export interface DashboardState {
  summary: SurveillanceSummaryResponse;
  weather: WeatherDailyResponse;
  anomalies: AuditAnomaliesResponse;
  health: PipelineHealthResponse;
  syntheticDemo: SyntheticDemoData | null;
  isLive: boolean;
  isFallback: boolean;
  snapshotGeneratedAt: string | null;
  lastUpdated: string;
}
