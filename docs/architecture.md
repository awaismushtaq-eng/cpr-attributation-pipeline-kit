# Architecture

## Overview

Local ELT pipeline linking Alpha Tango content performance → user signups → portfolio company revenue, producing dual attribution models, campaign ROI, cohort retention, forecasts, and anomaly flags.

```text
data/*.csv|json
      │
      ▼
scripts/validate.py  ──►  soft/validation_report.json
      │
      ▼
      
scripts/load_raw.py  ──►  DuckDB raw.*
      │
      ▼
dbt staging.*        ──►  cleaned typed sources
      │
      ▼
dbt intermediate.*   ──►  attribution resolution + journey stitch
      │
      ▼
dbt marts.*          ──►  facts + dimensions
      │
      ├─► analytics/*.sql          → outputs/*.csv
      ├─► forecasting/forecast.py  → analytics.company_forecast
      └─► dashboard/app.py         → Streamlit UI
```

## Layers

| Layer | Schema | Role |
|-------|--------|------|
| Raw | `raw` | Faithful load of source files |
| Staging | `staging` | Types, null cleanup, rename |
| Intermediate | `intermediate` | Attribution logic, joins |
| Marts | `marts` | Business facts/dims for consumers |
| Analytics | `analytics` | Forecast outputs (Python) |

## Orchestration

`scripts/run_pipeline.py` runs validate → load → `dbt run` → `dbt test` → forecast → SQL export.

No Airflow/Prefect — intentional for a local, reviewer-friendly submission. The script is the DAG.
