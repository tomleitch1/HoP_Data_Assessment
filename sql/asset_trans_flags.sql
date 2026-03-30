-- =============================================================================
-- asset_trans_flags.sql
-- Houses of Parliament — Finance Systems Programme
-- Fixed Asset Transaction Flags Extract (Targeted Row-Level)
-- Migration scope: DQ checks only — not a migration input
-- Source table: aattrans (filtered, narrow)
-- =============================================================================
--
-- INSTANCE & CLIENT
-- Run this script separately against the HoC instance and the HoL instance.
-- HoC clients: CA (Common Administration), CF (Miscellaneous Fund),
-- CM (Members Fund). HoL client: LA.
-- Add house column in Python after load (df['house'] = 'HOC' / 'HOL').
--
-- PURPOSE
-- This extract exists solely to support DQ consistency checks that require
-- row-level transaction data — specifically checks that need to know whether
-- a particular transaction type exists for a given asset, or whether a
-- transaction date falls outside an expected range. It is not used for balance
-- derivation (that is handled by asset_balances.sql) and is not a migration
-- input.
--
-- The checks this extract enables that asset_balances.sql cannot:
--   1. Disposal (SA) transaction on an asset that is still active in
--      asset_master (status = 'N') — needs the individual SA transaction
--      date and amount to surface to Parliament, not just the aggregate.
--   2. Depreciation (ND/ED/FD) posted after the asset's date_to in
--      asset_master — needs the individual transaction date to compare
--      against date_to.
--   3. Zero-cost capitalisation (CA with amount = 0) — needs the individual
--      row to confirm it is not an artefact of aggregation.
--   4. Future-dated transactions — needs trans_date at row level.
--
-- WHY NOT JUST USE asset_balances.sql FOR THESE
-- asset_balances.sql aggregates to one row per (asset, book, trans_type).
-- For checks 1-4 above you need the actual transaction date and amount on
-- individual rows — the aggregate loses the date detail needed to determine
-- whether a depreciation posting falls after date_to, or whether a specific
-- SA transaction predates or postdates a status change on the master.
--
-- VOLUME CONTROL
-- The WHERE clause restricts to only the transaction types needed for the
-- four checks above: CA, SA, ND, ED, FD. This excludes PC (Betterment),
-- VN (Revaluation), ZU (Grant), RV (Reversal), and CI (Calculatory Interest)
-- which are not needed for row-level DQ flags.
-- Only the fields needed for the checks are selected — no description, no
-- voucher detail, no all-seven dims. This keeps the extract lean.
-- Even with the type filter, ND volume may be high on a mature register.
-- If volume remains a concern after filtering, a secondary filter of
-- fiscal_year >= (current FY - 2) can be applied — depreciation posted
-- more than two years ago cannot fail the date_to check for assets still
-- active today. Add this filter only if Parliament confirms it is acceptable
-- to narrow the lookback window.
--
-- RELATIONSHIP TO OTHER EXTRACTS
-- This extract is joined to asset_master in Python on (client, asset_id)
-- to perform the cross-extract DQ checks. It is not joined to
-- asset_balances.sql — the two extracts serve separate purposes and are
-- processed independently.
--
-- ASSUMPTIONS
-- A1. trans_type filter ('CA','SA','ND','ED','FD') is sufficient to cover
--     all row-level DQ checks identified. If additional checks emerge that
--     require row-level data for other types (e.g. VN revaluation date
--     anomalies), the WHERE clause can be extended without changing anything
--     else.
-- A2. amount sign convention must be confirmed with Parliament before Python
--     interprets zero-cost CA records. A CA with amount = 0 is flagged as a
--     potential issue but may be valid for donated or grant-funded assets.
-- A3. ND volume may still be significant even with the type filter. If the
--     register has been live for many years on monthly depreciation frequency
--     the ND rows alone could be large. The fiscal_year secondary filter
--     described above is available as a fallback — note it as an assumption
--     if applied.
-- A4. This extract does not replace asset_balances.sql for balance derivation.
--     The two extracts must not be confused — this one is DQ flags only.
--
-- =============================================================================
-- DATA QUALITY TESTS (all executed in Python against the CSV output)
-- =============================================================================
--
-- These tests are the sole reason this extract exists. Each maps to a specific
-- row-level check that requires transaction date or individual amount detail.
--
-- DQ-AF-X01 [High]      SA transaction exists for an asset_id where
--            asset_master status = 'N' (active asset with a disposal posting).
--            Either the master has not been updated post-disposal or the SA
--            was posted in error. Produce a list of affected assets with
--            the SA trans_date and amount for Parliament to review.
--            Join: asset_master on (client, asset_id).
--
-- DQ-AF-X02 [High]      ND, ED, or FD transaction with trans_date after
--            asset_master date_to for the same asset_id.
--            Depreciation posted after ownership ended. The asset should have
--            been closed before further depreciation was run.
--            Join: asset_master on (client, asset_id).
--
-- DQ-AF-X03 [High]      CA transaction with amount = 0 or null.
--            Zero-cost capitalisation at row level. Not valid for standard
--            purchased assets. Surface each instance with asset_id, client,
--            and trans_date for Parliament to confirm whether legitimate
--            (donated/grant asset) or an error.
--
-- DQ-AF-X04 [High]      trans_date is in the future (beyond today's date)
--            for any transaction type in this extract.
--            Future-dated transaction — data entry error or a scheduled
--            posting that has not yet been processed. Produce a list by
--            asset_id and trans_type.
--
-- DQ-AF-X05 [Medium]    Multiple CA transactions for the same
--            (client, asset_id, depr_book_id).
--            More than one capitalisation event on the same asset and book.
--            May be valid for assets capitalised in stages — flag for
--            Parliament to confirm rather than treat as an error.
--
-- =============================================================================

SELECT
    client,           -- Fund/entity code. HoC: CA/CF/CM. HoL: LA.
    asset_id,         -- Foreign key to aatasset. Join key to asset_master.
    depr_book_id,     -- Depreciation book. Needed to scope checks to the correct book.
    trans_type,       -- Transaction type. Restricted to CA/SA/ND/ED/FD by WHERE clause.
    trans_date,       -- GL posting date. Core field for date-range DQ checks.
    at_trans_date,    -- AT module date. Cross-check against trans_date for cutoff anomalies.
    fiscal_year,      -- Financial year. Supports year-level scoping in Python if needed.
    amount,           -- Transaction amount. Needed to identify zero-cost CA records.
    dc_flag           -- Debit/Credit indicator. Needed to interpret amount sign correctly.
FROM
    aattrans
WHERE
    trans_type IN ('CA', 'SA', 'ND', 'ED', 'FD')
ORDER BY
    client,
    asset_id,
    depr_book_id,
    trans_type,
    trans_date
;