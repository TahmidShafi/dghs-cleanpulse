# DGHS-CleanPulse: Ground-Truth Engineering Status Report (`handoff.md`)

> **Generated at:** 2026-10-16T11:50:00+06:00  
> **Status:** Steps 0, 1, and 2 Fully Implemented, Tested (14/14 Pytest Passing), and Green on CI.

---

## 1. Git Commit History & Branch Status

### `git log --oneline -n 15`
```text
929b01e refactor(silver): replace untyped lambdas with typed check functions in firewall
f36fc5a feat(silver): implement Pandera validation firewall, deterministic repair, and parquet export
c0dccea feat(bronze): implement DGHS scraper with raw anomaly preservation and offline fixture
52dad71 fix(ci): upgrade setup-uv to v5, add uv.lock, and isolate commands with uv run
2dede62 feat: scaffold repository structure, workspace rules, and uv environment
```

### `git status -s`
```text
(working tree clean - all commits synchronized with origin/main)
```

---

## 2. Repository File Tree

```text
.
|-- .antigravity
|   \-- rules.md
|-- .github
|   \-- workflows
|       \-- ci.yml
|-- backend
|   |-- src
|   |   \-- cleanpulse
|   |       |-- api
|   |       |   \-- __init__.py
|   |       |-- bronze
|   |       |   |-- __init__.py
|   |       |   \-- dghs_scraper.py
|   |       |-- gold
|   |       |   \-- __init__.py
|   |       |-- silver
|   |       |   |-- __init__.py
|   |       |   \-- firewall.py
|   |       \-- __init__.py
|   |-- tests
|   |   |-- fixtures
|   |   |   |-- __init__.py
|   |   |   \-- dghs_sample_2026_10_14.html
|   |   |-- integration
|   |   |   \-- __init__.py
|   |   |-- unit
|   |   |   |-- __init__.py
|   |   |   |-- test_dghs_scraper.py
|   |   |   |-- test_silver_firewall.py
|   |   |   \-- test_smoke.py
|   |   \-- __init__.py
|   |-- README.md
|   |-- pyproject.toml
|   \-- uv.lock
|-- data
|   |-- bronze
|   |   |-- .gitkeep
|   |   \-- dghs_raw_2026_10_14.json
|   |-- gold
|   |   \-- .gitkeep
|   |-- reference
|   |   \-- .gitkeep
|   \-- silver
|       |-- .gitkeep
|       |-- audit_anomalies.parquet
|       |-- dengue_age_groups.parquet
|       \-- dengue_zones_daily.parquet
|-- frontend
|   \-- README.md
|-- .gitignore
|-- AGENTS.md
\-- README.md
```

---

## 3. Test Suite & Linter Verification

### Terminal Output: `python -m uv run --project backend pytest -v`
```text
============================= test session starts =============================
platform win32 -- Python 3.12.15, pytest-9.1.1, pluggy-1.7.0 -- D:\dghs-cleanpulse\backend\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\dghs-cleanpulse
plugins: anyio-4.15.1, asyncio-1.4.0, typeguard-4.6.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 14 items

backend/tests/unit/test_dghs_scraper.py::test_fixture_exists_and_readable PASSED [  7%]
backend/tests/unit/test_dghs_scraper.py::test_scraper_extracts_all_10_zones PASSED [ 14%]
backend/tests/unit/test_dghs_scraper.py::test_scraper_preserves_corrupted_age_buckets_verbatim PASSED [ 21%]
backend/tests/unit/test_dghs_scraper.py::test_sha256_hash_reproducibility PASSED [ 28%]
backend/tests/unit/test_dghs_scraper.py::test_save_snapshot_creates_valid_json PASSED [ 35%]
backend/tests/unit/test_dghs_scraper.py::test_offline_fallback_on_network_error PASSED [ 42%]
backend/tests/unit/test_silver_firewall.py::test_stage_2a_raw_audit_scan_collects_all_failures PASSED [ 50%]
backend/tests/unit/test_silver_firewall.py::test_excel_serial_date_decoding_and_quarantine PASSED [ 57%]
backend/tests/unit/test_silver_firewall.py::test_zero_pad_canonicalizer_merges_counts PASSED [ 64%]
backend/tests/unit/test_silver_firewall.py::test_invalid_buckets_quarantine PASSED [ 71%]
backend/tests/unit/test_silver_firewall.py::test_cross_column_arithmetic_reconciler PASSED [ 78%]
backend/tests/unit/test_silver_firewall.py::test_final_silver_schemas_and_parquet_persistence PASSED [ 85%]
backend/tests/unit/test_smoke.py::test_package_metadata PASSED           [ 92%]
backend/tests/unit/test_smoke.py::test_core_dependencies PASSED          [100%]

============================= 14 passed in 1.17s ==============================
```

