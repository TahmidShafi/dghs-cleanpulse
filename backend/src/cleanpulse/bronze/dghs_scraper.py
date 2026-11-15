"""Bronze Layer DGHS Dengue Surveillance Scraper & Raw Snapshot Ingestion Module.

Preserves byte-for-byte fidelity of raw DGHS HTML responses in immutable
date-partitioned storage (`data/bronze/dghs/YYYY-MM-DD/<UTC_timestamp>.html`)
with provenance sidecar JSON files. Fails loudly on network, HTTP, or parse
errors without silent fallbacks.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

from cleanpulse.bronze.provenance import (
    ensure_not_in_repo_data,
    write_immutable_with_sidecar,
)

logger = logging.getLogger(__name__)

DEFAULT_DGHS_URL = "https://dashboard.dghs.gov.bd/pages/heoc_dengue_v1.php"
DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "synthetic_dghs_fault_injection.html"
)
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "data" / "bronze" / "dghs"


class DGHSFetchError(RuntimeError):
    """Raised when fetching the live DGHS dashboard fails."""


class DGHSParseError(ValueError):
    """Raised when parsing DGHS HTML extracts 0 zones or 0 age groups."""


class DGHSBronzeScraper:
    """Scraper and raw snapshot extractor for DGHS Dengue Surveillance portal."""

    def __init__(
        self,
        base_url: str = DEFAULT_DGHS_URL,
        fixture_path: Path | str | None = None,
        timeout: float = 20.0,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        offline_mode: bool = False,
    ) -> None:
        """Initialize the DGHS Bronze scraper.

        Args:
            base_url: URL to the DGHS dynamic dengue dashboard.
            fixture_path: Path to synthetic HTML fixture (only for explicit offline mode).
            timeout: HTTP request timeout in seconds.
            max_retries: Maximum number of HTTP attempts on transient errors.
            backoff_factor: Base multiplier for retry sleep (enforced >= 2.0s).
            offline_mode: If True, bypass live HTTP requests and load synthetic fixture.
        """
        self.base_url = base_url
        self.fixture_path = Path(fixture_path) if fixture_path is not None else DEFAULT_FIXTURE_PATH
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.offline_mode = offline_mode

    def compute_sha256(self, content: str | bytes) -> str:
        """Compute SHA-256 cryptographic hash of raw HTML content."""
        raw = content.encode("utf-8") if isinstance(content, str) else content
        return hashlib.sha256(raw).hexdigest()

    def _read_fixture(self) -> bytes:
        """Read raw bytes from the designated synthetic local fixture file."""
        if not self.fixture_path.exists():
            raise FileNotFoundError(
                f"DGHS HTML fixture file does not exist at: {self.fixture_path}"
            )
        return self.fixture_path.read_bytes()

    def fetch_raw(self, force_offline: bool = False) -> tuple[bytes, dict[str, Any]]:
        """Fetch raw HTML bytes either via live HTTPS or explicit offline synthetic fixture.

        Retries ONLY on timeouts, connection errors, and HTTP 5xx responses, with
        at least 2.0 seconds between attempts. Never retries 4xx responses and never
        falls back silently.
        """
        if self.offline_mode or force_offline:
            logger.info(
                "Operating in explicit offline mode. Reading fixture: %s", self.fixture_path
            )
            raw_bytes = self._read_fixture()
            fetched_at = datetime.now(UTC).isoformat()
            return raw_bytes, {
                "url": str(self.fixture_path),
                "http_status": None,
                "fetched_at_utc": fetched_at,
                "fetch_source": "synthetic_fixture",
            }

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "Fetching live HTML from %s (attempt %d/%d)...",
                    self.base_url,
                    attempt,
                    self.max_retries,
                )
                with httpx.Client(
                    timeout=self.timeout,
                    follow_redirects=True,
                    headers=headers,
                    verify=True,
                ) as client:
                    response = client.get(self.base_url)

                status_code = response.status_code
                if 400 <= status_code < 500:
                    raise DGHSFetchError(
                        f"DGHS returned non-retryable client error HTTP {status_code} "
                        f"for {response.url}"
                    )
                if status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"DGHS server error HTTP {status_code}",
                        request=response.request,
                        response=response,
                    )

                fetched_at = datetime.now(UTC).isoformat()
                return response.content, {
                    "url": str(response.url),
                    "http_status": status_code,
                    "fetched_at_utc": fetched_at,
                    "fetch_source": "live",
                }
            except DGHSFetchError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                logger.warning(
                    "Transient DGHS fetch error on attempt %d/%d: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    sleep_time = max(2.0, self.backoff_factor * (2 ** (attempt - 1)))
                    time.sleep(sleep_time)
            except Exception as exc:
                raise DGHSFetchError(f"Unexpected DGHS fetch error: {exc}") from exc

        raise DGHSFetchError(
            f"DGHS live fetch exhausted {self.max_retries} retries: {last_error}"
        ) from last_error

    def save_raw_bronze(
        self,
        raw_bytes: bytes,
        provenance: dict[str, Any],
        output_dir: Path | str | None = None,
    ) -> tuple[Path, Path]:
        """Save unmodified raw HTML bytes and provenance sidecar under YYYY-MM-DD/."""
        target_dir = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
        if provenance.get("fetch_source") == "synthetic_fixture":
            ensure_not_in_repo_data(target_dir)

        fetched_dt = datetime.fromisoformat(str(provenance["fetched_at_utc"]))
        date_folder = fetched_dt.strftime("%Y-%m-%d")
        ts_name = fetched_dt.strftime("%Y%m%dT%H%M%S%fZ")
        html_path = target_dir / date_folder / f"{ts_name}.html"
        return write_immutable_with_sidecar(raw_bytes, html_path, provenance)

    def parse_bronze_file(self, html_path: Path | str) -> dict[str, Any]:
        """Parse a previously saved Bronze HTML file without making network requests."""
        path = Path(html_path)
        raw_bytes = path.read_bytes()
        source_hash = self.compute_sha256(raw_bytes)
        sidecar_path = path.with_suffix(".json")
        fetch_source = "bronze_file"
        source_url = str(path)
        if sidecar_path.exists():
            import json

            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            fetch_source = str(sidecar.get("fetch_source", fetch_source))
            source_url = str(sidecar.get("url", source_url))

        html_content = raw_bytes.decode("utf-8", errors="replace")
        return self.parse_dashboard(
            html_content=html_content,
            source_hash=source_hash,
            fetch_source=fetch_source,
            source_url=source_url,
        )

    def parse_dashboard(
        self,
        html_content: str,
        source_hash: str,
        fetch_source: str = "live",
        source_url: str | None = None,
    ) -> dict[str, Any]:
        """Parse raw HTML tables using BeautifulSoup (lxml) without altering raw values.

        Raises DGHSParseError if 0 zones or 0 age groups are extracted.
        """
        soup = BeautifulSoup(html_content, "lxml")

        report_date_raw = ""
        date_elem = soup.find(id="report_date_label")
        if date_elem:
            report_date_raw = date_elem.get_text(strip=True)
        else:
            date_match = re.search(r"Date:\s*([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})", html_content)
            if date_match:
                report_date_raw = date_match.group(0).strip()

        summary_cards: dict[str, str] = {}
        card_ids = [
            ("daily_admitted", "card_daily_admitted"),
            ("daily_deaths", "card_daily_deaths"),
            ("total_admitted", "card_total_admitted"),
            ("total_deaths", "card_total_deaths"),
        ]
        for key, elem_id in card_ids:
            card_elem = soup.find(id=elem_id)
            if card_elem:
                summary_cards[key] = card_elem.get_text(strip=True)

        zones: list[dict[str, str]] = []
        zone_table = soup.find("table", id="zone_distribution_table")
        if not zone_table:
            for tbl in soup.find_all("table"):
                if "Zone / Division" in tbl.get_text():
                    zone_table = tbl
                    break

        if zone_table:
            tbody = zone_table.find("tbody")
            rows = tbody.find_all("tr") if tbody else zone_table.find_all("tr")[1:]
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 6:
                    sl_val = cols[0].get_text(strip=True)
                    zone_name = cols[1].get_text(strip=True)
                    if zone_name.lower() == "total":
                        continue
                    zones.append(
                        {
                            "sl": sl_val,
                            "zone_name": zone_name,
                            "daily_admitted": cols[2].get_text(strip=True),
                            "daily_deaths": cols[3].get_text(strip=True),
                            "total_admitted": cols[4].get_text(strip=True),
                            "total_deaths": cols[5].get_text(strip=True),
                            "total_discharged": (
                                cols[6].get_text(strip=True) if len(cols) > 6 else ""
                            ),
                        }
                    )

        age_groups: list[dict[str, str]] = []
        age_table = soup.find("table", id="age_distribution_table")
        if not age_table:
            for tbl in soup.find_all("table"):
                if "Age Group" in tbl.get_text():
                    age_table = tbl
                    break

        if age_table:
            tbody = age_table.find("tbody")
            rows = tbody.find_all("tr") if tbody else age_table.find_all("tr")[1:]
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 4:
                    age_group_label = cols[0].get_text(strip=True)
                    male_val = cols[1].get_text(strip=True)
                    female_val = cols[2].get_text(strip=True)
                    total_val = cols[3].get_text(strip=True)
                    deaths_val = cols[4].get_text(strip=True) if len(cols) > 4 else "0"

                    if age_group_label.lower() == "total":
                        continue

                    age_groups.append(
                        {
                            "age_group": age_group_label,
                            "male": male_val,
                            "female": female_val,
                            "total": total_val,
                            "deaths": deaths_val,
                        }
                    )

        if len(zones) == 0 or len(age_groups) == 0:
            raise DGHSParseError(
                f"DGHS HTML parse failed: extracted {len(zones)} zones and "
                f"{len(age_groups)} age groups (source={fetch_source})."
            )

        scraped_at = datetime.now(UTC).isoformat()
        return {
            "metadata": {
                "source_url": source_url or self.base_url,
                "source_hash": source_hash,
                "scraped_at_utc": scraped_at,
                "report_date_raw": report_date_raw,
                "fetch_source": fetch_source,
                "total_zones_extracted": len(zones),
                "total_age_groups_extracted": len(age_groups),
            },
            "summary_cards": summary_cards,
            "zones": zones,
            "age_groups": age_groups,
            "raw_html_length": len(html_content),
        }

    def run_pipeline(
        self,
        force_offline: bool = False,
        output_dir: Path | str | None = None,
    ) -> tuple[dict[str, Any], Path]:
        """Execute Bronze extraction: fetch raw, save immutable bronze, parse from bronze."""
        raw_bytes, provenance = self.fetch_raw(force_offline=force_offline)
        html_path, _sidecar_path = self.save_raw_bronze(
            raw_bytes=raw_bytes,
            provenance=provenance,
            output_dir=output_dir,
        )
        data = self.parse_bronze_file(html_path)
        return data, html_path
