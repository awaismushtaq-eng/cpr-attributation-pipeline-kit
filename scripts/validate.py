"""
Validate source data before loading into DuckDB.

Hard failures abort the pipeline (missing files, broken referential integrity,
invalid dates/amounts). Soft warnings report known messy attribution
characteristics without failing — those are handled downstream in dbt.
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from paths import (
    CAMPAIGNS_PATH,
    CONTENT_PATH,
    KNOWN_CHANNELS,
    KNOWN_COMPANIES,
    OUTPUTS_DIR,
    REVENUE_PATH,
    SIGNUPS_PATH,
)


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def _parse_date(value: str, fmt: str = "%Y-%m-%d") -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, fmt)
    except ValueError:
        return None


def _parse_month(value: str) -> datetime | None:
    return _parse_date(value, "%Y-%m")


def _is_blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load_signups(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict) or "signups" not in payload:
        raise ValueError("user_signups.json must be an object with a 'signups' array")
    return payload["signups"]


def _campaign_slug(name: str) -> str:
    """Match generate_data.py: name.lower().replace(' ', '_')."""
    return name.strip().lower().replace(" ", "_")


def validate_files_exist(report: ValidationReport) -> None:
    for path in (CONTENT_PATH, SIGNUPS_PATH, REVENUE_PATH, CAMPAIGNS_PATH):
        if not path.exists():
            report.error(f"Missing required data file: {path}")


def validate_content(rows: list[dict[str, str]], report: ValidationReport) -> None:
    report.stats["content_rows"] = len(rows)
    if not rows:
        report.error("content_performance.csv is empty")
        return

    ids = [r["content_id"] for r in rows]
    if len(ids) != len(set(ids)):
        report.error("Duplicate content_id values in content_performance.csv")

    missing_utm_source = 0
    missing_utm_campaign = 0
    bad_dates = 0
    bad_metrics = 0
    unknown_channels = 0

    for r in rows:
        if _is_blank(r.get("utm_source")):
            missing_utm_source += 1
        if _is_blank(r.get("utm_campaign")):
            missing_utm_campaign += 1
        if _parse_date(r.get("publish_date", "")) is None:
            bad_dates += 1
        try:
            views = int(r["views"])
            clicks = int(r["clicks"])
            if views < 0 or clicks < 0 or clicks > views * 10:
                # clicks > views can happen; only flag extreme outliers
                if views < 0 or clicks < 0:
                    bad_metrics += 1
        except (KeyError, ValueError, TypeError):
            bad_metrics += 1
        channel = (r.get("channel") or "").strip().lower()
        if channel and channel not in KNOWN_CHANNELS:
            unknown_channels += 1

    if bad_dates:
        report.error(f"content_performance: {bad_dates} rows have invalid publish_date")
    if bad_metrics:
        report.error(f"content_performance: {bad_metrics} rows have invalid views/clicks")
    if unknown_channels:
        report.warn(f"content_performance: {unknown_channels} rows have unexpected channel values")

    pct_missing_source = missing_utm_source / len(rows)
    pct_missing_campaign = missing_utm_campaign / len(rows)
    report.stats["content_missing_utm_source_pct"] = round(pct_missing_source, 4)
    report.stats["content_missing_utm_campaign_pct"] = round(pct_missing_campaign, 4)
    report.warn(
        f"content_performance: {missing_utm_source}/{len(rows)} "
        f"({pct_missing_source:.1%}) missing utm_source"
    )
    report.warn(
        f"content_performance: {missing_utm_campaign}/{len(rows)} "
        f"({pct_missing_campaign:.1%}) missing utm_campaign"
    )

    dates = [_parse_date(r["publish_date"]) for r in rows if _parse_date(r.get("publish_date", ""))]
    if dates:
        report.stats["content_date_min"] = min(dates).date().isoformat()
        report.stats["content_date_max"] = max(dates).date().isoformat()


def validate_signups(
    rows: list[dict[str, Any]],
    campaign_slugs: set[str],
    report: ValidationReport,
) -> set[str]:
    report.stats["signup_rows"] = len(rows)
    if not rows:
        report.error("user_signups.json has no signup records")
        return set()

    ids = [r["user_id"] for r in rows]
    if len(ids) != len(set(ids)):
        report.error("Duplicate user_id values in user_signups.json")

    missing_utm_source = 0
    missing_utm_campaign = 0
    touch_conflicts = 0
    referral_utm_mismatch = 0
    unknown_campaigns = 0
    bad_dates = 0
    bad_companies = 0
    utm_vs_touch_mismatch = 0

    for r in rows:
        if _is_blank(r.get("utm_source")):
            missing_utm_source += 1
        if _is_blank(r.get("utm_campaign")):
            missing_utm_campaign += 1
        else:
            slug = str(r["utm_campaign"]).strip().lower()
            if slug not in campaign_slugs:
                unknown_campaigns += 1

        first = (r.get("first_touch_channel") or "").strip().lower()
        last = (r.get("last_touch_channel") or "").strip().lower()
        if first and last and first != last:
            touch_conflicts += 1

        utm_source = (r.get("utm_source") or "").strip().lower()
        referral = (r.get("referral_source") or "").strip().lower()
        # Soft: non-channel referral alongside a channel UTM, or channel referral ≠ UTM
        if referral and utm_source:
            if referral in {"direct", "word_of_mouth", "organic"} and utm_source in KNOWN_CHANNELS - {
                "organic",
                "referral",
            }:
                referral_utm_mismatch += 1
            elif referral in KNOWN_CHANNELS and referral != utm_source:
                referral_utm_mismatch += 1

        if utm_source and first and utm_source not in {first, last} and utm_source in KNOWN_CHANNELS:
            utm_vs_touch_mismatch += 1

        if _parse_date(str(r.get("signup_date", ""))) is None:
            bad_dates += 1
        if r.get("company_id") not in KNOWN_COMPANIES:
            bad_companies += 1

    if bad_dates:
        report.error(f"user_signups: {bad_dates} rows have invalid signup_date")
    if bad_companies:
        report.error(f"user_signups: {bad_companies} rows have unknown company_id")

    n = len(rows)
    report.stats["signups_missing_utm_source_pct"] = round(missing_utm_source / n, 4)
    report.stats["signups_missing_utm_campaign_pct"] = round(missing_utm_campaign / n, 4)
    report.stats["signups_first_last_conflict_pct"] = round(touch_conflicts / n, 4)
    report.stats["signups_referral_utm_mismatch_pct"] = round(referral_utm_mismatch / n, 4)
    report.stats["signups_utm_vs_touch_mismatch_pct"] = round(utm_vs_touch_mismatch / n, 4)
    report.stats["signups_unknown_utm_campaign_count"] = unknown_campaigns

    report.warn(f"user_signups: {missing_utm_source}/{n} ({missing_utm_source / n:.1%}) missing utm_source")
    report.warn(
        f"user_signups: {missing_utm_campaign}/{n} ({missing_utm_campaign / n:.1%}) missing utm_campaign"
    )
    report.warn(
        f"user_signups: {touch_conflicts}/{n} ({touch_conflicts / n:.1%}) "
        "first_touch_channel != last_touch_channel"
    )
    report.warn(
        f"user_signups: {referral_utm_mismatch}/{n} ({referral_utm_mismatch / n:.1%}) "
        "referral_source conflicts with UTM/touch channels"
    )
    if utm_vs_touch_mismatch:
        report.warn(
            f"user_signups: {utm_vs_touch_mismatch}/{n} ({utm_vs_touch_mismatch / n:.1%}) "
            "utm_source differs from both first and last touch"
        )
    if unknown_campaigns:
        report.warn(
            f"user_signups: {unknown_campaigns} non-null utm_campaign values "
            "do not match a known campaign slug (will be left unjoined)"
        )

    dates = [
        _parse_date(str(r["signup_date"]))
        for r in rows
        if _parse_date(str(r.get("signup_date", "")))
    ]
    if dates:
        report.stats["signup_date_min"] = min(dates).date().isoformat()
        report.stats["signup_date_max"] = max(dates).date().isoformat()

    return set(ids)


def validate_revenue(rows: list[dict[str, str]], signup_users: set[str], report: ValidationReport) -> None:
    report.stats["revenue_rows"] = len(rows)
    if not rows:
        report.error("portfolio_revenue.csv is empty")
        return

    ids = [r["revenue_id"] for r in rows]
    if len(ids) != len(set(ids)):
        report.error("Duplicate revenue_id values in portfolio_revenue.csv")

    orphan_users = 0
    bad_months = 0
    bad_amounts = 0
    bad_companies = 0

    for r in rows:
        if r.get("user_id") not in signup_users:
            orphan_users += 1
        if _parse_month(r.get("month", "")) is None:
            bad_months += 1
        try:
            amount = float(r["revenue_amount"])
            if amount < 0:
                bad_amounts += 1
        except (KeyError, ValueError, TypeError):
            bad_amounts += 1
        if r.get("company_id") not in KNOWN_COMPANIES:
            bad_companies += 1

    if orphan_users:
        report.error(
            f"portfolio_revenue: {orphan_users} rows reference user_id values "
            "missing from user_signups (referential integrity failure)"
        )
    if bad_months:
        report.error(f"portfolio_revenue: {bad_months} rows have invalid month (expected YYYY-MM)")
    if bad_amounts:
        report.error(f"portfolio_revenue: {bad_amounts} rows have invalid/negative revenue_amount")
    if bad_companies:
        report.error(f"portfolio_revenue: {bad_companies} rows have unknown company_id")

    # Soft: signup users with no revenue (should be rare in this dataset)
    rev_users = {r["user_id"] for r in rows}
    missing_rev = len(signup_users - rev_users)
    if missing_rev:
        report.warn(f"referential: {missing_rev} signup users have no revenue rows")

    months = [_parse_month(r["month"]) for r in rows if _parse_month(r.get("month", ""))]
    if months:
        report.stats["revenue_month_min"] = min(months).strftime("%Y-%m")
        report.stats["revenue_month_max"] = max(months).strftime("%Y-%m")
    report.stats["revenue_users"] = len(rev_users)


def validate_campaigns(rows: list[dict[str, str]], report: ValidationReport) -> set[str]:
    report.stats["campaign_rows"] = len(rows)
    if not rows:
        report.error("campaign_metadata.csv is empty")
        return set()

    ids = [r["campaign_id"] for r in rows]
    if len(ids) != len(set(ids)):
        report.error("Duplicate campaign_id values in campaign_metadata.csv")

    bad_dates = 0
    inverted_ranges = 0
    bad_budget = 0
    null_targets = 0

    for r in rows:
        start = _parse_date(r.get("start_date", ""))
        end = _parse_date(r.get("end_date", ""))
        if start is None or end is None:
            bad_dates += 1
        elif end < start:
            inverted_ranges += 1
        try:
            if float(r["budget_usd"]) < 0:
                bad_budget += 1
        except (KeyError, ValueError, TypeError):
            bad_budget += 1
        if _is_blank(r.get("target_company_id")):
            null_targets += 1
        elif r.get("target_company_id") not in KNOWN_COMPANIES:
            report.error(
                f"campaign_metadata: campaign {r.get('campaign_id')} has unknown "
                f"target_company_id={r.get('target_company_id')}"
            )

    if bad_dates:
        report.error(f"campaign_metadata: {bad_dates} rows have invalid start/end dates")
    if inverted_ranges:
        report.error(f"campaign_metadata: {inverted_ranges} rows have end_date < start_date")
    if bad_budget:
        report.error(f"campaign_metadata: {bad_budget} rows have invalid/negative budget_usd")
    if null_targets:
        report.warn(
            f"campaign_metadata: {null_targets}/{len(rows)} campaigns have null target_company_id "
            "(portfolio-wide campaigns)"
        )

    slugs = {_campaign_slug(r["campaign_name"]) for r in rows}
    report.stats["campaign_slugs"] = sorted(slugs)
    return slugs


def validate_date_window(report: ValidationReport) -> None:
    """Ensure core event windows are coherent across sources."""
    cmin = report.stats.get("content_date_min")
    cmax = report.stats.get("content_date_max")
    smin = report.stats.get("signup_date_min")
    smax = report.stats.get("signup_date_max")
    rmin = report.stats.get("revenue_month_min")
    rmax = report.stats.get("revenue_month_max")

    if cmin and smin and cmin > smax:
        report.error("Date range: all content publish dates fall after all signup dates")
    if smin and rmax and smin[:7] > rmax:
        report.error("Date range: signup window starts after last revenue month")
    if rmin and rmax and rmin > rmax:
        report.error("Date range: revenue month min > max")

    report.stats["date_window"] = {
        "content": [cmin, cmax],
        "signups": [smin, smax],
        "revenue_months": [rmin, rmax],
    }


def run_validation() -> ValidationReport:
    report = ValidationReport()
    validate_files_exist(report)
    if not report.ok:
        return report

    content = _load_csv(CONTENT_PATH)
    campaigns = _load_csv(CAMPAIGNS_PATH)
    try:
        signups = _load_signups(SIGNUPS_PATH)
    except (json.JSONDecodeError, ValueError) as exc:
        report.error(f"Failed to parse user_signups.json: {exc}")
        return report
    revenue = _load_csv(REVENUE_PATH)

    campaign_slugs = validate_campaigns(campaigns, report)
    validate_content(content, report)
    signup_users = validate_signups(signups, campaign_slugs, report)
    validate_revenue(revenue, signup_users, report)
    validate_date_window(report)
    return report


def print_report(report: ValidationReport) -> None:
    print("\n--- Validation report ---")
    print(f"Status: {'PASS' if report.ok else 'FAIL'}")
    print("\nStats:")
    for key, value in report.stats.items():
        if key == "campaign_slugs":
            print(f"  {key}: {len(value)} slugs")
        else:
            print(f"  {key}: {value}")
    if report.warnings:
        print(f"\nWarnings ({len(report.warnings)}):")
        for w in report.warnings:
            print(f"  [warn] {w}")
    if report.errors:
        print(f"\nErrors ({len(report.errors)}):")
        for e in report.errors:
            print(f"  [error] {e}")
    print("--- end validation ---\n")


def write_report(report: ValidationReport) -> Path:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUTS_DIR / "validation_report.json"
    payload = {
        "ok": report.ok,
        "errors": report.errors,
        "warnings": report.warnings,
        "stats": report.stats,
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


def main() -> int:
    report = run_validation()
    print_report(report)
    path = write_report(report)
    print(f"Wrote {path}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
