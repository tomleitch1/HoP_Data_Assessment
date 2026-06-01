USE Agresso_HoC;

-- HOW TO RUN
-- Database : Agresso_HoC (server mdata837)
-- Output   : gl_transact_dimensions_HOC.csv  →  data/gl/
-- Scope    : Distinct dimension codes actually used on GL postings in the
--            current fiscal year. HOC uses the start-year convention:
--            fiscal_year = 2025 covers FY2025/26.
--            One row per unique (client, dim_position, dim_value) combination.
--            This is NOT a transaction-level extract — it is a reference extract
--            of which dimension codes are in active use on posted GL lines.
--
-- WHY THIS EXTRACT EXISTS
--   agldimvalue defines the full set of valid dimension values and their
--   hierarchy (via rel_value). Some values are leaf nodes (no children) and
--   some are summary/rollup nodes (have children). Best practice is that
--   postings should only land on leaf nodes — posting to a summary node is
--   ambiguous and may not roll up correctly in the target ERP.
--   This extract provides the "which codes are actually posted to" side of
--   that check, joined against agldimvalue hierarchy in Python.
--
-- EXTRACTION TIPS
--   Enable column headers: Tools → Options → Query Results → SQL Server →
--     Results to Grid → tick "Include column headers when copying or saving results"
--     (close and reopen the query tab for the setting to take effect)
--   Save via "Save Results As" — navigate to C:\Users\leitchtb\HoP_Data_Assessment\data\gl\
--   Expected row count: a few thousand at most (distinct codes, not transaction lines).
--   If the count looks unexpectedly high, verify the UNION ALL structure is correct
--   and that the fiscal_year filter is applied to every branch.
--
-- COLUMNS
--   client       : CA or CM
--   dim_position : which GL dimension slot (1–7) this value was posted to
--   dim_value    : the dimension code used on that posting
--
-- DQ CHECKS THIS EXTRACT ENABLES
--   GL_DIM_POST_SUMMARY  Posting made to a summary (non-leaf) dimension node —
--                        the dim_value appears as a parent (rel_value) of another
--                        active value in agldimvalue for the same position/client.
--                        Postings should only land on leaf nodes.

SELECT DISTINCT client, '1' AS dim_position, dim_1 AS dim_value
FROM agltransact
WHERE client IN ('CA', 'CM')
  AND fiscal_year = 2025
  AND (status IS NULL OR status = '')
  AND voucher_type NOT IN ('BU', 'BV')
  AND dim_1 IS NOT NULL AND dim_1 != ''

UNION ALL

SELECT DISTINCT client, '2', dim_2
FROM agltransact
WHERE client IN ('CA', 'CM')
  AND fiscal_year = 2025
  AND (status IS NULL OR status = '')
  AND voucher_type NOT IN ('BU', 'BV')
  AND dim_2 IS NOT NULL AND dim_2 != ''

UNION ALL

SELECT DISTINCT client, '3', dim_3
FROM agltransact
WHERE client IN ('CA', 'CM')
  AND fiscal_year = 2025
  AND (status IS NULL OR status = '')
  AND voucher_type NOT IN ('BU', 'BV')
  AND dim_3 IS NOT NULL AND dim_3 != ''

UNION ALL

SELECT DISTINCT client, '4', dim_4
FROM agltransact
WHERE client IN ('CA', 'CM')
  AND fiscal_year = 2025
  AND (status IS NULL OR status = '')
  AND voucher_type NOT IN ('BU', 'BV')
  AND dim_4 IS NOT NULL AND dim_4 != ''

UNION ALL

SELECT DISTINCT client, '5', dim_5
FROM agltransact
WHERE client IN ('CA', 'CM')
  AND fiscal_year = 2025
  AND (status IS NULL OR status = '')
  AND voucher_type NOT IN ('BU', 'BV')
  AND dim_5 IS NOT NULL AND dim_5 != ''

UNION ALL

SELECT DISTINCT client, '6', dim_6
FROM agltransact
WHERE client IN ('CA', 'CM')
  AND fiscal_year = 2025
  AND (status IS NULL OR status = '')
  AND voucher_type NOT IN ('BU', 'BV')
  AND dim_6 IS NOT NULL AND dim_6 != ''

UNION ALL

SELECT DISTINCT client, '7', dim_7
FROM agltransact
WHERE client IN ('CA', 'CM')
  AND fiscal_year = 2025
  AND (status IS NULL OR status = '')
  AND voucher_type NOT IN ('BU', 'BV')
  AND dim_7 IS NOT NULL AND dim_7 != ''

ORDER BY dim_position, client, dim_value;
