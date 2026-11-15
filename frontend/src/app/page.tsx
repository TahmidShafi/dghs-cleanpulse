"use client";

import React, { useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { KpiCards } from "@/components/KpiCards";
import { FirewallInspector } from "@/components/FirewallInspector";
import { LagExplorer } from "@/components/LagExplorer";
import {
  fetchHistoricalScopeData,
  fetchInitialDashboardData,
} from "@/lib/api";
import {
  DashboardState,
  HistoricalWeeklyResponse,
  WeeklyLagCorrelationsResponse,
} from "@/lib/types";
import { CloudRain, ShieldCheck } from "lucide-react";

export default function Home() {
  const [dashboard, setDashboard] = useState<DashboardState | null>(null);
  const [activeTab, setActiveTab] = useState<"firewall" | "lags">("firewall");
  const [currentScope, setCurrentScope] = useState<string>("National");
  const [currentVariable, setCurrentVariable] =
    useState<string>("weekly_precip_mm");
  const [historicalWeekly, setHistoricalWeekly] =
    useState<HistoricalWeeklyResponse | null>(null);
  const [weeklyLags, setWeeklyLags] =
    useState<WeeklyLagCorrelationsResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isHistoricalLoading, setIsHistoricalLoading] =
    useState<boolean>(false);

  const loadData = async (refresh = false) => {
    if (refresh) setIsRefreshing(true);

    try {
      const state = await fetchInitialDashboardData();
      setDashboard(state);
      setHistoricalWeekly(state.historicalWeekly);
      setWeeklyLags(state.weeklyLags);
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
          setHistoricalWeekly(state.historicalWeekly);
          setWeeklyLags(state.weeklyLags);
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

  const updateHistoricalView = async (scope: string, variable: string) => {
    if (!dashboard) return;
    setIsHistoricalLoading(true);
    try {
      const { weekly, lags } = await fetchHistoricalScopeData(
        scope,
        variable,
        dashboard.isLive
      );
      setHistoricalWeekly(weekly);
      setWeeklyLags(lags);
    } catch (e) {
      console.error("Failed to load historical scope data:", e);
    } finally {
      setIsHistoricalLoading(false);
    }
  };

  const handleScopeChange = (newScope: string) => {
    setCurrentScope(newScope);
    void updateHistoricalView(newScope, currentVariable);
  };

  const handleVariableChange = (newVariable: string) => {
    setCurrentVariable(newVariable);
    void updateHistoricalView(currentScope, newVariable);
  };

  if (isLoading || !dashboard) {
    return (
      <div
        aria-busy="true"
        aria-label="Loading dashboard"
        className="min-h-screen bg-canvas text-primary flex flex-col"
      >
        <div className="border-b border-subtle px-4 lg:px-8 py-3">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <div className="h-8 w-48 rounded-md bg-surface animate-pulse" />
            <div className="h-9 w-28 rounded-md bg-surface animate-pulse" />
          </div>
        </div>
        <main className="max-w-7xl mx-auto w-full px-4 lg:px-8 py-6 space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
            {[0, 1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-28 rounded-lg bg-surface border border-subtle animate-pulse"
              />
            ))}
          </div>
          <div className="h-11 w-72 rounded-md bg-surface animate-pulse" />
          <div className="h-64 rounded-lg bg-surface border border-subtle animate-pulse" />
        </main>
      </div>
    );
  }

  const demoAnomalies = dashboard.syntheticDemo?.audit_anomalies ?? dashboard.anomalies;
  const demoAgeGroups = dashboard.syntheticDemo?.age_groups ?? [];

  return (
    <div className="min-h-screen bg-canvas text-primary flex flex-col font-sans">
      <Header
        isLive={dashboard.isLive}
        isFallback={dashboard.isFallback}
        snapshotGeneratedAt={dashboard.snapshotGeneratedAt}
        snapshotGitCommit={dashboard.snapshotGitCommit}
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

        <div
          role="tablist"
          aria-label="Dashboard views"
          className="flex items-center border-b border-subtle gap-1 overflow-x-auto whitespace-nowrap"
        >
          <button
            id="tab-firewall"
            type="button"
            role="tab"
            aria-selected={activeTab === "firewall"}
            onClick={() => setActiveTab("firewall")}
            className={`inline-flex items-center gap-2 min-h-[44px] px-4 py-2.5 text-sm font-medium border-b-2 transition-colors cursor-pointer shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
              activeTab === "firewall"
                ? "border-accent text-accent-text"
                : "border-transparent text-secondary hover:text-primary"
            }`}
          >
            <ShieldCheck className="w-4 h-4 shrink-0" />
            <span>Validation demo</span>
            <span className="text-xs font-medium px-1.5 py-0.5 rounded bg-warning-subtle text-warning border border-warning/40">
              Synthetic
            </span>
          </button>

          <button
            id="tab-lags"
            type="button"
            role="tab"
            aria-selected={activeTab === "lags"}
            onClick={() => setActiveTab("lags")}
            className={`inline-flex items-center gap-2 min-h-[44px] px-4 py-2.5 text-sm font-medium border-b-2 transition-colors cursor-pointer shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
              activeTab === "lags"
                ? "border-accent text-accent-text"
                : "border-transparent text-secondary hover:text-primary"
            }`}
          >
            <CloudRain className="w-4 h-4 shrink-0" />
            <span>Historical analysis</span>
          </button>
        </div>

        {activeTab === "firewall" && (
          <div id="content-tab-firewall" className="animate-fade-in">
            <FirewallInspector
              anomaliesData={demoAnomalies}
              ageGroups={demoAgeGroups}
              fixtureSha256={dashboard.syntheticDemo?.fixture_sha256}
            />
          </div>
        )}

        {activeTab === "lags" && (
          <div id="content-tab-lags" className="animate-fade-in">
            <LagExplorer
              currentScope={currentScope}
              currentVariable={currentVariable}
              historicalWeekly={historicalWeekly}
              weeklyLags={weeklyLags}
              onScopeChange={handleScopeChange}
              onVariableChange={handleVariableChange}
              isLoading={isHistoricalLoading}
            />
          </div>
        )}
      </main>

      <footer className="border-t border-subtle bg-canvas px-4 lg:px-8 py-5 text-xs text-secondary mt-10">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-primary font-medium">DGHS-CleanPulse</span>
            <span>·</span>
            <a
              href="https://github.com/TahmidShafi/dghs-cleanpulse"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent-text hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded"
            >
              Source on GitHub
            </a>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <a
              href="https://open-meteo.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent-text hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded"
            >
              Weather data by Open-Meteo.com
            </a>
            <span>·</span>
            <a
              href="https://creativecommons.org/licenses/by/4.0/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent-text hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded"
            >
              CC BY 4.0
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
