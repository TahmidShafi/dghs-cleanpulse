"use client";

import React, { useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { KpiCards } from "@/components/KpiCards";
import { FirewallInspector } from "@/components/FirewallInspector";
import { LagExplorer } from "@/components/LagExplorer";
import {
  fetchInitialDashboardData,
  fetchZoneWeatherData,
} from "@/lib/api";
import { DashboardState, WeatherDailyResponse } from "@/lib/types";
import { CloudRain, Database, ShieldCheck } from "lucide-react";

export default function Home() {
  const [dashboard, setDashboard] = useState<DashboardState | null>(null);
  const [activeTab, setActiveTab] = useState<"firewall" | "lags">("firewall");
  const [currentZone, setCurrentZone] = useState<string>("National");
  const [weatherData, setWeatherData] = useState<WeatherDailyResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isWeatherLoading, setIsWeatherLoading] = useState<boolean>(false);

  const loadData = async (refresh = false) => {
    if (refresh) setIsRefreshing(true);

    try {
      const state = await fetchInitialDashboardData();
      setDashboard(state);
      setWeatherData(state.weather);
    } catch (e) {
      console.error("Dashboard failed to initialize:", e);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    let isMounted = true;
    if (typeof window !== "undefined" && window.location.hash.includes("lag")) {
      queueMicrotask(() => {
        if (isMounted) setActiveTab("lags");
      });
    }

    fetchInitialDashboardData()
      .then((state) => {
        if (isMounted) {
          setDashboard(state);
          setWeatherData(state.weather);
          setIsLoading(false);
        }
      })
      .catch((e) => {
        console.error("Dashboard failed to initialize:", e);
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleZoneChange = async (newZone: string) => {
    setCurrentZone(newZone);
    if (!dashboard) return;
    setIsWeatherLoading(true);
    try {
      const data = await fetchZoneWeatherData(newZone, dashboard.isLive);
      setWeatherData(data);
    } catch (e) {
      console.error("Failed to load zone weather data:", e);
    } finally {
      setIsWeatherLoading(false);
    }
  };

  if (isLoading || !dashboard) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-6 text-slate-100">
        <div className="w-12 h-12 rounded-xl bg-teal-500/20 border border-teal-500/40 flex items-center justify-center animate-pulse mb-4">
          <Database className="w-6 h-6 text-teal-400" />
        </div>
        <h2 className="text-lg font-bold">Initializing DGHS-CleanPulse Console...</h2>
        <p className="text-xs text-slate-400 mt-1">Connecting to DuckDB Engine &amp; Pandera Firewall</p>
      </div>
    );
  }

  const demoAnomalies = dashboard.syntheticDemo?.audit_anomalies ?? dashboard.anomalies;
  const demoAgeGroups = dashboard.syntheticDemo?.age_groups ?? [];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Header
        isLive={dashboard.isLive}
        isFallback={dashboard.isFallback}
        snapshotGeneratedAt={dashboard.snapshotGeneratedAt}
        lastUpdated={dashboard.lastUpdated}
        isRefreshing={isRefreshing}
        onRefresh={() => loadData(true)}
      />

      <main className="max-w-7xl mx-auto w-full px-4 lg:px-8 py-6 flex-1 space-y-6">
        <KpiCards
          summary={dashboard.summary}
          weather={dashboard.weather}
          health={dashboard.health}
        />

        <div className="flex border-b border-slate-800 gap-2 pt-2">
          <button
            id="tab-firewall"
            onClick={() => setActiveTab("firewall")}
            className={`flex items-center gap-2 px-5 py-3 text-sm font-bold border-b-2 transition cursor-pointer ${
              activeTab === "firewall"
                ? "border-teal-400 text-teal-300 bg-teal-500/5 rounded-t-lg"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <ShieldCheck className="w-4 h-4 text-teal-400" />
            <span>Validation demo (synthetic fault-injection input)</span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
              Synthetic Demo
            </span>
          </button>

          <button
            id="tab-lags"
            onClick={() => setActiveTab("lags")}
            className={`flex items-center gap-2 px-5 py-3 text-sm font-bold border-b-2 transition cursor-pointer ${
              activeTab === "lags"
                ? "border-blue-400 text-blue-300 bg-blue-500/5 rounded-t-lg"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <CloudRain className="w-4 h-4 text-blue-400" />
            <span>Real Weather Explorer (Dengue Pending)</span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30">
              64 Districts
            </span>
          </button>
        </div>

        {activeTab === "firewall" && (
          <div id="content-tab-firewall">
            <FirewallInspector
              anomaliesData={demoAnomalies}
              ageGroups={demoAgeGroups}
              fixtureSha256={dashboard.syntheticDemo?.fixture_sha256}
            />
          </div>
        )}

        {activeTab === "lags" && weatherData && (
          <div id="content-tab-lags">
            <LagExplorer
              currentZone={currentZone}
              weatherData={weatherData}
              onZoneChange={handleZoneChange}
              isLoading={isWeatherLoading}
            />
          </div>
        )}
      </main>

      <footer className="border-t border-slate-900 bg-slate-950/80 px-4 lg:px-8 py-5 text-xs text-slate-500 mt-12">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 font-mono">
          <div>
            DGHS-CleanPulse • Pandera Validation Firewall &amp; Open-Meteo Climate Archive
          </div>
          <div className="flex items-center gap-4 text-slate-400">
            <span>Immutable Bronze</span>
            <span>•</span>
            <span>Silver Pandera Firewall</span>
            <span>•</span>
            <span>DuckDB Engine</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
