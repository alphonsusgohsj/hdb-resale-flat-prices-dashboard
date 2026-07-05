"""Single entrypoint: ingest -> clean -> load. This is what the scheduler calls.

Keeping orchestration in one readable place means the pipeline's order of
operations is obvious, and there is exactly one thing to run (locally or in CI).
"""
from __future__ import annotations

import time
from datetime import datetime

import config
from src import clean, ingest, load
from src.db import connect


def run() -> dict:
    batch_id = datetime.now().strftime("%Y%m%dT%H%M%S")
    print(f"=== pipeline run {batch_id} ===")

    # Stage 1 — ingest
    t0 = time.time()
    records, source_total = ingest.fetch_all_records()
    print(f"[ingest] {len(records):,} records in {time.time() - t0:.1f}s")

    # Stage 2a — clean
    clean_df = clean.clean_records(records)
    print("[clean]")
    print("  " + clean.summarise(clean_df).replace("\n", "\n  "))

    # Stage 2b — load
    con = connect()
    try:
        load.apply_schema(con)
        stats = load.load_all(con, records, clean_df, source_total, batch_id)
    finally:
        con.close()

    print(
        f"[load] fetched={stats['rows_fetched']:,} "
        f"deduped_in_batch={stats['rows_deduped_batch']:,} "
        f"inserted={stats['rows_inserted']:,} "
        f"clean_total={stats['clean_total']:,}"
    )
    print(f"=== done in {time.time() - t0:.1f}s ===")
    return stats


if __name__ == "__main__":
    run()
