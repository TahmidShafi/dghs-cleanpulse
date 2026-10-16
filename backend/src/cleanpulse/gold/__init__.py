"""Gold layer: DuckDB spatiotemporal lag engine, rolling statistics, and analytics views."""

from cleanpulse.gold.lag_engine import (
    GOLD_ZONES_LIST,
    DuckDBLagEngine,
    GoldDailySchema,
    GoldLagCorrelationSchema,
)

__all__ = [
    "GOLD_ZONES_LIST",
    "DuckDBLagEngine",
    "GoldDailySchema",
    "GoldLagCorrelationSchema",
]
