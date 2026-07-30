USE Agresso_HoC;

-- ============================================================
-- HOW TO RUN
-- Database : Agresso_HoC (server mdata837)
-- Output   : budgets_HOC.csv
-- Place in : data/budgets/
-- Notes    : HOC only — no HOL budget equivalent.
--            Current FY 2025/26 = periods 202501–202515.
--            dim2 and dim6 not yet confirmed — eyeball values
--            before relying on them in DQ checks.
--            dim1 = account (unusual — not a separate column here)
--            dim3 = unit code
--            dim5 = HAIS code (level Finance forecasts at)
-- ============================================================

SELECT
    b.client,
    b.period,
    b.dim1                AS account,
    b.dim2                AS dim2,               -- confirm: likely cost centre
    b.dim3                AS unit_code,
    b.dim4                AS dim4,               -- sparsely populated, likely project/contract
    b.dim5                AS hais_code,
    b.dim6                AS dim6,               -- confirm with Parliament
    b.pla_amount          AS orig_budget,        -- 2026ORIG  : original budget set at year start
    b.plb_amount          AS curr_budget,        -- 2026CURR  : current budget
    b.ple_amount          AS forecast_actuals,   -- 2026CFSTSP: live forecast + SAT-posted actuals
    b.plc_amount          AS funds_budget,       -- 2026FUNDS
    b.plf_amount          AS pfst_budget,        -- 2026PFST  : pre-financial statement
    b.plg_amount          AS q1_forecast,        -- 2026Q1FC
    b.plh_amount          AS q2_forecast,        -- 2026Q2FC
    b.pli_amount          AS q3_forecast,        -- 2026Q3FC
    b.plk_amount          AS mtip_budget,        -- 2026MTIP  : medium term investment plan
    b.plm_amount          AS base_budget,        -- 2026BASE
    b.plo_amount          AS myp_budget,         -- 2026MYP   : multi-year plan
    b.po_rest_com_amt     AS po_commitment
FROM aaghocbud b
WHERE b.client IN ('CA', 'CM')
  AND b.period BETWEEN 202501 AND 202515
ORDER BY b.client, b.period, b.dim1;
