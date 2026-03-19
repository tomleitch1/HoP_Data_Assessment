-- ============================================================
-- at_asset_master.sql
-- Source:  aatasset
-- Filter:  Both Houses, no status filter - full population
-- Purpose: Full fixed asset master extract. Status filter applied
--          in Python - active only for migration scope, full
--          population for backward compatibility checks against
--          aattrans and aatassetbook
-- ============================================================

SELECT
    -- === IDENTITY ===
    a.client,                    -- Which House - HoC or HoL
    a.asset_id,                  -- Fixed asset identifier - primary key
    a.description,               -- Asset description - main display name
    a.short_info,                -- Short description - secondary label
    a.long_info,                 -- Long description - additional detail
    a.asset_group,               -- Asset group - links to aatassetgroup for depreciation rules
    a.status,                    -- N=Active, C=Closed, P=Parked, T=Terminated

    -- === OWNERSHIP AND DATES ===
    a.date_from,                 -- Date ownership started
    a.date_to,                   -- Date ownership ended - populated on disposed assets
    a.cap_date_from,             -- Date of capitalisation
    a.cap_period_from,           -- Period of capitalisation

    -- === AMOUNTS ===
    a.base_amount,               -- Base amount for depreciation - depreciable cost
    a.org_amount,                -- Original amount - historical cost at acquisition
    a.org_amt_date,              -- Date of original amount
    a.std_amount,                -- Standard amount
    a.std_amt_date,              -- Date of standard amount
    a.ins_amount,                -- Insurance amount

    -- === CLASSIFICATION ===
    a.grant_flag,                -- 1=Grant funded asset, 0=Normal asset
    a.parent_asset,              -- Parent asset_id for component/structure assets
    a.at_attr_id,                -- Asset attribute ID - Parliament-specific asset type

    -- === DIMENSION CODING ===
    a.dim_1,                     -- Analytical category 1 - Cost Centre
    a.dim_2,                     -- Analytical category 2 - Subjective
    a.dim_3,                     -- Analytical category 3
    a.dim_4,                     -- Analytical category 4
    a.dim_5,                     -- Analytical category 5
    a.dim_6,                     -- Analytical category 6
    a.dim_7,                     -- Analytical category 7

    -- === SUPPLIER LINK ===
    a.apar_id,                   -- Supplier ID - links to asuheader where asset was purchased

    -- === PERIOD VALIDITY ===
    a.period_from,               -- From period
    a.period_to,                 -- To period

    -- === WORKFLOW AND AUDIT ===
    a.wf_state,                  -- Workflow state - T=Approved, W=In workflow
    a.last_update                -- Last time this record was modified

FROM aatasset a
WHERE a.client IN ('[HOC_CLIENT]', '[HOL_CLIENT]')
ORDER BY a.client, a.asset_id;


## at_asset_master.sql
## Source: aatasset
## Filter: Both Houses, no status filter - full population
## Purpose: Full fixed asset master extract. Status filter applied
##          in Python - active only for migration scope, full
##          population for backward compatibility checks against
##          transaction and depreciation book data.

---

## Assumptions

| # | Assumption |
|---|---|
| 1 | No status filter applied in SQL - full population extracted regardless of active/inactive |
| 2 | status = 'N' filter applied in Python for migration scope and active asset DQ tests |
| 3 | Full population retained for backward compatibility - checking whether closed or terminated assets still have open depreciation books or transactions against them |
| 4 | Migration scope includes capitalised, non-capitalised, and leased (IFRS 16) assets - all active assets in scope regardless of type |
| 5 | IFRS 16 lease assets are assumed to be identifiable by asset_group - specific group codes to be confirmed with Parliament |
| 6 | grant_flag = 1 identifies grant-funded assets - these may have different migration treatment and should be flagged for business review |
| 7 | parent_asset identifies component assets within a structure - parent record must exist and be active for child assets to migrate cleanly |
| 8 | apar_id links to the purchasing supplier in asuheader - populated where asset was procured through AP. May be blank for internally constructed or donated assets |
| 9 | base_amount is the depreciable cost used in depreciation calculations - distinct from org_amount which is the historical acquisition cost |
| 10 | dim_1 through dim_7 map to Parliament's configured dimensions - attribute_id mapping to be confirmed from gl_dimension_values.sql profile query |
| 11 | date_to populated indicates asset has been disposed or transferred - these are closed assets and not in migration scope unless status = N |
| 12 | cap_date_from is the capitalisation date - assets without a capitalisation date may not yet be fully capitalised and require review before migration |
| 13 | [HOC_CLIENT] and [HOL_CLIENT] are placeholders - actual client codes to be confirmed by Parliament |

