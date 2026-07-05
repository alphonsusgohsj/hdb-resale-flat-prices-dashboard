-- ============================================================================
-- 01 - Price rank within town  (technique: WINDOW FUNCTIONS)
-- ----------------------------------------------------------------------------
-- Within each town, rank flat types by average price per sqm, and compare each
-- segment to that town's overall average. Uses two window functions:
--   RANK() OVER (PARTITION BY town ORDER BY ...)  -> ordinal position in town
--   AVG(...) OVER (PARTITION BY town)             -> town-level benchmark
-- Windowed over the trailing 12 months so 2026 (a partial year) is not compared
-- unfairly against full years.
-- ============================================================================
WITH recent AS (
    SELECT *
    FROM main.resale_clean
    WHERE transaction_month
          > (SELECT max(transaction_month) FROM main.resale_clean) - INTERVAL '12 months'
),
by_segment AS (
    SELECT
        town,
        flat_type,
        count(*)                     AS n_transactions,
        round(avg(resale_price), 0)  AS avg_price,
        round(avg(price_per_sqm), 2) AS avg_psm
    FROM recent
    GROUP BY town, flat_type
)
SELECT
    town,
    flat_type,
    n_transactions,
    avg_price,
    avg_psm,
    RANK() OVER (PARTITION BY town ORDER BY avg_psm DESC)  AS psm_rank_in_town,
    round(AVG(avg_psm) OVER (PARTITION BY town), 2)        AS town_avg_psm
FROM by_segment
ORDER BY town, psm_rank_in_town;
