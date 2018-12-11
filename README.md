# Cross-Portfolio Revenue Attribution & Forecasting Pipeline

End-to-end local ELT pipeline that connects **content performance → user signups → portfolio revenue**, then answers: *which channels and campaigns actually drive revenue?*

Implements dual attribution (**last-touch** + **first-touch**), campaign ROI, CAC, cohort retention, dual forecasting (SQL + Python), anomaly detection, and a Streamlit dashboard.

**Stack:** Python 3.10+ · DuckDB · dbt · statsmodels · Streamlit · `venv`

---

## Setup instructions

### Prerequisites

- Python 3.10+
- ~500 MB free disk (venv + DuckDB warehouse)

### Install & run

```bash
cd revenue-attribution-pipeline

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Full pipeline: validate → load → dbt run/test → forecast → export analytics
python scripts/run_pipeline.py

# Optional dashboard
streamlit run dashboard/app.py
```

### What the pipeline does

| Step | Script / tool | Output |
|------|---------------|--------|
| 1. Validate sources | `scripts/validate.py` | `outputs/validation_report.json` |
| 2. Load raw tables | `scripts/load_raw.py` | DuckDB `raw.*` |
| 3. Transform + test | dbt | `staging` → `intermediate` → `marts` |
| 4. Forecast | `forecasting/forecast.py` | `analytics.company_forecast`, CSV |
| 5. Analytics export | `scripts/export_analytics.py` | `outputs/*.csv` |

### Regenerating sample data

```bash
python generate_data.py
python scripts/run_pipeline.py
```

Data is deterministic (seeded). Re-running produces identical source files.

### Exploring the warehouse

```bash
# CLI (if DuckDB CLI installed)
duckdb warehouse/warehouse.duckdb

# Or local UI
duckdb warehouse/warehouse.duckdb -ui
```

---

## Architecture diagram

```text
┌─────────────────────────────────────────────────────────────────┐
│  data/                                                          │
│  content_performance.csv │ user_signups.json                    │
│  portfolio_revenue.csv   │ campaign_metadata.csv                │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  validate.py          │
                    │  hard fail → abort    │
                    │  soft warn → continue │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  load_raw.py          │
                    │  DuckDB raw.*         │
                    └───────────┬───────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────┐
│  dbt                                                          │
│                                                               │
│  staging.*  →  intermediate.*  →  marts.*                     │
│  (clean)       (attribution +      (facts + dims)             │
│                 journey stitch)                                │
└───────────────────────────┬───────────────────────────────────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
   analytics/*.sql   forecasting/      dashboard/app.py
   → outputs/*.csv   Holt (Python)     Streamlit
                     → company_forecast
```

| Layer | DuckDB schema | Role |
|-------|---------------|------|
| Raw | `raw` | Faithful load of source files |
| Staging | `staging` | Typed, cleaned sources |
| Intermediate | `intermediate` | Channel resolution + revenue stitch |
| Marts | `marts` | Business-ready facts & dimensions |
| Analytics | `analytics` | Python forecast table |

Orchestration is `scripts/run_pipeline.py` (no Airflow/Prefect — intentional for a local, one-command review).

Deeper notes: [docs/architecture.md](docs/architecture.md) · [docs/lineage.md](docs/lineage.md)

---

## Data model documentation

### Sources

| File | Records | Grain |
|------|---------|-------|
| `content_performance.csv` | ~1,370 | 1 row per content piece |
| `user_signups.json` | ~6,170 | 1 row per user |
| `portfolio_revenue.csv` | ~27,070 | 1 row per user × month |
| `campaign_metadata.csv` | 30 | 1 row per campaign |

### Portfolio companies

| ID | Name | Industry |
|----|------|----------|
| CTC-001 | GreenLeaf Landscaping | Home Services |
| CTC-002 | BrightPath Education | Education |
| CTC-003 | QuickFix Auto Repair | Automotive |
| CTC-004 | Summit Dental Group | Healthcare |

### Model layers

**Staging** — `stg_content_performance`, `stg_user_signups`, `stg_portfolio_revenue`, `stg_campaign_metadata`

**Intermediate**

