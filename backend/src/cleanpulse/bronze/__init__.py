"""Bronze layer: Raw immutable government HTML/PDF and climate ingestion."""

from cleanpulse.bronze.dghs_scraper import DGHSBronzeScraper
from cleanpulse.bronze.weather_client import (
    OpenMeteoWeatherClient,
    WeatherDailySilverSchema,
)

__all__ = [
    "DGHSBronzeScraper",
    "OpenMeteoWeatherClient",
    "WeatherDailySilverSchema",
]
