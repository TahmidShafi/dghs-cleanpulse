"""Unified Medallion Pipeline CLI Orchestrator for DGHS-CleanPulse.

Provides command-line subcommands to execute and verify individual Medallion layers:
  - scrape-bronze: Ingests raw DGHS HTML and Open-Meteo 64-district climate data.
  - ingest-weather: Fetches live Open-Meteo batches into immutable Bronze storage.
  - build-silver: Builds Silver tables from Bronze (supports --weather-only while DGHS is down).
  - run-silver: Alias for build-silver.
  - export-snapshot: Updates frontend/public/data/fallback_snapshot.json from real data.
  - run-all: Executes the complete live pipeline (fails loudly if DGHS or weather fails).
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from cleanpulse.bronze.dghs_scraper import DGHSBronzeScraper
from cleanpulse.bronze.weather_client import OpenMeteoWeatherClient
from cleanpulse.silver.firewall import SilverSanitizerFirewall

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


def _rel_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _find_latest_weather_bronze_batches(weather_bronze_dir: Path) -> list[Path]:
    """Return raw JSON batch paths from the most recent date directory in Bronze weather."""
    if not weather_bronze_dir.exists():
        raise FileNotFoundError(f"Weather Bronze directory does not exist: {weather_bronze_dir}")
    date_dirs = sorted(p for p in weather_bronze_dir.iterdir() if p.is_dir())
    if not date_dirs:
        raise FileNotFoundError(
            f"No date-partitioned Bronze weather batches in {weather_bronze_dir}"
        )
    latest_dir = date_dirs[-1]
    batch_files = sorted(
        p for p in latest_dir.glob("*.json") if not p.name.endswith(".sidecar.json")
    )
    if not batch_files:
        raise FileNotFoundError(f"No raw weather JSON batches found in {latest_dir}")
    return batch_files


def run_ingest_weather(bronze_weather_dir: Path | None = None) -> list[StageResult]:
    """Fetch live Open-Meteo climate batches into immutable Bronze storage."""
    t0 = time.perf_counter()
    target_dir = bronze_weather_dir or (BRONZE_DIR / "weather")
    weather_client = OpenMeteoWeatherClient()
    batch_paths = weather_client.ingest_bronze_batches(bronze_dir=target_dir)
    dur = time.perf_counter() - t0
    return [
        StageResult(
            stage_name="1. Bronze Open-Meteo Weather",
            status="SUCCESS",
            metrics=f"{len(batch_paths)} Raw JSON Batches",
            duration_sec=dur,
            output_path=_rel_path(batch_paths[-1].parent),
        )
    ]


def run_scrape_bronze(
    offline: bool = False,
    offline_output_dir: Path | None = None,
) -> list[StageResult]:
    """Execute Bronze layer ingestion for DGHS dashboard and Open-Meteo weather."""
    results: list[StageResult] = []

    # 1. DGHS Scraping (fails loudly on live errors; --offline never writes to data/)
    t0 = time.perf_counter()
    scraper = DGHSBronzeScraper(offline_mode=offline)
    target_dghs_dir = (
        offline_output_dir or (Path.cwd() / "offline_bronze" / "dghs")
        if offline
        else (BRONZE_DIR / "dghs")
    )
    data, html_path = scraper.run_pipeline(force_offline=offline, output_dir=target_dghs_dir)
    dur_dghs = time.perf_counter() - t0

    zones_count = len(data.get("zones", []))
    age_count = len(data.get("age_groups", []))
    results.append(
        StageResult(
            stage_name="1. Bronze DGHS Surveillance",
            status="SUCCESS",
            metrics=f"{zones_count} Zones, {age_count} Age Buckets",
            duration_sec=dur_dghs,
            output_path=_rel_path(html_path),
        )
    )

    if not offline:
        results.extend(run_ingest_weather())

    return results


def run_silver_pipeline(
    weather_only: bool = False,
    bronze_dir: Path | None = None,
    silver_dir: Path | None = None,
) -> list[StageResult]:
    """Execute Silver layer validation from immutable Bronze files."""
    results: list[StageResult] = []
    b_dir = bronze_dir or BRONZE_DIR
    s_dir = silver_dir or SILVER_DIR

    # 1. Weather Silver from Bronze
    t0 = time.perf_counter()
    batch_files = _find_latest_weather_bronze_batches(b_dir / "weather")
    weather_target = s_dir / "weather_districts_daily.parquet"
    weather_df = OpenMeteoWeatherClient().build_silver_from_bronze(
        bronze_paths=batch_files,
        output_parquet=weather_target,
    )
    dur_weather = time.perf_counter() - t0
    dist_count = weather_df["district_id"].nunique()
    results.append(
        StageResult(
            stage_name="2. Silver Open-Meteo Weather",
            status="SUCCESS",
            metrics=f"{len(weather_df):,} District-Days ({dist_count} Dist)",
            duration_sec=dur_weather,
            output_path=_rel_path(weather_target),
        )
    )

    if weather_only:
        return results

    # 2. DGHS Silver Firewall from latest Bronze HTML
    dghs_bronze_dir = b_dir / "dghs"
    html_files = sorted(dghs_bronze_dir.rglob("*.html")) if dghs_bronze_dir.exists() else []
    if not html_files:
        raise FileNotFoundError(f"No Bronze DGHS HTML files found in {dghs_bronze_dir}")
    latest_html = html_files[-1]

    t0 = time.perf_counter()
    parsed = DGHSBronzeScraper().parse_bronze_file(latest_html)
    firewall = SilverSanitizerFirewall(output_dir=s_dir)
    silver_result = firewall.process_bronze_snapshot(bronze_data_or_path=parsed)
    dur_firewall = time.perf_counter() - t0

    results.append(
        StageResult(
            stage_name="3. Silver Pandera Firewall",
            status="SUCCESS",
            metrics=(
                f"{len(silver_result.age_groups_df)} Cohorts, "
                f"{len(silver_result.anomalies_df)} Anomalies"
            ),
            duration_sec=dur_firewall,
            output_path=_rel_path(s_dir),
        )
    )

    return results


def run_export_snapshot(snapshot_path: Path | None = None) -> list[StageResult]:
    """Export real API state into frontend fallback static JSON snapshot."""
    t0 = time.perf_counter()
    from cleanpulse.api.main import build_snapshot_payload

    target = snapshot_path or FRONTEND_SNAPSHOT_PATH
    payload = build_snapshot_payload()

    target.parent.mkdir(parents=True, exist_ok=True)
    import json

    with target.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    dur_snap = time.perf_counter() - t0
    size_kb = target.stat().st_size / 1024.0

    return [
        StageResult(
            stage_name="4. Frontend Static Snapshot",
            status="SUCCESS",
            metrics=f"{size_kb:.1f} KB Real JSON Snapshot",
            duration_sec=dur_snap,
            output_path=_rel_path(target),
        )
    ]


def run_export_report(output_path: Path | None = None) -> StageResult:
    """Generate Markdown Anomaly Audit Report from Silver audit anomalies."""
    t0 = time.perf_counter()
    if output_path is None:
        target_path = REPO_ROOT / "anomaly_report.md"
    elif output_path.is_absolute():
        target_path = output_path
    else:
        target_path = REPO_ROOT / output_path

    anomalies_parquet = SILVER_DIR / "audit_anomalies.parquet"
    if not anomalies_parquet.exists():
        raise FileNotFoundError(
            f"Missing {anomalies_parquet}; no real DGHS anomaly audit data ingested yet."
        )

    import duckdb

    con = duckdb.connect()
    query = (
        "SELECT anomaly_id, anomaly_type, severity, row_key, "
        "raw_value, repaired_value, explanation "
        "FROM read_parquet(?) ORDER BY anomaly_id"
    )
    rows = con.execute(query, [str(anomalies_parquet)]).fetchall()

    lines = [
        "# DGHS Daily Surveillance Anomaly Audit Report\n",
        f"**Total Upstream Anomalies Intercepted**: {len(rows)}\n",
        (
            "| Anomaly ID | Anomaly Type | Severity | Target Row | "
            "Raw Upstream Value | Repaired / Quarantined | Explanation |"
        ),
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for r in rows:
        lines.append(f"| {r[0]} | `{r[1]}` | **{r[2]}** | {r[3]} | `{r[4]}` | {r[5]} | {r[6]} |")

    target_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    dur = time.perf_counter() - t0
    return StageResult(
        stage_name="5. Anomaly Audit Report",
        status="SUCCESS",
        metrics=f"{len(rows)} Intercepted Anomalies",
        duration_sec=dur,
        output_path=_rel_path(target_path),
    )


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
        help="Use synthetic DGHS fixture (must not write to data/)",
    )
    p_bronze.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional output directory (required outside data/ for --offline)",
    )

    # 2. ingest-weather
    subparsers.add_parser(
        "ingest-weather",
        help="Fetch live Open-Meteo batches into immutable Bronze storage",
    )

    # 3. build-silver & run-silver
    for cmd_name in ("build-silver", "run-silver"):
        p_silver = subparsers.add_parser(
            cmd_name,
            help="Build Silver tables from archived Bronze files",
        )
        p_silver.add_argument(
            "--weather-only",
            action="store_true",
            help="Build Silver weather table only (skips DGHS firewall while DGHS is down)",
        )

    # 4. export-snapshot
    subparsers.add_parser(
        "export-snapshot",
        help="Generate frontend/public/data/fallback_snapshot.json from real data",
    )

    # 5. export-report
    p_report = subparsers.add_parser("export-report", help="Generate Markdown Anomaly Audit Report")
    p_report.add_argument(
        "--output",
        default="anomaly_report.md",
        help="Path for generated Markdown anomaly report",
    )

    # 6. run-all
    subparsers.add_parser(
        "run-all",
        help="Execute complete live Medallion pipeline (fails loudly if DGHS fails)",
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
            all_results = run_scrape_bronze(
                offline=args.offline,
                offline_output_dir=args.output_dir,
            )
        elif args.subcommand == "ingest-weather":
            all_results = run_ingest_weather()
        elif args.subcommand in ("build-silver", "run-silver"):
            all_results = run_silver_pipeline(weather_only=args.weather_only)
        elif args.subcommand == "export-snapshot":
            all_results = run_export_snapshot()
        elif args.subcommand == "export-report":
            all_results.append(run_export_report(Path(args.output)))
        elif args.subcommand == "run-all":
            all_results.extend(run_scrape_bronze(offline=False))
            all_results.extend(run_silver_pipeline(weather_only=False))
            all_results.extend(run_export_snapshot())
            all_results.append(run_export_report())
        else:
            parser.print_help()
            return 1

        total_elapsed = time.perf_counter() - t_start
        print_summary_table(all_results, total_elapsed)
        return 0

    except Exception as exc:
        logger.exception("Pipeline execution failed: %s", exc)
        print(f"\nError during execution: {exc}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
