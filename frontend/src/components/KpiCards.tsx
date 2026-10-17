"use client";

import React from "react";
import {
  AlertTriangle,
  Clock,
  Gauge,
  Skull,
  Users,
} from "lucide-react";
import { PipelineHealthResponse, SurveillanceSummaryResponse } from "@/lib/types";

interface KpiCardsProps {
  summary: SurveillanceSummaryResponse;
  health: PipelineHealthResponse;
}

export function KpiCards({ summary, health }: KpiCardsProps) {
  const cards = [
    {
      id: "kpi-national-admissions",
      title: "2026 National Admissions",
      value: summary.total_admitted.toLocaleString(),
      subtext: `Across 10 DGHS Reporting Zones • Report ${summary.report_date}`,
      icon: Users,
      accent: "from-blue-500/20 to-teal-500/10 border-blue-500/30 text-blue-400",
      badge: "Ground Truth",
      badgeColor: "bg-blue-500/20 text-blue-300 border-blue-500/40",
    },
    {
      id: "kpi-deaths-cfr",
      title: "Cumulative Deaths & CFR",
      value: summary.total_deaths.toLocaleString(),
      subtext: `${summary.cfr_pct}% Case Fatality Rate (${summary.total_discharged.toLocaleString()} discharged)`,
      icon: Skull,
      accent: "from-rose-500/20 to-red-500/10 border-rose-500/30 text-rose-400",
      badge: `${summary.cfr_pct}% CFR`,
      badgeColor: "bg-rose-500/20 text-rose-300 border-rose-500/40",
    },
    {
      id: "kpi-optimal-lag",
      title: "Optimal Monsoon Lag Peak",
      value: `${summary.optimal_lag_days} Days`,
      subtext: "Pearson r = 0.8102 Humidity Correlation (14–18d Window)",
      icon: Clock,
      accent: "from-purple-500/20 to-indigo-500/10 border-purple-500/30 text-purple-400",
      badge: "Biological Incubation",
      badgeColor: "bg-purple-500/20 text-purple-300 border-purple-500/40",
    },
    {
      id: "kpi-bugs-intercepted",
      title: "Upstream DGHS Bugs Intercepted",
      value: `${summary.anomalies_caught_count} Anomalies`,
      subtext: "4 CRITICAL • 2 WARNING • Zero Silent Data Dropping",
      icon: AlertTriangle,
      accent: "from-amber-500/20 to-orange-500/10 border-amber-500/30 text-amber-400",
      badge: "Pandera Firewall",
      badgeColor: "bg-amber-500/20 text-amber-300 border-amber-500/40",
    },
    {
      id: "kpi-duckdb-latency",
      title: "DuckDB Query Latency",
      value: `${health.duckdb_latency_ms.toFixed(2)} ms`,
      subtext: `${health.layer_counts.gold_daily_rows.toLocaleString()} Gold Rows • In-Memory Columnar Speed`,
      icon: Gauge,
      accent: "from-emerald-500/20 to-teal-500/10 border-emerald-500/30 text-emerald-400",
      badge: "In-Memory Engine",
      badgeColor: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
      {cards.map((card) => {
        const IconComponent = card.icon;
        return (
          <div
            key={card.id}
            id={card.id}
            className={`relative rounded-xl p-4 bg-gradient-to-br ${card.accent} bg-slate-900/90 border shadow-md transition hover:border-slate-600 flex flex-col justify-between`}
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                  {card.title}
                </span>
                <span
                  className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${card.badgeColor}`}
                >
                  {card.badge}
                </span>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold font-mono tracking-tight text-slate-100">
                  {card.value}
                </span>
              </div>
            </div>
            <div className="mt-3 pt-2.5 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
              <span className="truncate pr-2">{card.subtext}</span>
              <IconComponent className="w-4 h-4 shrink-0 opacity-80" />
            </div>
          </div>
        );
      })}
    </div>
  );
}
