USE Agresso_HoC;

-- ============================================================
-- BUDGET / PLANNER MODULE — EXPLORATORY PROFILING
-- Database : Agresso_HoC (server mdata837)
-- Purpose  : Discover the structure, scale, and key dimensions
--            of the apl* (Agresso Planner) tables before writing
--            any extraction queries or DQ checks.
--
-- HOW TO USE
--   Run each section independently (highlight + F5) so you can
--   read each result set before moving on.  Do not run all at
--   once — the schema queries are fast but some profiling
--   queries on apltransact may take 30–60 seconds.
--
-- SECTIONS
--   1. apl* table inventory and row counts
--   2. apltransact column schema
--   3. Distinct clients and total row count
--   4. Budget model / version / scenario codes
--   5. Fiscal year and period distribution
--   6. Amount statistics (scale, nulls, sign)
--   7. Key dimension columns (account, dim_1, status)
--   8. Sample rows (first 50)
--   9. Related apl tables — spot-check schemas
-- ============================================================


-- ============================================================
-- SECTION 1 — All apl* tables: names and row counts
-- Run this first to see the full picture of the planning module.
-- ============================================================

SELECT
    t.name                          AS table_name,
    SUM(p.rows)                     AS row_count
FROM sys.tables t
JOIN sys.partitions p ON t.object_id = p.object_id
WHERE t.name LIKE 'apl%'
  AND p.index_id < 2   -- heap or clustered index only (avoids double-counting)
GROUP BY t.name
ORDER BY row_count DESC;


-- ============================================================
-- SECTION 2 — apltransact column schema
-- Review this carefully before running the profiling queries below.
-- The column names in sections 3–8 are best guesses from the
-- standard Unit4 Agresso schema — adjust if real names differ.
-- ============================================================

SELECT
    COLUMN_NAME,
    DATA_TYPE,
    CHARACTER_MAXIMUM_LENGTH,
    IS_NULLABLE,
    ORDINAL_POSITION
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'apltransact'
ORDER BY ORDINAL_POSITION;


-- ============================================================
-- SECTION 3 — Distinct clients and total row count
-- ============================================================

SELECT
    client,
    COUNT(*)    AS row_count
FROM apltransact
GROUP BY client
ORDER BY row_count DESC;


-- ============================================================
-- SECTION 4 — Budget model / version / scenario codes
-- The planning module stores budgets in named "models" or
-- "scenarios" (original budget, revised, forecast Q1, etc.).
-- This is the most important structural question:
--   - What column holds the model/version identifier?
--   - What values does it contain?
--   - Which models are "current" vs historical?
--
-- Common column names in apl tables: model_id, budget_id,
-- version_id, scenario_id, attribute_id, plan_id.
-- Adjust the GROUP BY column once you know the real name.
-- ============================================================

-- Try model_id first (most common in standard Unit4):
SELECT
    client,
    model_id,
    COUNT(*)    AS row_count,
    SUM(amount) AS total_amount
FROM apltransact
GROUP BY client, model_id
ORDER BY client, row_count DESC;

-- If model_id doesn't exist, try these alternatives one at a time:
--   budget_id, version_id, scenario_id, attribute_id, plan_id, budget_model


-- ============================================================
-- SECTION 5 — Fiscal year and period distribution
-- How many years of budget history are held?
-- Are periods in YYYYPP format like agltransact / aglperiodic?
-- ============================================================

SELECT
    client,
    fiscal_year,
    MIN(period)     AS earliest_period,
    MAX(period)     AS latest_period,
    COUNT(*)        AS row_count
FROM apltransact
GROUP BY client, fiscal_year
ORDER BY client, fiscal_year DESC;


-- ============================================================
-- SECTION 6 — Amount statistics
-- Budget amounts: what is the scale, are there nulls,
-- are amounts signed or always positive?
-- ============================================================

SELECT
    client,
    COUNT(*)                AS total_rows,
    COUNT(amount)           AS non_null_amounts,
    COUNT(*) - COUNT(amount) AS null_amounts,
    SUM(CASE WHEN amount > 0 THEN 1 ELSE 0 END) AS positive_rows,
    SUM(CASE WHEN amount < 0 THEN 1 ELSE 0 END) AS negative_rows,
    SUM(CASE WHEN amount = 0 THEN 1 ELSE 0 END) AS zero_rows,
    MIN(amount)             AS min_amount,
    MAX(amount)             AS max_amount,
    SUM(amount)             AS total_amount
FROM apltransact
WHERE client IN ('CA', 'CM')
GROUP BY client;


-- ============================================================
-- SECTION 7 — Key dimension columns
-- How populated are the join fields?
-- ============================================================

-- Account coverage
SELECT
    client,
    COUNT(*)                            AS total_rows,
    COUNT(account)                      AS account_populated,
    COUNT(*) - COUNT(account)           AS account_missing,
    COUNT(DISTINCT account)             AS distinct_accounts
FROM apltransact
WHERE client IN ('CA', 'CM')
GROUP BY client;

-- dim_1 coverage
SELECT
    client,
    COUNT(*)                            AS total_rows,
    COUNT(NULLIF(dim_1,''))             AS dim1_populated,
    COUNT(*) - COUNT(NULLIF(dim_1,''))  AS dim1_missing,
    COUNT(DISTINCT NULLIF(dim_1,''))    AS distinct_dim1_values
FROM apltransact
WHERE client IN ('CA', 'CM')
GROUP BY client;

-- Status codes
SELECT
    client,
    ISNULL(NULLIF(status,''), '(blank)') AS status,
    COUNT(*)                             AS row_count
FROM apltransact
WHERE client IN ('CA', 'CM')
GROUP BY client, ISNULL(NULLIF(status,''), '(blank)')
ORDER BY client, row_count DESC;

-- Voucher / transaction type codes (if column exists)
SELECT
    client,
    ISNULL(NULLIF(voucher_type,''), '(blank)') AS voucher_type,
    COUNT(*)                                   AS row_count
FROM apltransact
WHERE client IN ('CA', 'CM')
GROUP BY client, ISNULL(NULLIF(voucher_type,''), '(blank)')
ORDER BY client, row_count DESC;


-- ============================================================
-- SECTION 8 — Sample rows (read the actual data)
-- Run after reviewing the schema from Section 2.
-- Adjust the ORDER BY once you know the key columns.
-- ============================================================

SELECT TOP 50 *
FROM apltransact
WHERE client IN ('CA', 'CM')
ORDER BY client;


-- ============================================================
-- SECTION 9 — Related apl tables — spot-check schemas
-- After reviewing the row-count list from Section 1, run
-- INFORMATION_SCHEMA queries on the other significant tables.
-- Budget models / versions / scenarios are usually defined in
-- a header table (e.g. aplbudget, aplmodel, aplversion).
-- ============================================================

-- Example — replace 'aplmodel' with whatever the header table is called:
--
-- SELECT
--     COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, ORDINAL_POSITION
-- FROM INFORMATION_SCHEMA.COLUMNS
-- WHERE TABLE_NAME = 'aplmodel'
-- ORDER BY ORDINAL_POSITION;
--
-- SELECT TOP 50 * FROM aplmodel WHERE client IN ('CA','CM');
