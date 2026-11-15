# Pre-Registered Analysis Plan: Weekly Climate–Dengue Associations (2022–2024)

**Status:** Pre-registered before any climate-dengue correlation was computed on these datasets.  
**Purpose:** Define the exact data alignment, aggregation, transformations, descriptive statistics, and reporting rules for Phase 2 before any Gold analysis code is written or executed.

---

## 0. Disclosure: What Was Seen Before This Plan
- During source due diligence (`scratch/phase2-sources`, `2026-11-15`) we computed: Dataset A national/per-division annual totals, A-vs-DGHS published annual totals, Dataset B annual totals, A-monthly vs B comparison, A's top-5 daily national maxima per year, and A's national sums on 10 spot dates. No correlation between dengue and any weather variable was computed.
- An earlier version of this repository reported a correlation ($r \approx 0.81$ at a 14-day lag) derived from **simulated** data. It was removed in Phase 1 and is not a hypothesis of this plan.

---

## 1. Data Sources & Scope

### 1.1 Dengue Cases (Primary Historical Series)
- **Source:** Dataset A — Mendeley Data (`z5mvwrfgsz`, v1, DOI `10.17632/z5mvwrfgsz.1`, CC BY 4.0), consisting of 8 division-level daily CSVs covering report dates `2022-01-01` through `2024-12-31`.
- **Mandatory Attribution / Source Label:**  
  `secondary source: transcribed from DGHS daily press releases (unverified transcription by third party)`
- **Columns Used:** Daily case counts only. All weather columns bundled in Dataset A are **dropped** (upstream source unstated and internally inconsistent).
- **Dhaka Division Scope:** It is **inferred** (from national totals matching DGHS published annual figures, rather than verified from an explicit source schema note) that `Dhaka` in Dataset A represents the whole Dhaka division including Dhaka city corporations (DNCC and DSCC).
- **Exclusions:**
  - Dataset B (`cgwjshkx5k`, v2) is used strictly for **reconciliation only** and is excluded from this correlation analysis and from the dashboard.
  - `Transaction receipt.pdf` in Dataset A is excluded from ingestion and analysis.

### 1.2 Climate Series
- **Source:** Open-Meteo Historical Archive API with `models=era5` pinned, for `2022-01-01` through `2024-12-31` across all 64 districts in `data/reference/bd_64_districts_crosswalk.json`.
- **Variables:**
  - `precipitation_sum` (mm/day)
  - `temperature_2m_mean` (°C)
  - `relative_humidity_2m_mean` (%)
- **2026 Weather Exclusion:** Existing `2026` ERA5 Bronze files are retained as immutable history and are **not** used or served in Silver, Gold, or UI for this analysis.

---

## 2. Date Alignment & Weekly Aggregation

### 2.1 Report-Date Alignment
DGHS daily dengue press releases cover the 24-hour window ending at `08:00 Asia/Dhaka` on `report_date`, meaning the majority of each reported 24-hour period falls on the preceding calendar day. Before weekly aggregation, every Dataset A record is assigned to:

$$\text{effective\_date} = \text{report\_date} - 1\text{ day}$$

(Thus `2022-01-01`..`2024-12-31` report dates map to `2021-12-31`..`2024-12-30` effective dates.)

### 2.2 Spatial Scopes (9 Total)
- **8 Canonical Divisions:** `Barishal`, `Chattogram`, `Dhaka`, `Khulna`, `Mymensingh`, `Rajshahi`, `Rangpur`, `Sylhet`.
  - Division daily cases = Dataset A daily case count for that division.
  - Division daily weather = unweighted arithmetic mean across member districts of that division in `data/reference/bd_64_districts_crosswalk.json`.
- **1 National Scope:** `National`.
  - National daily cases = sum of daily cases across all 8 divisions.
  - National daily weather = unweighted arithmetic mean across all 64 districts.

### 2.3 ISO 8601 Weekly Aggregation
- **Week Definition:** ISO 8601 calendar weeks (**Monday–Sunday**), keyed by `(iso_year, iso_week)` and `week_start_date` (Monday).
- **Completeness Rule:** Only **complete 7-day weeks** (7 days present in both `effective_date` cases and ERA5 climate for the scope) are retained. Incomplete edge weeks at the boundaries of the window are **dropped and logged** with their exact dates and day counts.
- **Expected Week Counts (asserted in code; fail loudly if different):**
  - `156` complete ISO weeks from `2022-W01` (Mon `2022-01-03`) to `2024-W52` (Sun `2024-12-29`).
  - Dropped partial boundary weeks: `2021-W52` (`3` days: `2021-12-31`..`2022-01-02`) and `2025-W01` (`1` day: `2024-12-30`).
