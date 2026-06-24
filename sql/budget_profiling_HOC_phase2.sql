USE Agresso_HoC;

-- ============================================================
-- BUDGET / PLANNER MODULE — PHASE 2 PROFILING
-- Database : Agresso_HoC (server mdata837)
-- Purpose  : Understand the key categorical dimensions of
--            apltransact now that the schema is known.
--            Run each section independently (highlight + F5).
--
-- Focus client: CA only (CM has only 8 rows and is out of scope)
-- ============================================================


-- ============================================================
-- SECTION 1 — Budget versions / scenarios
-- This is the most important structural question.
-- What named budget models exist, and how much data each holds?
-- e.g. ORIG (original budget), REV (revised), FCT (forecast),
-- Q1/Q2/Q3 (quarterly forecasts), etc.
-- ============================================================

SELECT
    version,
    COUNT(*)            AS row_count,
    SUM(period_value)   AS total_value,
    MIN(period_from)    AS earliest_from,
    MAX(period_to)      AS latest_to
FROM apltransact
WHERE client = 'CA'
GROUP BY version
ORDER BY row_count DESC;


-- ============================================================
-- SECTION 2 — Transaction types
-- What planning transaction types are used?
-- e.g. BUDGET, VIREMENT, ADJUSTMENT, TRANSFER
-- ============================================================

SELECT
    trans_type,
    COUNT(*)            AS row_count,
    SUM(period_value)   AS total_value
FROM apltransact
WHERE client = 'CA'
GROUP BY trans_type
ORDER BY row_count DESC;


-- ============================================================
-- SECTION 3 — Status and workflow state
-- Which records are live vs. draft/cancelled?
-- ============================================================

SELECT
    ISNULL(NULLIF(status,''),   '(blank)') AS status,
    ISNULL(NULLIF(wf_state,''), '(blank)') AS wf_state,
    COUNT(*)                               AS row_count
FROM apltransact
WHERE client = 'CA'
GROUP BY status, wf_state
ORDER BY row_count DESC;


-- ============================================================
-- SECTION 4 — Period range: format and distribution
-- What is the period_from / period_to format?
-- Is it YYYYPP (fiscal like agltransact), YYYYMM (calendar),
-- or something else?
-- ============================================================

SELECT
    MIN(period_from)    AS min_period_from,
    MAX(period_from)    AS max_period_from,
    MIN(period_to)      AS min_period_to,
    MAX(period_to)      AS max_period_to,
    COUNT(*)            AS total_rows,
    SUM(CASE WHEN period_from IS NULL THEN 1 ELSE 0 END) AS null_period_from,
    SUM(CASE WHEN period_to   IS NULL THEN 1 ELSE 0 END) AS null_period_to,
    SUM(CASE WHEN period_from = period_to THEN 1 ELSE 0 END) AS single_period_rows,
    SUM(CASE WHEN period_from <> period_to THEN 1 ELSE 0 END) AS multi_period_rows
FROM apltransact
WHERE client = 'CA';

-- Distribution by period_from (top 30 most common)
SELECT TOP 30
    period_from,
    COUNT(*)            AS row_count,
    SUM(period_value)   AS total_value
FROM apltransact
WHERE client = 'CA'
GROUP BY period_from
ORDER BY period_from DESC;


-- ============================================================
-- SECTION 5 — Budget book (bb_book_id)
-- Analogous to the depreciation book in the asset module.
-- Are there multiple books (e.g. approved vs. working draft)?
-- ============================================================

SELECT
    ISNULL(NULLIF(bb_book_id,''), '(blank)') AS bb_book_id,
    COUNT(*)                                 AS row_count,
    SUM(period_value)                        AS total_value
FROM apltransact
WHERE client = 'CA'
GROUP BY bb_book_id
ORDER BY row_count DESC;


-- ============================================================
-- SECTION 6 — Hierarchy levels
-- level_no defines where in the planning hierarchy a row sits.
-- Level 1 is typically the leaf (postable) level.
-- Higher levels aggregate up.  Only leaf-level rows have
-- financial values — others are summary nodes.
-- ============================================================

SELECT
    level_no,
    COUNT(*)                                        AS row_count,
    SUM(period_value)                               AS total_value,
    SUM(CASE WHEN period_value IS NULL THEN 1 ELSE 0 END) AS null_values,
    SUM(CASE WHEN period_value = 0    THEN 1 ELSE 0 END)  AS zero_values
