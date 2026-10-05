"""Traces DQ-AD-K01 (active depreciation book with date_to populated) step by step.

Read-only. Run from the repo root on the Parliament laptop:
    python scripts/diagnose_date_to.py

Shows, for every CA row with status N and a date_to that isn't blank or 1:
the raw values exactly as they sit in the CSV, what the dashboard turns them
into, and whether the check flags the row. Whichever step loses the row is
the bug.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dashboard.data_engine import load_data, _parse_dates  # noqa: E402
from dashboard.core.rules.asset_rules import get_asset_checks  # noqa: E402

PATH = os.path.join('data', 'assets', 'asset_depreciation_HOC.csv')

raw = pd.read_csv(PATH, dtype=str, keep_default_na=False)
print(f'Raw file: {len(raw):,} rows')
print('Distinct raw client values:', sorted({repr(v) for v in raw['client'].unique()}))
print('Distinct raw status values:', sorted({repr(v) for v in raw['status'].unique()}))

dt = raw['date_to'].str.strip()
cand = raw[(raw['client'].str.strip() == 'CA') & (raw['status'].str.strip() == 'N')
           & ~dt.isin(['', '1', 'NULL', 'nan'])]
print(f'\nStep 1 - raw CSV rows with client CA, status N, date_to not blank/1: {len(cand)}')
print(cand[['client', 'asset_id', 'depr_book_id', 'status', 'date_to']].map(repr).to_string())

print('\nStep 2 - how the date parser reads those date_to values:')
print(pd.DataFrame({'raw': cand['date_to'].map(repr),
                    'parsed': _parse_dates(cand['date_to']).astype(str)}).to_string())
print('Sample of other date_to values in the file:', sorted({repr(v) for v in dt.unique()})[:15])

frames = load_data(tab='assets')
ad = frames['asset_depreciation']
ids = set(cand['asset_id'].str.strip())
loaded = ad[ad['asset_id'].isin(ids)]
print(f'\nStep 3 - same assets after the dashboard loads them: {len(loaded)} rows')
print(loaded[['house', 'client', 'asset_id', 'depr_book_id', 'status', 'date_to']].map(repr).to_string())

check = next(c for c in get_asset_checks() if c[0] == 'DQ-AD-K01')
hoc = ad[ad['house'] == 'HOC']
flag = check[11](hoc)
print(f'\nStep 4 - DQ-AD-K01 on the loaded HoC data: {int(flag.sum())} flagged of {len(hoc):,}')
print('Of the step 1 assets, flagged:', sorted(hoc.loc[flag & hoc['asset_id'].isin(ids), 'asset_id']))
