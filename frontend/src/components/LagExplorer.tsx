"use client";

import React, { useMemo, useState } from "react";
import {
  HistoricalWeeklyResponse,
  WeeklyLagCorrelationsResponse,
} from "@/lib/types";
import { AlertCircle, Compass, GitCommitHorizontal, TrendingUp } from "lucide-react";

const SCOPES_LIST = [
  "National",
  "Barishal",
  "Chattogram",
  "Dhaka",
  "Khulna",
  "Mymensingh",
  "Rajshahi",
  "Rangpur",
  "Sylhet",
];

const WEATHER_VARIABLES: Array<{
  key: "weekly_precip_mm" | "weekly_temp_c" | "weekly_humidity_pct";
  label: string;
  statLabel: string;
  unit: string;
  shortLabel: string;
}> = [
  {
    key: "weekly_precip_mm",
    label: "Weekly precipitation (mm)",
    statLabel: "Mean weekly precip (mm)",
    unit: "mm",
    shortLabel: "Precip (mm)",
  },
  {
    key: "weekly_temp_c",
    label: "Weekly mean temperature (°C)",
    statLabel: "Mean weekly temp (°C)",
    unit: "°C",
    shortLabel: "Temp (°C)",
  },
  {
    key: "weekly_humidity_pct",
    label: "Weekly relative humidity (%)",
    statLabel: "Mean weekly humidity (%)",
    unit: "%",
    shortLabel: "Humidity (%)",
  },
];

function niceCeiling(rawMax: number, intervals: number): number {
  if (rawMax <= 0) return intervals;
  const rawStep = rawMax / intervals;
  const exp = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const frac = rawStep / exp;
  const niceBases = [1, 2, 2.5, 5, 6, 8, 10];
  const base = niceBases.find((b) => b >= frac) ?? 10;
  return base * exp * intervals;
}

function addDaysIso(isoDate: string, days: number): string {
  const dt = new Date(`${isoDate}T00:00:00Z`);
  dt.setUTCDate(dt.getUTCDate() + days);
  return dt.toISOString().slice(0, 10);
}

interface LagExplorerProps {
  currentScope: string;
  currentVariable: string;
  historicalWeekly: HistoricalWeeklyResponse | null;
  weeklyLags: WeeklyLagCorrelationsResponse | null;
  onScopeChange: (scope: string) => void;
  onVariableChange: (variable: string) => void;
  isLoading: boolean;
}

