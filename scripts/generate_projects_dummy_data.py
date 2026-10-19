"""
Dummy data for the Projects tab (Seq 22).

Writes two files to data/projects/, with exactly the headers of the real
exports so the loader is exercised the same way it will be on the Parliament
laptop:

  project_list.csv        Krishna's list: one row per HAIS code, with the
                          Department > Directorate > Cost Centre > Unit > HAIS
                          hierarchy and the Projcat / Projgrp classification.
  project_financials.csv  Ben's raw data dump: one row per account x HAIS code
                          x house (Recharge) x period, with Committed purchase,
                          Actuals, Current Budget and Current Forecast.
                          Amounts are comma-formatted, as Excel saves them.

Conventions copied from the real files:
  - Year is the start year of the financial year (2020 = FY2020/21).
  - Period is YYYYPP (202012 = FY2020/21 period 12).
  - A shared HAIS code has one row per house with the amount already split.
  - Committed purchase sits mostly on its own rows, against the PO's period.

One planted case per PRJ_* check is listed when the script finishes. The real
headers are kept exactly, so there is no _edge_case column.
"""
import os
import random

import numpy as np
import pandas as pd

random.seed(22)
np.random.seed(22)

OUT_DIR = os.path.join('data', 'projects')
FIRST_FY, CURRENT_FY, CURRENT_PERIOD = 2020, 2026, 7   # data as at FY2026/27 P7

DEPARTMENTS = {
    'BCS': ('Chamber and Participation', {
        'BSJAA': ('Serjeant at Arms', ['CBS', 'CBV']),
        'BOFRD': ('Broadcasting', ['BFE']),
    }),
    'CPD': ('Strategic Estates', {
        'INCEN': ('Central Services', ['CCE']),
        'RRINT': ('Restoration and Renewal Integration', ['CPN', 'CPS']),
        'SEFIN': ('IHSE Finance', ['CPE']),
    }),
    'PDS': ('Parliamentary Digital Service', {
        'PDINF': ('Digital Infrastructure', ['DIN', 'DNW']),
        'PDAPP': ('Digital Applications', ['DAP']),
    }),
    'CRS': ('Corporate Services', {
        'CSFIN': ('Finance', ['FIN']),
        'CSPPL': ('People', ['HRS']),
    }),
}
COSTC_NAMES = {
    'CBS': 'Access and Services Team', 'CBV': 'Visitor Services', 'BFE': 'Broadcasting Engineering',
    'CCE': 'Central Services', 'CPN': 'R&R Interface', 'CPS': 'R&R Enabling Works',
    'CPE': 'Estates Management', 'DIN': 'Infrastructure Services', 'DNW': 'Network Services',
    'DAP': 'Business Applications', 'FIN': 'Finance Operations', 'HRS': 'HR Services',
}

PROJCATS = {
    'F-MAJP': 'CAT A Project',
    'F-MINP': 'CAT B Project',
    'F-MNSP': 'Other Project',
    'F-ANRP': 'Annual Requirements',
}
# Two Projgrp code schemes are in use on the real list (F-W and F017 are both
# "Staff", F-O and F012 both "Other Projects"), so the dummy list uses both.
PROJGRPS = {
    'F-W': 'Staff', 'F017': 'Staff', 'F-O': 'Other Projects', 'F012': 'Other Projects',
    'F-V': 'Property', 'F-U': 'Annual', 'F-J': 'Accommodation', 'F-D': 'Digital',
}

# Mipck-l1, Mipck-l1(T), Mipck-l2, Mipck-l2(T), Mipck-l3, [(account, account description)]
COST_TYPES = {
    'capital': ('CX01', 'CAPITAL EXPENDITURE', 'CEXP', 'Capital Expenditure', 'CEX',
                [('10000', 'Software licences'), ('10500', 'Building works'), ('11000', 'IT hardware')]),
    'pay':     ('SAL', 'SALARIES & WAGES', 'SAL01', 'Pay', 'Pay and NIC',
                [('31100', 'Basic pay'), ('31200', 'Employer NIC')]),
    'goods':   ('GS01', 'GOODS AND SERVICES', 'GSRV', 'Goods and Services', 'GSV',
                [('41000', 'Consultancy'), ('42000', 'Office supplies'), ('43000', 'Training and development'),
                 ('44000', 'Maintenance')]),
    'income':  ('IN01', 'INCOME', 'INCR', 'Income and Recharges', 'INC',
                [('81000', 'Recharge income'), ('82000', 'Sales income')]),
}
CAPITAL_BUDGET_ACCOUNT = ('19900', 'Capital budget control')   # budget held off the spend accounts


