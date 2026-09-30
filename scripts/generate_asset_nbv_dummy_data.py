"""
Reshapes the HoC asset dummy data to match the account-level asset_balances
extract confirmed against real data in September 2026, so the NBV section of
the Assets tab has something realistic to show.

Run after generate_asset_data.py (which calls this at the end of main()).

What it does to the HoC files only:
  - depreciation books FINBOOK/TAXBOOK become CURR/HIST, and every asset gets
    both books (edge-case depreciation rows keep a single CURR book)
  - dummy method codes map to the real ones (LNA/LNB/MAN), buildings use NOD
  - each balance row is split into account-level postings with contra entries,
    so each asset's accounts net to zero, as they do in real data:
        cost 1G000 / control 1G005, accumulated depreciation 1G015 / P&L 57000,
        revaluation: cost 1G000 / reserve 70000 (CURR book only),
        disposal clears cost and depreciation against 48000
  - ~40% of buildings are made into legacy assets migrated through OS, with
    later revaluations, like 1 Parliament Street in the real data
  - one planted asset per DQ-NBV-* check
"""
import os
import random

import pandas as pd

random.seed(7)

DATA_DIR = os.path.join('data', 'assets')
HOUSE = 'HOC'

GROUP_PREFIX = {'BLDG': '14', 'IT_EQ': '16', 'FURN': '17', 'VEH': '18', 'SOFT': '19'}
METHOD_MAP = {'LIN': 'LNA', 'SYD': 'LNA', 'BAL': 'LNB', 'EXP': 'MAN'}
PL_DEPRECIATION = '57000'
REVAL_RESERVE = '70000'
DISPOSAL = '48000'
BOOK_MAP = {'FINBOOK': 'CURR', 'TAXBOOK': 'HIST'}


def _path(name):
    return os.path.join(DATA_DIR, f'{name}_{HOUSE}.csv')


def _accounts(group):
    p = GROUP_PREFIX.get(group, '13')
    return {'cost': f'{p}000', 'control': f'{p}005', 'depr': f'{p}015'}


def _row(base, account, amount, trans_type=None, book=None):
    r = dict(base)
    r['account'] = account
    r['total_amount'] = round(amount, 2) if pd.notna(amount) else amount
    r['total_cur_amount'] = r['total_amount']
    if trans_type:
        r['trans_type'] = trans_type
    if book:
        r['depr_book_id'] = book
    return r


def _split_asset_book(rows, acc):
    """Account-level postings for one asset/book from the old one-row-per-trans_type rows."""
    out = []
    amt_all = rows['total_amount']
    # OS carries a legacy asset's whole opening position: positive = cost, negative = depreciation.
    is_cost = rows['trans_type'].isin(['CA', 'PC']) | ((rows['trans_type'] == 'OS') & (amt_all >= 0))
    is_depr = rows['trans_type'].isin(['ND', 'ED', 'FD']) | ((rows['trans_type'] == 'OS') & (amt_all < 0))
    cost = amt_all[is_cost].sum()
    depr = amt_all[is_depr].sum()
    for i, r in rows.iterrows():
        base = r.to_dict()
        t, amt = r['trans_type'], r['total_amount']
        if pd.isna(amt):
            out.append(_row(base, acc['cost'], amt))
        elif is_cost[i]:
            out += [_row(base, acc['cost'], amt), _row(base, acc['control'], -amt)]
        elif is_depr[i]:
            out += [_row(base, acc['depr'], amt), _row(base, PL_DEPRECIATION, -amt)]
        elif t == 'SA':
            out += [_row(base, acc['cost'], -cost), _row(base, acc['depr'], -depr),
                    _row(base, DISPOSAL, cost + depr)]
        else:
            out.append(_row(base, '99999', amt))
    return out


