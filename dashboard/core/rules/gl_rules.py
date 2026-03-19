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
         'Ensures all active general ledger accounts have a meaningful description for reporting and audit transparency.',
         'Populate aglaccounts.description.', 'aglaccounts', None,
         'aglaccounts.description IS NULL WHERE status = "N"',
         lambda df: df['description'].isna()),

        ('GL_ACC_GRP_MISSING', 20, 'GL Accounts', 'Completeness', 'High',
         'Active account not assigned to a reporting group',
         'Verifies that every active account is mapped to a reporting group to ensure accurate financial consolidation.',
         'Populate aglaccounts.account_grp.', 'aglaccounts', None,
         'aglaccounts.account_grp IS NULL WHERE status = "N"',
         lambda df: df['account_grp'].isna()),

        ('GL_ACC_RESBAL_MISSING', 20, 'GL Accounts', 'Completeness', 'Critical',
         'Missing Balance Sheet/P&L classification',
         'Identifies accounts without a Balance Sheet or P&L classification, which is critical for year-end processing logic.',
         'Populate aglaccounts.res_bal (Must be R or B).', 'aglaccounts', None,
         'aglaccounts.res_bal IS NULL',
         lambda df: df['res_bal'].isna()),

        ('GL_ACC_RULE_MISSING', 20, 'GL Accounts', 'Completeness', 'High',
         'Active account missing its posting rule ID',
         'Checks for missing posting rules which define how the system handles automatic balancing and validation.',
         'Populate aglaccounts.account_rule.', 'aglaccounts', None,
         'aglaccounts.account_rule IS NULL',
         lambda df: df['account_rule'].isna()),

        ('GL_ACC_PERIOD_MISSING', 20, 'GL Accounts', 'Completeness', 'Medium',
         'Active account missing valid-from period',
         'Ensures that accounts have a defined start period to prevent posting into incorrect financial years.',
         'Populate aglaccounts.period_from.', 'aglaccounts', None,
         'aglaccounts.period_from IS NULL',
         lambda df: df['period_from'].isna()),

        ('GL_ACC_RESBAL_INVALID', 20, 'GL Accounts', 'Validity', 'Critical',
         'res_bal contains invalid code (must be R or B)',
         'Validates that the result/balance indicator contains only approved codes (R for Result, B for Balance).',
         'Correct aglaccounts.res_bal.', 'aglaccounts', None,
         'aglaccounts.res_bal NOT IN ("R", "B")',
         lambda df: (~df['res_bal'].isin(['R', 'B'])) & df['res_bal'].notna()),

        ('GL_ACC_TYPE_INVALID', 20, 'GL Accounts', 'Validity', 'High',
         'account_type not a valid GL/AP/AR code',
         'Ensures the account type matches Unit4 system standards (GL, AP, or AR) for correct sub-ledger integration.',
         'Correct aglaccounts.account_type.', 'aglaccounts', None,
         'aglaccounts.account_type NOT IN ("GL", "AP", "AR")',
         lambda df: (~df['account_type'].isin(['GL', 'AP', 'AR'])) & df['account_type'].notna()),

        ('GL_ACC_PERIOD_INV', 20, 'GL Accounts', 'Validity', 'Medium',
         'Valid-from period is after the valid-to period',
         'Identifies logical errors in the account validity range where the start date exceeds the end date.',
         'Correct aglaccounts.period_from/to.', 'aglaccounts', None,
         'aglaccounts.period_from > aglaccounts.period_to',
         lambda df: df['period_from'] > df['period_to']),

        ('GL_ACC_STALE_N', 20, 'GL Accounts', 'Validity', 'Low',
         'Account is active (status N) but its validity period has expired',
         'Flags accounts that should be closed (Status C) because their defined validity period has passed.',
         'Close account in aglaccounts (status C).', 'aglaccounts', None,
         'aglaccounts.status = "N" AND aglaccounts.period_to < TODAY',
         lambda df: (df['period_to'] < today) & (df['status'] == 'N')),

        ('GL_ACC_BFLAG_CON', 20, 'GL Accounts', 'Consistency', 'High',
         'Reconciliation account (bflag 7) is not flagged as AP or AR type',
         'Ensures that control/reconciliation accounts are correctly typed to allow sub-ledger postings.',
         'Verify aglaccounts.account_type aligns with bflag.', 'aglaccounts', None,
         'aglaccounts.bflag = 7 AND aglaccounts.account_type NOT IN ("AP", "AR")',
         lambda df: (df['bflag'] == 7) & (~df['account_type'].isin(['AP', 'AR']))),

        ('GL_ACC_DUP_CODE', 20, 'GL Accounts', 'Uniqueness', 'Critical',
         'Duplicate account code exists within the same House',
         'Critical check to prevent primary key violations and data ambiguity during the chart of accounts migration.',
         'Consolidate aglaccounts.account codes.', 'aglaccounts', None,
         'COUNT(*) OVER(PARTITION BY client, account) > 1',
         lambda df: df.duplicated(subset=['house', 'account'], keep=False)),

        ('GL_ACC_STALE_MOD', 20, 'GL Accounts', 'Timeliness', 'Low',
         'Stale account: Record has not been updated in over 3 years',
         'Identifies accounts that may no longer be relevant based on their lack of maintenance activity.',
         'Review for archival in aglaccounts.', 'aglaccounts', None,
         'aglaccounts.last_update < (TODAY - 3 years)',
         lambda df: df['last_update'] < (today - pd.Timedelta(days=3*365))),

        # ======================================================================
        # --- GL DIMENSION VALUES (agldimvalue) ---
        # ======================================================================
        ('GL_DIM_DESC_MISSING', 21, 'GL Dimensions', 'Completeness', 'High',
         'Active dimension value has no description',
         'Ensures all dimension values (Cost Centres, Projects, etc.) have descriptions for end-user selection.',
         'Populate agldimvalue.description.', 'agldimvalue', None,
         'agldimvalue.description IS NULL WHERE status = "N"',
         lambda df: df['description'].isna()),

        ('GL_DIM_PERIOD_MISSING', 21, 'GL Dimensions', 'Completeness', 'Medium',
         'Active dimension value missing valid-from period',
         'Verifies that dimension values have a defined start date to maintain temporal data integrity.',
         'Populate agldimvalue.period_from.', 'agldimvalue', None,
         'agldimvalue.period_from IS NULL',
         lambda df: df['period_from'].isna()),

        ('GL_DIM_PERIOD_INV', 21, 'GL Dimensions', 'Validity', 'Medium',
         'Dimension valid-from period is after the valid-to period',
         'Identifies illogical date ranges in the dimension master data.',
         'Correct agldimvalue.period_from/to.', 'agldimvalue', None,
         'agldimvalue.period_from > agldimvalue.period_to',
         lambda df: df['period_from'] > df['period_to']),

        ('GL_DIM_WF_STUCK', 21, 'GL Dimensions', 'Consistency', 'Medium',
         'Dimension value is stuck in a non-approved workflow state',
         "Detects records that haven't cleared the approval process, preventing them from being used in live postings.",
         'Approve or reject agldimvalue.wf_state.', 'agldimvalue', None,
         'agldimvalue.wf_state NOT IN ("", "T") AND wf_state IS NOT NULL',
         lambda df: (df['wf_state'].notna()) & (df['wf_state'] != '') & (df['wf_state'] != 'T')),

        ('GL_DIM_ORPHAN_REL', 21, 'GL Dimensions', 'Consistency', 'High',
         'Hierarchy link to a parent that is missing or inactive',
         'Ensures hierarchical relationships (e.g., Project to Department) point to valid, active parent records.',
         'Check agldimvalue.rel_value exists as an active agldimvalue.dim_value.', 'agldimvalue', 'agldimvalue',
         'agldimvalue.rel_value NOT IN (SELECT dim_value FROM agldimvalue WHERE status = "N")',
         lambda df, frames: df['rel_value'].notna() & (
             ~df[['house', 'attribute_id', 'rel_value']].apply(tuple, axis=1).isin(
                 frames.get('agldimvalue', pd.DataFrame())[frames.get('agldimvalue', pd.DataFrame())['status'] == 'N'][['house', 'attribute_id', 'dim_value']].apply(tuple, axis=1)
             )
         )),

        ('GL_DIM_DUP', 21, 'GL Dimensions', 'Uniqueness', 'Critical',
         'Duplicate dimension code within the same attribute and House',
         'Critical check to ensure uniqueness of Cost Centres and Projects within each House.',
         'Consolidate agldimvalue.dim_value codes.', 'agldimvalue', None,
         'COUNT(*) OVER(PARTITION BY client, attribute_id, dim_value) > 1',
         lambda df: df.duplicated(subset=['house', 'attribute_id', 'dim_value'], keep=False)),

        # ======================================================================
        # --- GL OPENING BALANCES (aglyearend) ---
        # ======================================================================
        ('GL_BAL_AMT_MISSING', 22, 'GL Balances', 'Completeness', 'Critical',
         'Opening balance record has no amount',
         'Ensures every ledger balance record has a numerical value to prevent "silent" data loss during migration.',
         'Check aglyearend.amount.', 'aglyearend', None,
         'aglyearend.amount IS NULL',
         lambda df: df['amount'].isna()),

        ('GL_BAL_FX_MISSING', 22, 'GL Balances', 'Completeness', 'High',
         'Foreign currency balance missing its transaction currency amount',
         'Verifies that for non-GBP balances, the original transaction currency amount is preserved for FX revaluation.',
         'Populate aglyearend.cur_amount.', 'aglyearend', None,
         'aglyearend.currency <> "GBP" AND aglyearend.cur_amount IS NULL',
         lambda df: (df['currency'] != 'GBP') & df['cur_amount'].isna()),

        ('GL_BAL_PL_NONZERO', 22, 'GL Balances', 'Consistency', 'High',
         'P&L account carries a non-zero balance at year end',
         'Validates that P&L accounts have been correctly cleared to Retained Earnings prior to migration.',
         'Review P&L transfer in aglyearend for accounts where aglaccounts.res_bal = "R".', 'aglyearend', 'aglaccounts',
         'aglyearend.amount <> 0 JOIN aglaccounts ON account WHERE aglaccounts.res_bal = "R"',
         lambda df, frames: (df['amount'].abs() > 0.01) & (
             df[['house', 'account']].apply(tuple, axis=1).isin(
                 frames.get('aglaccounts', pd.DataFrame())[frames.get('aglaccounts', pd.DataFrame())['res_bal'] == 'R'][['house', 'account']].apply(tuple, axis=1)
             )
         ) if 'aglaccounts' in frames else (df['amount'].abs() > 0.01)),

        ('GL_BAL_TOTAL_NET', 22, 'GL Balances', 'Consistency', 'Critical',
         'General Ledger is out of balance (Total Debits <> Credits)',
         'Ensures the fundamental accounting principle that Debits equal Credits is maintained for the trial balance migration.',
         'Investigate aglyearend.amount and dc_flag; total must net to zero per House.', 'aglyearend', None,
         'SUM(aglyearend.amount * aglyearend.dc_flag) GROUP BY client <> 0',
         lambda df: (df['amount'] * df['dc_flag'].fillna(1)).groupby(df['house']).transform('sum').abs() > 0.01),

        ('GL_BAL_ORPHAN_ACC', 22, 'GL Balances', 'Referential Integrity', 'Critical',
         'Balance refers to an account code that does not exist in master data',
         'Identifies balances mapped to non-existent accounts, which would cause the ledger migration to fail.',
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
         'Ensures transaction-level coding aligns with valid, active master data to prevent reporting orphans.',
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
