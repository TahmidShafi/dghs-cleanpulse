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
  const tPadLeft = 55;
  const tPadRight = 55;
  const tPadTop = 25;
  const tPadBottom = 35;
  const maxRainfall = Math.max(...series.map((s) => s.precip_mm), 20);

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
      {/* Calm Pending Notice */}
      <div
        id="dengue-pending-notice"
        className="rounded-lg p-4 bg-surface border border-subtle border-l-2 border-l-warning text-primary flex items-start gap-3"
      >
        <AlertCircle className="w-4 h-4 text-warning shrink-0 mt-0.5" />
        <p className="text-sm text-secondary leading-relaxed">
          Dengue series pending: no real DGHS data has been ingested yet (source offline when last checked, 15 Nov 2026). The chart shows real ERA5 weather; lag analysis will appear once dengue data is available.
        </p>
      </div>

      {/* Zone Selector */}
      <div className="rounded-lg p-5 bg-surface border border-subtle flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <label
            htmlFor="zone-selector"
            className="text-xs font-medium text-secondary flex items-center gap-1.5 mb-2"
          >
            <Compass className="w-3.5 h-3.5 text-accent-text" />
            <span>Target geography (Open-Meteo ERA5 archive)</span>
          </label>
          <select
            id="zone-selector"
            value={currentZone}
            onChange={(e) => onZoneChange(e.target.value)}
            disabled={isLoading}
            className="w-full md:w-72 bg-canvas border border-subtle hover:border-hover text-primary rounded-lg px-3.5 py-2.5 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent cursor-pointer"
          >
            {ZONES_LIST.map((z) => (
              <option key={z} value={z}>
                {z === "National" ? "All Bangladesh (64 districts avg)" : z}
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="px-4 py-2.5 rounded-lg bg-canvas border border-subtle">
            <span className="text-xs text-secondary block">Districts</span>
            <span className="text-base font-semibold font-mono tabular-nums text-primary">
              {weatherData.district_count}
            </span>
          </div>
          <div className="px-4 py-2.5 rounded-lg bg-canvas border border-subtle">
            <span className="text-xs text-secondary block">Mean temp / hum</span>
            <span className="text-base font-semibold font-mono tabular-nums text-primary">
              {avgTemp}°C / {avgHum}%
            </span>
          </div>
          <div className="px-4 py-2.5 rounded-lg bg-canvas border border-subtle">
            <span className="text-xs text-secondary block">Cumulative precip</span>
            <span className="text-base font-semibold font-mono tabular-nums text-accent-text">
              {totalPrecip} mm
            </span>
          </div>
        </div>
      </div>

      {/* Real Weather Chart */}
      <div className="rounded-lg p-5 bg-surface border border-subtle">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
          <div>
            <h3 className="text-base font-semibold text-primary flex items-center gap-2">
              <CloudRain className="w-4 h-4 text-accent-text" />
              <span>
                Daily precipitation and relative humidity ({currentZone})
              </span>
            </h3>
            <p className="text-xs text-secondary mt-0.5">
              Source: Open-Meteo ERA5 ·{" "}
              <span className="font-mono tabular-nums">{series.length}</span>{" "}
              days (
              <span className="font-mono tabular-nums">
                {weatherData.start_date}
              </span>{" "}
              to{" "}
              <span className="font-mono tabular-nums">
                {weatherData.end_date}
              </span>
              )
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-xs text-secondary">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-2 bg-accent opacity-80 inline-block rounded-sm" />
              Precipitation (mm)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-muted-line inline-block" />
              <span className="sm:hidden">Relative humidity (%, 0-100)</span>
              <span className="hidden sm:inline">Relative humidity (%)</span>
            </span>
          </div>
        </div>

        <div className="w-full">
          {[
            {
              key: "mobile",
              className: "w-full h-[240px] sm:hidden",
              width: 340,
              height: 240,
              padLeft: 44,
              padRight: 12,
              padTop: 18,
              padBottom: 32,
              ticks: [0, 0.5, 1],
              showRightAxis: false,
              fontSizeClass: "text-[13px]",
              barWidth: 1.5,
            },
            {
              key: "desktop",
              className: "hidden sm:block w-full h-auto",
              width: tWidth,
              height: tHeight,
              padLeft: tPadLeft,
              padRight: tPadRight,
              padTop: tPadTop,
              padBottom: tPadBottom,
              ticks: [0, 0.25, 0.5, 0.75, 1],
              showRightAxis: true,
              fontSizeClass: "text-[10px]",
              barWidth: 3,
            },
          ].map((cfg) => {
            const plotW = cfg.width - cfg.padLeft - cfg.padRight;
            const plotH = cfg.height - cfg.padTop - cfg.padBottom;
            const xAt = (idx: number) =>
              cfg.padLeft + (idx / Math.max(series.length - 1, 1)) * plotW;
            const yRain = (val: number) =>
              cfg.padTop + plotH - (val / maxRainfall) * plotH;
            const yHum = (val: number) =>
              cfg.padTop +
              plotH -
              (Math.min(Math.max(val, 40), 100) / 100) * plotH;
            const pathD = series
              .map(
                (s, i) =>
                  `${i === 0 ? "M" : "L"} ${xAt(i)} ${yHum(s.humidity_pct)}`
              )
              .join(" ");

            return (
              <svg
                key={cfg.key}
                viewBox={`0 0 ${cfg.width} ${cfg.height}`}
                className={cfg.className}
                role="img"
                aria-label={`Daily precipitation and relative humidity chart for ${currentZone}`}
              >
                {cfg.ticks.map((frac) => {
                  const y = cfg.padTop + plotH * (1 - frac);
                  const rainLabel = (maxRainfall * frac).toFixed(0);
                  const humLabel = (frac * 100).toFixed(0);
                  return (
                    <g key={frac}>
                      <line
                        x1={cfg.padLeft}
                        y1={y}
                        x2={cfg.width - cfg.padRight}
                        y2={y}
                        stroke="#27272a"
                        strokeDasharray="3 3"
                      />
                      <text
                        x={cfg.padLeft - 6}
                        y={y + 4}
                        textAnchor="end"
                        className={`fill-accent-text ${cfg.fontSizeClass} font-mono`}
                      >
                        {rainLabel}mm
                      </text>
                      {cfg.showRightAxis && (
                        <text
                          x={cfg.width - cfg.padRight + 8}
                          y={y + 4}
                          textAnchor="start"
                          className={`fill-muted-line ${cfg.fontSizeClass} font-mono`}
                        >
                          {humLabel}%
                        </text>
                      )}
                    </g>
                  );
                })}

                {series.map((s, idx) => {
                  const x = xAt(idx);
                  const barH = Math.max(
                    0,
                    cfg.padTop + plotH - yRain(s.precip_mm)
                  );
                  return (
                    <rect
                      key={s.date}
                      x={x - cfg.barWidth / 2}
                      y={yRain(s.precip_mm)}
                      width={cfg.barWidth}
                      height={barH}
                      className="fill-accent animate-bar-grow-y"
                      opacity={0.8}
                    />
                  );
                })}

                {series.length > 1 && (
                  <path
                    d={pathD}
                    fill="none"
                    stroke="#d4d4d8"
                    strokeWidth="1.75"
                  />
                )}

                {series.length > 0 && (
                  <>
                    <text
                      x={cfg.padLeft}
                      y={cfg.height - 8}
                      textAnchor="start"
                      className={`fill-secondary ${cfg.fontSizeClass} font-mono`}
                    >
                      {series[0].date}
                    </text>
                    <text
                      x={cfg.width - cfg.padRight}
                      y={cfg.height - 8}
                      textAnchor="end"
                      className={`fill-secondary ${cfg.fontSizeClass} font-mono`}
                    >
                      {series[series.length - 1].date}
                    </text>
                  </>
                )}
              </svg>
            );
          })}
        </div>

        <div className="mt-4 pt-3 border-t border-subtle flex items-start sm:items-center gap-2 text-xs text-secondary">
          <Thermometer className="w-3.5 h-3.5 text-accent-text shrink-0 mt-0.5 sm:mt-0" />
          <p className="leading-relaxed">
            <a
              href="https://open-meteo.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent-text hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded"
            >
              Weather data by Open-Meteo.com
            </a>{" "}
            ·{" "}
            <a
              href="https://creativecommons.org/licenses/by/4.0/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent-text hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded"
            >
              CC BY 4.0
            </a>{" "}
            · district values averaged to national series
          </p>
        </div>
      </div>
    </div>
  );
}
