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

export interface HistoricalSummaryBlock {
  window: string;
  report_date_start: string;
  report_date_end: string;
  total_cases: number;
  source_label: string;
  dataset_doi: string;
}

export interface SurveillanceSummaryResponse {
  status: "available" | "pending_real_source";
  reason: string | null;
  message: string;
  weather_available: boolean;
  data: SurveillanceSummaryData | null;
  historical?: HistoricalSummaryBlock | null;
}

export interface HistoricalWeeklyPoint {
  week_start: string;
  iso_week: string;
  weekly_cases: number;
  weekly_precip_mm: number;
  weekly_temp_c: number;
  weekly_humidity_pct: number;
}

export interface HistoricalWeeklyResponse {
  scope: string;
  source_label: string;
  dataset_doi: string;
  window: string;
  series: HistoricalWeeklyPoint[];
}

export interface WeeklyLagRow {
  lag_weeks: number;
  transform: string;
  rho: number | null;
  n: number;
  null_reason: string | null;
}

export interface WeeklyLagCorrelationsResponse {
  scope: string;
  variable: string;
  source_label: string;
  dataset_doi: string;
  rows: WeeklyLagRow[];
}

export interface SnapshotWeeklyLagRow extends WeeklyLagRow {
  scope: string;
  variable: string;
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
  historical_weekly_by_scope?: Record<string, HistoricalWeeklyResponse>;
  lag_correlations_weekly?: SnapshotWeeklyLagRow[];
  audit_anomalies: AuditAnomaliesResponse;
  pipeline_health: PipelineHealthResponse;
}

export interface DashboardState {
  summary: SurveillanceSummaryResponse;
  weather: WeatherDailyResponse;
  historicalWeekly: HistoricalWeeklyResponse | null;
  weeklyLags: WeeklyLagCorrelationsResponse | null;
  anomalies: AuditAnomaliesResponse;
  health: PipelineHealthResponse;
  syntheticDemo: SyntheticDemoData | null;
  isLive: boolean;
  isFallback: boolean;
  snapshotGeneratedAt: string | null;
  snapshotGitCommit: string | null;
  lastUpdated: string;
}
