-- =============================================================================
-- asset_groups_HOC_run.sql
-- Houses of Parliament — Finance Systems Programme
-- Fixed Asset Group & Category Configuration Extract — HoC Run File
-- =============================================================================
--
-- HOW TO RUN
-- Database  : Agresso_HoC
-- Output    : asset_groups_HOC.csv
-- Place in  : data/assets/
--
-- Joins aatassetgroup (group master) to aatassetgrbook (group depreciation books).
-- LEFT JOIN preserves groups that have no book configuration — these are flagged
-- as incomplete in the DQ checks.
-- See asset_groups.sql for full DQ test descriptions and assumptions.
-- =============================================================================

USE Agresso_HoC;

SELECT
    g.client,
    g.asset_group,
    g.description,
    g.status            AS grp_status,
    g.depr_method,
    g.depr_percent,
    g.lifetime,
    g.res_value,
    g.res_val_flag,
    g.salvage_amount,
    g.depr_start,
    g.depr_limit,
    g.depr_max_perc,
    g.frequency,
    g.switch,
    g.period_exact,
    g.nbv_rounding,
    g.index_id,
    g.index_code,
    g.ins_table_id,
    g.insurance_mode,
    g.dim_1,
    g.dim_2,
    g.dim_3,
    g.dim_4,
    g.dim_5,
    g.dim_6,
    g.dim_7,
    g.last_update       AS grp_last_update,
    g.user_id           AS grp_user_id,
    gb.depr_book_id,
    gb.status           AS book_status,
    gb.depr_method      AS book_depr_method,
    gb.depr_percent     AS book_depr_percent,
    gb.lifetime         AS book_lifetime,
    gb.res_value        AS book_res_value,
    gb.res_val_flag     AS book_res_val_flag,
    gb.salvage_amount   AS book_salvage_amount,
    gb.depr_start       AS book_depr_start,
    gb.depr_limit       AS book_depr_limit,
    gb.depr_max_perc    AS book_depr_max_perc,
    gb.frequency        AS book_frequency,
    gb.switch           AS book_switch,
    gb.period_exact     AS book_period_exact,
    gb.nbv_rounding     AS book_nbv_rounding,
    gb.index_id         AS book_index_id,
    gb.index_code       AS book_index_code,
    gb.last_update      AS book_last_update,
    gb.user_id          AS book_user_id
FROM
    aatassetgroup g
    LEFT JOIN aatassetgrbook gb
        ON  g.client      = gb.client
        AND g.asset_group = gb.asset_group
WHERE
    g.client IN ('CA', 'CM')
ORDER BY
    g.client,
    g.asset_group,
    gb.depr_book_id
;