### Terminal Output: `python -m uv run --project backend ruff check backend/`
```text
All checks passed!
```

### Terminal Output: `python -m uv run --project backend mypy backend/src`
```text
Success: no issues found in 7 source files
```

---

## 4. Bronze Layer Snapshot Summary (`data/bronze/`)

### File Metadata
- **File**: `data/bronze/dghs_raw_2026_10_14.json`
- **File Size**: 5,795 bytes (5.66 KB)
- **Source Hash (SHA-256)**: `bae590a1bf506c4c213b821f7585b06a50fabd0025fb0a47924458a126a3298f`
- **Report Date Raw**: `Date: 14 October 2026`
- **Scraped At UTC**: `2026-10-15T13:51:26.933329+00:00`
- **Total Zones Extracted**: `10`
- **Total Age Groups Extracted**: `22`

### Corrupted Raw Rows Preserved Verbatim in Bronze (Zero Silent Dropping)
```json
[
  {
    "age_group": "6-10",
    "male": "1",
    "female": "0",
    "total": "1",
    "deaths": "0"
  },
  {
    "age_group": "0-10",
    "male": "1",
    "female": "0",
    "total": "1",
    "deaths": "0"
  },
  {
    "age_group": "21-25",
    "male": "3005",
    "female": "2375",
    "total": "5390",
    "deaths": "30"
  },
  {
    "age_group": "42309",
    "male": "44",
    "female": "19",
    "total": "63",
    "deaths": "2"
  },
  {
    "age_group": "46301",
    "male": "36",
    "female": "31",
    "total": "67",
    "deaths": "3"
  },
  {
    "age_group": "",
    "male": "4",
    "female": "3",
    "total": "7",
    "deaths": "0"
  }
]
```

---

## 5. Silver Layer Pandera Firewall Implementation

Exact code extracted from `backend/src/cleanpulse/silver/firewall.py`:

```python
import pandera.pandas as pa
from pandera.typing import Series

# ---------------------------------------------------------------------------
# Typed Check Functions for Strict Static Analysis
# ---------------------------------------------------------------------------
def check_raw_gender_sum(df: pd.DataFrame) -> Series[bool]:
    """Validate that male + female equals reported total for raw age groups."""
    return df["male"] + df["female"] == df["total"]


def check_reconciled_gender_sum(df: pd.DataFrame) -> Series[bool]:
    """Validate that male_cases + female_cases equals reconciled_total for sanitized cohorts."""
    return df["male_cases"] + df["female_cases"] == df["reconciled_total"]


# ---------------------------------------------------------------------------
# Stage 2A: Raw Audit Schema (lazy=True diagnostic scan)
# ---------------------------------------------------------------------------
RawAuditSchema = pa.DataFrameSchema(
    columns={
        "age_group": pa.Column(
            str,
            pa.Check.isin(CANONICAL_AGE_GROUPS),
            nullable=False,
            description="Must belong to canonical 5-year age cohorts",
        ),
        "male": pa.Column(pa.Int64, pa.Check.ge(0), coerce=True),
        "female": pa.Column(pa.Int64, pa.Check.ge(0), coerce=True),
        "total": pa.Column(pa.Int64, pa.Check.ge(0), coerce=True),
        "deaths": pa.Column(pa.Int64, pa.Check.ge(0), coerce=True, required=False),
    },
    checks=[
        pa.Check(
            check_raw_gender_sum,
            error="Row sum mismatch: male + female != total",
            name="gender_sum_check",
        )
    ],
    strict=False,
)

# ---------------------------------------------------------------------------
# Final Silver Schemas
# ---------------------------------------------------------------------------
DGHSAgeGroupSilverSchema = pa.DataFrameSchema(
    columns={
        "report_date": pa.Column(str, nullable=False),
        "age_group": pa.Column(
            str,
            pa.Check.isin(CANONICAL_AGE_GROUPS),
            nullable=False,
        ),
        "male_cases": pa.Column(pa.Int64, pa.Check.ge(0), nullable=False),
        "female_cases": pa.Column(pa.Int64, pa.Check.ge(0), nullable=False),
        "reported_total": pa.Column(pa.Int64, pa.Check.ge(0), nullable=False),
        "reconciled_total": pa.Column(pa.Int64, pa.Check.ge(0), nullable=False),
        "deaths": pa.Column(pa.Int64, pa.Check.ge(0), nullable=False),
    },
    checks=[
        pa.Check(
            check_reconciled_gender_sum,
            error="Reconciled total must equal male_cases + female_cases",
            name="reconciled_gender_sum_check",
        )
    ],
    strict=True,
    coerce=True,
)

DGHSDivisionSilverSchema = pa.DataFrameSchema(
    columns={
        "report_date": pa.Column(str, nullable=False),
        "zone_name": pa.Column(
            str,
            pa.Check.isin(CANONICAL_ZONES),
            nullable=False,
        ),
        "daily_admitted": pa.Column(pa.Int64, pa.Check.ge(0), nullable=False),
        "daily_deaths": pa.Column(pa.Int64, pa.Check.ge(0), nullable=False),
        "total_admitted": pa.Column(pa.Int64, pa.Check.ge(0), nullable=False),
        "total_deaths": pa.Column(pa.Int64, pa.Check.ge(0), nullable=False),
        "total_discharged": pa.Column(pa.Int64, pa.Check.ge(0), nullable=False),
    },
    strict=True,
    coerce=True,
)
```

