"use client";

import React from "react";
import { Activity, Database, RefreshCw, ShieldCheck, Zap } from "lucide-react";

interface HeaderProps {
  isLive: boolean;
  isFallback: boolean;
  lastUpdated: string;
  isRefreshing: boolean;
  onRefresh: () => void;
}

export function Header({
  isLive,
  isFallback,
  lastUpdated,
  isRefreshing,
  onRefresh,
}: HeaderProps) {
  return (
    <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur-md sticky top-0 z-50 px-4 lg:px-8 py-3.5">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        {/* Brand & Subtitle */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-500 to-emerald-600 flex items-center justify-center shadow-lg shadow-teal-500/20 text-slate-950 font-bold">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-slate-100">
                DGHS-CleanPulse
              </h1>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-800 text-teal-400 border border-slate-700">
                v1.0 Medallion
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Bangladesh Dengue Surveillance & Monsoon Climate Lag Analytics Engine
            </p>
          </div>
        </div>

        {/* Pipeline Badges & Telemetry Status */}
        <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto justify-between sm:justify-end">
          {/* Medallion Pipeline Flow */}
          <div className="hidden md:flex items-center gap-1.5 text-xs text-slate-400 bg-slate-900/90 px-3 py-1.5 rounded-lg border border-slate-800">
            <span className="flex items-center gap-1 text-amber-400 font-mono text-[11px]">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400"></span> Bronze
            </span>
            <span className="text-slate-600">→</span>
            <span className="flex items-center gap-1 text-teal-400 font-mono text-[11px]">
              <ShieldCheck className="w-3 h-3" /> Silver Pandera
            </span>
            <span className="text-slate-600">→</span>
            <span className="flex items-center gap-1 text-emerald-400 font-mono text-[11px]">
              <Database className="w-3 h-3" /> Gold DuckDB
            </span>
          </div>

          {/* Connection Mode Pill */}
          <div
            id="connection-status-pill"
            title={
              isFallback
                ? "Operating in zero-cold-start static fallback mode"
                : "Connected to live FastAPI + DuckDB engine"
            }
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
              isLive
                ? "bg-emerald-950/60 text-emerald-300 border-emerald-800/80"
                : "bg-amber-950/60 text-amber-300 border-amber-800/80"
            }`}
          >
            {isLive ? (
              <>
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span>Live FastAPI + DuckDB Connected</span>
              </>
            ) : (
              <>
                <Zap className="w-3.5 h-3.5 text-amber-400" />
                <span>Static Gold Snapshot Mode (Zero Cold-Start)</span>
              </>
            )}
          </div>

          {/* Refresh Action */}
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition cursor-pointer disabled:opacity-50"
            title={`Last updated: ${lastUpdated}`}
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin text-teal-400" : ""}`}
            />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        </div>
      </div>
    </header>
  );
}
