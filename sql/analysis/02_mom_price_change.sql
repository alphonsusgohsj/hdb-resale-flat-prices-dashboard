-- ============================================================================
-- 02 - Month-on-month price change  (technique: CTE + LAG)
-- ----------------------------------------------------------------------------
-- National median resale price per month, and its month-on-month change.
--   monthly  CTE  -> collapse transactions to one row per month
--   LAG()         -> pull the previous month's median onto the current row
-- Median (not mean) resists the skew from a handful of very expensive flats.
-- ============================================================================
WITH monthly AS (
    SELECT
        transaction_month,
        count(*)                       AS n_transactions,
        round(median(resale_price), 0) AS median_price
    FROM main.resale_clean
    GROUP BY transaction_month
),
with_lag AS (
    SELECT
        transaction_month,
        n_transactions,
        median_price,
        LAG(median_price) OVER (ORDER BY transaction_month) AS prev_median
    FROM monthly
)
SELECT
    transaction_month,
    n_transactions,
    median_price,
    prev_median,
    round(median_price - prev_median, 0)                          AS mom_change,
    round(100.0 * (median_price - prev_median) / prev_median, 2)  AS mom_pct_change
FROM with_lag
ORDER BY transaction_month;