def _periods(fy):
    last = CURRENT_PERIOD if fy == CURRENT_FY else 12
    return [fy * 100 + p for p in range(1, last + 1)]


def _money(v):
    return f'{v:,.2f}'


def build_list():
    """Units and HAIS codes. Returns (list rows, unit meta)."""
    rows, units = [], []
    unit_no = 1000
    plan = ['F-MAJP'] * 8 + ['F-MINP'] * 14 + ['F-MNSP'] * 12 + ['F-ANRP'] * 30
    random.shuffle(plan)
    names = {
        'F-MAJP': ['Enhanced Maintenance Improvements', 'Shadow Sponsor Body', 'Northern Estate Programme',
                   'Elizabeth Tower Conservation', 'Digital Platform Replacement', 'Fire Safety Programme',
                   'Cloisters Restoration', 'Network Modernisation'],
        'F-MINP': ['Increase Desk Capacity - 14TS', 'Gatekeeper Move', 'CTA Switches Upgrade', 'Committee Room AV',
                   'Visitor Wi-Fi', 'Lift Replacement - PCH', 'Cyber Tooling', 'Kitchen Refit',
                   'Archive Digitisation', 'Telephony Migration', 'Courtyard Paving', 'Data Centre Cooling',
                   'Print Room Refit', 'Library Shelving'],
        'F-MNSP': ['R&R Recharges', 'IDD 004 Hosting Trueview Models', 'IDD 001 Sharing Hazards Data',
                   'Heritage Survey', 'Accessibility Audit', 'Sustainability Pilot', 'Security Review',
                   'Space Utilisation Study', 'Records Retention', 'Signage Refresh', 'Wellbeing Programme',
                   'Asbestos Survey'],
        'F-ANRP': ['Access and Services', 'IHSE Central', 'Estates Management', 'Property Costs - 1 Canon Row',
                   'Property Costs - 7 Millbank', 'Property Costs - Portcullis House', 'Broadcasting Operations',
                   'Finance Operations', 'HR Services', 'Network Services', 'Application Support',
                   'Visitor Services', 'Collections Care', 'Catering Support', 'Cleaning Services',
                   'Postal Services', 'Learning and Development', 'Payroll Services', 'Procurement Services',
                   'Health and Safety', 'Energy Costs', 'Waste Management', 'Furniture', 'Stationery',
                   'Travel and Subsistence', 'Recruitment', 'Insurance', 'Licences and Subscriptions',
                   'Telecoms', 'Security Operations'],
    }
    used = {k: 0 for k in names}
    costcs = [(d, dd, dir_, ddesc, cc) for d, (dd, dirs) in DEPARTMENTS.items()
              for dir_, (ddesc, ccs) in dirs.items() for cc in ccs]

    for projcat in plan:
        name = names[projcat][used[projcat]]
        used[projcat] += 1
        d, dd, dir_, ddesc, cc = random.choice(costcs)
        if projcat == 'F-ANRP':
            projgrp = random.choice(['F-W', 'F017', 'F-V', 'F-U'])
        elif projcat == 'F-MNSP':
            projgrp = random.choice(['F-O', 'F012'])
        else:
            projgrp = random.choice(['F-O', 'F-J', 'F-D', 'F-V'])
        letter = {'CPD': 'C', 'BCS': 'B', 'PDS': 'D', 'CRS': 'A'}[d]
        unit = f'{letter}{unit_no}'
        unit_no += random.randint(3, 40)
        n_codes = random.randint(1, 3) if projcat == 'F-ANRP' else random.randint(2, 6)
        if projcat == 'F-ANRP':
            start = FIRST_FY - random.randint(1, 8)          # running costs pre-date the extract
        else:
            start = random.randint(FIRST_FY - 2, CURRENT_FY - 1)
        end = None if random.random() < 0.7 else random.randint(max(start, FIRST_FY), CURRENT_FY)
        meta = dict(unit=unit, unit_desc=name, projcat=projcat, projgrp=projgrp, department=d, department_desc=dd,
                    directorate=dir_, directorate_desc=ddesc, costc=cc, start=start, end=end, codes=[])
        for i in range(n_codes):
            code = f'{unit}{100 + i}'
            suffix = ['', ' Staff Costs', ' Consultancy', ' Works', ' HOL', ' HOC', ' Shared 70/30'][min(i, 6)]
            meta['codes'].append(code)
            rows.append(dict(meta, hais_code=code, hais_desc=f'{name}{suffix}', status='N'))
        units.append(meta)
    return rows, units


