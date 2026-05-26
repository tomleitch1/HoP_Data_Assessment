-- HOW TO RUN
-- Run against Agresso_HoC  → save as gl_journals_HOC.csv
-- Run against agresso_HoL  → save as gl_journals_HOL.csv
-- Server: mdata837
-- Replace [CURRENT_FISCAL_YEAR] with actual 4-digit year e.g. 2026 for FY2025/26

SELECT
    client,
    voucher_no,
    sequence_no,
    account,
    fiscal_year,
    period,
    trans_date,
    voucher_date,
    voucher_type,
    amount,
    cur_amount,
    currency,
    dc_flag,
    update_flag,
    status,
    apar_id,
    apar_type,
    tax_code,
    tax_system,
    description,
    ext_inv_ref,
    dim_1,
    dim_2,
    dim_3,
    dim_4,
    dim_5,
    dim_6,
    dim_7,
    last_update,
    user_id
FROM agltransact
WHERE fiscal_year = [CURRENT_FISCAL_YEAR]
  AND status = ''
ORDER BY
    client,
    fiscal_year,
    period,
    voucher_no,
    sequence_no;
