"""Net book value (NBV) for HoC fixed assets.

Rule confirmed by Parliament's asset team (September 2026): per asset and
depreciation book, NBV is the sum of every aattrans posting, of any trans_type,
to an account that starts with '1' and ends in '00' (cost/valuation) or '15'
(accumulated depreciation). Every other account is a contra/control, P&L or
reserve account and is excluded. Account 70000 is the revaluation reserve,
which should equal HIST NBV minus CURR NBV for each asset.

HoC only. HoL's chart of accounts uses a letter-prefix format, so the rule
can't be applied there until Parliament confirms HoL's equivalent.
"""
import numpy as np
import pandas as pd

NBV_HOUSE = 'HOC'
REVAL_RESERVE_ACCOUNT = '70000'
TOLERANCE = 1.0
DEPRECIATING_METHODS = {'LNA', 'LNB'}

ACCOUNT_CLASS_LABELS = {
    'cost': 'Cost / valuation',
    'depreciation': 'Accumulated depreciation',
    'reserve': 'Revaluation reserve',
    'other': 'Other (contra / P&L)',
}

# Shown for every DQ-NBV-* drill-down, whichever figure triggered the check,
# so the reviewer sees the asset's whole NBV position.
NBV_EVIDENCE_COLS = [
    'asset_id', 'description', 'asset_group', 'status', 'origin', 'curr_depr_method',
    'curr_cost', 'curr_depreciation', 'curr_nbv', 'hist_nbv',
    'reval_reserve', 'reval_expected', 'reval_variance',
    'curr_net_all_accounts', 'hist_net_all_accounts', 'trans_types',
]

NBV_BANDS =['Negative', 'Nil', 'Under £1k', '£1k – £10k', '£10k – £100k', '£100k – £1m', 'Over £1m']


def normalise_account(s):
    s = s.astype(str).str.strip()
    s = s.str.replace(r'\.0+$', '', regex=True)
    return s.replace(['nan', 'None', ''], np.nan)


def classify_accounts(accounts):
    a = normalise_account(accounts).fillna('')
    starts_1 = a.str.startswith('1')
    return np.select(
        [starts_1 & a.str.endswith('00'),
         starts_1 & a.str.endswith('15'),
         a == REVAL_RESERVE_ACCOUNT],
        ['cost', 'depreciation', 'reserve'],
        default='other',
    )


def nbv_band(values):
    v = pd.to_numeric(values, errors='coerce').fillna(0)
    conds = [
        v <= -TOLERANCE,
        v.abs() < TOLERANCE,
        v < 1_000,
        v < 10_000,
        v < 100_000,
        v < 1_000_000,
    ]
    return np.select(conds, NBV_BANDS[:-1], default=NBV_BANDS[-1])


def account_rows(frames, house=NBV_HOUSE):
    """HoC asset_balances rows with a normalised account and its NBV class."""
    ab = frames.get('asset_balances', pd.DataFrame())
    if ab.empty or 'account' not in ab.columns or 'house' not in ab.columns:
        return pd.DataFrame()
    rows = ab[ab['house'] == house].copy()
    if rows.empty:
        return rows
    rows['account'] = normalise_account(rows['account'])
    rows['total_amount'] = pd.to_numeric(rows['total_amount'], errors='coerce').fillna(0)
    rows['account_class'] = classify_accounts(rows['account'])
    return rows


