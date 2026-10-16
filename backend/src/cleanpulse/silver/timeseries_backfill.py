"""180-Day Epidemiological Time-Series Backfill Generator.

Expands dengue_zones_daily.parquet from a single-day snapshot into a complete,
reproducible 180-day time series (2026-04-18 to 2026-10-14) covering all 10 DGHS zones
(1,800 rows total).

Key Features:
  - Anchors final cumulative admissions on 2026-10-14 to official 2026 DGHS ground truth
    (105,316 cumulative national cases across 10 zones).
  - Dynamically links daily admissions to each zone's 14-to-18 day lagged rainfall and humidity
    from weather_districts_daily.parquet.
  - Generates integer admissions via a seeded multinomial process (random_seed=42)
    guaranteeing 100% reproducibility and exact cumulative sum equality.
  - Enforces monotonic cumulative admitted, deaths, and discharges.
  - Strictly validates against DGHSDivisionSilverSchema and persists to Parquet.
"""

from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from cleanpulse.silver.firewall import CANONICAL_ZONES, DGHSDivisionSilverSchema

logger = logging.getLogger(__name__)

DEFAULT_SILVER_WEATHER_PARQUET = (
    Path(__file__).resolve().parents[4] / "data" / "silver" / "weather_districts_daily.parquet"
)
DEFAULT_SILVER_ZONES_PARQUET = (
    Path(__file__).resolve().parents[4] / "data" / "silver" / "dengue_zones_daily.parquet"
)

START_DATE = "2026-04-18"
END_DATE = "2026-10-14"

# Official 2026 DGHS cumulative admissions on 2026-10-14 (Total = 105,316)
ZONE_TARGET_ADMISSIONS: dict[str, int] = {
    "Chattogram": 19153,
    "DSCC": 16618,
    "Barishal": 15858,
    "Dhaka (Out of CC)": 13422,
    "DNCC": 12113,
    "Khulna": 11066,
    "Rajshahi": 7366,
    "Mymensingh": 5694,
    "Rangpur": 3486,
    "Sylhet": 540,
}

# Cumulative deaths target on 2026-10-14 (Total = 452, CFR ~0.43%)
ZONE_TARGET_DEATHS: dict[str, int] = {
    "Chattogram": 82,
    "DSCC": 112,
    "Barishal": 68,
    "Dhaka (Out of CC)": 58,
    "DNCC": 52,
    "Khulna": 44,
    "Rajshahi": 16,
    "Mymensingh": 12,
    "Rangpur": 7,
    "Sylhet": 1,
}


