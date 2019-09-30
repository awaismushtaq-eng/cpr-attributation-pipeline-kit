"""
Company-level revenue forecast using Holt's linear trend (exponential smoothing).

Writes:
  - outputs/company_forecast.csv
  - analytics.company_forecast table in DuckDB
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from paths import OUTPUTS_DIR, WAREHOUSE_PATH  # noqa: E402

HORIZON = 3
MIN_POINTS = 6


def _fit_forecast(series: pd.Series, horizon: int = HORIZON) -> list[float]:
    """Holt (additive trend, no seasonality) with SES fallback."""
    y = series.astype(float).dropna()
    if len(y) < 3:
        fill = float(y.iloc[-1]) if len(y) else 0.0
        return [fill] * horizon

    try:
        if len(y) >= MIN_POINTS:
            model = ExponentialSmoothing(
                y,
                trend="add",
                seasonal=None,
                initialization_method="estimated",
            )
        else:
            model = ExponentialSmoothing(
                y,
                trend=None,
                seasonal=None,
                initialization_method="estimated",
            )
        fitted = model.fit(optimized=True)
        pred = fitted.forecast(horizon)
        return [max(0.0, float(v)) for v in pred]
    except Exception:
        # Simple trailing mean fallback
        fill = float(y.tail(3).mean())
        return [max(0.0, fill)] * horizon


def run_forecast(warehouse: Path = WAREHOUSE_PATH) -> pd.DataFrame:
    con = duckdb.connect(str(warehouse))
    try:
        hist = con.execute(
            """
            select
                r.company_id,
                c.company_name,
                r.revenue_month,
                sum(r.revenue_amount) as revenue
            from marts.fct_attributed_revenue r
            left join marts.dim_company c using (company_id)
            group by 1, 2, 3
            order by 1, 3
            """
        ).fetchdf()

        rows: list[dict] = []
        for company_id, grp in hist.groupby("company_id", sort=True):
            grp = grp.sort_values("revenue_month")
            company_name = grp["company_name"].iloc[0]
            series = grp.set_index("revenue_month")["revenue"]
            # Ensure monthly frequency index for statsmodels
            series.index = pd.to_datetime(series.index)
            series = series.asfreq("MS", fill_value=0.0)

            last_month = series.index.max()
            forecasts = _fit_forecast(series)

            # Actuals marker rows (optional context)
            for ts, val in series.items():
                rows.append(
                    {
                        "company_id": company_id,
                        "company_name": company_name,
                        "month": ts.date(),
                        "revenue": round(float(val), 2),
                        "series_type": "actual",
                        "model": "history",
                    }
                )

            for i, val in enumerate(forecasts, start=1):
                month = (last_month + pd.DateOffset(months=i)).date()
                rows.append(
                    {
                        "company_id": company_id,
                        "company_name": company_name,
                        "month": month,
                        "revenue": round(val, 2),
                        "series_type": "forecast",
                        "model": "holt_linear",
                    }
                )

        out = pd.DataFrame(rows)
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        csv_path = OUTPUTS_DIR / "company_forecast.csv"
        out.to_csv(csv_path, index=False)

        con.execute("CREATE SCHEMA IF NOT EXISTS analytics")
        con.execute("DROP TABLE IF EXISTS analytics.company_forecast")
        con.register("_forecast_df", out)
        con.execute(
            """
            CREATE TABLE analytics.company_forecast AS
            SELECT
                company_id::VARCHAR AS company_id,
                company_name::VARCHAR AS company_name,
                month::DATE AS month,
                revenue::DOUBLE AS revenue,
                series_type::VARCHAR AS series_type,
                model::VARCHAR AS model
            FROM _forecast_df
            """
        )
        con.unregister("_forecast_df")
        print(f"Wrote {csv_path}")
        print("Wrote analytics.company_forecast")
        return out
    finally:
        con.close()


def main() -> int:
    print(f"Forecasting from {WAREHOUSE_PATH}")
    df = run_forecast()
    fc = df[df["series_type"] == "forecast"]
    print(fc.groupby("company_id")["revenue"].apply(list).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