def plant_list_cases(rows, units):
    planted = {}
    # PRJ_LIST_DUP_HAIS: the same HAIS code listed twice
    rows.append(dict(rows[5]))
    planted['PRJ_LIST_DUP_HAIS'] = rows[5]['hais_code']
    # PRJ_LIST_MISSING_CLASS: no Projgrp
    rows[8] = dict(rows[8], projgrp='')
    planted['PRJ_LIST_MISSING_CLASS'] = rows[8]['hais_code']
    # PRJ_LIST_HAIS_UNIT_PREFIX: HAIS code that doesn't sit under its Unit's prefix
    rows.append(dict(rows[12], hais_code='X9999100', hais_desc='Misfiled cost line'))
    planted['PRJ_LIST_HAIS_UNIT_PREFIX'] = 'X9999100'
    # PRJ_LIST_DO_NOT_USE_ACTIVE: retired codes still active
    for i in (15, 16):
        rows[i] = dict(rows[i], hais_desc=f"DO NOT USE - {rows[i]['hais_desc']}")
    planted['PRJ_LIST_DO_NOT_USE_ACTIVE'] = f"{rows[15]['hais_code']}, {rows[16]['hais_code']}"
    # PRJ_LIST_DUP_DESC: a cloned Unit re-using the same cost line description
    src = next(u for u in units if u['projcat'] == 'F-MNSP')
    clone_unit = 'C7780'
    rows.append(dict(rows[[r['unit'] for r in rows].index(src['unit'])],
                     unit=clone_unit, unit_desc=f"DO NOT USE - {src['unit_desc']}",
                     hais_code=f'{clone_unit}100', projgrp='F012'))
    planted['PRJ_LIST_DUP_DESC'] = f"{src['codes'][0]} / {clone_unit}100"
    # PRJ_UNIT_MULTI_CLASS: one Unit whose cost lines disagree on Projcat
    multi = next(u for u in units if u['projcat'] == 'F-MINP' and len(u['codes']) >= 2)
    for r in rows:
        if r['hais_code'] == multi['codes'][-1]:
            r['projcat'] = 'F-MAJP'
    planted['PRJ_UNIT_MULTI_CLASS'] = multi['unit']
    # PRJ_NO_ACTIVITY: listed codes with nothing in the financials
    idle = [u for u in units if u['projcat'] != 'F-ANRP'][-3:]
    for u in idle:
        u['idle'] = True
    planted['PRJ_NO_ACTIVITY'] = ', '.join(u['unit'] for u in idle)
    return planted