| Model | Grain | Purpose |
|-------|-------|---------|
| `int_user_attribution` | user | Resolved first/last channels, campaign, content, confidence |
| `int_user_revenue` | revenue_id | Revenue ⋈ attribution (signup-time inheritance) |

**Marts — facts**

| Model | Grain | Description |
|-------|-------|-------------|
| `fct_attributed_revenue` | revenue_id | Revenue + dual attribution channels |
| `fct_content_performance` | content_id | Views, clicks, CTR by piece |
| `fct_campaign_roi` | campaign_id | Spend vs attributed revenue / ROI / CAC |

**Marts — dimensions**

| Model | Key |
|-------|-----|
| `dim_channel` | `channel_id` |
| `dim_company` | `company_id` |
| `dim_user_cohort` | `user_id` (+ `cohort_key`) |
| `dim_time` | `date_day` |

### Relationships

```text
dim_company 1───* dim_user_cohort 1───* fct_attributed_revenue
dim_channel 1───* fct_attributed_revenue   (via first-touch & last-touch)
dim_channel 1───* fct_content_performance
campaign    1───* fct_attributed_revenue   (nullable — UTM join)
```

Full detail: [docs/data_model.md](docs/data_model.md)

---

## Attribution model trade-off analysis

### Models implemented

| Model | Credits | Best question it answers |
|-------|---------|--------------------------|
| **Last-touch** | Channel that closed the signup | “What converted them?” / closing ROI |
| **First-touch** | Channel that started the journey | “What acquired them?” / media top-of-funnel |

Every user has **both** fields. We do **not** split users into two groups. We stamp both resolved channels onto their revenue and aggregate twice:

- Last-touch ranking → `GROUP BY attr_channel_last_touch`
- First-touch ranking → `GROUP BY attr_channel_first_touch`

### Why first-touch (not linear / time-decay / position-based)

| Option | Why we skipped / chose |
|--------|-------------------------|
| **First-touch** (chosen) | Matches Alpha Tango’s “content as acquisition engine” story; ~38% of users have first ≠ last, so rankings diverge meaningfully |
| Linear | Needs a full multi-touch path; we only have first + last → would be a crude 50/50 split |
| Time-decay | Needs timestamps for every touch in the path — not available |
| Position-based (U-shaped) | Same limitation — only two touchpoints |

### Dirty-data handling

Channel resolution order (per touch):

1. Explicit touch field (`first_touch_channel` / `last_touch_channel`)
2. Else `utm_source` (if known channel)
3. Else `referral_source` (if known channel)
4. Else `'unknown'`

| Situation | Handling |
|-----------|----------|
| Missing UTMs (~12% source, ~57% campaign) | **Keep user**; fallback to touches/referral; campaign stays null if unmatched |
| first ≠ last (~38%) | Keep **both**; set `has_touch_conflict` |
| referral vs UTM conflict | Flag `has_referral_utm_conflict`; resolution order still applies |
| No usable signal | `unknown` + confidence `low` |

Confidence: `high` / `medium` / `low` (see [docs/attribution_rules.md](docs/attribution_rules.md)).

### Trade-off summary

| Choice | Upside | Downside |
|--------|--------|----------|
| Dual models side-by-side | Leadership sees how the story changes | Two answers, not one “truth” |
| Signup-time attribution frozen | Simple, stable cohorts | Ignores later nurturing touches |
| Never drop messy UTM rows | Complete revenue coverage | Some channel credit is imputed |
| Best-effort content join (30d) | Optional content_id enrichment | Many null `content_id`s — expected |

---

## Forecasting methodology & limitations

### Approach 1 — SQL trailing 3-month average (channel-level)

**Where:** `analytics/05_revenue_trend_forecast.sql`

1. Sum last-touch attributed revenue by channel × month  
2. Compute trailing 3-month average  
3. Project that average forward **3 months** (`series_type = 'forecast'`)

| Strengths | Weaknesses |
|-----------|------------|
| Transparent, auditable in SQL | Flat — no trend/seasonality |
| Stable for short horizons | Slow to react to regime changes |

### Approach 2 — Python Holt linear trend (company-level)

**Where:** `forecasting/forecast.py` (`statsmodels` ExponentialSmoothing, additive trend)

