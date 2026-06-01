USE Agresso_HoC;

-- HOW TO RUN
-- Run against Agresso_HoC (server mdata837)  → save as gl_dimension_config_HOC.csv
-- Save to data/gl/reference/gl_dimension_config_HOC.csv
-- This is a diagnostic/reference extract, not a DQ check input frame.
-- Shows all dimension types defined in agldimension for HOC, joined to agldimvalue
-- for row counts. Used to understand which attribute_ids map to which GL dim positions
-- before scoping the full agldimvalue extract.
--
-- KEY: dim_position values
--   1–7   → maps to dim_1 through dim_7 on GL journal lines — in scope for GL migration
--   A–Z   → header-level or cross-module dimension types — review for relevance
--   X     → not mapped to any GL transaction line — likely out of scope for GL migration
--
-- Clients: CA and CM (both included — same CoA but separate reporting entities)
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
WHERE d.client IN ('CA', 'CM')
  AND d.status = 'N'
GROUP BY d.client, d.attribute_id, d.description, d.dim_position
ORDER BY d.dim_position, d.attribute_id, d.client;
