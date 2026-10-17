/**
 * DGHS-CleanPulse Hybrid Client Data Fetcher
 *
 * Implements a Zero-Cold-Start hybrid architecture:
 * 1. Tries live FastAPI + DuckDB backend at NEXT_PUBLIC_API_URL or http://localhost:8000.
 * 2. Uses an aggressive 1500ms AbortController timeout.
 * 3. Gracefully and seamlessly falls back to /data/fallback_snapshot.json if backend is offline.
 */

import {
  AuditAnomaliesResponse,
  DashboardState,
  FallbackSnapshotData,
  PipelineHealthResponse,
  SurveillanceLagsResponse,
  SurveillanceSummaryResponse,
} from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let cachedFallbackSnapshot: FallbackSnapshotData | null = null;

async function fetchWithTimeout(url: string, timeoutMs = 1500): Promise<Response> {
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

  // Attempt to fetch static snapshot from public folder
  const res = await fetch("/data/fallback_snapshot.json", { cache: "default" });
  if (!res.ok) {
    throw new Error(`Failed to load fallback snapshot: HTTP ${res.status}`);
  }
  const data = (await res.json()) as FallbackSnapshotData;
  cachedFallbackSnapshot = data;
  return data;
}

export async function fetchInitialDashboardData(): Promise<DashboardState> {
  try {
    const [summaryRes, lagsRes, anomaliesRes, healthRes] = await Promise.all([
      fetchWithTimeout(`${API_BASE_URL}/v1/surveillance/summary`),
      fetchWithTimeout(`${API_BASE_URL}/v1/surveillance/lags?zone=National&lag_days=14`),
      fetchWithTimeout(`${API_BASE_URL}/v1/audit/anomalies?severity=ALL&anomaly_type=ALL`),
      fetchWithTimeout(`${API_BASE_URL}/v1/health/pipeline`),
    ]);

    if (!summaryRes.ok || !lagsRes.ok || !anomaliesRes.ok || !healthRes.ok) {
      throw new Error("One or more backend endpoints returned non-200");
    }

    const summary: SurveillanceSummaryResponse = await summaryRes.json();
    const lags: SurveillanceLagsResponse = await lagsRes.json();
    const anomalies: AuditAnomaliesResponse = await anomaliesRes.json();
    const health: PipelineHealthResponse = await healthRes.json();

    return {
      summary,
      lags,
      anomalies,
      health,
      isLive: true,
      isFallback: false,
      lastUpdated: new Date().toLocaleTimeString(),
    };
  } catch (err) {
    console.warn("FastAPI backend unreachable or cold; engaging zero-cold-start static fallback mode:", err);
    const snapshot = await getFallbackSnapshot();

    return {
      summary: snapshot.surveillance_summary,
      lags: snapshot.lags_by_zone["National"] || Object.values(snapshot.lags_by_zone)[0],
      anomalies: snapshot.audit_anomalies,
      health: snapshot.pipeline_health,
      isLive: false,
      isFallback: true,
      lastUpdated: new Date().toLocaleTimeString(),
    };
  }
}

export async function fetchZoneLagData(
  zone: string,
  lagDays: number,
  isLiveMode = true
): Promise<SurveillanceLagsResponse> {
  if (isLiveMode) {
    try {
      const url = `${API_BASE_URL}/v1/surveillance/lags?zone=${encodeURIComponent(
        zone
      )}&lag_days=${lagDays}`;
      const res = await fetchWithTimeout(url, 2000);
      if (res.ok) {
        return (await res.json()) as SurveillanceLagsResponse;
      }
    } catch (e) {
      console.warn("Live lag query failed; using fallback slice:", e);
    }
  }

  // Fallback mode computation
  const snapshot = await getFallbackSnapshot();
  const zoneData = snapshot.lags_by_zone[zone] || snapshot.lags_by_zone["National"];

  if (!zoneData) {
    throw new Error(`Zone ${zone} not found in fallback snapshot`);
  }

  // Dynamically shift series if lagDays differs
  const baseSeries = zoneData.aligned_time_series;
  const shiftedSeries = baseSeries.map((item, idx) => {
    const shiftIdx = idx - (lagDays - zoneData.selected_lag_days);
    const src = shiftIdx >= 0 && shiftIdx < baseSeries.length ? baseSeries[shiftIdx] : null;

    return {
      date: item.date,
      daily_admitted: item.daily_admitted,
      daily_deaths: item.daily_deaths,
      total_admitted: item.total_admitted,
      lagged_precip_mm: src ? src.lagged_precip_mm : null,
      lagged_humidity_pct: src ? src.lagged_humidity_pct : null,
      lagged_temp_c: src ? src.lagged_temp_c : null,
    };
  });

  return {
    ...zoneData,
    selected_lag_days: lagDays,
    aligned_time_series: shiftedSeries,
  };
}
