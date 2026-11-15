"use client";

import React from "react";
import { AlertTriangle, CloudRain, Database, FileArchive } from "lucide-react";
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
      title: "Live DGHS feed",
      value:
        hasRealDengue && summary.data
          ? summary.data.total_admitted.toLocaleString()
          : "Pending",
      subtext: hasRealDengue
        ? `Real DGHS report ${summary.data?.report_date}`
        : "No real DGHS series ingested yet (HTTP 404)",
      icon: Database,
      badge: hasRealDengue ? "Live" : "Pending",
    },
    {
      id: "kpi-historical-cases",
      title: summary.historical
        ? `Reported cases (report dates ${summary.historical.report_date_start} to ${summary.historical.report_date_end})`
        : "Reported cases (report dates 2022-01-01 to 2024-12-31)",
      value: summary.historical
        ? summary.historical.total_cases.toLocaleString()
        : "—",
      subtext: "secondary source",
      icon: AlertTriangle,
      badge: null,
    },
    {
      id: "kpi-weather-coverage",
      title: "Weather coverage",
      value: `${weather.district_count} districts`,
      subtext: "2022-2024 ERA5",
      icon: CloudRain,
      badge: null,
    },
    {
      id: "kpi-bronze-files",
      title: "Bronze files",
      value: `${health.layer_counts.bronze_snapshots}`,
      subtext: "each with a SHA-256 provenance sidecar",
      icon: FileArchive,
      badge: null,
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
            className="animate-fade-in rounded-lg p-4 bg-surface border border-subtle hover:border-hover transition-colors flex flex-col justify-between gap-3"
          >
            <div>
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="text-xs font-medium text-secondary">
                  {card.title}
                </span>
                {card.badge && (
                  <span
                    className={`text-xs font-medium px-2 py-0.5 rounded border ${
                      hasRealDengue
                        ? "bg-elevated text-accent-text border-accent/40"
                        : "bg-warning-subtle text-warning border-warning/40"
                    }`}
                  >
                    {card.badge}
                  </span>
                )}
              </div>
              <div className="text-2xl font-semibold font-mono tabular-nums tracking-tight text-primary">
                {card.value}
              </div>
            </div>
            <div className="pt-2.5 border-t border-subtle flex items-start justify-between gap-2 text-xs text-secondary">
              <span className="leading-relaxed">{card.subtext}</span>
              <IconComponent className="w-4 h-4 shrink-0 mt-0.5 text-secondary" />
            </div>
          </div>
        );
      })}
    </div>
  );
}
