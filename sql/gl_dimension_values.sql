-- ============================================================
-- gl_dimension_values.sql
-- Source:  agldimvalue
-- Filter:  Both Houses, no status filter - full population
-- Purpose: Full dimension value extract covering all segment types
--          (Cost Centres, Subjectives, Analysis codes etc.)
--          attribute_id values are Parliament-specific and require
--          confirmation via profile query before running against
--          live data. Status filter applied in Python.
-- ============================================================

-- ============================================================
-- HOW TO RUN
-- Run against Agresso_HoC  → save as gl_dimension_values_HOC.csv
-- Run against agresso_HoL  → save as gl_dimension_values_HOL.csv
-- Server: mdata837
-- ============================================================

-- ============================================================
-- STEP 1: Run this profile query first to identify Parliament's
--         attribute_id codes before running the main extract
-- ============================================================

SELECT
    d.client,
    d.attribute_id,              -- Dimension type identifier - Parliament-specific codes
    COUNT(*) AS value_count,     -- How many values exist per dimension
    SUM(CASE WHEN d.status = 'N' THEN 1 ELSE 0 END) AS active_count,
    SUM(CASE WHEN d.status != 'N' THEN 1 ELSE 0 END) AS inactive_count,
    MAX(d.last_update) AS last_updated
FROM agldimvalue d
GROUP BY d.client, d.attribute_id
ORDER BY value_count DESC;

-- ============================================================
-- STEP 2: Main extract - run once attribute_id codes confirmed
-- Replace placeholder values in the WHERE clause with actual
-- attribute_id codes from Step 1 output
-- ============================================================

SELECT
    -- === IDENTITY ===
    d.client,                    -- Internal Unit4 client/fund code (not the house identifier)
    d.attribute_id,              -- Dimension type e.g. COSTC, SUBJ, ANAL1 - Parliament-specific
    d.dim_value,                 -- The segment code itself e.g. cost centre 1000
    d.description,               -- Human readable description of the segment value
    d.status,                    -- N=Active, C=Closed, P=Parked, T=Terminated

    -- === PERIOD VALIDITY ===
    d.period_from,               -- First period this value is valid from
    d.period_to,                 -- Last period this value is valid to

    -- === RELATIONSHIPS ===
    d.rel_value,                 -- Related attribute value - links this value to a parent
                                 -- e.g. Cost Centre 1000 relates to Department A

    -- === AUDIT ===
    d.last_update,               -- Last time this record was modified
    d.wf_state                   -- Workflow state - blank=none, T=approved, W=in workflow

FROM agldimvalue d
WHERE d.attribute_id IN (
      '[ACCOUNT_ATTR_ID]',       -- Account dimension - confirm from Step 1
      '[COSTC_ATTR_ID]',         -- Cost Centre dimension - confirm from Step 1
      '[SUBJ_ATTR_ID]',          -- Subjective dimension - confirm from Step 1
      '[ANAL1_ATTR_ID]',         -- Analysis 1 dimension - confirm from Step 1
      '[ANAL2_ATTR_ID]'          -- Analysis 2 dimension - confirm from Step 1
                                 -- Add further attribute_ids as needed from Step 1
  )
ORDER BY d.attribute_id, d.dim_value;



## gl_dimension_values.sql
## Source: agldimvalue
## Filter: Both Houses, no status filter - full population
## Purpose: Full dimension value extract for all CoA segment types.
##          attribute_id values are Parliament-specific - Step 1 profile
##          query must be run first to identify correct values.
##          Status filter applied in Python.

---

## Assumptions

| # | Assumption |
|---|---|
| 1 | Step 1 profile query must be run first - attribute_id codes are Parliament-specific and cannot be determined from the data dictionary alone |
| 2 | No status filter applied in SQL - full population extracted for backward compatibility checks |
| 3 | status = 'N' filter applied in Python for migration scope and active segment DQ tests |
| 4 | agldimvalue contains dimension values for the entire system not just GL - the attribute_id filter in Step 2 restricts to CoA-relevant dimensions only |
| 5 | Parliament operates at minimum the following dimensions: Account, Cost Centre, Subjective, Analysis 1, Analysis 2 - actual dimension names and attribute_ids to be confirmed |
| 6 | rel_value links a segment value to its parent in a hierarchy e.g. Cost Centre rolls up to Department - hierarchy completeness tests depend on this field being populated |
| 7 | period_from and period_to define the valid date range for each segment value - values outside their valid period should not appear on live transactions |
| 8 | Both Houses may use different attribute_id codes for the same logical dimension - to be confirmed by Step 1 profile query output |
| 9 | [HOC_CLIENT] and [HOL_CLIENT] are placeholders - actual client codes to be confirmed by Parliament |
| 10 | Placeholder attribute_id values in Step 2 WHERE clause to be replaced with actual values from Step 1 output before running against live data |

