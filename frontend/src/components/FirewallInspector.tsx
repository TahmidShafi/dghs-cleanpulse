"use client";

import React, { useState } from "react";
import { CheckCircle2, FileCode, Filter, Layers } from "lucide-react";
import { AgeCohortItem, AuditAnomaliesResponse } from "@/lib/types";

interface FirewallInspectorProps {
  anomaliesData: AuditAnomaliesResponse;
  ageGroups: AgeCohortItem[];
  fixtureSha256?: string;
}

export function FirewallInspector({
  anomaliesData,
  ageGroups,
  fixtureSha256,
}: FirewallInspectorProps) {
  const [severityFilter, setSeverityFilter] = useState<string>("ALL");
  const [typeFilter, setTypeFilter] = useState<string>("ALL");

  const filteredAnomalies = anomaliesData.anomalies.filter((item) => {
    const matchesSev =
      severityFilter === "ALL" || item.severity === severityFilter;
    const matchesType =
      typeFilter === "ALL" || item.anomaly_type === typeFilter;
    return matchesSev && matchesType;
  });

  const maxCases = Math.max(...ageGroups.map((g) => g.reconciled_total), 1);
  const typeCount = Object.keys(anomaliesData.type_counts).length;

  return (
    <div className="space-y-8">
      {/* 1. Calm Synthetic Demo Notice */}
      <div
        id="synthetic-demo-banner"
        className="rounded-lg p-4 bg-surface border border-subtle border-l-2 border-l-warning flex flex-col sm:flex-row sm:items-center justify-between gap-2"
      >
        <div className="text-sm text-secondary leading-relaxed">
          <span className="text-primary font-medium mr-1.5">
            Synthetic fault-injection demo:
          </span>
          This tab demonstrates the Pandera firewall on hand-authored test input (
          <code className="font-mono text-primary">
            synthetic_dghs_fault_injection.html
          </code>
          ), not real DGHS surveillance data.
        </div>
        {fixtureSha256 && (
          <span
            title={`Full fixture SHA-256: ${fixtureSha256}`}
            className="text-xs font-mono tabular-nums text-secondary shrink-0"
          >
            SHA-256: {fixtureSha256.slice(0, 16)}…
          </span>
        )}
      </div>

      {/* 2. Summary Header */}
      <div className="rounded-lg p-5 bg-surface border border-subtle">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-1">
            <p className="text-xs font-medium text-secondary">
              Zero-silent-data-drop validation policy
            </p>
            <h2 className="text-lg font-semibold text-primary tracking-tight">
              Validation demo
            </h2>
            <p className="text-sm text-secondary max-w-3xl leading-relaxed">
              Demonstrates how CleanPulse detects, quarantines, and deterministically reconciles injected spreadsheet faults (Excel serial date numbers, zero-padding drift, and cross-column sum mismatches) on controlled test input.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-3 shrink-0">
            <div className="px-3.5 py-2.5 rounded-lg bg-canvas border border-subtle text-center">
              <span className="text-xs text-secondary block">Quarantined</span>
              <span className="text-lg font-semibold font-mono tabular-nums text-critical">
                {anomaliesData.severity_counts["CRITICAL"] || 0}
              </span>
            </div>
            <div className="px-3.5 py-2.5 rounded-lg bg-canvas border border-subtle text-center">
              <span className="text-xs text-secondary block">
                Warnings reconciled
              </span>
              <span className="text-lg font-semibold font-mono tabular-nums text-warning">
                {anomaliesData.severity_counts["WARNING"] || 0}
              </span>
            </div>
            <div className="px-3.5 py-2.5 rounded-lg bg-canvas border border-subtle text-center">
              <span className="text-xs text-secondary block">Valid cohorts</span>
              <span className="text-lg font-semibold font-mono tabular-nums text-primary">
                {ageGroups.length}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Bronze HTML vs. Silver Parquet Quarantine Diffs (derived from JSON) */}
      <section className="space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-accent-text shrink-0" />
            <h3 className="text-base font-semibold text-primary">
              Bronze HTML vs. Silver Parquet quarantine diffs
            </h3>
          </div>
          <span className="text-xs text-secondary">
            {anomaliesData.total_anomalies} injected faults across {typeCount}{" "}
            types (synthetic test input)
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {anomaliesData.anomalies.map((anom) => (
            <div
              key={anom.anomaly_id}
              className="rounded-lg p-4 bg-surface border border-subtle hover:border-hover transition-colors flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-2.5">
                  <span className="text-xs font-mono font-medium text-primary">
                    {anom.anomaly_type}
                  </span>
                  <span
                    className={`text-xs font-mono px-1.5 py-0.5 rounded ${
                      anom.severity === "CRITICAL"
                        ? "bg-critical-subtle text-critical border border-critical/40"
                        : "bg-warning-subtle text-warning border border-warning/40"
                    }`}
                  >
                    {anom.severity}
                  </span>
                </div>
                <p className="text-xs text-secondary mb-3 leading-relaxed">
                  {anom.explanation}
                </p>
                <div className="space-y-2 text-xs font-mono">
                  <div className="p-2 rounded bg-canvas border border-subtle text-secondary flex flex-col gap-0.5">
                    <span>- Raw Bronze ({anom.row_key}):</span>
                    <span className="text-primary break-words">
                      {anom.raw_value}
                    </span>
                  </div>
                  <div className="p-2 rounded bg-canvas border border-subtle text-secondary flex flex-col gap-0.5">
                    <span>+ Silver Clean:</span>
                    <span className="text-primary break-words">
                      {anom.repaired_value}
                    </span>
                  </div>
                </div>
              </div>
              <div className="mt-3 pt-2.5 text-xs font-mono text-secondary border-t border-subtle flex items-center justify-between">
                <span>{anom.anomaly_id}</span>
                <span>{anom.table_name}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 4. Interactive Anomaly Audit Table */}
      <section className="space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <FileCode className="w-4 h-4 text-accent-text shrink-0" />
            <h3 className="text-base font-semibold text-primary">
              Structured audit anomaly log (synthetic demo data)
            </h3>
          </div>

          {/* Filter Pills */}
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="text-secondary flex items-center gap-1 mr-1">
              <Filter className="w-3.5 h-3.5" /> Severity:
            </span>
            {["ALL", "CRITICAL", "WARNING"].map((sev) => (
              <button
                key={sev}
                id={`filter-severity-${sev.toLowerCase()}`}
                type="button"
                aria-pressed={severityFilter === sev}
                onClick={() => setSeverityFilter(sev)}
                className={`min-h-[36px] px-2.5 py-1 rounded-md font-mono transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                  severityFilter === sev
                    ? "bg-accent-strong text-white font-medium"
                    : "bg-surface text-secondary hover:text-primary border border-subtle hover:border-hover"
                }`}
              >
                {sev === "ALL" ? "All" : sev}
              </button>
            ))}

            <span className="text-secondary ml-1 mr-1">Type:</span>
            {[
              "ALL",
              "EXCEL_SERIAL_DATE_CAST",
              "ZERO_PAD_DRIFT",
              "GENDER_SUM_MISMATCH",
              "INVALID_AGE_BUCKET",
            ].map((t) => (
              <button
                key={t}
                id={`filter-type-${t.toLowerCase()}`}
                type="button"
                aria-pressed={typeFilter === t}
                onClick={() => setTypeFilter(t)}
                className={`min-h-[36px] px-2.5 py-1 rounded-md font-sans transition-colors cursor-pointer text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                  typeFilter === t
                    ? "bg-accent-strong text-white font-medium"
                    : "bg-surface text-secondary hover:text-primary border border-subtle hover:border-hover"
                }`}
              >
                {t === "EXCEL_SERIAL_DATE_CAST"
                  ? "Excel date"
                  : t === "ZERO_PAD_DRIFT"
                  ? "Zero-pad"
                  : t === "GENDER_SUM_MISMATCH"
                  ? "Sum mismatch"
                  : t === "INVALID_AGE_BUCKET"
                  ? "Invalid bucket"
                  : "All"}
              </button>
            ))}
          </div>
        </div>

        {/* Audit Table */}
        <div className="rounded-lg border border-subtle bg-surface overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-canvas text-secondary border-b border-subtle font-sans font-medium">
                <tr>
                  <th className="px-4 py-3">Anomaly ID</th>
                  <th className="px-4 py-3">Severity</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Row key</th>
                  <th className="px-4 py-3">Raw value</th>
                  <th className="px-4 py-3">Repaired / quarantined</th>
                  <th className="px-4 py-3">Explanation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-subtle text-primary">
                {filteredAnomalies.length > 0 ? (
                  filteredAnomalies.map((anom) => (
                    <tr
                      key={anom.anomaly_id}
                      className="hover:bg-elevated/40 transition-colors"
                    >
                      <td className="px-4 py-3 text-accent-text font-medium whitespace-nowrap">
                        {anom.anomaly_id}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-medium ${
                            anom.severity === "CRITICAL"
                              ? "bg-critical-subtle text-critical border border-critical/40"
                              : "bg-warning-subtle text-warning border border-warning/40"
                          }`}
                        >
                          {anom.severity}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-primary whitespace-nowrap">
                        {anom.anomaly_type}
                      </td>
                      <td className="px-4 py-3 text-secondary whitespace-nowrap">
                        {anom.row_key}
                      </td>
                      <td className="px-4 py-3 text-secondary">
                        {anom.raw_value}
                      </td>
                      <td className="px-4 py-3 text-primary font-medium">
                        {anom.repaired_value}
                      </td>
                      <td className="px-4 py-3 font-sans text-secondary min-w-[220px] leading-relaxed">
                        {anom.explanation}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td
                      colSpan={7}
                      className="px-4 py-8 text-center font-sans text-secondary"
                    >
                      No anomalies matching selected filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* 5. Sanitized Age Cohorts View */}
      <section className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-accent-text shrink-0" />
            <h3 className="text-base font-semibold text-primary">
              Sanitized age cohorts (synthetic demo data)
            </h3>
          </div>
          <span className="text-xs text-secondary">
            Row 21-25 highlights{" "}
            <span className="font-mono text-warning font-medium">
              +10 arithmetic_delta
            </span>
          </span>
        </div>

        {/* Visual Bar Breakdown Chart */}
        <div className="rounded-lg border border-subtle bg-surface p-5">
          <h4 className="text-xs font-medium text-secondary mb-4">
            Case frequency distribution by age cohort (male vs. female vs. total)
          </h4>
          <div className="space-y-2.5">
            {ageGroups.map((cohort) => {
              const totalPct = (cohort.reconciled_total / maxCases) * 100;
              const isDiscrepant = cohort.arithmetic_delta !== 0;

              return (
                <div
                  key={cohort.age_group}
                  className="flex items-center gap-3 text-xs"
                >
                  <div className="w-14 font-mono tabular-nums font-medium text-primary text-right shrink-0">
                    {cohort.age_group}
                  </div>
                  <div className="flex-1 bg-canvas rounded-full h-4 overflow-hidden flex items-center p-0.5 border border-subtle relative">
                    <div
                      style={{
                        width: `${
                          (cohort.male_cases /
                            Math.max(cohort.reconciled_total, 1)) *
                          totalPct
                        }%`,
                      }}
                      className="bg-accent h-full rounded-l-full animate-bar-grow-x"
                      title={`Male: ${cohort.male_cases.toLocaleString()}`}
                    />
                    <div
                      style={{
                        width: `${
                          (cohort.female_cases /
                            Math.max(cohort.reconciled_total, 1)) *
                          totalPct
                        }%`,
                      }}
                      className="bg-muted-line h-full rounded-r-full animate-bar-grow-x"
                      title={`Female: ${cohort.female_cases.toLocaleString()}`}
                    />
                    {isDiscrepant && (
                      <span className="absolute right-2 text-xs font-mono tabular-nums font-medium text-warning">
                        Δ +{cohort.arithmetic_delta}
                      </span>
                    )}
                  </div>
                  <div className="w-20 text-right font-mono tabular-nums text-primary shrink-0">
                    {cohort.reconciled_total.toLocaleString()}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-4 pt-3 border-t border-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-secondary">
            <div className="flex flex-wrap items-center gap-4">
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm bg-accent" /> Male cases
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm bg-muted-line" /> Female cases
              </span>
              <span className="flex items-center gap-1.5 text-warning">
                <span className="w-2 h-2 rounded-full bg-warning" /> Arithmetic
                delta row
              </span>
            </div>
            <span className="text-xs font-mono tabular-nums text-primary">
              Total cohort sum:{" "}
              {ageGroups
                .reduce((acc, c) => acc + c.reconciled_total, 0)
                .toLocaleString()}
            </span>
          </div>
        </div>

        {/* Detailed Cohort Table */}
        <div className="rounded-lg border border-subtle bg-surface overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono tabular-nums">
              <thead className="bg-canvas text-secondary border-b border-subtle font-sans font-medium">
                <tr>
                  <th className="px-4 py-3">Age cohort</th>
                  <th className="px-4 py-3 text-right">Male cases</th>
                  <th className="px-4 py-3 text-right">Female cases</th>
                  <th className="px-4 py-3 text-right">Reported total</th>
                  <th className="px-4 py-3 text-right">Reconciled total</th>
                  <th className="px-4 py-3 text-right">Arithmetic delta</th>
                  <th className="px-4 py-3 text-right">Deaths</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-subtle text-primary">
                {ageGroups.map((cohort) => {
                  const isDelta = cohort.arithmetic_delta !== 0;
                  return (
                    <tr
                      key={cohort.age_group}
                      className={`hover:bg-elevated/40 transition-colors ${
                        isDelta ? "bg-warning-subtle font-medium" : ""
                      }`}
                    >
                      <td className="px-4 py-2.5 text-primary">
                        {cohort.age_group}
                      </td>
                      <td className="px-4 py-2.5 text-right text-accent-text">
                        {cohort.male_cases.toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 text-right text-muted-line">
                        {cohort.female_cases.toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 text-right text-secondary">
                        {cohort.reported_total.toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 text-right text-primary font-medium">
                        {cohort.reconciled_total.toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        {isDelta ? (
                          <span className="px-2 py-0.5 rounded bg-warning-subtle text-warning border border-warning/40">
                            +{cohort.arithmetic_delta}
                          </span>
                        ) : (
                          <span className="text-secondary">0</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-right text-secondary">
                        {cohort.deaths.toLocaleString()}
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