1. Monthly company revenue from `fct_attributed_revenue`  
2. Fit Holt (fallback: SES or trailing mean if series is short / fit fails)  
3. Forecast next **3 months** → `outputs/company_forecast.csv` + `analytics.company_forecast`

| Strengths | Weaknesses |
|-----------|------------|
| Captures local trend | No seasonality (~18 months of history) |
| Per-company planning view | Sensitive to shocks; no prediction intervals in v1 |

### When forecasts break down

- Structural breaks (pricing, product, channel mix shifts)
- Strong seasonality (e.g. landscaping in spring)
- Sparse channels / young cohorts (noise dominates)
- Spend changes (models are univariate on revenue only)
- Horizons beyond ~3 months (treat as directional, not a budget)

**Intended use:** channel SQL forecast for “which channels are growing?”; Holt for portfolio planning conversations — always as a **baseline**, not a commitment.

Details: [docs/forecasting.md](docs/forecasting.md)

---

## Assumptions & trade-offs

| Assumption / trade-off | Rationale |
|------------------------|-----------|
| **DuckDB instead of BigQuery** | Fully local review with zero cloud credentials; same dbt layering ports later |
| **Attribution fixed at signup** | Revenue months inherit signup-time channels; supports clean cohorts |
| **Campaign via `utm_campaign` ↔ `campaign_slug`** | Matches how sample data is generated; unmatched → null campaign |
| **Content link is best-effort** | 30-day pre-signup window; nulls are OK |
| **CAC: untargeted budget split by signup share** | Pragmatic allocation when campaign has no `target_company_id` |
| **Hard-fail validation vs soft UTM warnings** | Broken keys/dates block load; messy marketing tags are expected |
| **`run_pipeline.py` as orchestrator** | One-command reproducibility for reviewers; no infra dependency |
| **Streamlit as stretch UI** | Demo-friendly; marts remain the source of truth for BI |

---

## Future improvements

1. **Richer multi-touch paths** — enable time-decay / position-based models with real event streams  
2. **Incremental dbt models** — append new revenue months instead of full refresh  
3. **Cloud warehouse profile** — BigQuery/Snowflake adapter beside DuckDB  
4. **Spend-driven forecasts** — campaign budget as exogenous input; prediction intervals + backtests  
5. **Production orchestration** — Prefect/Airflow DAG wrapping the same scripts  
6. **Stronger content identity** — deterministic content_id on signup events instead of fuzzy joins  
7. **Data quality monitors** — alert when orphan rates or null-UTM rates spike vs baseline  

---

## Project layout

```text
revenue-attribution-pipeline/
├── data/                 Source CSV/JSON (regenerable)
├── scripts/              validate, load_raw, export_analytics, run_pipeline
├── warehouse/            Local DuckDB file (gitignored)
├── dbt_project/          staging → intermediate → marts + tests
├── analytics/            Business SQL + anomaly detection
├── forecasting/          Python Holt forecasts
├── dashboard/            Streamlit app
├── docs/                 Deep-dive documentation
├── outputs/              Sample query / forecast CSVs
├── generate_data.py      Deterministic data generator
├── requirements.txt
└── README.md
```

### Analytics questions → outputs

| File | Question |
|------|----------|
| `01_channel_revenue_ranking.sql` | Which channels drive revenue under each model? |
| `02_campaign_roi.sql` | Campaign spend vs revenue efficiency |
| `03_cac_by_channel.sql` | CAC by channel × company |
| `04_cohort_retention.sql` | Retention by acquisition channel |
| `05_revenue_trend_forecast.sql` | MoM + 3-mo trailing-avg forecast |
| `anomaly_detection.sql` | Channel-months with \|z\| > 2 |

After `python scripts/run_pipeline.py`, sample results are in `outputs/`.

---

## Documentation index

| Doc | Topic |
|-----|-------|
| [docs/architecture.md](docs/architecture.md) | Layers & orchestration |
| [docs/data_model.md](docs/data_model.md) | Tables, grains, relationships |
| [docs/attribution_rules.md](docs/attribution_rules.md) | Resolution rules & confidence |
| [docs/forecasting.md](docs/forecasting.md) | Methods & failure modes |
| [docs/lineage.md](docs/lineage.md) | Source → mart → dashboard lineage |
