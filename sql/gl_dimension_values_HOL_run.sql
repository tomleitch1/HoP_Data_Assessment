USE agresso_HoL;

-- HOW TO RUN
-- Run against agresso_HoL (server mdata837)  → save as gl_dimension_values_HOL.csv
--
-- OPTIONAL STEP 1: Run the profile query to understand which attribute_ids
--                  map to which dim positions before extracting.
-- STEP 2: Run the main extract directly — it joins agldimension automatically
--         so no manual attribute_id codes need to be entered.

-- ============================================================
-- STEP 1 (optional): Profile — which attribute_id maps to which dim position
-- ============================================================

SELECT client, dim_position, attribute_id, description, status
FROM agldimension
WHERE client = 'LA'
  AND status = 'N'
ORDER BY dim_position, attribute_id;

-- ============================================================
-- STEP 2: Main extract — save this output as gl_dimension_values_HOL.csv
-- ============================================================

SELECT
    d.client,
    d.attribute_id,
    dim.dim_position,
    dim.description AS dim_description,
    d.dim_value,
    d.description,
    d.status,
    d.period_from,
    d.period_to,
    d.rel_value,
    d.last_update,
    d.wf_state
FROM agldimvalue d
INNER JOIN agldimension dim
    ON  dim.attribute_id = d.attribute_id
    AND dim.client       = d.client
    AND dim.status       = 'N'
WHERE d.client = 'LA'
ORDER BY dim.dim_position, d.attribute_id, d.dim_value;
