"use client";

import React from "react";
import {
  Calendar,
  Compass,
  Sliders,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import {
  SurveillanceLagsResponse,
  ZoneSummaryItem,
} from "@/lib/types";

interface LagExplorerProps {
  currentZone: string;
  selectedLag: number;
  lagData: SurveillanceLagsResponse;
  zonesSummary: ZoneSummaryItem[];
  onZoneChange: (zone: string) => void;
  onLagChange: (lag: number) => void;
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
  selectedLag,
  lagData,
  zonesSummary,
  onZoneChange,
  onLagChange,
  isLoading,
}: LagExplorerProps) {
  // Quick preset jump
  const PRESET_LAGS = [0, 7, 14, 16, 21, 28];

  // Correlation chart dimensions
  const cWidth = 800;
  const cHeight = 260;
  const cPadLeft = 55;
  const cPadRight = 30;
  const cPadTop = 25;
  const cPadBottom = 35;
  const plotW = cWidth - cPadLeft - cPadRight;
  const plotH = cHeight - cPadTop - cPadBottom;

  // Correlation scale: r ranges from -0.4 to 1.0
  const rMin = -0.4;
  const rMax = 1.0;
  const rToY = (r: number) =>
    cPadTop + plotH - ((r - rMin) / (rMax - rMin)) * plotH;
  const lagToX = (lag: number) => cPadLeft + (lag / 28) * plotW;

  // Build SVG path strings for Chart A
  const corrs = lagData.lag_correlations;
  const pathHumidity = corrs
    .map((c, i) => `${i === 0 ? "M" : "L"} ${lagToX(c.lag_days)} ${rToY(c.pearson_r_humidity)}`)
    .join(" ");
  const pathPrecip = corrs
    .map((c, i) => `${i === 0 ? "M" : "L"} ${lagToX(c.lag_days)} ${rToY(c.pearson_r_precip)}`)
    .join(" ");
  const pathTemp = corrs
    .map((c, i) => `${i === 0 ? "M" : "L"} ${lagToX(c.lag_days)} ${rToY(c.pearson_r_temp)}`)
    .join(" ");

  // Shaded biological incubation band: Days 14 to 18
  const bandX1 = lagToX(14);
  const bandX2 = lagToX(18);
  const bandWidth = bandX2 - bandX1;

  // Current selected correlation point
  const currentCorr =
    corrs.find((c) => c.lag_days === selectedLag) || corrs[14] || corrs[0];

  // Timeline chart dimensions (Chart B)
  const tWidth = 800;
  const tHeight = 280;
  const tPadLeft = 60;
  const tPadRight = 60;
  const tPadTop = 25;
  const tPadBottom = 35;
  const tPlotW = tWidth - tPadLeft - tPadRight;
  const tPlotH = tHeight - tPadTop - tPadBottom;

  const series = lagData.aligned_time_series;
  const maxAdmissions = Math.max(...series.map((s) => s.daily_admitted), 10);
  const maxRainfall = Math.max(
    ...series.map((s) => s.lagged_precip_mm || 0),
    20
  );

  const tIdxToX = (idx: number) =>
    tPadLeft + (idx / Math.max(series.length - 1, 1)) * tPlotW;
  const admToY = (val: number) =>
    tPadTop + tPlotH - (val / maxAdmissions) * tPlotH;
  const rainToY = (val: number) =>
    tPadTop + tPlotH - (val / maxRainfall) * tPlotH;
  const humToY = (val: number) =>
    tPadTop + tPlotH - (Math.min(Math.max(val, 40), 100) / 100) * tPlotH;

  // Admissions area path
  const admPath = series
    .map((s, i) => `${i === 0 ? "M" : "L"} ${tIdxToX(i)} ${admToY(s.daily_admitted)}`)
    .join(" ");
  const admAreaPath = `${admPath} L ${tIdxToX(series.length - 1)} ${tPadTop + tPlotH} L ${tPadLeft} ${tPadTop + tPlotH} Z`;

  // Rainfall line path
  const rainPath = series
    .filter((s) => s.lagged_precip_mm !== null)
    .map((s, i) => {
      const origIdx = series.findIndex((x) => x.date === s.date);
      return `${i === 0 ? "M" : "L"} ${tIdxToX(origIdx)} ${rainToY(s.lagged_precip_mm || 0)}`;
    })
    .join(" ");

  // Humidity line path
  const humPath = series
    .filter((s) => s.lagged_humidity_pct !== null)
    .map((s, i) => {
      const origIdx = series.findIndex((x) => x.date === s.date);
      return `${i === 0 ? "M" : "L"} ${tIdxToX(origIdx)} ${humToY(s.lagged_humidity_pct || 70)}`;
    })
    .join(" ");

  return (
    <div className="space-y-8">
      {/* 1. Interactive Control Console */}
      <div className="rounded-2xl p-6 bg-gradient-to-r from-slate-900 via-slate-900/95 to-slate-950 border border-slate-800 shadow-xl space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-500/20 text-purple-300 border border-purple-500/30">
                Spatiotemporal Lag Engine
              </span>
              <span className="text-xs text-slate-400">
                DuckDB Zero-Copy Window Functions
              </span>
            </div>
            <h2 className="text-xl font-bold text-slate-100 tracking-tight">
              Monsoon Rainfall & Humidity Lag Correlation Explorer
            </h2>
          </div>

          <div className="flex items-center gap-2 bg-slate-800/80 px-3.5 py-2 rounded-xl border border-slate-700">
            <Sparkles className="w-4 h-4 text-purple-400" />
            <div className="text-xs">
              <span className="text-slate-400">Peak Biological Correlation:</span>{" "}
              <span className="font-bold font-mono text-purple-300">
                Day {lagData.peak_lag_days} (r = {lagData.peak_correlation_r.toFixed(4)})
              </span>
            </div>
          </div>
        </div>

        {/* Zone Selector Pills */}
        <div>
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-2.5">
            Select Surveillance Zone ({ZONES_LIST.length} Reporting Zones)
          </label>
          <div className="flex flex-wrap gap-2">
            {ZONES_LIST.map((zone) => {
              const isSelected = currentZone === zone;
              return (
                <button
                  key={zone}
                  id={`btn-zone-${zone.toLowerCase().replace(/[^a-z0-9]/g, "-")}`}
                  onClick={() => onZoneChange(zone)}
                  disabled={isLoading}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer flex items-center gap-1.5 ${
                    isSelected
                      ? "bg-purple-600 text-white font-bold shadow-lg shadow-purple-600/30 ring-1 ring-purple-400"
                      : "bg-slate-800/80 hover:bg-slate-700 text-slate-300 border border-slate-700/80"
                  }`}
                >
                  {zone === "National" && <Compass className="w-3.5 h-3.5 text-purple-300" />}
                  <span>{zone}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Interactive Lag Offset Slider */}
        <div className="pt-4 border-t border-slate-800 space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Sliders className="w-4 h-4 text-teal-400" />
              <label htmlFor="lag-slider" className="text-sm font-bold text-slate-200">
                Climate Shift Offset:{" "}
                <span className="text-teal-400 font-mono text-base">
                  {selectedLag} Days
                </span>
              </label>
              <span className="text-xs text-slate-400">
                (Biological Incubation Window: 14–18 Days)
              </span>
            </div>

            {/* Quick Preset Buttons */}
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-slate-400 mr-1">Presets:</span>
              {PRESET_LAGS.map((lag) => (
                <button
                  key={lag}
                  id={`btn-preset-lag-${lag}`}
                  onClick={() => onLagChange(lag)}
                  className={`px-2 py-0.5 rounded text-xs font-mono transition cursor-pointer ${
                    selectedLag === lag
                      ? "bg-teal-500 text-slate-950 font-bold"
                      : "bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-700"
                  }`}
                >
                  {lag}d
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-4">
            <span className="text-xs font-mono text-slate-400">0d</span>
            <input
              id="lag-slider"
              type="range"
              min="0"
              max="28"
              step="1"
              value={selectedLag}
              onChange={(e) => onLagChange(parseInt(e.target.value, 10))}
              className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-teal-400"
            />
            <span className="text-xs font-mono text-slate-400">28d</span>
          </div>
        </div>
      </div>

      {/* 2. Chart A: The 0-to-28 Day Biological Correlation Curve */}
      <section className="rounded-xl border border-slate-800 bg-slate-900/90 p-5 shadow-lg space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-purple-400" />
              <h3 className="text-base font-bold text-slate-100">
                Chart A: Empirical Pearson Correlation Curve (0 to 28 Days) — {currentZone}
              </h3>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Plots correlation coefficients between daily dengue cases and lagged climate features. Shaded band highlights vector larval development + extrinsic viral incubation period.
            </p>
          </div>

          <div className="flex items-center gap-3 text-xs font-mono">
            <span className="flex items-center gap-1 text-purple-400">
              <span className="w-3 h-0.5 bg-purple-400"></span> Humidity
            </span>
            <span className="flex items-center gap-1 text-sky-400">
              <span className="w-3 h-0.5 bg-sky-400"></span> Rainfall
            </span>
            <span className="flex items-center gap-1 text-amber-400">
              <span className="w-3 h-0.5 bg-amber-400"></span> Temp
            </span>
          </div>
        </div>

        {/* Responsive SVG Chart */}
        <div className="w-full overflow-x-auto">
          <svg
            viewBox={`0 0 ${cWidth} ${cHeight}`}
            className="w-full h-auto min-w-[650px] font-mono text-xs select-none"
          >
            {/* Shaded Reference Band: Days 14 to 18 */}
            <rect
              x={bandX1}
              y={cPadTop}
              width={bandWidth}
              height={plotH}
              fill="rgba(168, 85, 247, 0.12)"
              stroke="rgba(168, 85, 247, 0.3)"
              strokeDasharray="3 3"
            />
            <text
              x={bandX1 + bandWidth / 2}
              y={cPadTop + 14}
              textAnchor="middle"
              className="fill-purple-300 font-bold text-[10px]"
            >
              14–18d Incubation Peak
            </text>

            {/* Zero correlation horizontal baseline */}
            <line
              x1={cPadLeft}
              y1={rToY(0)}
              x2={cWidth - cPadRight}
              y2={rToY(0)}
              stroke="#334155"
              strokeWidth="1"
              strokeDasharray="2 2"
            />
            <text
              x={cPadLeft - 8}
              y={rToY(0) + 4}
              textAnchor="end"
              className="fill-slate-500 text-[10px]"
            >
              0.0
            </text>

            {/* Horizontal Grid lines */}
            {[0.4, 0.8, -0.2].map((rVal) => (
              <g key={rVal}>
                <line
                  x1={cPadLeft}
                  y1={rToY(rVal)}
                  x2={cWidth - cPadRight}
                  y2={rToY(rVal)}
                  stroke="#1e293b"
                  strokeWidth="1"
                />
                <text
                  x={cPadLeft - 8}
                  y={rToY(rVal) + 4}
                  textAnchor="end"
                  className="fill-slate-500 text-[10px]"
                >
                  {rVal > 0 ? `+${rVal.toFixed(1)}` : rVal.toFixed(1)}
                </text>
              </g>
            ))}

            {/* Vertical Lag lines and labels */}
            {[0, 7, 14, 18, 21, 28].map((lagVal) => (
              <g key={lagVal}>
                <line
                  x1={lagToX(lagVal)}
                  y1={cPadTop}
                  x2={lagToX(lagVal)}
                  y2={cHeight - cPadBottom}
                  stroke="#1e293b"
                  strokeWidth="1"
                />
                <text
                  x={lagToX(lagVal)}
                  y={cHeight - cPadBottom + 16}
                  textAnchor="middle"
                  className="fill-slate-400 text-[10px]"
                >
                  {lagVal}d
                </text>
              </g>
            ))}

            {/* Curve 1: Temperature */}
            <path
              d={pathTemp}
              fill="none"
              stroke="#f59e0b"
              strokeWidth="2"
              strokeDasharray="4 2"
              opacity="0.8"
            />

            {/* Curve 2: Rainfall */}
            <path
              d={pathPrecip}
              fill="none"
              stroke="#38bdf8"
              strokeWidth="2.5"
              opacity="0.9"
            />

            {/* Curve 3: Humidity (Hero curve) */}
            <path
              d={pathHumidity}
              fill="none"
              stroke="#a855f7"
              strokeWidth="3.5"
            />

            {/* Vertical Marker for Current Lag Slider */}
            <line
              x1={lagToX(selectedLag)}
              y1={cPadTop}
              x2={lagToX(selectedLag)}
              y2={cHeight - cPadBottom}
              stroke="#14b8a6"
              strokeWidth="2"
            />
            {/* Active Humidity Point Indicator */}
            {currentCorr && (
              <circle
                cx={lagToX(selectedLag)}
                cy={rToY(currentCorr.pearson_r_humidity)}
                r="6"
                fill="#14b8a6"
                stroke="#0f172a"
                strokeWidth="2"
              />
            )}
          </svg>
        </div>

        {/* Selected Lag Metric Pills */}
        {currentCorr && (
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 pt-2 text-xs font-mono">
            <div className="p-2.5 rounded-lg bg-slate-800/60 border border-slate-700/80">
              <span className="text-slate-400 block text-[11px]">Selected Lag Day:</span>
              <span className="text-sm font-bold text-teal-400">
                Day {currentCorr.lag_days}
              </span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-800/60 border border-slate-700/80">
              <span className="text-slate-400 block text-[11px]">Humidity Pearson r:</span>
              <span className="text-sm font-bold text-purple-300">
                +{currentCorr.pearson_r_humidity.toFixed(4)}
              </span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-800/60 border border-slate-700/80">
              <span className="text-slate-400 block text-[11px]">Precipitation Pearson r:</span>
              <span className="text-sm font-bold text-sky-300">
                +{currentCorr.pearson_r_precip.toFixed(4)}
              </span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-800/60 border border-slate-700/80">
              <span className="text-slate-400 block text-[11px]">Temperature Pearson r:</span>
              <span className="text-sm font-bold text-amber-300">
                {currentCorr.pearson_r_temp >= 0 ? "+" : ""}
                {currentCorr.pearson_r_temp.toFixed(4)}
              </span>
            </div>
          </div>
        )}
      </section>

      {/* 3. Chart B: 180-Day Aligned Epidemic vs. Shifted Climate Timeline */}
      <section className="rounded-xl border border-slate-800 bg-slate-900/90 p-5 shadow-lg space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <Calendar className="w-5 h-5 text-teal-400" />
              <h3 className="text-base font-bold text-slate-100">
                Chart B: 180-Day Epidemic Timeline vs. {selectedLag}-Day Shifted Climate Features
              </h3>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Daily admissions (left Y-axis) overlaid against rainfall and humidity shifted backwards by {selectedLag} days.
            </p>
          </div>

          <div className="flex items-center gap-3 text-xs font-mono">
            <span className="flex items-center gap-1.5 text-teal-400">
              <span className="w-3 h-3 rounded-sm bg-teal-500/30 border border-teal-400"></span> Daily Admissions
            </span>
            <span className="flex items-center gap-1.5 text-purple-400">
              <span className="w-3 h-0.5 bg-purple-400"></span> Shifted Humidity (%)
            </span>
            <span className="flex items-center gap-1.5 text-sky-400">
              <span className="w-3 h-0.5 bg-sky-400"></span> Shifted Rainfall (mm)
            </span>
          </div>
        </div>

        {/* Dual Axis SVG Timeline Chart */}
        <div className="w-full overflow-x-auto">
          <svg
            viewBox={`0 0 ${tWidth} ${tHeight}`}
            className="w-full h-auto min-w-[650px] font-mono text-xs select-none"
          >
            {/* Grid lines */}
            {[0.25, 0.5, 0.75, 1.0].map((frac) => (
              <line
                key={frac}
                x1={tPadLeft}
                y1={tPadTop + tPlotH * (1 - frac)}
                x2={tWidth - tPadRight}
                y2={tPadTop + tPlotH * (1 - frac)}
                stroke="#1e293b"
                strokeWidth="1"
              />
            ))}

            {/* Left Y Axis (Admissions) */}
            <text
              x={tPadLeft - 8}
              y={tPadTop + 10}
              textAnchor="end"
              className="fill-teal-400 font-bold text-[10px]"
            >
              {maxAdmissions}
            </text>
            <text
              x={tPadLeft - 8}
              y={tPadTop + tPlotH / 2}
              textAnchor="end"
              className="fill-teal-400/80 text-[10px]"
            >
              {Math.round(maxAdmissions / 2)}
            </text>
            <text
              x={tPadLeft - 8}
              y={tHeight - tPadBottom}
              textAnchor="end"
              className="fill-teal-400/60 text-[10px]"
            >
              0
            </text>

            {/* Right Y Axis (Humidity / Precip) */}
            <text
              x={tWidth - tPadRight + 8}
              y={tPadTop + 10}
              textAnchor="start"
              className="fill-purple-300 font-bold text-[10px]"
            >
              100%
            </text>
            <text
              x={tWidth - tPadRight + 8}
              y={tPadTop + tPlotH / 2}
              textAnchor="start"
              className="fill-purple-300/80 text-[10px]"
            >
              70%
            </text>
            <text
              x={tWidth - tPadRight + 8}
              y={tHeight - tPadBottom}
              textAnchor="start"
              className="fill-purple-300/60 text-[10px]"
            >
              40%
            </text>

            {/* X Axis dates (April, June, August, October) */}
            {[
              { label: "2026-04-18", idx: 0 },
              { label: "2026-06-15", idx: 58 },
              { label: "2026-08-15", idx: 119 },
              { label: "2026-10-14", idx: series.length - 1 },
            ].map((d) => (
              <text
                key={d.label}
                x={tIdxToX(d.idx)}
                y={tHeight - tPadBottom + 16}
                textAnchor="middle"
                className="fill-slate-400 text-[10px]"
              >
                {d.label}
              </text>
            ))}

            {/* Primary Area: Admissions */}
            <path
              d={admAreaPath}
              fill="rgba(20, 184, 166, 0.18)"
            />
            <path
              d={admPath}
              fill="none"
              stroke="#14b8a6"
              strokeWidth="2.5"
            />

            {/* Secondary Curve: Shifted Rainfall */}
            <path
              d={rainPath}
              fill="none"
              stroke="#38bdf8"
              strokeWidth="2"
              opacity="0.85"
            />

            {/* Secondary Curve: Shifted Humidity */}
            <path
              d={humPath}
              fill="none"
              stroke="#a855f7"
              strokeWidth="2"
              strokeDasharray="4 2"
              opacity="0.9"
            />
          </svg>
        </div>
      </section>

      {/* 4. 10-Zone Outbreak Breakdown Table */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Compass className="w-5 h-5 text-teal-400" />
            <h3 className="text-base font-bold text-slate-100">
              10-Zone Surveillance Summary Table (Report 2026-10-14)
            </h3>
          </div>
          <span className="text-xs text-slate-400">
            Ground-Truth Cumulative &amp; Daily DGHS Case Breakdowns
          </span>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/90 overflow-hidden shadow-lg">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="px-4 py-3">Reporting Zone</th>
                  <th className="px-4 py-3 text-right">Total Admitted</th>
                  <th className="px-4 py-3 text-right">Daily Admitted</th>
                  <th className="px-4 py-3 text-right">Total Deaths</th>
                  <th className="px-4 py-3 text-right">Total Discharged</th>
                  <th className="px-4 py-3 text-right">CFR %</th>
                  <th className="px-4 py-3 text-center">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 text-slate-300">
                {zonesSummary.map((z) => {
                  const isCurrent = currentZone === z.zone_name;
                  return (
                    <tr
                      key={z.zone_name}
                      className={`hover:bg-slate-800/50 transition-colors ${
                        isCurrent ? "bg-purple-950/20 font-bold" : ""
                      }`}
                    >
                      <td className="px-4 py-2.5 text-slate-200 flex items-center gap-2">
                        {isCurrent && <span className="w-2 h-2 rounded-full bg-purple-400"></span>}
                        <span>{z.zone_name}</span>
                      </td>
                      <td className="px-4 py-2.5 text-right font-bold text-teal-400">
                        {z.total_admitted.toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 text-right text-slate-300">
                        {z.daily_admitted.toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 text-right text-rose-400">
                        {z.total_deaths.toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 text-right text-slate-400">
                        {z.total_discharged.toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            z.cfr_pct > 0.5
                              ? "bg-rose-950 text-rose-300 border border-rose-800"
                              : "text-slate-400"
                          }`}
                        >
                          {z.cfr_pct.toFixed(2)}%
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        <button
                          onClick={() => onZoneChange(z.zone_name)}
                          className="px-2 py-1 rounded text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 cursor-pointer"
                        >
                          Explore Lags
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  );
}