export function LagExplorer({
  currentScope,
  currentVariable,
  historicalWeekly,
  weeklyLags,
  onScopeChange,
  onVariableChange,
  isLoading,
}: LagExplorerProps) {
  const [hoveredLag, setHoveredLag] = useState<number | null>(null);

  const varMeta =
    WEATHER_VARIABLES.find((v) => v.key === currentVariable) ??
    WEATHER_VARIABLES[0];

  const series = useMemo(
    () => historicalWeekly?.series ?? [],
    [historicalWeekly]
  );

  const lagRows = useMemo(() => weeklyLags?.rows ?? [], [weeklyLags]);

  const rawByLag = useMemo(() => {
    const map = new Map<
      number,
      { rho: number | null; n: number; null_reason: string | null }
    >();
    for (const r of lagRows) {
      if (r.transform === "raw") {
        map.set(r.lag_weeks, {
          rho: r.rho,
          n: r.n,
          null_reason: r.null_reason,
        });
      }
    }
    return map;
  }, [lagRows]);

  const diffByLag = useMemo(() => {
    const map = new Map<
      number,
      { rho: number | null; n: number; null_reason: string | null }
    >();
    for (const r of lagRows) {
      if (r.transform === "diff_log") {
        map.set(r.lag_weeks, {
          rho: r.rho,
          n: r.n,
          null_reason: r.null_reason,
        });
      }
    }
    return map;
  }, [lagRows]);

  const totalCases = useMemo(
    () => series.reduce((acc, pt) => acc + pt.weekly_cases, 0),
    [series]
  );

  const meanWeatherVal = useMemo(() => {
    if (series.length === 0) return "0.0";
    const sum = series.reduce((acc, pt) => acc + pt[varMeta.key], 0);
    return (sum / series.length).toFixed(1);
  }, [series, varMeta.key]);

  const maxCases = useMemo(() => {
    if (series.length === 0) return 100;
    const rawMax = Math.max(...series.map((s) => s.weekly_cases), 10);
    return niceCeiling(rawMax, 4);
  }, [series]);

  const weatherBounds = useMemo(() => {
    if (series.length === 0) return { min: 0, max: 100 };
    if (varMeta.key === "weekly_precip_mm") {
      const m = Math.max(...series.map((s) => s.weekly_precip_mm), 10);
      return { min: 0, max: niceCeiling(m, 4) };
    }
    if (varMeta.key === "weekly_humidity_pct") {
      return { min: 40, max: 100 };
    }
    const vals = series.map((s) => s.weekly_temp_c);
    const minV = Math.floor(Math.min(...vals, 10) / 5) * 5;
    const span = niceCeiling(Math.max(...vals, 35) - minV, 4);
    return { min: minV, max: Math.max(minV + span, minV + 20) };
  }, [series, varMeta.key]);

  const windowEnd = useMemo(() => {
    if (series.length === 0) return "2024-12-29";
    return addDaysIso(series[series.length - 1].week_start, 6);
  }, [series]);

  const activeLag = hoveredLag ?? 0;
  const activeRaw = rawByLag.get(activeLag);
  const activeDiff = diffByLag.get(activeLag);

  const sourceLabel =
    historicalWeekly?.source_label ||
    "secondary source: transcribed from DGHS daily press releases (unverified transcription by third party)";

  return (
    <div className="space-y-6">
      {/* Calm secondary source disclosure */}
      <div
        id="historical-source-notice"
        className="rounded-lg p-4 bg-warning-subtle border border-warning/30 flex items-start gap-3"
      >
        <AlertCircle className="w-4 h-4 text-warning shrink-0 mt-0.5" />
        <div className="text-sm text-secondary leading-relaxed space-y-1">
          <p className="text-primary font-medium">{sourceLabel}</p>
          <p className="text-xs text-secondary">
            Dataset A, Mendeley (Naher), DOI{" "}
            <a
              href="https://doi.org/10.17632/z5mvwrfgsz.1"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent-text hover:underline font-mono"
            >
              10.17632/z5mvwrfgsz.1
            </a>
            ,{" "}
            <a
              href="https://creativecommons.org/licenses/by/4.0/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent-text hover:underline"
            >
              CC BY 4.0
            </a>
            ; changes: dates shifted -1 day, aggregated to ISO weeks.
          </p>
        </div>
      </div>

      {/* Scope & Weather Variable Selectors */}
      <div className="rounded-lg p-5 bg-surface border border-subtle flex flex-col lg:flex-row lg:items-end justify-between gap-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 flex-1">
          <div>
            <label
              htmlFor="scope-selector"
              className="text-xs font-medium text-secondary flex items-center gap-1.5 mb-2"
            >
              <Compass className="w-3.5 h-3.5 text-accent-text" />
              <span>Geographic scope</span>
            </label>
            <select
              id="scope-selector"
              value={currentScope}
              onChange={(e) => onScopeChange(e.target.value)}
              disabled={isLoading}
              className="w-full bg-canvas border border-subtle hover:border-hover text-primary rounded-lg px-3.5 py-2.5 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent cursor-pointer"
            >
              {SCOPES_LIST.map((s) => (
                <option key={s} value={s}>
                  {s === "National" ? "National (all 8 divisions)" : s}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              htmlFor="variable-selector"
              className="text-xs font-medium text-secondary flex items-center gap-1.5 mb-2"
            >
              <TrendingUp className="w-3.5 h-3.5 text-accent-text" />
              <span>Climate variable (ERA5)</span>
            </label>
            <select
              id="variable-selector"
              value={currentVariable}
              onChange={(e) => onVariableChange(e.target.value)}
              disabled={isLoading}
              className="w-full bg-canvas border border-subtle hover:border-hover text-primary rounded-lg px-3.5 py-2.5 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent cursor-pointer"
            >
              {WEATHER_VARIABLES.map((v) => (
                <option key={v.key} value={v.key}>
                  {v.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3 shrink-0">
          <div className="px-3.5 py-2.5 rounded-lg bg-canvas border border-subtle">
            <span className="text-xs text-secondary block">ISO weeks</span>
            <span className="text-base font-semibold font-mono tabular-nums text-primary">
              {series.length}
            </span>
          </div>
          <div
            className="px-3.5 py-2.5 rounded-lg bg-canvas border border-subtle"
            title="Excludes the cases on report dates in the 2 dropped partial ISO weeks"
          >
            <span className="text-xs text-secondary block">
              Cases in {series.length} complete weeks
            </span>
            <span className="text-base font-semibold font-mono tabular-nums text-primary">
              {totalCases.toLocaleString()}
            </span>
          </div>
          <div className="px-3.5 py-2.5 rounded-lg bg-canvas border border-subtle">
            <span className="text-xs text-secondary block">
              {varMeta.statLabel}
            </span>
            <span className="text-base font-semibold font-mono tabular-nums text-accent-text">
              {meanWeatherVal}
              {varMeta.unit}
            </span>
          </div>
        </div>
      </div>

      {/* Weekly 2022-2024 Chart */}
      <div className="rounded-lg p-5 bg-surface border border-subtle">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
          <div>
            <h3 className="text-base font-semibold text-primary">
              Weekly dengue cases and {varMeta.shortLabel.toLowerCase()} (
              {currentScope}, 2022–2024)
            </h3>
            <p className="text-xs text-secondary mt-0.5">
              <span className="font-mono tabular-nums">{series.length}</span>{" "}
              ISO weeks,{" "}
              <span className="font-mono tabular-nums">
                {series[0]?.week_start ?? "2022-01-03"}
              </span>{" "}
              to <span className="font-mono tabular-nums">{windowEnd}</span>
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-xs text-secondary">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-2 bg-accent opacity-80 inline-block rounded-sm" />
              Weekly cases
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-muted-line inline-block" />
              {varMeta.label}
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
              padLeft: 50,
              padRight: 12,
              padTop: 16,
              padBottom: 32,
              ticks: [0, 0.5, 1],
              showRightAxis: false,
              fontSizeClass: "text-[11px]",
              barWidth: 1.4,
            },
            {
              key: "desktop",
              className: "hidden sm:block w-full h-auto",
              width: 860,
              height: 280,
              padLeft: 58,
              padRight: 52,
              padTop: 22,
              padBottom: 36,
              ticks: [0, 0.25, 0.5, 0.75, 1],
              showRightAxis: true,
              fontSizeClass: "text-[11px]",
              barWidth: 3.4,
            },
          ].map((cfg) => {
            const plotW = cfg.width - cfg.padLeft - cfg.padRight;
            const plotH = cfg.height - cfg.padTop - cfg.padBottom;
            const xAt = (idx: number) =>
              cfg.padLeft + (idx / Math.max(series.length - 1, 1)) * plotW;
            const yCases = (val: number) =>
              cfg.padTop + plotH - (val / maxCases) * plotH;
            const yWeather = (val: number) => {
              const span = Math.max(weatherBounds.max - weatherBounds.min, 1);
              const clamped = Math.min(
                Math.max(val, weatherBounds.min),
                weatherBounds.max
              );
              return (
                cfg.padTop +
                plotH -
                ((clamped - weatherBounds.min) / span) * plotH
              );
            };
            const pathD = series
              .map(
                (s, i) =>
                  `${i === 0 ? "M" : "L"} ${xAt(i)} ${yWeather(s[varMeta.key])}`
              )
              .join(" ");

            return (
              <svg
                key={cfg.key}
                viewBox={`0 0 ${cfg.width} ${cfg.height}`}
                className={cfg.className}
                role="img"
                aria-label={`Weekly dengue cases and ${varMeta.shortLabel} for ${currentScope}`}
              >
                {cfg.ticks.map((frac) => {
                  const y = cfg.padTop + plotH * (1 - frac);
                  const casesLabel = Math.round(maxCases * frac).toLocaleString();
                  const weatherLabel = (
                    weatherBounds.min +
                    (weatherBounds.max - weatherBounds.min) * frac
                  ).toFixed(0);
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
                        {casesLabel}
                      </text>
                      {cfg.showRightAxis && (
                        <text
                          x={cfg.width - cfg.padRight + 8}
                          y={y + 4}
                          textAnchor="start"
                          className={`fill-muted-line ${cfg.fontSizeClass} font-mono`}
                        >
                          {weatherLabel}
                          {varMeta.unit}
                        </text>
                      )}
                    </g>
                  );
                })}

                {series.map((s, idx) => {
                  const x = xAt(idx);
                  const barH = Math.max(
                    0,
                    cfg.padTop + plotH - yCases(s.weekly_cases)
                  );
                  return (
                    <rect
                      key={s.iso_week}
                      x={x - cfg.barWidth / 2}
                      y={yCases(s.weekly_cases)}
                      width={cfg.barWidth}
                      height={barH}
                      className="fill-accent animate-bar-grow-y"
                      opacity={0.78}
                    />
                  );
                })}

                {series.length > 1 && (
                  <path
                    d={pathD}
                    fill="none"
                    className="stroke-muted-line"
                    strokeWidth={cfg.key === "mobile" ? 1.5 : 1.75}
                    strokeLinejoin="round"
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
                      {series[0].week_start}
                    </text>
                    {cfg.key === "desktop" && series.length > 2 && (
                      <text
                        x={cfg.padLeft + plotW / 2}
                        y={cfg.height - 8}
                        textAnchor="middle"
                        className={`fill-secondary ${cfg.fontSizeClass} font-mono`}
                      >
                        {series[Math.floor(series.length / 2)].week_start}
                      </text>
                    )}
                    <text
                      x={cfg.width - cfg.padRight}
                      y={cfg.height - 8}
                      textAnchor="end"
                      className={`fill-secondary ${cfg.fontSizeClass} font-mono`}
                    >
                      {windowEnd}
                    </text>
                  </>
                )}
              </svg>
            );
          })}
        </div>

        {/* Open-Meteo CC BY 4.0 Attribution */}
        <p className="text-xs text-secondary mt-3 pt-3 border-t border-subtle flex flex-wrap items-center gap-x-1.5 gap-y-1">
          <a
            href="https://open-meteo.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent-text hover:underline"
          >
            Weather data by Open-Meteo.com
          </a>
          <span>·</span>
          <a
            href="https://creativecommons.org/licenses/by/4.0/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent-text hover:underline"
          >
            CC BY 4.0
          </a>
          <span>· district values averaged to weekly series</span>
        </p>
      </div>

      {/* Lag Correlation Profile (0-8 weeks) */}
      <div className="rounded-lg p-5 bg-surface border border-subtle space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-base font-semibold text-primary flex items-center gap-2">
              <GitCommitHorizontal className="w-4 h-4 text-accent-text" />
              <span>
                Weekly Spearman rank correlation (ρ) across lags 0–8 weeks
              </span>
            </h3>
            <p className="text-xs text-secondary mt-0.5">
              {currentScope} · {varMeta.label}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-xs text-secondary">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-accent inline-block" />
              Raw weekly levels
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-muted-line inline-block border-b border-dashed" />
              Differenced (Δlog)
            </span>
          </div>
        </div>

        {/* Interactive hover readout */}
        <div className="px-3.5 py-2.5 rounded-lg bg-canvas border border-subtle flex flex-wrap items-center justify-between gap-3 text-xs">
          <span className="text-secondary font-medium">
            Lag{" "}
            <span className="font-mono tabular-nums text-primary">
              {activeLag}
            </span>{" "}
            {activeLag === 1 ? "week" : "weeks"}
          </span>
          <div className="flex flex-wrap items-center gap-4 font-mono tabular-nums">
            <span className="text-primary">
              raw ρ:{" "}
              <span className="text-accent-text">
                {activeRaw?.rho !== null && activeRaw?.rho !== undefined
                  ? activeRaw.rho.toFixed(2)
                  : activeRaw?.null_reason ?? "n/a"}
              </span>{" "}
              <span className="text-secondary">
                (n={activeRaw?.n ?? 0})
              </span>
            </span>
            <span className="text-primary">
              diff_log ρ:{" "}
              <span className="text-primary">
                {activeDiff?.rho !== null && activeDiff?.rho !== undefined
                  ? activeDiff.rho.toFixed(2)
                  : activeDiff?.null_reason ?? "n/a"}
              </span>{" "}
              <span className="text-secondary">
                (n={activeDiff?.n ?? 0})
              </span>
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
              padRight: 16,
              padTop: 16,
              padBottom: 32,
              ticks: [-1, 0, 1],
              fontSizeClass: "text-[11px]",
            },
            {
              key: "desktop",
              className: "hidden sm:block w-full h-auto",
              width: 860,
              height: 240,
              padLeft: 52,
              padRight: 28,
              padTop: 20,
              padBottom: 34,
              ticks: [-1, -0.5, 0, 0.5, 1],
              fontSizeClass: "text-[11px]",
            },
          ].map((cfg) => {
            const plotW = cfg.width - cfg.padLeft - cfg.padRight;
            const plotH = cfg.height - cfg.padTop - cfg.padBottom;
            const lags = [0, 1, 2, 3, 4, 5, 6, 7, 8];
            const xAt = (lag: number) => cfg.padLeft + (lag / 8) * plotW;
            const yAt = (rho: number) =>
              cfg.padTop + ((1 - Math.min(Math.max(rho, -1), 1)) / 2) * plotH;

            const rawPoints = lags
              .map((l) => ({ lag: l, rho: rawByLag.get(l)?.rho ?? null }))
              .filter((p): p is { lag: number; rho: number } => p.rho !== null);

            const diffPoints = lags
              .map((l) => ({ lag: l, rho: diffByLag.get(l)?.rho ?? null }))
              .filter((p): p is { lag: number; rho: number } => p.rho !== null);

            const rawPath = rawPoints
              .map(
                (p, i) =>
                  `${i === 0 ? "M" : "L"} ${xAt(p.lag)} ${yAt(p.rho)}`
              )
              .join(" ");

            const diffPath = diffPoints
              .map(
                (p, i) =>
                  `${i === 0 ? "M" : "L"} ${xAt(p.lag)} ${yAt(p.rho)}`
              )
              .join(" ");

            return (
              <svg
                key={cfg.key}
                viewBox={`0 0 ${cfg.width} ${cfg.height}`}
                className={cfg.className}
                role="img"
                aria-label={`Spearman correlation across lags 0 to 8 weeks for ${currentScope}`}
              >
                {cfg.ticks.map((val) => {
                  const y = yAt(val);
                  const isZero = val === 0;
                  return (
                    <g key={val}>
                      <line
                        x1={cfg.padLeft}
                        y1={y}
                        x2={cfg.width - cfg.padRight}
                        y2={y}
                        stroke={isZero ? "#52525b" : "#27272a"}
                        strokeWidth={isZero ? 1.25 : 1}
                        strokeDasharray={isZero ? undefined : "3 3"}
                      />
                      <text
                        x={cfg.padLeft - 8}
                        y={y + 4}
                        textAnchor="end"
                        className={`fill-secondary ${cfg.fontSizeClass} font-mono`}
                      >
                        {val.toFixed(cfg.key === "mobile" ? 0 : 1)}
                      </text>
                    </g>
                  );
                })}

                {rawPath && (
                  <path
                    d={rawPath}
                    fill="none"
                    className="stroke-accent"
                    strokeWidth={2}
                    strokeLinejoin="round"
                  />
                )}

                {diffPath && (
                  <path
                    d={diffPath}
                    fill="none"
                    className="stroke-muted-line"
                    strokeWidth={2}
                    strokeDasharray="5 4"
                    strokeLinejoin="round"
                  />
                )}

                {lags.map((lag) => {
                  const x = xAt(lag);
                  const rawEntry = rawByLag.get(lag);
                  const diffEntry = diffByLag.get(lag);
                  const rawRho = rawEntry?.rho;
                  const diffRho = diffEntry?.rho;
                  const isSelected = activeLag === lag;
                  const tooltipText = `Lag ${lag}w: raw ρ=${
                    rawRho !== null && rawRho !== undefined
                      ? rawRho.toFixed(2)
                      : rawEntry?.null_reason ?? "n/a"
                  } (n=${rawEntry?.n ?? 0}), diff_log ρ=${
                    diffRho !== null && diffRho !== undefined
                      ? diffRho.toFixed(2)
                      : diffEntry?.null_reason ?? "n/a"
                  } (n=${diffEntry?.n ?? 0})`;
                  return (
                    <g
                      key={lag}
                      className="cursor-pointer"
                      onMouseEnter={() => setHoveredLag(lag)}
                      onFocus={() => setHoveredLag(lag)}
                      tabIndex={0}
                      aria-label={tooltipText}
                    >
                      <title>{tooltipText}</title>
                      <rect
                        x={x - plotW / 18}
                        y={cfg.padTop}
                        width={plotW / 9}
                        height={plotH}
                        fill="transparent"
                      />
                      {rawRho !== null && rawRho !== undefined && (
                        <circle
                          cx={x}
                          cy={yAt(rawRho)}
                          r={isSelected ? 4.5 : 3}
                          className="fill-accent"
                        />
                      )}
                      {diffRho !== null && diffRho !== undefined && (
                        <circle
                          cx={x}
                          cy={yAt(diffRho)}
                          r={isSelected ? 4.5 : 3}
                          className="fill-muted-line"
                        />
                      )}
                      <text
                        x={x}
                        y={cfg.height - 8}
                        textAnchor="middle"
                        className={`fill-secondary ${cfg.fontSizeClass} font-mono`}
                      >
                        {lag}w
                      </text>
                    </g>
                  );
                })}
              </svg>
            );
          })}
        </div>

        <p className="text-xs text-secondary pt-3 border-t border-subtle leading-relaxed">
          Descriptive only. Raw-series values largely reflect shared
          seasonality; the differenced series is a sensitivity check. No
          p-values (see{" "}
          <a
            href="https://github.com/TahmidShafi/dghs-cleanpulse/blob/main/docs/analysis_plan.md"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent-text hover:underline"
          >
            analysis plan
          </a>{" "}
          and{" "}
          <a
            href="https://github.com/TahmidShafi/dghs-cleanpulse/blob/main/docs/analysis_results.md"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent-text hover:underline"
          >
            analysis results
          </a>
          ).
        </p>
      </div>
    </div>
  );
}
