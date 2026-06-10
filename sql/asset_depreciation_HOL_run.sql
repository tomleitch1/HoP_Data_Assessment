-- =============================================================================
-- asset_depreciation_HOL_run.sql
-- Houses of Parliament — Finance Systems Programme
-- Fixed Asset Depreciation Book Extract — HoL Run File
-- =============================================================================
--
-- HOW TO RUN
-- Database  : agresso_HoL
-- Output    : asset_depreciation_HOL.csv
-- Place in  : data/assets/
--
-- See asset_depreciation.sql for full DQ test descriptions and assumptions.
-- =============================================================================

USE agresso_HoL;

SELECT
    client,
    asset_id,
    depr_book_id,
    status,
    depr_method,
    depr_percent,
    lifetime,
    res_value,
    res_val_flag,
    salvage_amount,
    cap_date_from,
    cap_period_from,
    cap_flag,
    date_from,
    date_to,
    depr_period,
    depr_limit,
    depr_max_perc,
    nbv_rounding,
    switch,
    period_exact,
    frequency,
    index_id,
    index_code,
    repl_amount,
    dim_1,
    dim_2,
    dim_3,
    dim_4,
    dim_5,
    dim_6,
    dim_7,
    last_update,
    user_id
FROM
    aatassetbook
WHERE
    client = 'LA'
ORDER BY
    client,
    asset_id,
    depr_book_id
;
