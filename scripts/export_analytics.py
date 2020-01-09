"""Run analytics/*.sql against DuckDB and write CSV outputs."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from paths import OUTPUTS_DIR, ROOT as PROJECT_ROOT, WAREHOUSE_PATH  # noqa: E402

ANALYTICS_DIR = PROJECT_ROOT / "analytics"


def _strip_sql_comments(sql: str) -> str:
    # Remove full-line -- comments; keep inline SQL intact enough for DuckDB
    lines = []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(line)
    return "\n".join(lines)


def run_analytics() -> list[Path]:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    sql_files = sorted(ANALYTICS_DIR.glob("*.sql"))
    written: list[Path] = []
    con = duckdb.connect(str(WAREHOUSE_PATH))
    try:
        for path in sql_files:
            sql = _strip_sql_comments(path.read_text(encoding="utf-8")).strip()
            if not sql:
                continue
            # Allow multiple statements; take last result set
            statements = [s.strip() for s in sql.split(";") if s.strip()]
            df = None
            for stmt in statements:
                df = con.execute(stmt).fetchdf()
            if df is None:
                continue
            out_name = re.sub(r"\.sql$", ".csv", path.name)
            out_path = OUTPUTS_DIR / out_name
            df.to_csv(out_path, index=False)
            written.append(out_path)
            print(f"  {path.name} → {out_path.name} ({len(df)} rows)")
    finally:
        con.close()
    return written


def main() -> int:
    print(f"Exporting analytics from {WAREHOUSE_PATH}")
    run_analytics()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
