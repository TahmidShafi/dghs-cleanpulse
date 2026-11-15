"use client";

import React from "react";
import {
  AlertTriangle,
  CloudRain,
  Database,
  Gauge,
} from "lucide-react";
import {
  PipelineHealthResponse,
  SurveillanceSummaryResponse,
  WeatherDailyResponse,
} from "@/lib/types";

interface KpiCardsProps {
  summary: SurveillanceSummaryResponse;
  weather: WeatherDailyResponse;
  health: PipelineHealthResponse;
}

export function KpiCards({ summary, weather, health }: KpiCardsProps) {
  const hasRealDengue = summary.status === "available" && summary.data !== null;

  const cards = [
    {
      id: "kpi-dengue-status",
      title: "DGHS Dengue Series",
      value: hasRealDengue && summary.data
        ? summary.data.total_admitted.toLocaleString()
        : "Pending",
      subtext: hasRealDengue
        ? `Real DGHS report ${summary.data?.report_date}`
        : "No real DGHS series ingested yet (HTTP 404)",
      icon: Database,
      accent: "from-amber-500/20 to-orange-500/10 border-amber-500/30 text-amber-400",
      badge: hasRealDengue ? "Live DGHS" : "Pending Source",
      badgeColor: "bg-amber-500/20 text-amber-300 border-amber-500/40",
    },
    {
      id: "kpi-weather-coverage",
      title: "Real Weather Coverage",
      value: `${weather.district_count} Districts`,
      subtext: `${health.layer_counts.silver_weather_rows.toLocaleString()} Open-Meteo Archive rows (${weather.start_date} to ${weather.end_date})`,
      icon: CloudRain,
      accent: "from-blue-500/20 to-teal-500/10 border-blue-500/30 text-blue-400",
      badge: "Open-Meteo Real",
      badgeColor: "bg-blue-500/20 text-blue-300 border-blue-500/40",
    },
    {
      id: "kpi-real-anomalies",
      title: "Real DGHS Anomalies",
      value: `${health.layer_counts.silver_anomaly_rows}`,
      subtext: "Tab 1 shows synthetic fault-injection demo only",
      icon: AlertTriangle,
      accent: "from-slate-500/20 to-slate-700/10 border-slate-600/40 text-slate-300",
      badge: "Pandera Firewall",
      badgeColor: "bg-slate-700/60 text-slate-300 border-slate-600",
    },
    {
      id: "kpi-duckdb-latency",
      title: "DuckDB Query Latency",
      value: `${health.duckdb_latency_ms.toFixed(2)} ms`,
      subtext: `${health.layer_counts.bronze_snapshots} Bronze files • In-Memory Engine`,
      icon: Gauge,
      accent: "from-emerald-500/20 to-teal-500/10 border-emerald-500/30 text-emerald-400",
      badge: "In-Memory Engine",
      badgeColor: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
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
