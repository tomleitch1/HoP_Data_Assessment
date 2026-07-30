import pandas as pd
from dashboard.core.config import Scope


def _bud_account_orphan(df, frames):
    """Budget lines with an account code not found in the Chart of Accounts for the same house."""
    coa = frames.get('aglaccounts')
    if coa is None or coa.empty or df.empty:
        return pd.Series(False, index=df.index)
    house = df['house'].iloc[0] if 'house' in df.columns else None
    if house:
        valid = set(coa.loc[coa['house'] == house, 'account'].dropna().astype(str).str.strip())
    else:
        valid = set(coa['account'].dropna().astype(str).str.strip())
    return ~df['account'].astype(str).str.strip().isin(valid)


def _bud_account_closed(df, frames):
    """Budget lines coded to a closed GL account (account exists but status != 'N')."""
    coa = frames.get('aglaccounts')
    if coa is None or coa.empty or df.empty:
        return pd.Series(False, index=df.index)
    house = df['house'].iloc[0] if 'house' in df.columns else None
    if house:
        h_coa = coa[coa['house'] == house]
    else:
        h_coa = coa
    valid_accounts  = set(h_coa['account'].dropna().astype(str).str.strip())
    closed_accounts = set(h_coa.loc[h_coa['status'] != 'N', 'account'].dropna().astype(str).str.strip())
    acc = df['account'].astype(str).str.strip()
    return acc.isin(valid_accounts) & acc.isin(closed_accounts)


