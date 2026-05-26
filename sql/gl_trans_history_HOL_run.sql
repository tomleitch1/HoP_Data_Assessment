USE agresso_HoL;

-- HOW TO RUN
-- Run against agresso_HoL (server mdata837)  → save as gl_transact_dimensions_HOL.csv

SELECT DISTINCT
    client,
    dim_1,
    dim_2,
    dim_3,
    dim_4,
    dim_5,
    dim_6,
    dim_7
FROM agltransact
WHERE client = 'LA';