def build_financials(units, planted):
    rows = []

    def add(u, code, house, cost_key, fy, period, actual=0.0, budget=0.0, committed=0.0, costc=None, acct=None):
        m1, m1d, m2, m2d, m3, accts = COST_TYPES[cost_key]
        a, ad = acct or random.choice(accts)
        forecast = actual if (fy < CURRENT_FY or period % 100 <= CURRENT_PERIOD) else budget
        rows.append({
            'Mipck-l1': m1, 'Mipck-l1(T)': m1d, 'Mipck-l2': m2, 'Mipck-l2(T)': m2d, 'Mipck-l3': m3,
            'Account': a, 'Account(T)': ad, 'Department': u['department'], 'Directorate': u['directorate'],
            'Costc': costc or u['costc'], 'Unit': u['unit'], 'Haiscode': code,
            'Haiscode(T)': u['hais_desc_map'].get(code, u['unit_desc']), 'Recharge': house,
            'Year': fy, 'Period': period, 'Committed purchase': committed, 'Actuals': actual,
            'Current Budget': budget, 'Current Forecast': forecast,
        })

    split_case = None
    for u in units:
        if u.get('idle'):
            continue
        is_project = u['projcat'] != 'F-ANRP'
        first = max(u['start'], FIRST_FY)
        last = u['end'] or CURRENT_FY
        cost_keys = (['capital', 'goods', 'pay'] if is_project else ['pay', 'goods'])
        if u['projgrp'] in ('F-W', 'F017'):
            cost_keys = ['pay']
        for code in u['codes']:
            r = random.random()
            houses = {'HOC': 1.0} if r < 0.45 else ({'HOL': 1.0} if r < 0.6 else
                      random.choice([{'HOC': 0.6, 'HOL': 0.4}, {'HOC': 0.7, 'HOL': 0.3}]))
            if split_case is None and len(houses) == 2 and last - first >= 3:
                split_case = (u['unit'], code)
            scale = random.uniform(2_000, 40_000) * (4 if u['projcat'] == 'F-MAJP' else 1)
            for fy in range(first, last + 1):
                fy_budget = scale * random.uniform(9, 14) * (1.0 if is_project else 1.05)
                for period in _periods(fy):
                    if random.random() > (0.75 if is_project else 0.9):
                        continue
                    base = scale * random.uniform(0.3, 1.6)
                    key = random.choice(cost_keys)
                    for house, share in houses.items():
                        if split_case == (u['unit'], code) and fy >= first + 2:
                            share = 0.5                                    # PRJ_SPLIT_INCONSISTENT
                        add(u, code, house, key, fy, period, actual=round(base * share, 2))
                # Budget: spread over the year. Capital budget sits on a control
                # account on the first cost line only, as happens on real data
                # (capital lines show 0 budget against the spend accounts).
                for house, share in houses.items():
                    if is_project and 'capital' in cost_keys:
                        if code == u['codes'][0]:
                            add(u, code, house, 'capital', fy, fy * 100 + 1,
                                budget=round(fy_budget * len(u['codes']) * share, 2), acct=CAPITAL_BUDGET_ACCOUNT)
                    else:
                        add(u, code, house, cost_keys[0], fy, fy * 100 + 1, budget=round(fy_budget * share, 2))
            # Open commitments: mostly recent, a few stale, a few residual pennies
            if is_project and last == CURRENT_FY:
                for _ in range(random.randint(1, 4)):
                    fy = random.choice([CURRENT_FY, CURRENT_FY, CURRENT_FY - 1])
                    period = random.choice(_periods(fy))
                    house = random.choice(list(houses))
                    add(u, code, house, random.choice(cost_keys), fy, period,
                        committed=round(scale * random.uniform(0.5, 6), 2))
    planted['PRJ_SPLIT_INCONSISTENT'] = split_case[1] if split_case else '(none)'

    proj = [u for u in units if u['projcat'] != 'F-ANRP' and not u.get('idle')]
    # PRJ_STALE_COMMITMENT: POs from FY2022/23 still showing money outstanding
    for u in proj[:2]:
        add(u, u['codes'][0], 'HOC', 'goods', 2022, 202211, committed=80_139.60)
    planted['PRJ_STALE_COMMITMENT'] = ', '.join(u['codes'][0] for u in proj[:2]) + ' (plus random ones)'
    # PRJ_RESIDUAL_COMMITMENT: pennies left on finished POs
    add(proj[2], proj[2]['codes'][0], 'HOC', 'goods', 2024, 202410, committed=0.03)
    add(proj[3], proj[3]['codes'][0], 'HOC', 'goods', 2024, 202412, committed=3.00)
    planted['PRJ_RESIDUAL_COMMITMENT'] = f"{proj[2]['codes'][0]}, {proj[3]['codes'][0]}"
    # PRJ_NEG_COMMITMENT
    add(proj[4], proj[4]['codes'][0], 'HOC', 'goods', CURRENT_FY, 202605, committed=-1_250.00)
    planted['PRJ_NEG_COMMITMENT'] = proj[4]['codes'][0]
    # PRJ_ATTR_MISMATCH: financials post a cost line under a different cost centre
    for row in rows:
        if row['Haiscode'] == proj[5]['codes'][0]:
            row['Costc'] = 'ZZZ'
    planted['PRJ_ATTR_MISMATCH'] = proj[5]['codes'][0]
    # PRJ_OVERSPEND: big spend against the budget in one year
    u = proj[6]
    # Spend in a house that holds budget for the Unit (budget may sit on one house only)
    bud_house = next((r['Recharge'] for r in rows if r['Unit'] == u['unit'] and r['Current Budget']), 'HOC')
    for p in _periods(CURRENT_FY - 1):
        add(u, u['codes'][0], bud_house, 'goods', CURRENT_FY - 1, p, actual=250_000.00)
    for row in rows:                          # and a budget far too small to cover it
        if row['Unit'] == u['unit'] and row['Recharge'] == bud_house:
            row['Current Budget'] = round(row['Current Budget'] * 0.1, 2)
    planted['PRJ_OVERSPEND'] = u['unit']
    # PRJ_NO_BUDGET: current-year spend on a Unit with no budget lines at all this year
    u = proj[7]
    rows[:] = [r for r in rows if not (r['Unit'] == u['unit'] and r['Year'] == CURRENT_FY and r['Current Budget'])]
    add(u, u['codes'][0], 'HOC', 'goods', CURRENT_FY, 202603, actual=12_500.00)
    planted['PRJ_NO_BUDGET'] = u['unit']
    # PRJ_NEG_SPEND_TO_DATE: a Unit that only ever recharges income
    u = proj[8]
    rows[:] = [r for r in rows if r['Unit'] != u['unit']]
    for p in _periods(CURRENT_FY - 1):
        add(u, u['codes'][0], 'HOL', 'income', CURRENT_FY - 1, p, actual=-8_000.00)
    planted['PRJ_NEG_SPEND_TO_DATE'] = u['unit']
    planted['PRJ_HISTORY_TRUNCATED'] = 'every Annual Requirements Unit (they pre-date April 2020)'
    planted['PRJ_LIST_PROJGRP_DUP_DESC'] = 'F-W / F017 and F-O / F012'

    # Business-as-usual HAIS codes that aren't on the project list at all
    bau = dict(unit='Z0001', unit_desc='Unlisted running costs', department='CRS', directorate='CSFIN',
               costc='FIN', hais_desc_map={})
    for i in range(25):
        code = f'Z{1000 + i}100'
        bau['hais_desc_map'][code] = f'Unlisted cost line {i + 1}'
        bau['unit'] = f'Z{1000 + i}'
        for fy in range(FIRST_FY, CURRENT_FY + 1):
            for period in random.sample(_periods(fy), k=min(4, len(_periods(fy)))):
                add(bau, code, random.choice(['HOC', 'HOL']), 'goods', fy, period,
                    actual=round(random.uniform(200, 9_000), 2))
    return rows


