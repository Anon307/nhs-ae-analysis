"""
NHS A&E Data — SQL Analysis Queries
Run this AFTER pipeline.py has created ae_data.db
"""

import sqlite3
import pandas as pd

DB_PATH = "./data/ae_data.db"
conn = sqlite3.connect(DB_PATH)

print("=" * 60)
print("SQL ANALYSIS — NHS A&E DATA")
print("=" * 60)

# QUERY 1 — Monthly national trend
print("\n[QUERY 1] National monthly attendances and performance")
q1 = pd.read_sql("""
    SELECT
        strftime('%b %Y', date) AS month,
        ROUND(total_attendances / 1000000.0, 2) AS attendances_millions,
        ROUND(national_4hr_pct, 1) AS pct_within_4hr,
        ROUND(95 - national_4hr_pct, 1) AS gap_from_target,
        wait_12hr_plus_dta AS twelve_hr_waits
    FROM ae_national_monthly
    ORDER BY date
""", conn)
print(q1.to_string(index=False))

# QUERY 2 — Worst performing trusts (avg 4hr performance over 24 months)
print("\n[QUERY 2] Bottom 10 trusts by average 4-hour performance")
q2 = pd.read_sql("""
    SELECT
        org_name,
        parent_org AS region,
        COUNT(*) AS months_reported,
        ROUND(AVG(type1_4hr_pct), 1) AS avg_4hr_pct,
        ROUND(MIN(type1_4hr_pct), 1) AS worst_month_pct,
        ROUND(SUM(att_type1)) AS total_type1_att
    FROM ae_monthly_trust
    WHERE att_type1 >= 500
      AND type1_4hr_pct IS NOT NULL
    GROUP BY org_code, org_name, parent_org
    HAVING months_reported >= 18
    ORDER BY avg_4hr_pct ASC
    LIMIT 10
""", conn)
print(q2.to_string(index=False))

# QUERY 3 — Best performing trusts
print("\n[QUERY 3] Top 10 trusts by average 4-hour performance")
q3 = pd.read_sql("""
    SELECT
        org_name,
        parent_org AS region,
        COUNT(*) AS months_reported,
        ROUND(AVG(type1_4hr_pct), 1) AS avg_4hr_pct,
        ROUND(SUM(att_type1)) AS total_type1_att
    FROM ae_monthly_trust
    WHERE att_type1 >= 500
      AND type1_4hr_pct IS NOT NULL
    GROUP BY org_code, org_name, parent_org
    HAVING months_reported >= 18
    ORDER BY avg_4hr_pct DESC
    LIMIT 10
""", conn)
print(q3.to_string(index=False))

# QUERY 4 — Northumbria detailed performance
print("\n[QUERY 4] Northumbria Healthcare — month by month")
q4 = pd.read_sql("""
    SELECT
        strftime('%b %Y', date) AS month,
        total_attendances,
        att_type1 AS type1_attendances,
        ROUND(type1_4hr_pct, 1) AS pct_4hr,
        wait_12hr_plus_dta AS twelve_hr_waits,
        total_emerg_adm AS emergency_admissions
    FROM ae_northumbria
    ORDER BY date
""", conn)
print(q4.to_string(index=False))

# QUERY 5 — Year on year comparison
print("\n[QUERY 5] Year-on-year comparison (2023-24 vs 2024-25)")
q5 = pd.read_sql("""
    SELECT
        CASE
            WHEN date < '2024-04-01' THEN '2023-24'
            ELSE '2024-25'
        END AS financial_year,
        ROUND(AVG(total_attendances), 0) AS avg_monthly_att,
        ROUND(AVG(national_4hr_pct), 1) AS avg_4hr_pct,
        SUM(wait_12hr_plus_dta) AS total_12hr_waits,
        SUM(total_emerg_adm) AS total_emerg_adm
    FROM ae_national_monthly
    GROUP BY financial_year
    ORDER BY financial_year
""", conn)
print(q5.to_string(index=False))

# QUERY 6 — Regional performance
print("\n[QUERY 6] Average 4-hour performance by NHS England region")
q6 = pd.read_sql("""
    SELECT
        parent_org AS region,
        ROUND(AVG(type1_4hr_pct), 1) AS avg_4hr_pct,
        ROUND(SUM(total_attendances) / 1000000.0, 2) AS total_att_millions,
        COUNT(DISTINCT org_code) AS num_trusts
    FROM ae_monthly_trust
    WHERE att_type1 >= 500
      AND type1_4hr_pct IS NOT NULL
      AND parent_org NOT LIKE '%TOTAL%'
    GROUP BY parent_org
    ORDER BY avg_4hr_pct DESC
""", conn)
print(q6.to_string(index=False))

conn.close()
print("\n[DONE] All queries complete")
