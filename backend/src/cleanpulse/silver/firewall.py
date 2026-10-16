"""Silver Layer Pandera Validation Firewall & Deterministic Data Sanitization Module.

Implements two-stage Medallion processing:
  Stage 2A: Lazy raw audit scan flagging all schema and cross-column arithmetic violations.
  Stage 2B: Deterministic repair & quarantine (Excel serial date decoder, zero-pad canonicalizer,
            invalid bucket quarantine, gender cross-column reconciler).
Enforces final Pandera silver schemas and persists clean Parquet tables + audit_anomalies.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import pandera.pandas as pa
from pandera.typing import Series

logger = logging.getLogger(__name__)

DEFAULT_SILVER_DIR = Path(__file__).resolve().parents[4] / "data" / "silver"

CANONICAL_AGE_GROUPS: list[str] = [
    "0-5",
    "06-10",
    "11-15",
    "16-20",
    "21-25",
    "26-30",
    "31-35",
    "36-40",
    "41-45",
    "46-50",
    "51-55",
    "56-60",
    "61-65",
    "66-70",
    "71-75",
    "76-80",
    "80+",
]

CANONICAL_ZONES: list[str] = [
    "Chattogram",
    "DSCC",
    "Barishal",
    "Dhaka (Out of CC)",
    "DNCC",
    "Khulna",
    "Rajshahi",
    "Mymensingh",
    "Rangpur",
    "Sylhet",
]


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
        "arithmetic_delta": pa.Column(pa.Int64, nullable=False),
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

AuditAnomalySilverSchema = pa.DataFrameSchema(
    columns={
        "anomaly_id": pa.Column(str, nullable=False, unique=True),
        "detected_at_utc": pa.Column(str, nullable=False),
        "table_name": pa.Column(str, nullable=False),
        "row_key": pa.Column(str, nullable=False),
        "raw_value": pa.Column(str, nullable=False),
        "repaired_value": pa.Column(str, nullable=False),
        "anomaly_type": pa.Column(
            str,
            pa.Check.isin(
                [
                    "EXCEL_SERIAL_DATE_CAST",
                    "ZERO_PAD_DRIFT",
                    "INVALID_AGE_BUCKET",
                    "GENDER_SUM_MISMATCH",
                    "SCHEMA_VALIDATION_ERROR",
                ]
            ),
            nullable=False,
        ),
        "severity": pa.Column(
            str,
            pa.Check.isin(["CRITICAL", "WARNING", "INFO"]),
            nullable=False,
        ),
        "explanation": pa.Column(str, nullable=False),
    },
    strict=True,
    coerce=True,
)

AuditAnomalySchema = AuditAnomalySilverSchema


@dataclass
class SilverPipelineResult:
    """Container holding DataFrames and file paths produced by the Silver firewall."""

    age_groups_df: pd.DataFrame
    zones_df: pd.DataFrame
    anomalies_df: pd.DataFrame
    age_groups_parquet: Path
    zones_parquet: Path
    anomalies_parquet: Path


class SilverSanitizerFirewall:
    """Sanitization and Pandera validation firewall for DGHS Dengue surveillance data."""

    def __init__(self, output_dir: Path | str | None = None) -> None:
        """Initialize the Silver firewall.

        Args:
            output_dir: Output directory for silver parquet tables (defaults to data/silver).
        """
        self.output_dir = Path(output_dir) if output_dir is not None else DEFAULT_SILVER_DIR

    @staticmethod
    def decode_excel_serial_date(serial_str: str) -> str:
        """Compute date(1899, 12, 30) + timedelta(days=int(val)) to decode Excel serial dates.

        Args:
            serial_str: A string representing a 5-digit integer between 35000 and 55000.

        Returns:
            Decoded date string in YYYY-MM-DD format.
        """
        serial_val = int(serial_str)
        decoded = date(1899, 12, 30) + timedelta(days=serial_val)
        return decoded.isoformat()

    def run_raw_audit_scan(self, raw_age_df: pd.DataFrame) -> pd.DataFrame | None:
        """Stage 2A: Run lazy Pandera validation against RawAuditSchema without early exit.

        Args:
            raw_age_df: Raw DataFrame from Bronze snapshot.

        Returns:
            DataFrame of failure cases collected by Pandera, or None if validation passed.
        """
        # Ensure numeric columns are castable for check evaluation
        df_eval = raw_age_df.copy()
        for col in ["male", "female", "total", "deaths"]:
            if col in df_eval.columns:
                df_eval[col] = pd.to_numeric(
                    df_eval[col].astype(str).str.replace(",", "").str.strip(),
                    errors="coerce",
                ).fillna(0)

        try:
            RawAuditSchema.validate(df_eval, lazy=True)
            return None
        except pa.errors.SchemaErrors as exc:
            logger.info(
                "Stage 2A lazy audit scan collected %d failure cases",
                len(exc.failure_cases),
            )
            return exc.failure_cases

    def repair_and_quarantine_age_groups(
        self,
        raw_age_df: pd.DataFrame,
        report_date: str,
    ) -> tuple[pd.DataFrame, list[dict[str, str]]]:
        """Stage 2B: Apply deterministic repair and quarantine routines on age groups.

        Routines executed:
          a) Excel Serial Date Decoder: Detect 5-digit integer strings in `age_group`
             (35000..55000). Compute date(1899, 12, 30) + timedelta(days=int(val)),
             quarantine row, log anomaly.
          b) Zero-Pad Canonicalizer: Merge `6-10` into `06-10`, quarantine `0-10` and `""`.
          c) Cross-Column Arithmetic Reconciler: Compare male + female against reported total,
             log anomaly if delta != 0, store reported_total and reconciled_total.

        Args:
            raw_age_df: Raw DataFrame of age group records.
            report_date: ISO date string for the report.

        Returns:
            Tuple of (sanitized_age_df, list_of_audit_anomalies).
        """
        anomalies: list[dict[str, str]] = []
        now_utc = datetime.now(UTC).isoformat()

        # Temporary working dictionaries
        canonical_rows: dict[str, dict[str, int]] = {
            grp: {
                "male_cases": 0,
                "female_cases": 0,
                "reported_total": 0,
                "reconciled_total": 0,
                "deaths": 0,
            }
            for grp in CANONICAL_AGE_GROUPS
        }

        # Keep track of which canonical groups were actively populated from bronze
        active_canonical_groups: set[str] = set()

        # Pending zero-pad merge payload
        zero_pad_cases: dict[str, int] = {"male": 0, "female": 0, "total": 0, "deaths": 0}
        has_zero_pad_merge = False

        for _, row in raw_age_df.iterrows():
            raw_label = str(row.get("age_group", "")).strip()

            def _clean_num(val: Any) -> int:
                s = str(val).replace(",", "").strip()
                return int(s) if s.isdigit() else 0

            male = _clean_num(row.get("male", 0))
            female = _clean_num(row.get("female", 0))
            reported_total = _clean_num(row.get("total", 0))
            deaths = _clean_num(row.get("deaths", 0))

            # a) Excel Serial Date Decoder
            if raw_label.isdigit() and len(raw_label) == 5 and (35000 <= int(raw_label) <= 55000):
                decoded_date = self.decode_excel_serial_date(raw_label)
                anomalies.append(
                    {
                        "anomaly_id": f"ANOM-{uuid.uuid4().hex[:8].upper()}",
                        "detected_at_utc": now_utc,
                        "table_name": "dengue_age_groups",
                        "row_key": raw_label,
                        "raw_value": (
                            f"age_group={raw_label}, male={male}, female={female}, "
                            f"total={reported_total}, deaths={deaths}"
                        ),
                        "repaired_value": f"QUARANTINED_EXCEL_DATE (decoded={decoded_date})",
                        "anomaly_type": "EXCEL_SERIAL_DATE_CAST",
                        "severity": "CRITICAL",
                        "explanation": (
                            f"Excel serial date '{raw_label}' decoded to date {decoded_date}; "
                            "quarantined from primary age cohorts"
                        ),
                    }
                )
                continue

            # b) Zero-Pad Canonicalizer & Overlapping / Empty Buckets
            if raw_label == "6-10":
                has_zero_pad_merge = True
                zero_pad_cases["male"] += male
                zero_pad_cases["female"] += female
                zero_pad_cases["total"] += reported_total
                zero_pad_cases["deaths"] += deaths
                anomalies.append(
                    {
                        "anomaly_id": f"ANOM-{uuid.uuid4().hex[:8].upper()}",
                        "detected_at_utc": now_utc,
                        "table_name": "dengue_age_groups",
                        "row_key": "6-10",
                        "raw_value": (
                            f"age_group=6-10 (male={male}, female={female}, total={reported_total})"
                        ),
                        "repaired_value": "merged into age_group=06-10",
                        "anomaly_type": "ZERO_PAD_DRIFT",
                        "severity": "WARNING",
                        "explanation": (
                            f"Non-padded age group '6-10' merged into canonical '06-10' "
                            f"(absorbed {reported_total} cases)"
                        ),
                    }
                )
                continue

            if raw_label in ("0-10", ""):
                anomalies.append(
                    {
                        "anomaly_id": f"ANOM-{uuid.uuid4().hex[:8].upper()}",
                        "detected_at_utc": now_utc,
                        "table_name": "dengue_age_groups",
                        "row_key": raw_label if raw_label else "<EMPTY>",
                        "raw_value": (
                            f"age_group='{raw_label}', male={male}, female={female}, "
                            f"total={reported_total}, deaths={deaths}"
                        ),
                        "repaired_value": "QUARANTINED",
                        "anomaly_type": "INVALID_AGE_BUCKET",
                        "severity": "CRITICAL",
                        "explanation": (
                            f"Overlapping age bucket '{raw_label}' quarantined"
                            if raw_label
                            else "Empty age group bucket '' quarantined"
                        ),
                    }
                )
                continue

            # If it matches a canonical age group, store it
            if raw_label in canonical_rows:
                active_canonical_groups.add(raw_label)
                canonical_rows[raw_label]["male_cases"] = male
                canonical_rows[raw_label]["female_cases"] = female
                canonical_rows[raw_label]["reported_total"] = reported_total
                canonical_rows[raw_label]["deaths"] = deaths

        # Apply zero-pad merge into '06-10' if detected
        if has_zero_pad_merge and "06-10" in canonical_rows:
            canonical_rows["06-10"]["male_cases"] += zero_pad_cases["male"]
            canonical_rows["06-10"]["female_cases"] += zero_pad_cases["female"]
            canonical_rows["06-10"]["reported_total"] += zero_pad_cases["total"]
            canonical_rows["06-10"]["deaths"] += zero_pad_cases["deaths"]
            active_canonical_groups.add("06-10")

        # c) Cross-Column Arithmetic Reconciler
        sanitized_records: list[dict[str, Any]] = []
        for grp in CANONICAL_AGE_GROUPS:
            if grp not in active_canonical_groups:
                continue

            data = canonical_rows[grp]
            male_c = data["male_cases"]
            female_c = data["female_cases"]
            rep_tot = data["reported_total"]
            reconciled_tot = male_c + female_c
            delta = rep_tot - reconciled_tot

            if delta != 0:
                anomalies.append(
                    {
                        "anomaly_id": f"ANOM-{uuid.uuid4().hex[:8].upper()}",
                        "detected_at_utc": now_utc,
                        "table_name": "dengue_age_groups",
                        "row_key": grp,
                        "raw_value": (
                            f"reported_total={rep_tot} (male={male_c}, "
                            f"female={female_c}, sum={reconciled_tot})"
                        ),
                        "repaired_value": f"reconciled_total={reconciled_tot}",
                        "anomaly_type": "GENDER_SUM_MISMATCH",
                        "severity": "WARNING",
                        "explanation": (
                            f"Reported total ({rep_tot}) differs from "
                            f"male+female sum ({reconciled_tot}) by delta {delta:+d}"
                        ),
                    }
                )

            sanitized_records.append(
                {
                    "report_date": report_date,
                    "age_group": grp,
                    "male_cases": male_c,
                    "female_cases": female_c,
                    "reported_total": rep_tot,
                    "reconciled_total": reconciled_tot,
                    "arithmetic_delta": delta,
                    "deaths": data["deaths"],
                }
            )

        sanitized_df = pd.DataFrame(sanitized_records)
        return sanitized_df, anomalies

    def sanitize_zones(
        self,
        raw_zones_df: pd.DataFrame,
        report_date: str,
    ) -> pd.DataFrame:
        """Sanitize zone/division distribution records from Bronze into Silver format.

        Args:
            raw_zones_df: Raw DataFrame of zone reporting records.
            report_date: ISO date string for the report.

        Returns:
            Sanitized and typed DataFrame conforming to DGHSDivisionSilverSchema.
        """
        sanitized_rows: list[dict[str, Any]] = []
        for _, row in raw_zones_df.iterrows():
            zone_name = str(row.get("zone_name", "")).strip()
            if not zone_name or zone_name.lower() == "total":
                continue

            def _clean(val: Any) -> int:
                s = str(val).replace(",", "").strip()
                return int(s) if s.isdigit() else 0

            sanitized_rows.append(
                {
                    "report_date": report_date,
                    "zone_name": zone_name,
                    "daily_admitted": _clean(row.get("daily_admitted", 0)),
                    "daily_deaths": _clean(row.get("daily_deaths", 0)),
                    "total_admitted": _clean(row.get("total_admitted", 0)),
                    "total_deaths": _clean(row.get("total_deaths", 0)),
                    "total_discharged": _clean(row.get("total_discharged", 0)),
                }
            )

        return pd.DataFrame(sanitized_rows)

    def process_bronze_snapshot(
        self,
        bronze_data_or_path: dict[str, Any] | Path | str,
        output_dir: Path | str | None = None,
    ) -> SilverPipelineResult:
        """Execute end-to-end Silver pipeline on Bronze data.

        Stages:
          Stage 2A: Raw audit scan with lazy Pandera validation.
          Stage 2B: Deterministic repair & quarantine.
          Enforcement: Pandera validation on sanitized outputs.
          Persistence: Parquet export of silver tables and audit_anomalies.

        Args:
            bronze_data_or_path: In-memory Bronze dictionary or Path to Bronze raw JSON file.
            output_dir: Target output directory for Silver Parquet files.

        Returns:
            SilverPipelineResult with validated DataFrames and Parquet paths.
        """
        target_dir = Path(output_dir) if output_dir is not None else self.output_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        if isinstance(bronze_data_or_path, (str, Path)):
            with open(bronze_data_or_path, encoding="utf-8") as f:
                bronze_data = json.load(f)
        else:
            bronze_data = bronze_data_or_path

        # 1. Parse report date
        raw_date_str = str(bronze_data.get("metadata", {}).get("report_date_raw", ""))
        match = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", raw_date_str)
        if match:
            day, month_str, year = match.groups()
            try:
                report_date = datetime.strptime(f"{day} {month_str} {year}", "%d %B %Y").strftime(
                    "%Y-%m-%d"
                )
            except ValueError:
                report_date = datetime.now(UTC).strftime("%Y-%m-%d")
        else:
            report_date = datetime.now(UTC).strftime("%Y-%m-%d")

        raw_age_df = pd.DataFrame(bronze_data.get("age_groups", []))
        raw_zones_df = pd.DataFrame(bronze_data.get("zones", []))

        # 2. Stage 2A: Raw Audit Scan
        self.run_raw_audit_scan(raw_age_df)

        # 3. Stage 2B: Repair & Quarantine
        sanitized_age_df, anomalies = self.repair_and_quarantine_age_groups(
            raw_age_df=raw_age_df,
            report_date=report_date,
        )

        sanitized_zones_df = self.sanitize_zones(
            raw_zones_df=raw_zones_df,
            report_date=report_date,
        )

        # 4. Final Silver Schemas Enforcement (lazy=True)
        validated_age_df = DGHSAgeGroupSilverSchema.validate(sanitized_age_df, lazy=True)
        validated_zones_df = DGHSDivisionSilverSchema.validate(sanitized_zones_df, lazy=True)

        anomalies_df = pd.DataFrame(anomalies)
        validated_anomalies_df = AuditAnomalySilverSchema.validate(anomalies_df, lazy=True)

        # 5. Parquet Exports
        age_parquet_path = target_dir / "dengue_age_groups.parquet"
        zones_parquet_path = target_dir / "dengue_zones_daily.parquet"
        anomalies_parquet_path = target_dir / "audit_anomalies.parquet"

        validated_age_df.to_parquet(age_parquet_path, index=False)
        validated_zones_df.to_parquet(zones_parquet_path, index=False)
        validated_anomalies_df.to_parquet(anomalies_parquet_path, index=False)

        logger.info("Exported silver age groups to: %s", age_parquet_path)
        logger.info("Exported silver zones daily to: %s", zones_parquet_path)
        logger.info("Exported silver audit anomalies to: %s", anomalies_parquet_path)

        return SilverPipelineResult(
            age_groups_df=validated_age_df,
            zones_df=validated_zones_df,
            anomalies_df=validated_anomalies_df,
            age_groups_parquet=age_parquet_path,
            zones_parquet=zones_parquet_path,
            anomalies_parquet=anomalies_parquet_path,
        )
