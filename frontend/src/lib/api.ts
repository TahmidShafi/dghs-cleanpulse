/**
 * DGHS-CleanPulse Hybrid Client Data Fetcher
 *
 * 1. Tries live FastAPI + DuckDB backend at NEXT_PUBLIC_API_URL or http://localhost:8000.
 * 2. Falls back to /data/fallback_snapshot.json if backend is offline, and surfaces
 *    the snapshot's generated_at_utc in the Header.
 * 3. Loads /data/demo_synthetic_fault_injection.json for the clearly labelled Tab 1
 *    synthetic validation demo (never mixed into real data/).
 */

import {
  AuditAnomaliesResponse,
  DashboardState,
  FallbackSnapshotData,
  HistoricalWeeklyResponse,
  PipelineHealthResponse,
  SurveillanceSummaryResponse,
  SyntheticDemoData,
  WeatherDailyResponse,
  WeeklyLagCorrelationsResponse,
} from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let cachedFallbackSnapshot: FallbackSnapshotData | null = null;
let cachedSyntheticDemo: SyntheticDemoData | null = null;

async function fetchWithTimeout(
  url: string,
  timeoutMs = 1500
): Promise<Response> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      signal: controller.signal,
      cache: "no-store",
    });
    clearTimeout(id);
    return response;
  } catch (error) {
    clearTimeout(id);
    throw error;
  }
}

export async function getFallbackSnapshot(): Promise<FallbackSnapshotData> {
  if (cachedFallbackSnapshot) {
    return cachedFallbackSnapshot;
  }

  const res = await fetch("/data/fallback_snapshot.json", { cache: "default" });
  if (!res.ok) {
    throw new Error(`Failed to load fallback snapshot: HTTP ${res.status}`);
  }
  const data = (await res.json()) as FallbackSnapshotData;
  cachedFallbackSnapshot = data;
  return data;
}

export async function getSyntheticDemoData(): Promise<SyntheticDemoData | null> {
  if (cachedSyntheticDemo) {
    return cachedSyntheticDemo;
  }
  try {
    const res = await fetch("/data/demo_synthetic_fault_injection.json", {
      cache: "default",
    });
    if (!res.ok) {
      return null;
    }
    const data = (await res.json()) as SyntheticDemoData;
    cachedSyntheticDemo = data;
    return data;
  } catch {
    return null;
  }
}

function buildWeeklyLagsFromSnapshot(
  snapshot: FallbackSnapshotData,
  scope: string,
  variable: string
): WeeklyLagCorrelationsResponse | null {
  const rows = (snapshot.lag_correlations_weekly || [])
    .filter((r) => r.scope === scope && r.variable === variable)
    .map(({ lag_weeks, transform, rho, n, null_reason }) => ({
      lag_weeks,
      transform,
      rho,
      n,
      null_reason,
    }));

  if (rows.length === 0) {
    return null;
  }

  const weeklyMeta = snapshot.historical_weekly_by_scope?.[scope];
  return {
    scope,
    variable,
    source_label:
      weeklyMeta?.source_label ||
      snapshot.surveillance_summary.historical?.source_label ||
      "secondary source: transcribed from DGHS daily press releases (unverified transcription by third party)",
    dataset_doi:
      weeklyMeta?.dataset_doi ||
      snapshot.surveillance_summary.historical?.dataset_doi ||
      "10.17632/z5mvwrfgsz.1",
    rows,
  };
}

