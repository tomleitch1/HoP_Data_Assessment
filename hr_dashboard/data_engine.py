"""
Royal Mail HR & Payroll Data Quality Assessment — Data Engine
=================================================================
One-off bid-demo build (Veran Performance x Royal Mail). Same four-layer
shape as the Parliament finance dashboard's data_engine.py — load CSVs,
run every rule lambda, compute pass/fail/RAG, expose a drill-down lookup —
but deliberately lean: two tables, no disk cache, no per-check population
elif-chains, no versioning. This is a one-off demo, not a live engagement;
the caching/versioning machinery in the finance engine solved problems
(slow real-data reloads, HOC/HOL re-extracts) that don't exist here.

Single combined dataset — every dq_results row carries a constant 'house'
value (config.ENTITY_LABEL) purely so the shared scorecard/grid components
(built generic over "however many house values are present") work unchanged.
"""

import os

import numpy as np
import pandas as pd

from hr_dashboard.core.config import DATA_DIR, ENTITY_LABEL, RAG_THRESHOLDS
from hr_dashboard.core.rules.employee_rules import get_employee_checks, ACTIVE_ONLY_CHECKS
from hr_dashboard.core.rules.payroll_rules import get_payroll_checks

_DATE_COLS = {
    'employee_master':       ['dob', 'start_date', 'leaving_date'],
    'payroll_transactions':  ['pay_date'],
}

_NUMERIC_COLS = {
    'employee_master':      ['contracted_hours'],
    'payroll_transactions': [
        'basic_pay', 'overtime_hours', 'overtime_pay', 'shift_allowance', 'bonus',
        'gross_pay', 'tax_deducted', 'ni_deducted', 'pension_deducted', 'other_deductions',
        'net_pay', 'pension_contribution_pct',
    ],
}


def _clean_numeric(series: pd.Series) -> pd.Series:
    """Strip thousands-separator commas (SSMS/Excel artefact — same issue the
    finance dashboard's data_engine.py handles) before numeric conversion."""
    if series.dtype == object:
        series = series.astype(str).str.replace(',', '', regex=False)
    return pd.to_numeric(series, errors='coerce')


def load_data():
    frames = {}
    for table in ('employee_master', 'payroll_transactions'):
        path = os.path.join(DATA_DIR, f'{table}.csv')
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Missing {path}. Run `python scripts/generate_hr_dummy_data.py` first."
            )
        df = pd.read_csv(path, dtype=str, keep_default_na=True)

        for col in _DATE_COLS.get(table, []):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

        for col in _NUMERIC_COLS.get(table, []):
            if col in df.columns:
                df[col] = _clean_numeric(df[col])

        df['house'] = ENTITY_LABEL
        frames[table] = df

    return frames


def get_dq_checks():
    return get_employee_checks() + get_payroll_checks()


def _employee_population(df: pd.DataFrame, check_id: str) -> pd.DataFrame:
    if check_id in ACTIVE_ONLY_CHECKS:
        return df[df['employment_status'] == 'Active']
    return df


def run_dq_analysis(frames):
    checks = get_dq_checks()
    rows = []

    for (check_id, scope_id, obj, dimension, severity, description, intent,
         remediation, table, joined_table, sql_equiv, fn) in checks:

        base_df = frames.get(table)
        if base_df is None or base_df.empty:
            continue

        pop = _employee_population(base_df, check_id) if table == 'employee_master' else base_df
        if pop.empty:
            continue

        if joined_table is not None:
            mask = fn(pop, frames)
        else:
            mask = fn(pop)

        total = len(pop)
        failing = int(mask.sum())
        passing = total - failing
        error_rate = round(failing / total * 100, 2) if total else 0.0
        pass_rate = round(100 - error_rate, 2)

        green_t, amber_t = RAG_THRESHOLDS.get(severity, (5, 15))
        if error_rate <= green_t:
            rag = 'Green'
        elif error_rate <= amber_t:
            rag = 'Amber'
        else:
            rag = 'Red'

        rows.append({
            'check_id': check_id,
            'scope_id': int(scope_id),
            'object': obj,
            'house': ENTITY_LABEL,
            'dimension': dimension,
            'severity': severity,
            'description': description,
            'intent': intent,
            'total': total,
            'failing': failing,
            'passing': passing,
            'error_rate': error_rate,
            'pass_rate': pass_rate,
            'rag': rag,
            'remediation': remediation,
            'table': table,
            'joined_table': joined_table,
            'technical_logic': sql_equiv,
        })

    return pd.DataFrame(rows)


