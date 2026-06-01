import pandas as pd


def get_gl_checks():
    return [

        # ---------------------------------------------------------------
        # DIMENSION VALUES — agldimvalue
        # Population: all rows for the house (SQL already filters to status = 'N').
        # period_from / period_to are YYYYMM integers (e.g. 201202), NOT Excel serial dates.
        # Engine converts them to numeric; lambdas use pd.to_numeric() for safety.
        # wf_state is not used in Parliament's Agresso — GL_DIM_WF_STUCK not implemented.
        # rel_value is blank for root nodes; populated for hierarchy children.
        # ---------------------------------------------------------------

        ('GL_DIM_DESC_MISSING',
         21, 'Dimension Values', 'Completeness', 'Medium',
         'Active dimension value has no description',
         'Every active dimension value must have a description. '
         'Finance staff use the description to identify the value when coding transactions and reviewing reports. '
         'The new system displays descriptions in all dimension selection screens — a blank label cannot be mapped during migration sign-off or identified by users after go-live.',
         'Add a description to each affected dimension value in the legacy system before migration.',
         'agldimvalue', None,
         "WHERE status = 'N' AND (description IS NULL OR TRIM(description) = '')",
         lambda df: df['description'].isna() | (df['description'].astype(str).str.strip() == '')),

        ('GL_DIM_PERIOD_MISSING',
         21, 'Dimension Values', 'Completeness', 'Low',
         'Active dimension value has no valid-from period',
         'Every active dimension value should have a period_from value recording when it became valid. '
         'This supports audit trails and validity checking in the new system. '
         'Values without a valid-from period cannot be validated against fiscal calendar periods during migration.',
         'Populate the period_from field for each affected dimension value.',
         'agldimvalue', None,
         'WHERE status = \'N\' AND period_from IS NULL',
         lambda df: pd.to_numeric(df['period_from'], errors='coerce').isna()),

        ('GL_DIM_PERIOD_INV',
         21, 'Dimension Values', 'Validity', 'Medium',
         'Dimension value valid-from period is after its valid-to period',
         'The period_from value must be less than or equal to period_to. '
         'An inverted validity range means the value has no valid period and will be treated as permanently out of date in the new system. '
         'Any transaction coded to a value with an inverted range may fail posting validation at cutover.',
         'Correct the period_from and period_to values so the valid-from period is not later than the valid-to period.',
         'agldimvalue', None,
         'WHERE status = \'N\' AND period_from > period_to',
         lambda df: (
             pd.to_numeric(df['period_from'], errors='coerce').notna() &
             pd.to_numeric(df['period_to'],   errors='coerce').notna() &
             (pd.to_numeric(df['period_from'], errors='coerce') >
              pd.to_numeric(df['period_to'],   errors='coerce'))
         )),

        ('GL_DIM_ORPHAN_REL',
         21, 'Dimension Values', 'Consistency', 'High',
         'Active dimension value references a parent that does not exist',
         'Where a dimension value has a hierarchy parent (rel_value populated), that parent must exist as an active value within the same dimension attribute. '
         'An orphaned reference means the value sits at a broken branch in the dimension tree. '
         'Financial reports that aggregate by hierarchy will produce incorrect totals if parent codes are missing at cutover.',
         'Reinstate the missing parent as an active dimension value, reassign the child to a valid parent, or clear rel_value if the value should be a root node.',
         'agldimvalue', None,
         "WHERE status = 'N' AND rel_value IS NOT NULL AND rel_value NOT IN (SELECT dim_value FROM agldimvalue d2 WHERE d2.attribute_id = d.attribute_id AND d2.client = d.client AND d2.status = 'N')",
         lambda df: (
             lambda valid: (
                 df['rel_value'].notna() &
                 ~(df['attribute_id'].astype(str) + '||' + df['client'].astype(str) + '||' + df['rel_value'].astype(str))
                 .isin(valid)
             )
         )(set(
             (df['attribute_id'].astype(str) + '||' + df['client'].astype(str) + '||' + df['dim_value'].astype(str)).tolist()
         ))),

        ('GL_DIM_SELF_REF',
         21, 'Dimension Values', 'Consistency', 'High',
         'Dimension value is its own parent',
         'A dimension value must not reference itself as its hierarchy parent. '
         'Self-referential nodes create an infinite loop in any hierarchy traversal and cannot be imported into the new system. '
         'Reporting tools that walk the dimension tree will hang or error if a node points back to itself.',
         'Clear the rel_value field for the affected dimension value, or reassign it to a valid parent.',
         'agldimvalue', None,
         "WHERE status = 'N' AND rel_value = dim_value",
         lambda df: (
             df['rel_value'].notna() &
             (df['rel_value'].astype(str).str.strip() != '') &
             (df['rel_value'].astype(str) == df['dim_value'].astype(str))
         )),

        ('GL_DIM_DUP',
         21, 'Dimension Values', 'Uniqueness', 'High',
         'Duplicate dimension value code within the same attribute and client',
         'Each dimension value code must be unique within a given attribute type and client. '
         'Duplicate codes cannot both be loaded into the new system — only one can exist per (attribute, client, code) combination. '
         'Duplicate dimension values will cause the data load to fail or create ambiguous references in transaction coding.',
         'Investigate each duplicate pair. Merge or delete the redundant value after confirming no live transactions depend on it.',
         'agldimvalue', None,
         "WHERE (client, attribute_id, dim_value) appears more than once",
         lambda df: df.duplicated(subset=['client', 'attribute_id', 'dim_value'], keep=False)),

        # ---------------------------------------------------------------
        # DIMENSION CONFIGURATION — gl_dimconfig (source: agldimension joined to agldimvalue counts)
        # Population: GL_DIM_ATTR_GL_EMPTY → GL-mapped rows only (dim_position 0-7, filtered in engine)
        #             GL_DIM_ATTR_DESC_MISSING → all rows for the house
        # One row per (client, attribute_id) — counts of active/closed values per attribute type.
        # No 'status' column — SQL already filters agldimension to status = 'N'.
        # ---------------------------------------------------------------

        ('GL_DIM_ATTR_GL_EMPTY',
         21, 'Dimension Attributes', 'Completeness', 'High',
         'GL-mapped dimension attribute has no active values',
         'Every dimension attribute mapped to a GL journal line position (dim_1 through dim_7) must have at least one active value. '
         'If a GL dimension has no active values, journal lines cannot reference it and postings will either fail or leave the dimension blank. '
         'A dimension with no active values at cutover cannot be loaded into the new system and will block any transaction that references it.',
         'Review the dimension attribute and either activate existing closed values, create new active values, '
         'or remove the attribute from the GL journal line mapping if it is no longer required.',
         'gl_dimconfig', None,
         "WHERE dim_position IN ('0','1','2','3','4','5','6','7') AND active = 0",
         lambda df: pd.to_numeric(df['active'], errors='coerce').fillna(0) == 0),

        ('GL_DIM_ATTR_DESC_MISSING',
         21, 'Dimension Attributes', 'Completeness', 'Low',
         'Dimension attribute has no description',
         'Every dimension attribute must have a description. '
         'Finance staff rely on the description to identify the attribute when coding transactions and reviewing reports. '
         'The new system displays descriptions in all dimension selection screens. '
         'An attribute with no description will appear as a blank label and cannot be mapped during migration sign-off.',
         'Add a meaningful description to each affected attribute in agldimension in the legacy system before migration.',
         'gl_dimconfig', None,
         "WHERE description IS NULL OR TRIM(description) = ''",
         lambda df: df['description'].isna() | (df['description'].astype(str).str.strip() == '')),

        # ---------------------------------------------------------------
        # OPENING BALANCES — aglyearend (source: aglperiodic)
        # Population: all rows for the house — no status filter
        # Confirmed schema: amount is signed (dc_flag always 0), currency always GBP,
        # only dim_1 populated, trans_date is placeholder value 1 (not a real date),
        # apar_id always blank. Scope.GL_BALANCES = 22.
        # ---------------------------------------------------------------

        ('GL_BAL_AMT_MISSING',
         22, 'GL Opening Balances', 'Completeness', 'High',
         'Balance record has no amount',
         'Every row in the period balance table must have an amount populated. '
         'A record with no amount cannot be included in any balance or reconciliation calculation. '
         'Blank amounts at cutover will mean the opening balance in the new system is incomplete and the GL will fail to balance.',
         'Investigate the posting that created this record. Correct the amount in the legacy system '
         'or exclude the record from migration if it is invalid.',
         'aglyearend', None,
         'WHERE amount IS NULL',
         lambda df: df['amount'].isna()),

        ('GL_BAL_ORPHAN_ACC',
         22, 'GL Opening Balances', 'Consistency', 'High',
         'Balance record references an account not in the Chart of Accounts',
         'Every balance row must reference an account code that exists in aglaccounts. '
         'An orphaned balance cannot be loaded into the new system — the account must exist before balances can be posted against it. '
         'Orphaned balances will cause the opening balance load to fail at cutover.',
         'Either add the missing account to the Chart of Accounts, or investigate whether the balance '
         'was posted in error and should be reversed before migration.',
         'aglyearend', 'aglaccounts',
         "WHERE account NOT IN (SELECT account FROM aglaccounts WHERE client = p.client)",
         lambda df, frames: ~df['account'].isin(
             frames['aglaccounts'][frames['aglaccounts']['house'] == df['house'].iloc[0]]['account']
         )),

        ('GL_BAL_PL_NONZERO',
         22, 'GL Opening Balances', 'Validity', 'Medium',
         'P&L account carries a non-zero net balance after year-end close',
         'P&L accounts (res_bal = R) must carry a zero net balance after year-end close journals have been posted in periods 13, 14, or 15. '
         'A non-zero net balance at that point means the year-end close did not fully zero the account, '
         'or a post-close adjustment was made without a corresponding reversal. '
         'P&L balances carried into migration will create incorrect opening positions in the new system. '
         'This check is suppressed automatically until period 12 data is present in the extract. '
         'HOL closes within period 12; HOC posts additional adjustment journals in periods 13 and sometimes 14. '
         'For HOC the check may fire before period 13 is posted — those results should be treated as indicative until the full close is complete.',
         'Confirm that year-end close is complete for all periods (13, 14, and 15 as applicable). '
         'Investigate any P&L account with a residual balance and post a correcting journal or reclassify before cutover.',
         'aglyearend', 'aglaccounts',
         "WHERE res_bal = 'R' (joined from aglaccounts) AND period 13/14/15 exists AND SUM(amount) <> 0 GROUP BY account",
         lambda df, frames: (
             pd.Series(False, index=df.index)
             if not (pd.to_numeric(df['period'], errors='coerce') % 100 >= 12).any()
             else (
                 lambda full_mask: full_mask & ~df.loc[full_mask, 'account'].duplicated(keep='first').reindex(df.index, fill_value=False)
             )(
                 df['account'].isin(
                     frames['aglaccounts'][
                         (frames['aglaccounts']['house'] == df['house'].iloc[0]) &
                         (frames['aglaccounts']['res_bal'] == 'R')
                     ]['account']
                 ) &
                 df['account'].map(
                     df.groupby('account')['amount'].sum().round(2)
                 ).ne(0)
             )
         )),

        # ---------------------------------------------------------------
        # CHART OF ACCOUNTS — aglaccounts
        # Population: active accounts (status == 'N'), except GL_ACC_DUP_CODE (full)
        # period_from, period_to, last_update arrive as datetime64 after _parse_dates()
        # ---------------------------------------------------------------

        # COMPLETENESS
        ('GL_ACC_DESC_MISSING',
         20, 'Chart of Accounts', 'Completeness', 'Medium',
         'Active account has no description',
         'Every active account must have a description. '
         'Without it, finance staff cannot identify what the account is for during review or migration mapping. '
         'The new system will reject accounts with no description during data load.',
         'Add a description to the account in the legacy system before migration.',
         'aglaccounts', None,
         "WHERE status = 'N' AND (description IS NULL OR description = '')",
         lambda df: df['description'].isna() | (df['description'].astype(str).str.strip() == '')),

        ('GL_ACC_GRP_MISSING',
         20, 'Chart of Accounts', 'Completeness', 'Medium',
         'Active account not assigned to an account group',
         'Every active account must belong to a reporting group. '
         'The account group drives the financial statement hierarchy in the new system. '
         'Accounts without a group will be excluded from all reports after migration.',
         'Assign the account to the correct group in the legacy system.',
         'aglaccounts', None,
         "WHERE status = 'N' AND (account_grp IS NULL OR account_grp = '')",
         lambda df: df['account_grp'].isna() | (df['account_grp'].astype(str).str.strip() == '')),

        ('GL_ACC_RESBAL_MISSING',
         20, 'Chart of Accounts', 'Completeness', 'High',
         'Active account missing Balance Sheet / P&L classification (res_bal)',
         'Every active account must be classified as either a Balance Sheet account (B) or a P&L account (R). '
         'This field controls whether the account balance is carried forward at year end or reset to zero. '
         'A missing classification will cause incorrect opening balances in the new system.',
         'Set res_bal to R (P&L) or B (Balance Sheet) for each affected account.',
         'aglaccounts', None,
         "WHERE status = 'N' AND (res_bal IS NULL OR res_bal = '')",
         lambda df: df['res_bal'].isna() | (df['res_bal'].astype(str).str.strip() == '')),

        ('GL_ACC_RULE_MISSING',
         20, 'Chart of Accounts', 'Completeness', 'Medium',
         'Active account missing its posting rule',
         'Every active account must have a posting rule assigned. '
         'The posting rule controls which transaction types are permitted on the account. '
         'An account without a rule may be rejected during transaction posting in the new system.',
         'Assign the correct posting rule to the account.',
         'aglaccounts', None,
         "WHERE status = 'N' AND (account_rule IS NULL OR account_rule = '')",
         lambda df: df['account_rule'].isna() | (df['account_rule'].astype(str).str.strip().isin(['', 'nan']))),

        ('GL_ACC_PERIOD_MISSING',
         20, 'Chart of Accounts', 'Completeness', 'Low',
         'Active account missing valid-from date',
         'Every active account should have a period_from date recording when it became valid. '
         'This field supports audit trails and validity checking in the new system.',
         'Populate the valid-from date for the account.',
         'aglaccounts', None,
         "WHERE status = 'N' AND period_from IS NULL",
         lambda df: df['period_from'].isna()),

        # VALIDITY
        ('GL_ACC_RESBAL_INVALID',
         20, 'Chart of Accounts', 'Validity', 'High',
         'Account res_bal contains a value other than R or B',
         'The res_bal field must be either R (P&L) or B (Balance Sheet). '
         'Any other value is not a recognised classification and will fail validation on import to the new system. '
         'Affected accounts must be corrected before migration.',
         'Set res_bal to R or B. Remove or replace any non-standard codes.',
         'aglaccounts', None,
         "WHERE status = 'N' AND res_bal NOT IN ('R', 'B')",
         lambda df: df['res_bal'].notna() & ~df['res_bal'].isin(['R', 'B'])),

        ('GL_ACC_TYPE_INVALID',
         20, 'Chart of Accounts', 'Validity', 'Medium',
         'Account type is not GL, AP, or AR',
         'The account_type field must be GL (General Ledger), AP (Accounts Payable control), or AR (Accounts Receivable control). '
         'An unrecognised account type cannot be mapped to the new system chart of accounts. '
         'Affected accounts must be corrected or excluded before migration.',
         'Correct the account_type to GL, AP, or AR.',
         'aglaccounts', None,
         "WHERE status = 'N' AND account_type NOT IN ('GL', 'AP', 'AR')",
         lambda df: df['account_type'].notna() & ~df['account_type'].isin(['GL', 'AP', 'AR'])),

        ('GL_ACC_PERIOD_INV',
         20, 'Chart of Accounts', 'Validity', 'Medium',
         'Account valid-from date is after its valid-to date',
         'The period_from date must be earlier than or equal to period_to. '
         'An inverted validity range means the account has no valid period and should never be active. '
         'This will cause posting failures in the new system if not corrected.',
         'Correct period_from and period_to so that the valid-from is not after the valid-to.',
         'aglaccounts', None,
         'WHERE status = \'N\' AND period_from > period_to',
         lambda df: df['period_from'].notna() & df['period_to'].notna() & (df['period_from'] > df['period_to'])),

        ('GL_ACC_STALE_N',
         20, 'Chart of Accounts', 'Validity', 'Low',
         'Account status is active (N) but validity period has expired',
         'Active accounts must have a valid-to date that is in the future. '
         'An account whose validity period has passed but is still marked active may represent an account that should have been closed. '
         'These accounts should be reviewed before migration to avoid carrying stale data into the new system.',
         'Either extend the validity period if the account is still required or close the account (status C) if it is no longer needed.',
         'aglaccounts', None,
         'WHERE status = \'N\' AND period_to < GETDATE()',
         lambda df: df['period_to'].notna() & (df['period_to'] < pd.Timestamp.now())),

        # UNIQUENESS
        ('GL_ACC_DUP_CODE',
         20, 'Chart of Accounts', 'Uniqueness', 'Critical',
         'Duplicate account code within the same client',
         'Each account code must be unique within a client. '
         'Duplicate account codes indicate a data integrity failure in the source system. '
         'They cannot be migrated without resolution as the new system enforces uniqueness on account code.',
         'Investigate each duplicate pair. Merge or delete the redundant account after confirming no live transactions depend on it.',
         'aglaccounts', None,
         'WHERE (client, account) appears more than once',
         lambda df: df.duplicated(subset=['client', 'account'], keep=False)),

        # TIMELINESS
        ('GL_ACC_STALE_MOD',
         20, 'Chart of Accounts', 'Timeliness', 'Low',
         'Account not modified in over 3 years',
         'Accounts that have not been updated in more than 3 years may be obsolete or no longer required. '
         'These should be reviewed before migration to determine whether they should be carried forward into the new system or closed.',
         'Review each stale account. Close accounts that are no longer required and confirm that active accounts are still needed.',
         'aglaccounts', None,
         'WHERE status = \'N\' AND last_update < DATEADD(year, -3, GETDATE())',
         lambda df: df['last_update'].notna() & (df['last_update'] < pd.Timestamp.now() - pd.Timedelta(days=3 * 365))),

    ]