export async function fetchInitialDashboardData(): Promise<DashboardState> {
  const syntheticDemo = await getSyntheticDemoData();

  try {
    const [
      summaryRes,
      weatherRes,
      anomaliesRes,
      healthRes,
      histWeeklyRes,
      weeklyLagsRes,
    ] = await Promise.all([
      fetchWithTimeout(`${API_BASE_URL}/v1/surveillance/summary`),
      fetchWithTimeout(`${API_BASE_URL}/v1/weather/daily?zone=National`),
      fetchWithTimeout(
        `${API_BASE_URL}/v1/audit/anomalies?severity=ALL&anomaly_type=ALL`
      ),
      fetchWithTimeout(`${API_BASE_URL}/v1/health/pipeline`),
      fetchWithTimeout(`${API_BASE_URL}/v1/historical/weekly?scope=National`),
      fetchWithTimeout(
        `${API_BASE_URL}/v1/analytics/lag-correlations?scope=National&variable=weekly_precip_mm`
      ),
    ]);

    if (
      !summaryRes.ok ||
      !weatherRes.ok ||
      !anomaliesRes.ok ||
      !healthRes.ok ||
      !histWeeklyRes.ok ||
      !weeklyLagsRes.ok
    ) {
      throw new Error("One or more backend endpoints returned non-200");
    }

    const summary: SurveillanceSummaryResponse = await summaryRes.json();
    const weather: WeatherDailyResponse = await weatherRes.json();
    const anomalies: AuditAnomaliesResponse = await anomaliesRes.json();
    const health: PipelineHealthResponse = await healthRes.json();
    const historicalWeekly: HistoricalWeeklyResponse =
      await histWeeklyRes.json();
    const weeklyLags: WeeklyLagCorrelationsResponse =
      await weeklyLagsRes.json();

    return {
      summary,
      weather,
      historicalWeekly,
      weeklyLags,
      anomalies,
      health,
      syntheticDemo,
      isLive: true,
      isFallback: false,
      snapshotGeneratedAt: null,
      snapshotGitCommit: null,
      lastUpdated: new Date().toLocaleTimeString(),
    };
  } catch (err) {
    console.warn(
      "FastAPI backend unreachable; falling back to static snapshot:",
      err
    );
    const snapshot = await getFallbackSnapshot();

    return {
      summary: snapshot.surveillance_summary,
      weather:
        snapshot.weather_by_zone["National"] ||
        Object.values(snapshot.weather_by_zone)[0],
      historicalWeekly:
        snapshot.historical_weekly_by_scope?.["National"] ?? null,
      weeklyLags: buildWeeklyLagsFromSnapshot(
        snapshot,
        "National",
        "weekly_precip_mm"
      ),
      anomalies: snapshot.audit_anomalies,
      health: snapshot.pipeline_health,
      syntheticDemo,
      isLive: false,
      isFallback: true,
      snapshotGeneratedAt:
        snapshot.metadata.generated_at_utc || snapshot.metadata.extracted_at,
      snapshotGitCommit: snapshot.metadata.git_commit ?? null,
      lastUpdated: new Date().toLocaleTimeString(),
    };
  }
}

export async function fetchZoneWeatherData(
  zone: string,
  isLive: boolean
): Promise<WeatherDailyResponse> {
  if (isLive) {
    try {
      const res = await fetchWithTimeout(
        `${API_BASE_URL}/v1/weather/daily?zone=${encodeURIComponent(zone)}`
      );
      if (res.ok) {
        return (await res.json()) as WeatherDailyResponse;
      }
    } catch (err) {
      console.warn(
        "Live weather query failed, falling back to static snapshot:",
        err
      );
    }
  }

  const snapshot = await getFallbackSnapshot();
  if (snapshot.weather_by_zone[zone]) {
    return snapshot.weather_by_zone[zone];
  }
  return (
    snapshot.weather_by_zone["National"] ||
    Object.values(snapshot.weather_by_zone)[0]
  );
}

export async function fetchHistoricalScopeData(
  scope: string,
  variable: string,
  isLive: boolean
): Promise<{
  weekly: HistoricalWeeklyResponse | null;
  lags: WeeklyLagCorrelationsResponse | null;
}> {
  if (isLive) {
    try {
      const [weeklyRes, lagsRes] = await Promise.all([
        fetchWithTimeout(
          `${API_BASE_URL}/v1/historical/weekly?scope=${encodeURIComponent(scope)}`
        ),
        fetchWithTimeout(
          `${API_BASE_URL}/v1/analytics/lag-correlations?scope=${encodeURIComponent(
            scope
          )}&variable=${encodeURIComponent(variable)}`
        ),
      ]);
      if (weeklyRes.ok && lagsRes.ok) {
        return {
          weekly: (await weeklyRes.json()) as HistoricalWeeklyResponse,
          lags: (await lagsRes.json()) as WeeklyLagCorrelationsResponse,
        };
      }
    } catch (err) {
      console.warn(
        "Live historical query failed, falling back to static snapshot:",
        err
      );
    }
  }

  const snapshot = await getFallbackSnapshot();
  return {
    weekly: snapshot.historical_weekly_by_scope?.[scope] ?? null,
    lags: buildWeeklyLagsFromSnapshot(snapshot, scope, variable),
  };
}
