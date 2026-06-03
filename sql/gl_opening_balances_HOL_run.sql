USE agresso_HoL;

-- HOW TO RUN
-- Run against agresso_HoL (server mdata837)  → save as gl_opening_balances_HOL.csv
-- Extracts all posted GL transactions for FY2025/26 from aglperiodic
--
-- HOL FISCAL YEAR CONVENTION: start-year naming — same as HOC
-- fiscal year 2025 = FY2025/26 = April 2025 to March 2026
-- HOL periods run 202501 (April 2025) through 202512 (March 2026)
-- HOL historically never posts period 13 or 14 — period 12 is always the final period
--
-- aglyearend is not used in this Agresso installation (contains only legacy pre-2008 data)
-- Budget/forecast entries (BU, BV) are excluded; future-dated rows are budget artefacts
-- dc_flag is always 0 — amount is signed (positive = debit, negative = credit)
-- currency is always GBP; cur_amount is always blank; apar_id is always blank
-- trans_date is stored as integer 1 (system placeholder, not a real date)

SELECT
    p.client,
    p.account,
    p.period,
    p.dim_1,
    p.dim_2,
    p.dim_3,
    p.dim_4,
    p.dim_5,
    p.dim_6,
    p.dim_7,
    p.amount,
    p.cur_amount,
    p.currency,
    p.dc_flag,
    p.voucher_type,
    p.voucher_no,
    p.trans_date,
    p.tax_code,
    p.apar_id,
    p.apar_type,
    p.status,
    p.description
FROM aglperiodic p
WHERE p.client = 'LA'
  AND p.period BETWEEN 202501 AND 202512
  AND p.voucher_type NOT IN ('BU', 'BV')
ORDER BY p.client, p.period, p.account, p.dim_1;
