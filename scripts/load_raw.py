"""
Load validated source files into DuckDB raw.* tables.

Creates / replaces:
  raw.content_performance
  raw.user_signups
  raw.portfolio_revenue
  raw.campaign_metadata
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from paths import (
    CAMPAIGNS_PATH,
    CONTENT_PATH,
    REVENUE_PATH,
    SIGNUPS_PATH,
    WAREHOUSE_DIR,
    WAREHOUSE_PATH,
)


def _ensure_warehouse() -> duckdb.DuckDBPyConnection:
    WAREHOUSE_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE_PATH))
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    return con


def _load_content(con: duckdb.DuckDBPyConnection) -> int:
    df = pd.read_csv(CONTENT_PATH)
    df["publish_date"] = pd.to_datetime(df["publish_date"]).dt.date
    df["views"] = df["views"].astype("int64")
    df["clicks"] = df["clicks"].astype("int64")
    for col in ("utm_source", "utm_campaign", "channel", "content_id"):
        df[col] = df[col].astype("string").where(df[col].notna(), None)
        df[col] = df[col].apply(lambda x: None if x is None or str(x).strip() == "" else str(x).strip())

    con.execute("DROP TABLE IF EXISTS raw.content_performance")
    con.register("_content_df", df)
    con.execute(
        """
        CREATE TABLE raw.content_performance AS
        SELECT
            content_id::VARCHAR AS content_id,
            lower(channel)::VARCHAR AS channel,
            publish_date::DATE AS publish_date,
            views::BIGINT AS views,
            clicks::BIGINT AS clicks,
            nullif(lower(utm_source), '')::VARCHAR AS utm_source,
            nullif(lower(utm_campaign), '')::VARCHAR AS utm_campaign
        FROM _content_df
        """
    )
    con.unregister("_content_df")
    return len(df)


def _load_signups(con: duckdb.DuckDBPyConnection) -> int:
    with SIGNUPS_PATH.open(encoding="utf-8") as f:
        payload = json.load(f)
    df = pd.DataFrame(payload["signups"])
    df["signup_date"] = pd.to_datetime(df["signup_date"]).dt.date

    for col in (
        "user_id",
        "company_id",
        "referral_source",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "first_touch_channel",
        "last_touch_channel",
    ):
        if col not in df.columns:
            df[col] = None
        df[col] = df[col].astype("string").where(df[col].notna(), None)
        df[col] = df[col].apply(
            lambda x: None if x is None or str(x).strip() == "" else str(x).strip()
        )

    con.execute("DROP TABLE IF EXISTS raw.user_signups")
    con.register("_signups_df", df)
    con.execute(
        """
        CREATE TABLE raw.user_signups AS
        SELECT
            user_id::VARCHAR AS user_id,
            signup_date::DATE AS signup_date,
            company_id::VARCHAR AS company_id,
            nullif(lower(referral_source), '')::VARCHAR AS referral_source,
            nullif(lower(utm_source), '')::VARCHAR AS utm_source,
            nullif(lower(utm_medium), '')::VARCHAR AS utm_medium,
            nullif(lower(utm_campaign), '')::VARCHAR AS utm_campaign,
            nullif(lower(first_touch_channel), '')::VARCHAR AS first_touch_channel,
            nullif(lower(last_touch_channel), '')::VARCHAR AS last_touch_channel
        FROM _signups_df
        """
    )
    con.unregister("_signups_df")
    return len(df)


def _load_revenue(con: duckdb.DuckDBPyConnection) -> int:
    df = pd.read_csv(REVENUE_PATH)
    # month stored as DATE first-of-month for easier joins later
    df["month"] = pd.to_datetime(df["month"] + "-01").dt.date
    df["revenue_amount"] = df["revenue_amount"].astype("float64")
    # CSV may load bools as strings
    if df["is_recurring"].dtype == object:
        df["is_recurring"] = df["is_recurring"].astype(str).str.lower().isin(["true", "1", "yes"])
    else:
        df["is_recurring"] = df["is_recurring"].astype(bool)

    con.execute("DROP TABLE IF EXISTS raw.portfolio_revenue")
    con.register("_revenue_df", df)
    con.execute(
        """
        CREATE TABLE raw.portfolio_revenue AS
        SELECT
            revenue_id::VARCHAR AS revenue_id,
            company_id::VARCHAR AS company_id,
            user_id::VARCHAR AS user_id,
            month::DATE AS month,
            revenue_amount::DOUBLE AS revenue_amount,
            is_recurring::BOOLEAN AS is_recurring
        FROM _revenue_df
        """
    )
    con.unregister("_revenue_df")
    return len(df)


def _load_campaigns(con: duckdb.DuckDBPyConnection) -> int:
    df = pd.read_csv(CAMPAIGNS_PATH)
    df["start_date"] = pd.to_datetime(df["start_date"]).dt.date
    df["end_date"] = pd.to_datetime(df["end_date"]).dt.date
    df["budget_usd"] = df["budget_usd"].astype("float64")
    for col in ("campaign_id", "campaign_name", "channel", "target_company_id"):
        df[col] = df[col].astype("string").where(df[col].notna(), None)
        df[col] = df[col].apply(
            lambda x: None if x is None or str(x).strip() == "" else str(x).strip()
        )

    # Helpful raw helper: slug for joining to utm_campaign (matches generate_data.py)
    df["campaign_slug"] = df["campaign_name"].str.lower().str.replace(" ", "_", regex=False)

    con.execute("DROP TABLE IF EXISTS raw.campaign_metadata")
    con.register("_campaigns_df", df)
    con.execute(
        """
        CREATE TABLE raw.campaign_metadata AS
        SELECT
            campaign_id::VARCHAR AS campaign_id,
            campaign_name::VARCHAR AS campaign_name,
            lower(channel)::VARCHAR AS channel,
            budget_usd::DOUBLE AS budget_usd,
            start_date::DATE AS start_date,
            end_date::DATE AS end_date,
            nullif(target_company_id, '')::VARCHAR AS target_company_id,
            campaign_slug::VARCHAR AS campaign_slug
        FROM _campaigns_df
        """
    )
    con.unregister("_campaigns_df")
    return len(df)


def load_all() -> dict[str, int]:
    con = _ensure_warehouse()
    try:
        counts = {
            "content_performance": _load_content(con),
            "user_signups": _load_signups(con),
            "portfolio_revenue": _load_revenue(con),
            "campaign_metadata": _load_campaigns(con),
        }
        # Sanity counts from DuckDB
        verified = {}
        for table in counts:
            verified[table] = con.execute(f"SELECT COUNT(*) FROM raw.{table}").fetchone()[0]
        return verified
    finally:
        con.close()


def main() -> int:
    print(f"Loading raw tables into {WAREHOUSE_PATH}")
    counts = load_all()
    print("Loaded raw tables:")
    for name, n in counts.items():
        print(f"  raw.{name}: {n:,} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
