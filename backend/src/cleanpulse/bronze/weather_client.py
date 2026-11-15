"""Open-Meteo Historical Archive Batch Client & Weather Daily Silver Module.

Fetches daily climate data (temperature_2m_mean, precipitation_sum,
relative_humidity_2m_mean) for all 64 districts of Bangladesh from the
Open-Meteo Historical Archive API, stores raw API JSON responses in immutable
Bronze storage with provenance sidecars, and builds the Pandera-validated
Silver Parquet table from those Bronze files.
"""

from __future__ import annotations

import json
import logging
import math
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pandas as pd  # type: ignore[import-untyped]
import pandera.pandas as pa

from cleanpulse.bronze.provenance import write_immutable_with_sidecar
from cleanpulse.silver.spatial_crosswalk import load_district_crosswalk

logger = logging.getLogger(__name__)

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_BRONZE_WEATHER_DIR = REPO_ROOT / "data" / "bronze" / "weather"
DEFAULT_SILVER_WEATHER_PARQUET = REPO_ROOT / "data" / "silver" / "weather_districts_daily.parquet"

DEFAULT_START_DATE = "2026-04-18"
DEFAULT_END_DATE = "2026-10-14"


class WeatherFetchError(RuntimeError):
    """Raised when fetching live Open-Meteo archive data fails."""


# ---------------------------------------------------------------------------
# Pandera Silver Validation Schema
# ---------------------------------------------------------------------------
WeatherDailySilverSchema = pa.DataFrameSchema(
    columns={
        "date": pa.Column(str, nullable=False),
        "district_id": pa.Column(str, nullable=False),
        "district_name": pa.Column(str, nullable=False),
        "dghs_reporting_zone": pa.Column(
            str,
            nullable=False,
        ),
        "temperature_2m_mean": pa.Column(
            float,
            pa.Check.in_range(-5.0, 55.0),
            nullable=False,
        ),
        "precipitation_sum": pa.Column(
            float,
            pa.Check.ge(0.0),
            nullable=False,
        ),
        "relative_humidity_2m_mean": pa.Column(
            float,
            pa.Check.in_range(0.0, 100.0),
            nullable=False,
        ),
    },
    strict=True,
    coerce=True,
)


