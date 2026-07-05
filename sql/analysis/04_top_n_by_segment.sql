-- ============================================================================
-- 04 - Top-N by segment  (technique: TOP-N per group via QUALIFY)
-- ----------------------------------------------------------------------------
-- For each flat type (the segment), the 5 priciest towns by median resale price
-- over the trailing 12 months. QUALIFY filters directly on a window function's
-- result without needing a wrapping subquery — DuckDB's neat shorthand.
-- Thin segments (< 20 transactions) are dropped so a single sale can't top a
-- ranking.
-- ============================================================================
WITH recent AS (
    SELECT flat_type, town, resale_price, price_per_sqm
    FROM main.resale_clean
    WHERE transaction_month
          > (SELECT max(transaction_month) FROM main.resale_clean) - INTERVAL '12 months'
),
by_town AS (
    SELECT
        flat_type,
        town,
        count(*)                       AS n_transactions,
        round(median(resale_price), 0) AS median_price,
        round(avg(price_per_sqm), 2)   AS avg_psm
    FROM recent
    GROUP BY flat_type, town
    HAVING count(*) >= 20
)
SELECT
    flat_type,
    town,
    n_transactions,
    median_price,
    avg_psm,
    ROW_NUMBER() OVER (PARTITION BY flat_type ORDER BY median_price DESC) AS rank_in_type
FROM by_town
QUALIFY rank_in_type <= 5
ORDER BY flat_type, rank_in_type;
