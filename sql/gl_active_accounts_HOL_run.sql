USE agresso_HoL;

-- HOW TO RUN
-- Database : agresso_HoL (server mdata837)
-- Output   : gl_active_accounts_HOL.csv  →  data/gl/
-- Scope    : Distinct GL accounts with at least one actual posting in agltransact
--            in the last 18 months (period >= 202409 = December 2024).
--            Covers three ranges not fully captured by the current-year journals extract:
--              - FY2024/25 tail : periods 202409–202412 (Dec 2024 – Mar 2025)
--              - FY2025/26 full : periods 202501–202512 (Apr 2025 – Mar 2026)
--              - FY2026/27 YTD  : periods 202601–202603 (Apr 2026 – Jun 2026)
--            Used by the GL_ACC_NO_ACTIVITY check to exclude accounts that have
--            had a real posting in the last 18 months, even if not in the
--            current-year journals frame.
--            Update the period cutoff by 1 each month if re-extracting later.
--            HoL only (client LA) — run the equivalent HOC check separately if needed.
--
-- EXTRACTION TIPS
--   Enable column headers: Tools → Options → Query Results → SQL Server →
--     Results to Grid → tick "Include column headers when copying or saving results"
--     (close and reopen the query tab for the setting to take effect)
--   Save via "Save Results As" — navigate to C:\Users\leitchtb\HoP_Data_Assessment\data\gl\
--   Do NOT open the CSV by double-clicking — use Excel Data → Get Data → From Text/CSV.
--   When Excel prompts about data type conversion, click "Don't Convert".
--
-- EXPECTED OUTPUT
--   One row per distinct GL account code that has had at least one posting
--   in the qualifying 18-month window.
--   Expect a few hundred to low thousands of rows.
--   If row count is unexpectedly low, verify the period column is a numeric YYYYPP
--   integer (not a string) — compare a sample against the journals extract.
--
-- COLUMNS
--   account         : GL account code — join key to aglaccounts and gl_journals
--   earliest_period : earliest qualifying posting period for this account (YYYYPP)
--   latest_period   : latest qualifying posting period for this account (YYYYPP)
--   posting_count   : total posting lines for this account in the qualifying window
--
-- PERIOD FORMAT
--   YYYYPP integer: 202409 = FY2024/25 period 9 (December 2024).
--   Same convention as all other GL extracts for Parliament.
--
-- HOW THIS IS USED IN THE DASHBOARD
--   GL_ACC_NO_ACTIVITY flags active CoA accounts with no posting in the current-year
--   journals frame (FY2025/26 only). HoL requested the lookback be extended to 18
--   months. This extract provides the extended set of active accounts so the check
--   excludes any account posted to since December 2024, not just since April 2025.
--   The Planner exclusion (aagholp) is a separate extract — see gl_planner_accounts_HOL_run.sql.

SELECT
    account,
    MIN(period)  AS earliest_period,
    MAX(period)  AS latest_period,
    COUNT(*)     AS posting_count
FROM agltransact
WHERE client  = 'LA'
  AND period  >= 202409
  AND (status IS NULL OR status = '')
  AND voucher_type NOT IN ('BU', 'BV')
GROUP BY account
ORDER BY account;
