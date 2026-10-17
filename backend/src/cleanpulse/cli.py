"""Unified Medallion Pipeline CLI Orchestrator for DGHS-CleanPulse.

Provides command-line subcommands to execute and verify individual Medallion layers:
  - scrape-bronze: Ingests raw DGHS HTML and Open-Meteo 64-district climate data.
  - run-silver: Runs Pandera sanitization firewall and 180-day time-series backfill.
  - build-gold: Materializes DuckDB spatiotemporal lag views and correlation matrices.
  - export-snapshot: Updates frontend/public/data/fallback_snapshot.json.
  - run-all: Executes the complete Bronze -> Silver -> Gold -> Snapshot pipeline end-to-end.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cleanpulse.bronze.dghs_scraper import DGHSBronzeScraper
from cleanpulse.bronze.weather_client import OpenMeteoWeatherClient
from cleanpulse.gold.lag_engine import DuckDBLagEngine
from cleanpulse.silver.firewall import SilverSanitizerFirewall
from cleanpulse.silver.timeseries_backfill import EpidemiologicalBackfillGenerator

logger = logging.getLogger("cleanpulse.cli")

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"
FRONTEND_SNAPSHOT_PATH = REPO_ROOT / "frontend" / "public" / "data" / "fallback_snapshot.json"


@dataclass
class StageResult:
    """Represents the execution outcome of an individual pipeline stage."""

    stage_name: str
    status: str
    metrics: str
    duration_sec: float
    output_path: str


def run_scrape_bronze(offline: bool = False) -> list[StageResult]:
    """Execute Bronze layer ingestion for DGHS dashboard and weather archive."""
    results: list[StageResult] = []

    # 1. DGHS Scraping
    t0 = time.perf_counter()
    scraper = DGHSBronzeScraper(offline_mode=offline)
    data, snapshot_path = scraper.run_pipeline(force_offline=offline, output_dir=BRONZE_DIR)
    dur_dghs = time.perf_counter() - t0

    zones_count = len(data.get("zones", []))
    age_count = len(data.get("age_groups", []))
    results.append(
        StageResult(
            stage_name="1. Bronze DGHS Surveillance",
            status="SUCCESS",
            metrics=f"{zones_count} Zones, {age_count} Age Buckets",
            duration_sec=dur_dghs,
            output_path=str(snapshot_path.relative_to(REPO_ROOT)),
        )
    )

    # 2. Weather Batch Scraping
    t0 = time.perf_counter()
    weather_target = SILVER_DIR / "weather_districts_daily.parquet"
    if offline and weather_target.exists():
        import pandas as pd
        weather_df = pd.read_parquet(weather_target)
    else:
        weather_client = OpenMeteoWeatherClient()
        weather_df = weather_client.fetch_climate_data(
            force_offline=offline,
            output_parquet=weather_target,
        )
    dur_weather = time.perf_counter() - t0
    results.append(
        StageResult(
            stage_name="2. Bronze Open-Meteo Weather",
            status="SUCCESS",
            metrics=f"{len(weather_df):,} District-Days (64 Dist)",
            duration_sec=dur_weather,
            output_path=str(weather_target.relative_to(REPO_ROOT)),
        )
    )

    return results


def run_silver_pipeline() -> list[StageResult]:
    """Execute Silver Pandera validation firewall and 180-day backfill generator."""
    results: list[StageResult] = []

    # 1. Locate latest bronze snapshot
    bronze_files = sorted(BRONZE_DIR.glob("dghs_raw_*.json"))
    if not bronze_files:
        raise FileNotFoundError(f"No Bronze JSON snapshots found in {BRONZE_DIR}")
    latest_bronze = bronze_files[-1]

    # 2. Silver Firewall
    t0 = time.perf_counter()
    firewall = SilverSanitizerFirewall(output_dir=SILVER_DIR)
    silver_result = firewall.process_bronze_snapshot(bronze_data_or_path=latest_bronze)
    dur_firewall = time.perf_counter() - t0

    num_cohorts = len(silver_result.age_groups_df)
    num_anomalies = len(silver_result.anomalies_df)
    results.append(
        StageResult(
            stage_name="3. Silver Pandera Firewall",
            status="SUCCESS",
            metrics=f"{num_cohorts} Cohorts, {num_anomalies} Intercepted Bugs",
            duration_sec=dur_firewall,
            output_path=str(SILVER_DIR.relative_to(REPO_ROOT)),
        )
    )

    # 3. 180-day Time-series Backfill
    t0 = time.perf_counter()
    backfill_gen = EpidemiologicalBackfillGenerator(
        weather_parquet_path=SILVER_DIR / "weather_districts_daily.parquet"
    )
    backfill_df = backfill_gen.generate_180_day_series(
        output_parquet=SILVER_DIR / "dengue_zones_daily.parquet"
    )
    dur_backfill = time.perf_counter() - t0
    results.append(
        StageResult(
            stage_name="4. Silver 180d Backfill",
            status="SUCCESS",
            metrics=f"{len(backfill_df):,} Zone-Days (10 Zones)",
            duration_sec=dur_backfill,
            output_path=str((SILVER_DIR / "dengue_zones_daily.parquet").relative_to(REPO_ROOT)),
        )
    )

    return results


def run_gold_pipeline() -> list[StageResult]:
    """Execute Gold DuckDB spatiotemporal lag engine."""
    results: list[StageResult] = []

    t0 = time.perf_counter()
    engine = DuckDBLagEngine(
        silver_dir=SILVER_DIR,
        gold_dir=GOLD_DIR,
    )
    daily_df, lags_df = engine.build_gold_tables(save_parquet=True)
    optimal_lag = engine.get_optimal_lag(zone_name="National")
    dur_gold = time.perf_counter() - t0

    results.append(
        StageResult(
            stage_name="5. Gold DuckDB Lag Engine",
            status="SUCCESS",
            metrics=f"{len(lags_df)} Correlations (Peak Day {optimal_lag})",
            duration_sec=dur_gold,
            output_path=str(GOLD_DIR.relative_to(REPO_ROOT)),
        )
    )

    return results


def run_export_snapshot() -> list[StageResult]:
    """Export API state into frontend fallback static JSON snapshot."""
    results: list[StageResult] = []

    t0 = time.perf_counter()
    # Lazy import to ensure database connection initializes after gold tables exist
    from cleanpulse.api.main import (
        get_audit_anomalies,
        get_db,
        get_pipeline_health,
        get_surveillance_lags,
        get_surveillance_summary,
    )
    from cleanpulse.gold.lag_engine import GOLD_ZONES_LIST

    # Refresh in-memory database tables
    get_db()

    summary = get_surveillance_summary()
    audit = get_audit_anomalies(severity="ALL", anomaly_type="ALL")
    health = get_pipeline_health()

    lags_by_zone: dict[str, Any] = {}
    for zone in GOLD_ZONES_LIST:
        lags_by_zone[zone] = get_surveillance_lags(zone=zone, lag_days=14)

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

    FRONTEND_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FRONTEND_SNAPSHOT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    dur_snap = time.perf_counter() - t0
    size_kb = FRONTEND_SNAPSHOT_PATH.stat().st_size / 1024.0

    results.append(
        StageResult(
            stage_name="6. Frontend Static Cache",
            status="SUCCESS",
            metrics=f"{size_kb:.1f} KB JSON Snapshot",
            duration_sec=dur_snap,
            output_path=str(FRONTEND_SNAPSHOT_PATH.relative_to(REPO_ROOT)),
        )
    )

    return results


def print_summary_table(results: list[StageResult], total_elapsed: float) -> None:
    """Print a formatted ASCII execution summary table to stdout."""
    line = "=" * 94
    subline = "-" * 94

    print(f"\n{line}")
    print("DGHS-CleanPulse Medallion Pipeline Execution Summary")
    print(line)
    print(
        f"{'Stage':<30} {'Status':<10} {'Records / Metrics':<32} {'Duration':<10} {'Output Path'}"
    )
    print(subline)

    for r in results:
        dur = f"{r.duration_sec:>6.2f}s"
        print(f"{r.stage_name:<28} {r.status:<9} {r.metrics:<32} {dur:<9} {r.output_path}")

    print(subline)
    summary_status = f"ALL {len(results)} STAGES PASSED"
    print(f"Total Pipeline Elapsed Time: {total_elapsed:.2f}s | Status: {summary_status}")
    print(f"{line}\n")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="cleanpulse",
        description="DGHS-CleanPulse Medallion Pipeline CLI Orchestrator",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Pipeline subcommands")

    # 1. scrape-bronze
    p_bronze = subparsers.add_parser("scrape-bronze", help="Ingest raw DGHS HTML & weather data")
    p_bronze.add_argument(
        "--offline",
        action="store_true",
        help="Use deterministic offline fixtures instead of live HTTP",
    )

    # 2. run-silver
    subparsers.add_parser("run-silver", help="Run Pandera firewall & 180-day backfill")

    # 3. build-gold
    subparsers.add_parser("build-gold", help="Materialize DuckDB spatiotemporal lag tables")

    # 4. export-snapshot
    subparsers.add_parser(
        "export-snapshot", help="Generate frontend/public/data/fallback_snapshot.json"
    )

    # 5. run-all
    p_all = subparsers.add_parser("run-all", help="Execute complete Medallion pipeline end-to-end")
    p_all.add_argument(
        "--offline",
        action="store_true",
        help="Use deterministic offline fixtures instead of live HTTP",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.subcommand:
        parser.print_help()
        return 0

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    t_start = time.perf_counter()
    all_results: list[StageResult] = []

    try:
        if args.subcommand == "scrape-bronze":
            all_results = run_scrape_bronze(offline=args.offline)
        elif args.subcommand == "run-silver":
            all_results = run_silver_pipeline()
        elif args.subcommand == "build-gold":
            all_results = run_gold_pipeline()
        elif args.subcommand == "export-snapshot":
            all_results = run_export_snapshot()
        elif args.subcommand == "run-all":
            all_results.extend(run_scrape_bronze(offline=args.offline))
            all_results.extend(run_silver_pipeline())
            all_results.extend(run_gold_pipeline())
            all_results.extend(run_export_snapshot())
        else:
            parser.print_help()
            return 1

        total_elapsed = time.perf_counter() - t_start
        print_summary_table(all_results, total_elapsed)
        return 0

    except Exception as exc:
        logger.exception("Pipeline execution failed: %s", exc)
        print(f"\n❌ Error during execution: {exc}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
