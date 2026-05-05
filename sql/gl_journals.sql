-- =============================================================================
-- gl_journals.sql
-- Houses of Parliament — Finance Systems Programme
-- General Ledger Current Year Journals Extract
-- Migration scope: Seq 20 (Current Year Journals)
-- Source table: agltransact
-- =============================================================================
--
-- HOW TO RUN
-- Run against Agresso_HoC (server mdata837)  → save as gl_journals_HOC.csv
-- Run against agresso_HoL (server mdata837)  → save as gl_journals_HOL.csv
-- House is assigned by Python from the filename suffix, not the client column.
--
-- CLIENT CODES (internal fund codes within each database, NOT house identifiers)
-- Agresso_HoC clients: CA (Common Administration), CF (Miscellaneous Fund), CM (Members Fund)
-- agresso_HoL client:  LA
--
-- RELATIONSHIP TO gl_transact_dimensions.csv
-- A separate lean extract (SELECT DISTINCT client, dim_1...dim_7) already
-- exists in data/gl_transact_dimensions.csv. That extract supports dimension
-- referential integrity checks only — it is not replaced by this script.
-- This script exists alongside it for balance integrity, completeness,
-- validity, and scope checks that require row-level transaction detail.
--
-- EXTRACTION APPROACH
-- Unlike other extracts in this assessment, a WHERE clause is applied here.
-- Two filters are intentional and documented as assumptions:
--   (a) fiscal_year filter — Seq 20 scope is current FY only. Prior year
--       journals are out of scope for migration and would inflate volume
--       significantly without adding DQ value for cutover purposes.
--   (b) status filter — blank status only (normal posted transactions).
--       System-generated entries (P, T, B, D) are not manually mastered
--       journals and are not in scope for Seq 20 migration.
-- All other logic — voucher balance checks, period scoping, voucher type
-- classification — is handled in Python.
--
-- VOLUME NOTE
-- agltransact is the primary GL posting table and will be large. The two
-- filters above are the primary volume control mechanism. If volume remains
-- a concern after filtering, a secondary filter on voucher_type can be
-- applied in Python to isolate manually entered journals from system-posted
-- entries — do not add this to the SQL without Parliament confirmation of
-- which voucher_type codes represent manual journals.
--
-- DC_FLAG VS UPDATE_FLAG
-- Two debit/credit fields exist on agltransact:
--   dc_flag:     described as "Debet/Credit flag" — no valuelist documented.
--   update_flag: described as "Debit/Credit indicator" — 1=Debit, 2=Credit.
-- update_flag has a confirmed valuelist; dc_flag does not. Both are extracted.
-- The balance integrity logic in Python must use the confirmed field.
-- Which field Unit4 actually uses to drive posting sign must be confirmed
-- with Rod or Dan before any balance derivation is written. This is a hard
-- dependency — do not write the Python balance check until confirmed.
--
-- TRANS_DATE VS VOUCHER_DATE
-- Both date fields are extracted. In Unit4 practice:
--   voucher_date: the date the journal was entered into the system.
--   trans_date:   the economic/posting date the journal relates to.
-- These may differ at period end. Differences of more than one period are
-- unexpected and flagged as a DQ issue. Parliament must confirm which date
-- is used for period allocation — assumption is trans_date drives the period.
--
-- MIGRATION SCOPE LOGIC (applied in Python, not here)
-- Seq 20 scope: all current FY journals mastered in GL from both Houses.
-- Cutover timing impacts this significantly:
--   Mid-year go-live: only journals up to the cutover period migrate;
--   remaining periods stay in Unit4. THIS IS WHAT IS BEING DONE. THEY WILL NOT GO FOR AN APRIL 1st GO LIVE
-- Period 13/14/15 adjustment journals may remain in Unit4 regardless of
-- cutover timing — confirm with Parliament before finalising scope.
-- Python must produce a count and value split by period so Parliament can
-- confirm exactly which periods are in scope.
--
-- ASSUMPTIONS
-- A1. fiscal_year filter value must be substituted before running.
--     Replace [CURRENT_FISCAL_YEAR] with the actual 4-digit year value
--     e.g. 2026 for FY 2025/26. Confirm the fiscal_year convention with
--     Parliament — Unit4 may store FY 2025/26 as 2025 or 2026 depending
--     on configuration.
-- A2. status = '' (blank) captures normal posted transactions only.
--     P (periodic), T (TT/IC trigger), B (year-end), D (difference) are
--     system-generated and excluded. If Parliament uses periodic accruals
--     (status P) as part of their monthly close and wants these assessed,
--     remove the status filter and handle classification in Python.
-- A3. update_flag is assumed to be the reliable debit/credit indicator
--     (1=Debit, 2=Credit per the data dictionary valuelist). dc_flag is
--     extracted for completeness but its convention is unconfirmed.
-- A4. A journal voucher balances when the sum of all lines for that
--     voucher_no nets to zero after applying the debit/credit sign.
--     This assumes double-entry is enforced at voucher level in Unit4.
--     Confirm with Parliament whether any single-sided posting types exist.
-- A5. apar_id and apar_type are populated on control account postings only
--     (AP and AR sub-ledger entries posting through to the GL). Their
--     presence on a non-control account line is unexpected.
-- A6. The GL dimension naming convention uses dim_1 through dim_7 with
--     underscore — consistent with all other module tables. The budget
--     table (aglbuddetail) uses dim1 through dim8 without underscore;
--     do not confuse the two when writing Python join logic.
-- A7. Journals posted to period 13, 14, or 15 are year-end adjustment
--     entries. These are extracted by this script if they fall within
--     [CURRENT_FISCAL_YEAR] but Parliament must confirm whether they
--     are in migration scope or remain in Unit4 post-cutover.
-- A8. ext_inv_ref is populated on journals that originate from a
--     sub-ledger (AP invoice, AR invoice) posted through to GL. Its
--     presence indicates a feeder system origin rather than a manually
--     entered journal — useful for classifying journal populations.
--
-- =============================================================================
-- DATA QUALITY TESTS (all executed in Python against the CSV output)
-- =============================================================================
--
-- COMPLETENESS
-- DQ-GJ-C01 [Critical]  voucher_no is null.
--            Every GL transaction must belong to a voucher. A null voucher_no
--            means the transaction cannot be grouped for balance checking or
--            traced back to its source.
-- DQ-GJ-C02 [Critical]  account is null or blank.
--            A journal line with no account cannot be posted to the GL in
--            the target system. Blocking for migration.
-- DQ-GJ-C03 [Critical]  amount is null.
--            A journal line with no amount has no financial value. Cannot
--            be included in balance derivation or migration.
-- DQ-GJ-C04 [High]      trans_date is null.
--            All journal lines must have an economic date for period
--            allocation and audit trail purposes.
-- DQ-GJ-C05 [High]      voucher_date is null.
--            Entry date must be present for audit trail completeness.
-- DQ-GJ-C06 [High]      voucher_type is null or blank.
--            Required to classify journals by type and determine which
--            voucher types Parliament uses for manual vs system journals.
-- DQ-GJ-C07 [Medium]    description is null or blank.
--            Manual journals without a description cannot be understood
--            or audited. System-generated entries may legitimately have
--            no description — Python should split this check by
--            voucher_type to avoid false positives.
-- DQ-GJ-C08 [Medium]    user_id is null or blank.
--            Every posting must have an operator signature for audit trail.
--            Missing user_id indicates either a system posting gap or a
--            data integrity issue.
--
-- VALIDITY
-- DQ-GJ-V01 [Critical]  update_flag not in (1, 2).
--            Value outside the documented valuelist (1=Debit, 2=Credit).
--            Cannot determine posting direction — blocking for balance checks.
-- DQ-GJ-V02 [High]      trans_date is in the future (beyond today's date).
--            Future-dated journal lines indicate a data entry error or a
--            pre-posted journal that has not yet been processed.
-- DQ-GJ-V03 [High]      voucher_date is in the future.
--            Same concern as DQ-GJ-V02 at the entry date level.
-- DQ-GJ-V04 [High]      trans_date and voucher_date differ by more than
--            one GL period. Expected tolerance is within-period cutoff
--            timing. Greater differences indicate a posting alignment issue.
-- DQ-GJ-V05 [Medium]    currency is null or blank.
--            Required to determine whether FX handling applies in the
--            target system.
-- DQ-GJ-V06 [Medium]    currency != 'GBP' and cur_amount is null.
--            Non-GBP journal line missing its transaction currency amount.
--            FX revaluation in the target system requires both amounts.
-- DQ-GJ-V07 [Medium]    period is outside the expected range for the
--            current fiscal year (e.g. period < 202601 or > 202615).
--            Indicates a miscoded period or a system configuration issue.
--            Confirm the valid period range with Parliament.
-- DQ-GJ-V08 [Advisory]  apar_id is populated on a line where the account
--            is not a control account (account_type != 'AP' and != 'AR'
--            in aglaccounts). Sub-ledger reference on a non-control account
--            is unexpected. Requires join to aglaccounts.
--
-- CONSISTENCY
-- DQ-GJ-K01 [Critical]  Voucher does not balance — sum of signed amounts
--            per voucher_no does not net to zero.
--            The most important journals DQ check. A voucher that does not
--            balance violates double-entry and will be rejected by the
--            target system. Produce a list of unbalanced vouchers with the
--            net difference and the posting user for Parliament to correct.
--            Python logic: group by (house, voucher_no), sum
--            (amount * sign derived from update_flag), flag where
--            abs(sum) > 0.01 to allow for rounding.
-- DQ-GJ-K02 [High]      trans_date falls in a different period to the
--            period field value. The economic date and the posted period
--            are inconsistent — indicates a period-end posting that was
--            dated incorrectly.
-- DQ-GJ-K03 [High]      apar_id is populated but apar_type is null, or
--            apar_type is populated but apar_id is null. The sub-ledger
--            reference fields must both be present or both be absent.
-- DQ-GJ-K04 [Medium]    Same voucher_no contains lines in different periods.
--            A journal that spans multiple periods is unusual and may
--            indicate a posting error. Flag for Parliament to review —
--            not an automatic failure as some accrual reversals legitimately
--            span periods.
-- DQ-GJ-K05 [Medium]    tax_code is populated but tax_system is null, or
--            vice versa. Tax code and tax system must both be present or
--            both absent on a line.
--
-- DUPLICATES
-- DQ-GJ-D01 [Critical]  Duplicate (client, voucher_no, sequence_no).
--            Composite primary key violation. Indicates a structural data
--            integrity issue in the source system.
-- DQ-GJ-D02 [Medium]    Duplicate (client, voucher_no, account, amount,
--            trans_date) excluding known reversal voucher types.
--            Potential duplicate posting of the same journal line. Flag
--            for Parliament review — do not auto-exclude.
--
-- SCOPE
-- DQ-GJ-S01 [Info]      Count of vouchers and lines by period and
--            voucher_type and client.
--            Baseline journal population split — understand volume and
--            composition by period before migration scope is confirmed.
-- DQ-GJ-S02 [Info]      Count and value of journals in periods 13, 14, 15
--            by client. Year-end adjustment journals — Parliament must
--            confirm whether these are in migration scope.
-- DQ-GJ-S03 [Info]      Count of vouchers by user_id and voucher_type.
--            Identifies the most active posting users — useful for
--            access migration planning (Seq 8/9).
-- DQ-GJ-S04 [Info]      Count and value of non-GBP journal lines by
--            currency and client. FX journal population for target
--            system configuration planning.
-- DQ-GJ-S05 [Info]      Count of lines where apar_id is populated by
--            apar_type (AP vs AR). Volume of sub-ledger postings passing
--            through GL — reconciliation reference population.
--
-- CROSS-EXTRACT TESTS (Python, joining aglaccounts and agldimvalue)
-- DQ-GJ-X01 [Critical]  account on a journal line does not exist in
--            aglaccounts for the same house. Orphaned account reference —
--            the journal cannot be posted to the target system.
-- DQ-GJ-X02 [High]      account on a journal line exists in aglaccounts
--            but status != 'N' (posting to a closed or inactive account).
--            The account has been deactivated but journals are still being
--            posted to it.
-- DQ-GJ-X03 [High]      dim_1 value on a journal line does not exist as
--            an active value in agldimvalue for the same house.
--            Already covered by GL_TRA_ORPHAN_DIM1 in gl_rules.py —
--            extend equivalent checks to dim_2 through dim_7 using the
--            gl_transact_dimensions.csv extract.
-- DQ-GJ-X04 [High]      Sum of journal amounts by account for the current
--            FY does not reconcile to the corresponding aglyearend balance
--            for the same account and house. Current year activity does
--            not tie to the closing balance position.
--            Note: this test is only valid at April 1 go-live where the
--            full year has closed. For mid-year cutover a partial year
--            reconciliation approach is needed.
--
-- =============================================================================

SELECT
    client,           -- Fund/entity code. HoC: CA/CF/CM. HoL: LA.
    voucher_no,       -- Voucher/journal number. Groups all lines of a single journal entry.
                      -- Core field for balance integrity check — sum lines per voucher_no.
    sequence_no,      -- Sequence number within a voucher. Part of composite primary key.
    account,          -- GL account code. Join key to aglaccounts for validity checks.
    fiscal_year,      -- Financial year. Filtered to current FY only by WHERE clause.
    period,           -- GL posting period (YYYYPP). Used for period scoping and consistency
                      -- checks against trans_date.
    trans_date,       -- Economic/posting date. Drives period allocation. Check vs voucher_date.
    voucher_date,     -- Entry date. Audit trail field. Should be close to trans_date.
    voucher_type,     -- Journal/transaction type. Used to classify manual vs system journals.
    amount,           -- Amount in local currency (GBP). Core value for balance checks.
    cur_amount,       -- Amount in transaction currency. Required for non-GBP lines.
    currency,         -- Transaction currency. Expected GBP for most Parliament journals.
    dc_flag,          -- Debet/Credit flag. Convention unconfirmed — extract for reference.
                      -- Do not use in balance logic until convention confirmed with Parliament.
    update_flag,      -- Debit/Credit indicator. 1=Debit, 2=Credit per documented valuelist.
                      -- Use this field for balance integrity checks in Python.
    status,           -- Transaction status. Filtered to blank (normal) by WHERE clause.
                      -- Retained in SELECT to confirm filter is working as expected.
    apar_id,          -- Sub-ledger reference (supplier or customer ID). Control account lines only.
    apar_type,        -- Ledger type. R=Customer (AR), P=Supplier (AP). Pair with apar_id.
    tax_code,         -- Tax code applied to this line. Must pair with tax_system.
    tax_system,       -- Tax system reference. Must pair with tax_code.
    description,      -- Journal line description. Free text — audit trail and manual journal review.
    ext_inv_ref,      -- External invoice reference. Populated on sub-ledger feeder postings.
    dim_1,            -- Analytical dimension 1. Join key to agldimvalue for validity checks.
    dim_2,            -- Analytical dimension 2.
    dim_3,            -- Analytical dimension 3.
    dim_4,            -- Analytical dimension 4.
    dim_5,            -- Analytical dimension 5.
    dim_6,            -- Analytical dimension 6.
    dim_7,            -- Analytical dimension 7.
    last_update,      -- Last modified timestamp.
    user_id           -- Posted by. Audit trail and access migration planning.
FROM
    agltransact
WHERE
    fiscal_year = [CURRENT_FISCAL_YEAR]  -- Seq 20 scope: current FY only.
                                              -- Replace with actual year e.g. 2026.
                                              -- Confirm FY convention with Parliament
                                              -- before running.
    AND status = ''                           -- Normal posted transactions only.
                                              -- Excludes P (periodic), T (trigger),
                                              -- B (year-end), D (difference).
                                              -- Remove if Parliament confirms periodic
                                              -- accruals (P) should be assessed.
ORDER BY
    client,
    fiscal_year,
    period,
    voucher_no,
    sequence_no
;