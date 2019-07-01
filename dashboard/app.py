"""
Streamlit dashboard: attribution comparison, campaign ROI, forecasts, anomalies.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "warehouse" / "warehouse.duckdb"


@st.cache_data(ttl=60)
def query(sql: str) -> pd.DataFrame:
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        return con.execute(sql).fetchdf()
    finally:
        con.close()


def main() -> None:
    st.set_page_config(
        page_title="Revenue Attribution",
        layout="wide",
    )
    st.title("Cross-Portfolio Revenue Attribution")
    st.caption("Last-touch vs first-touch · campaign ROI · forecasts · anomalies")

    if not WAREHOUSE.exists():
        st.error(
            f"Warehouse not found at `{WAREHOUSE}`. "
            "Run `python scripts/run_pipeline.py` first."
        )
        st.stop()

    tab_attr, tab_roi, tab_fc, tab_anom = st.tabs(
        ["Attribution", "Campaign ROI", "Forecasts", "Anomalies"]
    )

    with tab_attr:
        st.subheader("Channel revenue: last-touch vs first-touch")
        ranking = query(
            """
            with last_touch as (
                select attr_channel_last_touch as channel,
                       sum(revenue_amount) as revenue
                from marts.fct_attributed_revenue
                group by 1
            ),
            first_touch as (
                select attr_channel_first_touch as channel,
                       sum(revenue_amount) as revenue
                from marts.fct_attributed_revenue
                group by 1
            )
            select
                coalesce(l.channel, f.channel) as channel,
                coalesce(l.revenue, 0) as last_touch,
                coalesce(f.revenue, 0) as first_touch
            from last_touch l
            full outer join first_touch f using (channel)
            order by last_touch desc
            """
        )
        long = ranking.melt(
            id_vars="channel",
            value_vars=["last_touch", "first_touch"],
            var_name="model",
            value_name="revenue",
        )
        fig = px.bar(
            long,
            x="channel",
            y="revenue",
            color="model",
            barmode="group",
            labels={"revenue": "Attributed revenue (USD)", "channel": "Channel"},
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(ranking.round(2), use_container_width=True)
        st.info(
            "Ranks shift when first≠last touch (~38% of users). "
            "Last-touch credits the closing channel; first-touch credits acquisition."
        )

    with tab_roi:
        st.subheader("Campaign spend vs attributed revenue")
        roi = query(
            """
            select
                campaign_name,
                channel,
                budget_usd,
                attributed_signups,
                round(attributed_revenue_last_touch, 2) as revenue_last_touch,
                round(roi_last_touch, 3) as roi_last_touch,
                round(cac_last_touch, 2) as cost_per_signup
            from marts.fct_campaign_roi
            order by roi_last_touch desc nulls last
            """
        )
        st.dataframe(roi, use_container_width=True)
        top = roi.dropna(subset=["roi_last_touch"]).head(10)
        if not top.empty:
            fig = px.bar(
                top,
                x="campaign_name",
                y="roi_last_touch",
                color="channel",
                labels={"roi_last_touch": "ROI (revenue / spend)"},
            )
            fig.update_layout(xaxis_tickangle=-35)
            st.plotly_chart(fig, use_container_width=True)

    with tab_fc:
        st.subheader("Company revenue forecast (Holt linear, next 3 months)")
        try:
            fc = query(
                """
                select company_id, company_name, month, revenue, series_type, model
                from analytics.company_forecast
                order by company_id, month
                """
            )
        except Exception:
            st.warning("Forecast table missing — run the full pipeline first.")
            fc = pd.DataFrame()

        if not fc.empty:
            company = st.selectbox(
                "Company",
                sorted(fc["company_name"].dropna().unique()),
            )
            subset = fc[fc["company_name"] == company]
            fig = px.line(
                subset,
                x="month",
                y="revenue",
                color="series_type",
                markers=True,
                labels={"revenue": "Revenue (USD)"},
            )
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(
                subset[subset["series_type"] == "forecast"][
                    ["company_name", "month", "revenue", "model"]
                ],
                use_container_width=True,
            )

    with tab_anom:
        st.subheader("Channel revenue anomalies (|z| > 2 vs trailing mean)")
        anom = query(
            Path(ROOT / "analytics" / "anomaly_detection.sql").read_text(encoding="utf-8")
        )
        flagged = anom[anom["is_anomaly"] == True]  # noqa: E712
        st.metric("Anomalous channel-months", len(flagged))
        if not flagged.empty:
            st.dataframe(flagged, use_container_width=True)
            fig = px.scatter(
                anom,
                x="revenue_month",
                y="z_score",
                color="channel",
                symbol=anom["is_anomaly"].map({True: "anomaly", False: "normal"}),
                title="Z-scores by channel-month",
            )
            fig.add_hline(y=2, line_dash="dash")
            fig.add_hline(y=-2, line_dash="dash")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("No anomalies at |z| > 2 with current threshold.")
            st.dataframe(anom.head(20), use_container_width=True)


if __name__ == "__main__":
    main()
