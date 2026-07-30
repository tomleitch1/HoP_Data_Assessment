"""
Generate dummy budget data for development.

Output: data/budgets/budgets_report.csv
Mimics the pre-built Finance report format (single HOC+HOL file).

Columns match the Finance report exactly:
  Mipck-l1, Mipck-l1(T), Mipck-l2, Mipck-l2(T), Mipck-l3,
  Account, Account(T), Department, Directorate, Costc,
  Haiscode, Haiscode(T), Recharge, Year, Period,
  Amount, Amount DA, Amount DB, Amount DE, Amount DF,
  Amount DG, Amount DH, Amount DI, Unit
"""

import os
import random
import sys

import numpy as np
import pandas as pd

random.seed(42)
np.random.seed(42)

# ── Output path ───────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT   = os.path.dirname(SCRIPT_DIR)
OUT_DIR     = os.path.join(REPO_ROOT, 'data', 'budgets')
OUT_FILE    = os.path.join(OUT_DIR, 'budgets_report.csv')
os.makedirs(OUT_DIR, exist_ok=True)

# ── MIPCK hierarchy ───────────────────────────────────────────────────────────
MIPCK = [
    # (L1 code, L1 desc, L2 code, L2 desc, L3)
    ('SAL',  'Salaries & Wages',        'SAL01', 'Pay',               'Pay and NIC'),
    ('SAL',  'Salaries & Wages',        'SAL02', 'Agency Staff',      'Agency & Temporary'),
    ('SAL',  'Salaries & Wages',        'SAL03', 'Superannuation',    'Pension Costs'),
    ('PROP', 'Property & Facilities',   'PROP01','Accommodation',     'Rent & Rates'),
    ('PROP', 'Property & Facilities',   'PROP02','Maintenance',       'Repairs & Maintenance'),
    ('ICT',  'ICT & Digital',           'ICT01', 'Infrastructure',    'IT Hardware & Networks'),
    ('ICT',  'ICT & Digital',           'ICT02', 'Software',          'Licences & Subscriptions'),
    ('ICT',  'ICT & Digital',           'ICT03', 'Support',           'IT Support Contracts'),
    ('EXT',  'External Services',       'EXT01', 'Professional Svcs', 'Consultancy & Advisory'),
    ('EXT',  'External Services',       'EXT02', 'Parliamentary Svcs','Broadcasting & Reporting'),
    ('CAP',  'Capital Expenditure',     'CAP01', 'IT Capital',        'IT Capital Projects'),
    ('CAP',  'Capital Expenditure',     'CAP02', 'Building Capital',  'Estates Capital Projects'),
    ('ADM',  'Administration',          'ADM01', 'Office Supplies',   'Stationery & Consumables'),
    ('ADM',  'Administration',          'ADM02', 'Travel & Subsist',  'Staff Travel'),
    ('ADM',  'Administration',          'ADM03', 'Comms & Marketing', 'Communications'),
]

# ── Departments / directorates ────────────────────────────────────────────────
DEPTS = [
    ('HR',  'Finance & HR',          'Corporate Services'),
    ('FIN', 'Finance & HR',          'Corporate Services'),
    ('DIG', 'Digital Service',       'Digital & Technology'),
    ('ICT', 'ICT Department',        'Digital & Technology'),
    ('EST', 'Estates',               'Facilities & Estates'),
    ('FAC', 'Facilities Management', 'Facilities & Estates'),
    ('CLK', 'Clerk\'s Department',   'Parliamentary'),
    ('LIB', 'Library',               'Parliamentary'),
    ('COM', 'Communications',        'Parliamentary'),
    ('SEC', 'Security',              'Security & Safety'),
]

# ── HOC accounts (numeric) ────────────────────────────────────────────────────
HOC_ACCOUNTS = [
    ('1100', 'Staff Salaries'),
    ('1110', 'Agency Staff'),
    ('1120', 'Employer NIC'),
    ('1130', 'Employer Pension'),
    ('2100', 'Accommodation Costs'),
    ('2110', 'Maintenance & Repairs'),
    ('2120', 'Cleaning & Security'),
    ('3100', 'IT Hardware'),
    ('3110', 'Software Licences'),
    ('3120', 'IT Support'),
    ('3130', 'Telecoms'),
    ('4100', 'Consultancy'),
    ('4110', 'Legal Services'),
    ('4120', 'Broadcasting Services'),
    ('5100', 'Office Supplies'),
    ('5110', 'Travel & Subsistence'),
    ('5120', 'Conferences & Events'),
    ('6100', 'IT Capital'),
    ('6110', 'Buildings Capital'),
    ('9100', 'Internal Recharge Out'),
]

