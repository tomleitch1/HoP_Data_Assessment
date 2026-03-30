-- =============================================================================
-- asset_master.sql
-- Houses of Parliament — Finance Systems Programme
-- Fixed Asset Master Extract
-- Migration scope: Seq 12 (Fixed Asset Registry)
-- Source table: aatasset
-- =============================================================================
--
-- INSTANCE & CLIENT
-- Run this script separately against the HoC instance and the HoL instance.
-- HoC instance has three clients: CA (Common Administration), CF (Miscellaneous
-- Fund), CM (Members Fund). HoL instance has one client: LA.
-- 'client' identifies the fund/sub-entity within a house — it does NOT identify
-- the house itself. The house is implicit from which instance you ran this query
-- against. Add a 'house' column in Python after load (e.g. df['house'] = 'HOC').
-- No client filter is applied — all clients are extracted. Python handles any
-- fund-level breakdowns.
--
-- EXTRACTION APPROACH
-- No WHERE clause. All asset statuses are extracted so Python can:
--   (a) filter to active (status = 'N') for migration scoping, and
--   (b) retain the full population for backward compatibility checks against
--       transaction data and to produce the archive candidate list.
-- All joins, calculations, and DQ logic are handled in Python, not SQL.
--
-- MIGRATION SCOPE LOGIC (applied in Python, not here)
-- In scope for migration (Seq 12): status = 'N' (Normal/active), covering
-- capitalised, non-capitalised, and leased (IFRS16) assets from both houses.
-- Out of scope (archive candidates): status in ('C', 'T') — Closed/Terminated.
-- Parked assets (status = 'P') require Parliament confirmation before categorising
-- as in or out of scope.
-- IFRS16 leased assets are expected to be identifiable by asset_group or
-- depreciation book naming convention — confirm with Parliament before finalising
-- the leased asset population.
-- Component/child assets (where parent_asset is populated) are in scope only if
-- their parent asset is also in scope. Python must validate parent-child integrity.
--
-- ASSUMPTIONS
-- A1. Active assets are status = 'N'. No other status code denotes active.
-- A2. Non-capitalised assets (cap_date_from null) are legitimately in scope per
--     Seq 12 — the scope explicitly includes non-capitalised assets.
-- A3. org_amount may be null for non-capitalised assets. This is not a DQ failure
--     for those assets. For capitalised assets (cap_date_from populated), a null
--     or zero org_amount is a failure.
-- A4. The same asset_id appearing in both HoC and HoL is a separate physical
--     asset in each house — not a duplicate. Cross-house deduplication must not
--     be performed. Flag cross-house matches for Parliament awareness only.
-- A5. dim_1 through dim_7 map to CoA analytical segments. The mapping of each
--     dimension number to a segment label (e.g. Cost Centre, Subjective) must be
--     confirmed with Parliament before Python profiling of these fields.
-- A6. wf_state values of W, R, U, or X on an active asset indicate an in-flight
--     or stuck workflow. These assets should not be migrated until the workflow
--     is resolved. Assumption is that 'T' (approved) and blank/'N' are clean states.
-- A7. ins_amount (insurance value) may legitimately be null or zero. Not a hard
--     DQ failure — flagged as an advisory gap rather than a blocking issue.
--
-- =============================================================================
-- DATA QUALITY TESTS (all executed in Python against the CSV output)
-- =============================================================================
--
-- COMPLETENESS
-- DQ-AM-C01 [Critical]  asset_id is null or blank.
--            No asset can exist without a primary key. Blocking for migration.
-- DQ-AM-C02 [High]      description is null or blank for status = 'N'.
--            Active assets must have a human-readable identifier in the new system.
-- DQ-AM-C03 [High]      asset_group is null or blank for status = 'N'.
--            Asset group drives depreciation defaults and GL account mapping.
--            Missing group breaks downstream migration dependencies.
-- DQ-AM-C04 [High]      date_from is null for status = 'N'.
--            Ownership start date must be present for all active assets.
-- DQ-AM-C05 [High]      org_amount is null or zero for status = 'N' where
--            cap_date_from is not null (i.e. capitalised active asset with no cost).
-- DQ-AM-C06 [Medium]    cap_date_from is null for status = 'N' where
--            cap_flag is expected to be true (confirm cap_flag source with Parliament
--            — this field lives on aatassetbook, not aatasset; cross-extract test).
-- DQ-AM-C07 [Advisory]  ins_amount is null or zero for status = 'N'.
--            Not a migration blocker but a completeness gap worth surfacing.
--
-- VALIDITY
-- DQ-AM-V01 [Critical]  status not in ('N', 'P', 'C', 'T').
--            Unexpected status code — indicates corrupt or non-standard data.
-- DQ-AM-V02 [High]      wf_state not in ('', 'N', 'T', 'A', 'C', 'R', 'U', 'W', 'X').
--            Value outside the documented valuelist — data integrity issue.
-- DQ-AM-V03 [High]      org_amount is negative for any status.
--            Negative original cost is not valid for an asset record.
-- DQ-AM-V04 [High]      date_from is after date_to where both are populated.
--            Ownership cannot end before it begins.
-- DQ-AM-V05 [Medium]    cap_date_from is before date_from.
--            An asset cannot be capitalised before ownership started.
-- DQ-AM-V06 [Medium]    org_amt_date differs from cap_date_from by more than
--            365 days. May indicate the cost was recorded at a significantly
--            different time to capitalisation — worth querying with finance.
-- DQ-AM-V07 [Medium]    last_update is in the future (beyond today's date).
--            Indicates a system clock or data entry error.
--
-- CONSISTENCY
-- DQ-AM-K01 [High]      date_to is populated but status = 'N'.
--            Asset shows as active but ownership has ended. Contradictory state.
-- DQ-AM-K02 [High]      wf_state in ('W', 'R', 'U', 'X') and status = 'N'.
--            Active asset has an in-flight or stuck workflow. Must be resolved
--            before migration. Produce a list for Parliament to action.
-- DQ-AM-K03 [Medium]    org_amt_date is null but org_amount is populated.
--            The cost amount exists but has no date — incomplete record.
-- DQ-AM-K04 [Medium]    grant_flag = 1 but no grant-related dim value is present
--            (requires Parliament to confirm which dim field carries grant coding).
--
-- DUPLICATES
-- DQ-AM-D01 [Critical]  Duplicate asset_id within the same client.
--            Primary key violation within a fund — blocking for migration.
-- DQ-AM-D02 [Medium]    Identical combination of description + asset_group +
--            cap_date_from + org_amount within the same client.
--            Potential duplicate asset entries rather than genuine separate assets.
--            Flag for Parliament review — do not auto-exclude.
-- DQ-AM-D03 [Info]      Same asset_id present in both HoC and HoL extracts.
--            Expected to occur — separate physical assets. Surface for awareness
--            so Parliament is not surprised during consolidation design.
--
-- SCOPE
-- DQ-AM-S01 [Info]      Count of records by status and client.
--            Produces the migration candidate count (status = 'N') and archive
--            candidate count (status in 'C', 'T') split by fund.
-- DQ-AM-S02 [High]      parent_asset references an asset_id not present in
--            this extract. Orphaned child asset — parent may have been deleted
--            or terminated. Python cross-reference within the same house extract.
-- DQ-AM-S03 [Info]      Count of assets with grant_flag = 1 by client.
--            Grant-funded assets may have specific accounting treatment in the
--            target system — surface the population for Parliament's awareness.

-- REFERENTIAL INTEGRITY (Python — requires joining to other extracts)
-- DQ-AM-R01 [Critical]  asset_id appears in asset_trans extract but has no
--            matching record in this master extract (same house).
--            Orphaned transaction — no parent asset record. Blocking for migration.
--            Cannot migrate a transaction against an asset that doesn't exist.
-- DQ-AM-R02 [Critical]  asset_id appears in asset_depr extract but has no
--            matching record in this master extract (same house).
--            Orphaned depreciation book — configuration with no parent asset.
--            Blocking — depreciation rules cannot be migrated without the asset.
-- DQ-AM-R03 [High]      asset_id in asset_trans or asset_depr matches a record
--            in this extract where status != 'N' (transaction or book against
--            an inactive/closed/terminated asset).
--            Active financial activity against a non-active asset master record.
--            Requires Parliament to confirm whether these transactions are
--            historical tail (acceptable) or a live processing error (blocking).
-- DQ-AM-R04 [High]      parent_asset value does not match any asset_id in this
--            extract for the same client and house.
--            Child asset references a parent that either doesn't exist or has
--            been closed. Component asset cannot be migrated without its parent.
-- DQ-AM-R05 [Medium]    apar_id is populated but does not match any supplier_id
--            in the supplier master extract (same house).
--            Asset references a supplier that is not in the migration scope or
--            has been deleted. Not blocking for asset migration but breaks the
--            procurement link in the new system.
--
-- =============================================================================

SELECT
    client,           -- Fund/entity code. HoC: CA/CF/CM. HoL: LA. NOT the house identifier.
    asset_id,         -- Primary key. Unique per client. Join key to aatassetbook and aattrans.
    asset_group,      -- Asset category/group. Drives depreciation defaults and GL account mapping.
    description,      -- Full asset description. Primary human-readable identifier.
    short_info,       -- Short description (60 chars). May be blank — use description as fallback.
    status,           -- Asset status. N=Normal(active), P=Parked, C=Closed, T=Terminated.
    wf_state,         -- Workflow state. Clean = blank/N/T. In-flight = W/R/U/X — flag for resolution.
    cap_date_from,    -- Capitalisation date. Null for non-capitalised assets (valid per scope).
    cap_period_from,  -- Capitalisation GL period (YYYYPP format). Consistency check vs cap_date_from.
    date_from,        -- Ownership start date. Must be populated for all active assets.
    date_to,          -- Ownership end date. Should be null for active assets (status = 'N').
    apar_id,          -- Linked supplier ID. Optional — not all assets have a procurement link.
    parent_asset,     -- Parent asset_id for component/structured assets. Null if standalone.
    grant_flag,       -- 1 = grant-funded asset. 0 = standard. Relevant for accounting treatment.
    org_amount,       -- Original cost. Must be populated for capitalised active assets.
    org_amt_date,     -- Date of original cost. Should be consistent with cap_date_from.
    base_amount,      -- Depreciation base amount. May differ from org_amount for imported assets.
    std_amount,       -- Standard/benchmark valuation amount. Internal reference value.
    ins_amount,       -- Insurance valuation. May legitimately be null — advisory completeness check only.
    dim_1,            -- Analytical dimension 1. Segment mapping to be confirmed with Parliament.
    dim_2,            -- Analytical dimension 2.
    dim_3,            -- Analytical dimension 3.
    dim_4,            -- Analytical dimension 4.
    dim_5,            -- Analytical dimension 5.
    dim_6,            -- Analytical dimension 6.
    dim_7,            -- Analytical dimension 7.
    last_update,      -- Last modified timestamp. Used to identify stale or untouched records.
    user_id           -- Last updated by. Audit trail field.
FROM
    aatasset
ORDER BY
    client,
    asset_id
;