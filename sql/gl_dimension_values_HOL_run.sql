USE agresso_HoL;

-- HOW TO RUN
-- Run against agresso_HoL (server mdata837)  → save as gl_dimension_values_HOL.csv

-- ============================================================
-- STEP 1: Run first to identify Parliament's attribute_id codes
-- ============================================================

SELECT
    d.client,
    d.attribute_id,
    COUNT(*) AS value_count,
    SUM(CASE WHEN d.status = 'N' THEN 1 ELSE 0 END) AS active_count,
    SUM(CASE WHEN d.status != 'N' THEN 1 ELSE 0 END) AS inactive_count,
    MAX(d.last_update) AS last_updated
FROM agldimvalue d
WHERE d.client = 'LA'
GROUP BY d.client, d.attribute_id
ORDER BY value_count DESC;

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
WHERE d.client = 'LA'
  AND d.attribute_id IN (
    '[ACCOUNT_ATTR_ID]',
    '[COSTC_ATTR_ID]',
    '[SUBJ_ATTR_ID]',
    '[ANAL1_ATTR_ID]',
    '[ANAL2_ATTR_ID]'
)
ORDER BY d.attribute_id, d.dim_value;
