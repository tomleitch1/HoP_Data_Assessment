USE agresso_HoL;

-- HOW TO RUN
-- Database : agresso_HoL (server mdata837)
-- Output   : gl_planner_accounts_HOL.csv  →  data/gl/
-- Scope    : HoL Planner (aagholp) — distinct GL accounts with a Planner entry
--            in the last 18 months or forecasted for future years.
--            Used by the GL_ACC_NO_ACTIVITY check to exclude accounts that are
--            active in the Planner even if they have no agltransact posting.
--            Period cutoff 202409 = December 2024 (18 months before June 2026).
--            Any period >= 202601 is a future forecast and is also included.
--            Update the cutoff by 1 period each month if re-extracting later.
--            HoL only — aagholp is not present in Agresso_HoC.
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
--   One row per distinct GL account code (dim1) that appears in Planner
--   within the qualifying period window.
--   Expect a few hundred rows at most — this is a compact reference table.
--   If row count is zero, check that dim1 and period column names are correct
--   (run SELECT TOP 5 * FROM aagholp to inspect the actual schema first).
--
-- COLUMNS
--   account         : GL account code (dim1 in aagholp) — join key to aglaccounts
--   earliest_period : earliest qualifying Planner period for this account (YYYYPP)
--   latest_period   : latest qualifying Planner period for this account (YYYYPP)
--   entry_count     : total Planner entries for this account in the qualifying window
--
-- PERIOD FORMAT
--   Same YYYYPP convention as agltransact: 202409 = FY2024/25 period 9 (December 2024).
--   Both current-year and future-year forecast entries are included.
--
-- HOW THIS IS USED IN THE DASHBOARD
--   The GL_ACC_NO_ACTIVITY check flags active CoA accounts with no current-year
--   posting in agltransact. HoL requested that accounts appearing in the Planner
--   module — either recently used or budgeted for future years — are excluded
--   from that check, as they are legitimately active even without a GL posting.

SELECT
    dim1         AS account,
    MIN(period)  AS earliest_period,
    MAX(period)  AS latest_period,
    COUNT(*)     AS entry_count
FROM aagholp
WHERE dim1    IS NOT NULL
  AND dim1    != ''
  AND period  >= 202409
GROUP BY dim1
ORDER BY dim1;
