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
-- Aggregates aattrans to one row per (client, asset_id, depr_book_id,
-- trans_type, account).
-- CI (Calculatory Interest) excluded — does not affect NBV or GL balance.
-- dc_flag = 1 filters to real transactions only. dc_flag = -1 entries are
-- the AT module's year-end reset reversals — including them causes every
-- trans_type group to SUM to zero. Confirmed from real HoC data June 2026.
-- Closed assets (aatasset.status = 'C') are excluded — balance checks are
-- only relevant for assets still in scope for migration.
--
-- ACCOUNT added September 2026 — see asset_balances_HOC_run.sql for the full
-- explanation. **HOL's account-number convention has NOT been confirmed** —
-- the "starts with 1, ends 00/15" rule was validated against HoC data only,
-- and HOL's chart of accounts uses a different format (letter-prefix, e.g.
-- A1000 — see CLAUDE.md Chart of Accounts section). Do not assume the same
-- rule applies here until confirmed with Parliament.
-- See asset_balances.sql for full DQ test descriptions and assumptions.
-- =============================================================================

USE agresso_HoL;

SELECT
    t.client,
    t.asset_id,
    t.depr_book_id,
    t.trans_type,
    t.account,
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
    t.client = 'LA'
    AND t.trans_type != 'CI'
    AND t.dc_flag = 1
    AND m.status != 'C'
GROUP BY
    t.client,
    t.asset_id,
    t.depr_book_id,
    t.trans_type,
    t.account
ORDER BY
    t.client,
    t.asset_id,
    t.depr_book_id,
    t.trans_type,
    t.account
;