def get_budget_checks():
    checks = [
        (
            'BUD_ACCOUNT_MISSING', Scope.PBF, 'Budget Lines', 'Completeness', 'High',
            'Budget line with no account code',
            'Every budget line must be coded to a valid GL account. A line with no account cannot '
            'be validated against the chart of accounts, cannot be included in account-level '
            'reconciliation, and may be silently excluded from financial reporting in the new system.',
            'Identify and assign a valid GL account code to every unaccounted budget line.',
            'budgets_report', None,
            "account IS NULL OR account = ''",
            lambda df: df['account'].isna() | (df['account'].astype(str).str.strip() == ''),
        ),
        (
            'BUD_MIPCK_MISSING', Scope.PBF, 'Budget Lines', 'Completeness', 'Medium',
            'Budget line with no MIPCK L1 reporting hierarchy code',
            'Every budget line must sit within the MIPCK reporting hierarchy. A missing L1 code '
            'means the line cannot be included in the Finance team\'s standard budget reports and '
            'exception queries will produce misleading totals.',
            'Assign a valid MIPCK L1 code to every unclassified budget line.',
            'budgets_report', None,
            "mipck_l1 IS NULL OR mipck_l1 = ''",
            lambda df: df['mipck_l1'].isna() | (df['mipck_l1'].astype(str).str.strip() == ''),
        ),
        (
            'BUD_HAISCODE_MISSING', Scope.PBF, 'Budget Lines', 'Completeness', 'Medium',
            'Budget line with no HAIS code',
            'Finance forecasts at HAIS code level. A budget line without a HAIS code cannot be '
            'matched to a forecast entry and will be excluded from variance analysis and the '
            'Budget vs Actuals report from Day 1 in the new system.',
            'Assign the correct HAIS code to every unclassified budget line.',
            'budgets_report', None,
            "haiscode IS NULL OR haiscode = ''",
            lambda df: df['haiscode'].isna() | (df['haiscode'].astype(str).str.strip() == ''),
        ),
        (
            'BUD_COSTC_MISSING', Scope.PBF, 'Budget Lines', 'Completeness', 'Low',
            'Budget line with no cost centre code',
            'Cost centre is a mandatory dimension for GL posting and budget reporting. A missing '
            'cost centre prevents the line from being attributed to a directorate or department '
            'and will break departmental budget reports in the new system.',
            'Assign a valid cost centre to every unclassified budget line.',
            'budgets_report', None,
            "costc IS NULL OR costc = ''",
            lambda df: df['costc'].isna() | (df['costc'].astype(str).str.strip() == ''),
        ),
        (
            'BUD_CURR_BUDGET_MISSING', Scope.PBF, 'Budget Lines', 'Completeness', 'High',
            'Budget line with no current approved budget figure',
            'The current approved budget (CURR version) is the primary control figure for the '
            'migration. A line with no current budget cannot be validated, cannot populate '
            'Budget vs Actuals from Day 1, and will not appear in the new system\'s financial reports.',
            'Confirm and enter the current approved budget for every line that is missing it.',
            'budgets_report', None,
            'curr_budget IS NULL',
            lambda df: df['curr_budget'].isna(),
        ),
        (
            'BUD_ORIG_BUDGET_MISSING', Scope.PBF, 'Budget Lines', 'Completeness', 'Medium',
            'Budget line with no original budget figure',
            'The original budget (ORIG version) provides the baseline against which virements and '
            'adjustments are measured. Without it, the audit trail for in-year budget movements '
            'cannot be reconstructed in the new system.',
            'Confirm and enter the original budget for every line that is missing it.',
            'budgets_report', None,
            'orig_budget IS NULL',
            lambda df: df['orig_budget'].isna(),
        ),
        (
            'BUD_PERIOD_INVALID', Scope.PBF, 'Budget Lines', 'Validity', 'Medium',
            'Budget line with a missing or out-of-range period number',
            'Period is the time dimension for budget and actuals reporting. A missing or invalid '
            'period means the line cannot be attributed to the correct month, will be excluded '
            'from period-by-period analysis, and cannot be mapped to the new system\'s fiscal calendar.',
            'Correct the period value to a valid period number (1–15 for HOC, 1–12 for HOL).',
            'budgets_report', None,
            'period IS NULL OR period NOT BETWEEN 1 AND 15',
            lambda df: df['period'].isna() | ~df['period'].between(1, 15),
        ),
        (
            'BUD_ACCOUNT_ORPHAN', Scope.PBF, 'Budget Lines', 'Consistency', 'High',
            'Budget line with an account code not found in the Chart of Accounts',
            'Every budget line must reference a valid, known GL account. An orphaned account '
            'cannot be validated during migration, will fail GL account mapping in the new '
            'system, and may cause the opening budget to not load at all.',
            'Resolve the account code against the Chart of Accounts and correct or delete the affected lines.',
            'budgets_report', 'aglaccounts',
            "account NOT IN (SELECT account FROM aglaccounts WHERE house = budget.house)",
            _bud_account_orphan,
        ),
        (
            'BUD_ACCOUNT_CLOSED', Scope.PBF, 'Budget Lines', 'Consistency', 'Medium',
            'Budget line coded to a closed GL account',
            'Budget lines must reference active accounts. Posting to a closed account will fail '
            'in the new system. A closed account on a budget line also suggests the budget was '
            'not updated following an account deactivation and requires a corrective repost.',
            'Repost affected budget lines to the replacement active account.',
            'budgets_report', 'aglaccounts',
            "account IN (SELECT account FROM aglaccounts WHERE status != 'N' AND house = budget.house)",
            _bud_account_closed,
        ),
        (
            'BUD_ACTUALS_NO_CURR_BUDGET', Scope.PBF, 'Budget Lines', 'Consistency', 'Medium',
            'Spend recorded against an account with no current approved budget',
            'Every account with actual spend must have an approved budget entry. Unbudgeted spend '
            'cannot be reported against a budget in the new system and will appear as an unexplained '
            'variance from Day 1 of go-live.',
            'Create an approved budget entry for every account that has recorded actuals but no current budget.',
            'budgets_report', None,
            "gl_actuals <> 0 AND (curr_budget IS NULL OR curr_budget = 0)",
            lambda df: (
                df['gl_actuals'].fillna(0).abs() > 0.01
            ) & (df['curr_budget'].fillna(0).abs() <= 0.01),
        ),
    ]
    return checks
