"""
Fixed charts — run this to regenerate chart2 and chart3 with proper x-axis labels
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
import sqlite3
import os

DB_PATH = "./data/ae_data.db"
CHARTS_FOLDER = "./charts"

conn = sqlite3.connect(DB_PATH)
national = pd.read_sql("SELECT * FROM ae_national_monthly ORDER BY date", conn)
northumbria = pd.read_sql("SELECT * FROM ae_northumbria ORDER BY date", conn)
conn.close()

# Fix date column back to datetime
national["date"] = pd.to_datetime(national["date"])
northumbria["date"] = pd.to_datetime(northumbria["date"])

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linestyle": "--",
})

NHS_BLUE  = "#005EB8"
NHS_DARK  = "#003087"
RED       = "#DA291C"
GREEN     = "#009639"

def fmt_xaxis(ax):
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[4, 7, 10, 1]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right", fontsize=9)

# ── CHART 1 — National attendances (re-render with proper x labels) ──────────
fig, ax = plt.subplots(figsize=(12, 5))
ax.fill_between(national["date"], national["total_attendances"], alpha=0.15, color=NHS_BLUE)
ax.plot(national["date"], national["total_attendances"],
        color=NHS_BLUE, linewidth=2.5, marker="o", markersize=4)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x/1e6:.2f}M"))
ax.set_title("Total A&E Attendances — England (Apr 2023 – Mar 2025)",
             fontsize=13, fontweight="bold", pad=12)
ax.set_ylabel("Monthly attendances")
ax.axvline(pd.Timestamp("2024-04-01"), color="gray", linestyle=":", alpha=0.7)
ax.text(pd.Timestamp("2024-04-15"),
        national["total_attendances"].min() * 1.002,
        "2024-25 →", fontsize=9, color="gray")
fmt_xaxis(ax)
plt.tight_layout()
plt.savefig(os.path.join(CHARTS_FOLDER, "chart1_national_attendances.png"),
            dpi=150, bbox_inches="tight")
plt.close()
print("Chart 1 regenerated")

# ── CHART 2 — 4hr performance: fixed with annotations ────────────────────────
fig, ax = plt.subplots(figsize=(12, 5))

# Plot the actual line
ax.plot(national["date"], national["national_4hr_pct"],
        color=NHS_DARK, linewidth=2.5, marker="o", markersize=5,
        label="National 4hr performance", zorder=3)

# 95% target line
ax.axhline(95, color=GREEN, linestyle="--", linewidth=1.8, label="95% target", zorder=2)

# Shade gap between line and target
ax.fill_between(national["date"],
                national["national_4hr_pct"],
                95,
                alpha=0.10, color=RED, label="Gap from target")

# Annotate best and worst months
best_idx = national["national_4hr_pct"].idxmax()
worst_idx = national["national_4hr_pct"].idxmin()
ax.annotate(f"Best: {national.loc[best_idx,'national_4hr_pct']}%",
            xy=(national.loc[best_idx, "date"], national.loc[best_idx, "national_4hr_pct"]),
            xytext=(10, 8), textcoords="offset points",
            fontsize=9, color=NHS_DARK,
            arrowprops=dict(arrowstyle="->", color=NHS_DARK, lw=1))
ax.annotate(f"Worst: {national.loc[worst_idx,'national_4hr_pct']}%",
            xy=(national.loc[worst_idx, "date"], national.loc[worst_idx, "national_4hr_pct"]),
            xytext=(10, -14), textcoords="offset points",
            fontsize=9, color=RED,
            arrowprops=dict(arrowstyle="->", color=RED, lw=1))

ax.set_ylim(55, 100)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
ax.set_title("Type 1 A&E 4-Hour Performance — England vs 95% Target (Apr 2023 – Mar 2025)",
             fontsize=13, fontweight="bold", pad=12)
ax.set_ylabel("% patients seen within 4 hours")
ax.legend(loc="upper right", fontsize=10)
fmt_xaxis(ax)
plt.tight_layout()
plt.savefig(os.path.join(CHARTS_FOLDER, "chart2_4hr_performance.png"),
            dpi=150, bbox_inches="tight")
plt.close()
print("Chart 2 regenerated")

# ── CHART 3 — Northumbria vs National ────────────────────────────────────────
fig, ax = plt.subplots(figsize=(12, 5))

ax.plot(national["date"], national["national_4hr_pct"],
        color="gray", linewidth=1.8, linestyle="--",
        label=f"England average ({national['national_4hr_pct'].mean():.1f}%)", alpha=0.8)
ax.plot(northumbria["date"], northumbria["type1_4hr_pct"],
        color=NHS_BLUE, linewidth=2.5, marker="o", markersize=5,
        label=f"Northumbria Healthcare NHS FT ({northumbria['type1_4hr_pct'].mean():.1f}%)")
ax.axhline(95, color=GREEN, linestyle=":", linewidth=1.2, label="95% target")

# Shade the outperformance gap
merged = pd.merge(national[["date","national_4hr_pct"]],
                  northumbria[["date","type1_4hr_pct"]], on="date")
ax.fill_between(merged["date"],
                merged["national_4hr_pct"],
                merged["type1_4hr_pct"],
                where=merged["type1_4hr_pct"] >= merged["national_4hr_pct"],
                alpha=0.12, color=NHS_BLUE, label="Northumbria outperformance")

ax.set_ylim(55, 100)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
ax.set_title("Type 1 A&E 4-Hour Performance: Northumbria Healthcare vs England Average",
             fontsize=13, fontweight="bold", pad=12)
ax.set_ylabel("% patients seen within 4 hours")
ax.legend(loc="lower left", fontsize=10)
fmt_xaxis(ax)
plt.tight_layout()
plt.savefig(os.path.join(CHARTS_FOLDER, "chart3_northumbria_vs_national.png"),
            dpi=150, bbox_inches="tight")
plt.close()
print("Chart 3 regenerated")

# ── CHART 4 — 12hr waits (re-render with proper x labels) ────────────────────
fig, ax = plt.subplots(figsize=(12, 5))
colors = [RED if v > 50000 else "#E87070" for v in national["wait_12hr_plus_dta"]]
ax.bar(national["date"], national["wait_12hr_plus_dta"],
       color=colors, alpha=0.85, width=20)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
ax.set_title("Patients Waiting 12+ Hours from Decision to Admit — England (Apr 2023 – Mar 2025)",
             fontsize=13, fontweight="bold", pad=12)
ax.set_ylabel("Number of patients")
# Add a trend line
z = np.polyfit(range(len(national)), national["wait_12hr_plus_dta"], 1)
p = np.poly1d(z)
ax.plot(national["date"], p(range(len(national))),
        color="darkred", linewidth=1.5, linestyle="--", alpha=0.6, label="Trend")
ax.legend(fontsize=10)
fmt_xaxis(ax)
plt.tight_layout()
plt.savefig(os.path.join(CHARTS_FOLDER, "chart4_12hr_waits.png"),
            dpi=150, bbox_inches="tight")
plt.close()
print("Chart 4 regenerated")

print("\nAll charts regenerated — check your charts/ folder")
