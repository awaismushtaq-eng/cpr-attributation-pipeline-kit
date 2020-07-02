"""Shared filesystem paths for pipeline scripts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
WAREHOUSE_DIR = ROOT / "warehouse"
WAREHOUSE_PATH = WAREHOUSE_DIR / "warehouse.duckdb"
OUTPUTS_DIR = ROOT / "outputs"

CONTENT_PATH = DATA_DIR / "content_performance.csv"
SIGNUPS_PATH = DATA_DIR / "user_signups.json"
REVENUE_PATH = DATA_DIR / "portfolio_revenue.csv"
CAMPAIGNS_PATH = DATA_DIR / "campaign_metadata.csv"

KNOWN_COMPANIES = {"CTC-001", "CTC-002", "CTC-003", "CTC-004"}
KNOWN_CHANNELS = {
    "youtube",
    "twitter",
    "instagram",
    "newsletter",
    "podcast",
    "blog",
    "organic",
    "referral",
}