def main():
    list_rows, units = build_list()
    planted = plant_list_cases(list_rows, units)
    for u in units:
        u['hais_desc_map'] = {r['hais_code']: r['hais_desc'] for r in list_rows if r['unit'] == u['unit']}
    fin_rows = build_financials(units, planted)

    lst = pd.DataFrame([{
        'Department': r['department'], 'Department(T)': r['department_desc'],
        'Directorate': r['directorate'], 'Directorate(T)': r['directorate_desc'],
        'Cost Centre': r['costc'], 'Cost Centre(T)': COSTC_NAMES[r['costc']],
        'Projcat': r['projcat'], 'Projcat(T)': PROJCATS[r['projcat']],
        'Projgrp': r['projgrp'], 'Projgrp(T)': PROJGRPS.get(r['projgrp'], ''),
        'Unit': r['unit'], 'Unit(T)': r['unit_desc'],
        'HAIS Code': r['hais_code'], 'HAIS Code(T)': r['hais_desc'], 'S': r['status'],
    } for r in list_rows])

    fin = pd.DataFrame(fin_rows).sort_values(['Mipck-l1', 'Account', 'Haiscode', 'Recharge', 'Period'])
    for col in ('Committed purchase', 'Actuals', 'Current Budget', 'Current Forecast'):
        fin[col] = fin[col].map(_money)

    os.makedirs(OUT_DIR, exist_ok=True)
    lst.to_csv(os.path.join(OUT_DIR, 'project_list.csv'), index=False)
    fin.to_csv(os.path.join(OUT_DIR, 'project_financials.csv'), index=False)

    print(f'project_list.csv:       {len(lst):,} HAIS codes across {lst["Unit"].nunique()} Units')
    print(f'project_financials.csv: {len(fin):,} rows, FY{FIRST_FY}/{str(FIRST_FY + 1)[2:]} to '
          f'FY{CURRENT_FY}/{str(CURRENT_FY + 1)[2:]} P{CURRENT_PERIOD}')
    print('\nPlanted cases:')
    for check_id, where in sorted(planted.items()):
        print(f'  {check_id:28s} {where}')


if __name__ == '__main__':
    main()
