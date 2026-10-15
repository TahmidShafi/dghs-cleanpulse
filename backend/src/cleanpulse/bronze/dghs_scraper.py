"""Bronze Layer DGHS Dengue Surveillance Scraper & Raw Snapshot Ingestion Module.

Preserves byte-for-byte fidelity of raw DGHS HTML tables, including upstream
anomalies (e.g. Excel serial dates, non-normalized age buckets, row-sum mismatches)
without silent dropping or premature cleaning.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DEFAULT_DGHS_URL = "https://dashboard.dghs.gov.bd/pages/heoc_dengue_v1.php"
DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "dghs_sample_2026_10_14.html"
)
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[4] / "data" / "bronze"


class DGHSBronzeScraper:
    """Scraper and raw snapshot extractor for DGHS Dengue Surveillance portal."""

    def __init__(
        self,
        base_url: str = DEFAULT_DGHS_URL,
        fixture_path: Path | str | None = None,
        timeout: float = 20.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        offline_mode: bool = False,
    ) -> None:
        """Initialize the DGHS Bronze scraper.

        Args:
            base_url: URL to the DGHS dynamic dengue dashboard.
            fixture_path: Path to local HTML fallback fixture.
            timeout: HTTP request timeout in seconds.
            max_retries: Maximum number of HTTP request retries before falling back.
            backoff_factor: Multiplier for exponential backoff sleep.
            offline_mode: If True, bypass live HTTP requests and load local fixture directly.
        """
        self.base_url = base_url
        self.fixture_path = Path(fixture_path) if fixture_path is not None else DEFAULT_FIXTURE_PATH
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.offline_mode = offline_mode

    def compute_sha256(self, content: str) -> str:
        """Compute SHA-256 cryptographic hash of raw HTML content.

        Args:
            content: Raw HTML content string.

        Returns:
            Hex-encoded SHA-256 digest string.
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def fetch_html(self, force_offline: bool = False) -> tuple[str, str, str]:
        """Fetch raw HTML content either via live HTTP request or from local fixture.

        Args:
            force_offline: If True, forces reading from fixture regardless of scraper settings.

        Returns:
            Tuple of (raw_html_content, sha256_hash, source_type).
        """
        if self.offline_mode or force_offline:
            logger.info("Operating in offline mode. Reading from fixture: %s", self.fixture_path)
            content = self._read_fixture()
            return content, self.compute_sha256(content), "fixture"

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
                    verify=False,
                ) as client:
                    response = client.get(self.base_url)
                    response.raise_for_status()
                    html = response.text
                    return html, self.compute_sha256(html), "live"
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_error = exc
                logger.warning(
                    "Attempt %d/%d failed with error: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    sleep_time = self.backoff_factor * (2 ** (attempt - 1))
                    time.sleep(sleep_time)

        logger.warning(
            "Live fetch exhausted %d retries (%s). Falling back to fixture: %s",
            self.max_retries,
            last_error,
            self.fixture_path,
        )
        content = self._read_fixture()
        return content, self.compute_sha256(content), "fixture_fallback"

    def _read_fixture(self) -> str:
        """Read HTML content from the designated local fixture file."""
        if not self.fixture_path.exists():
            raise FileNotFoundError(
                f"DGHS HTML fixture file does not exist at: {self.fixture_path}"
            )
        return self.fixture_path.read_text(encoding="utf-8")

    def parse_dashboard(
        self,
        html_content: str,
        source_hash: str,
        fetch_source: str = "fixture",
    ) -> dict[str, Any]:
        """Parse raw HTML tables using BeautifulSoup (lxml) without altering raw data values.

        Preserves exact strings, numbers, corrupted Excel dates, and unnormalized labels.

        Args:
            html_content: Raw HTML text of the dashboard.
            source_hash: Cryptographic SHA-256 hash of html_content.
            fetch_source: Provenance string ("live", "fixture", "fixture_fallback").

        Returns:
            Dictionary payload representing the raw Bronze snapshot.
        """
        soup = BeautifulSoup(html_content, "lxml")

        # 1. Extract report date metadata
        report_date_raw = ""
        date_elem = soup.find(id="report_date_label")
        if date_elem:
            report_date_raw = date_elem.get_text(strip=True)
        else:
            date_match = re.search(r"Date:\s*([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})", html_content)
            if date_match:
                report_date_raw = date_match.group(0).strip()

        # 2. Extract summary cards if present
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

        # 3. Extract Zone Distribution Table (10 reporting zones)
        zones: list[dict[str, str]] = []
        zone_table = soup.find("table", id="zone_distribution_table")
        if not zone_table:
            # Fallback heuristic: search for table with header containing 'Zone / Division'
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
                    # Expected format: Sl, Zone/Division, Daily Admitted, Daily Deaths,
                    # Total Admitted, Total Deaths, Total Discharged (optional)
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

        # 4. Extract Age Group Distribution Table (preserving corrupted rows verbatim)
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
                    # Columns: Age Group, Male, Female, Total, Deaths (optional)
                    # Note: cols[0].get_text(strip=True) preserves exact string
                    # e.g. "42309", "6-10", ""
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

        scraped_at = datetime.now(UTC).isoformat()
        return {
            "metadata": {
                "source_url": self.base_url,
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

    def save_snapshot(
        self,
        data: dict[str, Any],
        output_dir: Path | str | None = None,
        date_str: str | None = None,
    ) -> Path:
        """Write immutable Bronze JSON snapshot to data/bronze/dghs_raw_YYYY_MM_DD.json.

        Args:
            data: Parsed raw dictionary payload.
            output_dir: Directory where the snapshot will be saved.
            date_str: Optional formatted date string (YYYY_MM_DD). If omitted, inferred from
                      report_date_raw or current UTC date.

        Returns:
            Path of the saved snapshot file.
        """
        target_dir = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
        target_dir.mkdir(parents=True, exist_ok=True)

        if not date_str:
            raw_date = str(data.get("metadata", {}).get("report_date_raw", ""))
            # Try to parse e.g. "14 October 2026" or "14-10-2026"
            date_match = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", raw_date)
            if date_match:
                day, month_str, year = date_match.groups()
                try:
                    dt = datetime.strptime(f"{day} {month_str} {year}", "%d %B %Y")
                    date_str = dt.strftime("%Y_%m_%d")
                except ValueError:
                    date_str = datetime.now(UTC).strftime("%Y_%m_%d")
            else:
                date_str = datetime.now(UTC).strftime("%Y_%m_%d")

        output_path = target_dir / f"dghs_raw_{date_str}.json"

        # Atomic write: write to temp file then rename
        temp_path = target_dir / f".dghs_raw_{date_str}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        temp_path.replace(output_path)
        logger.info("Saved raw Bronze snapshot to: %s", output_path)
        return output_path

    def run_pipeline(
        self,
        force_offline: bool = False,
        output_dir: Path | str | None = None,
    ) -> tuple[dict[str, Any], Path]:
        """Execute end-to-end Bronze extraction: fetch, parse, and persist.

        Args:
            force_offline: If True, bypass live network requests.
            output_dir: Target output directory for raw JSON snapshots.

        Returns:
            Tuple of (parsed_data_dict, saved_snapshot_path).
        """
        html_content, source_hash, fetch_source = self.fetch_html(force_offline=force_offline)
        data = self.parse_dashboard(
            html_content=html_content,
            source_hash=source_hash,
            fetch_source=fetch_source,
        )
        saved_path = self.save_snapshot(data, output_dir=output_dir)
        return data, saved_path
