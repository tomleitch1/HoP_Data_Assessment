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
-- See asset_balances.sql for full DQ test descriptions and assumptions.
-- =============================================================================

USE Agresso_HoC;

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
    client IN ('CA', 'CM')
    AND trans_type != 'CI'
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
