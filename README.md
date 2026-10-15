# DGHS-CleanPulse

> Production-grade Medallion ETL pipeline, Pandera data-sanitization firewall, DuckDB spatiotemporal lag engine, and FastAPI + Next.js analytics platform for Bangladesh's DGHS Dengue surveillance and 64-district climate data.

---

## 🏛️ Architecture Overview

The system implements a strict Medallion architecture:

1. **Bronze Layer (`data/bronze/`)**:
   - Immutable raw snapshots of DGHS MIS daily Dengue situation reports (HTML/PDF) and Bangladesh Meteorological Department (BMD) / ERA5 climate payloads.
   - Organized by partition date `YYYY-MM-DD/` with SHA256 cryptographic verification.

2. **Silver Layer (`data/silver/`)**:
   - Pandera-validated Parquet tables partitioned by year and month.
   - Enforces a zero-data-drop guarantee: malformed rows or parsing quirks are preserved with structured metadata in `audit_anomalies.parquet`.

3. **Gold Layer (`data/gold/`)**:
   - Embedded DuckDB analytical engine computing spatiotemporal lag views (7, 14, 21, 28 days) correlating rainfall, temperature, and relative humidity with dengue case spikes.
   - High-performance materialized views for API serving.

4. **FastAPI & Next.js Platform (`backend/` & `frontend/`)**:
   - High-throughput asynchronous REST API serving district choropleths, time-series projections, and audit logs.
   - Next.js dashboard providing interactive maps and public health decision-support metrics.

---

## 🛠️ Tech Stack

- **Language & Runtime**: Python 3.12+ managed via `uv`
- **Validation**: `pandera>=0.34.1` with `pandera.pandas` schema models
- **Analytics & Storage**: `duckdb`, `pyarrow`, `pandas`
- **Backend API**: `fastapi`, `uvicorn`, `pydantic`
- **Ingestion**: `httpx`, `beautifulsoup4`, `lxml`
- **Quality & Testing**: `pytest`, `pytest-asyncio`, `ruff`, `mypy`

---

## 🚀 Quickstart

### Prerequisites
- Python 3.12+
- `uv` package manager (`pip install uv`)

### Setup & Testing
```bash
# Create Python 3.12 virtual environment
uv venv backend/.venv --python 3.12

# Install backend package and dependencies in editable mode
uv pip install -e "backend[dev]"

# Run tests
pytest backend/tests/unit -v

# Run lint checks
ruff check backend/
```