- **Weekly Aggregations:**
  - `weekly_cases` = sum of daily cases over the 7-day ISO week
  - `weekly_precip_mm` = sum of daily `precipitation_sum` over the 7-day ISO week
  - `weekly_temp_c` = arithmetic mean of daily `temperature_2m_mean` over the 7-day ISO week
  - `weekly_humidity_pct` = arithmetic mean of daily `relative_humidity_2m_mean` over the 7-day ISO week

### 2.4 Data Handling
- No outlier removal, no imputation, and no manual corrections are applied to Dataset A; zero-case weeks are kept as `0`.
- Reconciliation findings (e.g., Dataset A vs published DGHS totals or Dataset B) are reported alongside results and are never applied as adjustments to the case series.

---

## 3. Descriptive Statistic, Transforms, and Lag Grid

### 3.1 Descriptive Statistic (No p-values)
- **Metric:** **Spearman rank correlation ($\rho$)**, computed as the Pearson correlation of ranks with ties assigned average ranks, and reported **strictly as a descriptive statistic**.
- **Undefined / Constant Series:** If either series is constant over the paired sample, $\rho$ is undefined: store `null` with reason `"constant series"`, never `0`.
- **No p-values:** No $p$-values, normal/$t$-approximations, confidence intervals, or significance thresholds will be computed or displayed anywhere. Two reasons require this:
  1. Weekly dengue case counts and weekly meteorological series are **strongly autocorrelated**, violating the independence assumption of standard $p$-value approximations.
  2. Evaluating $9\text{ scopes} \times 3\text{ climate variables} \times 2\text{ transforms} \times 9\text{ lags} = 486$ coefficients constitutes a large multiple-comparisons grid where nominal $p$-values would be misleading.

### 3.2 Two Series Transforms
For each scope and climate variable $X_t$ (at weekly index $t$) and lag $k \in \{0, 1, 2, 3, 4, 5, 6, 7, 8\}$ weeks (climate at $t - k$ paired with cases at $t$):

1. **(i) Raw weekly series:**
   $$\rho\bigl(\text{weekly\_cases}_t,\; X_{t-k}\bigr)$$
2. **(ii) Seasonality-reduced sensitivity series:**
   $$\rho\Bigl(\Delta_1 \log(\text{weekly\_cases}_t + 1),\; \Delta_1 X_{t-k}\Bigr)$$
   where $\Delta_1 y_t = y_t - y_{t-1}$ is the week-over-week first difference. This differenced series **removes slow trends and reduces, but does not remove, seasonal confounding**; it is included strictly as a sensitivity analysis alongside the raw series.

### 3.3 Lag Grid
- All integer lags $k \in \{0, 1, 2, 3, 4, 5, 6, 7, 8\}$ weeks are computed and stored for all 9 scopes, 3 climate variables, and 2 transforms ($486$ total coefficients).
- At lag $k$, pairs are restricted to contiguous weekly indices where both $t$ and $t-k$ (and $t-1, t-k-1$ for differenced series) are present in the complete-week series; the exact sample count $n$ is recorded alongside each $\rho$.
- **Expected Paired Sample Sizes (asserted in code; fail loudly if different):** $n = 156 - k$ (raw series) and $n = 155 - k$ (differenced series).

---

## 4. Reporting Rules, Confounders, and Interpretation Guardrails

1. **Report all lags (0–8):** Every lag from $0$ to $8$ weeks must be reported in full in Gold outputs. The UI lag view will provide a selector for scope (`National` + 8 divisions) and climate variable, displaying the $0$–$8$ week $\rho$ curve for both raw and differenced series (no 486-cell table dump).
2. **No peak-picking:** Do not single out a maximum-$|\rho|$ lag as an "optimal" or "true biological" delay.
3. **No causal language & no qualitative strength labels:** Describe all $\rho$ values strictly as descriptive associations/co-movements; never claim that weather changes *cause* or *drive* case changes from these correlations, and never use qualitative strength labels (`"strong"`, `"weak"`, `"moderate"`, `"significant"`, etc.) anywhere in outputs, docs, or UI.
4. **Known Confounders & Limitations (must accompany results):**
   - **Shared monsoon seasonality:** Both dengue incidence and rainfall/humidity/temperature follow strong annual monsoon cycles in Bangladesh.
   - **Reporting & transcription artifacts:** Weekend/holiday reporting dips, hospital reporting backlogs, and unverified third-party transcription errors in Dataset A.
   - **Outbreak dynamics:** Epidemic autocorrelation, exponential growth/decay phases, susceptible depletion, and vector-control interventions.
   - **Spatial aggregation mismatch:** Division/national weather is an unweighted mean of district ERA5 grid points, whereas dengue hospitalizations are heavily concentrated in dense urban centers (notably Dhaka).
   - **Edge truncation:** Dropping incomplete boundary ISO weeks slightly trims the start/end of the 2022–2024 series.

---

## 5. Amendments
Changes to this plan after its initial commit are appended here with the date and reason; results under the original pre-registered plan remain reported alongside any amended results.
