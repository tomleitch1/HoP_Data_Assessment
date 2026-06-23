-- =============================================================================
-- asset_balances_HOC_run.sql
-- Houses of Parliament — Finance Systems Programme
-- Fixed Asset Balance Extract (Aggregated) — HoC Run File
-- =============================================================================
--
-- HOW TO RUN
-- Database  : Agresso_HoC
-- Output    : asset_balances_HOC.csv
-- Place in  : data/assets/
--
-- Aggregates aattrans to one row per (client, asset_id, depr_book_id, trans_type).
-- CI (Calculatory Interest) excluded — does not affect NBV or GL balance.
-- dc_flag = 1 filters to real transactions only. dc_flag = -1 entries are
-- the AT module's year-end reset reversals — including them causes every
-- trans_type group to SUM to zero. Confirmed from real HoC data June 2026.
-- Closed assets (aatasset.status = 'C') are excluded — balance checks are
-- only relevant for assets still in scope for migration.
-- See asset_balances.sql for full DQ test descriptions and assumptions.
-- =============================================================================

USE Agresso_HoC;

SELECT
    t.client,
    t.asset_id,
    t.depr_book_id,
    t.trans_type,
    SUM(t.amount)      AS total_amount,
    SUM(t.cur_amount)  AS total_cur_amount,
    MAX(t.trans_date)  AS max_trans_date,
    MIN(t.trans_date)  AS min_trans_date,
    COUNT(*)           AS transaction_count
FROM
    aattrans t
    INNER JOIN aatasset m
        ON  m.client   = t.client
        AND m.asset_id = t.asset_id
WHERE
    t.client IN ('CA', 'CM')
    AND t.trans_type != 'CI'
    AND t.dc_flag = 1
    AND m.status != 'C'
GROUP BY
    t.client,
    t.asset_id,
    t.depr_book_id,
    t.trans_type
ORDER BY
    t.client,
    t.asset_id,
    t.depr_book_id,
    t.trans_type
;
