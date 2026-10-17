"""Export production backend state to a static fallback JSON snapshot for Next.js.

Generates frontend/public/data/fallback_snapshot.json for zero-cold-start offline viewing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cleanpulse.api.main import (
    GOLD_ZONES_LIST,
    get_audit_anomalies,
    get_db,
    get_pipeline_health,
    get_surveillance_lags,
    get_surveillance_summary,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_PUBLIC_DATA = REPO_ROOT / "frontend" / "public" / "data"
SNAPSHOT_PATH = FRONTEND_PUBLIC_DATA / "fallback_snapshot.json"


def export_snapshot() -> None:
    """Extract backend API responses and persist to fallback JSON snapshot."""
    print("Connecting to backend DuckDB engine and extracting snapshot payloads...")
    get_db()  # Ensures tables are pre-loaded

    summary = get_surveillance_summary()
    audit = get_audit_anomalies(severity="ALL", anomaly_type="ALL")
    health = get_pipeline_health()

    lags_by_zone: dict[str, Any] = {}
    for zone in GOLD_ZONES_LIST:
        lags_data = get_surveillance_lags(zone=zone, lag_days=14)
        lags_by_zone[zone] = lags_data

    payload = {
        "metadata": {
            "source": "DGHS-CleanPulse DuckDB In-Memory Engine",
            "snapshot_version": "1.0.0",
            "extracted_at": health["timestamp"],
        },
        "surveillance_summary": summary,
        "lags_by_zone": lags_by_zone,
        "audit_anomalies": audit,
        "pipeline_health": health,
    }

    FRONTEND_PUBLIC_DATA.mkdir(parents=True, exist_ok=True)
    with SNAPSHOT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    size_kb = SNAPSHOT_PATH.stat().st_size / 1024.0
    print(f"Fallback snapshot exported to: {SNAPSHOT_PATH.resolve()} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    export_snapshot()