class OpenMeteoWeatherClient:
    """Client for retrieving, archiving, and validating daily climate time series."""

    def __init__(
        self,
        base_url: str = OPEN_METEO_ARCHIVE_URL,
        timeout_seconds: float = 20.0,
        max_retries: int = 3,
        batch_size: int = 16,
    ) -> None:
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.batch_size = batch_size

    @staticmethod
    def generate_dates(start_date: str, end_date: str) -> list[str]:
        """Generate contiguous ISO date strings between start_date and end_date inclusive."""
        d_start = date.fromisoformat(start_date)
        d_end = date.fromisoformat(end_date)
        days = (d_end - d_start).days + 1
        return [(d_start + timedelta(days=i)).isoformat() for i in range(days)]

    def _fetch_batch_raw(
        self,
        batch_districts: list[dict[str, Any]],
        start_date: str,
        end_date: str,
    ) -> tuple[bytes, dict[str, Any]]:
        """Fetch raw Open-Meteo JSON bytes for a coordinate batch. Fails loudly."""
        lats = ",".join(str(d["latitude"]) for d in batch_districts)
        lons = ",".join(str(d["longitude"]) for d in batch_districts)

        params: dict[str, str] = {
            "latitude": lats,
            "longitude": lons,
            "start_date": start_date,
            "end_date": end_date,
            "daily": "temperature_2m_mean,precipitation_sum,relative_humidity_2m_mean",
            "timezone": "Asia/Dhaka",
            "models": "era5",
        }

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = httpx.get(
                    self.base_url,
                    params=params,
                    timeout=self.timeout_seconds,
                )
                if 400 <= resp.status_code < 500:
                    raise WeatherFetchError(
                        f"Open-Meteo returned non-retryable HTTP {resp.status_code}: "
                        f"{resp.text[:200]}"
                    )
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"Open-Meteo HTTP {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )

                # Validate JSON structure before archiving
                parsed = resp.json()
                if not isinstance(parsed, (dict, list)):
                    raise WeatherFetchError(f"Unexpected Open-Meteo payload type: {type(parsed)}")

                fetched_at = datetime.now(UTC).isoformat()
                return resp.content, {
                    "url": str(resp.url),
                    "models": params["models"],
                    "request_params": params,
                    "district_ids": [str(d["district_id"]) for d in batch_districts],
                    "http_status": resp.status_code,
                    "fetched_at_utc": fetched_at,
                    "fetch_source": "live",
                }
            except WeatherFetchError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                logger.warning(
                    "Transient Open-Meteo error on attempt %d/%d: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(2.0 * (2 ** (attempt - 1)))
            except Exception as exc:
                raise WeatherFetchError(f"Unexpected Open-Meteo error: {exc}") from exc

        raise WeatherFetchError(
            f"Failed to fetch climate batch after {self.max_retries} attempts: {last_error}"
        ) from last_error

    def ingest_bronze_batches(
        self,
        crosswalk_df: pd.DataFrame | None = None,
        start_date: str = DEFAULT_START_DATE,
        end_date: str = DEFAULT_END_DATE,
        bronze_dir: Path | str | None = None,
    ) -> list[Path]:
        """Fetch all 64-district batches from Open-Meteo and save immutable Bronze files.

        Fetches all batches first before writing to Bronze so a mid-run batch failure
        does not leave partial batch sets, or raises WeatherFetchError immediately.
        """
        cw = crosswalk_df if crosswalk_df is not None else load_district_crosswalk()
        districts: list[dict[str, Any]] = cw.to_dict(orient="records")
        target_bronze = Path(bronze_dir) if bronze_dir is not None else DEFAULT_BRONZE_WEATHER_DIR

        fetched_batches: list[tuple[bytes, dict[str, Any], int]] = []
        for batch_idx, i in enumerate(range(0, len(districts), self.batch_size)):
            batch = districts[i : i + self.batch_size]
            raw_bytes, provenance = self._fetch_batch_raw(batch, start_date, end_date)
            fetched_batches.append((raw_bytes, provenance, batch_idx))

        saved_paths: list[Path] = []
        for raw_bytes, provenance, batch_idx in fetched_batches:
            fetched_dt = datetime.fromisoformat(str(provenance["fetched_at_utc"]))
            date_folder = fetched_dt.strftime("%Y-%m-%d")
            ts_name = fetched_dt.strftime("%Y%m%dT%H%M%S%fZ")
            raw_path = target_bronze / date_folder / f"{ts_name}_batch_{batch_idx:02d}.json"
            saved_raw, _saved_sidecar = write_immutable_with_sidecar(
                raw_bytes=raw_bytes,
                target_path=raw_path,
                sidecar_metadata=provenance,
            )
            saved_paths.append(saved_raw)

        logger.info("Archived %d Open-Meteo Bronze batches to %s", len(saved_paths), target_bronze)
        return saved_paths

    def build_silver_from_bronze(
        self,
        bronze_paths: list[Path],
        crosswalk_df: pd.DataFrame | None = None,
        output_parquet: Path | str | None = DEFAULT_SILVER_WEATHER_PARQUET,
    ) -> pd.DataFrame:
        """Build validated Silver weather Parquet strictly from archived Bronze JSON files."""
        if not bronze_paths:
            raise ValueError("No Bronze weather files provided to build Silver table.")

        cw = crosswalk_df if crosswalk_df is not None else load_district_crosswalk()
        districts_by_id: dict[str, dict[str, Any]] = {
            str(rec["district_id"]): rec for rec in cw.to_dict(orient="records")
        }

        all_records: list[dict[str, Any]] = []
        for raw_path in sorted(bronze_paths):
            payload = json.loads(raw_path.read_text(encoding="utf-8"))
            batch_responses = [payload] if isinstance(payload, dict) else payload

            sidecar_path = raw_path.with_name(f"{raw_path.stem}.sidecar.json")
            if not sidecar_path.exists():
                raise FileNotFoundError(f"Missing provenance sidecar for Bronze file: {raw_path}")
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            batch_district_ids: list[str] = [str(did) for did in sidecar["district_ids"]]

            if len(batch_responses) != len(batch_district_ids):
                raise ValueError(
                    f"Batch response count ({len(batch_responses)}) does not match "
                    f"district count ({len(batch_district_ids)}) in {raw_path}"
                )

            for dist_id, resp_data in zip(batch_district_ids, batch_responses, strict=True):
                dist_meta = districts_by_id[dist_id]
                daily = resp_data.get("daily", {})
                times = daily.get("time", [])
                temps = daily.get("temperature_2m_mean", [])
                precips = daily.get("precipitation_sum", [])
                humidities = daily.get("relative_humidity_2m_mean", [])

                for day_str, t_val, p_val, h_val in zip(
                    times, temps, precips, humidities, strict=True
                ):
                    if (
                        t_val is None
                        or p_val is None
                        or h_val is None
                        or math.isnan(float(t_val))
                        or math.isnan(float(p_val))
                        or math.isnan(float(h_val))
                    ):
                        raise ValueError(
                            f"Missing/NaN Open-Meteo value for {dist_id} on {day_str} in {raw_path}"
                        )

                    all_records.append(
                        {
                            "date": str(day_str),
                            "district_id": dist_meta["district_id"],
                            "district_name": dist_meta["district_name"],
                            "dghs_reporting_zone": dist_meta["dghs_reporting_zone"],
                            "temperature_2m_mean": round(float(t_val), 1),
                            "precipitation_sum": round(max(float(p_val), 0.0), 1),
                            "relative_humidity_2m_mean": round(
                                min(max(float(h_val), 0.0), 100.0), 1
                            ),
                        }
                    )

        df_online = pd.DataFrame(all_records)
        df_result = WeatherDailySilverSchema.validate(df_online, lazy=True)

        if output_parquet is not None:
            out_path = Path(output_parquet)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = out_path.with_suffix(".parquet.tmp")
            df_result.to_parquet(tmp_path, index=False)
            tmp_path.replace(out_path)
            logger.info("Exported %d weather rows to %s", len(df_result), out_path)

        return df_result

    def fetch_climate_data(
        self,
        crosswalk_df: pd.DataFrame | None = None,
        start_date: str = DEFAULT_START_DATE,
        end_date: str = DEFAULT_END_DATE,
        bronze_dir: Path | str | None = None,
        output_parquet: Path | str | None = DEFAULT_SILVER_WEATHER_PARQUET,
    ) -> pd.DataFrame:
        """Fetch live Open-Meteo batches into Bronze, then build Silver from Bronze."""
        cw = crosswalk_df if crosswalk_df is not None else load_district_crosswalk()
        bronze_paths = self.ingest_bronze_batches(
            crosswalk_df=cw,
            start_date=start_date,
            end_date=end_date,
            bronze_dir=bronze_dir,
        )
        return self.build_silver_from_bronze(
            bronze_paths=bronze_paths,
            crosswalk_df=cw,
            output_parquet=output_parquet,
        )
