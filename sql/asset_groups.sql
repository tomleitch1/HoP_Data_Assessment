-- =============================================================================
-- asset_groups.sql
-- Houses of Parliament — Finance Systems Programme
-- Fixed Asset Group & Category Configuration Extract
-- Migration scope: Seq 13 (Asset Depreciation Rules & Methods — by asset
-- category)
-- Source tables: aatassetgroup, aatassetgrbook
-- =============================================================================
--
-- INSTANCE & CLIENT
-- Run this script separately against the HoC instance and the HoL instance.
-- HoC clients: CA (Common Administration), CF (Miscellaneous Fund),
-- CM (Members Fund). HoL client: LA.
-- Add house column in Python after load (df['house'] = 'HOC' / 'HOL').
-- No client filter applied — all clients extracted.
--
-- PURPOSE
-- This extract captures the group-level (category-level) depreciation
-- configuration from Unit4. It is the correct primary source for Seq 13
-- of the migration scope — "migrate all active depreciation methods, useful
-- lives, and residual values by asset category."
--
-- aatassetgroup holds the asset group master record — the category definition
-- itself, including its default depreciation parameters.
-- aatassetgrbook holds the depreciation book configuration at group level —
-- one row per (asset_group, depr_book_id), defining the method, rate, and
-- lifetime that apply to all assets in that group unless overridden at asset
-- level in aatassetbook.
--
-- RELATIONSHIP TO asset_depreciation.sql
-- asset_depreciation.sql extracts aatassetbook — the per-asset depreciation
-- configuration. Some of those asset-level values will be identical to the
-- group defaults (inherited); others will be deliberate overrides.
-- Python can compare the two extracts to identify:
--   (a) which asset groups are actually in use across the asset population
--   (b) which individual assets deviate from their group default — these
--       are the overrides the SI needs to know about when configuring the
--       target system
--   (c) asset groups that exist in configuration but have no assets assigned
--       to them — orphaned group definitions
--
-- RELATIONSHIP TO asset_master.sql
-- asset_group on aatasset is the foreign key to aatassetgroup. Every
-- asset_group value in asset_master should have a corresponding record
-- in this extract. Python validates this in both directions.
--
-- WHY THIS IS NEEDED IN ADDITION TO asset_depreciation.sql
-- The target system will be configured at category/group level first.
-- The SI needs to know: for each asset category, what is the standard
-- method, rate, and useful life? That question is answered by this extract,
-- not by asset_depreciation.sql. asset_depreciation.sql tells you what each
-- individual asset is doing; this extract tells you what the system is
-- configured to do by default for each category. Both are needed.
--
-- EXTRACTION APPROACH
-- No WHERE clause on either table. All statuses extracted.
-- Python filters to active groups (status = 'N') for migration scoping.
-- The two tables are joined in SQL here on (client, asset_group, depr_book_id)
-- because they have a direct parent-child relationship and there is no value
-- in extracting them separately — aatassetgrbook has no meaning without its
-- parent aatassetgroup record.
-- All further analysis and DQ logic in Python.
--
-- ASSUMPTIONS
-- A1. aatassetgroup is a small table — one row per asset group per client.
--     Volume is negligible regardless of house or number of clients.
-- A2. aatassetgrbook has one row per (client, asset_group, depr_book_id).
--     An asset group may have multiple depreciation books (e.g. financial
--     and tax). This is valid. Python should surface multi-book groups for
--     Parliament to confirm which books require migration.
-- A3. The depreciation parameters on aatassetgrbook represent the default
--     that applies to all assets in the group unless explicitly overridden
--     in aatassetbook. Where an asset in asset_depreciation.sql has values
--     that differ from the group default here, that is a deliberate override
--     and must be migrated as an asset-level exception in the target system.
-- A4. HoC and HoL may define different asset groups with different naming
--     conventions. This is expected — do not attempt to normalise group
--     names across houses. The consolidation mapping is a separate exercise
--     for the SI during target system configuration.
-- A5. depr_method, lifetime, depr_percent, and res_value on aatassetgrbook
--     are the same fields as on aatassetbook but represent group-level
--     defaults rather than asset-level actuals. The same validity rules apply.
-- A6. status on aatassetgroup and status on aatassetgrbook may differ —
--     a group may be active while a specific book within it is closed.
--     Both status fields are extracted and Python handles the combination.
-- A7. The same caveats on dc_flag, ZU grant treatment, and trans_type
--     convention from asset_balances.sql apply equally here when comparing
--     group configuration to individual asset behaviour. Those are Python-side
--     concerns — this extract simply surfaces the configured values.
-- A8. depr_start on aatassetgrbook defines when depreciation begins for
--     assets in this group (e.g. from capitalisation date, from period start).
--     This field has no equivalent in aatassetbook — it is a group-level
--     setting. The SI needs this to configure the correct depreciation start
--     rule in the target system.
--
-- =============================================================================
-- DATA QUALITY TESTS (all executed in Python against the CSV output)
-- =============================================================================
--
-- COMPLETENESS
-- DQ-AG-C01 [Critical]  asset_group is null or blank.
--            Primary key of aatassetgroup. Cannot exist without a group code.
-- DQ-AG-C02 [High]      description is null or blank for grp_status = 'N'.
--            Active asset groups must have a human-readable label for the
--            target system configuration and for Parliament's review.
-- DQ-AG-C03 [High]      depr_book_id is null or blank.
--            Every group record joined from aatassetgrbook must have a book.
-- DQ-AG-C04 [High]      depr_method is null or blank for grp_status = 'N'
--            and book_status = 'N'.
--            Active group with active book must have a method defined.
--            Without this, the SI cannot configure the target system.
-- DQ-AG-C05 [High]      lifetime is null or zero for grp_status = 'N',
--            book_status = 'N', and depr_method in ('LIN', 'SYD').
--            Straight line and sum of year digits require a useful life.
-- DQ-AG-C06 [High]      depr_percent is null or zero for grp_status = 'N',
--            book_status = 'N', and depr_method = 'BAL'.
--            Reducing balance method requires a rate at group level.
--
-- VALIDITY
-- DQ-AG-V01 [Critical]  depr_method not in ('LIN', 'BAL', 'EXP', 'SYD').
--            Invalid method code at group level. Any asset inheriting this
--            group default will also carry an invalid method. Blocking.
-- DQ-AG-V02 [Critical]  grp_status not in ('N', 'P', 'C', 'T').
--            Unexpected status on the group master record.
-- DQ-AG-V03 [Critical]  book_status not in ('N', 'P', 'C', 'T').
--            Unexpected status on the group book record.
-- DQ-AG-V04 [High]      depr_percent > 100.
--            Depreciation rate above 100% is not valid at group level.
-- DQ-AG-V05 [High]      lifetime <= 0 for method in ('LIN', 'SYD').
--            Zero or negative useful life at group level — all assets
--            inheriting this default will fail the same check.
-- DQ-AG-V06 [Medium]    res_value < 0.
--            Negative residual value is not valid.
--
-- CONSISTENCY
-- DQ-AG-K01 [High]      book_status = 'N' but grp_status != 'N'.
--            Active depreciation book on an inactive group. Assets cannot
--            be assigned to an inactive group — this configuration is
--            contradictory.
-- DQ-AG-K02 [Medium]    switch = true and depr_method != 'BAL' at group
--            level. Degressive-to-linear switch is only valid for reducing
--            balance. Inheriting assets will carry the same inconsistency.
-- DQ-AG-K03 [Medium]    res_value > 0 and depr_method = 'EXP'.
--            Expensed assets are not typically depreciated to a residual
--            value. Flag for Parliament to confirm intent.
--
-- DUPLICATES
-- DQ-AG-D01 [Critical]  Duplicate (client, asset_group, depr_book_id).
--            Violation of the composite primary key of aatassetgrbook.
-- DQ-AG-D02 [Medium]    Duplicate description within same client.
--            Two different asset groups with identical descriptions —
--            potential misconfiguration or naming collision.
--
-- SCOPE
-- DQ-AG-S01 [Info]      Count of active asset groups (grp_status = 'N')
--            by client. Baseline category population for SI configuration.
-- DQ-AG-S02 [Info]      Count of groups by depr_method and client.
--            Method distribution across the category population — useful
--            for target system configuration planning.
-- DQ-AG-S03 [Info]      Count of groups with multiple depr_book_id values
--            per client. Multi-book groups need all books confirmed for
--            migration by Parliament.
--
-- CROSS-EXTRACT TESTS (Python, joining asset_master and asset_depreciation)
-- DQ-AG-X01 [Critical]  asset_group in asset_master with no matching record
--            in this extract. An asset is assigned to a group that does not
--            exist in the group configuration table. Orphaned asset group
--            reference — blocking for migration.
-- DQ-AG-X02 [High]      asset_group in this extract with grp_status = 'N'
--            and no assets assigned to it in asset_master. Active group
--            with no assets — orphaned configuration. Flag for Parliament
--            to confirm whether the group should be retired.
-- DQ-AG-X03 [High]      For assets in asset_depreciation where depr_method
--            differs from the group default in this extract for the same
--            (client, asset_group, depr_book_id) — asset-level override
--            detected. Produce a list of overrides by group and method for
--            the SI. This is not an error but must be explicitly migrated
--            as an exception in the target system.
-- DQ-AG-X04 [Medium]    For assets in asset_depreciation where lifetime
--            differs from the group default in this extract for the same
--            (client, asset_group, depr_book_id). Useful life override
--            at asset level — same handling as DQ-AG-X03.
-- DQ-AG-X05 [Medium]    For assets in asset_depreciation where res_value
--            differs from the group default in this extract for the same
--            (client, asset_group, depr_book_id). Residual value override
--            at asset level.
--
-- =============================================================================