### Deterministic Excel Serial Date Decoder Method
```python
@staticmethod
def decode_excel_serial_date(serial_str: str) -> str:
    """Compute date(1899, 12, 30) + timedelta(days=int(val)) to decode Excel serial dates."""
    serial_val = int(serial_str)
    decoded = date(1899, 12, 30) + timedelta(days=serial_val)
    return decoded.isoformat()
```

---

## 6. Actual Parquet Data Dump (`data/silver/*.parquet`)

Rendered directly from disk via Python and PyArrow:

### a) `data/silver/audit_anomalies.parquet` (6 rows)

| anomaly_id | detected_at_utc | table_name | row_key | raw_value | repaired_value | anomaly_type | severity | explanation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ANOM-E7453038 | 2026-10-16T05:41:40.069673+00:00 | dengue_age_groups | 6-10 | age_group=6-10 (male=1, female=0, total=1) | merged into age_group=06-10 | ZERO_PAD_DRIFT | WARNING | Non-padded age group '6-10' merged into canonical '06-10' (absorbed 1 cases) |
| ANOM-4421A02C | 2026-10-16T05:41:40.069673+00:00 | dengue_age_groups | 0-10 | age_group='0-10', male=1, female=0, total=1, deaths=0 | QUARANTINED | INVALID_AGE_BUCKET | CRITICAL | Overlapping age bucket '0-10' quarantined |
| ANOM-68DD7CBD | 2026-10-16T05:41:40.069673+00:00 | dengue_age_groups | 42309 | age_group=42309, male=44, female=19, total=63, deaths=2 | QUARANTINED_EXCEL_DATE (decoded=2015-11-01) | EXCEL_SERIAL_DATE_CAST | CRITICAL | Excel serial date '42309' decoded to date 2015-11-01; quarantined from primary age cohorts |
| ANOM-E30D03E6 | 2026-10-16T05:41:40.069673+00:00 | dengue_age_groups | 46301 | age_group=46301, male=36, female=31, total=67, deaths=3 | QUARANTINED_EXCEL_DATE (decoded=2026-10-06) | EXCEL_SERIAL_DATE_CAST | CRITICAL | Excel serial date '46301' decoded to date 2026-10-06; quarantined from primary age cohorts |
| ANOM-03A2FBD7 | 2026-10-16T05:41:40.069673+00:00 | dengue_age_groups | <EMPTY> | age_group='', male=4, female=3, total=7, deaths=0 | QUARANTINED | INVALID_AGE_BUCKET | CRITICAL | Empty age group bucket '' quarantined |
| ANOM-11EF9574 | 2026-10-16T05:41:40.069673+00:00 | dengue_age_groups | 21-25 | reported_total=5390 (male=3005, female=2375, sum=5380) | reconciled_total=5380 | GENDER_SUM_MISMATCH | WARNING | Reported total (5390) differs from male+female sum (5380) by delta +10 |

### b) `data/silver/dengue_age_groups.parquet` (17 rows)

