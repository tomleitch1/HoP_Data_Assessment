-- =============================================================================
-- asset_trans_flags_HOL_run.sql
-- Houses of Parliament — Finance Systems Programme
-- Fixed Asset Transaction Flags — HoL Run File
-- =============================================================================
--
-- HOW TO RUN
-- Database  : agresso_HoL
-- Output    : asset_trans_flags_HOL.csv
-- Place in  : data/assets/
--
-- Fiscal year filter applied: fiscal_year >= 2023 (current FY 2025 minus 2).
-- Depreciation posted more than two years ago cannot fail the date_to check
-- for any asset still active today. CA (capitalisation) events older than the
-- window will be missed — confirm with Parliament that this lookback is acceptable.
-- See asset_trans_flags.sql (full spec) for complete DQ test descriptions.
-- =============================================================================

USE agresso_HoL;

SELECT
    client,
    asset_id,
    depr_book_id,
    trans_type,
    trans_date,
    at_trans_date,
    fiscal_year,
    amount,
    dc_flag
FROM
    aattrans
WHERE
    client = 'LA'
    AND trans_type IN ('CA', 'SA', 'ND', 'ED', 'FD')
    AND fiscal_year >= 2023
ORDER BY
    client,
    asset_id,
    depr_book_id,
    trans_type,
    trans_date
;
