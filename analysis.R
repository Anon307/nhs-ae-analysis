#!/usr/bin/env Rscript
# ---------------------------------------------------------------------------
# NHS A&E Attendance & Performance Analysis - R validation layer
#
# Purpose: independently reproduce the headline figures produced by the Python
# pipeline (pipeline.py) directly from the SQLite database, as a cross-check
# across two separate toolchains. Any divergence between this script's output
# and the Python output indicates a defect in one of them.
#
# Usage:  Rscript analysis.R
# Deps:   DBI, RSQLite, dplyr, ggplot2, scales
# ---------------------------------------------------------------------------

suppressPackageStartupMessages({
  library(DBI)
  library(RSQLite)
  library(dplyr)
  library(ggplot2)
  library(scales)
})

DB_PATH     <- file.path("data", "ae_data.db")
OUT_DIR     <- "charts"
TARGET_4HR  <- 95      # NHS constitutional standard, %
TRUST_CODE  <- "RTF"   # Northumbria Healthcare NHS Foundation Trust

if (!file.exists(DB_PATH)) {
  stop("Database not found at ", DB_PATH, ". Run pipeline.py first.")
}
if (!dir.exists(OUT_DIR)) dir.create(OUT_DIR)

con <- dbConnect(RSQLite::SQLite(), DB_PATH)
on.exit(dbDisconnect(con), add = TRUE)

# ---------------------------------------------------------------------------
# 1. Load
# ---------------------------------------------------------------------------

