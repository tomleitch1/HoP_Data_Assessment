USE Agresso_HoC;

-- HOW TO RUN
-- Database : Agresso_HoC (server mdata837)
-- Output   : gl_dimension_values_HOC.csv  →  data/gl/
-- Scope    : GL-mapped dimension attributes only (dim_position 0–7).
--            Excludes the 650+ X-position and letter-coded attributes that are
--            out of scope for GL journal line migration.
--            Active values only (status = N). Orphan checks work with active-only
--            data: if a parent (rel_value) is not present as an active value in the
--            same attribute, it is either closed or missing — both are flagged.
--
-- EXTRACTION TIPS
--   Enable column headers: Tools → Options → Query Results → SQL Server →
--     Results to Grid → tick "Include column headers when copying or saving results"
--     (close and reopen the query tab for the setting to take effect)
--   Save via "Save Results As" — go to C:\Users\leitchtb\HoP_Data_Assessment\data\gl\
--   Do NOT open the CSV by double-clicking — use Excel Data → Get Data → From Text/CSV
--     and set dim_value, rel_value to Text type to preserve leading zeros.
--
-- EXPECTED OUTPUT
--   HOC has two in-scope client codes (CA and CM) — both are included.
--   Expect roughly 5,000–20,000 rows (GL positions, active values only).
--   If the row count looks unexpectedly high, re-check that dim.dim_position
--   IN ('0','1','2','3','4','5','6','7') is filtering correctly.
--
-- COLUMNS
--   client         : CA or CM
--   attribute_id   : dimension type code (e.g. COSTC, SUBJ)
--   dim_position   : GL journal position (1–7; 0 included if present)
--   dim_description: human-readable name for the attribute type
--   dim_value      : the actual code (e.g. ITSERV, 1000)
--   description    : human-readable label for this value
--   status         : N = active, C = closed
--   period_from    : validity start (Excel serial integer from SSMS)
--   period_to      : validity end  (Excel serial integer from SSMS)
--   rel_value      : parent code in the dimension hierarchy (blank = root)
--   last_update    : last modified date (Excel serial integer from SSMS)
--   wf_state       : workflow state — blank or T = approved, W = pending approval
--
-- DQ CHECKS THIS EXTRACT ENABLES
--   GL_DIM_DESC_MISSING   Active value has no description
--   GL_DIM_PERIOD_MISSING Active value missing valid-from date
--   GL_DIM_PERIOD_INV     Valid-from date is after valid-to date
--   GL_DIM_WF_STUCK       Active value stuck in pending workflow state (wf_state = W)
--   GL_DIM_ORPHAN_REL     Active value whose parent (rel_value) is missing or closed
--   GL_DIM_DUP            Duplicate dim_value code within the same attribute and house

SELECT
    d.client,
    d.attribute_id,
    dim.dim_position,
    dim.description                      AS dim_description,
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
WHERE d.client IN ('CA', 'CM')
  AND d.status = 'N'
  AND dim.dim_position IN ('0', '1', '2', '3', '4', '5', '6', '7')
ORDER BY dim.dim_position, d.attribute_id, d.client, d.dim_value;
