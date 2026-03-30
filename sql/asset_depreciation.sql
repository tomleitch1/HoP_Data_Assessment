-- =============================================================================
-- asset_depreciation.sql
-- Houses of Parliament — Finance Systems Programme
-- Fixed Asset Depreciation Book Extract
-- Migration scope: Seq 13 (Asset Depreciation Rules & Methods)
-- Source table: aatassetbook
-- =============================================================================
--
-- INSTANCE & CLIENT
-- Run this script separately against the HoC instance and the HoL instance.
-- HoC clients: CA (Common Administration), CF (Miscellaneous Fund),
-- CM (Members Fund). HoL client: LA.
-- 'client' identifies the fund within a house, not the house itself.
-- Add house column in Python after load (df['house'] = 'HOC' / 'HOL').
-- No client filter applied — all clients extracted.
--
-- EXTRACTION APPROACH
-- No WHERE clause. All statuses and all depreciation books extracted.
-- One row per asset per depreciation book — an asset may have multiple books
-- (e.g. a financial reporting book and a tax book). This is valid in Unit4.
-- Python handles scoping, filtering, and all DQ logic.
--
-- RELATIONSHIP TO OTHER EXTRACTS
-- This extract joins to asset_master on (client, asset_id).
-- Every asset_id here should have a corresponding record in asset_master.
-- Every active asset in asset_master (status = 'N') should have at least one
-- depreciation book record here. Both directions are tested in Python.
-- The (client, asset_id, depr_book_id) combination is the composite key and
-- the join key to asset_transactions.
--
-- MIGRATION SCOPE LOGIC (applied in Python, not here)
-- In scope: depreciation books where the parent asset is in migration scope
-- (asset_master status = 'N'). All books for that asset are extracted and
-- Parliament must confirm whether all books require migration or only the
-- primary financial reporting book.
-- Out of scope: books where parent asset is status C or T (archive candidates).
-- Parked assets (status = 'P'): same position as asset_master — confirm with
-- Parliament.
--
-- ASSUMPTIONS
-- A1. Multiple depreciation books per asset are valid. Common patterns include
--     a primary financial book plus a tax or insurance book. Python should flag
--     multi-book assets so Parliament can confirm which books to migrate.
-- A2. depr_method values are: LIN (Straight Line), BAL (Reducing Balance),
--     EXP (Expense), SYD (Sum of Year Digits). Any value outside this list is
--     invalid and blocking for migration.
-- A3. For LIN and SYD methods, lifetime must be > 0. For BAL method,
--     depr_percent must be > 0. For EXP method, neither may be mandatory —
--     confirm with Parliament.
-- A4. depr_period holds the last period in which depreciation was calculated
--     (YYYYPP format). A value significantly behind the current period on an
--     active book indicates depreciation has not been run — this is a processing
--     gap, not a data entry error, but must be resolved before cutover.
-- A5. cap_date_from on aatassetbook should match cap_date_from on aatasset for
--     the same asset_id. Discrepancies indicate the book was set up independently
--     of the master record and need Parliament to adjudicate which date is correct.
-- A6. HoC and HoL may use different depreciation book naming conventions
--     (e.g. HoC uses 'FINBOOK', HoL uses 'MAIN'). This is expected and not a
--     DQ issue. Do not attempt to normalise book names across houses.
-- A7. res_value and salvage_amount may both be zero for fully depreciating assets.
--     This is valid. A non-zero res_value on a fully depreciated asset
--     (NBV = 0) is a consistency issue — flagged in cross-extract tests.
-- A8. The switch flag (degressive to linear switch) is relevant only for BAL
--     method assets. Its presence on a LIN or EXP asset is unexpected and
--     should be flagged.
-- A9. nbv_rounding behaviour may differ between Unit4 and the target system.
--     The population of assets with nbv_rounding = true should be surfaced so
--     the SI can confirm equivalent behaviour in the new system.
-- A10. index_id and index_code being populated indicates an indexed or revalued
--      asset class. Revaluation treatment must be confirmed with Parliament and
--      the SI before migration — target system behaviour may differ.
--
-- =============================================================================
-- DATA QUALITY TESTS (all executed in Python against the CSV output)
-- =============================================================================
--
-- COMPLETENESS
-- DQ-AD-C01 [Critical]  asset_id is null or blank.
--            No depreciation book can exist without an asset reference.
-- DQ-AD-C02 [Critical]  depr_book_id is null or blank.
--            Composite primary key component. Blocking for migration.
-- DQ-AD-C03 [High]      depr_method is null or blank for status = 'N'.
--            Active depreciation books must have a method defined.
--            Without this, depreciation cannot be calculated in the target system.
-- DQ-AD-C04 [High]      lifetime is null or zero where depr_method in ('LIN','SYD')
--            and status = 'N'. Straight line and sum of year digits methods
--            require a defined useful life to calculate the annual charge.
-- DQ-AD-C05 [High]      depr_percent is null or zero where depr_method = 'BAL'
--            and status = 'N'. Reducing balance method requires a rate.
-- DQ-AD-C06 [Medium]    cap_date_from is null for status = 'N' and cap_flag = 1.
--            If the book is flagged as capitalised, a capitalisation date is
--            expected.
-- DQ-AD-C07 [Medium]    depr_period is null for status = 'N'.
--            Should be populated once depreciation has been run at least once.
--            Null on a long-standing active book suggests it has never been run.
--
-- VALIDITY
-- DQ-AD-V01 [Critical]  depr_method not in ('LIN', 'BAL', 'EXP', 'SYD').
--            Value outside the documented valuelist. Blocking for migration —
--            target system must have a mapped equivalent.
-- DQ-AD-V02 [Critical]  status not in ('N', 'P', 'C', 'T').
--            Unexpected status code — data integrity issue.
-- DQ-AD-V03 [High]      depr_percent > 100.
--            A depreciation rate above 100% is not mathematically valid.
-- DQ-AD-V04 [High]      lifetime <= 0 for any active depreciating asset
--            (status = 'N', method not 'EXP').
--            Zero or negative useful life cannot produce a valid depreciation
--            schedule.
-- DQ-AD-V05 [High]      date_from is after date_to where both are populated.
--            Ownership period on the book is inverted.
-- DQ-AD-V06 [Medium]    cap_date_from is before date_from.
--            Book cannot be capitalised before ownership started on that book.
-- DQ-AD-V07 [Medium]    depr_percent is negative.
--            Negative depreciation rate is not valid.
-- DQ-AD-V08 [Medium]    last_update is in the future (beyond today's date).
--            System clock or data entry error.
--
-- CONSISTENCY
-- DQ-AD-K01 [High]      date_to is populated but status = 'N'.
--            Book is marked active but ownership has ended. Contradictory state —
--            same pattern as asset_master DQ-AM-K01, applied at book level.
-- DQ-AD-K02 [High]      depr_period is more than 3 periods behind the current
--            GL period for status = 'N'. Depreciation has not been run recently
--            on an active book. Must be investigated and resolved before cutover
--            to avoid a gap in accumulated depreciation.
-- DQ-AD-K03 [Medium]    switch = true but depr_method != 'BAL'.
--            The degressive-to-linear switch is only applicable to reducing
--            balance assets. Its presence on other methods is unexpected.
-- DQ-AD-K04 [Medium]    index_id is populated but depr_method = 'EXP'.
--            Indexed revaluation is not typically applied to expensed assets.
--            Flag for Parliament to confirm intent.
-- DQ-AD-K05 [Medium]    res_value > org_amount on aatasset for same asset_id.
--            Residual value exceeds original cost — not economically valid.
--            Requires join to asset_master; see cross-extract tests.
--
-- DUPLICATES
-- DQ-AD-D01 [Critical]  Duplicate (client, asset_id, depr_book_id).
--            Violation of the composite primary key. Blocking for migration.
-- DQ-AD-D02 [Info]      Count of asset_id values with more than one
--            depr_book_id within the same client.
--            Multi-book assets are valid but Parliament must confirm which
--            books require migration. Produce a list for their review.
--
-- SCOPE
-- DQ-AD-S01 [Info]      Count of records by status and client.
--            Baseline population split — active books vs archived books.
-- DQ-AD-S02 [Info]      Count of assets with nbv_rounding = true by client.
--            Surface this population for the SI to confirm equivalent rounding
--            behaviour exists in the target system.
-- DQ-AD-S03 [Info]      Count of assets with index_id populated by client.
--            Indexed/revalued assets may require specific configuration in the
--            target system. Surface the population early.
--
-- CROSS-EXTRACT TESTS (Python, joining asset_master and asset_transactions)
-- DQ-AD-X01 [Critical]  asset_id in this extract with no matching record in
--            asset_master (orphaned depreciation book).
-- DQ-AD-X02 [High]      asset_id in asset_master with status = 'N' and no
--            corresponding record in this extract (active asset with no
--            depreciation book — cannot calculate depreciation in target system).
-- DQ-AD-X03 [High]      cap_date_from on this extract does not match
--            cap_date_from on asset_master for the same asset_id.
--            Discrepancy between master and book capitalisation dates.
-- DQ-AD-X04 [Medium]    res_value on this extract exceeds org_amount on
--            asset_master for the same asset_id.
--            Residual value greater than original cost is not valid.
-- DQ-AD-X05 [High]      (client, asset_id, depr_book_id) in this extract with
--            no corresponding transactions in asset_transactions.
--            Active depreciation book with no transaction history — asset may
--            never have been capitalised or depreciation never posted.
--
-- =============================================================================

SELECT
    client,           -- Fund/entity code. HoC: CA/CF/CM. HoL: LA. Not the house identifier.
    asset_id,         -- Foreign key to aatasset. Part of composite primary key.
    depr_book_id,     -- Depreciation book identifier. Multiple books per asset are valid.
    status,           -- Book-level status. N=Normal, P=Parked, C=Closed, T=Terminated.
    depr_method,      -- Depreciation method. LIN=Straight Line, BAL=Reducing Balance,
                      -- EXP=Expense, SYD=Sum of Year Digits. Must map to target system method.
    depr_percent,     -- Depreciation rate (%). Required for BAL method. Must be > 0 and <= 100.
    lifetime,         -- Useful life in years. Required for LIN and SYD methods. Must be > 0.
    res_value,        -- Residual value at end of useful life. May be zero — valid for full depreciation.
    res_val_flag,     -- Controls how residual value is applied in the depreciation calculation.
    salvage_amount,   -- Salvage/scrap value. Related to residual value but used differently by method.
    cap_date_from,    -- Capitalisation date on this book. Should match aatasset.cap_date_from.
    cap_period_from,  -- Capitalisation GL period (YYYYPP). Consistency check vs cap_date_from.
    cap_flag,         -- 1 = asset is capitalised for this book. 0 = not capitalised. IFRS16 relevant.
    date_from,        -- Ownership start date on this book.
    date_to,          -- Ownership end date on this book. Should be null for active books.
    depr_period,      -- Last period depreciation was calculated (YYYYPP). Stale = processing gap.
    depr_limit,       -- Minimum depreciation threshold — amounts below this are not posted.
    depr_max_perc,    -- Maximum annual depreciation as a percentage of a fixed value.
    nbv_rounding,     -- True = NBV rounding applied. Surface population for SI confirmation.
    switch,           -- True = degressive method switches to linear at a point. BAL method only.
    period_exact,     -- True = depreciation calculated on exact periods rather than amounts.
    frequency,        -- Depreciation posting frequency (e.g. annual, monthly, quarterly).
    index_id,         -- Index table reference for indexed/revalued assets. Populated = revaluation in use.
    index_code,       -- Index code for revaluation calculation.
    repl_amount,      -- Replacement/reinstatement amount. Insurance or revaluation reference.
    dim_1,            -- Analytical dimension 1. Segment mapping to be confirmed with Parliament.
    dim_2,            -- Analytical dimension 2.
    dim_3,            -- Analytical dimension 3.
    dim_4,            -- Analytical dimension 4.
    dim_5,            -- Analytical dimension 5.
    dim_6,            -- Analytical dimension 6.
    dim_7,            -- Analytical dimension 7.
    last_update,      -- Last modified timestamp.
    user_id           -- Last updated by. Audit trail field.
FROM
    aatassetbook
ORDER BY
    client,
    asset_id,
    depr_book_id
;