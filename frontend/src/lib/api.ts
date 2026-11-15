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
  PipelineHealthResponse,
  SurveillanceSummaryResponse,
  SyntheticDemoData,
  WeatherDailyResponse,
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

export async function fetchInitialDashboardData(): Promise<DashboardState> {
  const syntheticDemo = await getSyntheticDemoData();

  try {
    const [summaryRes, weatherRes, anomaliesRes, healthRes] = await Promise.all([
      fetchWithTimeout(`${API_BASE_URL}/v1/surveillance/summary`),
      fetchWithTimeout(`${API_BASE_URL}/v1/weather/daily?zone=National`),
      fetchWithTimeout(
        `${API_BASE_URL}/v1/audit/anomalies?severity=ALL&anomaly_type=ALL`
      ),
      fetchWithTimeout(`${API_BASE_URL}/v1/health/pipeline`),
    ]);

    if (!summaryRes.ok || !weatherRes.ok || !anomaliesRes.ok || !healthRes.ok) {
      throw new Error("One or more backend endpoints returned non-200");
    }

    const summary: SurveillanceSummaryResponse = await summaryRes.json();
    const weather: WeatherDailyResponse = await weatherRes.json();
    const anomalies: AuditAnomaliesResponse = await anomaliesRes.json();
    const health: PipelineHealthResponse = await healthRes.json();

    return {
      summary,
      weather,
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