# ── HOL accounts (letter-prefix) ─────────────────────────────────────────────
HOL_ACCOUNTS = [
    ('A1100', 'Staff Salaries'),
    ('A1110', 'Agency Staff'),
    ('A1120', 'Employer NIC'),
    ('A1130', 'Employer Pension'),
    ('A2100', 'Accommodation Costs'),
    ('A2110', 'Maintenance & Repairs'),
    ('A3100', 'IT Hardware'),
    ('A3110', 'Software Licences'),
    ('A3120', 'IT Support'),
    ('A4100', 'Consultancy'),
    ('A4110', 'Legal Services'),
    ('A5100', 'Office Supplies'),
    ('A5110', 'Travel & Subsistence'),
    ('A6100', 'Capital Expenditure'),
]


def _make_hais(dept_code, seq):
    return f'{dept_code}{seq:04d}00'


def _make_costc(dept_code, seq):
    return f'{dept_code}{seq:03d}'


def _budget_amounts(scale=1.0):
    """Return (orig, virement, actuals_fraction, q1_frac, q2_frac, q3_frac, live_delta)."""
    orig = round(random.uniform(50_000, 5_000_000) * scale, -2)
    vir  = round(orig * random.uniform(-0.05, 0.12), -2)
    curr = orig + vir
    actuals_frac = random.uniform(0.3, 0.85)
    q1_delta = round(curr * random.uniform(-0.03, 0.05), -2)
    q2_delta = round(curr * random.uniform(-0.04, 0.06), -2)
    q3_delta = round(curr * random.uniform(-0.05, 0.08), -2)
    live_delta = round(q3_delta * random.uniform(0.8, 1.2), -2)
    return orig, vir, curr, actuals_frac, q1_delta, q2_delta, q3_delta, live_delta


def _spread_to_periods(annual, num_periods, period_12th_variance=0.15):
    """Spread an annual figure across periods with some month-to-month variance."""
    if annual == 0 or num_periods == 0:
        return [0.0] * num_periods
    base = annual / num_periods
    raw  = [base * (1 + random.uniform(-period_12th_variance, period_12th_variance))
            for _ in range(num_periods)]
    # re-scale to hit the total exactly
    total = sum(raw)
    if total == 0:
        return [annual / num_periods] * num_periods
    return [v * annual / total for v in raw]


def build_rows(house, accounts, periods, year=2025):
    rows = []
    for dept_code, dept_name, directorate in DEPTS:
        num_hais = random.randint(2, 5)
        for h_seq in range(1, num_hais + 1):
            hais      = _make_hais(dept_code, h_seq)
            hais_desc = f'{dept_name} – {dept_code} unit {h_seq}'
            costc     = _make_costc(dept_code, h_seq)
            mipck_row = random.choice(MIPCK)
            l1, l1t, l2, l2t, l3 = mipck_row

            # Pick a relevant account
            acc, acc_desc = random.choice(accounts)

            # Scale capital accounts smaller
            scale = 0.3 if l1 == 'CAP' else 1.0

            orig, vir, curr, actfrac, q1d, q2d, q3d, live_d = _budget_amounts(scale)
            actuals = round(curr * actfrac, 2)

            # Spread across periods
            curr_by_period   = _spread_to_periods(curr,   periods)
            actuals_by_period = _spread_to_periods(actuals, min(periods, max(1, int(periods * actfrac))))
            # Pad actuals with zeros for future periods
            actuals_by_period += [0.0] * (periods - len(actuals_by_period))

            for p in range(1, periods + 1):
                p_curr   = round(curr_by_period[p - 1], 2)
                p_actual = round(actuals_by_period[p - 1] if p <= len(actuals_by_period) else 0.0, 2)
                p_fcst   = round(p_curr + live_d / periods, 2)
                p_pfst   = round(p_curr + (q2d + q3d) / (2 * periods), 2)
                p_q1     = round(p_curr + q1d / periods, 2)
                p_q2     = round(p_curr + q2d / periods, 2)
                p_q3     = round(p_curr + q3d / periods, 2)

                rows.append({
                    'Mipck-l1':    l1,
                    'Mipck-l1(T)': l1t,
                    'Mipck-l2':    l2,
                    'Mipck-l2(T)': l2t,
                    'Mipck-l3':    l3,
                    'Account':     acc,
                    'Account(T)':  acc_desc,
                    'Department':  dept_name,
                    'Directorate': directorate,
                    'Costc':       costc,
                    'Haiscode':    hais,
                    'Haiscode(T)': hais_desc,
                    'Recharge':    house,
                    'Year':        year,
                    'Period':      p,
                    'Amount':      p_actual,
                    'Amount DA':   round(orig / periods, 2),   # original budget per period
                    'Amount DB':   p_curr,                      # current budget per period
                    'Amount DE':   p_fcst,                      # live forecast
                    'Amount DF':   p_pfst,                      # pre-financial statement forecast
                    'Amount DG':   p_q1,
                    'Amount DH':   p_q2,
                    'Amount DI':   p_q3,
                    'Unit':        f'{dept_code}{h_seq:02d}',
                })

    return rows


