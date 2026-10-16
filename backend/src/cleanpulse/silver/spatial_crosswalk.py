"""Spatial Crosswalk Module for Bangladesh 64 Districts and DGHS Surveillance Zones.

Maps Bangladesh 64 canonical districts to geographical centroids (latitude, longitude),
parent administrative divisions, and the 10 canonical DGHS Dengue Surveillance zones:
  - 7 Division zones: Chattogram, Barishal, Khulna, Rajshahi, Mymensingh, Rangpur, Sylhet.
  - 3 Greater Dhaka zones:
      - DNCC (Dhaka North City Corporation) -> mapped from Dhaka district
      - DSCC (Dhaka South City Corporation) -> mapped from Dhaka district
      - Dhaka (Out of CC) -> 12 suburban districts (Faridpur, Gazipur, Gopalganj,
        Kishoreganj, Madaripur, Manikganj, Munshiganj, Narayanganj, Narsingdi,
        Rajbari, Shariatpur, Tangail)

Enforces Pandera validation ensuring exactly 64 unique districts and full 10-zone coverage.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import pandera.pandas as pa
from pydantic import BaseModel, Field

from cleanpulse.silver.firewall import CANONICAL_ZONES

DEFAULT_CROSSWALK_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "reference" / "bd_64_districts_crosswalk.json"
)

CANONICAL_DIVISIONS: list[str] = [
    "Barishal",
    "Chattogram",
    "Dhaka",
    "Khulna",
    "Mymensingh",
    "Rajshahi",
    "Rangpur",
    "Sylhet",
]


class DistrictCrosswalkRecord(BaseModel):
    """Pydantic model validating an individual district crosswalk entry."""

    district_id: str = Field(..., description="Unique kebab/snake district identifier")
    district_name: str = Field(..., description="Official English district name")
    division_name: str = Field(..., description="One of 8 administrative divisions")
    latitude: float = Field(..., ge=20.5, le=26.8, description="Centroid latitude")
    longitude: float = Field(..., ge=88.0, le=92.8, description="Centroid longitude")
    dghs_reporting_zones: list[str] = Field(
        default_factory=list,
        description="List of mapped DGHS zones (Dhaka maps to ['DNCC', 'DSCC'])",
    )
    dghs_reporting_zone: str = Field(
        ...,
        description="Comma-separated or primary DGHS reporting zone string",
    )


def check_exact_64_districts(df: pd.DataFrame) -> bool:
    """Verify that the crosswalk contains exactly 64 unique districts."""
    return len(df) == 64 and df["district_id"].nunique() == 64


def check_covers_all_dghs_zones(df: pd.DataFrame) -> bool:
    """Verify that all 10 canonical DGHS zones are represented in the crosswalk."""
    all_zones: set[str] = set()
    for zones in df["dghs_reporting_zones"]:
        if isinstance(zones, (list, np.ndarray)):
            all_zones.update(zones)
        elif isinstance(zones, str):
            all_zones.update([z.strip() for z in zones.split(",")])
    return set(CANONICAL_ZONES).issubset(all_zones)


DistrictCrosswalkSilverSchema = pa.DataFrameSchema(
    columns={
        "district_id": pa.Column(str, nullable=False, unique=True),
        "district_name": pa.Column(str, nullable=False, unique=True),
        "division_name": pa.Column(
            str,
            pa.Check.isin(CANONICAL_DIVISIONS),
            nullable=False,
        ),
        "latitude": pa.Column(
            float,
            pa.Check.in_range(20.5, 26.8),
            nullable=False,
        ),
        "longitude": pa.Column(
            float,
            pa.Check.in_range(88.0, 92.8),
            nullable=False,
        ),
        "dghs_reporting_zones": pa.Column(object, nullable=False),
        "dghs_reporting_zone": pa.Column(str, nullable=False),
    },
    checks=[
        pa.Check(
            check_exact_64_districts,
            error="Crosswalk must contain exactly 64 unique districts",
            name="exact_64_districts_check",
        ),
        pa.Check(
            check_covers_all_dghs_zones,
            error="Crosswalk must cover all 10 canonical DGHS surveillance zones",
            name="covers_all_dghs_zones_check",
        ),
    ],
    strict=True,
    coerce=True,
)


def load_district_crosswalk(crosswalk_path: Path | str | None = None) -> pd.DataFrame:
    """Load and validate the canonical 64-district spatial crosswalk.

    Args:
        crosswalk_path: Path to crosswalk JSON (defaults to
            data/reference/bd_64_districts_crosswalk.json).

    Returns:
        Validated DataFrame conforming to DistrictCrosswalkSilverSchema.
    """
    path = Path(crosswalk_path) if crosswalk_path is not None else DEFAULT_CROSSWALK_PATH
    if not path.exists():
        raise FileNotFoundError(f"Spatial crosswalk file not found at: {path}")

    with open(path, encoding="utf-8") as f:
        records: list[dict[str, Any]] = json.load(f)

    # Validate each entry against Pydantic model
    validated_records = [DistrictCrosswalkRecord(**rec).model_dump() for rec in records]
    df = pd.DataFrame(validated_records)

    # Validate against Pandera silver schema
    validated_df = DistrictCrosswalkSilverSchema.validate(df, lazy=True)
    return validated_df


def get_district_by_id(district_id: str, df: pd.DataFrame | None = None) -> dict[str, Any]:
    """Retrieve metadata and coordinates for a specific district.

    Args:
        district_id: District identifier (e.g. 'dhaka', 'chattogram', 'madaripur').
        df: Optional preloaded crosswalk DataFrame.

    Returns:
        Dictionary representation of the district record.
    """
    crosswalk = df if df is not None else load_district_crosswalk()
    match = crosswalk[crosswalk["district_id"] == district_id]
    if match.empty:
        raise KeyError(f"District ID '{district_id}' not found in crosswalk.")
    record: dict[str, Any] = match.iloc[0].to_dict()
    return record


def get_districts_for_zone(zone_name: str, df: pd.DataFrame | None = None) -> list[str]:
    """Retrieve all district IDs belonging to a specific DGHS reporting zone.

    Args:
        zone_name: Canonical zone name (e.g. 'Chattogram', 'DNCC', 'Dhaka (Out of CC)').
        df: Optional preloaded crosswalk DataFrame.

    Returns:
        List of matching district_ids.
    """
    if zone_name not in CANONICAL_ZONES:
        raise ValueError(f"Zone '{zone_name}' is not one of the 10 canonical DGHS zones.")
    crosswalk = df if df is not None else load_district_crosswalk()
    matching_ids: list[str] = []
    for _, row in crosswalk.iterrows():
        zones = row["dghs_reporting_zones"]
        is_in_list = isinstance(zones, (list, np.ndarray)) and zone_name in zones
        is_in_str = isinstance(zones, str) and zone_name in [z.strip() for z in zones.split(",")]
        if is_in_list or is_in_str:
            matching_ids.append(str(row["district_id"]))
    return matching_ids


def get_district_zone_bridge(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build an unnested bridge table mapping district_id to zone_name.

    Returns:
        DataFrame with columns ['district_id', 'zone_name'] (65 rows total:
        Dhaka maps to both DNCC and DSCC; other 63 districts map 1-to-1).
    """
    crosswalk = df if df is not None else load_district_crosswalk()
    rows: list[dict[str, str]] = []
    for _, row in crosswalk.iterrows():
        did = str(row["district_id"])
        zones = row["dghs_reporting_zones"]
        if isinstance(zones, (list, np.ndarray)):
            for z in zones:
                rows.append({"district_id": did, "zone_name": str(z)})
        elif isinstance(zones, str):
            for z in zones.split(","):
                rows.append({"district_id": did, "zone_name": z.strip()})
    return pd.DataFrame(rows)
