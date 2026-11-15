"""Export real backend state and synthetic Tab-1 demo JSON for the Next.js frontend."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from cleanpulse.api.main import build_snapshot_payload
from cleanpulse.bronze.dghs_scraper import DEFAULT_FIXTURE_PATH, DGHSBronzeScraper
from cleanpulse.bronze.provenance import get_git_provenance
from cleanpulse.silver.firewall import SilverSanitizerFirewall

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_PUBLIC_DATA = REPO_ROOT / "frontend" / "public" / "data"
SNAPSHOT_PATH = FRONTEND_PUBLIC_DATA / "fallback_snapshot.json"
DEMO_PATH = FRONTEND_PUBLIC_DATA / "demo_synthetic_fault_injection.json"


def export_snapshot() -> None:
    """Extract real backend API responses and persist to fallback_snapshot.json."""
    print("Connecting to backend DuckDB engine and extracting real snapshot payloads...")
    payload = build_snapshot_payload()

    FRONTEND_PUBLIC_DATA.mkdir(parents=True, exist_ok=True)
    with SNAPSHOT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    size_kb = SNAPSHOT_PATH.stat().st_size / 1024.0
    print(f"Fallback snapshot exported to: {SNAPSHOT_PATH.resolve()} ({size_kb:.1f} KB)")


def export_synthetic_demo() -> None:
    """Generate Tab 1 synthetic fault-injection demo JSON from test fixture (never in data/)."""
    raw_bytes = DEFAULT_FIXTURE_PATH.read_bytes()
    fixture_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    git_commit, git_dirty = get_git_provenance()

    scraper = DGHSBronzeScraper(offline_mode=True, fixture_path=DEFAULT_FIXTURE_PATH)
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        parsed, _html_path = scraper.run_pipeline(
            force_offline=True,
            output_dir=tmp_path / "bronze",
        )
        firewall = SilverSanitizerFirewall(output_dir=tmp_path / "silver")
        silver_res = firewall.process_bronze_snapshot(bronze_data_or_path=parsed)

        age_groups = silver_res.age_groups_df.to_dict(orient="records")
        anomalies = silver_res.anomalies_df.to_dict(orient="records")
        severity_counts = {
            str(k): int(v)
            for k, v in silver_res.anomalies_df["severity"].value_counts().to_dict().items()
        }
        type_counts = {
            str(k): int(v)
            for k, v in silver_res.anomalies_df["anomaly_type"].value_counts().to_dict().items()
        }

    demo_payload = {
        "synthetic": True,
        "fixture_path": str(DEFAULT_FIXTURE_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "fixture_sha256": fixture_sha256,
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "disclaimer": (
            "SYNTHETIC DEMO: Generated from hand-authored fault-injection test input "
            "(synthetic_dghs_fault_injection.html). Not real DGHS surveillance data."
        ),
        "age_groups": age_groups,
        "audit_anomalies": {
            "total_anomalies": len(anomalies),
            "severity_counts": severity_counts,
            "type_counts": type_counts,
            "anomalies": anomalies,
        },
    }

    FRONTEND_PUBLIC_DATA.mkdir(parents=True, exist_ok=True)
    with DEMO_PATH.open("w", encoding="utf-8") as f:
        json.dump(demo_payload, f, indent=2)
    print(f"Synthetic demo exported to: {DEMO_PATH.resolve()}")


if __name__ == "__main__":
    export_snapshot()
    export_synthetic_demo()
