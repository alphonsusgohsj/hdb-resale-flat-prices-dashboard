"""Stage 2b — Load.

Write the raw snapshot and upsert the clean rows into DuckDB, then record the
run in the ingestion log. The whole thing runs in ONE transaction so a failure
half-way cannot leave the warehouse in a torn state.

The idempotency mechanism (the interview centrepiece):
  * raw.resale is REPLACED each run (latest snapshot only).
  * main.resale_clean is inserted via an anti-join — only rows whose row_hash is
    not already present. Run the pipeline twice and the second run inserts 0.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

import config

SCHEMA_PATH = config.PROJECT_ROOT / "sql" / "schema.sql"

# Raw string columns to land verbatim (source_id is the renamed CKAN _id).
_RAW_STRING_COLS = [
    "month", "town", "flat_type", "block", "street_name", "storey_range",
    "floor_area_sqm", "flat_model", "lease_commence_date", "remaining_lease",
    "resale_price", "source_id",
]


def apply_schema(con) -> None:
    """Create schemas/tables if they do not yet exist (idempotent DDL)."""
    con.execute(SCHEMA_PATH.read_text())


def _build_raw_frame(records: list[dict], batch_id: str) -> pd.DataFrame:
    """Records -> a frame shaped exactly like raw.resale (all strings)."""
    raw = pd.DataFrame.from_records(records).rename(columns={"_id": "source_id"})
    for col in _RAW_STRING_COLS:
        raw[col] = raw[col].astype(str)
    raw["_ingested_at"] = pd.Timestamp.now()
    raw["_batch_id"] = batch_id
    return raw


def load_all(con, records, clean_df, source_total, batch_id) -> dict:
    """Load raw + clean + log inside a single transaction. Returns run stats."""
    rows_fetched = len(records)
    con.execute("BEGIN TRANSACTION")
    try:
        # 1) RAW — replace with the latest snapshot.
        raw_df = _build_raw_frame(records, batch_id)
        con.register("raw_df", raw_df)
        con.execute("DELETE FROM raw.resale")
        con.execute(
            """
            INSERT INTO raw.resale
                (month, town, flat_type, block, street_name, storey_range,
                 floor_area_sqm, flat_model, lease_commence_date, remaining_lease,
                 resale_price, source_id, _ingested_at, _batch_id)
            SELECT month, town, flat_type, block, street_name, storey_range,
                   floor_area_sqm, flat_model, lease_commence_date, remaining_lease,
                   resale_price, source_id, _ingested_at, _batch_id
            FROM raw_df
            """
        )

        # 2) CLEAN — idempotent anti-join upsert.
        con.register("clean_df", clean_df)
        before = con.execute("SELECT count(*) FROM main.resale_clean").fetchone()[0]
        con.execute(
            """
            INSERT INTO main.resale_clean (
                row_hash, transaction_month, town, flat_type, block, street_name,
                storey_range, floor_area_sqm, flat_model, lease_commence_year,
                remaining_lease_months, resale_price, price_per_sqm, _loaded_at
            )
            SELECT
                c.row_hash, CAST(c.transaction_month AS DATE), c.town, c.flat_type,
                c.block, c.street_name, c.storey_range, c.floor_area_sqm, c.flat_model,
                c.lease_commence_year, c.remaining_lease_months, c.resale_price,
                c.price_per_sqm, current_timestamp
            FROM clean_df c
            WHERE NOT EXISTS (
                SELECT 1 FROM main.resale_clean t WHERE t.row_hash = c.row_hash
            )
            """
        )
        after = con.execute("SELECT count(*) FROM main.resale_clean").fetchone()[0]
        rows_inserted = after - before

        # 3) LOG — a durable record that the run happened.
        con.execute(
            "INSERT INTO main.ingestion_log VALUES (?, ?, ?, ?, ?, ?, ?)",
            [batch_id, datetime.now(), source_total, rows_fetched, rows_inserted,
             "success", None],
        )
        con.execute("COMMIT")
        return {
            "rows_fetched": rows_fetched,
            "rows_deduped_batch": rows_fetched - len(clean_df),
            "rows_inserted": rows_inserted,
            "clean_total": after,
        }
    except Exception as exc:
        con.execute("ROLLBACK")
        # Record the failure in its own autocommit statement.
        con.execute(
            "INSERT INTO main.ingestion_log VALUES (?, ?, ?, ?, ?, ?, ?)",
            [batch_id, datetime.now(), source_total, rows_fetched, 0,
             "failed", str(exc)[:500]],
        )
        raise
