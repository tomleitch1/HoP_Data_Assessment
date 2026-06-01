USE agresso_HoL;

-- HOW TO RUN
-- Database : agresso_HoL (server mdata837)
-- Output   : gl_budgets_HOL.csv  →  data/gl/
-- Scope    : GL budget and virement entries for the current fiscal year.
--            HOL uses the end-year convention: fiscal_year = 2026 = FY2025/26.
--            HOL does not use periods 13 or 14 — period 12 is always the final period.
--            Budget entries (BU) and virements (BV) are excluded from the opening
--            balances extract — this is the complementary extract covering Seq 23.
--            Note: budget entries can carry future-dated periods (e.g. 203407) for
--            multi-year budget planning. These are intentional and not data errors.
--
-- EXTRACTION TIPS
--   Enable column headers: Tools → Options → Query Results → SQL Server →
--     Results to Grid → tick "Include column headers when copying or saving results"
--     (close and reopen the query tab for the setting to take effect)
--   Save via "Save Results As" — navigate to C:\Users\leitchtb\HoP_Data_Assessment\data\gl\
--   Expected row count: a few thousand (budget entries are fewer than actuals).
--
-- COLUMNS (same schema as gl_opening_balances — same source table aglperiodic)
--   client       : LA
--   account      : GL account code
--   period       : YYYYPP integer (e.g. 202601 = period 1 of FY2025/26 under HOL convention)
--   dim_1–dim_7  : dimension codes (dim_1 typically populated; others usually blank)
--   amount       : signed budget amount (positive = debit, negative = credit)
--   voucher_type : BU (budget) or BV (virement/transfer between budget lines)
--
-- DQ CHECKS THIS EXTRACT ENABLES (Seq 23 — GL Budgets & Forecasts)
--   GL_BUD_AMT_MISSING    Budget entry has no amount
--   GL_BUD_ORPHAN_ACC     Budget entry references account not in Chart of Accounts
--   GL_BUD_ORPHAN_DIM     Budget entry references dim_1 code not in agldimvalue
--   GL_BUD_NO_BUDGET      Active P&L account in CoA has no budget entry this year
--
-- FISCAL YEAR CUTOVER
--   Update lower bound to 202901 when extracting for migration cutover (FY2028/29).

SELECT
    client,
    account,
    period,
    dim_1, dim_2, dim_3, dim_4, dim_5, dim_6, dim_7,
    amount,
    cur_amount,
    currency,
    dc_flag,
    voucher_type,
    voucher_no,
    trans_date,
    tax_code,
    apar_id,
    apar_type,
    status,
    description
FROM aglperiodic
WHERE client = 'LA'
  AND period BETWEEN 202601 AND 209912
  AND voucher_type IN ('BU', 'BV')
  AND (status IS NULL OR status = '')
ORDER BY client, account, period;
