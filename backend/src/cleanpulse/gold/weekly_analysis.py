"""Pre-registered weekly climate-dengue analysis and Gold table builder."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from cleanpulse.silver.weather_division import WEATHER_SCOPES

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SILVER_DIR = REPO_ROOT / "data" / "silver"
DEFAULT_GOLD_DIR = REPO_ROOT / "data" / "gold"
DEFAULT_RESULTS_MD = REPO_ROOT / "docs" / "analysis_results.md"

CLIMATE_VARIABLES: tuple[str, ...] = (
    "weekly_precip_mm",
    "weekly_temp_c",
    "weekly_humidity_pct",
)
TRANSFORMS: tuple[str, ...] = ("raw", "diff_log")
LAGS_WEEKS: tuple[int, ...] = tuple(range(0, 9))


@dataclass(frozen=True)
class DroppedWeekLog:
    """Record of an incomplete boundary ISO week dropped before correlation."""

    iso_year: int
    iso_week: int
    case_days: int
    paired_days: int
    start_date: str
    end_date: str


@dataclass(frozen=True)
class WeeklyGoldOutputs:
    """Paths and assertion summary produced by the weekly Gold build."""

    weekly_path: Path
    lag_path: Path
    results_md_path: Path
    complete_weeks_per_scope: int
    first_week: str
    last_week: str
    dropped_weeks: tuple[DroppedWeekLog, ...]


def spearman_rho(x: pd.Series, y: pd.Series) -> tuple[float | None, str | None]:
    """Compute descriptive Spearman rho = Pearson correlation of average ranks.

    Returns (None, 'constant series') if either paired series has zero variance.
    Never computes p-values or confidence intervals.
    """
    if len(x) != len(y) or len(x) == 0:
        raise ValueError(f"Invalid paired series lengths: {len(x)} vs {len(y)}")
    if x.nunique(dropna=True) <= 1 or y.nunique(dropna=True) <= 1:
        return None, "constant series"

    rx = x.rank(method="average")
    ry = y.rank(method="average")
    dx = rx - rx.mean()
    dy = ry - ry.mean()
    denom = math.sqrt(float((dx * dx).sum()) * float((dy * dy).sum()))
    if denom == 0.0:
        return None, "constant series"
    return float((dx * dy).sum() / denom), None


def build_weekly_scope_climate_cases(
    dengue_daily_path: Path,
    weather_divisions_path: Path,
    assert_expected_counts: bool = True,
) -> tuple[pd.DataFrame, tuple[DroppedWeekLog, ...]]:
    """Aggregate daily dengue (shifted -1d) and division ERA5 weather to complete ISO weeks."""
    df_d = pd.read_parquet(dengue_daily_path)
    df_w = pd.read_parquet(weather_divisions_path)

    # Effective date = report_date - 1 day per pre-registered plan
    df_d["effective_date"] = (
        pd.to_datetime(df_d["report_date"]) - pd.Timedelta(days=1)
    ).dt.strftime("%Y-%m-%d")

    nat_cases = (
        df_d.groupby("effective_date", as_index=False)["cases"].sum().assign(scope="National")
    )
    div_cases = df_d.rename(columns={"division": "scope"})[["effective_date", "scope", "cases"]]
    all_cases = pd.concat([nat_cases, div_cases], ignore_index=True)

    # ISO 8601 week metadata on all case dates
    eff_dt = pd.to_datetime(all_cases["effective_date"])
    iso = eff_dt.dt.isocalendar()
    all_cases["iso_year"] = iso["year"].astype(int)
    all_cases["iso_week"] = iso["week"].astype(int)

    merged = all_cases.merge(
        df_w,
        left_on=["effective_date", "scope"],
        right_on=["date", "scope"],
        how="left",
    )

    # Track case_days and paired_days per (iso_year, iso_week) on National scope
    nat_merged = merged[merged["scope"] == "National"].copy()
    week_counts = (
        nat_merged.groupby(["iso_year", "iso_week"], as_index=False)
        .agg(
            case_days=("effective_date", "nunique"),
            paired_days=("date", lambda s: int(s.notna().sum())),
            start_date=("effective_date", "min"),
            end_date=("effective_date", "max"),
        )
        .sort_values(["iso_year", "iso_week"])
    )

    dropped: list[DroppedWeekLog] = []
    complete_keys: set[tuple[int, int]] = set()
    for _, row in week_counts.iterrows():
        key = (int(row["iso_year"]), int(row["iso_week"]))
        if int(row["paired_days"]) == 7 and int(row["case_days"]) == 7:
            complete_keys.add(key)
        else:
            dropped.append(
                DroppedWeekLog(
                    iso_year=key[0],
                    iso_week=key[1],
                    case_days=int(row["case_days"]),
                    paired_days=int(row["paired_days"]),
                    start_date=str(row["start_date"]),
                    end_date=str(row["end_date"]),
                )
            )

    complete_mask = [
        (int(y), int(w)) in complete_keys
        for y, w in zip(merged["iso_year"], merged["iso_week"], strict=True)
    ]
    df_complete = merged.loc[complete_mask].copy()
    if (
        df_complete[["precipitation_sum", "temperature_2m_mean", "relative_humidity_2m_mean"]]
        .isna()
        .any()
        .any()
    ):
        raise ValueError("Missing weather values in complete ISO weeks")

    weekly = (
        df_complete.groupby(["scope", "iso_year", "iso_week"], as_index=False)
        .agg(
            week_start_date=("effective_date", "min"),
            week_end_date=("effective_date", "max"),
            weekly_cases=("cases", "sum"),
            weekly_precip_mm=("precipitation_sum", "sum"),
            weekly_temp_c=("temperature_2m_mean", "mean"),
            weekly_humidity_pct=("relative_humidity_2m_mean", "mean"),
        )
        .sort_values(["scope", "iso_year", "iso_week"])
        .reset_index(drop=True)
    )

    if assert_expected_counts:
        scopes_present = tuple(sorted(weekly["scope"].unique()))
        if set(scopes_present) != set(WEATHER_SCOPES):
            raise AssertionError(f"Expected 9 scopes, got {scopes_present}")
        for scope in WEATHER_SCOPES:
            sub = weekly[weekly["scope"] == scope]
            if len(sub) != 156:
                raise AssertionError(f"Scope {scope}: expected 156 weeks, got {len(sub)}")
            first_row = sub.iloc[0]
            last_row = sub.iloc[-1]
            if (int(first_row["iso_year"]), int(first_row["iso_week"])) != (2022, 1):
                raise AssertionError(f"First week must be 2022-W01, got {first_row.to_dict()}")
            if str(first_row["week_start_date"]) != "2022-01-03":
                raise AssertionError(
                    f"First week start must be 2022-01-03, got {first_row['week_start_date']}"
                )
            if (int(last_row["iso_year"]), int(last_row["iso_week"])) != (2024, 52):
                raise AssertionError(f"Last week must be 2024-W52, got {last_row.to_dict()}")
            if str(last_row["week_end_date"]) != "2024-12-29":
                raise AssertionError(
                    f"Last week end must be 2024-12-29, got {last_row['week_end_date']}"
                )

        dropped_summary = [(d.iso_year, d.iso_week, d.case_days) for d in dropped]
        if dropped_summary != [(2021, 52, 3), (2025, 1, 1)]:
            raise AssertionError(
                f"Expected dropped partial weeks [(2021, 52, 3), (2025, 1, 1)], "
                f"got {dropped_summary}"
            )

    return weekly, tuple(dropped)


def compute_lag_correlations(
    weekly_df: pd.DataFrame,
    assert_expected_counts: bool = True,
) -> pd.DataFrame:
    """Compute descriptive Spearman rho at lags 0..8 for raw and diff_log series."""
    records: list[dict[str, object]] = []

    for scope, sub in weekly_df.groupby("scope", sort=False):
        sub_sorted = sub.sort_values("week_start_date").reset_index(drop=True)
        starts = pd.to_datetime(sub_sorted["week_start_date"])
        diffs = starts.diff().dropna()
        if not (diffs == pd.Timedelta(days=7)).all():
            raise AssertionError(f"Non-contiguous ISO weeks in scope {scope}")

        raw_cases = sub_sorted["weekly_cases"].astype(float)
        diff_log_cases = np.log(raw_cases + 1.0).diff()

        for variable in CLIMATE_VARIABLES:
            raw_x = sub_sorted[variable].astype(float)
            diff_x = raw_x.diff()

            for transform in TRANSFORMS:
                y_series = raw_cases if transform == "raw" else diff_log_cases
                x_series = raw_x if transform == "raw" else diff_x

                for lag_k in LAGS_WEEKS:
                    x_shifted = x_series.shift(lag_k)
                    paired = pd.DataFrame({"y": y_series, "x": x_shifted}).dropna()
                    n_obs = len(paired)
                    if assert_expected_counts:
                        expected_n = (156 - lag_k) if transform == "raw" else (155 - lag_k)
                        if n_obs != expected_n:
                            raise AssertionError(
                                f"{scope} {variable} {transform} lag={lag_k}: "
                                f"expected n={expected_n}, got {n_obs}"
                            )
                    rho, null_reason = spearman_rho(paired["y"], paired["x"])
                    records.append(
                        {
                            "scope": str(scope),
                            "variable": variable,
                            "transform": transform,
                            "lag_weeks": lag_k,
                            "rho": rho,
                            "n": n_obs,
                            "null_reason": null_reason,
                        }
                    )

    return pd.DataFrame(records)


def render_analysis_results_md(
    lag_df: pd.DataFrame,
    dropped_weeks: tuple[DroppedWeekLog, ...],
    first_week: str,
    last_week: str,
    complete_weeks: int,
    lag_parquet_rel: str,
) -> str:
    """Render docs/analysis_results.md purely from computed outputs (no prose claims)."""
    nat_df = lag_df[lag_df["scope"] == "National"].copy()
    nat_df["rho"] = nat_df["rho"].map(lambda v: "null" if pd.isna(v) else f"{float(v):.4f}")
    nat_df["null_reason"] = nat_df["null_reason"].fillna("")

    dropped_rows = [
        {
            "iso_week": f"{d.iso_year}-W{d.iso_week:02d}",
            "case_days": d.case_days,
            "paired_weather_days": d.paired_days,
            "effective_date_range": f"{d.start_date}..{d.end_date}",
        }
        for d in dropped_weeks
    ]

    lines = [
        "<!-- Generated by cleanpulse build-weekly-gold — do not edit by hand -->",
        "# Pre-Registered Weekly Climate–Dengue Descriptive Results (2022–2024)",
        "",
        (
            "Source label: *secondary source: transcribed from DGHS daily press releases "
            "(unverified transcription by third party)*; climate: Open-Meteo ERA5 (`models=era5`)."
        ),
        "",
        "## 1. Window & Completeness Assertions",
        "",
        f"- **Complete ISO 8601 weeks per scope:** {complete_weeks} "
        f"(`{first_week}` to `{last_week}`)",
        f"- **Division & full grid results:** `{lag_parquet_rel}` "
        f"({len(lag_df)} rows: 9 scopes × 3 variables × 2 transforms × 9 lags)",
        "",
        "### Dropped Partial Boundary Weeks",
        "",
        pd.DataFrame(dropped_rows).to_markdown(index=False),
        "",
        "## 2. National Descriptive Spearman ρ (Lags 0–8 Weeks)",
        "",
        nat_df[["variable", "transform", "lag_weeks", "rho", "n", "null_reason"]].to_markdown(
            index=False
        ),
        "",
        "## 3. Confounders & Limitations (from `docs/analysis_plan.md`)",
        "",
        "- **No p-values or causal claims:** Spearman ρ is descriptive only; weekly series are "
        "strongly autocorrelated and 486 coefficients are reported across 9 scopes × 3 variables "
        "× 2 transforms × 9 lags.",
        "- **Shared monsoon seasonality:** Both dengue incidence and "
        "rainfall/humidity/temperature follow strong annual monsoon cycles in Bangladesh.",
        "- **Reporting & transcription artifacts:** Weekend/holiday reporting dips, hospital "
        "reporting backlogs, and unverified third-party transcription errors in Dataset A.",
        "- **Outbreak dynamics:** Epidemic autocorrelation, exponential growth/decay phases, "
        "susceptible depletion, and vector-control interventions.",
        "- **Spatial aggregation mismatch:** Division/national weather is an unweighted mean of "
        "district ERA5 grid points, whereas dengue hospitalizations are concentrated in dense "
        "urban centers (notably Dhaka; Dhaka division scope inferred from national totals "
        "matching DGHS published figures).",
        "- **Edge truncation:** Dropping incomplete boundary ISO weeks trims partial "
        "boundary dates.",
        "",
    ]
    return "\n".join(lines)


def build_weekly_gold(
    silver_dir: Path | None = None,
    gold_dir: Path | None = None,
    results_md_path: Path | None = None,
    assert_expected_counts: bool = True,
) -> WeeklyGoldOutputs:
    """Execute pre-registered weekly Gold build and render docs/analysis_results.md."""
    s_dir = silver_dir or DEFAULT_SILVER_DIR
    g_dir = gold_dir or DEFAULT_GOLD_DIR
    out_md = results_md_path or DEFAULT_RESULTS_MD
    g_dir.mkdir(parents=True, exist_ok=True)

    weekly_df, dropped = build_weekly_scope_climate_cases(
        dengue_daily_path=s_dir / "dengue_division_daily.parquet",
        weather_divisions_path=s_dir / "weather_divisions_daily.parquet",
        assert_expected_counts=assert_expected_counts,
    )
    lag_df = compute_lag_correlations(
        weekly_df,
        assert_expected_counts=assert_expected_counts,
    )

    weekly_path = g_dir / "weekly_scope_climate_cases.parquet"
    lag_path = g_dir / "lag_correlations_weekly.parquet"
    weekly_df.to_parquet(weekly_path, index=False)
    lag_df.to_parquet(lag_path, index=False)

    nat_weeks = weekly_df[weekly_df["scope"] == "National"].sort_values("week_start_date")
    first_w = f"{int(nat_weeks.iloc[0]['iso_year'])}-W{int(nat_weeks.iloc[0]['iso_week']):02d}"
    last_w = f"{int(nat_weeks.iloc[-1]['iso_year'])}-W{int(nat_weeks.iloc[-1]['iso_week']):02d}"

    try:
        lag_rel = str(lag_path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        lag_rel = str(lag_path)

    md_text = render_analysis_results_md(
        lag_df=lag_df,
        dropped_weeks=dropped,
        first_week=first_w,
        last_week=last_w,
        complete_weeks=len(nat_weeks),
        lag_parquet_rel=lag_rel,
    )
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(md_text, encoding="utf-8")

    return WeeklyGoldOutputs(
        weekly_path=weekly_path,
        lag_path=lag_path,
        results_md_path=out_md,
        complete_weeks_per_scope=len(nat_weeks),
        first_week=first_w,
        last_week=last_w,
        dropped_weeks=dropped,
    )
