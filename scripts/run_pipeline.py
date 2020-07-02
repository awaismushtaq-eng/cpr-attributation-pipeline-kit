"""
End-to-end local pipeline orchestrator.

  1. Validate source data
  2. Load raw tables into DuckDB
  3. dbt run + dbt test
  4. Python company forecasting
  5. Export analytics SQL sample outputs
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
DBT_DIR = ROOT / "dbt_project"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _dbt_env() -> dict[str, str]:
    env = os.environ.copy()
    env["DUCKDB_PATH"] = str(ROOT / "warehouse" / "warehouse.duckdb")
    return env


def run_dbt(args: list[str]) -> int:
    cmd = [
        "dbt",
        *args,
        "--project-dir",
        str(DBT_DIR),
        "--profiles-dir",
        str(DBT_DIR),
    ]
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(ROOT), env=_dbt_env()).returncode


def main() -> int:
    print("=" * 60)
    print("Revenue Attribution Pipeline")
    print("=" * 60)
    print(f"Project root: {ROOT}")
    print()

    from validate import print_report, run_validation, write_report

    print("[1/5] Validating source data...")
    report = run_validation()
    print_report(report)
    report_path = write_report(report)
    print(f"Wrote {report_path}")
    if not report.ok:
        print("Validation failed — aborting.")
        return 1

    print("[2/5] Loading raw tables into DuckDB...")
    from load_raw import load_all
    from paths import WAREHOUSE_PATH

    counts = load_all()
    print(f"Warehouse: {WAREHOUSE_PATH}")
    for name, n in counts.items():
        print(f"  raw.{name}: {n:,} rows")

    print()
    print("[3/5] Running dbt models + tests...")
    if run_dbt(["run"]) != 0:
        print("dbt run failed.")
        return 1
    if run_dbt(["test"]) != 0:
        print("dbt test failed.")
        return 1

    print()
    print("[4/5] Python company forecasting...")
    sys.path.insert(0, str(ROOT / "forecasting"))
    from forecast import run_forecast

    run_forecast()

    print()
    print("[5/5] Exporting analytics SQL outputs...")
    from export_analytics import run_analytics

    run_analytics()

    print()
    print("Pipeline complete.")
    print("Dashboard: streamlit run dashboard/app.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
