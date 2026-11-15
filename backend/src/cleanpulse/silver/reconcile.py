"""Cross-source reconciliation between Mendeley A, Mendeley B, and DGHS published totals."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SILVER_DIR = REPO_ROOT / "data" / "silver"
DEFAULT_REFERENCE_CSV = REPO_ROOT / "data" / "reference" / "dghs_published_annual_totals.csv"
DEFAULT_REPORT_PATH = REPO_ROOT / "docs" / "reconciliation_report.md"


@dataclass(frozen=True)
class ReconciliationOutputs:
    """Paths to generated reconciliation Parquet tables and Markdown report."""

    a_vs_ref_path: Path
    b_vs_ref_path: Path
    a_monthly_vs_b_path: Path
    report_path: Path


def _pct_diff(actual: float, ref: float) -> float:
    return round(((actual - ref) / ref) * 100.0, 4) if ref != 0 else 0.0


def run_reconciliation(
    silver_dir: Path | None = None,
    reference_csv: Path | None = None,
    report_path: Path | None = None,
) -> ReconciliationOutputs:
    """Compute all three reconciliation tables and render docs/reconciliation_report.md."""
    s_dir = silver_dir or DEFAULT_SILVER_DIR
    ref_path = reference_csv or DEFAULT_REFERENCE_CSV
    out_md = report_path or DEFAULT_REPORT_PATH

    df_a = pd.read_parquet(s_dir / "dengue_division_daily.parquet")
    df_b = pd.read_parquet(s_dir / "dengue_division_monthly_b.parquet")
    df_ref = pd.read_csv(ref_path)

    required_ref_cols = {
        "year",
        "cases",
        "deaths",
        "scope_note",
        "source_outlet",
        "source_url",
        "accessed_utc",
        "verified_on_page",
    }
    missing = required_ref_cols - set(df_ref.columns)
    if missing:
        raise ValueError(f"Reference CSV missing columns: {sorted(missing)}")

    # 1. Dataset A annual vs DGHS published reference (2022-2024)
    df_a["year"] = pd.to_datetime(df_a["report_date"]).dt.year
    a_annual = (
        df_a.groupby("year", as_index=False)["cases"].sum().rename(columns={"cases": "a_cases"})
    )
    a_vs_ref = pd.merge(
        a_annual,
        df_ref[["year", "cases", "scope_note", "source_outlet", "verified_on_page"]].rename(
            columns={"cases": "ref_cases"}
        ),
        on="year",
        how="inner",
    )
    a_vs_ref["abs_diff"] = a_vs_ref["a_cases"] - a_vs_ref["ref_cases"]
    a_vs_ref["pct_diff_percent"] = [
        _pct_diff(float(a), float(r))
        for a, r in zip(a_vs_ref["a_cases"], a_vs_ref["ref_cases"], strict=True)
    ]

    # 2. Dataset B annual vs DGHS published reference
    b_annual = (
        df_b.groupby("year", as_index=False)[["infected", "death"]]
        .sum()
        .rename(columns={"infected": "b_infected", "death": "b_death"})
    )
    b_vs_ref = pd.merge(
        b_annual,
        df_ref[
            ["year", "cases", "deaths", "scope_note", "source_outlet", "verified_on_page"]
        ].rename(columns={"cases": "ref_cases", "deaths": "ref_deaths"}),
        on="year",
        how="inner",
    )
    b_vs_ref["cases_diff"] = b_vs_ref["b_infected"] - b_vs_ref["ref_cases"]
    b_vs_ref["deaths_diff"] = b_vs_ref["b_death"] - b_vs_ref["ref_deaths"]

    # 3. Dataset A monthly vs Dataset B (2022-2024) by (division, year, month)
    df_a["month"] = pd.to_datetime(df_a["report_date"]).dt.month
    a_monthly = (
        df_a[df_a["year"].between(2022, 2024)]
        .groupby(["division", "year", "month"], as_index=False)["cases"]
        .sum()
        .rename(columns={"cases": "a_cases"})
    )
    b_sub = df_b[df_b["year"].between(2022, 2024)][
        ["division", "year", "month", "infected"]
    ].rename(columns={"infected": "b_infected"})

    merged = pd.merge(
        a_monthly,
        b_sub,
        on=["division", "year", "month"],
        how="outer",
        indicator=True,
    )
    joined = merged[merged["_merge"] == "both"].drop(columns=["_merge"]).copy()
    unmatched_a = int((merged["_merge"] == "left_only").sum())
    unmatched_b = int((merged["_merge"] == "right_only").sum())

    joined["diff"] = joined["a_cases"] - joined["b_infected"]
    joined["abs_diff"] = joined["diff"].abs()
    denom = joined["b_infected"].abs().clip(lower=1)
    joined["rel_diff"] = joined["abs_diff"] / denom
    joined["exact_match"] = joined["abs_diff"] == 0
    joined["within_1pct"] = joined["rel_diff"] <= 0.01
    joined["within_5pct"] = joined["rel_diff"] <= 0.05

    a_vs_ref_path = s_dir / "reconcile_a_vs_reference.parquet"
    b_vs_ref_path = s_dir / "reconcile_b_vs_reference.parquet"
    a_monthly_vs_b_path = s_dir / "reconcile_a_monthly_vs_b.parquet"
    a_vs_ref.to_parquet(a_vs_ref_path, index=False)
    b_vs_ref.to_parquet(b_vs_ref_path, index=False)
    joined.to_parquet(a_monthly_vs_b_path, index=False)

    n_pairs = len(joined)
    n_exact = int(joined["exact_match"].sum()) if n_pairs else 0
    n_1pct = int(joined["within_1pct"].sum()) if n_pairs else 0
    n_5pct = int(joined["within_5pct"].sum()) if n_pairs else 0
    pct_exact = (100.0 * n_exact / n_pairs) if n_pairs else 0.0
    pct_1 = (100.0 * n_1pct / n_pairs) if n_pairs else 0.0
    pct_5 = (100.0 * n_5pct / n_pairs) if n_pairs else 0.0
    top_gaps = joined.sort_values("abs_diff", ascending=False).head(10)[
        ["division", "year", "month", "a_cases", "b_infected", "diff"]
    ]

    md_lines = [
        "<!-- Generated by cleanpulse reconcile-sources — do not edit by hand -->",
        "# Secondary Source Reconciliation Report",
        "",
        "## 1. Dataset A Annual Totals vs Published DGHS Reference",
        "",
        a_vs_ref.to_markdown(index=False),
        "",
        "## 2. Dataset B Annual Totals vs Published DGHS Reference (Reconciliation Only)",
        "",
        b_vs_ref.to_markdown(index=False),
        "",
        "## 3. Dataset A (Monthly Sum) vs Dataset B by Division-Month (2022–2024)",
        "",
        f"- **Joined pairs:** {n_pairs}",
        f"- **Unmatched keys (A only):** {unmatched_a}",
        f"- **Unmatched keys (B only):** {unmatched_b}",
        f"- **Exact matches:** {n_exact}/{n_pairs} ({pct_exact:.2f}%)",
        f"- **Within 1% (`|A-B|/max(|B|,1) <= 0.01`):** {n_1pct}/{n_pairs} ({pct_1:.2f}%)",
        f"- **Within 5% (`|A-B|/max(|B|,1) <= 0.05`):** {n_5pct}/{n_pairs} ({pct_5:.2f}%)",
        "",
        "### Top 10 Largest Absolute Division-Month Differences",
        "",
        top_gaps.to_markdown(index=False),
        "",
    ]
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(md_lines), encoding="utf-8")

    return ReconciliationOutputs(
        a_vs_ref_path=a_vs_ref_path,
        b_vs_ref_path=b_vs_ref_path,
        a_monthly_vs_b_path=a_monthly_vs_b_path,
        report_path=out_md,
    )
