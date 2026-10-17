"use client";

import React, { useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { KpiCards } from "@/components/KpiCards";
import { FirewallInspector } from "@/components/FirewallInspector";
import { LagExplorer } from "@/components/LagExplorer";
import {
  fetchInitialDashboardData,
  fetchZoneLagData,
} from "@/lib/api";
import { DashboardState, SurveillanceLagsResponse } from "@/lib/types";
import { Clock, Database, ShieldCheck } from "lucide-react";

export default function Home() {
  const [dashboard, setDashboard] = useState<DashboardState | null>(null);
  const [activeTab, setActiveTab] = useState<"firewall" | "lags">("firewall");
  const [currentZone, setCurrentZone] = useState<string>("National");
  const [selectedLag, setSelectedLag] = useState<number>(14);
  const [lagData, setLagData] = useState<SurveillanceLagsResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isLagLoading, setIsLagLoading] = useState<boolean>(false);

  // Load initial data
  const loadData = async (refresh = false) => {
    if (refresh) setIsRefreshing(true);

    try {
      const state = await fetchInitialDashboardData();
      setDashboard(state);
      setLagData(state.lags);
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
          setLagData(state.lags);
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

  // Handle zone or lag slider changes
  const handleZoneChange = async (newZone: string) => {
    setCurrentZone(newZone);
    if (!dashboard) return;
    setIsLagLoading(true);
    try {
      const data = await fetchZoneLagData(newZone, selectedLag, dashboard.isLive);
      setLagData(data);
    } catch (e) {
      console.error("Failed to load zone lag data:", e);
    } finally {
      setIsLagLoading(false);
    }
  };

  const handleLagChange = async (newLag: number) => {
    setSelectedLag(newLag);
    if (!dashboard) return;
    setIsLagLoading(true);
    try {
      const data = await fetchZoneLagData(currentZone, newLag, dashboard.isLive);
      setLagData(data);
    } catch (e) {
      console.error("Failed to adjust lag offset:", e);
    } finally {
      setIsLagLoading(false);
    }
  };

  if (isLoading || !dashboard) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-6 text-slate-100">
        <div className="w-12 h-12 rounded-xl bg-teal-500/20 border border-teal-500/40 flex items-center justify-center animate-pulse mb-4">
          <Database className="w-6 h-6 text-teal-400" />
        </div>
        <h2 className="text-lg font-bold">Initializing DGHS-CleanPulse Console...</h2>
        <p className="text-xs text-slate-400 mt-1">Connecting to DuckDB In-Memory Engine &amp; Pandera Firewall</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* 1. Telemetry Header */}
      <Header
        isLive={dashboard.isLive}
        isFallback={dashboard.isFallback}
        lastUpdated={dashboard.lastUpdated}
        isRefreshing={isRefreshing}
        onRefresh={() => loadData(true)}
      />

      {/* Main Container */}
      <main className="max-w-7xl mx-auto w-full px-4 lg:px-8 py-6 flex-1 space-y-6">
        {/* 2. Top-Level KPI Summary Cards */}
        <KpiCards summary={dashboard.summary} health={dashboard.health} />

        {/* 3. Navigation Tab Bar */}
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
            <span>Live Government Data Firewall Inspector</span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30">
              {dashboard.anomalies.total_anomalies} Intercepted
            </span>
          </button>

          <button
            id="tab-lags"
            onClick={() => setActiveTab("lags")}
            className={`flex items-center gap-2 px-5 py-3 text-sm font-bold border-b-2 transition cursor-pointer ${
              activeTab === "lags"
                ? "border-purple-400 text-purple-300 bg-purple-500/5 rounded-t-lg"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Clock className="w-4 h-4 text-purple-400" />
            <span>Monsoon Rainfall &amp; Humidity Lag Explorer</span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
              14d Peak
            </span>
          </button>
        </div>

        {/* 4. Active Tab Content */}
        {activeTab === "firewall" && (
          <div id="content-tab-firewall">
            <FirewallInspector
              anomaliesData={dashboard.anomalies}
              ageGroups={dashboard.summary.age_groups}
            />
          </div>
        )}

        {activeTab === "lags" && lagData && (
          <div id="content-tab-lags">
            <LagExplorer
              currentZone={currentZone}
              selectedLag={selectedLag}
              lagData={lagData}
              zonesSummary={dashboard.summary.zones_summary}
              onZoneChange={handleZoneChange}
              onLagChange={handleLagChange}
              isLoading={isLagLoading}
            />
          </div>
        )}
      </main>

      {/* 5. Console Footer */}
      <footer className="border-t border-slate-900 bg-slate-950/80 px-4 lg:px-8 py-5 text-xs text-slate-500 mt-12">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 font-mono">
          <div>
            DGHS-CleanPulse © 2026 • Directorate General of Health Services (HEOC) Dengue Surveillance &amp; Open-Meteo Climate Lag Engine
          </div>
          <div className="flex items-center gap-4 text-slate-400">
            <span>Bronze Ingestion</span>
            <span>•</span>
            <span>Silver Pandera Firewall</span>
            <span>•</span>
            <span>Gold DuckDB Columnar</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