def reshape(master, depr, bal, flags):
    group = master.drop_duplicates('asset_id').set_index('asset_id')['asset_group'].to_dict()
    status = master.drop_duplicates('asset_id').set_index('asset_id')['status'].to_dict()

    # Depreciation books: CURR/HIST, real method codes, every clean asset has both.
    depr['depr_book_id'] = depr['depr_book_id'].replace(BOOK_MAP)
    clean = depr['_edge_case'].isna()
    depr.loc[clean, 'depr_method'] = depr.loc[clean, 'depr_method'].replace(METHOD_MAP)
    is_bldg = depr['asset_id'].map(group) == 'BLDG'
    depr.loc[clean & is_bldg, 'depr_method'] = 'NOD'
    depr = depr[~((depr['depr_book_id'] == 'HIST') & clean)].reset_index(drop=True)
    hist = depr[depr['_edge_case'].isna() & (depr['depr_book_id'] == 'CURR')].copy()
    hist['depr_book_id'] = 'HIST'
    depr = pd.concat([depr, hist], ignore_index=True)

    flags['depr_book_id'] = flags['depr_book_id'].replace(BOOK_MAP)

    # Balances: CURR from the old FINBOOK rows, HIST mirrors CURR for clean assets.
    bal['depr_book_id'] = bal['depr_book_id'].replace(BOOK_MAP)
    bal = bal[bal['depr_book_id'] != 'HIST']
    hist_assets = set(hist['asset_id'])
    edge_rows = bal[bal['_edge_case'].notna() | bal['asset_id'].isna()]
    clean_rows = bal.drop(edge_rows.index)

    out = []
    for (aid, book), rows in clean_rows.groupby(['asset_id', 'depr_book_id'], dropna=False):
        acc = _accounts(group.get(aid))
        rows = rows.copy()
        legacy = group.get(aid) == 'BLDG' and status.get(aid) == 'N' and random.random() < 0.4
        if legacy:
            rows.loc[rows['trans_type'] == 'CA', 'trans_type'] = 'OS'
            rows.loc[rows['trans_type'] == 'ND', 'trans_type'] = 'OS'
        if group.get(aid) == 'BLDG' and not legacy:
            rows = rows[rows['trans_type'] != 'ND']
        books = [book] + (['HIST'] if book == 'CURR' and aid in hist_assets else [])
        for b in books:
            posted = _split_asset_book(rows.assign(depr_book_id=b), acc)
            out += posted
            if b == 'CURR' and group.get(aid) == 'BLDG' and status.get(aid) == 'N' and random.random() < 0.6:
                base = dict(posted[0])
                uplift = round(random.uniform(0.2, 2.5) * abs(base['total_amount'] or 10000), 2)
                out += [_row(base, acc['cost'], uplift, 'VN'), _row(base, REVAL_RESERVE, -uplift, 'VN')]

    for (aid, _), rows in edge_rows.groupby(['asset_id', 'depr_book_id'], dropna=False):
        out += _split_asset_book(rows, _accounts(group.get(aid)))

    new_bal = pd.DataFrame(out)
    new_master, new_depr, planted = planted_cases(master.columns, depr.columns)
    new_bal = pd.concat([new_bal, planted], ignore_index=True)
    master = pd.concat([master, new_master], ignore_index=True)
    depr = pd.concat([depr, new_depr], ignore_index=True)
    return master, depr, new_bal, flags


