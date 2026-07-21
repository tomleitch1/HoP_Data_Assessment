"""
Royal Mail HR & Payroll Data Quality Assessment — Dummy Data Generator
=======================================================================
One-off bid-demo build for Veran Performance. Entirely synthetic — no
relationship to any real Royal Mail Group data. Generates two CSVs:

  - employee_master.csv          (~600 employee records)
  - payroll_transactions.csv     (~12 weekly pay runs per active employee)

Deliberately injects the specific data quality issues the HR/Payroll DQ
checks are designed to catch (missing NI numbers, duplicate IDs, orphaned
payroll records, gross/net mismatches, etc.) so the dashboard has something
real to show in a demo.

Run:    python scripts/generate_hr_dummy_data.py
Output: ./data/hr/
"""

import os
import random
from datetime import date, timedelta

import pandas as pd
from faker import Faker

fake = Faker('en_GB')
random.seed(7)
Faker.seed(7)

OUTPUT_DIR = os.path.join('data', 'hr')
os.makedirs(OUTPUT_DIR, exist_ok=True)

TODAY = date.today()

N_EMPLOYEES = 600

BUSINESS_UNITS = {
    'Royal Mail':            0.68,
    'Parcelforce Worldwide': 0.27,
    'Group Functions':       0.05,
}
DEPARTMENTS = {
    'Royal Mail':            ['Delivery Office', 'Mail Centre', 'Distribution Hub', 'Customer Service', 'Fleet & Logistics'],
    'Parcelforce Worldwide': ['Depot Operations', 'Hub Sortation', 'Customer Service', 'Fleet & Logistics'],
    'Group Functions':       ['Finance', 'HR', 'IT', 'Sales & Marketing', 'Legal & Compliance'],
}
SITES = [fake.city() for _ in range(24)]
REGIONS = ['London & South East', 'Midlands', 'North West', 'North East & Yorkshire', 'Scotland', 'Wales & West', 'South West']

GRADES_OPS   = ['OPS1', 'OPS2']
GRADES_MGMT  = ['MGR1', 'MGR2']
GRADES_OTHER = ['SUP1', 'EXEC']

CONTRACT_TYPES = {'Permanent': 0.75, 'Fixed-Term': 0.15, 'Casual': 0.10}
BASIS          = {'Full-Time': 0.70, 'Part-Time': 0.30}
UNION_OPS      = {'CWU': 0.68, 'Unite': 0.04, 'None': 0.28}
UNION_NONOPS   = {'CWU': 0.05, 'Unite': 0.10, 'None': 0.85}
PENSION_SCHEMES = ['RMPP', 'DC Scheme', 'None']

INVALID_NI_PREFIXES = {'BG', 'GB', 'NK', 'KN', 'TN', 'NT', 'ZZ'}
NI_FIRST_OK  = 'ABCEGHJKLMNOPRSTWXYZ'
NI_SECOND_OK = 'ABCEGHJKLMNPRSTWXYZ'


def _weighted_choice(weights: dict):
    keys = list(weights.keys())
    vals = list(weights.values())
    return random.choices(keys, weights=vals, k=1)[0]


def _rand_date(start: date, end: date) -> date:
    delta = (end - start).days
    if delta <= 0:
        return start
    return start + timedelta(days=random.randint(0, delta))


def _fmt_ni(valid=True) -> str:
    if valid:
        prefix = random.choice(NI_FIRST_OK) + random.choice(NI_SECOND_OK)
        while prefix in INVALID_NI_PREFIXES:
            prefix = random.choice(NI_FIRST_OK) + random.choice(NI_SECOND_OK)
        return f"{prefix}{random.randint(100000, 999999)}{random.choice('ABCD')}"
    # malformed: wrong length, lowercase, or bad suffix letter
    bad_type = random.choice(['short', 'bad_suffix', 'numeric_only'])
    if bad_type == 'short':
        return f"AB{random.randint(1000, 9999)}C"
    if bad_type == 'bad_suffix':
        return f"AB{random.randint(100000, 999999)}Z"
    return str(random.randint(10000000, 99999999))


def _fmt_sort_code() -> str:
    return f"{random.randint(10,99)}-{random.randint(10,99)}-{random.randint(10,99)}"


def _fmt_account() -> str:
    return str(random.randint(10000000, 99999999))


def _fmt_postcode(valid=True) -> str:
    if valid:
        return fake.postcode()
    return random.choice(['N/A', '00000', 'UNKNOWN', str(random.randint(1000, 9999))])


