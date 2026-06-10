-- =============================================================================
-- asset_master_HOL_run.sql
-- Houses of Parliament — Finance Systems Programme
-- Fixed Asset Master Extract — HoL Run File
-- =============================================================================
--
-- HOW TO RUN
-- Database  : agresso_HoL
-- Output    : asset_master_HOL.csv
-- Place in  : data/assets/
--
-- See at_asset_master.sql for full DQ test descriptions and assumptions.
-- =============================================================================

USE agresso_HoL;

SELECT
    client,
    asset_id,
    asset_group,
    description,
    short_info,
    status,
    wf_state,
    cap_date_from,
    cap_period_from,
    date_from,
    date_to,
    apar_id,
    parent_asset,
    grant_flag,
    org_amount,
    org_amt_date,
    base_amount,
    std_amount,
    ins_amount,
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
    aatasset
WHERE
    client = 'LA'
ORDER BY
    client,
    asset_id
;