---

## Data Quality Tests

### Completeness — Active Values Only (status = 'N' in Python)

| Test | Fields | Notes |
|---|---|---|
| Total active segment value count per dimension per House | `client`, `attribute_id`, `status` | Baseline population per dimension for migration scope |
| Missing description | `description`, `dim_value`, `attribute_id` | Segment value with no description cannot be reviewed by business |
| Missing period_from | `period_from`, `dim_value` | Should always be populated |
| Missing rel_value where hierarchy is expected | `rel_value`, `attribute_id` | Cost Centres and Subjectives should roll up to a parent - blank rel_value breaks reporting hierarchy |

### Validity — Active Values Only (status = 'N' in Python)

| Test | Fields | Notes |
|---|---|---|
| period_from greater than period_to | `period_from`, `period_to` | Invalid period range |
| Values where period_to is in the past but status still N | `period_to`, `status` | Period expired but segment still active |
| dim_value format validity per dimension type | `dim_value`, `attribute_id` | e.g. Cost Centres should be numeric 4 digits - format rules to be confirmed with Parliament |
| wf_state stuck in workflow | `wf_state` | Segment values not yet approved - cannot be used on transactions until resolved |

### Consistency — Active Values Only (status = 'N' in Python)

| Test | Fields | Notes |
|---|---|---|
| rel_value references a dim_value that does not exist in the same dimension | `rel_value`, `dim_value`, `attribute_id` | Orphaned hierarchy relationship - parent code does not exist |
| rel_value references an inactive parent | `rel_value`, `status` | Active child segment rolling up to inactive parent - breaks reporting hierarchy |
| Same description used for different dim_value codes within same dimension and House | `description`, `dim_value`, `attribute_id`, `client` | Possible duplicate segment values with slightly different codes |

### Duplicates — Full Population

| Test | Fields | Notes |
|---|---|---|
| Duplicate dim_value within same attribute_id and House | `client`, `attribute_id`, `dim_value` | Should be prevented by unique index but worth confirming |
| Same dim_value and description exists in both Houses under same attribute_id | `attribute_id`, `dim_value`, `description` | Same segment in both Houses - consolidation candidate |
| Values in HoC but not HoL and vice versa per dimension | `attribute_id`, `dim_value`, `client` | House-specific segments - need consolidation decision |

### Scope — Active Values Only (status = 'N' in Python)

| Test | Fields | Notes |
|---|---|---|
| Active segment count by dimension and House | `attribute_id`, `client` | Total migration scope per dimension |
| Stale segment values - last_update older than 3 years | `last_update`, `attribute_id` | May indicate values never used or maintained |
| Segments with no rel_value - no parent hierarchy | `rel_value`, `attribute_id` | Flat segments with no rollup - may be valid or may indicate missing hierarchy setup |

### Backward Compatibility — Full Population joined to agltransact in Python

| Test | Fields | Notes |
|---|---|---|
| Transactions referencing dim_value codes that do not exist in agldimvalue for that attribute_id | `dim_value`, `attribute_id`, `client` | Orphaned dimension values on transactions - would fail load into new system |
| Transactions referencing inactive segment values | `dim_value`, `status`, `attribute_id` | Live transactions coded to closed or terminated segments |

### Backward Compatibility — Full Population joined to aglyearend in Python

| Test | Fields | Notes |
|---|---|---|
| Year end balances referencing dim_value codes that do not exist in agldimvalue | `dim_value`, `attribute_id`, `client` | Balance carried against segment with no master record |
| Year end balances referencing inactive segment values | `dim_value`, `status` | Balance carried on closed or terminated segment |

---

## Outstanding Questions — Parliament Team

| # | Question |
|---|---|
| 1 | Run Step 1 profile query to identify actual attribute_id codes for each dimension before completing Step 2 extract |
| 2 | What are the expected format rules for each dimension value e.g. Cost Centre always 4 numeric digits? Required before format validity tests can be written in Python |
| 3 | Which dimensions use a parent hierarchy via rel_value and which are flat? Determines whether missing rel_value is an error or expected |
| 4 | Does Parliament use the same attribute_id codes in both Houses or are they configured differently per House? |
| 5 | Are there any dimensions beyond Account, Cost Centre, Subjective, Analysis 1 and Analysis 2 that are in scope for migration? |