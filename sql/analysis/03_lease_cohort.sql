-- ============================================================================
-- 03 - Lease-commencement cohorts  (technique: COHORT ANALYSIS)
-- ----------------------------------------------------------------------------
-- A cohort here is a group of flats defined by WHEN their 99-year lease began.
-- Bucketed into decades (1960s ... 2020s) for legibility, then compared on
-- price, price-per-sqm and remaining lease. This isolates the "lease decay"
-- effect: older cohorts have less lease left and typically lower price-per-sqm.
-- Trailing 12 months so the comparison reflects the current market.
-- ============================================================================
WITH cohorts AS (
    SELECT
        (lease_commence_year // 10) * 10 AS lease_decade,   -- 1979 -> 1970
        resale_price,
        price_per_sqm,
        remaining_lease_months
    FROM main.resale_clean
    WHERE transaction_month
          > (SELECT max(transaction_month) FROM main.resale_clean) - INTERVAL '12 months'
)
SELECT
    lease_decade,
    count(*)                                   AS n_transactions,
    round(avg(remaining_lease_months) / 12, 1) AS avg_remaining_lease_years,
    round(median(resale_price), 0)             AS median_price,
    round(avg(price_per_sqm), 2)               AS avg_psm
FROM cohorts
GROUP BY lease_decade
ORDER BY lease_decade;
