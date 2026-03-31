import pandas as pd
from datetime import date

def get_gl_checks():
    """Returns a list of GL DQ check definitions."""
    today = pd.Timestamp(date.today())
    
    checks = [
        # ======================================================================
        # --- GL CHART OF ACCOUNTS (aglaccounts) ---
        # ======================================================================
        ('GL_ACC_DESC_MISSING', 20, 'GL Accounts', 'Completeness', 'High',
         'Active account has no description',
         'Flags active accounts with no description, making them unidentifiable in reports and audit trails.',
         'Populate aglaccounts.description.', 'aglaccounts', None,
         'aglaccounts.description IS NULL WHERE status = "N"',
         lambda df: df['description'].isna()),

        ('GL_ACC_GRP_MISSING', 20, 'GL Accounts', 'Completeness', 'High',
         'Active account not assigned to a reporting group',
         'Finds active accounts not assigned to a reporting group, which would exclude them from financial consolidation.',
         'Populate aglaccounts.account_grp.', 'aglaccounts', None,
         'aglaccounts.account_grp IS NULL WHERE status = "N"',
         lambda df: df['account_grp'].isna()),

        ('GL_ACC_RESBAL_MISSING', 20, 'GL Accounts', 'Completeness', 'Critical',
         'Missing Balance Sheet/P&L classification',
         'Catches accounts missing their Balance Sheet or P&L classification — without this, year-end processing logic cannot determine how to carry the balance forward.',
         'Populate aglaccounts.res_bal (Must be R or B).', 'aglaccounts', None,
         'aglaccounts.res_bal IS NULL',
         lambda df: df['res_bal'].isna()),

        ('GL_ACC_RULE_MISSING', 20, 'GL Accounts', 'Completeness', 'High',
         'Active account missing its posting rule ID',
         'Identifies active accounts with no posting rule, which controls how the system auto-balances entries; missing rules can cause posting failures.',
         'Populate aglaccounts.account_rule.', 'aglaccounts', None,
         'aglaccounts.account_rule IS NULL',
         lambda df: df['account_rule'].isna()),

        ('GL_ACC_PERIOD_MISSING', 20, 'GL Accounts', 'Completeness', 'Medium',
         'Active account missing valid-from period',
         'Flags accounts with no valid-from period, leaving the system unable to restrict postings to the correct financial year.',
         'Populate aglaccounts.period_from.', 'aglaccounts', None,
         'aglaccounts.period_from IS NULL',
         lambda df: df['period_from'].isna()),

        ('GL_ACC_RESBAL_INVALID', 20, 'GL Accounts', 'Validity', 'Critical',
         'res_bal contains invalid code (must be R or B)',
         'Catches accounts where the result/balance code is not R (Result) or B (Balance) — any other value is invalid and will cause year-end processing errors.',
         'Correct aglaccounts.res_bal.', 'aglaccounts', None,
         'aglaccounts.res_bal NOT IN ("R", "B")',
         lambda df: (~df['res_bal'].isin(['R', 'B'])) & df['res_bal'].notna()),

        ('GL_ACC_TYPE_INVALID', 20, 'GL Accounts', 'Validity', 'High',
         'account_type not a valid GL/AP/AR code',
         'Flags accounts where the type is not one of the three valid Unit4 codes (GL, AP, AR), which determines sub-ledger integration.',
         'Correct aglaccounts.account_type.', 'aglaccounts', None,
         'aglaccounts.account_type NOT IN ("GL", "AP", "AR")',
         lambda df: (~df['account_type'].isin(['GL', 'AP', 'AR'])) & df['account_type'].notna()),

        ('GL_ACC_PERIOD_INV', 20, 'GL Accounts', 'Timeliness', 'Medium',
         'Valid-from period is after the valid-to period',
         'Finds accounts where the valid-from date is later than the valid-to date — a logical impossibility that would prevent the account from ever being active.',
         'Correct aglaccounts.period_from/to.', 'aglaccounts', None,
         'aglaccounts.period_from > aglaccounts.period_to',
         lambda df: df['period_from'] > df['period_to']),

        ('GL_ACC_STALE_N', 20, 'GL Accounts', 'Timeliness', 'Low',
         'Account is active (status N) but its validity period has expired',
         'Identifies accounts still marked as active whose validity period has already expired — these should have been closed.',
         'Close account in aglaccounts (status C).', 'aglaccounts', None,
         'aglaccounts.status = "N" AND aglaccounts.period_to < TODAY',
         lambda df: (df['period_to'] < today) & (df['status'] == 'N')),

        ('GL_ACC_BFLAG_CON', 20, 'GL Accounts', 'Consistency', 'High',
         'Reconciliation account (bflag 7) is not flagged as AP or AR type',
         'Flags reconciliation accounts (bflag 7) that are not typed as AP or AR — without this, sub-ledger postings to control accounts will be rejected.',
         'Verify aglaccounts.account_type aligns with bflag.', 'aglaccounts', None,
         'aglaccounts.bflag = 7 AND aglaccounts.account_type NOT IN ("AP", "AR")',
         lambda df: (df['bflag'] == 7) & (~df['account_type'].isin(['AP', 'AR']))),

        ('GL_ACC_DUP_CODE', 20, 'GL Accounts', 'Uniqueness', 'Critical',
         'Duplicate account code exists within the same House',
         'Finds duplicate account codes within the same House — a primary key violation that would cause ambiguity and migration failures.',
         'Consolidate aglaccounts.account codes.', 'aglaccounts', None,
         'COUNT(*) OVER(PARTITION BY client, account) > 1',
         lambda df: df.duplicated(subset=['house', 'account'], keep=False)),

        ('GL_ACC_STALE_MOD', 20, 'GL Accounts', 'Timeliness', 'Low',
         'Stale account: Record has not been updated in over 3 years',
         'Surfaces accounts that have not been updated in over 3 years, suggesting they may be redundant and candidates for archival.',
         'Review for archival in aglaccounts.', 'aglaccounts', None,
         'aglaccounts.last_update < (TODAY - 3 years)',
         lambda df: df['last_update'] < (today - pd.Timedelta(days=3*365))),

        # ======================================================================
        # --- GL DIMENSION VALUES (agldimvalue) ---
        # ======================================================================
        ('GL_DIM_DESC_MISSING', 21, 'GL Dimensions', 'Completeness', 'High',
         'Active dimension value has no description',
         'Flags dimension values (Cost Centres, Projects, etc.) with no description, making them impossible for end-users to identify in lookups.',
         'Populate agldimvalue.description.', 'agldimvalue', None,
         'agldimvalue.description IS NULL WHERE status = "N"',
         lambda df: df['description'].isna()),

        ('GL_DIM_PERIOD_MISSING', 21, 'GL Dimensions', 'Completeness', 'Medium',
         'Active dimension value missing valid-from period',
         'Finds dimension values with no valid-from period, preventing the system from restricting usage to the correct time range.',
         'Populate agldimvalue.period_from.', 'agldimvalue', None,
         'agldimvalue.period_from IS NULL',
         lambda df: df['period_from'].isna()),

        ('GL_DIM_PERIOD_INV', 21, 'GL Dimensions', 'Timeliness', 'Medium',
         'Dimension valid-from period is after the valid-to period',
         'Identifies dimension values where the start date is after the end date — a logical error that means the value can never be valid.',
         'Correct agldimvalue.period_from/to.', 'agldimvalue', None,
         'agldimvalue.period_from > agldimvalue.period_to',
         lambda df: df['period_from'] > df['period_to']),

        ('GL_DIM_WF_STUCK', 21, 'GL Dimensions', 'Consistency', 'Medium',
         'Dimension value is stuck in a non-approved workflow state',
         'Finds dimension values stuck in an incomplete workflow state, meaning they have not been approved and cannot be used in live postings.',
         'Approve or reject agldimvalue.wf_state.', 'agldimvalue', None,
         'agldimvalue.wf_state NOT IN ("", "T") AND wf_state IS NOT NULL',
         lambda df: (df['wf_state'].notna()) & (df['wf_state'] != '') & (df['wf_state'] != 'T')),

        ('GL_DIM_ORPHAN_REL', 21, 'GL Dimensions', 'Consistency', 'High',
         'Hierarchy link to a parent that is missing or inactive',
         'Finds dimension values that reference a parent (rel_value) which either does not exist or is inactive in the same table — breaking the reporting hierarchy.',
         'Check agldimvalue.rel_value exists as an active agldimvalue.dim_value.', 'agldimvalue', 'agldimvalue',
         'agldimvalue.rel_value NOT IN (SELECT dim_value FROM agldimvalue WHERE status = "N")',
         lambda df, frames: df['rel_value'].notna() & (
             ~df[['house', 'attribute_id', 'rel_value']].apply(tuple, axis=1).isin(
                 frames.get('agldimvalue', pd.DataFrame())[frames.get('agldimvalue', pd.DataFrame())['status'] == 'N'][['house', 'attribute_id', 'dim_value']].apply(tuple, axis=1)
             )
         )),

        ('GL_DIM_DUP', 21, 'GL Dimensions', 'Uniqueness', 'Critical',
         'Duplicate dimension code within the same attribute and House',
         'Detects duplicate dimension codes within the same House and attribute type — a primary key violation that causes ambiguity in cost centre and project reporting.',
         'Consolidate agldimvalue.dim_value codes.', 'agldimvalue', None,
         'COUNT(*) OVER(PARTITION BY client, attribute_id, dim_value) > 1',
         lambda df: df.duplicated(subset=['house', 'attribute_id', 'dim_value'], keep=False)),

        # ======================================================================
        # --- GL OPENING BALANCES (aglyearend) ---
        # ======================================================================
        ('GL_BAL_AMT_MISSING', 22, 'GL Balances', 'Completeness', 'Critical',
         'Opening balance record has no amount',
         'Finds opening balance records with no monetary value — a blank amount means the balance is effectively lost in migration.',
         'Check aglyearend.amount.', 'aglyearend', None,
         'aglyearend.amount IS NULL',
         lambda df: df['amount'].isna()),

        ('GL_BAL_FX_MISSING', 22, 'GL Balances', 'Completeness', 'High',
         'Foreign currency balance missing its transaction currency amount',
         'Flags non-GBP balances that are missing the original transaction currency amount, which is needed for FX revaluation in the new system.',
         'Populate aglyearend.cur_amount.', 'aglyearend', None,
         'aglyearend.currency <> "GBP" AND aglyearend.cur_amount IS NULL',
         lambda df: (df['currency'] != 'GBP') & df['cur_amount'].isna()),

        ('GL_BAL_PL_NONZERO', 22, 'GL Balances', 'Consistency', 'High',
         'P&L account carries a non-zero balance at year end',
         'Checks that P&L accounts carry a zero balance at year end — non-zero values indicate the profit/loss transfer to Retained Earnings has not been completed.',
         'Review P&L transfer in aglyearend for accounts where aglaccounts.res_bal = "R".', 'aglyearend', 'aglaccounts',
         'aglyearend.amount <> 0 JOIN aglaccounts ON account WHERE aglaccounts.res_bal = "R"',
         lambda df, frames: (df['amount'].abs() > 0.01) & (
             df[['house', 'account']].apply(tuple, axis=1).isin(
                 frames.get('aglaccounts', pd.DataFrame())[frames.get('aglaccounts', pd.DataFrame())['res_bal'] == 'R'][['house', 'account']].apply(tuple, axis=1)
             )
         ) if 'aglaccounts' in frames else (df['amount'].abs() > 0.01)),

        ('GL_BAL_TOTAL_NET', 22, 'GL Balances', 'Consistency', 'Critical',
         'General Ledger is out of balance (Total Debits <> Credits)',
         'Verifies that total debits equal total credits for each House — if they do not net to zero, the trial balance is out of balance and migration will fail.',
         'Investigate aglyearend.amount and dc_flag; total must net to zero per House.', 'aglyearend', None,
         'SUM(aglyearend.amount * aglyearend.dc_flag) GROUP BY client <> 0',
         lambda df: (df['amount'] * df['dc_flag'].fillna(1)).groupby(df['house']).transform('sum').abs() > 0.01),

        ('GL_BAL_ORPHAN_ACC', 22, 'GL Balances', 'Referential Integrity', 'Critical',
         'Balance refers to an account code that does not exist in master data',
         'Finds balance records pointing to account codes that do not exist in the chart of accounts — these balances have nowhere to post to and would block migration.',
         'Check aglyearend.account against aglaccounts.account.', 'aglyearend', 'aglaccounts',
         'aglyearend.account NOT IN (SELECT account FROM aglaccounts)',
         lambda df, frames: ~df[['house', 'account']].apply(tuple, axis=1).isin(
             frames.get('aglaccounts', pd.DataFrame())[['house', 'account']].apply(tuple, axis=1)
         ) if 'aglaccounts' in frames else pd.Series([False]*len(df))),

        # ======================================================================
        # --- GL TRANSACTIONS (agltransact) ---
        # ======================================================================
        ('GL_TRA_ORPHAN_DIM1', 23, 'GL Transactions', 'Referential Integrity', 'High',
         'Transaction coded to a dimension value that does not exist or is inactive',
         'Finds transactions coded to a Cost Centre dimension value that does not exist or is inactive in master data — the coding is invalid and would create orphaned reporting entries.',
         'Check agltransact.dim_1 against agldimvalue.dim_value.', 'agltransact', 'agldimvalue',
         'agltransact.dim_1 NOT IN (SELECT dim_value FROM agldimvalue WHERE status = "N")',
         lambda df, frames: ~df[['house', 'dim_1']].apply(tuple, axis=1).isin(
             frames.get('agldimvalue', pd.DataFrame())[
                 (frames.get('agldimvalue', pd.DataFrame())['status'] == 'N') &
                 (frames.get('agldimvalue', pd.DataFrame())['attribute_id'] == 'COSTC')
             ][['house', 'dim_value']].apply(tuple, axis=1)
         ) if 'agldimvalue' in frames else pd.Series([False]*len(df))),

        # ======================================================================
        # --- GL JOURNALS (agltransact) ---
        # Seq 20 — Current Year Journals extract.
        # Source table: agltransact (same as GL Transactions above).
        # DQ tests sourced from sql/gl_journals.sql.
        # update_flag is the confirmed debit/credit indicator (1=Debit, 2=Credit).
        # dc_flag convention is unconfirmed — not used in balance logic here.
        # ======================================================================

        # --- COMPLETENESS ---

        ('DQ-GJ-C01', 23, 'GL Journals', 'Completeness', 'Critical',
         'Journal line has no voucher number',
         'Finds journal lines with a null voucher_no — every GL transaction must belong to a voucher for balance checking and source traceability.',
         'Investigate agltransact source data; voucher_no must be populated for all Seq 20 rows.',
         'gl_journals', None,
         'agltransact.voucher_no IS NULL',
         lambda df: df['voucher_no'].isna()),

        ('DQ-GJ-C02', 23, 'GL Journals', 'Completeness', 'Critical',
         'Journal line has no account code',
         'Identifies journal lines with no account — a line with no account cannot be posted to the GL in the target system and will block migration.',
         'Populate agltransact.account.',
         'gl_journals', None,
         'agltransact.account IS NULL OR agltransact.account = ""',
         lambda df: df['account'].isna() | (df['account'].astype(str).str.strip() == '')),

        ('DQ-GJ-C03', 23, 'GL Journals', 'Completeness', 'Critical',
         'Journal line has no amount',
         'Flags journal lines with a null amount — a line with no value cannot contribute to balance derivation or be included in migration.',
         'Populate agltransact.amount.',
         'gl_journals', None,
         'agltransact.amount IS NULL',
         lambda df: df['amount'].isna()),

        ('DQ-GJ-C04', 23, 'GL Journals', 'Completeness', 'High',
         'Journal line has no transaction date',
         'Finds lines with no trans_date — all journal lines must have an economic date for period allocation and audit trail purposes.',
         'Populate agltransact.trans_date.',
         'gl_journals', None,
         'agltransact.trans_date IS NULL',
         lambda df: pd.to_datetime(df['trans_date'], errors='coerce').isna()),

        ('DQ-GJ-C05', 23, 'GL Journals', 'Completeness', 'High',
         'Journal line has no voucher entry date',
         'Flags lines with no voucher_date — the entry date is mandatory for audit trail completeness.',
         'Populate agltransact.voucher_date.',
         'gl_journals', None,
         'agltransact.voucher_date IS NULL',
         lambda df: pd.to_datetime(df['voucher_date'], errors='coerce').isna()),

        ('DQ-GJ-C06', 23, 'GL Journals', 'Completeness', 'High',
         'Journal line has no voucher type',
         'Identifies lines with no voucher_type — required to classify journals and determine which types represent manual vs system entries.',
         'Populate agltransact.voucher_type.',
         'gl_journals', None,
         'agltransact.voucher_type IS NULL OR agltransact.voucher_type = ""',
         lambda df: df['voucher_type'].isna() | (df['voucher_type'].astype(str).str.strip() == '')),

        ('DQ-GJ-C07', 23, 'GL Journals', 'Completeness', 'Medium',
         'Manual journal line (JRNL type) has no description',
         'Finds JRNL-type lines with no description — manual journals without a description cannot be understood or audited; scoped to JRNL to avoid false positives on system-generated entries.',
         'Populate agltransact.description for JRNL voucher types.',
         'gl_journals', None,
         'agltransact.description IS NULL AND agltransact.voucher_type = "JRNL"',
         lambda df: (df['voucher_type'] == 'JRNL') & (df['description'].isna() | (df['description'].astype(str).str.strip() == ''))),

        ('DQ-GJ-C08', 23, 'GL Journals', 'Completeness', 'Medium',
         'Journal line has no user ID',
         'Flags lines with no user_id — every posting must carry an operator signature for audit trail and access migration planning.',
         'Populate agltransact.user_id.',
         'gl_journals', None,
         'agltransact.user_id IS NULL OR agltransact.user_id = ""',
         lambda df: df['user_id'].isna() | (df['user_id'].astype(str).str.strip() == '')),

        # --- VALIDITY ---

        ('DQ-GJ-V01', 23, 'GL Journals', 'Validity', 'Critical',
         'update_flag contains an invalid debit/credit code',
         'Catches lines where update_flag is not 1 (Debit) or 2 (Credit) — any other value is outside the documented valuelist and the posting direction cannot be determined, blocking balance checks.',
         'Correct agltransact.update_flag (must be 1 or 2).',
         'gl_journals', None,
         'agltransact.update_flag NOT IN (1, 2)',
         lambda df: (~df['update_flag'].isin([1, 2])) & df['update_flag'].notna()),

        ('DQ-GJ-V02', 23, 'GL Journals', 'Validity', 'High',
         'Journal trans_date is in the future',
         'Finds lines where trans_date is later than today — indicates a data entry error or a pre-posted journal that has not yet been processed.',
         'Review agltransact.trans_date; future dates are unexpected in a current-year extract.',
         'gl_journals', None,
         'agltransact.trans_date > TODAY',
         lambda df: pd.to_datetime(df['trans_date'], errors='coerce') > today),

        ('DQ-GJ-V03', 23, 'GL Journals', 'Validity', 'High',
         'Journal voucher_date is in the future',
         'Flags lines where the entry date is later than today — same concern as DQ-GJ-V02 at the voucher entry date level.',
         'Review agltransact.voucher_date.',
         'gl_journals', None,
         'agltransact.voucher_date > TODAY',
         lambda df: pd.to_datetime(df['voucher_date'], errors='coerce') > today),

        ('DQ-GJ-V04', 23, 'GL Journals', 'Validity', 'High',
         'trans_date and voucher_date differ by more than one GL period (~60 days)',
         'Identifies lines where the economic date and entry date are more than 60 days apart — greater differences indicate a posting alignment issue beyond normal period-end cutoff timing.',
         'Investigate agltransact.trans_date vs voucher_date; confirm with Parliament the tolerance threshold.',
         'gl_journals', None,
         'ABS(agltransact.trans_date - agltransact.voucher_date) > 60 days',
         lambda df: (
             pd.to_datetime(df['trans_date'], errors='coerce').notna() &
             pd.to_datetime(df['voucher_date'], errors='coerce').notna() &
             ((pd.to_datetime(df['voucher_date'], errors='coerce') -
               pd.to_datetime(df['trans_date'], errors='coerce')).dt.days.abs() > 60)
         )),

        ('DQ-GJ-V05', 23, 'GL Journals', 'Validity', 'Medium',
         'Journal line has no currency code',
         'Finds lines with no currency — required to determine whether FX handling applies in the target system.',
         'Populate agltransact.currency.',
         'gl_journals', None,
         'agltransact.currency IS NULL OR agltransact.currency = ""',
         lambda df: df['currency'].isna() | (df['currency'].astype(str).str.strip() == '')),

        ('DQ-GJ-V06', 23, 'GL Journals', 'Validity', 'Medium',
         'Non-GBP journal line is missing its transaction currency amount',
         'Flags non-GBP lines where cur_amount is null — FX revaluation in the target system requires both the base currency and the transaction currency amounts.',
         'Populate agltransact.cur_amount for all non-GBP lines.',
         'gl_journals', None,
         'agltransact.currency <> "GBP" AND agltransact.cur_amount IS NULL',
         lambda df: (df['currency'] != 'GBP') & df['cur_amount'].isna() & df['currency'].notna()),

        ('DQ-GJ-V07', 23, 'GL Journals', 'Validity', 'Medium',
         'Period is outside the expected fiscal year range (202601 – 202615)',
         'Finds lines with a period code outside the valid range for FY2026 — indicates a miscoded period or system configuration issue.',
         'Confirm valid period range with Parliament; correct agltransact.period.',
         'gl_journals', None,
         'agltransact.period < 202601 OR agltransact.period > 202615',
         lambda df: df['period'].notna() & (
             (pd.to_numeric(df['period'], errors='coerce') < 202601) |
             (pd.to_numeric(df['period'], errors='coerce') > 202615)
         )),

        ('DQ-GJ-V08', 23, 'GL Journals', 'Validity', 'Low',
         'Sub-ledger reference (apar_id) on a non-control account line',
         'Flags lines where apar_id is populated but the account is not typed AP or AR in aglaccounts — a sub-ledger reference on a non-control account is unexpected.',
         'Confirm with Parliament; review agltransact.apar_id and the corresponding aglaccounts.account_type.',
         'gl_journals', 'aglaccounts',
         'agltransact.apar_id IS NOT NULL AND aglaccounts.account_type NOT IN ("AP", "AR")',
         lambda df, frames: (
             df['apar_id'].notna() &
             ~df[['house', 'account']].apply(tuple, axis=1).isin(
                 frames.get('aglaccounts', pd.DataFrame())[
                     frames.get('aglaccounts', pd.DataFrame())['account_type'].isin(['AP', 'AR'])
                 ][['house', 'account']].apply(tuple, axis=1)
             )
         ) if 'aglaccounts' in frames else pd.Series([False]*len(df))),

        # --- CONSISTENCY ---

        ('DQ-GJ-K01', 23, 'GL Journals', 'Consistency', 'Critical',
         'Voucher does not balance — debits do not equal credits',
         'The most critical journals check. Groups lines by (house, voucher_no), sums signed amounts using update_flag (1=Debit +, 2=Credit −), and flags every row belonging to a voucher where abs(net) > 0.01. A non-zero net violates double-entry and will be rejected by the target system.',
         'Produce a list of unbalanced vouchers with net difference and user_id; correct in source before migration.',
         'gl_journals', None,
         'SUM(amount * SIGN(update_flag)) GROUP BY house, voucher_no <> 0',
         lambda df: (
             df['voucher_no'].notna() &
             df[['house', 'voucher_no']].apply(tuple, axis=1).isin(
                 df.assign(
                     _signed=lambda x: x['amount'].fillna(0) *
                                       x['update_flag'].map({1: 1, 2: -1}).fillna(0)
                 ).groupby(['house', 'voucher_no'])['_signed'].sum()
                  .pipe(lambda s: s[s.abs() > 0.01])
                  .reset_index()[['house', 'voucher_no']]
                  .apply(tuple, axis=1)
             )
         )),

        ('DQ-GJ-K02', 23, 'GL Journals', 'Consistency', 'High',
         'trans_date falls in a different period to the period field',
         'Finds lines where the economic date and the posted period are inconsistent — the month derived from trans_date does not match the period field, indicating a period-end posting that was dated incorrectly.',
         'Correct agltransact.period or agltransact.trans_date to ensure they agree.',
         'gl_journals', None,
         'YEAR(trans_date)*100 + MONTH(trans_date) <> period',
         lambda df: (
             pd.to_datetime(df['trans_date'], errors='coerce').notna() &
             df['period'].notna() &
             (
                 pd.to_datetime(df['trans_date'], errors='coerce').dt.year * 100 +
                 pd.to_datetime(df['trans_date'], errors='coerce').dt.month !=
                 pd.to_numeric(df['period'], errors='coerce')
             )
         )),

        ('DQ-GJ-K03', 23, 'GL Journals', 'Consistency', 'High',
         'apar_id and apar_type are not both present or both absent',
         'Flags lines where one of the sub-ledger reference fields is populated and the other is null — apar_id and apar_type must always appear together or not at all.',
         'Populate the missing field in agltransact, or clear both if the sub-ledger reference is not required.',
         'gl_journals', None,
         '(apar_id IS NOT NULL AND apar_type IS NULL) OR (apar_type IS NOT NULL AND apar_id IS NULL)',
         lambda df: (
             (df['apar_id'].notna() & df['apar_type'].isna()) |
             (df['apar_type'].notna() & df['apar_id'].isna())
         )),

        ('DQ-GJ-K04', 23, 'GL Journals', 'Consistency', 'Medium',
         'Voucher contains lines posted to different periods',
         'Flags every row in a voucher where at least two lines carry different period values — cross-period vouchers are unusual and may indicate a posting error, though some accrual reversals legitimately span periods.',
         'Review with Parliament; confirm whether cross-period vouchers are intentional.',
         'gl_journals', None,
         'COUNT(DISTINCT period) OVER(PARTITION BY house, voucher_no) > 1',
         lambda df: (
             df['voucher_no'].notna() &
             df[['house', 'voucher_no']].apply(tuple, axis=1).isin(
                 df[df['period'].notna()]
                 .groupby(['house', 'voucher_no'])['period'].nunique()
                 .pipe(lambda s: s[s > 1])
                 .reset_index()[['house', 'voucher_no']]
                 .apply(tuple, axis=1)
             )
         )),

        ('DQ-GJ-K05', 23, 'GL Journals', 'Consistency', 'Medium',
         'tax_code and tax_system are not both present or both absent',
         'Finds lines where one tax field is populated and the other is null — tax_code and tax_system must pair together on every line.',
         'Populate the missing tax field in agltransact, or clear both if tax does not apply.',
         'gl_journals', None,
         '(tax_code IS NOT NULL AND tax_system IS NULL) OR (tax_system IS NOT NULL AND tax_code IS NULL)',
         lambda df: (
             (df['tax_code'].notna() & df['tax_system'].isna()) |
             (df['tax_system'].notna() & df['tax_code'].isna())
         )),

        # --- DUPLICATES ---

        ('DQ-GJ-D01', 23, 'GL Journals', 'Uniqueness', 'Critical',
         'Duplicate composite primary key (client, voucher_no, sequence_no)',
         'Detects rows sharing the same client, voucher_no, and sequence_no — a composite primary key violation that indicates a structural data integrity issue in the source system.',
         'Identify and remove duplicate rows in agltransact before migration.',
         'gl_journals', None,
         'COUNT(*) OVER(PARTITION BY client, voucher_no, sequence_no) > 1',
         lambda df: df.duplicated(subset=['client', 'voucher_no', 'sequence_no'], keep=False)),

        ('DQ-GJ-D02', 23, 'GL Journals', 'Uniqueness', 'Medium',
         'Potential duplicate posting — same client, voucher, account, amount, and date',
         'Flags lines sharing identical client, voucher_no, account, amount, and trans_date where the voucher type is not a known reversal type — a potential duplicate posting of the same journal line.',
         'Flag for Parliament review; do not auto-exclude as some may be legitimate.',
         'gl_journals', None,
         'COUNT(*) OVER(PARTITION BY client, voucher_no, account, amount, trans_date) > 1 WHERE voucher_type NOT IN ("REVERSAL")',
         lambda df: (
             ~df['voucher_type'].isin(['REVERSAL']) &
             df.duplicated(subset=['client', 'voucher_no', 'account', 'amount', 'trans_date'], keep=False)
         )),

        # --- SCOPE / INFO ---

        ('DQ-GJ-S02', 23, 'GL Journals', 'Completeness', 'Low',
         'Journal line is in a year-end adjustment period (13, 14, or 15)',
         'Flags lines posted to periods 13, 14, or 15 — year-end adjustment entries that Parliament must confirm are in migration scope or should remain in Unit4 post-cutover.',
         'Confirm with Parliament whether period 13/14/15 journals are in Seq 20 migration scope.',
         'gl_journals', None,
         'period IN (YYYYPP where PP IN (13, 14, 15))',
         lambda df: (
             df['period'].notna() &
             pd.to_numeric(df['period'], errors='coerce').astype(str).str[-2:].isin(['13', '14', '15'])
         )),

        ('DQ-GJ-S04', 23, 'GL Journals', 'Completeness', 'Low',
         'Non-GBP journal line — FX population for target system planning',
         'Surfaces all non-GBP journal lines so Parliament can confirm the FX currency population and ensure the target system is configured to handle each currency.',
         'Review with Parliament; confirm target system FX configuration covers all currencies present.',
         'gl_journals', None,
         'agltransact.currency <> "GBP" AND agltransact.currency IS NOT NULL',
         lambda df: df['currency'].notna() & (df['currency'] != 'GBP')),

        ('DQ-GJ-S05', 23, 'GL Journals', 'Completeness', 'Low',
         'Journal line carries a sub-ledger reference (apar_id populated)',
         'Flags all lines with an apar_id — identifies the volume of sub-ledger postings passing through the GL for reconciliation reference planning.',
         'Review with Parliament; confirm sub-ledger feeder postings are expected and in migration scope.',
         'gl_journals', None,
         'agltransact.apar_id IS NOT NULL',
         lambda df: df['apar_id'].notna()),

        # --- CROSS-EXTRACT ---

        ('DQ-GJ-X01', 23, 'GL Journals', 'Referential Integrity', 'Critical',
         'Journal account code does not exist in the chart of accounts',
         'Finds journal lines referencing an account that has no matching record in aglaccounts for the same House — the journal cannot be posted in the target system and will block migration.',
         'Verify agltransact.account against aglaccounts.account; create missing account records or correct the journal coding.',
         'gl_journals', 'aglaccounts',
         'agltransact.account NOT IN (SELECT account FROM aglaccounts)',
         lambda df, frames: ~df[['house', 'account']].apply(tuple, axis=1).isin(
             frames.get('aglaccounts', pd.DataFrame())[['house', 'account']].apply(tuple, axis=1)
         ) if 'aglaccounts' in frames else pd.Series([False]*len(df))),

        ('DQ-GJ-X02', 23, 'GL Journals', 'Referential Integrity', 'High',
         'Journal posts to a closed or inactive account',
         'Identifies journal lines where the account exists in aglaccounts but its status is not N (active) — the account has been deactivated but postings are still being made to it.',
         'Recode agltransact lines to an active account, or reactivate the account in aglaccounts if the deactivation was in error.',
         'gl_journals', 'aglaccounts',
         'agltransact.account IN (SELECT account FROM aglaccounts WHERE status != "N")',
         lambda df, frames: df[['house', 'account']].apply(tuple, axis=1).isin(
             frames.get('aglaccounts', pd.DataFrame())[
                 frames.get('aglaccounts', pd.DataFrame())['status'] != 'N'
             ][['house', 'account']].apply(tuple, axis=1)
         ) if 'aglaccounts' in frames else pd.Series([False]*len(df))),

        ('DQ-GJ-X03', 23, 'GL Journals', 'Referential Integrity', 'High',
         'Journal dim_1 value does not exist as an active dimension in master data',
         'Extends GL_TRA_ORPHAN_DIM1 to the journals dataset — finds journal lines coded to a dim_1 (Cost Centre) value that does not exist or is inactive in agldimvalue.',
         'Check agltransact.dim_1 against agldimvalue.dim_value where status = "N" and attribute_id = "COSTC".',
         'gl_journals', 'agldimvalue',
         'agltransact.dim_1 NOT IN (SELECT dim_value FROM agldimvalue WHERE status = "N" AND attribute_id = "COSTC")',
         lambda df, frames: (
             df['dim_1'].notna() &
             ~df[['house', 'dim_1']].apply(tuple, axis=1).isin(
                 frames.get('agldimvalue', pd.DataFrame())[
                     (frames.get('agldimvalue', pd.DataFrame())['status'] == 'N') &
                     (frames.get('agldimvalue', pd.DataFrame())['attribute_id'] == 'COSTC')
                 ][['house', 'dim_value']].apply(tuple, axis=1)
             )
         ) if 'agldimvalue' in frames else pd.Series([False]*len(df))),
    ]
    return checks
