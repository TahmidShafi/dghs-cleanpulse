"""Silver builder for division-level and national daily ERA5 weather."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pandera.pandas as pa

from cleanpulse.silver.dengue_secondary import CANONICAL_DIVISIONS
from cleanpulse.silver.spatial_crosswalk import DEFAULT_CROSSWALK_PATH, load_district_crosswalk

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SILVER_DIR = REPO_ROOT / "data" / "silver"
WEATHER_SCOPES: tuple[str, ...] = ("National", *CANONICAL_DIVISIONS)

WeatherDivisionsDailySchema = pa.DataFrameSchema(
    columns={
        "date": pa.Column(str, nullable=False),
        "scope": pa.Column(str, pa.Check.isin(WEATHER_SCOPES), nullable=False),
        "temperature_2m_mean": pa.Column(float, pa.Check.in_range(-5.0, 55.0), nullable=False),
        "precipitation_sum": pa.Column(float, pa.Check.ge(0.0), nullable=False),
        "relative_humidity_2m_mean": pa.Column(
            float, pa.Check.in_range(0.0, 100.0), nullable=False
        ),
        "district_count": pa.Column(pa.Int64, pa.Check.gt(0), nullable=False),
    },
    unique=["date", "scope"],
    strict=True,
    coerce=True,
)


def build_weather_divisions_daily(
    districts_parquet: Path | None = None,
    crosswalk_path: Path | None = None,
    output_parquet: Path | None = None,
) -> Path:
    """Aggregate 64-district Silver weather into 8 divisions + National daily means."""
    src_parquet = districts_parquet or (DEFAULT_SILVER_DIR / "weather_districts_daily.parquet")
    out_path = output_parquet or (DEFAULT_SILVER_DIR / "weather_divisions_daily.parquet")

    df_dist = pd.read_parquet(src_parquet)
    cw = load_district_crosswalk(crosswalk_path or DEFAULT_CROSSWALK_PATH)
    merged = df_dist.merge(
        cw[["district_id", "division_name"]],
        on="district_id",
        how="left",
        validate="many_to_one",
    )
    if merged["division_name"].isna().any():
        missing = sorted(merged.loc[merged["division_name"].isna(), "district_id"].unique())
        raise ValueError(f"Unmapped district_id(s) in crosswalk: {missing}")

    metrics = ["temperature_2m_mean", "precipitation_sum", "relative_humidity_2m_mean"]
    div_agg = (
        merged.groupby(["date", "division_name"], as_index=False)
        .agg(
            temperature_2m_mean=("temperature_2m_mean", "mean"),
            precipitation_sum=("precipitation_sum", "mean"),
            relative_humidity_2m_mean=("relative_humidity_2m_mean", "mean"),
            district_count=("district_id", "nunique"),
        )
        .rename(columns={"division_name": "scope"})
    )

    nat_agg = (
        merged.groupby("date", as_index=False)
        .agg(
            temperature_2m_mean=("temperature_2m_mean", "mean"),
            precipitation_sum=("precipitation_sum", "mean"),
            relative_humidity_2m_mean=("relative_humidity_2m_mean", "mean"),
            district_count=("district_id", "nunique"),
        )
        .assign(scope="National")
    )

    combined = (
        pd.concat([nat_agg, div_agg], ignore_index=True)[
            ["date", "scope", *metrics, "district_count"]
        ]
        .sort_values(["date", "scope"])
        .reset_index(drop=True)
    )
    validated = WeatherDivisionsDailySchema.validate(combined, lazy=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(".parquet.tmp")
    validated.to_parquet(tmp_path, index=False)
    tmp_path.replace(out_path)
    return out_path
