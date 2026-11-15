"""Silver-layer builders for secondary historical dengue datasets (Mendeley A & B)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pandera.pandas as pa

from cleanpulse.bronze.xlsx_reader import read_xlsx_rows
from cleanpulse.silver.firewall import AuditAnomalySilverSchema

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_BRONZE_MENDELEY_DIR = REPO_ROOT / "data" / "bronze" / "mendeley"
DEFAULT_SILVER_DIR = REPO_ROOT / "data" / "silver"

SECONDARY_SOURCE_LABEL = (
    "secondary source: transcribed from DGHS daily press releases "
    "(unverified transcription by third party)"
)

CANONICAL_DIVISIONS: tuple[str, ...] = (
    "Barishal",
    "Chattogram",
    "Dhaka",
    "Khulna",
    "Mymensingh",
    "Rajshahi",
    "Rangpur",
    "Sylhet",
)

# Maps Dataset A filename -> (case_column_name, raw_label_in_source, canonical_division)
DATASET_A_FILE_SPECS: dict[str, tuple[str, str, str]] = {
    "Barisal.csv": ("effected-Barishal", "Barishal", "Barishal"),
    "Chittagong.csv": ("effected-chittagong", "chittagong", "Chattogram"),
    "Dhaka.csv": ("effected", "Dhaka", "Dhaka"),
    "khulna.csv": ("effected-khulna", "khulna", "Khulna"),
    "Mymensingh.csv": ("effected-Mymensingh", "Mymensingh", "Mymensingh"),
    "Rajshahi.csv": ("effected-Rajhshahi", "Rajhshahi", "Rajshahi"),
    "Rangpur.csv": ("effected-Rangpur", "Rangpur", "Rangpur"),
    "Sylhet.csv": ("effected-Syllhet", "Syllhet", "Sylhet"),
}

DIV_CANON_MAP: dict[str, str] = {
    "barisal": "Barishal",
    "barishal": "Barishal",
    "chittagong": "Chattogram",
    "chattogram": "Chattogram",
    "dhaka": "Dhaka",
    "khulna": "Khulna",
    "mymensingh": "Mymensingh",
    "rajshahi": "Rajshahi",
    "rajhshahi": "Rajshahi",
    "rangpur": "Rangpur",
    "sylhet": "Sylhet",
    "syllhet": "Sylhet",
}

MONTH_NAME_TO_NUM: dict[str, int] = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

DengueDivisionDailySchema = pa.DataFrameSchema(
    columns={
        "report_date": pa.Column(str, nullable=False),
        "division": pa.Column(str, pa.Check.isin(CANONICAL_DIVISIONS), nullable=False),
        "cases": pa.Column(pa.Int64, pa.Check.ge(0), nullable=False),
        "source_label": pa.Column(str, nullable=False),
    },
    unique=["report_date", "division"],
    strict=True,
    coerce=True,
)

DengueDivisionMonthlyBSchema = pa.DataFrameSchema(
    columns={
        "division": pa.Column(str, pa.Check.isin(CANONICAL_DIVISIONS), nullable=False),
        "year": pa.Column(pa.Int64, pa.Check.in_range(2020, 2025), nullable=False),
        "month": pa.Column(pa.Int64, pa.Check.in_range(1, 12), nullable=False),
        "infected": pa.Column(pa.Int64, pa.Check.ge(0), nullable=False),
        "death": pa.Column(pa.Int64, pa.Check.ge(0), nullable=False),
    },
    unique=["division", "year", "month"],
    strict=True,
    coerce=True,
)


def _make_anomaly(
    anomaly_id: str,
    table_name: str,
    row_key: str,
    raw_value: str,
    repaired_value: str,
    anomaly_type: str,
    explanation: str,
    now_utc: str,
) -> dict[str, str]:
    return {
        "anomaly_id": anomaly_id,
        "detected_at_utc": now_utc,
        "table_name": table_name,
        "row_key": row_key,
        "raw_value": raw_value,
        "repaired_value": repaired_value,
        "anomaly_type": anomaly_type,
        "severity": "INFO",
        "explanation": explanation,
    }


def build_dengue_division_daily(
    bronze_a_dir: Path | None = None,
    silver_dir: Path | None = None,
) -> tuple[Path, list[dict[str, str]]]:
    """Build Silver dengue_division_daily.parquet from Bronze Dataset A CSVs."""
    src_dir = bronze_a_dir or (DEFAULT_BRONZE_MENDELEY_DIR / "A" / "v1")
    out_dir = silver_dir or DEFAULT_SILVER_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(UTC).isoformat()

    frames: list[pd.DataFrame] = []
    anomalies: list[dict[str, str]] = []

    for filename, (case_col, raw_label, canon_div) in DATASET_A_FILE_SPECS.items():
        csv_path = src_dir / filename
        if not csv_path.exists():
            raise FileNotFoundError(f"Missing Bronze Dataset A file: {csv_path}")
        df = pd.read_csv(csv_path)
        if "Date" not in df.columns or case_col not in df.columns:
            raise ValueError(
                f"Expected columns 'Date' and {case_col!r} in {filename}; got {list(df.columns)}"
            )

        parsed_dates = pd.to_datetime(df["Date"], format="%d-%m-%y", errors="raise")
        cases_num = pd.to_numeric(df[case_col], errors="raise")
        if ((cases_num % 1) != 0).any() or cases_num.isna().any():
            raise ValueError(f"Non-integer or missing case values in {filename}")

        if raw_label != canon_div:
            anomalies.append(
                _make_anomaly(
                    anomaly_id=f"A_DIV_NORM_{filename}",
                    table_name="dengue_division_daily",
                    row_key=f"file:{filename}",
                    raw_value=raw_label,
                    repaired_value=canon_div,
                    anomaly_type="DIVISION_LABEL_NORMALIZED",
                    explanation=(
                        f"REPAIRED: normalized Dataset A division label {raw_label!r} "
                        f"to canonical {canon_div!r} (weather columns dropped)."
                    ),
                    now_utc=now_utc,
                )
            )

        frames.append(
            pd.DataFrame(
                {
                    "report_date": parsed_dates.dt.strftime("%Y-%m-%d"),
                    "division": canon_div,
                    "cases": cases_num.astype("int64"),
                    "source_label": SECONDARY_SOURCE_LABEL,
                }
            )
        )

    combined = (
        pd.concat(frames, ignore_index=True)
        .sort_values(["report_date", "division"])
        .reset_index(drop=True)
    )
    validated = DengueDivisionDailySchema.validate(combined)
    out_path = out_dir / "dengue_division_daily.parquet"
    validated.to_parquet(out_path, index=False)
    return out_path, anomalies


def build_dengue_division_monthly_b(
    bronze_b_dir: Path | None = None,
    silver_dir: Path | None = None,
) -> tuple[Path, list[dict[str, str]]]:
    """Build reconciliation-only Silver dengue_division_monthly_b.parquet from Bronze B."""
    src_dir = bronze_b_dir or (DEFAULT_BRONZE_MENDELEY_DIR / "B" / "v2")
    out_dir = silver_dir or DEFAULT_SILVER_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(UTC).isoformat()

    xlsx_path = src_dir / "dataset.xlsx"
    if not xlsx_path.exists():
        raise FileNotFoundError(f"Missing Bronze Dataset B file: {xlsx_path}")

    raw_rows = read_xlsx_rows(xlsx_path)
    if len(raw_rows) < 2:
        raise ValueError(f"Dataset B XLSX has insufficient rows: {len(raw_rows)}")

    headers = [h.strip() for h in raw_rows[0]]
    idx_div = headers.index("Division")
    idx_year = headers.index("Year")
    idx_month = headers.index("Month")
    idx_inf = headers.index("Infected")
    idx_death = headers.index("Death")

    anomalies: list[dict[str, str]] = []
    records: list[dict[str, object]] = []

    current_div_raw = ""
    current_year_raw = ""
    div_ffill_count = 0
    year_ffill_count = 0
    seen_div_norm: set[str] = set()

    for row_num, row in enumerate(raw_rows[1:], start=2):
        raw_div = row[idx_div]
        raw_year = row[idx_year]
        raw_month = row[idx_month].strip()

        if raw_div == "":
            div_ffill_count += 1
        else:
            current_div_raw = raw_div

        if raw_year == "":
            year_ffill_count += 1
        else:
            current_year_raw = raw_year

        if not current_div_raw or not current_year_raw:
            raise ValueError(f"Missing Division/Year before row {row_num} in {xlsx_path}")

        stripped_div = current_div_raw.strip()
        canon_div = DIV_CANON_MAP.get(stripped_div.lower())
        if canon_div is None:
            raise ValueError(
                f"Unrecognized Dataset B division {current_div_raw!r} at row {row_num}"
            )

        if current_div_raw != canon_div and current_div_raw not in seen_div_norm:
            seen_div_norm.add(current_div_raw)
            anomalies.append(
                _make_anomaly(
                    anomaly_id=f"B_DIV_NORM_{canon_div}",
                    table_name="dengue_division_monthly_b",
                    row_key=f"division:{current_div_raw!r}",
                    raw_value=current_div_raw,
                    repaired_value=canon_div,
                    anomaly_type="DIVISION_LABEL_NORMALIZED",
                    explanation=(
                        f"REPAIRED: normalized Dataset B division label "
                        f"{current_div_raw!r} to {canon_div!r}."
                    ),
                    now_utc=now_utc,
                )
            )

        month_num = MONTH_NAME_TO_NUM.get(raw_month.lower())
        if month_num is None:
            month_num = int(float(raw_month))

        records.append(
            {
                "division": canon_div,
                "year": int(float(current_year_raw)),
                "month": month_num,
                "infected": int(float(row[idx_inf])),
                "death": int(float(row[idx_death])),
            }
        )

    if div_ffill_count > 0:
        anomalies.append(
            _make_anomaly(
                anomaly_id="B_MERGED_CELL_FFILL_DIVISION",
                table_name="dengue_division_monthly_b",
                row_key="column:Division",
                raw_value=f"{div_ffill_count} empty merged cells",
                repaired_value="forward-filled from block header",
                anomaly_type="MERGED_CELL_FORWARD_FILL",
                explanation=(
                    f"REPAIRED: forward-filled {div_ffill_count} blank merged Division cells "
                    "in Dataset B XLSX."
                ),
                now_utc=now_utc,
            )
        )
    if year_ffill_count > 0:
        anomalies.append(
            _make_anomaly(
                anomaly_id="B_MERGED_CELL_FFILL_YEAR",
                table_name="dengue_division_monthly_b",
                row_key="column:Year",
                raw_value=f"{year_ffill_count} empty merged cells",
                repaired_value="forward-filled from block header",
                anomaly_type="MERGED_CELL_FORWARD_FILL",
                explanation=(
                    f"REPAIRED: forward-filled {year_ffill_count} blank merged Year cells "
                    "in Dataset B XLSX."
                ),
                now_utc=now_utc,
            )
        )

    df_b = pd.DataFrame(records).sort_values(["division", "year", "month"]).reset_index(drop=True)
    validated = DengueDivisionMonthlyBSchema.validate(df_b)
    out_path = out_dir / "dengue_division_monthly_b.parquet"
    validated.to_parquet(out_path, index=False)
    return out_path, anomalies


def write_or_merge_audit_anomalies(
    anomalies: list[dict[str, str]],
    silver_dir: Path | None = None,
) -> Path:
    """Merge new INFO/REPAIRED anomaly rows into Silver audit_anomalies.parquet."""
    out_dir = silver_dir or DEFAULT_SILVER_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    audit_path = out_dir / "audit_anomalies.parquet"

    new_df = pd.DataFrame(anomalies)
    if audit_path.exists():
        existing_df = pd.read_parquet(audit_path)
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["anomaly_id"], keep="last")
    else:
        combined = new_df

    validated = AuditAnomalySilverSchema.validate(combined)
    validated.to_parquet(audit_path, index=False)
    return audit_path
