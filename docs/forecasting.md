# Forecasting Methodology

## Approaches

### 1. SQL trailing 3-month average (channel-level)

Implemented in `analytics/05_revenue_trend_forecast.sql`.

- Aggregate last-touch attributed revenue by channel × month
- Compute trailing 3-month average
- Project that average forward 3 months (`series_type = 'forecast'`)

**Strengths:** Transparent, easy to audit in SQL, stable for short horizons.  
**Weaknesses:** Ignores trend/seasonality; flat forecast; reacts slowly to regime change.

### 2. Python Holt linear trend (company-level)

Implemented in `forecasting/forecast.py` via `statsmodels` `ExponentialSmoothing` with additive trend (Holt). Falls back to level-only SES or trailing mean if fit fails / series too short.

- Monthly company revenue from `fct_attributed_revenue`
- Forecast next 3 months
- Outputs: `outputs/company_forecast.csv` + `analytics.company_forecast`

**Strengths:** Captures local trend; non-negative clipped; per-company.  
**Weaknesses:** No seasonality (only ~18 months history); sensitive to shocks; no uncertainty intervals in v1.

## Limitations — when forecasts break down

- **Structural breaks** (new product, pricing, channel mix) — both methods extrapolate the recent past
- **Seasonality** (e.g. landscaping spring peak) — Holt without seasonal terms will miss it
- **Sparse channels / young cohorts** — trailing averages overfit noise
- **Marketing spend changes** — models are univariate on revenue, not spend-driven
- **Horizon > 3 months** — error compounds; treat as directional only

## Recommended use

Use SQL channel forecasts for leadership “directionally, which channels are growing?”  
Use Holt company forecasts for portfolio planning conversations — always with the caveat that this is a baseline, not a budget.
