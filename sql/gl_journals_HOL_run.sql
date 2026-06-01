USE agresso_HoL;

-- HOW TO RUN
-- Database : agresso_HoL (server mdata837)
-- Output   : gl_journals_HOL.csv  →  data/gl/
-- Scope    : Current fiscal year actual journals only (Seq 21).
--            HOL uses the END-YEAR fiscal year convention:
--              fiscal_year = 2026 covers FY2025/26 (periods 202601–202612).
--            HOL does not use periods 13 or 14 — period 12 is always final.
--            Update fiscal_year value when the current FY rolls over.
--            Excludes budget/virement entries (BU, BV) — those are Seq 23.
--            Excludes system-generated entries (status P, T, B, D).
--            Normal posted transactions have status blank or NULL.
--
-- EXTRACTION TIPS
--   Enable column headers: Tools → Options → Query Results → SQL Server →
--     Results to Grid → tick "Include column headers when copying or saving results"
--     (close and reopen the query tab for the setting to take effect)
--   Save via "Save Results As" — navigate to C:\Users\leitchtb\HoP_Data_Assessment\data\gl\
--   Do NOT open the CSV by double-clicking — use Excel Data → Get Data → From Text/CSV.
--   When Excel prompts about data type conversion, click "Don't Convert".
--   Leading zeros on dim_* values: set those columns to Text type in Power Query.
--
-- EXPECTED OUTPUT
--   HOL has one in-scope client code (LA).
--   Expect roughly 10,000–40,000 rows for a full fiscal year.
--   If row count is unexpectedly low, check that fiscal_year matches the
--   HOL end-year convention (fiscal_year = 2026 for FY2025/26).
--   If unexpectedly high, verify BU/BV exclusion is filtering correctly.
--
-- COLUMNS
--   client        : LA (the only in-scope client in agresso_HoL)
--   voucher_no    : journal/voucher number — groups all lines of one entry
--   sequence_no   : line sequence within the voucher — part of composite PK
--   account       : GL account code — join key to aglaccounts
--   fiscal_year   : financial year (HOL end-year convention: 2026 = FY2025/26)
--   period        : GL posting period as YYYYPP (e.g. 202606 = FY2025/26 period 6)
--   trans_date    : economic/posting date — drives period allocation
--   voucher_date  : entry date — audit trail
--   voucher_type  : journal classification (e.g. JL, AC, PE, PY — see full spec)
--   amount        : amount in GBP — core field for balance integrity checks
--   cur_amount    : amount in transaction currency (blank if GBP)
--   currency      : transaction currency (expected GBP for most Parliament journals)
--   dc_flag       : debit/credit flag — convention unconfirmed, do not use in logic
--   update_flag   : debit/credit indicator — 1=Debit, 2=Credit (documented valuelist)
--   status        : transaction status — blank/NULL = normal; extracted to confirm filter
--   apar_id       : sub-ledger reference (supplier or customer ID) — control accounts only
--   apar_type     : ledger type — R=Customer (AR), P=Supplier (AP)
--   tax_code      : tax code applied to the line (must pair with tax_system)
--   tax_system    : tax system reference (must pair with tax_code)
--   description   : free-text journal line description
--   ext_inv_ref   : external invoice reference — populated on sub-ledger feeder postings
--   dim_1..dim_7  : analytical dimension codes — join keys to agldimvalue
--   last_update   : last modified timestamp (Excel serial integer from SSMS)
--   user_id       : posting user — audit trail and access migration planning
--
-- FISCAL YEAR CUTOVER NOTE
--   When FY2025/26 closes and FY2026/27 becomes current, update:
--     fiscal_year = 2027   (HOL end-year: FY2026/27 = 2027)
--   For the migration cutover year (FY2027/28):
--     fiscal_year = 2028   (HOL end-year: FY2027/28 = 2028)
--
-- DQ CHECKS THIS EXTRACT ENABLES (see gl_journals.sql for full specification)
--   GL_JNL_VOUCHER_MISSING   voucher_no is null (Critical)
--   GL_JNL_ACCT_MISSING      account is null or blank (Critical)
--   GL_JNL_AMT_MISSING       amount is null (Critical)
--   GL_JNL_FLAG_INVALID      update_flag not in (1, 2) (Critical)
--   GL_JNL_DUP_KEY           duplicate (client, voucher_no, sequence_no) (Critical)
--   GL_JNL_UNBALANCED        voucher lines do not net to zero (Critical)
--   GL_JNL_DATE_MISSING      trans_date is null (High)
--   GL_JNL_ACCT_ORPHAN       account not in aglaccounts for same house (Critical)
--   GL_JNL_ACCT_CLOSED       account in aglaccounts but status != N (High)
--   GL_JNL_DIM1_ORPHAN       dim_1 not in agldimvalue for same house (High)

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
WHERE client = 'LA'
  AND fiscal_year = 2026
  AND (status IS NULL OR status = '')
  AND voucher_type NOT IN ('BU', 'BV')
ORDER BY
    client,
    fiscal_year,
    period,
    voucher_no,
    sequence_no;
