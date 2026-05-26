USE Agresso_HoC;

-- HOW TO RUN
-- Run against Agresso_HoC (server mdata837)  → save as gl_dimension_values_HOC.csv
--
-- STEP 1: Run the mapping query to find which attribute_id maps to each dim position.
-- STEP 2: Copy the attribute_id values from the Step 1 results into the WHERE clause below.
-- STEP 3: Run Step 2 and save the output as gl_dimension_values_HOC.csv

-- ============================================================
-- STEP 1: Map dim positions to attribute_id codes
-- ============================================================

SELECT 'dim_1' AS dim_pos, d.attribute_id, COUNT(*) AS match_count
FROM (SELECT DISTINCT dim_1 AS val FROM agltransact WHERE client IN ('CA', 'CM') AND dim_1 IS NOT NULL) t
JOIN agldimvalue d ON d.dim_value = t.val AND d.client IN ('CA', 'CM')
GROUP BY d.attribute_id

UNION ALL

SELECT 'dim_2', d.attribute_id, COUNT(*)
FROM (SELECT DISTINCT dim_2 AS val FROM agltransact WHERE client IN ('CA', 'CM') AND dim_2 IS NOT NULL) t
JOIN agldimvalue d ON d.dim_value = t.val AND d.client IN ('CA', 'CM')
GROUP BY d.attribute_id

UNION ALL

SELECT 'dim_3', d.attribute_id, COUNT(*)
FROM (SELECT DISTINCT dim_3 AS val FROM agltransact WHERE client IN ('CA', 'CM') AND dim_3 IS NOT NULL) t
JOIN agldimvalue d ON d.dim_value = t.val AND d.client IN ('CA', 'CM')
GROUP BY d.attribute_id

UNION ALL

SELECT 'dim_4', d.attribute_id, COUNT(*)
FROM (SELECT DISTINCT dim_4 AS val FROM agltransact WHERE client IN ('CA', 'CM') AND dim_4 IS NOT NULL) t
JOIN agldimvalue d ON d.dim_value = t.val AND d.client IN ('CA', 'CM')
GROUP BY d.attribute_id

UNION ALL

SELECT 'dim_5', d.attribute_id, COUNT(*)
FROM (SELECT DISTINCT dim_5 AS val FROM agltransact WHERE client IN ('CA', 'CM') AND dim_5 IS NOT NULL) t
JOIN agldimvalue d ON d.dim_value = t.val AND d.client IN ('CA', 'CM')
GROUP BY d.attribute_id

UNION ALL

SELECT 'dim_6', d.attribute_id, COUNT(*)
FROM (SELECT DISTINCT dim_6 AS val FROM agltransact WHERE client IN ('CA', 'CM') AND dim_6 IS NOT NULL) t
JOIN agldimvalue d ON d.dim_value = t.val AND d.client IN ('CA', 'CM')
GROUP BY d.attribute_id

UNION ALL

SELECT 'dim_7', d.attribute_id, COUNT(*)
FROM (SELECT DISTINCT dim_7 AS val FROM agltransact WHERE client IN ('CA', 'CM') AND dim_7 IS NOT NULL) t
JOIN agldimvalue d ON d.dim_value = t.val AND d.client IN ('CA', 'CM')
GROUP BY d.attribute_id

ORDER BY dim_pos, match_count DESC;

-- ============================================================
-- STEP 2: Main extract — replace attribute_id placeholders
--         with actual codes from Step 1 output above
-- ============================================================

SELECT
    d.client,
    d.attribute_id,
    d.dim_value,
    d.description,
    d.status,
    d.period_from,
    d.period_to,
    d.rel_value,
    d.last_update,
    d.wf_state
FROM agldimvalue d
WHERE d.client IN ('CA', 'CM')
  AND d.attribute_id IN (
    '[DIM_1_ATTR_ID]',
    '[DIM_2_ATTR_ID]',
    '[DIM_3_ATTR_ID]',
    '[DIM_4_ATTR_ID]',
    '[DIM_5_ATTR_ID]',
    '[DIM_6_ATTR_ID]',
    '[DIM_7_ATTR_ID]'
)
ORDER BY d.attribute_id, d.dim_value;
