# Singapore HDB Resale Flat Prices — end-to-end data pipeline

A descriptive-analytics pipeline over Singapore public-housing resale
transactions: it pulls from the **data.gov.sg** API on a schedule, cleans and
loads into a **DuckDB** analytical warehouse, runs analytical **SQL**, and
publishes CSV extracts for a **Tableau Public** dashboard.

> **Dashboard:** [Tableau Public — alphonsus.goh](https://public.tableau.com/app/profile/alphonsus.goh/vizzes)

Built as a portfolio project to demonstrate each layer of a real pipeline —
ingestion, a raw/clean warehouse split, idempotent incremental loads, and
analytical SQL — end to end.

---

## Architecture

```
data.gov.sg API                     DuckDB warehouse (data/warehouse.duckdb)
(CKAN datastore)          ┌───────────────────────────────────────────┐
      │                   │  raw.resale        (all VARCHAR, verbatim)  │
      │  paginate +       │        │  pandas: type, parse, derive, hash │
      ▼  retry/backoff    │        ▼                                    │
  ingest.py ─────────────▶│  main.resale_clean (typed, deduplicated)    │──┐
                          │  main.ingestion_log (one row per run)       │  │
                          └───────────────────────────────────────────┘  │
                                                                          │ export.py
   Tableau Public  ◀────────  exports/*.csv  ◀────────────────────────────┘
   (dashboard)               (fact table + 4 analytical marts)
```

Stages, one Python module each:

| Stage | Module | What it does |
|---|---|---|
| Ingest | `src/ingest.py` | Pull every row from the API, paginated, with retry/backoff |
| Clean | `src/clean.py` | Cast types, parse `remaining_lease`, derive `price_per_sqm`, compute `row_hash` |
| Load | `src/load.py` | Replace `raw`, idempotently upsert `main`, log the run — in one transaction |
| Export | `src/export.py` | Write the fact table + four marts to `exports/` for Tableau |
| Orchestrate | `run_pipeline.py` | ingest → clean → load → export, the scheduled entrypoint |

---

## Key design decisions (the interview talking points)

- **Raw vs clean split.** `raw.resale` lands the API response verbatim as all
  `VARCHAR`, so ingestion can never fail on a bad cast and the clean table can be
  re-derived without re-hitting the API. `main.resale_clean` is the typed,
  analysis-ready layer.
- **Idempotent incremental loads.** The source is a full monthly snapshot with no
  per-row update key, so each clean row carries `row_hash` = MD5 of its source
  business columns. Loads are an anti-join insert (only unseen hashes), and
  `row_hash` is the primary key. Run the pipeline twice → the second run inserts
  **0** rows. Chosen over a `month > last_loaded` high-water mark because the
  latest month keeps receiving late-registered transactions.
- **Paginate against `total`, not `_links.next`.** The CKAN API emits a `next`
  link on *every* page including the last, so termination is driven by
  `result.total` (with an empty-page backstop). Page size is 10,000 (20,000
  exceeds the API's payload cap).
- **Transactional load.** Raw-replace, clean-upsert and log commit together, so a
  mid-run failure cannot leave a torn warehouse.

---

## Analytical SQL (`sql/analysis/`)

| File | Technique | Question |
|---|---|---|
| `01_price_rank_within_town.sql` | Window functions (`RANK`, `AVG OVER`) | Priciest flat types within each town |
| `02_mom_price_change.sql` | CTE + `LAG` | Month-on-month change in median price |
| `03_lease_cohort.sql` | Cohort analysis | Price-per-sqm by lease-commencement decade |
| `04_top_n_by_segment.sql` | Top-N per group (`QUALIFY`) | Top-5 towns per flat type |

---

## Running it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python run_pipeline.py          # ingest -> clean -> load -> export
```

Outputs: `data/warehouse.duckdb` (the warehouse) and `exports/*.csv` (for
Tableau). Both are gitignored except the small aggregated marts.

**Scheduling.** `.github/workflows/pipeline.yml` runs the pipeline monthly (and
on demand), then commits the refreshed marts back — visible proof the ingestion
runs unattended. Because the source is a full snapshot, each CI run rebuilds the
warehouse from scratch, which is always complete and correct.

**Dashboard.** See [`docs/tableau_dashboard_guide.md`](docs/tableau_dashboard_guide.md)
for the step-by-step Tableau Public build.

---

## Scope

Descriptive analysis only — no prediction, forecasting, hypothesis testing or ML;
no serving API or monitoring layer. The pipeline deliberately ends at analytical
SQL plus a dashboard.

## Data source & licence

Resale flat prices, [data.gov.sg](https://data.gov.sg) (resource
`d_8b84c4ee58e3cfc0ece0d773c8ca6abc`), © Housing & Development Board, published
under the [Singapore Open Data Licence](https://data.gov.sg/open-data-licence).