SELECT
    -- aatassetgroup fields (group master)
    g.client,               -- Fund/entity code. HoC: CA/CF/CM. HoL: LA.
    g.asset_group,          -- Asset group/category code. Primary key of aatassetgroup.
    g.description,          -- Group description. Human-readable category label for target system.
    g.status    AS grp_status, -- Group-level status. N=Normal, P=Parked, C=Closed, T=Terminated.
    g.depr_method,          -- Group default depreciation method. LIN/BAL/EXP/SYD.
    g.depr_percent,         -- Group default depreciation rate (%). Required for BAL method.
    g.lifetime,             -- Group default useful life in years. Required for LIN and SYD.
    g.res_value,            -- Group default residual value.
    g.res_val_flag,         -- Controls how residual value is applied in calculation.
    g.salvage_amount,       -- Group default salvage/scrap value.
    g.depr_start,           -- When depreciation begins for assets in this group.
                            -- e.g. from capitalisation date, period start. SI needs this.
    g.depr_limit,           -- Minimum depreciation threshold for this group.
    g.depr_max_perc,        -- Maximum annual depreciation as % of fixed value.
    g.frequency,            -- Group default depreciation posting frequency.
    g.switch,               -- True = degressive switches to linear. BAL method only.
    g.period_exact,         -- True = depreciation calculated on exact periods.
    g.nbv_rounding,         -- True = NBV rounding applied for this group.
    g.index_id,             -- Index table for revaluation. Populated = indexed asset class.
    g.index_code,           -- Index code for revaluation calculation.
    g.ins_table_id,         -- Insurance table reference for this group.
    g.insurance_mode,       -- Insurance mode for this group.
    g.dim_1,                -- Analytical dimension 1 default for this group.
    g.dim_2,                -- Analytical dimension 2.
    g.dim_3,                -- Analytical dimension 3.
    g.dim_4,                -- Analytical dimension 4.
    g.dim_5,                -- Analytical dimension 5.
    g.dim_6,                -- Analytical dimension 6.
    g.dim_7,                -- Analytical dimension 7.
    g.last_update AS grp_last_update, -- Group record last modified timestamp.
    g.user_id     AS grp_user_id,     -- Group record last updated by.

    -- aatassetgrbook fields (group depreciation book)
    gb.depr_book_id,        -- Depreciation book for this group. Multiple books per group valid.
    gb.status   AS book_status, -- Book-level status. N=Normal, P=Parked, C=Closed, T=Terminated.
    gb.depr_method  AS book_depr_method,    -- Book-level method override. May differ from group default.
    gb.depr_percent AS book_depr_percent,   -- Book-level rate override.
    gb.lifetime     AS book_lifetime,       -- Book-level useful life override.
    gb.res_value    AS book_res_value,      -- Book-level residual value override.
    gb.res_val_flag AS book_res_val_flag,   -- Book-level residual value flag.
    gb.salvage_amount AS book_salvage_amount, -- Book-level salvage amount override.
    gb.depr_start   AS book_depr_start,     -- Book-level depreciation start rule.
    gb.depr_limit   AS book_depr_limit,     -- Book-level minimum threshold override.
    gb.depr_max_perc AS book_depr_max_perc, -- Book-level maximum % override.
    gb.frequency    AS book_frequency,      -- Book-level frequency override.
    gb.switch       AS book_switch,         -- Book-level degressive switch flag.
    gb.period_exact AS book_period_exact,   -- Book-level exact period flag.
    gb.nbv_rounding AS book_nbv_rounding,   -- Book-level NBV rounding flag.
    gb.index_id     AS book_index_id,       -- Book-level index table reference.
    gb.index_code   AS book_index_code,     -- Book-level index code.
    gb.last_update  AS book_last_update,    -- Book record last modified timestamp.
    gb.user_id      AS book_user_id         -- Book record last updated by.

FROM
    aatassetgroup g
    LEFT JOIN aatassetgrbook gb
        ON  g.client      = gb.client
        AND g.asset_group = gb.asset_group

ORDER BY
    g.client,
    g.asset_group,
    gb.depr_book_id
;