def get_check_columns():
    """check_id -> list of column names to highlight in the modal inspector."""
    return {
        'EMP_NI_MISSING':          ['ni_number'],
        'EMP_NI_FORMAT':           ['ni_number'],
        'EMP_BANK_MISSING':        ['bank_account', 'sort_code'],
        'EMP_DOB_MISSING':         ['dob'],
        'EMP_DOB_INVALID':         ['dob'],
        'EMP_START_AFTER_LEAVE':   ['start_date', 'leaving_date'],
        'EMP_DUP_NI':              ['ni_number'],
        'EMP_DUP_EMPID':           ['employee_id'],
        'EMP_MANAGER_ORPHAN':      ['manager_id'],
        'EMP_EMAIL_MISSING':       ['email'],
        'EMP_POSTCODE_FORMAT':     ['postcode'],
        'EMP_TAX_CODE_MISSING':    ['tax_code'],

        'PAY_NET_EXCEEDS_GROSS':      ['gross_pay', 'net_pay'],
        'PAY_NEGATIVE_GROSS':         ['gross_pay'],
        'PAY_MISSING_TAX_CODE':       ['tax_code'],
        'PAY_NI_CAT_MISSING':         ['ni_category'],
        'PAY_ORPHAN_EMPLOYEE':        ['employee_id'],
        'PAY_DUP_TRANSACTION':        ['employee_id', 'pay_period'],
        'PAY_OVERTIME_NO_HOURS':      ['overtime_pay', 'overtime_hours'],
        'PAY_GROSSNET_CALC_MISMATCH': ['gross_pay', 'tax_deducted', 'ni_deducted', 'pension_deducted', 'other_deductions', 'net_pay'],
        'PAY_BANK_MISMATCH':          ['bank_account', 'sort_code'],
        'PAY_ZERO_NET_ACTIVE':        ['gross_pay', 'net_pay'],
        'PAY_STALE_PENDING':          ['status', 'pay_date'],
        'PAY_FUTURE_PAYDATE':         ['pay_date'],
    }


_CHECK_LOOKUP = {c[0]: c for c in get_dq_checks()}


def get_failing_records(check_id, frames, base_cols=None, for_export=False):
    if check_id not in _CHECK_LOOKUP:
        return pd.DataFrame()

    (_, _, _, _, _, _, _, _, table, joined_table, _, fn) = _CHECK_LOOKUP[check_id]
    base_df = frames.get(table)
    if base_df is None or base_df.empty:
        return pd.DataFrame()

    pop = _employee_population(base_df, check_id) if table == 'employee_master' else base_df
    mask = fn(pop, frames) if joined_table is not None else fn(pop)
    failing = pop[mask].copy()

    if check_id == 'PAY_ORPHAN_EMPLOYEE':
        return failing[['payroll_id', 'employee_id', 'pay_period', 'pay_date', 'status']]

    if check_id == 'PAY_BANK_MISMATCH':
        emp = frames.get('employee_master')
        if emp is not None and not emp.empty:
            emp_bank = (
                emp.drop_duplicates(subset=['employee_id'])
                .set_index('employee_id')[['bank_account', 'sort_code']]
                .rename(columns={'bank_account': 'employee_master.bank_account', 'sort_code': 'employee_master.sort_code'})
            )
            failing = failing.join(emp_bank, on='employee_id')
        return failing[[c for c in failing.columns if c not in ('house',)]]

    if check_id == 'EMP_MANAGER_ORPHAN':
        return failing[['employee_id', 'first_name', 'last_name', 'manager_id', 'department', 'site']]

    cols = [c for c in failing.columns if c != 'house']
    return failing[cols]
