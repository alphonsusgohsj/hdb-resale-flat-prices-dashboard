"""Stage 4a — Export.

Tableau Public cannot read a DuckDB file, so the pipeline's final act is to
write CSVs it *can* connect to:
  * resale_clean.csv          - the full typed fact table, for flexible charts,
                                maps and filters (Tableau does the aggregating).
  * mart_<query>.csv (x4)     - the pre-aggregated analytical results, so the
                                dashboard can surface the SQL work directly.

We use DuckDB's COPY ... TO because it streams straight to disk (fast, no
intermediate pandas frame) and reuses the exact analysis SQL as the source.
"""
from __future__ import annotations

import config
from src.db import connect

ANALYSIS_DIR = config.PROJECT_ROOT / "sql" / "analysis"


def _copy(con, inner_sql: str, out_path) -> None:
    # COPY wraps a single SELECT, so strip the file's trailing semicolon.
    inner = inner_sql.strip().rstrip(";")
    con.execute(f"COPY ({inner}) TO '{out_path}' (HEADER, FORMAT CSV)")


def export_all(con=None) -> list:
    """Write the fact table and the four marts to exports/. Returns paths."""
    owns_connection = con is None
    if owns_connection:
        con = connect()
    config.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    written = []

    fact_path = config.EXPORTS_DIR / "resale_clean.csv"
    _copy(con, "SELECT * FROM main.resale_clean ORDER BY transaction_month", fact_path)
    written.append(fact_path)

    for sql_file in sorted(ANALYSIS_DIR.glob("*.sql")):
        out_path = config.EXPORTS_DIR / f"mart_{sql_file.stem}.csv"
        _copy(con, sql_file.read_text(), out_path)
        written.append(out_path)

    if owns_connection:
        con.close()
    return written


if __name__ == "__main__":
    for path in export_all():
        kb = path.stat().st_size / 1024
        print(f"  wrote {path.relative_to(config.PROJECT_ROOT)}  ({kb:,.0f} KB)")
