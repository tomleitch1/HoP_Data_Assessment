USE Agresso_HoC;

-- ============================================================
-- HOW TO RUN
-- Database : Agresso_HoC (server mdata837)
-- Output   : budgets_HOC.csv
-- Place in : data/budgets/
-- Notes    : HOC only — no HOL budget equivalent.
--            Current FY 2025/26 = periods 202501–202515.
--            Dimension mapping confirmed from balance table definition:
--              dim1 = account (ACCOUNT — unusual, not a separate column)
--              dim2 = cost_centre (COSTC)
--              dim3 = unit_code (UNIT)
--              dim4 = resno (RESNO — resource number, sparse: capital/project lines only)
--              dim5 = hais_code (HAISCODE)
--              dim6 = recharge (RECHARGE — HOC/HOL house split)
--            amount column = GL actuals (pulled automatically by AGRDWS)
--            ple_amount (Planner E) = CFSTSP: SAT-posted manual actuals + forecast
-- ============================================================

SELECT
    b.client,
    b.period,
    b.dim1                AS account,
    b.dim2                AS cost_centre,        -- COSTC
    b.dim3                AS unit_code,          -- UNIT
    b.dim4                AS resno,              -- RESNO: resource number, sparsely populated (capital/project lines only)
    b.dim5                AS hais_code,          -- HAISCODE
    b.dim6                AS recharge,           -- RECHARGE: HOC/HOL house split
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
