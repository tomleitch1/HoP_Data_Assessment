USE agresso_HoL;

-- HOW TO RUN
-- Run against agresso_HoL (server mdata837)  → save as gl_dimension_config_HOL.csv
-- Save to data/gl/reference/gl_dimension_config_HOL.csv
-- This is a diagnostic/reference extract, not a DQ check input frame.
-- Shows all dimension types defined in agldimension for HOL, joined to agldimvalue
-- for row counts. Used to understand which attribute_ids map to which GL dim positions
-- before scoping the full agldimvalue extract.
--
-- KEY: dim_position values
--   1–7   → maps to dim_1 through dim_7 on GL journal lines — in scope for GL migration
--   A–Z   → header-level or cross-module dimension types — review for relevance
--   X     → not mapped to any GL transaction line — likely out of scope for GL migration
--
-- Client: LA only
-- status = 'N' on agldimension filters to active dimension type definitions only

SELECT
    d.client,
    d.attribute_id,
    d.description,
    d.dim_position,
    COUNT(v.dim_value)                                           AS total_values,
    SUM(CASE WHEN v.status = 'N' THEN 1 ELSE 0 END)             AS active,
    SUM(CASE WHEN v.status = 'C' THEN 1 ELSE 0 END)             AS closed
FROM agldimension d
LEFT JOIN agldimvalue v
    ON  v.attribute_id = d.attribute_id
    AND v.client       = d.client
WHERE d.client = 'LA'
  AND d.status = 'N'
GROUP BY d.client, d.attribute_id, d.description, d.dim_position
ORDER BY d.dim_position, d.attribute_id, d.client;
