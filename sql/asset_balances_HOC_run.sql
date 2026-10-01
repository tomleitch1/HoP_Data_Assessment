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
-- Aggregates aattrans to one row per (client, asset_id, depr_book_id,
-- trans_type, account).
-- CI (Calculatory Interest) excluded — does not affect NBV or GL balance.
-- ALL dc_flag values are included (corrected September 2026). dc_flag = -1
-- rows were previously excluded as "year-end reset reversals", which was
-- wrong: they are real postings, the other side of each entry. Every posting
-- has both sides in aattrans on different accounts (e.g. 14015 / 57000), which
-- is why each trans_type sums to zero across all accounts. Validated on
-- LB22JOHN: including dc_flag = -1 reproduces Parliament's CURR NBV £352,000,
-- HIST NBV £43,760.32 and reserve −£308,239.69; dc_flag = 1 alone does not.
-- Closed assets (aatasset.status = 'C') are excluded — balance checks are
-- only relevant for assets still in scope for migration.
--
-- ACCOUNT added September 2026 — confirmed by Parliament (direct example:
-- asset LB1PARLI) that NBV is derived per account, not by netting every
-- account for a trans_type together. Aggregating without account previously
-- made OS (historical pre-migration capitalisation) look like it always
-- carried a £0 amount — that was an artifact of this extract summing a
-- cost account and its contra/control account together, which are designed
-- to net to zero. The confirmed rule (validated against two real assets,
-- 1 Parliament Street and 22 John Islip, matching Parliament's own figures
-- to the penny, and checked to hold for every asset in the register with
-- any transaction history): an account contributes to NBV if it starts
-- with '1' and ends in '00' (cost) or '15' (accumulated depreciation).
-- Every other account (e.g. control/contra accounts, P&L depreciation
-- charge accounts, the revaluation reserve account) is excluded from NBV.
-- See asset_balances.sql for full DQ test descriptions and assumptions.
-- =============================================================================

USE Agresso_HoC;

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
    t.client = 'CA'  -- CM is out of scope for assets (confirmed September 2026)
    AND t.trans_type != 'CI'
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