# ──────────────────────────────────────────────────────────────────────────────
# Employee master
# ──────────────────────────────────────────────────────────────────────────────

employees = []
manager_pool = []  # employee_ids eligible to be a manager (grade MGR1/MGR2/EXEC)

for i in range(1, N_EMPLOYEES + 1):
    emp_id = f"RM{100000 + i}"
    bu = _weighted_choice(BUSINESS_UNITS)
    dept = random.choice(DEPARTMENTS[bu])
    is_ops = dept in ('Delivery Office', 'Mail Centre', 'Distribution Hub', 'Depot Operations', 'Hub Sortation', 'Fleet & Logistics')
    grade = random.choice(GRADES_OPS) if is_ops and random.random() < 0.85 else random.choice(GRADES_MGMT + GRADES_OTHER)

    start_date = _rand_date(date(2005, 1, 1), TODAY - timedelta(days=30))
    is_leaver = random.random() < 0.13
    leaving_date = _rand_date(start_date + timedelta(days=90), TODAY) if is_leaver else None
    status = 'Leaver' if is_leaver else 'Active'

    dob = _rand_date(date(1958, 1, 1), date(2007, 1, 1))

    gender = random.choice(['Male', 'Female'])
    first = fake.first_name_male() if gender == 'Male' else fake.first_name_female()
    last = fake.last_name()

    union_weights = UNION_OPS if is_ops else UNION_NONOPS
    union = _weighted_choice(union_weights)

    contract = _weighted_choice(CONTRACT_TYPES)
    basis = _weighted_choice(BASIS)
    contracted_hours = round(random.uniform(16, 30), 1) if basis == 'Part-Time' else 37.5

    row = {
        'employee_id': emp_id,
        'first_name': first,
        'last_name': last,
        'dob': dob,
        'gender': gender,
        'ni_number': _fmt_ni(valid=True),
        'start_date': start_date,
        'leaving_date': leaving_date,
        'employment_status': status,
        'business_unit': bu,
        'department': dept,
        'job_title': f"{grade} — {dept}",
        'site': random.choice(SITES),
        'region': random.choice(REGIONS),
        'contract_type': contract,
        'employment_basis': basis,
        'contracted_hours': contracted_hours,
        'grade': grade,
        'union_member': union,
        'manager_id': None,  # filled in second pass
        'email': f"{first.lower()}.{last.lower()}@royalmailgroup.example",
        'phone': fake.phone_number(),
        'address_line1': fake.street_address(),
        'town': fake.city(),
        'postcode': _fmt_postcode(valid=True),
        'bank_account': _fmt_account(),
        'sort_code': _fmt_sort_code(),
        'tax_code': random.choice(['1257L', '1257L', '1257L', 'BR', 'S1257L', '0T']),
        'ni_category': random.choice(['A', 'A', 'A', 'B', 'C', 'J']),
        'pension_scheme': random.choice(PENSION_SCHEMES),
    }
    employees.append(row)
    if grade in ('MGR1', 'MGR2', 'EXEC') and status == 'Active':
        manager_pool.append(emp_id)

# Assign managers (root/senior nodes stay blank)
for row in employees:
    if row['grade'] in ('MGR2', 'EXEC') or random.random() < 0.04:
        continue  # senior leadership — no manager
    candidates = [m for m in manager_pool if m != row['employee_id']]
    if candidates:
        row['manager_id'] = random.choice(candidates)

df_emp = pd.DataFrame(employees)

# ── Inject data quality issues ───────────────────────────────────────────────

n = len(df_emp)
active_idx = df_emp[df_emp['employment_status'] == 'Active'].index.tolist()


def _sample(idx_pool, frac):
    k = max(1, int(len(idx_pool) * frac))
    return random.sample(idx_pool, min(k, len(idx_pool)))


# Missing NI number (~3% of active)
for idx in _sample(active_idx, 0.03):
    df_emp.at[idx, 'ni_number'] = None

# Malformed NI number (~2.5% of active)
remaining_active = [i for i in active_idx if pd.notna(df_emp.at[i, 'ni_number'])]
for idx in _sample(remaining_active, 0.025):
    df_emp.at[idx, 'ni_number'] = _fmt_ni(valid=False)

# Duplicate NI numbers — force a handful of pairs (~1%)
dup_candidates = _sample(active_idx, 0.01)
for idx in dup_candidates:
    if idx + 1 < n:
        df_emp.at[idx + 1, 'ni_number'] = df_emp.at[idx, 'ni_number']

