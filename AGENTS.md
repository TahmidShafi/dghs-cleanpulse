# DGHS-CleanPulse Workspace Rules & Engineering Standards

These rules are mandatory for all AI agents and human contributors working on `DGHS-CleanPulse`.

---

## 1. Architecture: Strict Medallion Separation
The data pipeline is organized into immutable layers:
- `data/bronze/`: Immutable raw government HTML, PDF snapshots, and raw JSON payloads. Never overwrite or mutate raw bronze files; organize by date (`YYYY-MM-DD/`).
- `data/silver/`: Pandera-validated Parquet tables with deterministic corrections and a mandatory companion `audit_anomalies.parquet` table.
- `data/gold/`: DuckDB spatiotemporal lag views, rolling statistics (7/14/21/28 days), and analytical aggregates optimized for the FastAPI engine.
- `data/reference/`: Canonical geospatial master data (e.g. Bangladesh 8 divisions, 64 districts, official English and Bengali spellings, geocoordinates).

---

## 2. Python Standards & Environment
- **Python Version**: Python 3.12+ managed via `uv` and `pyproject.toml`.
- **Typing**: Strict type hints everywhere (`mypy --strict`). Avoid untyped definitions (`Any` must be explicitly justified).
- **Code Style & Linting**: Formatted and linted with `ruff` (`ruff format` and `ruff check`).
- **Data Validation**: Validated using `pandera>=0.34.1` with `import pandera.pandas as pa` (or typed `DataFrameModel`).

---

## 3. Zero Silent Data Dropping
- **Never use `df.dropna()`** or drop rows silently when encountering malformed government records or unexpected schema changes.
- Every anomalous row, column mismatch, out-of-bounds number, or parsing quirk must be logged to `audit_anomalies` with structured metadata:
  - `timestamp`: Ingestion run timestamp.
  - `source_layer`: `bronze` or `silver`.
  - `record_identifier`: District, report date, or line index.
  - `severity`: `CRITICAL`, `WARNING`, or `INFO`.
  - `anomaly_code`: E.g., `DISTRICT_UNRECOGNIZED`, `OUT_OF_BOUNDS_CASES`, `SUM_MISMATCH`.
  - `raw_payload`: Serialized string representation of the problematic raw entry.
  - `action_taken`: `REPAIRED` or `QUARANTINED`.

---

## 4. Testing, Honesty & Atomic Commits
- **Test Parity**: Every module in `backend/src/` must have a corresponding test in `backend/tests/`.
- **No Synthetic Data in `data/`**: Never write synthetic or fixture-derived outputs into `data/`.
- **No Silent Fallbacks**: Pipeline stages and scrapers must fail loudly with explicit errors and non-zero exit codes rather than falling back silently to fixtures or stale caches.
- **Bronze Provenance Sidecars**: Every raw file in `data/bronze/` must be immutable (never overwritten) and paired with a JSON provenance sidecar recording `url`, `http_status`, `sha256`, `fetched_at_utc`, `fetch_source`, `git_commit`, and `git_dirty`.
- **No Hard-Coded Result Numbers**: Never hard-code pipeline output numbers in integration tests, real-data tests, or docs (exact oracle assertions are permitted only in unit tests against controlled synthetic fixtures). Every number in docs/README must be produced by a repo script or command, with the command shown.
- **Pin External API Models/Versions**: Pin model/version parameters for external data APIs where available, and record them in bronze sidecars.
- **Testing Tools**: `pytest` and `pytest-asyncio`. Run tests before committing.
- **Git Commits**: Use small, atomic Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`) to ensure disciplined version control history.