# =============================================================================
# GL DQ CHECK CATALOGUE — remaining checks, to be built once real data schema
# is confirmed for each dataset
# =============================================================================
# Chart of Accounts (aglaccounts) — IMPLEMENTED ABOVE
#   GL_ACC_DESC_MISSING   Active account has no description
#   GL_ACC_GRP_MISSING    Active account not assigned to a reporting group
#   GL_ACC_RESBAL_MISSING Missing Balance Sheet/P&L classification
#   GL_ACC_RULE_MISSING   Active account missing its posting rule ID
#   GL_ACC_PERIOD_MISSING Active account missing valid-from date
#   GL_ACC_RESBAL_INVALID res_bal contains invalid code (must be R or B)
#   GL_ACC_TYPE_INVALID   account_type not a valid GL/AP/AR code
#   GL_ACC_PERIOD_INV     Valid-from date is after the valid-to date
#   GL_ACC_STALE_N        Account is active (status N) but validity period has expired
#   GL_ACC_DUP_CODE       Duplicate account code within the same client
#   GL_ACC_STALE_MOD      Account not updated in over 3 years
#
# Chart of Accounts (aglaccounts) — PENDING (bflag reconciliation bit TBD)
#   GL_ACC_BFLAG_CON      Reconciliation account (specific bflag bit) not flagged as AP or AR type
#
# Dimension Values (agldimvalue)
#   GL_DIM_DESC_MISSING   Active dimension value has no description
#   GL_DIM_PERIOD_MISSING Active dimension value missing valid-from period
#   GL_DIM_PERIOD_INV     Dimension valid-from period is after the valid-to period
#   GL_DIM_WF_STUCK       Dimension value stuck in a non-approved workflow state
#   GL_DIM_ORPHAN_REL     Hierarchy link to a parent that is missing or inactive
#   GL_DIM_DUP            Duplicate dimension code within the same attribute and House
#
# Opening Balances / Period Balances (aglperiodic → frame key aglyearend) — 3 of 5 IMPLEMENTED
#   GL_BAL_AMT_MISSING    Opening balance record has no amount                             ✓ LIVE
#   GL_BAL_ORPHAN_ACC     Balance refers to an account code not in the chart of accounts   ✓ LIVE
#   GL_BAL_PL_NONZERO     P&L account carries a non-zero balance at year end               ✓ LIVE
#   GL_BAL_FX_MISSING     Foreign currency balance missing cur_amount — SKIP (always GBP)
#   GL_BAL_TOTAL_NET      GL out of balance (aggregate check — does not fit row-level model)
#
# Transactions (agltransact)
#   GL_TRA_ORPHAN_DIM1    Transaction coded to a dimension value that does not exist or is inactive
#
# Journals (gl_journals — agltransact filtered to current FY)
#   DQ-GJ-C01  Journal line has no voucher number
#   DQ-GJ-C02  Journal line has no account code
#   DQ-GJ-C03  Journal line has no amount
#   DQ-GJ-C04  Journal line has no transaction date
#   DQ-GJ-C05  Journal line has no voucher entry date
#   DQ-GJ-C06  Journal line has no voucher type
#   DQ-GJ-C07  Manual journal line (JRNL type) has no description
#   DQ-GJ-C08  Journal line has no user ID
#   DQ-GJ-V01  update_flag contains an invalid debit/credit code
#   DQ-GJ-V02  Journal trans_date is in the future
#   DQ-GJ-V03  Journal voucher_date is in the future
#   DQ-GJ-V04  trans_date and voucher_date differ by more than one GL period (~60 days)
#   DQ-GJ-V05  Journal line has no currency code
#   DQ-GJ-V06  Non-GBP journal line is missing its transaction currency amount
#   DQ-GJ-V07  Period is outside the expected fiscal year range (202601–202615)
#   DQ-GJ-V08  Sub-ledger reference (apar_id) on a non-control account line
#   DQ-GJ-K01  Voucher does not balance — debits do not equal credits
#   DQ-GJ-K02  trans_date falls in a different period to the period field
#   DQ-GJ-K03  apar_id and apar_type are not both present or both absent
#   DQ-GJ-K04  Voucher contains lines posted to different periods
#   DQ-GJ-K05  tax_code and tax_system are not both present or both absent
#   DQ-GJ-D01  Duplicate composite primary key (client, voucher_no, sequence_no)
#   DQ-GJ-D02  Potential duplicate posting — same client, voucher, account, amount, and date
#   DQ-GJ-S02  Journal line is in a year-end adjustment period (13, 14, or 15)
#   DQ-GJ-S04  Non-GBP journal line — FX population for target system planning
#   DQ-GJ-S05  Journal line carries a sub-ledger reference (apar_id populated)
#   DQ-GJ-X01  Journal account code does not exist in the chart of accounts
#   DQ-GJ-X02  Journal posts to a closed or inactive account
#   DQ-GJ-X03  Journal dim_1 value does not exist as an active dimension in master data