# Duplicate employee_id — force a few exact-duplicate rows (~0.5%)
for idx in _sample(list(range(n)), 0.005):
    dup_row = df_emp.loc[idx].copy()
    df_emp.loc[len(df_emp)] = dup_row  # employee_id collides with an existing row

# Missing bank details (~2.5% of active)
for idx in _sample(active_idx, 0.015):
    df_emp.at[idx, 'bank_account'] = None
for idx in _sample(active_idx, 0.01):
    df_emp.at[idx, 'sort_code'] = None

# Missing DOB (~2%)
for idx in _sample(active_idx, 0.02):
    df_emp.at[idx, 'dob'] = None

# Invalid DOB — implies age <16 or >75 (~1%)
for idx in _sample(active_idx, 0.006):
    df_emp.at[idx, 'dob'] = TODAY - timedelta(days=random.randint(3000, 5000))  # ~8-13 yrs old
for idx in _sample(active_idx, 0.006):
    df_emp.at[idx, 'dob'] = TODAY - timedelta(days=random.randint(29500, 32000))  # ~80-87 yrs old

# start_date after leaving_date (~1% of leavers)
leaver_idx = df_emp[df_emp['employment_status'] == 'Leaver'].index.tolist()
for idx in _sample(leaver_idx, 0.08):
    lv = df_emp.at[idx, 'leaving_date']
    if pd.notna(lv):
        df_emp.at[idx, 'start_date'] = lv + timedelta(days=random.randint(10, 200))

# Orphaned manager_id — points to a non-existent employee (~2%)
for idx in _sample(active_idx, 0.02):
    df_emp.at[idx, 'manager_id'] = f"RM{999000 + random.randint(1, 900)}"

# Missing email (~4%)
for idx in _sample(active_idx, 0.04):
    df_emp.at[idx, 'email'] = None

# Malformed postcode (~3%)
for idx in _sample(active_idx, 0.03):
    df_emp.at[idx, 'postcode'] = _fmt_postcode(valid=False)

# Missing tax_code (~2%)
for idx in _sample(active_idx, 0.02):
    df_emp.at[idx, 'tax_code'] = None

df_emp = df_emp.sample(frac=1, random_state=7).reset_index(drop=True)  # shuffle
df_emp.to_csv(os.path.join(OUTPUT_DIR, 'employee_master.csv'), index=False)


# ──────────────────────────────────────────────────────────────────────────────
# Payroll transactions
# ──────────────────────────────────────────────────────────────────────────────

active_employees = df_emp[df_emp['employment_status'] == 'Active'].drop_duplicates(subset=['employee_id'])
N_WEEKS = 12
week_starts = [TODAY - timedelta(weeks=w) for w in range(N_WEEKS, 0, -1)]

payroll_rows = []
pid = 1
for _, emp in active_employees.iterrows():
    basic_weekly = round(random.uniform(380, 950), 2) if emp['employment_basis'] == 'Full-Time' else round(random.uniform(180, 420), 2)
    pension_pct = 0.0 if emp['pension_scheme'] == 'None' else round(random.choice([3.0, 5.0, 6.0]), 1)

    for wk_start in week_starts:
        overtime_hours = round(random.uniform(0, 8), 1) if random.random() < 0.35 else 0.0
        overtime_pay = round(overtime_hours * (basic_weekly / 37.5) * 1.5, 2) if overtime_hours > 0 else 0.0
        shift_allowance = round(random.uniform(10, 45), 2) if random.random() < 0.4 else 0.0
        bonus = round(random.uniform(20, 150), 2) if random.random() < 0.05 else 0.0

        gross = round(basic_weekly + overtime_pay + shift_allowance + bonus, 2)
        tax = round(gross * random.uniform(0.10, 0.18), 2)
        ni = round(gross * random.uniform(0.06, 0.09), 2)
        pension = round(gross * pension_pct / 100, 2)
        other_ded = round(random.uniform(0, 8), 2) if random.random() < 0.15 else 0.0
        net = round(gross - tax - ni - pension - other_ded, 2)

        payroll_rows.append({
            'payroll_id': f"PR{200000 + pid}",
            'employee_id': emp['employee_id'],
            'pay_period': f"{wk_start.isocalendar()[0]}-W{wk_start.isocalendar()[1]:02d}",
            'pay_date': wk_start + timedelta(days=4),
            'basic_pay': basic_weekly,
            'overtime_hours': overtime_hours,
            'overtime_pay': overtime_pay,
            'shift_allowance': shift_allowance,
            'bonus': bonus,
            'gross_pay': gross,
            'tax_deducted': tax,
            'ni_deducted': ni,
            'pension_deducted': pension,
            'other_deductions': other_ded,
            'net_pay': net,
            'tax_code': emp['tax_code'],
            'ni_category': emp['ni_category'],
            'payment_method': 'BACS',
            'bank_account': emp['bank_account'],
            'sort_code': emp['sort_code'],
            'pension_scheme': emp['pension_scheme'],
            'pension_contribution_pct': pension_pct,
            'status': 'Processed',
        })
        pid += 1

