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
    ]
    return checks
