USE Agresso_HoC;

-- HOW TO RUN
-- Run against Agresso_HoC (server mdata837)  → save as gl_opening_balances_HOC.csv
-- Extracts all posted GL transactions for FY2025/26 from aglperiodic (periods 202601-202699)
-- aglyearend is not used in this Agresso installation (contains only legacy pre-2008 data)
-- Budget/forecast entries (BU, BV) are excluded; future-dated rows in aglperiodic are budget artefacts

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
WHERE p.client IN ('CA', 'CM')
  AND p.period BETWEEN 202601 AND 202699
  AND p.voucher_type NOT IN ('BU', 'BV')
ORDER BY p.client, p.period, p.account, p.dim_1;
