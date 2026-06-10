-- =============================================================================
-- asset_balances_HOL_run.sql
-- Houses of Parliament — Finance Systems Programme
-- Fixed Asset Balance Extract (Aggregated) — HoL Run File
-- =============================================================================
--
-- HOW TO RUN
-- Database  : agresso_HoL
-- Output    : asset_balances_HOL.csv
-- Place in  : data/assets/
--
-- Aggregates aattrans to one row per (client, asset_id, depr_book_id, trans_type).
-- CI (Calculatory Interest) excluded — does not affect NBV or GL balance.
-- dc_flag = 1 filters to real transactions only. dc_flag = -1 entries are
-- the AT module's year-end reset reversals — including them causes every
-- trans_type group to SUM to zero. Confirmed from real HoC data June 2026.
-- See asset_balances.sql for full DQ test descriptions and assumptions.
-- =============================================================================

USE agresso_HoL;

SELECT
    client,
    asset_id,
    depr_book_id,
    trans_type,
    SUM(amount)      AS total_amount,
    SUM(cur_amount)  AS total_cur_amount,
    MAX(trans_date)  AS max_trans_date,
    MIN(trans_date)  AS min_trans_date,
    COUNT(*)         AS transaction_count
FROM
    aattrans
WHERE
    client = 'LA'
    AND trans_type != 'CI'
    AND dc_flag = 1
GROUP BY
    client,
    asset_id,
    depr_book_id,
    trans_type
ORDER BY
    client,
    asset_id,
    depr_book_id,
    trans_type
;
