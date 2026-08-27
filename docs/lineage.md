# Data Lineage

End-to-end path from files on disk to dashboard metrics.

## Lineage diagram

```text
content_performance.csv ─┐
user_signups.json ───────┼─► validate.py ─► load_raw.py ─► raw.*
portfolio_revenue.csv ───┤
campaign_metadata.csv ───┘
                              │
                              ▼
                    staging.stg_* (dbt)
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
   intermediate.int_user_attribution   (uses campaigns + content)
              │
              ▼
   intermediate.int_user_revenue
              │
              ├─► marts.fct_attributed_revenue
              ├─► marts.dim_user_cohort
              │
staging.stg_content_performance ─► marts.fct_content_performance
staging.stg_campaign_metadata + attribution ─► marts.fct_campaign_roi
attribution ∪ content ∪ campaigns ─► marts.dim_channel
static mapping ─► marts.dim_company
date spine from source mins/maxes ─► marts.dim_time

marts.fct_attributed_revenue
        │
        ├─► analytics/01_channel_revenue_ranking.sql
        ├─► analytics/03_cac_by_channel.sql
        ├─► analytics/04_cohort_retention.sql
        ├─► analytics/05_revenue_trend_forecast.sql
        ├─► analytics/anomaly_detection.sql
        └─► forecasting/forecast.py → analytics.company_forecast

marts.fct_campaign_roi ─► analytics/02_campaign_roi.sql

All of the above ─► dashboard/app.py (Streamlit)
                 ─► outputs/*.csv
```

## Column-level highlights

| Consumer field | Upstream |
|----------------|----------|
| `attr_channel_last_touch` | `last_touch_channel` → `utm_source` → `referral_source` → `unknown` |
| `attr_channel_first_touch` | `first_touch_channel` → same fallback chain |
| `campaign_id` | `utm_campaign` = `campaign_slug` |
| `content_id_last_touch` | Best-effort content in 30d pre-signup matching channel/campaign |
| Company forecast `revenue` | Monthly sum of `fct_attributed_revenue.revenue_amount` |

## Refresh

Re-run `python scripts/run_pipeline.py` to rebuild from source files through outputs. Data can be regenerated with `python generate_data.py` (deterministic seed).