class EpidemiologicalBackfillGenerator:
    """Generates a climate-linked 180-day dengue surveillance time series across 10 DGHS zones."""

    def __init__(
        self,
        weather_parquet_path: Path | str | None = None,
        target_admissions: dict[str, int] | None = None,
        target_deaths: dict[str, int] | None = None,
    ) -> None:
        """Initialize the backfill generator.

        Args:
            weather_parquet_path: Path to weather_districts_daily.parquet.
            target_admissions: Optional custom zone admission targets for 2026-10-14.
            target_deaths: Optional custom zone death targets for 2026-10-14.
        """
        self.weather_path = (
            Path(weather_parquet_path)
            if weather_parquet_path is not None
            else DEFAULT_SILVER_WEATHER_PARQUET
        )
        self.target_admissions = (
            target_admissions if target_admissions is not None else ZONE_TARGET_ADMISSIONS
        )
        self.target_deaths = target_deaths if target_deaths is not None else ZONE_TARGET_DEATHS

    @staticmethod
    def generate_date_range(start_str: str, end_str: str) -> list[str]:
        """Generate contiguous ISO dates between start_str and end_str inclusive."""
        d_start = date.fromisoformat(start_str)
        d_end = date.fromisoformat(end_str)
        days = (d_end - d_start).days + 1
        return [(d_start + timedelta(days=i)).isoformat() for i in range(days)]

    def _compute_zone_climate_weights(
        self,
        zone_weather: pd.DataFrame,
        dates: list[str],
    ) -> np.ndarray:
        """Compute climate-linked daily transmission intensity weights for a single zone.

        Uses 14-to-18 day lagged rainfall and humidity to reflect Aedes mosquito breeding
        and viral extrinsic incubation periods (EIP).
        """
        # Aggregate across districts belonging to the zone by date
        daily_climate = (
            zone_weather.groupby("date")
            .agg(
                mean_precip=("precipitation_sum", "mean"),
                mean_humidity=("relative_humidity_2m_mean", "mean"),
                mean_temp=("temperature_2m_mean", "mean"),
            )
            .reindex(dates)
            .bfill()
            .ffill()
        )

        precip_series = daily_climate["mean_precip"].to_numpy()
        humidity_series = daily_climate["mean_humidity"].to_numpy()
        num_days = len(dates)

        weights = np.zeros(num_days, dtype=float)

        for t in range(num_days):
            # 14-to-18 day lag window [t-18, t-14]
            lag_start = max(0, t - 18)
            lag_end = max(0, t - 14)

            if lag_end > lag_start:
                lag_rain = float(np.mean(precip_series[lag_start:lag_end]))
                lag_hum = float(np.mean(humidity_series[lag_start:lag_end]))
            else:
                lag_rain = float(precip_series[0])
                lag_hum = float(humidity_series[0])

            # Non-linear ecological response:
            # - Mosquito abundance scales with cumulative puddles (rainfall saturation ~25mm)
            # - Relative humidity > 70% dramatically increases adult mosquito longevity
            rain_factor = 1.0 + min(lag_rain / 12.0, 3.5)
            hum_factor = 1.0 + max(0.0, (lag_hum - 65.0) / 20.0)

            # Seasonal baseline curve peaking in August/September (day 120-145)
            seasonal_bell = math.exp(-0.5 * ((t - 130) / 38.0) ** 2)

            # Combined weight
            intensity = (0.05 + 0.95 * seasonal_bell) * (rain_factor**0.8) * (hum_factor**1.2)
            weights[t] = max(intensity, 1e-4)

        return weights

    def generate_180_day_series(
        self,
        weather_df_or_path: pd.DataFrame | Path | str | None = None,
        start_date: str = START_DATE,
        end_date: str = END_DATE,
        random_seed: int = 42,
        output_parquet: Path | str | None = DEFAULT_SILVER_ZONES_PARQUET,
    ) -> pd.DataFrame:
        """Generate and validate 180-day dengue surveillance time series across all 10 zones.

        Args:
            weather_df_or_path: In-memory weather DataFrame or path to weather Parquet file.
            start_date: Series start date (YYYY-MM-DD).
            end_date: Series end date (YYYY-MM-DD).
            random_seed: Fixed random seed for 100% deterministic reproducibility.
            output_parquet: Parquet file destination path.

        Returns:
            Validated DataFrame adhering to DGHSDivisionSilverSchema (1,800 rows).
        """
        # Load weather DataFrame
        if weather_df_or_path is not None:
            if isinstance(weather_df_or_path, (str, Path)):
                weather_df = pd.read_parquet(weather_df_or_path)
            else:
                weather_df = weather_df_or_path
        else:
            weather_df = pd.read_parquet(self.weather_path)

        dates = self.generate_date_range(start_date, end_date)
        num_days = len(dates)

        all_zone_records: list[dict[str, Any]] = []

        for zone_idx, zone_name in enumerate(CANONICAL_ZONES):
            target_adm = self.target_admissions.get(zone_name, 1000)
            target_dth = self.target_deaths.get(zone_name, 10)

            zone_weather = weather_df[weather_df["dghs_reporting_zone"] == zone_name]
            if zone_weather.empty:
                # Fallback to entire weather dataset if zone slice is missing
                zone_weather = weather_df

            # 1. Climate weights for admissions
            weights_adm = self._compute_zone_climate_weights(zone_weather, dates)
            probs_adm = weights_adm / np.sum(weights_adm)

            # Zone-specific RNG seed derived deterministically from master seed
            zone_rng = np.random.default_rng(random_seed * 1000 + zone_idx)

            # Deterministic multinomial sampling guaranteeing exact sum equality
            daily_adm_array = zone_rng.multinomial(target_adm, probs_adm)
            total_adm_array = np.cumsum(daily_adm_array)

            # 2. Deaths modeling with clinical mortality delay (4-day lag)
            weights_dth = np.roll(daily_adm_array.astype(float), 4)
            weights_dth[:4] = daily_adm_array[:4] * 0.5 + 1e-4
            probs_dth = weights_dth / np.sum(weights_dth)
            daily_dth_array = zone_rng.multinomial(target_dth, probs_dth)
            total_dth_array = np.cumsum(daily_dth_array)

            # 3. Discharges modeling
            # Typically discharged after 4-6 days; ~95-97% of admitted minus active/deaths
            total_discharged_array = np.zeros(num_days, dtype=int)
            for t in range(num_days):
                # Patients admitted up to 5 days ago have mostly been discharged
                eligible_adm = total_adm_array[max(0, t - 5)]
                disch_target = int(max(0, eligible_adm - total_dth_array[t]))
                # Enforce that total_discharged <= total_admitted - total_deaths
                max_allowed = int(max(0, total_adm_array[t] - total_dth_array[t]))
                total_discharged_array[t] = min(disch_target, max_allowed)

            # Build daily rows for this zone
            for t in range(num_days):
                all_zone_records.append(
                    {
                        "report_date": dates[t],
                        "zone_name": zone_name,
                        "daily_admitted": int(daily_adm_array[t]),
                        "daily_deaths": int(daily_dth_array[t]),
                        "total_admitted": int(total_adm_array[t]),
                        "total_deaths": int(total_dth_array[t]),
                        "total_discharged": int(total_discharged_array[t]),
                    }
                )

        df = pd.DataFrame(all_zone_records)

        # Sort chronologically, then by canonical zone order
        zone_order_map = {z: i for i, z in enumerate(CANONICAL_ZONES)}
        df["zone_sort"] = df["zone_name"].map(zone_order_map)
        df = df.sort_values(by=["report_date", "zone_sort"]).drop(columns=["zone_sort"])
        df = df.reset_index(drop=True)

        # Pandera Silver Validation
        validated_df = DGHSDivisionSilverSchema.validate(df, lazy=True)

        if output_parquet is not None:
            out_p = Path(output_parquet)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            validated_df.to_parquet(out_p, index=False)
            logger.info("Exported 180-day silver zone series (%d rows) to: %s", len(df), out_p)

        return validated_df
