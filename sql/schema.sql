-- ============================================================================
-- Warehouse schema for the HDB resale pipeline.
-- Two layers in one DuckDB file, separated by schema:
--   raw   -> the API response landed verbatim (all VARCHAR) + ingest metadata
--   main  -> typed, deduplicated, analysis-ready + an operational ingestion log
-- Idempotent: everything is CREATE ... IF NOT EXISTS, so re-running is safe.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS raw;

-- ---------- RAW LAYER: land the API exactly as received --------------------
-- Every business column is VARCHAR so ingestion can NEVER fail on a bad cast;
-- type decisions are deferred to the clean layer. Holds the latest snapshot
-- only (replace-on-run) — the run history lives in main.ingestion_log.
CREATE TABLE IF NOT EXISTS raw.resale (
    month                VARCHAR,   -- "2017-01"
    town                 VARCHAR,
    flat_type            VARCHAR,
    block                VARCHAR,
    street_name          VARCHAR,
    storey_range         VARCHAR,   -- "10 TO 12"
    floor_area_sqm       VARCHAR,
    flat_model           VARCHAR,
    lease_commence_date  VARCHAR,   -- "1979"
    remaining_lease      VARCHAR,   -- "61 years 04 months"
    resale_price         VARCHAR,   -- "232000"
    source_id            VARCHAR,   -- CKAN _id from the API
    _ingested_at         TIMESTAMP,
    _batch_id            VARCHAR
);

-- ---------- CLEAN LAYER: typed, deduplicated, analysis-ready ----------------
-- row_hash is the PRIMARY KEY: an MD5 of the source business columns. It is
-- both the dedup key (idempotent loads) and a DB-enforced uniqueness guarantee.
CREATE TABLE IF NOT EXISTS main.resale_clean (
    row_hash               VARCHAR PRIMARY KEY,
    transaction_month      DATE,          -- "2017-01" -> 2017-01-01
    town                   VARCHAR,
    flat_type              VARCHAR,
    block                  VARCHAR,
    street_name            VARCHAR,
    storey_range           VARCHAR,
    floor_area_sqm         DOUBLE,
    flat_model             VARCHAR,
    lease_commence_year    INTEGER,
    remaining_lease_months INTEGER,       -- "61 years 04 months" -> 736
    resale_price           DECIMAL(10,2), -- money: exact, no float rounding
    price_per_sqm          DOUBLE,        -- derived: resale_price / floor_area_sqm
    _loaded_at             TIMESTAMP
);

-- ---------- OPERATIONAL: make each run demonstrable ------------------------
CREATE TABLE IF NOT EXISTS main.ingestion_log (
    batch_id           VARCHAR,
    run_at             TIMESTAMP,
    source_total_rows  INTEGER,   -- what the API reported as 'total'
    rows_fetched       INTEGER,   -- rows actually pulled this run
    rows_inserted      INTEGER,   -- NEW rows after dedup (0 on a repeat run)
    status             VARCHAR,   -- 'success' / 'failed'
    message            VARCHAR
);
