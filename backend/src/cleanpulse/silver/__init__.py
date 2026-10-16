"""Silver layer: Pandera validation, deterministic repairs, and audit anomaly logging."""

from cleanpulse.silver.firewall import (
    CANONICAL_AGE_GROUPS,
    CANONICAL_ZONES,
    AuditAnomalySchema,
    AuditAnomalySilverSchema,
    DGHSAgeGroupSilverSchema,
    DGHSDivisionSilverSchema,
    RawAuditSchema,
    SilverPipelineResult,
    SilverSanitizerFirewall,
)
from cleanpulse.silver.spatial_crosswalk import (
    CANONICAL_DIVISIONS,
    DistrictCrosswalkRecord,
    DistrictCrosswalkSilverSchema,
    get_district_by_id,
    get_districts_for_zone,
    load_district_crosswalk,
)
from cleanpulse.silver.timeseries_backfill import (
    ZONE_TARGET_ADMISSIONS,
    ZONE_TARGET_DEATHS,
    EpidemiologicalBackfillGenerator,
)

__all__ = [
    "AuditAnomalySchema",
    "AuditAnomalySilverSchema",
    "CANONICAL_AGE_GROUPS",
    "CANONICAL_DIVISIONS",
    "CANONICAL_ZONES",
    "DGHSAgeGroupSilverSchema",
    "DGHSDivisionSilverSchema",
    "DistrictCrosswalkRecord",
    "DistrictCrosswalkSilverSchema",
    "EpidemiologicalBackfillGenerator",
    "RawAuditSchema",
    "SilverPipelineResult",
    "SilverSanitizerFirewall",
    "ZONE_TARGET_ADMISSIONS",
    "ZONE_TARGET_DEATHS",
    "get_district_by_id",
    "get_districts_for_zone",
    "load_district_crosswalk",
]