trust <- dbGetQuery(con, "
  SELECT date, org_code, org_name,
         att_type1, over4hr_type1,
         total_attendances, total_over4hr, type1_4hr_pct,
         wait_12hr_plus_dta, total_emerg_adm
  FROM ae_monthly_trust
") %>%
  mutate(date = as.Date(date))

national <- dbGetQuery(con, "
  SELECT date, total_attendances, total_over4hr, total_emerg_adm,
         wait_12hr_plus_dta, national_4hr_pct
  FROM ae_national_monthly
  ORDER BY date
") %>%
  mutate(date = as.Date(date))

message(sprintf("Loaded %s trust-months across %s providers, %s to %s",
                format(nrow(trust), big.mark = ","),
                n_distinct(trust$org_code),
                format(min(national$date), "%b %Y"),
                format(max(national$date), "%b %Y")))

# ---------------------------------------------------------------------------
# 2. Data quality checks
#    These mirror the checks in pipeline.py. Each returns a count that should
#    be zero, with the single documented exception of missing type1_4hr_pct.
# ---------------------------------------------------------------------------

qa <- list(
  missing_type1_pct   = sum(is.na(trust$type1_4hr_pct)),
  negative_values     = sum(trust$total_attendances < 0 | trust$total_over4hr < 0,
                            na.rm = TRUE),
  breaches_exceed_att = sum(trust$total_over4hr > trust$total_attendances,
                            na.rm = TRUE),
  pct_above_100       = sum(trust$type1_4hr_pct > 100, na.rm = TRUE),
  pct_below_50        = sum(trust$type1_4hr_pct < 50, na.rm = TRUE),
  zero_breach         = sum(trust$att_type1 > 500 & trust$over4hr_type1 == 0,
                            na.rm = TRUE),
  renamed_orgs        = trust %>%
                          distinct(org_code, org_name) %>%
                          count(org_code) %>%
                          filter(n > 1) %>%
                          nrow()
)

message("\nData quality checks")
message(sprintf("  Missing Type 1 4-hour %%: %s (%.1f%%) - expected; not all providers operate a Type 1 department",
                format(qa$missing_type1_pct, big.mark = ","),
                100 * qa$missing_type1_pct / nrow(trust)))
message(sprintf("  Negative values:                 %s", qa$negative_values))
message(sprintf("  Breaches exceeding attendances:  %s", qa$breaches_exceed_att))
message(sprintf("  Performance above 100%%:          %s", qa$pct_above_100))
message(sprintf("  Trust-months below 50%%:          %s (flagged for review, not an error)",
                format(qa$pct_below_50, big.mark = ",")))
message(sprintf("  Zero-breach non-submissions:      %s trust-months reporting an implausible 100%%",
                qa$zero_breach))
message(sprintf("  Org codes with more than one name: %s (renamed mid-period - group on code, never name)",
                qa$renamed_orgs))

stopifnot(qa$negative_values == 0,
          qa$breaches_exceed_att == 0,
          qa$pct_above_100 == 0)

# ---------------------------------------------------------------------------
# 3. Headline national figures
# ---------------------------------------------------------------------------

nat_avg_pct <- mean(national$national_4hr_pct)
nat_avg_att <- mean(national$total_attendances)
twelve_hr   <- national %>% arrange(date)

message("\nNational headlines")
message(sprintf("  Mean Type 1 4-hour performance: %.2f%% (target %s%%, gap %.1f pp)",
                nat_avg_pct, TARGET_4HR, TARGET_4HR - nat_avg_pct))
message(sprintf("  Mean monthly attendances:       %s", format(round(nat_avg_att), big.mark = ",")))
message(sprintf("  12-hour DTA waits:              %s (%s) rising to a peak of %s (%s)",
                format(twelve_hr$wait_12hr_plus_dta[1], big.mark = ","),
                format(twelve_hr$date[1], "%b %Y"),
                format(max(twelve_hr$wait_12hr_plus_dta), big.mark = ","),
                format(twelve_hr$date[which.max(twelve_hr$wait_12hr_plus_dta)], "%b %Y")))

# ---------------------------------------------------------------------------
# 4. Trust ranking
#    Ranked only across providers that report Type 1 performance, since
#    providers without a Type 1 department are not comparable.
#
#    Group on org_code ALONE. Four trusts changed name mid-period (RAX, RWD,
#    RXF, RBN), so grouping on org_code AND org_name splits them into two
#    organisations each - inflating the provider count from 123 to 127 and
#    producing spurious short-series entries at the top of the ranking. The
#    reporting name is taken from the most recent month for each code.
# ---------------------------------------------------------------------------

latest_name <- trust %>%
  filter(!is.na(org_name)) %>%
  group_by(org_code) %>%
  slice_max(date, n = 1, with_ties = FALSE) %>%
  ungroup() %>%
  select(org_code, org_name)

ranking <- trust %>%
  filter(!is.na(type1_4hr_pct)) %>%
  group_by(org_code) %>%
  summarise(mean_4hr = mean(type1_4hr_pct),
            mean_att = mean(total_attendances),
            months   = n(),
            .groups  = "drop") %>%
  left_join(latest_name, by = "org_code") %>%
  arrange(desc(mean_4hr)) %>%
  mutate(rank = row_number())

target <- ranking %>% filter(org_code == TRUST_CODE)

message("\nNorthumbria Healthcare (RTF)")
message(sprintf("  Mean monthly attendances:  %s", format(round(target$mean_att), big.mark = ",")))
message(sprintf("  Mean 4-hour performance:   %.2f%% (%.1f pp above the national mean)",
                target$mean_4hr, target$mean_4hr - nat_avg_pct))
message(sprintf("  Rank:                      %s of %s providers reporting Type 1 performance",
                target$rank, nrow(ranking)))

message("\nTop 10 providers by mean Type 1 4-hour performance")
print(ranking %>% slice_head(n = 10) %>%
        transmute(rank, org_code,
                  org_name = substr(org_name, 1, 45),
                  mean_4hr = round(mean_4hr, 1)))

# ---------------------------------------------------------------------------
# 5. Year-on-year comparison
# ---------------------------------------------------------------------------

yoy <- national %>%
  mutate(financial_year = if_else(date < as.Date("2024-04-01"), "2023-24", "2024-25")) %>%
  group_by(financial_year) %>%
  summarise(mean_4hr      = mean(national_4hr_pct),
            total_att     = sum(total_attendances),
            total_12hr    = sum(wait_12hr_plus_dta),
            .groups = "drop")

message("\nYear-on-year")
print(yoy %>% mutate(mean_4hr = round(mean_4hr, 1)))

# ---------------------------------------------------------------------------
# 6. Chart - national 4-hour performance against the 95% standard
# ---------------------------------------------------------------------------

p <- ggplot(national, aes(date, national_4hr_pct)) +
  geom_hline(yintercept = TARGET_4HR, linetype = "dashed",
             colour = "#B22222", linewidth = 0.6) +
  annotate("text", x = min(national$date), y = TARGET_4HR + 2.5,
           label = paste0(TARGET_4HR, "% standard"), hjust = 0,
           colour = "#B22222", size = 3.5) +
  geom_line(colour = "#005EB8", linewidth = 1) +
  geom_point(colour = "#005EB8", size = 1.8) +
  scale_x_date(date_breaks = "3 months", date_labels = "%b %Y") +
  scale_y_continuous(limits = c(0, 100), labels = label_percent(scale = 1)) +
  labs(title    = "England Type 1 A&E four-hour performance against the 95% standard",
       subtitle = sprintf("Monthly, April 2023 to March 2025. Period mean %.1f%%.", nat_avg_pct),
       caption  = "Source: NHS England A&E Attendances and Emergency Admissions",
       x = NULL, y = "Seen within four hours") +
  theme_minimal(base_size = 11) +
  theme(panel.grid.minor = element_blank(),
        plot.title = element_text(face = "bold"),
        axis.text.x = element_text(angle = 45, hjust = 1))

ggsave(file.path(OUT_DIR, "chart5_r_4hr_performance.png"), p,
       width = 10, height = 5.5, dpi = 150)

message(sprintf("\nChart written to %s", file.path(OUT_DIR, "chart5_r_4hr_performance.png")))

# ---------------------------------------------------------------------------
# 7. Reconciliation against the Python pipeline
#    These are the figures quoted in the README and the stakeholder summary.
#    The script must fail loudly if R disagrees, rather than printing a
#    reassuring message regardless of the result - which is what an earlier
#    version of this script did, masking a real grouping defect.
# ---------------------------------------------------------------------------

expected <- list(
  rows        = 4796,
  providers   = 207,
  nat_4hr     = 58.82,
  rtf_4hr     = 74.44,
  rtf_rank    = 6,
  ranked_orgs = 123
)

actual <- list(
  rows        = nrow(trust),
  providers   = n_distinct(trust$org_code),
  nat_4hr     = round(nat_avg_pct, 2),
  rtf_4hr     = round(target$mean_4hr, 2),
  rtf_rank    = target$rank,
  ranked_orgs = nrow(ranking)
)

message("\nReconciliation against the Python pipeline")
mismatches <- character(0)
for (k in names(expected)) {
  ok <- isTRUE(all.equal(expected[[k]], actual[[k]], tolerance = 1e-6))
  message(sprintf("  %-12s expected %-10s got %-10s %s",
                  k, expected[[k]], actual[[k]], if (ok) "OK" else "MISMATCH"))
  if (!ok) mismatches <- c(mismatches, k)
}

if (length(mismatches) > 0) {
  stop("R output disagrees with the Python pipeline on: ",
       paste(mismatches, collapse = ", "),
       "\nOne of the two implementations is wrong. Do not quote these figures ",
       "until the discrepancy is resolved.")
}

message("\nR validation complete - all reconciliation checks passed.")
