"""Test-only synthetic weather generator (moved out of src/ for Phase 1 honesty)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from cleanpulse.bronze.weather_client import (
    DEFAULT_END_DATE,
    DEFAULT_START_DATE,
    OpenMeteoWeatherClient,
    WeatherDailySilverSchema,
)


def generate_synthetic_weather(
    districts: list[dict[str, Any]],
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate deterministic, synthetic monsoon weather series for unit tests only."""
    rng = np.random.default_rng(seed)
    dates = OpenMeteoWeatherClient.generate_dates(start_date, end_date)
    records: list[dict[str, Any]] = []

    for dist in districts:
        lat = float(dist["latitude"])
        lon = float(dist["longitude"])
        lat_effect = (24.0 - lat) * 0.3
        east_effect = (lon - 90.0) * 0.2

        for day_idx, d_str in enumerate(dates):
            monsoon_intensity = math.exp(-0.5 * ((day_idx - 85) / 35.0) ** 2)
            base_temp = 32.5 - (monsoon_intensity * 3.5) + lat_effect
            temp = round(float(np.clip(base_temp + float(rng.normal(0, 1.2)), 22.0, 42.0)), 1)

            base_humidity = 68.0 + (monsoon_intensity * 22.0)
            humidity = round(
                float(np.clip(base_humidity + float(rng.normal(0, 3.0)), 45.0, 99.0)), 1
            )

            rain_prob = 0.25 + (monsoon_intensity * 0.55)
            if rng.random() < rain_prob:
                rain_amount = float(
                    rng.gamma(shape=2.0, scale=8.0 + (monsoon_intensity * 14.0) + east_effect)
                )
                precip = round(max(rain_amount, 0.1), 1)
            else:
                precip = 0.0

            records.append(
                {
                    "date": d_str,
                    "district_id": dist["district_id"],
                    "district_name": dist["district_name"],
                    "dghs_reporting_zone": dist["dghs_reporting_zone"],
                    "temperature_2m_mean": temp,
                    "precipitation_sum": precip,
                    "relative_humidity_2m_mean": humidity,
                }
            )

    df = pd.DataFrame(records)
    return WeatherDailySilverSchema.validate(df, lazy=True)
