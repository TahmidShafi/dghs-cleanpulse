"use client";

import React from "react";
import { Activity, RefreshCw } from "lucide-react";

interface HeaderProps {
  isLive: boolean;
  isFallback: boolean;
  snapshotGeneratedAt: string | null;
  snapshotGitCommit: string | null;
  lastUpdated: string;
  isRefreshing: boolean;
  onRefresh: () => void;
}

function formatUtcTimestamp(iso: string | null): string {
  if (!iso) return "unknown";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "unknown";
  const day = d.getUTCDate();
  const month = d.toLocaleString("en-GB", { month: "short", timeZone: "UTC" });
  const year = d.getUTCFullYear();
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mm = String(d.getUTCMinutes()).padStart(2, "0");
  return `${day} ${month} ${year}, ${hh}:${mm} UTC`;
}

export function Header({
  isLive,
  isFallback,
  snapshotGeneratedAt,
  snapshotGitCommit,
  lastUpdated,
  isRefreshing,
  onRefresh,
}: HeaderProps) {
  const sourceLabel = isLive
    ? "Live API"
    : `Snapshot · ${formatUtcTimestamp(snapshotGeneratedAt)}`;

  const sourceTooltip = isFallback
    ? `Static snapshot generated ${snapshotGeneratedAt ?? "unknown"}${
        snapshotGitCommit ? ` (commit ${snapshotGitCommit})` : ""
      }`
    : `Connected to Live FastAPI + DuckDB API (updated ${lastUpdated})`;

  return (
    <header className="border-b border-subtle bg-canvas sticky top-0 z-50 px-4 lg:px-8 py-3">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-3">
        {/* Title + Subtitle on line 1, Source label wraps to line 2 on <640px */}
        <div className="min-w-0 flex-1 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1.5 sm:gap-4">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-surface border border-subtle flex items-center justify-center text-accent-text shrink-0">
              <Activity className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <h1 className="text-lg font-semibold tracking-tight text-primary">
                DGHS-CleanPulse
              </h1>
              <p className="hidden sm:block text-xs text-secondary">
                Bangladesh dengue surveillance firewall and Open-Meteo ERA5 archive
              </p>
            </div>
          </div>

          <div
            id="connection-status-pill"
            title={sourceTooltip}
            className={`inline-flex items-center gap-2 self-start sm:self-auto px-2.5 py-1 rounded-md text-xs font-medium border ${
              isLive
                ? "bg-surface text-accent-text border-accent/40"
                : "bg-surface text-secondary border-subtle"
            }`}
          >
            <span
              className={`inline-block h-1.5 w-1.5 rounded-full shrink-0 ${
                isLive ? "bg-accent" : "bg-warning"
              }`}
            />
            <span className="font-mono tabular-nums">{sourceLabel}</span>
          </div>
        </div>

        <button
          type="button"
          onClick={onRefresh}
          disabled={isRefreshing}
          aria-label="Refresh dashboard data"
          title={`Refresh data (last updated ${lastUpdated})`}
          className="inline-flex items-center justify-center gap-1.5 min-w-[44px] min-h-[44px] px-2.5 sm:px-3 rounded-lg text-xs font-medium bg-surface hover:bg-elevated text-primary border border-subtle hover:border-hover transition-colors cursor-pointer disabled:opacity-50 shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <RefreshCw
            className={`w-4 h-4 ${isRefreshing ? "animate-spin text-accent-text" : "text-secondary"}`}
          />
          <span className="hidden sm:inline">Refresh</span>
        </button>
      </div>
    </header>
  );
}
