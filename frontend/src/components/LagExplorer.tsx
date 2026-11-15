"use client";

import React from "react";
import { AlertCircle, CloudRain, Compass, Thermometer } from "lucide-react";
import { WeatherDailyResponse } from "@/lib/types";

interface LagExplorerProps {
  currentZone: string;
  weatherData: WeatherDailyResponse;
  onZoneChange: (zone: string) => void;
  isLoading: boolean;
}

const ZONES_LIST = [
  "National",
  "Chattogram",
  "DSCC",
  "Barishal",
  "Dhaka (Out of CC)",
  "DNCC",
  "Khulna",
  "Rajshahi",
  "Mymensingh",
  "Rangpur",
  "Sylhet",
];

export function LagExplorer({
  currentZone,
  weatherData,
  onZoneChange,
  isLoading,
}: LagExplorerProps) {
  const series = weatherData.series;
  const tWidth = 800;
  const tHeight = 280;
  const tPadLeft = 60;
  const tPadRight = 60;
  const tPadTop = 25;
  const tPadBottom = 35;
  const tPlotW = tWidth - tPadLeft - tPadRight;
  const tPlotH = tHeight - tPadTop - tPadBottom;

  const maxRainfall = Math.max(...series.map((s) => s.precip_mm), 20);
  const tIdxToX = (idx: number) =>
    tPadLeft + (idx / Math.max(series.length - 1, 1)) * tPlotW;
  const rainToY = (val: number) =>
    tPadTop + tPlotH - (val / maxRainfall) * tPlotH;
  const humToY = (val: number) =>
    tPadTop + tPlotH - (Math.min(Math.max(val, 40), 100) / 100) * tPlotH;

  const humPath = series
    .map((s, i) => `${i === 0 ? "M" : "L"} ${tIdxToX(i)} ${humToY(s.humidity_pct)}`)
    .join(" ");

  const avgTemp =
    series.length > 0
      ? (series.reduce((acc, s) => acc + s.temp_c, 0) / series.length).toFixed(1)
      : "—";
  const avgHum =
    series.length > 0
      ? (series.reduce((acc, s) => acc + s.humidity_pct, 0) / series.length).toFixed(1)
      : "—";
  const totalPrecip = series
    .reduce((acc, s) => acc + s.precip_mm, 0)
    .toFixed(1);

  return (
    <div className="space-y-6">
      {/* Visible Notice: Dengue Series Pending Real Source */}
      <div
        id="dengue-pending-notice"
        className="rounded-xl p-4 bg-amber-950/50 border border-amber-500/50 text-amber-200 flex items-start gap-3"
      >
        <AlertCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
        <div className="text-xs sm:text-sm">
          <strong className="text-amber-300">
            Dengue Time Series &amp; Lag Correlation Pending Real Source:
          </strong>{" "}
          Simulated dengue admissions and synthetic Pearson <em>r</em> curves have been removed.
          Below is the verified real climate series from the{" "}
          <span className="font-semibold text-amber-100">
            {weatherData.source}
          </span>{" "}
          ({weatherData.start_date} to {weatherData.end_date}). Spatiotemporal lag
          correlations will activate once real DGHS dengue data is ingested in Phase 2.
        </div>
      </div>

      {/* Zone Selector */}
      <div className="rounded-2xl p-6 bg-slate-900/80 border border-slate-800 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <label className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5 mb-2">
            <Compass className="w-3.5 h-3.5 text-teal-400" /> Target Geography (Real Open-Meteo Archive)
          </label>
          <select
            id="zone-selector"
            value={currentZone}
            onChange={(e) => onZoneChange(e.target.value)}
            disabled={isLoading}
            className="w-full md:w-72 bg-slate-950 border border-slate-700 text-slate-100 rounded-xl px-4 py-2.5 text-sm font-medium focus:outline-none focus:border-teal-500 cursor-pointer"
          >
            {ZONES_LIST.map((z) => (
              <option key={z} value={z}>
                {z === "National" ? "All Bangladesh (64 Districts Avg)" : z}
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="px-4 py-2 rounded-xl bg-slate-950 border border-slate-800">
            <span className="text-[11px] text-slate-400 block">Districts</span>
            <span className="text-base font-bold font-mono text-teal-300">
              {weatherData.district_count}
            </span>
          </div>
          <div className="px-4 py-2 rounded-xl bg-slate-950 border border-slate-800">
            <span className="text-[11px] text-slate-400 block">Mean Temp / Hum</span>
            <span className="text-base font-bold font-mono text-amber-300">
              {avgTemp}°C / {avgHum}%
            </span>
          </div>
          <div className="px-4 py-2 rounded-xl bg-slate-950 border border-slate-800">
            <span className="text-[11px] text-slate-400 block">Cumulative Precip</span>
            <span className="text-base font-bold font-mono text-blue-300">
              {totalPrecip} mm
            </span>
          </div>
        </div>
      </div>

      {/* Real Weather Chart */}
      <div className="rounded-2xl p-6 bg-slate-900/90 border border-slate-800 shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
          <div>
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <CloudRain className="w-4 h-4 text-blue-400" />
              Real Daily Precipitation &amp; Relative Humidity ({currentZone})
            </h3>
            <p className="text-xs text-slate-400">
              Source: Open-Meteo Historical Weather API • {series.length} days ({weatherData.start_date} to {weatherData.end_date})
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs text-slate-400">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-2 bg-blue-400/70 inline-block rounded-sm"></span>{" "}
              Precipitation (mm)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-amber-400 inline-block"></span>{" "}
              Relative Humidity (%)
            </span>
          </div>
        </div>

        <div className="w-full overflow-x-auto">
          <svg
            viewBox={`0 0 ${tWidth} ${tHeight}`}
            className="w-full h-auto min-w-[600px]"
          >
            {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
              const y = tPadTop + tPlotH * (1 - frac);
              const rainLabel = (maxRainfall * frac).toFixed(0);
              const humLabel = (frac * 100).toFixed(0);
              return (
                <g key={frac}>
                  <line
                    x1={tPadLeft}
                    y1={y}
                    x2={tWidth - tPadRight}
                    y2={y}
                    stroke="#1e293b"
                    strokeDasharray="3 3"
                  />
                  <text
                    x={tPadLeft - 8}
                    y={y + 4}
                    textAnchor="end"
                    className="fill-blue-400/80 text-[10px] font-mono"
                  >
                    {rainLabel}mm
                  </text>
                  <text
                    x={tWidth - tPadRight + 8}
                    y={y + 4}
                    textAnchor="start"
                    className="fill-amber-400/80 text-[10px] font-mono"
                  >
                    {humLabel}%
                  </text>
                </g>
              );
            })}

            {series.map((s, idx) => {
              const x = tIdxToX(idx);
              const barH = Math.max(0, tPadTop + tPlotH - rainToY(s.precip_mm));
              return (
                <rect
                  key={s.date}
                  x={x - 1.5}
                  y={rainToY(s.precip_mm)}
                  width={3}
                  height={barH}
                  fill="#38bdf8"
                  opacity={0.7}
                />
              );
            })}

            {series.length > 1 && (
              <path
                d={humPath}
                fill="none"
                stroke="#fbbf24"
                strokeWidth="2"
              />
            )}

            {series.length > 0 && (
              <>
                <text
                  x={tPadLeft}
                  y={tHeight - 10}
                  textAnchor="start"
                  className="fill-slate-400 text-[10px] font-mono"
                >
                  {series[0].date}
                </text>
                <text
                  x={tWidth - tPadRight}
                  y={tHeight - 10}
                  textAnchor="end"
                  className="fill-slate-400 text-[10px] font-mono"
                >
                  {series[series.length - 1].date}
                </text>
              </>
            )}
          </svg>
        </div>

        <div className="mt-4 pt-3 border-t border-slate-800 flex items-center gap-2 text-xs text-slate-400">
          <Thermometer className="w-3.5 h-3.5 text-teal-400" />
          <span>
            All 64 Bangladesh districts aggregated from immutable Bronze Open-Meteo JSON batches into Silver Parquet.
          </span>
        </div>
      </div>
    </div>
  );
}
