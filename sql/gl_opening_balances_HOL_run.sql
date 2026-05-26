USE agresso_HoL;

-- HOW TO RUN
-- Run against agresso_HoL (server mdata837)  → save as gl_opening_balances_HOL.csv
-- Replace [CURRENT_FISCAL_YEAR] e.g. 2025 for FY2025/26 (confirm format with Parliament)
-- Replace [YEAR_END_PERIOD] — likely period 12 or 15 depending on year-end adjustments

SELECT
    y.client,
    y.account,
    y.fiscal_year,
    y.period,
    y.dim_1,
    y.dim_2,
    y.dim_3,
    y.dim_4,
    y.dim_5,
    y.dim_6,
    y.dim_7,
    y.amount,
    y.cur_amount,
    y.currency,
    y.dc_flag,
    y.voucher_type,
    y.tax_code,
    y.apar_id,
    y.apar_type
FROM aglyearend y
WHERE y.client = 'LA'
  AND y.fiscal_year = '[CURRENT_FISCAL_YEAR]'
  AND y.period = '[YEAR_END_PERIOD]'
ORDER BY y.account, y.dim_1;
