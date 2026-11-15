"""Unit tests for pre-registered weekly climate-dengue analysis on small synthetic data."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from cleanpulse.gold.weekly_analysis import (
    build_weekly_scope_climate_cases,
    compute_lag_correlations,
    spearman_rho,
)
from cleanpulse.silver.dengue_secondary import CANONICAL_DIVISIONS
from cleanpulse.silver.weather_division import WEATHER_SCOPES


def test_spearman_rho_exact_ties_and_constant_series() -> None:
    # Hand-checkable ties: x = [1, 2, 2, 4] -> ranks [1, 2.5, 2.5, 4]
    # y = [10, 20, 30, 40] -> ranks [1, 2, 3, 4]
    # Exact Pearson of [1, 2.5, 2.5, 4] and [1, 2, 3, 4] = 0.9 / sqrt(0.9 * 1.0) = 0.948683298...
    x = pd.Series([1.0, 2.0, 2.0, 4.0])
    y = pd.Series([10.0, 20.0, 30.0, 40.0])
    rho, reason = spearman_rho(x, y)
    assert reason is None
    assert rho == pytest.approx(0.9486832980505138, abs=1e-12)

    const_x = pd.Series([5.0, 5.0, 5.0, 5.0])
    rho_c, reason_c = spearman_rho(const_x, y)
    assert rho_c is None
    assert reason_c == "constant series"


def test_lag_and_differencing_alignment_on_synthetic_weeks() -> None:
    # 12 contiguous ISO weeks starting 2022-01-03 (2022-W01)
    # Non-monotone precipitation wave so lag 2 matches cases[t] == precip[t-2] * 10
    # with rho == 1.0, while lag 0 does not.
    precip = [10.0, 2.0, 8.0, 4.0, 12.0, 1.0, 9.0, 3.0, 11.0, 5.0, 7.0, 6.0]
    cases = [1, 1] + [int(p * 10) for p in precip[:-2]]
    rows = []
    start = date(2022, 1, 3)
    for w in range(12):
        ws = start + timedelta(days=7 * w)
        we = ws + timedelta(days=6)
        rows.append(
            {
                "scope": "National",
                "iso_year": 2022,
                "iso_week": w + 1,
                "week_start_date": ws.isoformat(),
                "week_end_date": we.isoformat(),
                "weekly_cases": cases[w],
                "weekly_precip_mm": precip[w],
                "weekly_temp_c": 25.0,  # constant -> null
                "weekly_humidity_pct": float(80 - w),
            }
        )
    df_w = pd.DataFrame(rows)
    lag_df = compute_lag_correlations(df_w, assert_expected_counts=False)

    p_raw_lag2 = lag_df[
        (lag_df["variable"] == "weekly_precip_mm")
        & (lag_df["transform"] == "raw")
        & (lag_df["lag_weeks"] == 2)
    ].iloc[0]
    assert p_raw_lag2["rho"] == pytest.approx(1.0)
    assert p_raw_lag2["n"] == 10
    assert pd.isna(p_raw_lag2["null_reason"])

    p_raw_lag0 = lag_df[
        (lag_df["variable"] == "weekly_precip_mm")
        & (lag_df["transform"] == "raw")
        & (lag_df["lag_weeks"] == 0)
    ].iloc[0]
    assert p_raw_lag0["rho"] < 0.5

    t_const = lag_df[
        (lag_df["variable"] == "weekly_temp_c")
        & (lag_df["transform"] == "raw")
        & (lag_df["lag_weeks"] == 0)
    ].iloc[0]
    assert pd.isna(t_const["rho"])
    assert t_const["null_reason"] == "constant series"

    # Differencing reduces n by 1: 12 - 1 - lag_k
    p_diff_lag2 = lag_df[
        (lag_df["variable"] == "weekly_precip_mm")
        & (lag_df["transform"] == "diff_log")
        & (lag_df["lag_weeks"] == 2)
    ].iloc[0]
    assert p_diff_lag2["n"] == 9
    assert p_diff_lag2["rho"] > 0.9


def test_iso_week_shift_minus_one_day_and_partial_edge_drop(tmp_path: Path) -> None:
    d_rows = []
    w_rows = []
    for i in range(17):
        rep = date(2022, 1, 1) + timedelta(days=i)
        eff = rep - timedelta(days=1)
        for div in CANONICAL_DIVISIONS:
            d_rows.append(
                {
                    "report_date": rep.isoformat(),
                    "division": div,
                    "cases": 1,
                    "source_label": "sec",
                }
            )
        for scope in WEATHER_SCOPES:
            w_rows.append(
                {
                    "date": eff.isoformat(),
                    "scope": scope,
                    "temperature_2m_mean": 25.0,
                    "precipitation_sum": 2.0,
                    "relative_humidity_2m_mean": 75.0,
                    "district_count": 64 if scope == "National" else 8,
                }
            )
    d_path = tmp_path / "dengue.parquet"
    w_path = tmp_path / "weather.parquet"
    pd.DataFrame(d_rows).to_parquet(d_path, index=False)
    pd.DataFrame(w_rows).to_parquet(w_path, index=False)

    weekly, dropped = build_weekly_scope_climate_cases(d_path, w_path, assert_expected_counts=False)
    assert len(dropped) == 1
    assert (dropped[0].iso_year, dropped[0].iso_week, dropped[0].case_days) == (2021, 52, 3)
    nat = weekly[weekly["scope"] == "National"]
    assert len(nat) == 2
    assert list(nat["week_start_date"]) == ["2022-01-03", "2022-01-10"]
    assert list(nat["weekly_cases"]) == [56, 56]
