# Data Model

## Sources → staging

| Source | Staging model | Grain |
|--------|---------------|-------|
| `content_performance.csv` | `stg_content_performance` | 1 row per content piece |
| `user_signups.json` | `stg_user_signups` | 1 row per user |
| `portfolio_revenue.csv` | `stg_portfolio_revenue` | 1 row per user-month revenue |
| `campaign_metadata.csv` | `stg_campaign_metadata` | 1 row per campaign |

## Intermediate

| Model | Grain | Purpose |
|-------|-------|---------|
| `int_user_attribution` | user | Resolved first/last channels, campaign, content, confidence |
| `int_user_revenue` | revenue_id | Revenue ⋈ attribution (signup-time inheritance) |

## Marts

### Facts

| Model | Grain | Notes |
|-------|-------|-------|
| `fct_attributed_revenue` | revenue_id | Dual channel attrs + campaign/content IDs |
| `fct_content_performance` | content_id | Views, clicks, CTR, month |
| `fct_campaign_roi` | campaign_id | Spend vs attributed revenue + ROI/CAC |

### Dimensions

| Model | Key |
|-------|-----|
| `dim_channel` | `channel_id` |
| `dim_company` | `company_id` |
| `dim_user_cohort` | `user_id` (+ `cohort_key`) |
| `dim_time` | `date_day` |

## Entity relationships

```text
dim_company 1───* dim_user_cohort 1───* fct_attributed_revenue
dim_channel 1───* fct_attributed_revenue (first & last)
dim_channel 1───* fct_content_performance
stg_campaign_metadata 1───* fct_attributed_revenue (nullable)
```

## Portfolio companies

| ID | Name | Industry |
|----|------|----------|
| CTC-001 | GreenLeaf Landscaping | Home Services |
| CTC-002 | BrightPath Education | Education |
| CTC-003 | QuickFix Auto Repair | Automotive |
| CTC-004 | Summit Dental Group | Healthcare |