| report_date | age_group | male_cases | female_cases | reported_total | reconciled_total | deaths |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-10-14 | 0-5 | 1250 | 980 | 2230 | 2230 | 12 |
| 2026-10-14 | 06-10 | 3021 | 2296 | 5317 | 5317 | 25 |
| 2026-10-14 | 11-15 | 2400 | 1900 | 4300 | 4300 | 18 |
| 2026-10-14 | 16-20 | 3100 | 2500 | 5600 | 5600 | 22 |
| 2026-10-14 | 21-25 | 3005 | 2375 | 5390 | 5380 | 30 |
| 2026-10-14 | 26-30 | 2800 | 2100 | 4900 | 4900 | 24 |
| 2026-10-14 | 31-35 | 2200 | 1800 | 4000 | 4000 | 20 |
| 2026-10-14 | 36-40 | 1800 | 1500 | 3300 | 3300 | 15 |
| 2026-10-14 | 41-45 | 1400 | 1200 | 2600 | 2600 | 14 |
| 2026-10-14 | 46-50 | 1100 | 950 | 2050 | 2050 | 16 |
| 2026-10-14 | 51-55 | 850 | 720 | 1570 | 1570 | 12 |
| 2026-10-14 | 56-60 | 600 | 510 | 1110 | 1110 | 10 |
| 2026-10-14 | 61-65 | 450 | 390 | 840 | 840 | 8 |
| 2026-10-14 | 66-70 | 280 | 240 | 520 | 520 | 6 |
| 2026-10-14 | 71-75 | 150 | 130 | 280 | 280 | 4 |
| 2026-10-14 | 76-80 | 80 | 70 | 150 | 150 | 2 |
| 2026-10-14 | 80+ | 45 | 40 | 85 | 85 | 2 |

### c) `data/silver/dengue_zones_daily.parquet` (10 rows)

| report_date | zone_name | daily_admitted | daily_deaths | total_admitted | total_deaths | total_discharged |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-10-14 | Chattogram | 185 | 1 | 11420 | 42 | 10950 |
| 2026-10-14 | DSCC | 320 | 3 | 18910 | 112 | 18100 |
| 2026-10-14 | Barishal | 92 | 0 | 5430 | 21 | 5200 |
| 2026-10-14 | Dhaka (Out of CC) | 145 | 1 | 8640 | 38 | 8280 |
| 2026-10-14 | DNCC | 240 | 2 | 13750 | 68 | 13200 |
| 2026-10-14 | Khulna | 78 | 1 | 4120 | 14 | 3950 |
| 2026-10-14 | Rajshahi | 46 | 0 | 2380 | 7 | 2290 |
| 2026-10-14 | Mymensingh | 38 | 0 | 1840 | 5 | 1760 |
| 2026-10-14 | Rangpur | 24 | 0 | 1122 | 4 | 1080 |
| 2026-10-14 | Sylhet | 18 | 0 | 820 | 4 | 790 |

---

## 7. Deviations, Open Questions & Readiness for Step 3

### Deviations & Technical Gotchas Resolved
1. **GitHub Actions Cache & `setup-uv` Versioning**:
   - `setup-uv@v3` failed on initial runner initialization due to Node 20 deprecation and default search for `uv.lock`.
   - Upgraded to `astral-sh/setup-uv@v5`, committed `backend/uv.lock`, and isolated commands with `uv run --project backend`.
2. **Pyright Static Analysis on Anonymous Lambdas**:
   - Anonymous lambda checks (`lambda df: ...`) triggered unknown parameter type warnings under strict IDE checks.
   - Refactored to explicit named check functions (`check_raw_gender_sum`, `check_reconciled_gender_sum`) typed with `Series[bool]`.
3. **Excel Epoch Calculation**:
   - Confirmed `date(1899, 12, 30) + timedelta(days=val)` as the standard formula accounting for Excel's 1900 leap year bug (`42309` -> `2015-11-01`, `46301` -> `2026-10-06`).

### Readiness for Step 3 (64-District Open-Meteo Batch Client & Spatial Crosswalk)
- **Reference Data Required**: Build `data/reference/bangladesh_districts.json` containing the 64 canonical districts, centroid coordinates (lat/lon), and mapping to the 10 DGHS surveillance reporting zones.
- **Climate Ingestion Scope**: Ingest daily temperature (min, max, mean), relative humidity, and precipitation via Open-Meteo Historical / Archive API.
- **Pipeline Health**: Both Bronze and Silver layers are deterministic, immutable, zero-drop compliant, and verified by 14 unit tests.
