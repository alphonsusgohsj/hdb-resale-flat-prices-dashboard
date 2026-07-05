"""Stage 1 — Ingest.

Single responsibility: pull the full resale-price dataset from the data.gov.sg
API *safely*. "Safely" means paginate through every row and survive a flaky or
partial API call via retry with exponential backoff.

Design notes worth defending in an interview:
  * We paginate against ``result.total``, NOT ``_links.next``. The CKAN API emits
    a ``next`` link unconditionally — even on the final page — so trusting it
    would loop forever. Stopping when we have fetched ``total`` rows (with an
    empty-page backstop) is the reliable termination condition.
  * Records are returned exactly as the API delivers them (all strings). Type
    casting is deliberately the clean layer's job, so a surprise value can never
    crash ingestion.
"""
from __future__ import annotations

import time
from typing import Any

import requests

import config


class IngestionError(RuntimeError):
    """Raised when the API cannot be read after exhausting retries."""


def _fetch_page(session: requests.Session, offset: int, limit: int) -> dict[str, Any]:
    """Fetch one page, retrying with exponential backoff.

    Retries on transport errors, non-200 responses, unparseable bodies, and
    CKAN ``success: false`` payloads (e.g. transient validation errors). Raises
    :class:`IngestionError` once all attempts are exhausted.
    """
    params = {"resource_id": config.RESOURCE_ID, "limit": limit, "offset": offset}
    last_error: Exception | None = None

    for attempt in range(config.MAX_RETRIES):
        try:
            resp = session.get(
                config.API_BASE_URL,
                params=params,
                timeout=config.REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            payload = resp.json()
            if not payload.get("success"):
                raise IngestionError(f"API returned success=false: {payload.get('error')}")
            return payload["result"]
        except (requests.RequestException, IngestionError, ValueError) as exc:
            last_error = exc
            if attempt < config.MAX_RETRIES - 1:
                sleep_for = config.BACKOFF_BASE_SECONDS * (2 ** attempt)
                print(
                    f"  [warn] page offset={offset} attempt {attempt + 1} failed: {exc} "
                    f"-> retrying in {sleep_for:.1f}s"
                )
                time.sleep(sleep_for)

    raise IngestionError(
        f"Failed to fetch page offset={offset} after {config.MAX_RETRIES} attempts: {last_error}"
    )


def fetch_all_records(page_size: int | None = None) -> tuple[list[dict[str, Any]], int]:
    """Pull every record from the dataset.

    Returns ``(records, source_total)`` where ``source_total`` is the row count
    the API reported — kept so the load stage can log fetched-vs-expected.
    """
    page_size = page_size or config.PAGE_SIZE
    records: list[dict[str, Any]] = []
    offset = 0
    source_total: int | None = None

    with requests.Session() as session:
        while True:
            result = _fetch_page(session, offset, page_size)
            if source_total is None:
                source_total = result["total"]
                print(f"Source reports {source_total:,} rows; paging by {page_size:,}")

            page = result["records"]
            if not page:  # empty-page backstop
                break
            records.extend(page)
            print(f"  fetched {len(records):,}/{source_total:,}")

            offset += page_size
            if offset >= source_total:  # primary termination condition
                break

    return records, source_total or 0


if __name__ == "__main__":
    start = time.time()
    recs, total = fetch_all_records()
    elapsed = time.time() - start
    print("-" * 50)
    print(f"Fetched {len(recs):,} records (source total {total:,}) in {elapsed:.1f}s")
    assert recs, "No records returned"
    print("Sample row:", recs[0])
    if len(recs) != total:
        print(f"[warn] fetched count != source total ({len(recs):,} vs {total:,})")
    else:
        print("Row count matches source total ✓")
