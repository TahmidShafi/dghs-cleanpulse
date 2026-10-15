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

## 4. Testing & Atomic Commits
- **Test Parity**: Every module in `backend/src/` must have a corresponding test in `backend/tests/`.
- **Testing Tools**: `pytest` and `pytest-asyncio`. Run tests before committing.
- **Git Commits**: Use small, atomic Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`) to ensure disciplined version control history.
