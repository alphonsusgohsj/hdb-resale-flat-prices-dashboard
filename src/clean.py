"""Stage 2a — Clean.

Turn the raw string records from the API into a typed, deduplicated DataFrame
that matches main.resale_clean. Every transform here is a deliberate decision
that ingestion deliberately did NOT make.

Key design points to defend:
  * row_hash is computed from the ORIGINAL source strings (not the cast values),
    so the dedup key is stable regardless of how we later type the columns.
  * We drop_duplicates on row_hash within the batch. This is where genuinely
    identical transactions collapse — an accepted, documented trade-off for a
    descriptive dataset with no true transaction id.
  * Casts use errors="coerce" so a bad value becomes NULL and is caught by the
    validation summary, rather than silently crashing the load.
"""
from __future__ import annotations

import hashlib

import pandas as pd

# The business identity of a resale transaction — everything except the CKAN
# _id (a source surrogate we don't trust to be stable across republishes).
BUSINESS_COLS = [
    "month", "town", "flat_type", "block", "street_name", "storey_range",
    "floor_area_sqm", "flat_model", "lease_commence_date", "remaining_lease",
    "resale_price",
]

# Columns of the returned frame, in main.resale_clean order.
CLEAN_COLS = [
    "row_hash", "transaction_month", "town", "flat_type", "block", "street_name",
    "storey_range", "floor_area_sqm", "flat_model", "lease_commence_year",
    "remaining_lease_months", "resale_price", "price_per_sqm",
]


def _row_hash(raw: pd.DataFrame) -> pd.Series:
    """MD5 of the source business columns joined by '|'. Vectorised concat."""
    joined = raw[BUSINESS_COLS[0]].astype(str).str.strip()
    for col in BUSINESS_COLS[1:]:
        joined = joined.str.cat(raw[col].astype(str).str.strip(), sep="|")
    return joined.map(lambda s: hashlib.md5(s.encode("utf-8")).hexdigest())


def _remaining_lease_to_months(series: pd.Series) -> pd.Series:
    """Parse "61 years 04 months" -> 736. Months default to 0 when absent."""
    years = pd.to_numeric(series.str.extract(r"(\d+)\s*year", expand=False), errors="coerce")
    months = pd.to_numeric(series.str.extract(r"(\d+)\s*month", expand=False), errors="coerce").fillna(0)
    return (years * 12 + months).astype("Int64")


def clean_records(records: list[dict]) -> pd.DataFrame:
    """Records (raw strings) -> typed, deduplicated DataFrame."""
    raw = pd.DataFrame.from_records(records)

    out = pd.DataFrame()
    out["row_hash"] = _row_hash(raw)
    out["transaction_month"] = pd.to_datetime(raw["month"], format="%Y-%m")
    out["town"] = raw["town"].astype(str).str.strip()
    out["flat_type"] = raw["flat_type"].astype(str).str.strip()
    out["block"] = raw["block"].astype(str).str.strip()
    out["street_name"] = raw["street_name"].astype(str).str.strip()
    out["storey_range"] = raw["storey_range"].astype(str).str.strip()
    out["floor_area_sqm"] = pd.to_numeric(raw["floor_area_sqm"], errors="coerce")
    out["flat_model"] = raw["flat_model"].astype(str).str.strip()
    out["lease_commence_year"] = pd.to_numeric(raw["lease_commence_date"], errors="coerce").astype("Int64")
    out["remaining_lease_months"] = _remaining_lease_to_months(raw["remaining_lease"])
    out["resale_price"] = pd.to_numeric(raw["resale_price"], errors="coerce")
    out["price_per_sqm"] = (out["resale_price"] / out["floor_area_sqm"]).round(2)

    # Collapse true duplicates within the batch (see module docstring).
    out = out[CLEAN_COLS].drop_duplicates(subset="row_hash").reset_index(drop=True)
    return out


def summarise(df: pd.DataFrame) -> str:
    """A short data-quality report — NULLs after casting and headline ranges."""
    lines = [f"Clean rows: {len(df):,}"]
    null_cols = {c: int(df[c].isna().sum()) for c in df.columns if df[c].isna().any()}
    lines.append(f"NULLs after casting: {null_cols or 'none'}")
    lines.append(
        f"transaction_month: {df['transaction_month'].min().date()} "
        f"-> {df['transaction_month'].max().date()}"
    )
    lines.append(
        f"resale_price: {df['resale_price'].min():,.0f} -> {df['resale_price'].max():,.0f}"
    )
    lines.append(
        f"remaining_lease_months: {int(df['remaining_lease_months'].min())} "
        f"-> {int(df['remaining_lease_months'].max())}"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    # Isolated check on a tiny sample — no full pull, no DB.
    import requests

    from src import ingest

    with requests.Session() as session:
        page = ingest._fetch_page(session, offset=0, limit=5)
    df = clean_records(page["records"])
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    print(df.to_string(index=False))
    print("\n--- dtypes ---")
    print(df.dtypes)
    print("\n--- summary ---")
    print(summarise(df))
