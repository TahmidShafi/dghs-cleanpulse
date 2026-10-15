# DGHS-CleanPulse Workspace Rules

Refer to `AGENTS.md` at the repository root for full details.

Key architectural and coding mandates:
1. **Medallion Architecture**: `data/bronze/` (raw), `data/silver/` (Pandera Parquet + `audit_anomalies`), `data/gold/` (DuckDB views).
2. **Python Standards**: Python 3.12+, managed with `uv`, strict type hints, formatted with `ruff`, validated using `pandera>=0.34.1` with `import pandera.pandas as pa`.
3. **No Silent Data Dropping**: Never use `df.dropna()`. All anomalous rows logged to `audit_anomalies` with structured severity codes.
4. **Testing & Commits**: Test coverage for all modules in `src/`. Small, atomic Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`).