def planted_cases(master_cols, depr_cols):
    """One active asset per DQ-NBV-* check, CURR and HIST books."""
    masters, deprs, rows = [], [], []

    def asset(aid, label, group='IT_EQ', method='LNA', books=('CURR', 'HIST')):
        m = {c: None for c in master_cols}
        m.update({'client': 'CA', 'asset_id': aid, 'asset_group': group, 'status': 'N',
                  'description': f'Planted NBV case {label}', 'org_amount': 10000.0,
                  'cap_date_from': '2021-04-01', 'date_from': '2021-04-01', '_edge_case': label})
        masters.append(m)
        for b in books:
            d = {c: None for c in depr_cols}
            d.update({'client': 'CA', 'asset_id': aid, 'depr_book_id': b, 'status': 'N',
                      'depr_method': method, 'lifetime': 60, 'cap_date_from': '2021-04-01',
                      'date_from': '2021-04-01', '_edge_case': label})
            deprs.append(d)

    def post(aid, label, book, trans_type, account, amount):
        rows.append({'client': 'CA', 'asset_id': aid, 'depr_book_id': book, 'trans_type': trans_type,
                     'account': account, 'total_amount': amount, 'total_cur_amount': amount,
                     'max_trans_date': '2026-03-31', 'min_trans_date': '2021-04-01',
                     'transaction_count': 12, '_edge_case': label})

    def capitalise(aid, label, cost, depr, books=('CURR', 'HIST'), p='16'):
        for b in books:
            post(aid, label, b, 'CA', f'{p}000', cost)
            post(aid, label, b, 'CA', f'{p}005', -cost)
            if depr:
                post(aid, label, b, 'ND', f'{p}015', -depr)
                post(aid, label, b, 'ND', PL_DEPRECIATION, depr)

    a = 'ANBV0001'; asset(a, 'DQ-NBV-C01')
    for b in ('CURR', 'HIST'):
        post(a, 'DQ-NBV-C01', b, 'ND', PL_DEPRECIATION, 500.0)
        post(a, 'DQ-NBV-C01', b, 'ND', DISPOSAL, -500.0)

    a = 'ANBV0002'; asset(a, 'DQ-NBV-V01'); capitalise(a, 'DQ-NBV-V01', 1000.0, 1500.0)

    for i in range(3):
        a = f'ANBV001{i}'; asset(a, 'DQ-NBV-K01'); capitalise(a, 'DQ-NBV-K01', 5000.0, 5000.0)

    a = 'ANBV0003'; asset(a, 'DQ-NBV-K02', group='BLDG', method='NOD')
    capitalise(a, 'DQ-NBV-K02', 250000.0, 0, p='14')
    post(a, 'DQ-NBV-K02', 'CURR', 'VN', '14000', 20000.0)
    post(a, 'DQ-NBV-K02', 'CURR', 'VN', REVAL_RESERVE, -15000.0)
    post(a, 'DQ-NBV-K02', 'CURR', 'VN', '14005', -5000.0)

    a = 'ANBV0004'; asset(a, 'DQ-NBV-K03')
    for b in ('CURR', 'HIST'):
        post(a, 'DQ-NBV-K03', b, 'CA', '16000', 8000.0)
        post(a, 'DQ-NBV-K03', b, 'ND', '16015', -2000.0)
        post(a, 'DQ-NBV-K03', b, 'ND', PL_DEPRECIATION, 2000.0)

    a = 'ANBV0005'; asset(a, 'DQ-NBV-K04'); capitalise(a, 'DQ-NBV-K04', 10000.0, 3000.0)
    for b in ('CURR', 'HIST'):
        post(a, 'DQ-NBV-K04', b, 'SA', '16000', -4000.0)
        post(a, 'DQ-NBV-K04', b, 'SA', DISPOSAL, 4000.0)

    a = 'ANBV0006'; asset(a, 'DQ-NBV-K05', method='LNA'); capitalise(a, 'DQ-NBV-K05', 12000.0, 0)

    return pd.DataFrame(masters), pd.DataFrame(deprs), pd.DataFrame(rows)


def main():
    master = pd.read_csv(_path('asset_master'))
    depr = pd.read_csv(_path('asset_depreciation'))
    bal = pd.read_csv(_path('asset_balances'))
    flags = pd.read_csv(_path('asset_trans_flags'))
    if 'account' in bal.columns:
        print('  asset_balances_HOC.csv already has accounts — rerun generate_asset_data.py first')
        return

    master, depr, bal, flags = reshape(master, depr, bal, flags)
    cols = ['client', 'asset_id', 'depr_book_id', 'trans_type', 'account', 'total_amount',
            'total_cur_amount', 'max_trans_date', 'min_trans_date', 'transaction_count', '_edge_case']
    bal = bal[cols]

    master.to_csv(_path('asset_master'), index=False)
    depr.to_csv(_path('asset_depreciation'), index=False)
    bal.to_csv(_path('asset_balances'), index=False)
    flags.to_csv(_path('asset_trans_flags'), index=False)
    print(f'[HOC] NBV reshape: {len(bal)} account-level balance rows, '
          f'{bal["asset_id"].nunique()} assets, CURR/HIST books')


if __name__ == '__main__':
    main()
