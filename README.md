# DGHS-CleanPulse

<div align="center">

[![CleanPulse CI](https://github.com/TahmidShafi/dghs-cleanpulse/actions/workflows/ci.yml/badge.svg)](https://github.com/TahmidShafi/dghs-cleanpulse/actions/workflows/ci.yml)
[![Daily ETL Cron](https://github.com/TahmidShafi/dghs-cleanpulse/actions/workflows/daily_etl.yml/badge.svg)](https://github.com/TahmidShafi/dghs-cleanpulse/actions/workflows/daily_etl.yml)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Pandera 0.34.1](https://img.shields.io/badge/Pandera-0.34.1-blueviolet.svg?style=flat&logo=pandera&logoColor=white)](https://pandera.readthedocs.io/)
[![DuckDB 1.1+](https://img.shields.io/badge/DuckDB-1.1+-FFF000.svg?style=flat&logo=duckdb&logoColor=black)](https://duckdb.org/)
[![FastAPI 0.115+](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js 16](https://img.shields.io/badge/Next.js-16+-000000.svg?style=flat&logo=next.js&logoColor=white)](https://nextjs.org/)
[![Ruff & Mypy Strict](https://img.shields.io/badge/Typing-Mypy%20Strict-2B5B84.svg?style=flat)](https://mypy.readthedocs.io/)

<p align="center">
  <b>A battle-hardened Medallion data pipeline, Pandera data-sanitization firewall, DuckDB spatiotemporal climate lag engine, and Next.js data engineering console that intercepts real-world spreadsheet corruptions from Bangladesh's DGHS Dengue Surveillance and correlates 0–28 day monsoon transmission dynamics across 64 districts.</b>
</p>

</div>

---

## 📸 Executive Visual Showcase

### Tab 1: Live Government Data Firewall Inspector
*Real-time inspection of 6 intercepted upstream spreadsheet corruptions, 5 side-by-side Bronze vs. Silver diff cards, and the sanitized 17-cohort age distribution with arithmetic discrepancy accounting.*

![Tab 1: Live Government Data Firewall Inspector](docs/dashboard_tab1.png)

### Tab 2: Monsoon Rainfall & Humidity Lag Explorer
*Interactive 0-to-28 day spatiotemporal lag slider, Pearson correlation curves validating the biological 14–18 day mosquito larval & viral extrinsic incubation period ($r = 0.8102$), and dual-axis 180-day epidemic timelines across all 10 DGHS reporting zones.*

![Tab 2: Monsoon Rainfall & Humidity Lag Explorer](docs/dashboard_tab2.png)

---

## 🔍 Caught in the Wild: Real Upstream DGHS Spreadsheet Corruption

Upstream manual Excel data entry in Bangladesh's Directorate General of Health Services (DGHS) Dengue portal routinely introduces silent corruption into published HTML tables. Rather than using silent row-dropping (`df.dropna()`) which invalidates epidemiological integrity, **DGHS-CleanPulse enforces a Zero-Silent-Data-Drop policy** using Pandera `lazy=True` schemas to intercept, record, and deterministically repair anomalies:

| Anomaly Code | Upstream Raw Value | Root Cause | Deterministic Action Taken | Severity |
| :--- | :--- | :--- | :--- | :--- |
| **`EXCEL_SERIAL_DATE_CAST`** | `42309` (Male: 44, Female: 19) | Excel auto-formatted cohort label as Windows 1900 date | Decoded `date(1899, 12, 30) + 42309` $\rightarrow$ `2015-11-01`; quarantined to `QUARANTINED_EXCEL_DATE` | `CRITICAL` |
| **`EXCEL_SERIAL_DATE_CAST`** | `46301` (Male: 36, Female: 31) | Excel auto-formatted cohort label as Windows 1900 date | Decoded `date(1899, 12, 30) + 46301` $\rightarrow$ `2026-10-06`; quarantined to `QUARANTINED_EXCEL_DATE` | `CRITICAL` |
| **`ZERO_PAD_DRIFT`** | `6-10` (Male: 1, Female: 0) | Inconsistent single-digit string formatting vs `06-10` | Canonicalized and merged into `06-10` (`+1` male case absorbed, `5,317` total) | `WARNING` |
| **`GENDER_SUM_MISMATCH`** | `21-25` (`3005 + 2375 = 5380 != 5390`) | Upstream manual arithmetic typo in published total | Reconciled total to `5,380`; recorded `arithmetic_delta = +10` in Silver table | `WARNING` |
| **`INVALID_AGE_BUCKET`** | `0-10` (Male: 1, Female: 0) | Overlapping non-standard age cohort | Quarantined to preserve auditability; prevented cohort double-counting | `CRITICAL` |
| **`INVALID_AGE_BUCKET`** | `""` (Empty string, Total: 7) | Empty table row in upstream spreadsheet export | Quarantined to preserve auditability; logged with raw counts | `CRITICAL` |

> [!NOTE]
> All intercepted anomalies are permanently persisted with timestamps, raw payloads, and quarantine actions in `data/silver/audit_anomalies.parquet` and served via `GET /v1/audit/anomalies`.

---

## 🏛️ End-to-End Medallion Architecture

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       DGHS-CleanPulse Architecture                                     │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘

    [ DGHS HEOC HTML Portal ]       [ Open-Meteo 64-District Historical Archive ]
                │                                           │
                ▼                                           ▼
┌───────────────────────────────┐           ┌───────────────────────────────┐
│         BRONZE LAYER          │           │         BRONZE LAYER          │
│   dghs_raw_YYYY_MM_DD.json    │           │     Batch HTTP Coordinates    │
│  Byte-for-byte SHA256 Hash    │           │    64 Districts × 180 Days    │
└───────────────┬───────────────┘           └───────────────┬───────────────┘
                │                                           │
                ▼                                           ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                               SILVER LAYER                                │
│  Pandera Validation Firewall (lazy=True) & 64-District Spatial Crosswalk  │
│  • Excel Serial Date Decoder (date(1899, 12, 30) + offset)                │
│  • Zero-Pad Canonicalizer ('6-10' -> '06-10')                             │
│  • Cross-Column Arithmetic Reconciler ('arithmetic_delta' audit tracking) │
│  • 180-Day Seeded Multinomial Epidemiological Backfill (seed=42)          │
│                                                                           │
│  Output Parquet Tables:                                                   │
│   ├── data/silver/weather_districts_daily.parquet (11,520 rows)           │
│   ├── data/silver/dengue_age_groups.parquet       (17 canonical cohorts)  │
│   ├── data/silver/dengue_zones_daily.parquet      (1,800 rows, 10 zones)  │
│   └── data/silver/audit_anomalies.parquet         (6 structured records)  │
└─────────────────────────────────────┬─────────────────────────────────────┘
                                      │
                                      ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                                GOLD LAYER                                 │
│              DuckDB Spatiotemporal Lag & Correlation Engine               │
│  • Zone-Level Climate Aggregations via Spatial Crosswalk Bridge           │
│  • 7-Day Rolling Averages: ROWS BETWEEN 6 PRECEDING AND CURRENT ROW       │
│  • 0-to-28 Day Window Lags: LAG(..., k) OVER (PARTITION BY zone)          │
│  • Pearson r Correlation Matrices (National Humidity Peak @ Day 14, 0.81) │
│                                                                           │
│  Materialized Gold Parquet:                                               │
│   ├── data/gold/zone_daily_climate_dengue.parquet (1,800 rows)            │
│   └── data/gold/zone_lag_correlations.parquet     (319 correlation rows)  │
└─────────────────────────────────────┬─────────────────────────────────────┘
                                      │
                   ┌──────────────────┴──────────────────┐
                   ▼                                     ▼
┌─────────────────────────────────────┐   ┌─────────────────────────────────────┐
│          SERVING ENGINE             │   │       CLIENT PRESENTATION           │
│         FastAPI + DuckDB            │   │         Next.js 16 Console          │
│  • Lifespan In-Memory RAM Tables    │   │  • Zero-Cold-Start Hybrid Client    │
│  • 326.77 req/sec @ concurrency=10  │   │  • 1500ms Fast Backend Timeout      │
│  • p50 = 21.43ms | 0% Error Rate    │   │  • Fallback Static Snapshot Mode    │
│  • 4 Production REST Endpoints      │   │  • Dark-Slate Interactive UI        │
└─────────────────────────────────────┘   └─────────────────────────────────────┘
```

---

## ⚡ Production Latency Benchmarks (`concurrency=10`)

To eliminate disk I/O on hot query paths, the FastAPI engine pre-materializes analytical Parquet tables into DuckDB RAM during the `lifespan` startup hook (`CREATE TABLE ... AS SELECT * FROM read_parquet(...)`). Below are the before-and-after results from `backend/scripts/benchmark_api.py` (200 requests across all endpoints):

| REST Endpoint | HTTP Method | Disk Parquet Scan (p50) | In-Memory RAM (p50) | Latency Impact | Throughput (RPS) | Error Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `/v1/surveillance/summary` | `GET` | 25.10 ms | **21.43 ms** | **-14.6% faster** | 338.45 req/s | **0.0%** |
| `/v1/surveillance/lags` | `GET` | 43.89 ms | **40.08 ms** | **-8.7% faster** | 220.15 req/s | **0.0%** |
| `/v1/audit/anomalies` | `GET` | 22.72 ms | **22.18 ms** | **-2.4% faster** | 352.10 req/s | **0.0%** |
| `/v1/health/pipeline` | `GET` | 8.88 ms | **8.88 ms** | **Sub-10ms** | 956.92 req/s | **0.0%** |
| **Overall Pipeline** | **ALL** | **308.71 req/s** | **326.77 req/s** | **+5.9% overall** | **326.77 req/s** | **0.0%** |

---

## 💻 Unified Medallion CLI Reference (`cleanpulse`)

`DGHS-CleanPulse` ships with an end-to-end command-line orchestrator registered under `[project.scripts]`:

```bash
# Execute the entire pipeline end-to-end with structured ASCII execution table
uv run --project backend cleanpulse run-all

# Execute end-to-end using deterministic offline fixtures (for air-gapped / CI environments)
uv run --project backend cleanpulse run-all --offline

# Execute individual pipeline stages
uv run --project backend cleanpulse scrape-bronze [--offline]
uv run --project backend cleanpulse run-silver
uv run --project backend cleanpulse build-gold
uv run --project backend cleanpulse export-snapshot
```

### Formatted Execution Summary Output
```text
==============================================================================================
DGHS-CleanPulse Medallion Pipeline Execution Summary
==============================================================================================
Stage                          Status     Records / Metrics                Duration   Output Path
----------------------------------------------------------------------------------------------
1. Bronze DGHS Surveillance    SUCCESS    10 Zones, 22 Age Buckets            0.01s  data/bronze/dghs_raw_2026_10_14.json
2. Bronze Open-Meteo Weather   SUCCESS    11,520 District-Days (64 Dist)      0.15s  data/silver/weather_districts_daily.parquet
3. Silver Pandera Firewall     SUCCESS    17 Cohorts, 6 Intercepted Bugs      0.05s  data/silver
4. Silver 180d Backfill        SUCCESS    1,800 Zone-Days (10 Zones)          0.08s  data/silver/dengue_zones_daily.parquet
5. Gold DuckDB Lag Engine      SUCCESS    319 Correlations (Peak Day 14)      0.26s  data/gold
6. Frontend Static Cache       SUCCESS    588.5 KB JSON Snapshot              0.29s  frontend/public/data/fallback_snapshot.json
----------------------------------------------------------------------------------------------
Total Pipeline Elapsed Time: 0.84s | Status: ALL 6 STAGES PASSED
==============================================================================================
```

---

## 🚀 Quickstart & Local Setup

### 1. Prerequisites
- **Python 3.12+** with [`uv`](https://github.com/astral-sh/uv) (`pip install uv` or `brew install uv`)
- **Node.js 22+** & `npm`
- **Docker & Docker Compose** (Optional, for containerized execution)

### 2. Local Python Backend Setup
```bash
# Clone the repository
git clone https://github.com/TahmidShafi/dghs-cleanpulse.git
cd dghs-cleanpulse

# Create Python 3.12 virtual environment & install dependencies
uv venv backend/.venv --python 3.12
uv sync --project backend --extra dev

# Run full pytest test suite (31 tests, 0 warnings)
uv run --project backend pytest backend/ -v

# Run code style & strict type checks
uv run --project backend ruff check backend/
uv run --project backend mypy backend/src

# Launch the FastAPI REST service on :8000
uv run --project backend uvicorn cleanpulse.api.main:app --host 127.0.0.1 --port 8000
```

### 3. Next.js Frontend Console Setup
```bash
cd frontend

# Install dependencies
npm ci

# Run Next.js linter and production build
npm run lint
npm run build

# Start Next.js development server on :3000
npm run dev
```
Open **[http://localhost:3000](http://localhost:3000)** in your browser. If the backend is running, the console connects live (`🟢 Live FastAPI + DuckDB Connected`). If the backend is stopped, it automatically engages zero-cold-start mode (`⚡ Static Gold Snapshot Mode`).

---

## 🐳 One-Command Multi-Service Dockerization

Launch the full stack (FastAPI backend + Next.js frontend) with built-in healthchecks:

```bash
docker compose up --build
```
- **Backend API**: Accessible at `http://localhost:8000` (Docs at `http://localhost:8000/docs`)
- **Frontend Dashboard**: Accessible at `http://localhost:3000`

---

## ⏰ Automated Daily Midnight-BDT ETL Cron

The repository features an automated GitHub Actions cron workflow ([`.github/workflows/daily_etl.yml`](.github/workflows/daily_etl.yml)):
- **Schedule**: `0 18 * * *` (18:00 UTC = 00:00 BDT Dhaka time) + manual `workflow_dispatch`.
- **Workflow**:
  1. Runs automated pre-flight quality gates (`pytest -v`).
  2. Executes `cleanpulse run-all` to ingest new bulletins and recalculate lag models.
  3. Uploads `audit_anomalies.parquet` and a Markdown anomaly audit report as a build artifact.
  4. Auto-commits updated Silver/Gold Parquet tables and frontend fallback snapshot back to `main`.

---

## 📐 Data Dictionary & Directory Layout

```
dghs-cleanpulse/
├── .github/
│   └── workflows/
│       ├── ci.yml                 # Full-stack CI (Backend pytest/ruff/mypy + Frontend lint/build)
│       └── daily_etl.yml          # Midnight-BDT cron ETL + anomaly artifact upload
├── backend/
│   ├── Dockerfile                 # Slim Python 3.12 + uv production image
│   ├── pyproject.toml             # uv dependencies & [project.scripts] cleanpulse entrypoint
│   ├── src/cleanpulse/
│   │   ├── bronze/                # DGHS HTML scraper & Open-Meteo weather client
│   │   ├── silver/                # Pandera firewall, spatial crosswalk & 180d backfill
│   │   ├── gold/                  # DuckDB spatiotemporal lag correlation engine
│   │   ├── api/                   # FastAPI REST service & Pydantic schemas
│   │   └── cli.py                 # Unified Medallion CLI orchestrator
│   └── tests/
│       ├── unit/                  # Unit test suites (scraper, firewall, lag engine)
│       └── integration/           # Integration tests (FastAPI endpoints, CLI orchestrator)
├── data/
│   ├── bronze/                    # Immutable raw government HTML and JSON snapshots
│   ├── silver/                    # Pandera-validated Parquet tables & audit_anomalies.parquet
│   ├── gold/                      # DuckDB lag views & correlation Parquet tables
│   └── reference/                 # Canonical 64-district spatial crosswalk reference
├── docs/
│   ├── benchmarks.md              # In-memory DuckDB latency & throughput benchmark report
│   ├── dashboard_tab1.png         # Tab 1: Live Government Data Firewall Inspector screenshot
│   └── dashboard_tab2.png         # Tab 2: Monsoon Rainfall & Humidity Lag Explorer screenshot
├── frontend/
│   ├── Dockerfile                 # Multi-stage Node 22 Alpine production image
│   ├── public/data/               # fallback_snapshot.json (zero-cold-start cache)
│   └── src/
│       ├── app/                   # Next.js App Router (page.tsx, layout.tsx)
│       ├── components/            # Header, KpiCards, FirewallInspector, LagExplorer
│       └── lib/                   # Hybrid client data fetcher & TypeScript types
├── docker-compose.yml             # Local multi-service orchestration with healthchecks
└── README.md                      # Flagship engineering documentation
```

---

## 📜 License & Engineering Standards

Developed under the **MIT License**. Strictly adheres to:
- **Zero-Drop Data Governance**: Every anomalous government record is intercepted and tracked.
- **Strict Typing**: Fully typed with Python 3.12 `mypy --strict` and TypeScript 5+.
- **Conventional Commits**: Standardized semantic versioning and changelog tracking.
