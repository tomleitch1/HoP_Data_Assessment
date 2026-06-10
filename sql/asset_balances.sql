-- =============================================================================
-- asset_balances.sql
-- Houses of Parliament — Finance Systems Programme
-- Fixed Asset Balance Extract (Aggregated)
-- Migration scope: Seq 19 (Asset Balances — NBV, Accumulated Depreciation,
-- Original Cost)
-- Source table: aattrans (aggregated)
-- =============================================================================
--
-- INSTANCE & CLIENT
-- Run this script separately against the HoC instance and the HoL instance.
-- HoC clients: CA (Common Administration), CF (Miscellaneous Fund),
-- CM (Members Fund). HoL client: LA.
-- Add house column in Python after load (df['house'] = 'HOC' / 'HOL').
-- No client filter applied — all clients extracted.
--
-- PURPOSE
-- Derives the current balance position per asset per depreciation book by
-- aggregating all posted transactions by type. Produces one row per
-- (client, asset_id, depr_book_id, trans_type) — a deliberately wide pivot
-- that Python then uses to calculate:
--   Original cost        = SUM(amount) where trans_type in ('CA', 'PC')
--   Accumulated depr     = SUM(amount) where trans_type in ('ND', 'ED', 'FD')
--   Revaluation movement = SUM(amount) where trans_type = 'VN'
--   Grant credits        = SUM(amount) where trans_type = 'ZU'
--   Disposals            = SUM(amount) where trans_type = 'SA'
--   Reversals            = SUM(amount) where trans_type = 'RV'
--   NBV                  = Original cost - Accumulated depr +/- Revaluation
--                          - Disposals +/- Reversals
--
-- WHY AGGREGATED NOT RAW
-- aattrans contains one row per transaction line. A monthly-depreciated asset
-- capitalised ten years ago has 120+ depreciation rows alone before betterments,
-- revaluations, and reversals. Extracting raw rows for a mature asset register
-- would produce an unmanageable volume with no additional value for migration
-- purposes — Seq 19 requires the balance position, not the transaction trail.
-- Aggregating in SQL reduces the extract to one row per asset per book per
-- transaction type regardless of how many individual postings exist.
--
-- CI (Calculatory Interest) EXCLUSION
-- trans_type = 'CI' is excluded from this extract. Calculatory interest is an
-- internal management accounting charge and does not affect NBV or the balance
-- sheet position that must reconcile to the GL. Including it would distort the
-- balance derivation.
--
-- RELATIONSHIP TO OTHER EXTRACTS
-- Balance positions derived from this extract must reconcile to:
--   (a) asset_master (Seq 12) — every asset_id here should be in asset_master
--   (b) asset_depreciation (Seq 13) — every (asset_id, depr_book_id) here
--       should have a corresponding depreciation book record
--   (c) GL Opening Balance extract (Seq 14) — sum of NBV across all assets
--       must reconcile to the Fixed Assets control account balance in the GL.
--       This is the primary migration reconciliation check. Available once the
--       GL extract exists.
--
-- ASSUMPTIONS
-- A1. CI (Calculatory Interest) does not affect NBV or the GL balance sheet.
--     Excluded from this extract by the WHERE clause.
-- A2. dc_flag is +1 (debit) or -1 (credit). amount is already signed —
--     negative amounts carry a minus sign directly in the amount field.
--     dc_flag mirrors the sign but does not drive it. SUM(amount) is
--     therefore correct as written — no dc_flag multiplication needed.
-- A3. RV (Reversal) transactions fully offset the transaction they reverse.
--     Including them in the aggregation means they net out automatically.
--     If Unit4 stores reversals as equal and opposite amounts, the net effect
--     is zero and they do not distort the balance. If they are stored differently,
--     the aggregation logic must be adjusted.
-- A4. max_trans_date (most recent transaction date per group) is extracted to
--     support stale asset identification in Python — assets where the most
--     recent transaction is very old relative to the current period.
-- A5. transaction_count is extracted to support volume profiling — assets with
--     unusually high or low transaction counts may indicate data anomalies.
-- A6. An asset with only CA transactions and no ND/ED/FD may be a
--     non-depreciating asset (land, heritage asset) or a processing gap.
--     Python must surface this population for Parliament to categorise.
-- A7. The aggregation is performed across all fiscal years — there is no date
--     filter. This produces the lifetime cumulative position, which is the
--     correct input for deriving current NBV at cutover.
--
-- =============================================================================
-- DATA QUALITY TESTS (all executed in Python against the CSV output)
-- =============================================================================
--
-- COMPLETENESS
-- DQ-AB-C01 [Critical]  asset_id is null or blank in any aggregated row.
--            Should not be possible given the GROUP BY, but validate on load.
-- DQ-AB-C02 [Critical]  depr_book_id is null or blank in any aggregated row.
--            Same as above — structural check on load.
-- DQ-AB-C03 [Critical]  trans_type is null or blank in any aggregated row.
--            WHERE clause excludes CI but all other types must be present.
-- DQ-AB-C04 [High]      total_amount is null for any row.
--            SUM should never return null given the WHERE clause excludes
--            nulls — flag if encountered.
--
-- VALIDITY
-- DQ-AB-V01 [Critical]  trans_type not in ('CA','PC','SA','ND','ED','FD',
--            'VN','RV','ZU'). Value outside expected set after CI exclusion.
-- DQ-AB-V02 [High]      total_amount = 0 for trans_type = 'CA'.
--            An asset capitalised with zero total cost. Not valid for standard
--            assets. Grant or donated assets may be legitimate exceptions —
--            confirm with Parliament.
-- DQ-AB-V03 [Medium]    max_trans_date is in the future.
--            A transaction posted beyond today's date — data entry error.
--
-- CONSISTENCY
-- DQ-AB-K01 [High]      Derived NBV is negative per (client, asset_id,
--            depr_book_id). Accumulated depreciation exceeds original cost.
--            Not valid unless a revaluation or extraordinary transaction
--            explains the position — produce a list for Parliament to review.
-- DQ-AB-K02 [High]      SA (disposal) rows exist but no corresponding CA row
--            for the same (client, asset_id, depr_book_id).
--            Asset was disposed but no capitalisation exists in the ledger.
-- DQ-AB-K03 [High]      ND/ED/FD rows exist but no CA row for the same
--            (client, asset_id, depr_book_id).
--            Depreciation has been posted against an asset with no original
--            cost transaction — indicates a missing capitalisation posting.
-- DQ-AB-K04 [Advisory]  Derived NBV = 0 and no SA transaction exists for the
--            same (client, asset_id, depr_book_id).
--            Asset is fully depreciated but still on the register with no
--            disposal transaction. Parliament should confirm whether these
--            assets are still in use or should be formally disposed.
-- DQ-AB-K05 [Advisory]  No ND/ED/FD rows for an asset where asset_depreciation
--            shows depr_method in ('LIN','BAL','SYD').
--            Asset has a depreciating method configured but no depreciation
--            has ever been posted — processing gap or recently capitalised.
--
-- SCOPE
-- DQ-AB-S01 [Info]      Count of (client, asset_id, depr_book_id) combinations
--            with only CA transactions — no depreciation of any kind.
--            Non-depreciating asset candidates or processing gaps.
-- DQ-AB-S02 [Info]      Sum of derived NBV by client and asset_group.
--            Baseline balance position before GL reconciliation.
-- DQ-AB-S03 [Info]      Count and total_amount of SA transactions by client.
--            Volume and value of disposals — confirms disposal activity in
--            the register before migration scope is finalised.
-- DQ-AB-S04 [Info]      Max and min max_trans_date by client.
--            Understand the recency of transaction activity across the register.
--
-- CROSS-EXTRACT TESTS (Python, joining asset_master and asset_depreciation)
-- DQ-AB-X01 [Critical]  asset_id in this extract with no matching record in
--            asset_master. Orphaned balance — no master record for this asset.
-- DQ-AB-X02 [Critical]  (client, asset_id, depr_book_id) in this extract with
--            no matching record in asset_depreciation. Balance exists for a
--            book that has no configuration record.
-- DQ-AB-X03 [High]      asset_id in asset_master with status = 'N' and no
--            rows in this extract. Active asset with no transaction history —
--            never capitalised. Either a data gap or a non-capitalised asset
--            that should not be in the active register.
-- DQ-AB-X04 [Critical]  Sum of derived NBV across all clients does not
--            reconcile to Fixed Assets control account in GL Opening Balance
--            (Seq 14). Primary migration reconciliation check. Must balance
--            before migration can proceed. Available once GL extract exists.
--
-- =============================================================================

SELECT
    client,                         -- Fund/entity code. HoC: CA/CF/CM. HoL: LA.
    asset_id,                       -- Foreign key to aatasset. Group key for balance derivation.
    depr_book_id,                   -- Depreciation book. Group key — one balance position per book.
    trans_type,                     -- Transaction type after CI exclusion. Drives Python balance logic.
    SUM(amount)      AS total_amount,       -- Lifetime cumulative amount by type. Core balance input.
    SUM(cur_amount)  AS total_cur_amount,   -- Cumulative transaction currency amount. FX comparison.
    MAX(trans_date)  AS max_trans_date,     -- Most recent posting date. Stale asset identification.
    MIN(trans_date)  AS min_trans_date,     -- Earliest posting date. Asset activity start point.
    COUNT(*)         AS transaction_count   -- Row count before aggregation. Volume profiling.
FROM
    aattrans
WHERE
    trans_type != 'CI'              -- Exclude Calculatory Interest — does not affect NBV or GL balance.
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