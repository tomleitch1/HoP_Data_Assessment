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
-- See asset_trans_flags.sql for full design rationale.
-- Hybrid extract: individual rows for CA/SA, aggregated MAX date for ND/ED/FD.
-- The row_type column tells Python which is which.
-- =============================================================================

USE agresso_HoL;

-- Part 1: Individual CA and SA transactions (low volume, full row detail needed)
SELECT
    client,
    asset_id,
    depr_book_id,
    trans_type,
    trans_date,
    at_trans_date,
    fiscal_year,
    amount,
    dc_flag,
    'INDIVIDUAL'    AS row_type
FROM
    aattrans
WHERE
    client = 'LA'
    AND trans_type IN ('CA', 'SA')

UNION ALL

-- Part 2: Latest depreciation date per asset/book/type (collapses high-volume ND/ED/FD)
SELECT
    client,
    asset_id,
    depr_book_id,
    trans_type,
    MAX(trans_date) AS trans_date,
    NULL            AS at_trans_date,
    NULL            AS fiscal_year,
    NULL            AS amount,
    NULL            AS dc_flag,
    'LATEST_DEPR'   AS row_type
FROM
    aattrans
WHERE
    client = 'LA'
    AND trans_type IN ('ND', 'ED', 'FD')
GROUP BY
    client,
    asset_id,
    depr_book_id,
    trans_type

ORDER BY
    client,
    asset_id,
    depr_book_id,
    trans_type,
    trans_date
;