def build_asset_nbv(frames):
    """Adds frames['asset_nbv_books'] (one row per asset per depreciation book)
    and frames['asset_nbv'] (one row per asset, CURR and HIST side by side).
    Neither is added when asset_balances has no account column (e.g. an
    extract taken before September 2026)."""
    frames.pop('asset_nbv_books', None)
    frames.pop('asset_nbv', None)
    rows = account_rows(frames)
    if rows.empty:
        return

    keys = ['house', 'client', 'asset_id', 'depr_book_id']
    amt = rows.pivot_table(index=keys, columns='account_class', values='total_amount',
                           aggfunc='sum', fill_value=0).reset_index()
    for c in ('cost', 'depreciation', 'reserve', 'other'):
        if c not in amt.columns:
            amt[c] = 0.0
    amt['nbv'] = amt['cost'] + amt['depreciation']
    amt['net_all_accounts'] = amt[['cost', 'depreciation', 'reserve', 'other']].sum(axis=1)

    g = rows.groupby(keys)
    meta = pd.DataFrame({
        'trans_types': g['trans_type'].agg(lambda s: ', '.join(sorted(set(s.dropna().astype(str))))),
        'has_nbv_account': g['account_class'].agg(lambda s: s.isin(['cost', 'depreciation']).any()),
        'has_disposal': g['trans_type'].agg(lambda s: (s == 'SA').any()),
        'has_os': g['trans_type'].agg(lambda s: (s == 'OS').any()),
        'has_ca': g['trans_type'].agg(lambda s: s.isin(['CA', 'PC']).any()),
        'transaction_count': g['transaction_count'].sum() if 'transaction_count' in rows.columns else g.size(),
    }).reset_index()
    if 'max_trans_date' in rows.columns:
        last = rows.assign(_d=pd.to_datetime(rows['max_trans_date'], errors='coerce')).groupby(keys)['_d'].max()
        meta = meta.merge(last.rename('last_trans_date').reset_index(), on=keys, how='left')
    books = amt.merge(meta, on=keys, how='left')

    ad = frames.get('asset_depreciation', pd.DataFrame())
    if not ad.empty and {'client', 'asset_id', 'depr_book_id'} <= set(ad.columns):
        cols = [c for c in ('client', 'asset_id', 'depr_book_id', 'depr_method', 'lifetime', 'status') if c in ad.columns]
        dep = ad[ad['house'] == NBV_HOUSE][cols].drop_duplicates(['client', 'asset_id', 'depr_book_id'])
        dep = dep.rename(columns={'status': 'book_status'})
        books = books.merge(dep, on=['client', 'asset_id', 'depr_book_id'], how='left')
    for c in ('depr_method', 'lifetime', 'book_status'):
        if c not in books.columns:
            books[c] = np.nan

    frames['asset_nbv_books'] = books

    # Asset level: CURR and HIST side by side. Flags and counts combine every book.
    book_vals = books.pivot_table(index=['house', 'client', 'asset_id'], columns='depr_book_id',
                                  values=['cost', 'depreciation', 'nbv', 'net_all_accounts'],
                                  aggfunc='sum')
    book_vals.columns = [f'{b.lower()}_{v}' for v, b in book_vals.columns]
    book_vals = book_vals.reset_index()
    for b in ('curr', 'hist'):
        for v in ('cost', 'depreciation', 'nbv', 'net_all_accounts'):
            if f'{b}_{v}' not in book_vals.columns:
                book_vals[f'{b}_{v}'] = np.nan

    present = books.groupby(['house', 'client', 'asset_id'])['depr_book_id'].agg(set)
    ga = books.groupby(['house', 'client', 'asset_id'])
    flags = pd.DataFrame({
        'has_curr': present.map(lambda s: 'CURR' in s),
        'has_hist': present.map(lambda s: 'HIST' in s),
        'reval_reserve': ga['reserve'].sum(),
        'has_nbv_account': ga['has_nbv_account'].any(),
        'has_disposal': ga['has_disposal'].any(),
        'has_os': ga['has_os'].any(),
        'has_ca': ga['has_ca'].any(),
        'transaction_count': ga['transaction_count'].sum(),
        'trans_types': ga['trans_types'].agg(lambda s: ', '.join(sorted({t.strip() for x in s for t in str(x).split(',') if t.strip()}))),
    }).reset_index()
    assets = book_vals.merge(flags, on=['house', 'client', 'asset_id'], how='left')

    curr_method = books[books['depr_book_id'] == 'CURR'][['client', 'asset_id', 'depr_method']].drop_duplicates(['client', 'asset_id'])
    assets = assets.merge(curr_method.rename(columns={'depr_method': 'curr_depr_method'}),
                          on=['client', 'asset_id'], how='left')

    am = frames.get('asset_master', pd.DataFrame())
    if not am.empty:
        cols = [c for c in ('client', 'asset_id', 'description', 'asset_group', 'status', 'cap_date_from', 'org_amount') if c in am.columns]
        master = am[am['house'] == NBV_HOUSE][cols].drop_duplicates(['client', 'asset_id'])
        assets = assets.merge(master, on=['client', 'asset_id'], how='left')
    for c in ('description', 'asset_group', 'status', 'cap_date_from', 'org_amount'):
        if c not in assets.columns:
            assets[c] = np.nan

    both = assets['has_curr'] & assets['has_hist']
    expected = assets['hist_nbv'].fillna(0) - assets['curr_nbv'].fillna(0)
    assets['reval_expected'] = np.where(both, expected, np.nan)
    assets['reval_variance'] = np.where(both, assets['reval_reserve'] - expected, np.nan)
    assets['origin'] = np.where(assets['has_os'] & ~assets['has_ca'], 'Migrated (OS)',
                        np.where(assets['has_os'], 'Migrated + Unit4 additions', 'Capitalised in Unit4'))
    assets['nbv_band'] = nbv_band(assets['curr_nbv'])
    assets['asset_group'] = assets['asset_group'].fillna('(no group)')
    frames['asset_nbv'] = assets


def active(df):
    return df['status'] == 'N'


def nbv_population(df, check_id):
    """Population for each DQ-NBV-* check. Shared by run_dq_analysis and
    get_failing_records so the summary count and the drill-down agree."""
    if df.empty:
        return df
    a = active(df)
    if check_id in ('DQ-NBV-C01', 'DQ-NBV-K03'):
        return df[a]
    if check_id == 'DQ-NBV-V01':
        return df[a & df['has_nbv_account']]
    if check_id == 'DQ-NBV-K01':
        return df[a & df['has_nbv_account'] & df['has_curr'] & ~df['has_disposal']]
    if check_id == 'DQ-NBV-K02':
        return df[a & df['has_curr'] & df['has_hist']]
    if check_id == 'DQ-NBV-K04':
        return df[a & df['has_disposal'] & df['has_curr']]
    if check_id == 'DQ-NBV-K05':
        cost = pd.to_numeric(df['curr_cost'], errors='coerce').fillna(0)
        return df[a & df['has_curr'] & df['curr_depr_method'].isin(DEPRECIATING_METHODS) & (cost > TOLERANCE)]
    return df


def asset_account_detail(frames, asset_id):
    """Account x trans_type pivot for one asset, per depreciation book — the
    same view Parliament used to confirm the NBV rule."""
    rows = account_rows(frames)
    if rows.empty:
        return rows
    rows = rows[rows['asset_id'].astype(str) == str(asset_id)]
    if rows.empty:
        return rows
    ga = frames.get('aglaccounts', pd.DataFrame())
    if not ga.empty and {'account', 'description'} <= set(ga.columns):
        names = ga[ga['house'] == NBV_HOUSE][['account', 'description']].copy()
        names['account'] = normalise_account(names['account'])
        names = names.drop_duplicates('account').rename(columns={'description': 'account_description'})
        rows = rows.merge(names, on='account', how='left')
    else:
        rows['account_description'] = np.nan
    return rows