df_pay = pd.DataFrame(payroll_rows)
m = len(df_pay)


def _psample(frac):
    k = max(1, int(m * frac))
    return random.sample(range(m), k)


# net_pay > gross_pay (~0.5%)
for idx in _psample(0.005):
    df_pay.at[idx, 'net_pay'] = df_pay.at[idx, 'gross_pay'] + round(random.uniform(5, 50), 2)

# negative gross_pay (~0.2%)
for idx in _psample(0.002):
    df_pay.at[idx, 'gross_pay'] = -abs(df_pay.at[idx, 'gross_pay'])

# missing tax_code (~1.5%)
for idx in _psample(0.015):
    df_pay.at[idx, 'tax_code'] = None

# missing ni_category (~1.5%)
for idx in _psample(0.015):
    df_pay.at[idx, 'ni_category'] = None

# orphaned employee_id — references an employee not in the master (~1%)
for idx in _psample(0.01):
    df_pay.at[idx, 'employee_id'] = f"RM{998000 + random.randint(1, 900)}"

# duplicate (employee_id, pay_period) — double-processed transactions (~0.8%)
dup_src = _psample(0.008)
for idx in dup_src:
    dup_row = df_pay.loc[idx].copy()
    dup_row['payroll_id'] = f"PR{300000 + idx}"
    df_pay.loc[len(df_pay)] = dup_row

# overtime_pay > 0 but overtime_hours recorded as 0 (~1%)
ot_idx = df_pay[df_pay['overtime_pay'] > 0].index.tolist()
for idx in random.sample(ot_idx, min(int(m * 0.01), len(ot_idx))):
    df_pay.at[idx, 'overtime_hours'] = 0.0

# gross/net calculation mismatch beyond tolerance (~1%)
for idx in _psample(0.01):
    df_pay.at[idx, 'net_pay'] = round(df_pay.at[idx, 'net_pay'] + random.choice([-1, 1]) * random.uniform(5, 30), 2)

# bank details mismatch vs employee master (~1.2%)
for idx in _psample(0.012):
    df_pay.at[idx, 'bank_account'] = _fmt_account()
    df_pay.at[idx, 'sort_code'] = _fmt_sort_code()

# zero/negative net while gross is positive (~0.5%)
for idx in _psample(0.005):
    if df_pay.at[idx, 'gross_pay'] > 0:
        df_pay.at[idx, 'net_pay'] = round(random.uniform(-10, 0), 2)

# stale pending transactions — status Pending, pay_date >7 days ago (~1%)
old_idx = df_pay[df_pay['pay_date'] < (TODAY - timedelta(days=8))].index.tolist()
for idx in random.sample(old_idx, min(int(m * 0.01), len(old_idx))):
    df_pay.at[idx, 'status'] = 'Pending'

# a few genuinely still-pending recent transactions (not a DQ issue — normal in-flight state)
recent_idx = df_pay[df_pay['pay_date'] >= (TODAY - timedelta(days=8))].index.tolist()
for idx in random.sample(recent_idx, min(int(m * 0.01), len(recent_idx))):
    df_pay.at[idx, 'status'] = 'Pending'

# future pay_date (~0.3%)
for idx in _psample(0.003):
    df_pay.at[idx, 'pay_date'] = TODAY + timedelta(days=random.randint(3, 30))

df_pay = df_pay.sample(frac=1, random_state=7).reset_index(drop=True)  # shuffle
df_pay.to_csv(os.path.join(OUTPUT_DIR, 'payroll_transactions.csv'), index=False)

print(f"Employee master:       {len(df_emp):,} rows -> {os.path.join(OUTPUT_DIR, 'employee_master.csv')}")
print(f"Payroll transactions:  {len(df_pay):,} rows -> {os.path.join(OUTPUT_DIR, 'payroll_transactions.csv')}")
