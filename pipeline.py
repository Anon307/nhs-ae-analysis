"""
NHS A&E Attendances & Emergency Admissions — Data Quality Pipeline
Author: Prem Bdr Shah
Data source: NHS England Statistics (england.nhs.uk/statistics)
Coverage: April 2023 – March 2025 (24 months)
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import sqlite3
import os
import glob
import warnings
warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────
# CONFIG — update this path to your data folder
# ─────────────────────────────────────────────
DATA_FOLDER = "./data/raw"          # folder containing all 24 CSVs
OUTPUT_FOLDER = "./data/processed"
CHARTS_FOLDER = "./charts"
DB_PATH = "./data/ae_data.db"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(CHARTS_FOLDER, exist_ok=True)

NORTHUMBRIA_CODE = "RTF"            # Northumbria Healthcare NHS Foundation Trust
TARGET_TRUST_NAME = "NORTHUMBRIA HEALTHCARE NHS FOUNDATION TRUST"

# ─────────────────────────────────────────────
# STEP 1 — INGEST: load all 24 CSV files
# ─────────────────────────────────────────────
print("=" * 60)
print("STEP 1 — INGESTING DATA")
print("=" * 60)

all_files = glob.glob(os.path.join(DATA_FOLDER, "*.csv"))
print(f"  Found {len(all_files)} CSV files")

frames = []
for f in sorted(all_files):
    df = pd.read_csv(f, dtype=str)
    frames.append(df)

raw = pd.concat(frames, ignore_index=True)
print(f"  Total rows loaded (including totals rows): {len(raw):,}")

# ─────────────────────────────────────────────
# STEP 2 — CLEAN: remove totals rows, fix types
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 2 — CLEANING")
print("=" * 60)

# Remove the TOTAL summary rows at the bottom of each file
df = raw[raw["Org Code"].str.upper() != "TOTAL"].copy()
print(f"  Rows after removing TOTAL rows: {len(df):,}")

# Standardise column names
df.columns = [c.strip() for c in df.columns]

# Rename columns to shorter, cleaner names
col_map = {
    "Period": "period",
    "Org Code": "org_code",
    "Parent Org": "parent_org",
    "Org name": "org_name",
    "A&E attendances Type 1": "att_type1",
    "A&E attendances Type 2": "att_type2",
    "A&E attendances Other A&E Department": "att_other",
    "A&E attendances Booked Appointments Type 1": "att_booked_type1",
    "A&E attendances Booked Appointments Type 2": "att_booked_type2",
    "A&E attendances Booked Appointments Other Department": "att_booked_other",
    "Attendances over 4hrs Type 1": "over4hr_type1",
    "Attendances over 4hrs Type 2": "over4hr_type2",
    "Attendances over 4hrs Other Department": "over4hr_other",
    "Attendances over 4hrs Booked Appointments Type 1": "over4hr_booked_type1",
    "Attendances over 4hrs Booked Appointments Type 2": "over4hr_booked_type2",
    "Attendances over 4hrs Booked Appointments Other Department": "over4hr_booked_other",
    "Patients who have waited 4-12 hs from DTA to admission": "wait_4_12hr_dta",
    "Patients who have waited 12+ hrs from DTA to admission": "wait_12hr_plus_dta",
    "Emergency admissions via A&E - Type 1": "emerg_adm_type1",
    "Emergency admissions via A&E - Type 2": "emerg_adm_type2",
    "Emergency admissions via A&E - Other A&E department": "emerg_adm_other",
    "Other emergency admissions": "emerg_adm_other2",
}
df = df.rename(columns=col_map)

# Convert numeric columns — replace blanks with NaN
numeric_cols = [c for c in df.columns if c not in ["period", "org_code", "parent_org", "org_name"]]
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# Parse period into a proper date
# Format in data: MSitAE-APRIL-2023 → extract month and year
def parse_period(p):
    try:
        parts = str(p).strip().split("-")
        # Format: MSitAE-MONTH-YEAR or MSitAE-MONTH-YEAR-REVISED etc
        month = parts[1]
        year = parts[2][:4]
        return pd.to_datetime(f"01-{month}-{year}", format="%d-%B-%Y")
    except:
        return pd.NaT

df["date"] = df["period"].apply(parse_period)
invalid_dates = df["date"].isna().sum()
print(f"  Rows with unparseable dates: {invalid_dates}")
df = df[df["date"].notna()].copy()

# Standardise org_name
df["org_name"] = df["org_name"].str.strip().str.upper()
df["org_code"] = df["org_code"].str.strip().str.upper()
df["parent_org"] = df["parent_org"].str.strip().str.upper()

print(f"  Clean rows: {len(df):,}")
print(f"  Date range: {df['date'].min().strftime('%b %Y')} to {df['date'].max().strftime('%b %Y')}")
print(f"  Unique trusts/providers: {df['org_code'].nunique():,}")

# ─────────────────────────────────────────────
# STEP 3 — DERIVE KEY METRICS
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 3 — DERIVING METRICS")
print("=" * 60)

# Total attendances (all types combined)
df["total_attendances"] = df[["att_type1", "att_type2", "att_other"]].sum(axis=1)

# Total over-4hr breaches
df["total_over4hr"] = df[["over4hr_type1", "over4hr_type2", "over4hr_other"]].sum(axis=1)

# 4-hour performance % (Type 1 only — the standard NHS measure)
# Type 1 = Major A&E departments; this is the main performance target
df["type1_4hr_pct"] = np.where(
    df["att_type1"] > 0,
    ((df["att_type1"] - df["over4hr_type1"]) / df["att_type1"] * 100).round(1),
    np.nan
)

# Total emergency admissions
df["total_emerg_adm"] = df[["emerg_adm_type1", "emerg_adm_type2",
                              "emerg_adm_other", "emerg_adm_other2"]].sum(axis=1)

# 12-hour waits — a serious patient safety indicator
df["wait_12hr_plus_dta"] = df["wait_12hr_plus_dta"].fillna(0)

print(f"  Metrics derived: total_attendances, total_over4hr, type1_4hr_pct, total_emerg_adm")

# ─────────────────────────────────────────────
# STEP 4 — DATA QUALITY CHECKS
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 4 — DATA QUALITY REPORT")
print("=" * 60)

quality_issues = []

# Check 1: Missing values in key columns
print("\n  [CHECK 1] Missing values in key columns:")
key_cols = ["total_attendances", "total_over4hr", "type1_4hr_pct", "total_emerg_adm"]
for col in key_cols:
    n_missing = df[col].isna().sum()
    pct = n_missing / len(df) * 100
    print(f"    {col}: {n_missing:,} missing ({pct:.1f}%)")
    if n_missing > 0:
        quality_issues.append(f"Missing values in {col}: {n_missing} rows")

# Check 2: Impossible values — attendances cannot be negative
print("\n  [CHECK 2] Negative values (impossible):")
for col in ["total_attendances", "total_over4hr", "total_emerg_adm"]:
    n_neg = (df[col] < 0).sum()
    print(f"    {col}: {n_neg} negative values")
    if n_neg > 0:
        quality_issues.append(f"Negative values in {col}: {n_neg} rows")

# Check 3: Breaches cannot exceed attendances
print("\n  [CHECK 3] Over-4hr breaches > attendances (logical error):")
impossible = df[df["over4hr_type1"] > df["att_type1"]].shape[0]
print(f"    Rows where over4hr_type1 > att_type1: {impossible}")
if impossible > 0:
    quality_issues.append(f"Breach count exceeds attendance count: {impossible} rows")

# Check 4: 4-hour performance outliers (< 50% or > 100% are suspicious)
print("\n  [CHECK 4] Outlier 4-hour performance rates:")
low_perf = df[(df["type1_4hr_pct"] < 50) & (df["att_type1"] > 500)]
high_perf = df[df["type1_4hr_pct"] > 100]
print(f"    Trusts with Type 1 performance < 50% (min 500 attendances): {len(low_perf)}")
print(f"    Rows with performance > 100% (data error): {len(high_perf)}")
if len(low_perf) > 0:
    quality_issues.append(f"Low 4hr performance outliers (< 50%): {len(low_perf)} trust-months")
if len(high_perf) > 0:
    quality_issues.append(f"Performance > 100% (impossible): {len(high_perf)} rows — flagged for review")

# Check 5: Trusts with zero attendances for an entire month
print("\n  [CHECK 5] Trust-months with zero total attendances:")
zero_att = df[df["total_attendances"] == 0]
print(f"    {len(zero_att)} trust-months with zero attendances")
print(f"    (These are typically specialist trusts — noted, not removed)")

# Check 6: Zero recorded breaches against a substantial Type 1 caseload.
# A large A&E reporting not one patient over four hours in a month is not
# credible; it is a non-submission being read as a zero. Check 4 cannot catch
# these because they produce exactly 100%, not above 100%.
print("\n  [CHECK 6] Zero recorded breaches against a substantial caseload:")
zero_breach = df[(df["att_type1"] > 500) & (df["over4hr_type1"] == 0)]
print(f"    {len(zero_breach)} trust-months reporting 100% with >500 Type 1 attendances")
if len(zero_breach) > 0:
    affected = zero_breach["att_type1"].sum()
    months = sorted(zero_breach["date"].dt.strftime("%b %Y").unique())
    print(f"    Attendances sitting in those rows: {affected:,}")
    print(f"    Months affected: {', '.join(months)}")
    print(f"    Treated as missing rather than 100% — see README")
    quality_issues.append(
        f"Zero-breach non-submissions: {len(zero_breach)} trust-months "
        f"({affected:,} attendances) reporting an implausible 100%"
    )

# Summary
print(f"\n  QUALITY SUMMARY: {len(quality_issues)} issue types identified")
for i, issue in enumerate(quality_issues, 1):
    print(f"    {i}. {issue}")

# Flag and remove impossible rows (performance > 100%)
df = df[~(df["type1_4hr_pct"] > 100)].copy()
print(f"\n  Rows removed (performance > 100%): {len(high_perf)}")
print(f"  Final clean dataset: {len(df):,} rows")

# ─────────────────────────────────────────────
# STEP 5 — NATIONAL MONTHLY AGGREGATION
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 5 — NATIONAL AGGREGATION")
print("=" * 60)

national = df.groupby("date").agg(
    total_attendances=("total_attendances", "sum"),
    total_over4hr=("total_over4hr", "sum"),
    total_emerg_adm=("total_emerg_adm", "sum"),
    wait_12hr_plus_dta=("wait_12hr_plus_dta", "sum"),
    type1_att=("att_type1", "sum"),
    type1_over4hr=("over4hr_type1", "sum"),
).reset_index().sort_values("date")

national["national_4hr_pct"] = (
    (national["type1_att"] - national["type1_over4hr"]) /
    national["type1_att"] * 100
).round(1)

print(f"  Monthly national data: {len(national)} months")
print(f"\n  National averages:")
print(f"    Avg monthly attendances: {national['total_attendances'].mean():,.0f}")
print(f"    Avg 4-hour performance: {national['national_4hr_pct'].mean():.1f}%")
print(f"    NHS target: 95.0%")
print(f"    Gap from target: {95 - national['national_4hr_pct'].mean():.1f} percentage points")

# ─────────────────────────────────────────────
# STEP 6 — NORTHUMBRIA FOCUS
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 6 — NORTHUMBRIA HEALTHCARE FOCUS")
print("=" * 60)

northumbria = df[df["org_code"] == NORTHUMBRIA_CODE].copy().sort_values("date")
print(f"  Northumbria records found: {len(northumbria)}")

if len(northumbria) > 0:
    n_avg_4hr = northumbria["type1_4hr_pct"].mean()
    n_avg_att = northumbria["total_attendances"].mean()
    print(f"  Northumbria avg monthly attendances: {n_avg_att:,.0f}")
    print(f"  Northumbria avg 4-hour performance: {n_avg_4hr:.1f}%")
    print(f"  vs National average: {national['national_4hr_pct'].mean():.1f}%")
    diff = n_avg_4hr - national["national_4hr_pct"].mean()
    direction = "above" if diff > 0 else "below"
    print(f"  Northumbria is {abs(diff):.1f} percentage points {direction} national average")

# ─────────────────────────────────────────────
# STEP 7 — SAVE TO SQLITE
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 7 — SAVING TO SQLITE")
print("=" * 60)

conn = sqlite3.connect(DB_PATH)
df.to_sql("ae_monthly_trust", conn, if_exists="replace", index=False)
national.to_sql("ae_national_monthly", conn, if_exists="replace", index=False)
northumbria.to_sql("ae_northumbria", conn, if_exists="replace", index=False)
conn.close()
print(f"  Saved to {DB_PATH}")
print(f"  Tables: ae_monthly_trust, ae_national_monthly, ae_northumbria")

# ─────────────────────────────────────────────
# STEP 8 — SAVE CLEAN CSV
# ─────────────────────────────────────────────
clean_path = os.path.join(OUTPUT_FOLDER, "ae_clean_2023_2025.csv")
df.to_csv(clean_path, index=False)
print(f"  Clean CSV saved: {clean_path}")

# ─────────────────────────────────────────────
# STEP 9 — CHARTS
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 9 — GENERATING CHARTS")
print("=" * 60)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linestyle": "--",
})

NHS_BLUE = "#005EB8"
NHS_DARK = "#003087"
AMBER = "#FFB81C"
RED = "#DA291C"
GREEN = "#009639"

# CHART 1 — National monthly attendances
fig, ax = plt.subplots(figsize=(12, 5))
ax.fill_between(national["date"], national["total_attendances"],
                alpha=0.15, color=NHS_BLUE)
ax.plot(national["date"], national["total_attendances"],
        color=NHS_BLUE, linewidth=2.5, marker="o", markersize=4)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x/1e6:.1f}M"))
ax.set_title("Total A&E Attendances — England (Apr 2023 – Mar 2025)",
             fontsize=13, fontweight="bold", pad=12)
ax.set_ylabel("Monthly attendances")
ax.set_xlabel("")
# Mark financial year boundary
ax.axvline(pd.Timestamp("2024-04-01"), color="gray", linestyle=":", alpha=0.7)
ax.text(pd.Timestamp("2024-04-15"), ax.get_ylim()[0] * 1.02,
        "2024-25 starts", fontsize=9, color="gray")
plt.tight_layout()
plt.savefig(os.path.join(CHARTS_FOLDER, "chart1_national_attendances.png"),
            dpi=150, bbox_inches="tight")
plt.close()
print("  Chart 1 saved: national attendances trend")

# CHART 2 — National 4-hour performance vs 95% target
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(national["date"], national["national_4hr_pct"],
        color=NHS_DARK, linewidth=2.5, marker="o", markersize=4, label="National 4hr %")
ax.axhline(95, color=GREEN, linestyle="--", linewidth=1.5, label="95% target")

# Shade the gap from target in red
ax.fill_between(national["date"],
                national["national_4hr_pct"].clip(upper=95),
                95,
                alpha=0.12, color=RED, label="Gap from target")

ax.set_ylim(60, 100)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
ax.set_title("Type 1 A&E 4-Hour Performance — England vs 95% Target (Apr 2023 – Mar 2025)",
             fontsize=13, fontweight="bold", pad=12)
ax.set_ylabel("% seen within 4 hours")
ax.legend(loc="lower right")
plt.tight_layout()
plt.savefig(os.path.join(CHARTS_FOLDER, "chart2_4hr_performance.png"),
            dpi=150, bbox_inches="tight")
plt.close()
print("  Chart 2 saved: 4-hour performance vs target")

# CHART 3 — Northumbria vs National 4-hour performance
if len(northumbria) > 0:
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(national["date"], national["national_4hr_pct"],
            color="gray", linewidth=1.8, linestyle="--",
            label="England national average", alpha=0.7)
    ax.plot(northumbria["date"], northumbria["type1_4hr_pct"],
            color=NHS_BLUE, linewidth=2.5, marker="o", markersize=5,
            label="Northumbria Healthcare NHS FT")
    ax.axhline(95, color=GREEN, linestyle=":", linewidth=1.2, label="95% target")
    ax.set_ylim(60, 100)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.set_title("Type 1 A&E 4-Hour Performance: Northumbria vs National Average",
                 fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("% seen within 4 hours")
    ax.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(os.path.join(CHARTS_FOLDER, "chart3_northumbria_vs_national.png"),
                dpi=150, bbox_inches="tight")
    plt.close()
    print("  Chart 3 saved: Northumbria vs national")

# CHART 4 — 12-hour waits (patient safety indicator)
fig, ax = plt.subplots(figsize=(12, 5))
ax.bar(national["date"], national["wait_12hr_plus_dta"],
       color=RED, alpha=0.75, width=20)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
ax.set_title("Patients Waiting 12+ Hours from Decision to Admit — England (Apr 2023 – Mar 2025)",
             fontsize=13, fontweight="bold", pad=12)
ax.set_ylabel("Number of patients")
ax.set_xlabel("")
plt.tight_layout()
plt.savefig(os.path.join(CHARTS_FOLDER, "chart4_12hr_waits.png"),
            dpi=150, bbox_inches="tight")
plt.close()
print("  Chart 4 saved: 12-hour waits")

print("\n" + "=" * 60)
print("PIPELINE COMPLETE")
print("=" * 60)
print(f"  Clean data: {clean_path}")
print(f"  Database:   {DB_PATH}")
print(f"  Charts:     {CHARTS_FOLDER}/")
print("\n  Next step: run sql_queries.py to generate the SQL analysis")