def inject_dq_failures(rows):
    """Introduce deliberate DQ failures for testing the checks."""
    n = len(rows)

    # BUD_ACCOUNT_MISSING — 1% of rows
    account_missing_idx = random.sample(range(n), max(1, int(n * 0.01)))
    for i in account_missing_idx:
        rows[i]['Account'] = ''

    # BUD_MIPCK_MISSING — 0.8%
    mipck_missing_idx = random.sample(range(n), max(1, int(n * 0.008)))
    for i in mipck_missing_idx:
        rows[i]['Mipck-l1'] = ''
        rows[i]['Mipck-l1(T)'] = ''

    # BUD_HAISCODE_MISSING — 1.5%
    hais_missing_idx = random.sample(range(n), max(1, int(n * 0.015)))
    for i in hais_missing_idx:
        rows[i]['Haiscode'] = ''
        rows[i]['Haiscode(T)'] = ''

    # BUD_COSTC_MISSING — 2%
    costc_missing_idx = random.sample(range(n), max(1, int(n * 0.02)))
    for i in costc_missing_idx:
        rows[i]['Costc'] = ''

    # BUD_CURR_BUDGET_MISSING — 0.5%
    curr_missing_idx = random.sample(range(n), max(1, int(n * 0.005)))
    for i in curr_missing_idx:
        rows[i]['Amount DB'] = None

    # BUD_ORIG_BUDGET_MISSING — 1%
    orig_missing_idx = random.sample(range(n), max(1, int(n * 0.01)))
    for i in orig_missing_idx:
        rows[i]['Amount DA'] = None

    # BUD_PERIOD_INVALID — a handful of rows with period = 16 (invalid)
    period_bad_idx = random.sample(range(n), max(1, int(n * 0.003)))
    for i in period_bad_idx:
        rows[i]['Period'] = 16

    # BUD_ACTUALS_NO_CURR_BUDGET — a handful with actuals but zero current budget
    no_budget_idx = random.sample(range(n), max(1, int(n * 0.008)))
    for i in no_budget_idx:
        rows[i]['Amount'] = abs(rows[i].get('Amount', 0) or 0) + random.uniform(1000, 50000)
        rows[i]['Amount DB'] = 0.0

    return rows


if __name__ == '__main__':
    print('Generating budget dummy data...')

    hoc_rows = build_rows('HOC', HOC_ACCOUNTS, periods=13, year=2025)
    hol_rows = build_rows('HOL', HOL_ACCOUNTS, periods=12, year=2025)

    all_rows = hoc_rows + hol_rows
    all_rows = inject_dq_failures(all_rows)

    df = pd.DataFrame(all_rows)
    df.to_csv(OUT_FILE, index=False)

    hoc = df[df['Recharge'] == 'HOC']
    hol = df[df['Recharge'] == 'HOL']
    print(f'  HOC: {len(hoc):,} rows')
    print(f'  HOL: {len(hol):,} rows')
    print(f'  Total: {len(df):,} rows')
    print(f'  Saved to: {OUT_FILE}')
    print()
    print('  HOC Current Budget (DB):',
          f'£{pd.to_numeric(hoc["Amount DB"], errors="coerce").sum():,.0f}')
    print('  HOL Current Budget (DB):',
          f'£{pd.to_numeric(hol["Amount DB"], errors="coerce").sum():,.0f}')
    print('  HOC GL Actuals:',
          f'£{pd.to_numeric(hoc["Amount"], errors="coerce").sum():,.0f}')
    print('  HOL GL Actuals:',
          f'£{pd.to_numeric(hol["Amount"], errors="coerce").sum():,.0f}')
