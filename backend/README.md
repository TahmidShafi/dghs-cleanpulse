# DGHS-CleanPulse Backend

Backend package containing:
- `cleanpulse.bronze`: Raw immutable ingestion
- `cleanpulse.silver`: Pandera schema validation, anomaly quarantine, deterministic repair
- `cleanpulse.gold`: DuckDB spatiotemporal lag views & feature computation
- `cleanpulse.api`: FastAPI analytics and surveillance service
