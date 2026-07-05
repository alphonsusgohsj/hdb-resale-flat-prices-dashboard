# Tableau Public dashboard — build guide

Tableau Public cannot read a DuckDB file, so it connects to the CSVs the pipeline
writes to `exports/`. Run `python run_pipeline.py` first to (re)generate them.

The guide is deliberately prescriptive: every sheet names its **form** (chart
type), why that form fits the data's job, the **fields** to drop on each shelf,
and any **caveat** to annotate. Follow it top to bottom and you get a coherent
five-sheet dashboard.

---

## 1. Connect the data

1. Open **Tableau Public Desktop → Connect → Text file** → select
   `exports/resale_clean.csv` (the full 234k-row fact table).
2. Add the four `mart_*.csv` files as **separate data sources** (Data → New Data
   Source → Text file). They are pre-aggregated, so keep them independent — do
   **not** join them to the fact table.
3. On the fact source, confirm Tableau's inferred types:
   `transaction_month` → **Date**, `resale_price` / `price_per_sqm` /
   `floor_area_sqm` → **Number**, everything else **String**. Fix any it guessed
   wrong (it sometimes reads `block` as a number).

**Why two kinds of source?** The fact table lets Tableau aggregate flexibly
(trends, maps, ad-hoc filters); the marts let the dashboard surface the exact SQL
you wrote without re-deriving it in Tableau. Reviewers see both the raw grain and
the analytical outputs.

---

## 2. One global colour convention (do this once, first)

`flat_type` is the dimension that recurs across sheets. Assign it **one fixed,
colour-blind-safe palette and reuse it everywhere** — colour must follow the
entity, never its rank, so a filter never repaints the survivors.

- Drag `flat_type` to Colour on any sheet → Edit Colours → choose the built-in
  **"Color Blind"** palette → **Assign Palette** → **OK**.
- Right-click the `flat_type` colour legend → **Use as Filter** is off for now;
  we make it a dashboard-wide filter later.

Rules to hold to (from the dataviz method):
- **One axis per chart.** Never put price and transaction-count on twin y-axes —
  use two charts, or show volume as tooltip/size. Dual-axis is the single most
  common charting mistake.
- **Sequential = one hue, light→dark** for magnitude (heatmap, cohort bars).
- **Legend present for ≥ 2 series; recessive gridlines; label selectively**, never
  a number on every mark.

---

## 3. The five sheets

### Sheet 0 — KPI tiles (headline numbers, not a chart)
The data's job is a single headline, so the right "form" is a **stat tile**, not a
plot. Build three as separate sheets (fact source), each a big BAN (big-ass
number):
- **Latest median price** — `MEDIAN([resale_price])`, filtered to the max month.
- **Transactions (12m)** — `COUNT` over the trailing 12 months.
- **YoY median change %** — a calculated field comparing the latest month's median
  to twelve months prior.
Format: large number, muted caption, no axes.

### Sheet 1 — National median price over time  *(mart_02 or fact)*
- **Form:** line chart — the job is change-over-time.
- **Shelf:** `transaction_month` (continuous, Month) → Columns;
  `median_price` → Rows. Single series → **no legend**, the title names it.
- **Caveat to annotate:** the **latest month is partial** (month-to-date), so its
  point is noisy. Either add a reference annotation, or filter it out with
  `transaction_month < DATETRUNC('month', TODAY())`.

### Sheet 2 — Lease-commencement cohorts  *(mart_03)*
- **Form:** bar chart — magnitude across ordered categories.
- **Shelf:** `lease_decade` (discrete) → Columns; `avg_psm` → Rows.
- **Colour:** sequential single hue (e.g. Blue), light→dark by decade — reinforces
  the ordering. Add `avg_remaining_lease_years` to Tooltip.
- **Story it tells:** newer leases → more years left → higher price-per-sqm (the
  lease-decay effect).

### Sheet 3 — Price rank within town  *(mart_01)*
- **Form:** highlight table / heatmap — magnitude across **two** categoricals.
- **Shelf:** `town` → Rows, `flat_type` → Columns; `avg_psm` → Colour (sequential
  hue) and → Label. Mark type = **Square**.
- **Reading it:** each cell is a town×flat-type average; the colour gradient makes
  the priciest segments pop. Complements the ranked bars below.

### Sheet 4 — Top-5 towns per flat type  *(mart_04)*
- **Form:** horizontal ranked bars — the job is ranked magnitude.
- **Shelf:** `median_price` → Columns; `town` → Rows, **sorted descending** by
  `median_price`; add a **filter on `flat_type`** shown as a single-select
  dropdown so the reader picks the segment.
- Because the mart already keeps only rank ≤ 5 (and drops thin segments), each
  flat type shows a clean top 5.

*(Optional stretch — a choropleth map of median price by town. Skip unless you
have time: Tableau does not geocode HDB town names out of the box, so it needs a
custom lat/long lookup. Not worth the rabbit hole for a first pass.)*

---

## 4. Assemble the dashboard

- New Dashboard, size **Automatic** or fixed 1200×900.
- **Top row:** the three KPI tiles side by side.
- **Filter row (one row, above the charts):** `transaction_month` range,
  `town` (multi-select), `flat_type` (single-select). Set each filter to **Apply
  to → All using this data source** so they act dashboard-wide. Keeping filters in
  one row above the charts is the expected place for readers to look.
- **Body:** 2×2 grid — trend (Sheet 1) and cohorts (Sheet 2) on top, heatmap
  (Sheet 3) and top-5 bars (Sheet 4) below.
- Give it a title, a one-line data-source credit ("data.gov.sg, resale flat
  prices, refreshed monthly"), and the partial-month caveat as a small footnote.

---

## 5. Publish

- **File → Save to Tableau Public** (needs a free Tableau Public account). This
  uploads an **embedded extract** — the data is baked into the published viz, so
  the dashboard keeps working without the local CSVs.
- Copy the public URL into the project `README.md`.
- To refresh next month: re-run the pipeline, then re-publish (Tableau Public's
  auto-refresh only works from Google Sheets; a manual re-publish is fine at this
  cadence).