---

## Data Quality Tests

### Completeness — Active Assets Only (status = 'N' in Python)

| Test | Fields | Notes |
|---|---|---|
| Total active asset count per House | `client`, `status` | Baseline migration scope population |
| Missing description | `description`, `asset_id` | Asset with no description cannot be reviewed or mapped by business |
| Missing asset_group | `asset_group`, `asset_id` | All assets must belong to a group - drives depreciation rules |
| Missing cap_date_from | `cap_date_from`, `asset_id` | Assets without a capitalisation date cannot have depreciation calculated correctly |
| Missing base_amount | `base_amount`, `asset_id` | Depreciable cost must be populated for any asset subject to depreciation |
| Missing org_amount | `org_amount`, `asset_id` | Original cost should always be populated - blank may indicate incomplete asset setup |
| Missing dim_1 (Cost Centre) | `dim_1`, `asset_id` | Assets must have a cost centre for posting depreciation in new system |

### Validity — Active Assets Only (status = 'N' in Python)

| Test | Fields | Notes |
|---|---|---|
| date_from after date_to | `date_from`, `date_to` | Invalid ownership period - ownership cannot end before it starts |
| cap_date_from before date_from | `cap_date_from`, `date_from` | Asset capitalised before ownership started - likely a data entry error |
| base_amount greater than org_amount | `base_amount`, `org_amount` | Depreciable cost exceeds original cost - may be valid after revaluation but worth flagging |
| base_amount negative | `base_amount` | Negative depreciable cost is not valid |
| wf_state stuck in workflow | `wf_state`, `asset_id` | Assets not yet approved cannot be migrated |
| Active assets with date_to populated | `status`, `date_to` | Status is N but ownership end date is set - contradictory |

### Consistency — Active Assets Only (status = 'N' in Python)

| Test | Fields | Notes |
|---|---|---|
| asset_group references a group that does not exist in aatassetgroup | `asset_group`, `client` | Joined in Python - orphaned asset group reference |
| parent_asset references an asset_id that does not exist | `parent_asset`, `asset_id` | Joined in Python - child asset pointing to non-existent parent |
| parent_asset references an inactive asset | `parent_asset`, `status` | Joined in Python - child asset pointing to closed or terminated parent |
| apar_id references a supplier that does not exist in asuheader | `apar_id`, `client` | Joined in Python to supplier master - purchasing supplier has no master record |
| apar_id references an inactive supplier | `apar_id` | Joined in Python - asset linked to closed supplier |
| dim_1 references inactive or non-existent cost centre | `dim_1`, `client` | Joined to gl_dimension_values - coding string invalid for migration |

### Duplicates — Full Population

| Test | Fields | Notes |
|---|---|---|
| Duplicate asset_id within same House | `client`, `asset_id` | Should be prevented by unique index but worth confirming |
| Same description and asset_group within same House | `description`, `asset_group`, `client` | Possible duplicate assets with different codes |
| Asset codes that exist in HoC but not HoL and vice versa | `asset_id`, `client` | Not errors but consolidation candidates for review |

### Scope — Active Assets Only (status = 'N' in Python)

| Test | Fields | Notes |
|---|---|---|
| Active asset count by asset_group and House | `asset_group`, `client` | Volume by category - helps size migration effort |
| Grant-funded assets (grant_flag = 1) | `grant_flag`, `client` | May need separate migration treatment - flag for business review |
| Component assets with parent_asset populated | `parent_asset`, `client` | Parent-child structures require careful load ordering in new system |
| Assets with no capitalisation date | `cap_date_from`, `client` | May be work-in-progress or non-capitalised assets - scope decision needed |
| Stale assets - last_update older than 3 years | `last_update`, `client` | May indicate assets never actively maintained |
| Assets with no dimension coding (dim_1 null) | `dim_1`, `client` | Cannot post depreci