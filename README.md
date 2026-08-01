# NHS A&E Attendance & Performance Analysis
## England | April 2023 – March 2025

An end-to-end data pipeline and analysis project using publicly available NHS England statistics. Built to demonstrate data quality assurance, SQL analysis, Python-based visualisation, and Power BI reporting using real health service data.

---

## Project Overview

NHS England publishes monthly A&E attendance and emergency admissions data at trust level. This project ingests 24 months of that data (April 2023 – March 2025), applies a structured data quality pipeline, analyses performance trends at national and trust level, and presents findings in both Python charts and a Power BI dashboard.

**Data source:** [NHS England A&E Attendances and Emergency Admissions](https://www.england.nhs.uk/statistics/statistical-work-areas/ae-waiting-times-and-activity/)

---

## Key Findings

- England's national average Type 1 A&E 4-hour performance was **58.8%** across the 24-month period — significantly below the **95% NHS target**
- Patients waiting **12+ hours** from Decision to Admit rose from **26,492** in April 2023 to a peak of **61,529** in January 2025 — a worsening patient safety trend
- **Northumbria Healthcare NHS Foundation Trust** averaged **74.4%** 4-hour performance — **15.6 percentage points above the national average**, ranking **6th of the 123 providers** that report Type 1 performance
- Total monthly A&E attendances across England averaged **2.16 million**, remaining broadly stable across both financial years

---

## Repository Structure

```
nhs_ae_project/
├── pipeline.py              # Main data pipeline: ingest, clean, validate, aggregate, chart
├── fix_charts.py            # Chart refinement with proper x-axis labels and annotations
├── sql_queries.py           # 6 SQL analytical queries on the cleaned SQLite database
├── analysis.R               # R validation layer: reproduces headline figures independently
├── charts/
│   ├── chart1_national_attendances.png
│   ├── chart2_4hr_performance.png
│   ├── chart3_northumbria_vs_national.png
│   └── chart4_12hr_waits.png
├── data/
│   ├── raw/                 # 24 monthly CSVs from NHS England (not tracked in Git)
│   └── processed/
│       ├── ae_clean_2023_2025.csv
│       └── ae_national_monthly.csv
└── README.md
```

---

## Pipeline Steps

### 1. Ingestion
- Loads all 24 monthly CSV files from `data/raw/` using `glob`
- Concatenates into a single DataFrame (4,820 rows including totals rows)

### 2. Cleaning
- Removes TOTAL summary rows appended to each monthly file
- Standardises column names and strips whitespace
- Converts all numeric columns with `pd.to_numeric(errors='coerce')`
- Parses period strings (e.g. `MSitAE-APRIL-2023`) into datetime objects
- Standardises trust names and org codes to uppercase

### 3. Data Quality Checks
Five structured checks with documented outputs:

| Check | Finding |
|---|---|
| Missing values in key columns | `type1_4hr_pct`: 1,868 missing (38.9%) — expected, as not all providers have Type 1 departments |
| Negative values | None found |
| Breaches exceeding attendances | None found |
| 4-hour performance outliers (<50%) | 589 trust-months flagged — documented, not removed |
| Performance >100% (impossible) | None found |

### 4. Metric Derivation
- `total_attendances`: sum of Type 1, Type 2, and Other attendances
- `total_over4hr`: sum of all over-4-hour breaches
- `type1_4hr_pct`: `(att_type1 - over4hr_type1) / att_type1 × 100`
- `total_emerg_adm`: total emergency admissions across all types

### 5. Aggregation & Output
- National monthly totals saved to `ae_national_monthly.csv` and SQLite (`ae_national_monthly` table)
- Trust-level clean data saved to `ae_clean_2023_2025.csv` and SQLite (`ae_monthly_trust` table)
- Northumbria-specific subset saved to `ae_northumbria` table

---

## SQL Analysis

Six queries run against the SQLite database (`data/ae_data.db`):

1. **Monthly national trend** — attendances, 4hr performance, gap from target, 12hr waits
2. **Bottom 10 trusts** — by average 4-hour performance (minimum 500 Type 1 attendances, 18+ months reported)
3. **Top 10 trusts** — same criteria, best performers
4. **Northumbria month-by-month** — detailed trust-level performance across all 24 months
5. **Year-on-year comparison** — 2023-24 vs 2024-25 across all key metrics
6. **Regional breakdown** — average 4hr performance by NHS England region

---

## Charts

### Chart 1 — National Monthly A&E Attendances
Monthly total attendances across England, April 2023 to March 2025, with financial year boundary marked.

### Chart 2 — Type 1 4-Hour Performance vs 95% Target
National average performance against the 95% standard, with best/worst months annotated and gap from target shaded.

### Chart 3 — Northumbria vs National Average
Trust-level comparison showing Northumbria Healthcare consistently outperforming the national average, with outperformance area shaded.

### Chart 4 — 12-Hour Waits from Decision to Admit
Monthly counts of patients waiting 12+ hours post-DTA, with trend line showing deterioration over the period.

### Chart 5 — National 4-Hour Performance (R / ggplot2)
The same national performance series rendered independently in R, produced by `analysis.R` as part of the cross-toolchain validation described below.

---

## R Validation Layer

`analysis.R` connects to the same SQLite database via `DBI`/`RSQLite` and independently recomputes every headline figure using `dplyr`, rather than reusing any Python output. It repeats the five data quality checks, recalculates the national mean, the trust ranking and the year-on-year comparison, and renders a `ggplot2` chart of national performance.

The purpose is verification rather than duplication: two independent implementations agreeing on the same numbers is stronger evidence that the figures are right than one implementation on its own. Any divergence between `pipeline.py` and `analysis.R` output signals a defect in one of them.

```bash
Rscript analysis.R
```

Requires `DBI`, `RSQLite`, `dplyr`, `ggplot2` and `scales`. Run `pipeline.py` first to build the database.

---

## Power BI Dashboard

A two-page dashboard built in Power BI Desktop:

**Page 1 — National Overview**
- KPI cards: National average (58.82%), NHS target (95%), Northumbria average (74.4%)
- Line chart: Monthly A&E attendances trend

**Page 2 — Trust Performance**
- Horizontal bar chart: Top 10 trusts by average Type 1 4-hour performance

---

## Tools & Technologies

| Tool | Purpose |
|---|---|
| Python 3 | Pipeline, cleaning, analysis, charting |
| Pandas | Data ingestion, transformation, aggregation |
| Matplotlib | Chart generation |
| SQLite3 | Structured query analysis |
| SQL | Aggregation, ranking, year-on-year comparison |
| R (DBI, RSQLite, dplyr, ggplot2) | Independent validation of headline figures and charting |
| Power BI Desktop | Interactive dashboard |
| Git | Version control |

---

## How to Run

```bash
# 1. Clone the repo
git clone https://github.com/Anon307/nhs-ae-analysis.git
cd nhs-ae-analysis

# 2. Install dependencies
pip3 install pandas matplotlib

# 3. Add raw data
# Download 24 monthly CSVs from NHS England statistics page
# Place in data/raw/

# 4. Run the pipeline
python3 pipeline.py

# 5. Run SQL analysis
python3 sql_queries.py

# 6. Regenerate charts (optional)
python3 fix_charts.py

# 7. Run the R validation layer
Rscript analysis.R
```

---

## Data Notes

- Raw CSV files are not tracked in this repository due to size; download directly from NHS England
- The `type1_4hr_pct` column is null for providers without a Type 1 (major) A&E department — this is expected and documented
- 2 rows with unparseable period strings were dropped during cleaning
- The TOTAL summary row appended to each monthly file is removed before analysis

---

*Data: NHS England Open Data | Analysis: Prem Bdr Shah*