FROM apltransact
WHERE client = 'CA'
GROUP BY level_no
ORDER BY level_no;


-- ============================================================
-- SECTION 7 — Planning attributes (att_1_id through att_7_id)
-- These are planner-specific attributes, separate from the GL
-- dim_* columns.  Are they actually used or mostly blank?
-- ============================================================

SELECT
    COUNT(NULLIF(att_1_id,''))  AS att1_populated,
    COUNT(NULLIF(att_2_id,''))  AS att2_populated,
    COUNT(NULLIF(att_3_id,''))  AS att3_populated,
    COUNT(NULLIF(att_4_id,''))  AS att4_populated,
    COUNT(NULLIF(att_5_id,''))  AS att5_populated,
    COUNT(NULLIF(att_6_id,''))  AS att6_populated,
    COUNT(NULLIF(att_7_id,''))  AS att7_populated,
    COUNT(*)                    AS total_rows
FROM apltransact
WHERE client = 'CA';

-- If any att_* is populated, check distinct values for those columns:
-- SELECT DISTINCT att_1_id FROM apltransact WHERE client = 'CA' AND att_1_id != '';


-- ============================================================
-- SECTION 8 — GL dimension coverage (dim_1 through dim_7)
-- Budget lines should reference valid GL dimension values.
-- Which dim_* columns are actually used?
-- ============================================================

SELECT
    COUNT(NULLIF(dim_1,''))  AS dim1_populated,
    COUNT(NULLIF(dim_2,''))  AS dim2_populated,
    COUNT(NULLIF(dim_3,''))  AS dim3_populated,
    COUNT(NULLIF(dim_4,''))  AS dim4_populated,
    COUNT(NULLIF(dim_5,''))  AS dim5_populated,
    COUNT(NULLIF(dim_6,''))  AS dim6_populated,
    COUNT(NULLIF(dim_7,''))  AS dim7_populated,
    COUNT(*)                 AS total_rows
FROM apltransact
WHERE client = 'CA';


-- ============================================================
-- SECTION 9 — Account coverage
-- What proportion of rows have an account code?
-- Cross-reference with aglaccounts to check orphan rate.
-- ============================================================

SELECT
    COUNT(*)                                    AS total_rows,
    COUNT(NULLIF(account,''))                   AS account_populated,
    COUNT(*) - COUNT(NULLIF(account,''))        AS account_missing,
    COUNT(DISTINCT NULLIF(account,''))          AS distinct_accounts
FROM apltransact
WHERE client = 'CA';

-- What accounts are most common in budget entries?
SELECT TOP 20
    account,
    COUNT(*)            AS row_count,
    SUM(period_value)   AS total_value
FROM apltransact
WHERE client = 'CA'
  AND account != ''
GROUP BY account
ORDER BY ABS(SUM(period_value)) DESC;


-- ============================================================
-- SECTION 10 — Cross-version: versions × trans_types
-- Understand which version+trans_type combinations exist.
-- e.g. Original budget only has BUDGET type; virements only
-- appear in revised/forecast versions, etc.
-- ============================================================

SELECT
    version,
    trans_type,
    COUNT(*)            AS row_count,
    SUM(period_value)   AS total_value
FROM apltransact
WHERE client = 'CA'
GROUP BY version, trans_type
ORDER BY version, row_count DESC;


-- ============================================================
-- SECTION 11 — Sample rows by version
-- Read a few actual rows from the most important version(s).
-- Replace 'ORIG' with whatever the current budget version is
-- called once Section 1 reveals the version names.
-- ============================================================

-- Sample from the largest version (replace version value after running Section 1):
SELECT TOP 30 *
FROM apltransact
WHERE client = 'CA'
  AND version = 'ORIG'   -- <-- replace with actual version name from Section 1
ORDER BY account, period_from;


-- ============================================================
-- SECTION 12 — apl* related tables — schema and row counts
-- for the tables found in phase 1 that look like budget headers
-- or model definitions.  Replace table names with whatever
-- was returned in phase 1 section 1.
-- Run after reviewing which apl* tables exist.
-- ============================================================

-- Budget model / version header table (replace name as needed):
-- SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, ORDINAL_POSITION
-- FROM INFORMATION_SCHEMA.COLUMNS
-- WHERE TABLE_NAME = 'aplmodel'   -- <-- replace with actual table name
-- ORDER BY ORDINAL_POSITION;

-- SELECT TOP 50 * FROM aplmodel WHERE client = 'CA';
