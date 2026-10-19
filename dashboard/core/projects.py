"""Projects (Seq 22): scope and opening position.

Parliament has no Unit4 projects module. A project is a Unit (confirmed by
Krishna, Oct 2026) and its HAIS codes are the cost lines under it. Two files
feed this module, both single combined files in data/projects/:

  project_list        Krishna's list, one row per HAIS code, with the
                      hierarchy and the Projcat / Projgrp classification.
  project_financials  Ben's dump, one row per account x HAIS code x house x
                      period: committed (open PO balance), actuals, budget.

Opening position per Unit and house:
  spend to date     = sum of actuals
  commitments       = sum of committed purchase (Q3: checked on real data, it
                      doesn't repeat across periods, so summing is safe)
  budget to date    = sum of current budget, rolled up to the Unit before any
                      comparison, because budget can sit on different accounts
                      or cost lines from the spend (Q4)
  remaining budget  = budget to date - spend to date

See build_spec/projects_tab.md for the design and the open questions.
"""
import numpy as np
import pandas as pd

LIST_HOUSE = 'Parliament'            # house value for checks on the list itself (not split by house)
HOUSES = ['HOC', 'HOL']
TOLERANCE = 1.0
STALE_COMMITMENT_MONTHS = 12
RESIDUAL_COMMITMENT_MAX = 5.0
TRUNCATED_WINDOW_MONTHS = 3          # first activity this close to the extract start = history probably cut off
OVERSPEND_PCT, OVERSPEND_ABS = 0.05, 1000.0
SPLIT_DRIFT_PP = 5.0
LIVE_MONTHS = 12                     # activity this recent = still live at the extract date
SIGNAL_ORDER = ['Live', 'Dormant', 'No activity']
SIGNAL_HEX = {'Live': '#16a34a', 'Dormant': '#d97706', 'No activity': '#94a3b8'}

PROJECT_TYPES = {
    'F-MAJP': 'CAT A',
    'F-MINP': 'CAT B',
    'F-MNSP': 'Other (CAT C?)',
    'F-ANRP': 'Annual Requirements',
}
TYPE_ORDER = ['CAT A', 'CAT B', 'Other (CAT C?)', 'Annual Requirements', 'Unclassified']
TYPE_HEX = {
    'CAT A': '#0f4c81', 'CAT B': '#3b7dd8', 'Other (CAT C?)': '#8fb8ee',
    'Annual Requirements': '#b8a77a', 'Unclassified': '#94a3b8', 'Not on list': '#cbd5e1',
}
# Provisional "expenditure only" rule (Q5): cost types whose description says
# income or recharge are left out. To be confirmed with Ben / Ebenezer.
INCOME_KEYWORDS = ('INCOME', 'RECHARGE')

DERIVED_TABLES = ('project_codes', 'project_units', 'project_commitments')
SOURCE_TABLES = ('project_list', 'project_financials')

AMOUNT_COLS = ['actuals', 'budget', 'committed', 'forecast']

# Display names, shared by the tab, the drill-downs and the SI extract.
COLUMN_LABELS = {
    'unit': 'Unit', 'unit_desc': 'Project (Unit)', 'hais_code': 'HAIS code', 'hais_desc': 'Cost line',
    'house': 'House', 'project_type': 'Category', 'projcat': 'Projcat', 'projcat_desc': 'Projcat description',
    'projgrp': 'Projgrp', 'projgrp_desc': 'Portfolio (Projgrp)', 'costc': 'Cost centre',
    'costc_desc': 'Cost centre description', 'directorate': 'Directorate', 'directorate_desc': 'Directorate description',
    'department': 'Department', 'department_desc': 'Department description', 'status': 'Status',
    'spend_to_date': 'Spend to date', 'commitments': 'Open commitments', 'budget_to_date': 'Budget to date',
    'remaining_budget': 'Remaining budget', 'remaining_after_commitments': 'Remaining after commitments',
    'current_fy_actuals': 'Current FY actuals', 'current_fy_budget': 'Current FY budget',
    'first_period': 'First activity', 'last_period': 'Last activity', 'hais_count': 'Cost lines with activity',
    'fy_label': 'Financial year', 'fiscal_year': 'Year', 'period': 'Period', 'actuals': 'Actuals',
    'budget': 'Budget', 'committed': 'Committed', 'account': 'Account', 'account_desc': 'Account description',
    'mipck_l1': 'Cost type', 'mipck_l1_desc': 'Cost type description', 'age_months': 'Age (months)',
    'houses': 'Houses', 'actuals_total': 'Actuals (all years)', 'budget_total': 'Budget (all years)',
    'committed_total': 'Open commitments', 'has_activity': 'Any activity', 'dup_count': 'Times listed',
    'unit_class_variants': 'Conflicting classification', 'desc_dup_units': 'Same description under',
    'projgrp_desc_codes': 'Codes sharing this portfolio name', 'attr_mismatch': 'List vs financials',
    'split_by_year': 'HoC share by year', 'split_range_pp': 'HoC share range (pp)', 'on_list': 'On project list',
    'in_financials': 'In financials', 'truncated': 'History may start before April 2020',
    'cumulative_actuals': 'Spend to date', 'cumulative_budget': 'Budget to date',
    'signal': 'Activity signal', 'first_activity': 'First activity', 'last_activity': 'Last activity',
    'hais_listed': 'Cost lines listed',
}


# ── Small helpers ─────────────────────────────────────────────────────────────

def fy_label(fy) -> str:
    try:
        fy = int(fy)
    except (TypeError, ValueError):
        return '—'
    return f'{fy}/{str(fy + 1)[2:]}'


def period_label(period) -> str:
    """202012 -> 'FY2020/21 P12'."""
    if period is None or (isinstance(period, float) and np.isnan(period)):
        return '—'
    p = int(period)
    return f'FY{fy_label(p // 100)} P{p % 100:02d}'


def period_index(period: pd.Series) -> pd.Series:
    """YYYYPP -> a running month number, so period gaps can be measured.
    Adjustment periods 13-15 count as period 12."""
    p = pd.to_numeric(period, errors='coerce')
    return (p // 100) * 12 + np.minimum(p % 100, 12)


def _strip(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip().replace({'nan': np.nan, 'None': np.nan, '': np.nan, '<NA>': np.nan})
    return df


def _join_unique(s) -> str:
    vals = sorted({str(v) for v in s.dropna() if str(v).strip()})
    return ', '.join(vals)


def extract_bounds(lines: pd.DataFrame) -> dict:
    """First and latest period in the financials, and the current FY."""
    if lines is None or lines.empty:
        return {'first': None, 'latest': None, 'current_fy': None}
    p = pd.to_numeric(lines['period'], errors='coerce').dropna()
    if p.empty:
        return {'first': None, 'latest': None, 'current_fy': None}
    return {'first': int(p.min()), 'latest': int(p.max()), 'current_fy': int(p.max()) // 100}


# ── Build ─────────────────────────────────────────────────────────────────────

def _prepare_list(lst: pd.DataFrame) -> pd.DataFrame:
    lst = _strip(lst.copy(), ['department', 'department_desc', 'directorate', 'directorate_desc', 'costc',
                              'costc_desc', 'projcat', 'projcat_desc', 'projgrp', 'projgrp_desc', 'unit',
                              'unit_desc', 'hais_code', 'hais_desc', 'status'])
    lst['project_type'] = lst['projcat'].map(PROJECT_TYPES).fillna('Unclassified')
    lst['house'] = LIST_HOUSE
    return lst.reset_index(drop=True)


def _prepare_lines(fin: pd.DataFrame, lst: pd.DataFrame) -> pd.DataFrame:
    fin = _strip(fin.copy(), ['hais_code', 'hais_desc', 'unit', 'costc', 'directorate', 'department', 'account',
                              'account_desc', 'mipck_l1', 'mipck_l1_desc', 'mipck_l2', 'mipck_l2_desc', 'recharge'])
    for c in AMOUNT_COLS:
        fin[c] = pd.to_numeric(fin[c], errors='coerce').fillna(0.0) if c in fin.columns else 0.0
    fin['period'] = pd.to_numeric(fin['period'], errors='coerce')
    fin['fiscal_year'] = pd.to_numeric(fin['fiscal_year'], errors='coerce').fillna(fin['period'] // 100)
    fin['house'] = fin['recharge'].astype(str).str.upper().map({'HOC': 'HOC', 'HOL': 'HOL'}).fillna('Unknown')
    desc = (fin['mipck_l1_desc'].fillna('') + ' ' + fin.get('mipck_l2_desc', pd.Series('', index=fin.index)).fillna('')).str.upper()
    fin['is_income'] = desc.str.contains('|'.join(INCOME_KEYWORDS), regex=True)
    fin = fin.rename(columns={'unit': 'fin_unit', 'costc': 'fin_costc', 'directorate': 'fin_directorate',
                              'department': 'fin_department', 'hais_desc': 'fin_hais_desc'})

    attrs = ['unit', 'unit_desc', 'projcat', 'project_type', 'projgrp', 'projgrp_desc', 'costc',
             'directorate', 'department', 'hais_desc']
    first_listing = lst.dropna(subset=['hais_code']).drop_duplicates('hais_code')[['hais_code'] + attrs]
    lines = fin.merge(first_listing, on='hais_code', how='left')
    lines['on_list'] = lines['hais_code'].isin(first_listing['hais_code'])
    off = ~lines['on_list']
    lines.loc[off, 'unit'] = lines.loc[off, 'fin_unit']
    lines.loc[off, 'project_type'] = 'Not on list'
    lines['hais_desc'] = lines['hais_desc'].fillna(lines['fin_hais_desc'])
    lines['unit_desc'] = lines['unit_desc'].fillna(lines['unit'])
    lines['fy_label'] = lines['fiscal_year'].map(fy_label)
    return lines


def _active(lines: pd.DataFrame) -> pd.Series:
    return (lines[['actuals', 'budget', 'committed']].abs() >= 0.005).any(axis=1)


# Grain of project_summary: everything the views filter or group by, without the
# account and period detail. Ben's file is ~440k rows; this is a small fraction.
SUMMARY_KEYS = ['unit', 'unit_desc', 'hais_code', 'hais_desc', 'house', 'fiscal_year', 'project_type',
                'is_income', 'on_list', 'mipck_l1_desc']


def _summarise(lines: pd.DataFrame) -> pd.DataFrame:
    """Lines rolled up to SUMMARY_KEYS, with the first and last period that had any activity."""
    df = lines[SUMMARY_KEYS[:-1] + ['period', 'actuals', 'budget', 'committed']].copy()
    df['mipck_l1_desc'] = lines['mipck_l1_desc'].fillna('(blank)')
    df['unit_desc'] = df['unit_desc'].fillna(df['unit'])
    df['hais_desc'] = df['hais_desc'].fillna('')
    df['_p_act'] = df['period'].where(_active(df))
    s = df.groupby(SUMMARY_KEYS, dropna=False, sort=False).agg(
        actuals=('actuals', 'sum'), budget=('budget', 'sum'), committed=('committed', 'sum'),
        first_active=('_p_act', 'min'), last_active=('_p_act', 'max')).reset_index()
    s['fy_label'] = s['fiscal_year'].map(fy_label)
    return s


def unit_attributes(codes: pd.DataFrame) -> pd.DataFrame:
    """One row per Unit: the most common value of each classification across its cost lines."""
    if codes is None or codes.empty:
        return pd.DataFrame(columns=['unit'])
    cols = ['unit_desc', 'projcat', 'project_type', 'projgrp', 'projgrp_desc', 'costc', 'costc_desc',
            'directorate', 'directorate_desc', 'department', 'department_desc']
    out = pd.DataFrame({'unit': codes['unit'].dropna().unique()})
    for c in cols:
        if c not in codes.columns:
            out[c] = np.nan
            continue
        top = (codes[['unit', c]].dropna().value_counts().reset_index(name='_n')
               .sort_values(['unit', '_n', c], ascending=[True, False, True]).drop_duplicates('unit'))
        out[c] = out['unit'].map(top.set_index('unit')[c])
    out['hais_listed'] = out['unit'].map(codes.groupby('unit')['hais_code'].nunique()).fillna(0).astype(int)
    return out


def _build_codes(lst: pd.DataFrame, summary: pd.DataFrame, lines: pd.DataFrame) -> pd.DataFrame:
    codes = lst.copy()
    codes['dup_count'] = codes.groupby('hais_code')['hais_code'].transform('size')
    codes['prefix_ok'] = [bool(h) and bool(u) and str(h).startswith(str(u))
                          for h, u in zip(codes['hais_code'].fillna(''), codes['unit'].fillna(''))]
    text = (codes['hais_desc'].fillna('') + ' ' + codes['unit_desc'].fillna('')).str.upper()
    codes['do_not_use'] = text.str.contains('DO NOT USE') & (codes['status'] == 'N')

    # A project needs one classification: report every attribute that varies within the Unit
    class_cols = [('projcat', 'Projcat'), ('projgrp', 'Projgrp'), ('costc', 'Cost centre'), ('directorate', 'Directorate')]
    nun = codes.groupby('unit')[[c for c, _ in class_cols]].nunique()
    multi = nun[(nun > 1).any(axis=1)].index
    variants = {}
    for unit, g in codes[codes['unit'].isin(multi)].groupby('unit'):
        variants[unit] = '; '.join(f'{label}: {_join_unique(g[col])}' for col, label in class_cols
                                   if g[col].dropna().nunique() > 1)
    codes['unit_class_variants'] = codes['unit'].map(variants).fillna('')

    # Cloned cost lines: same description, active, under a different Unit
    norm = codes['hais_desc'].fillna('').str.upper().str.replace(r'^DO NOT USE\s*-?\s*', '', regex=True).str.strip()
    codes['_norm_desc'] = norm
    active_units = codes[codes['status'] == 'N'].dropna(subset=['unit'])
    shared_desc = active_units.groupby('_norm_desc')['unit'].nunique()
    shared_desc = shared_desc[(shared_desc > 1) & (shared_desc.index != '')].index
    by_desc = active_units[active_units['_norm_desc'].isin(shared_desc)].groupby('_norm_desc')['unit'] \
        .agg(lambda s: set(s))
    codes['desc_dup_units'] = [
        ', '.join(sorted(by_desc[d] - {u})) if d in by_desc.index else ''
        for d, u in zip(codes['_norm_desc'], codes['unit'])
    ]
    codes = codes.drop(columns='_norm_desc')

    # Portfolio names used by more than one Projgrp code (two code schemes in use)
    pg = codes.dropna(subset=['projgrp']).assign(_d=lambda d: d['projgrp_desc'].fillna('').str.upper())
    grp = pg.groupby('_d')['projgrp'].agg(lambda s: ', '.join(sorted(set(s))))
    grp = grp[pg.groupby('_d')['projgrp'].nunique() > 1]
    codes['projgrp_desc_codes'] = codes['projgrp_desc'].fillna('').str.upper().map(grp).fillna('')

    # Activity per listed cost line
    on = summary[summary['on_list']]
    stats = on.groupby('hais_code').agg(
        actuals_total=('actuals', 'sum'), budget_total=('budget', 'sum'), committed_total=('committed', 'sum'),
        first_period=('first_active', 'min'), last_period=('last_active', 'max')).reset_index()
    act_houses = on[on['first_active'].notna()][['hais_code', 'house']].drop_duplicates()
    n_houses = act_houses.groupby('hais_code')['house'].agg(['nunique', 'first'])
    stats['houses'] = stats['hais_code'].map(
        n_houses['first'].where(n_houses['nunique'] == 1, 'Shared'))
    codes = codes.merge(stats, on='hais_code', how='left')
    codes['has_activity'] = codes['first_period'].notna()
    codes['houses'] = codes['houses'].fillna('—')
    for c in ('actuals_total', 'budget_total', 'committed_total'):
        codes[c] = codes[c].fillna(0.0)

    # List vs financials: the financials carry their own Unit / cost centre / directorate / department
    pairs = [('fin_unit', 'unit', 'Unit'), ('fin_costc', 'costc', 'Cost centre'),
             ('fin_directorate', 'directorate', 'Directorate'), ('fin_department', 'department', 'Department')]
    combos = lines.loc[lines['on_list'], ['hais_code'] + [f for f, _, _ in pairs]].drop_duplicates()
    ref = codes.drop_duplicates('hais_code').set_index('hais_code')
    parts = []
    for fin_col, list_col, label in pairs:
        listed = combos['hais_code'].map(ref[list_col])
        bad = combos[combos[fin_col].notna() & listed.notna() & (combos[fin_col] != listed)]
        if bad.empty:
            continue
        fin_vals = combos[combos['hais_code'].isin(bad['hais_code'])].groupby('hais_code')[fin_col] \
            .agg(lambda s: ', '.join(sorted(set(s.dropna()))))
        parts.append(pd.Series({h: f'{label}: list {ref.at[h, list_col]}, financials {v}' for h, v in fin_vals.items()}))
    mism = pd.concat(parts, axis=1).apply(lambda r: '; '.join(r.dropna()), axis=1) if parts else pd.Series(dtype=str)
    codes['attr_mismatch'] = codes['hais_code'].map(mism).fillna('')

    # HoC / HoL split per year for shared codes (positive spend only)
    spend = on[on['actuals'] > 0].pivot_table(index=['hais_code', 'fiscal_year'], columns='house',
                                               values='actuals', aggfunc='sum', fill_value=0.0)
    if {'HOC', 'HOL'} <= set(spend.columns):
        both = spend[(spend['HOC'] > 0) & (spend['HOL'] > 0)].copy().reset_index()
        both['share'] = both['HOC'] / (both['HOC'] + both['HOL']) * 100
        both['_txt'] = both['fiscal_year'].map(fy_label) + ' ' + both['share'].round(0).astype(int).astype(str) + '%'
        g = both.groupby('hais_code')
        codes['split_range_pp'] = codes['hais_code'].map((g['share'].max() - g['share'].min()).round(1))
        codes['split_by_year'] = codes['hais_code'].map(g['_txt'].agg(' · '.join)).fillna('')
    else:
        codes['split_range_pp'] = np.nan
        codes['split_by_year'] = ''
    return codes


def filter_lines(lines, include_annual=True, expenditure_only=False, houses=None, on_list_only=True):
    """Works on project_summary and on project_lines (both carry the filter columns)."""
    if lines is None or lines.empty:
        return lines
    m = pd.Series(True, index=lines.index)
    if on_list_only:
        m &= lines['on_list']
    if not include_annual:
        m &= lines['project_type'] != 'Annual Requirements'
    if expenditure_only:
        m &= ~lines['is_income']
    if houses:
        m &= lines['house'].isin(houses)
    return lines[m]


def unit_positions(summary: pd.DataFrame, attrs: pd.DataFrame, bounds: dict) -> pd.DataFrame:
    """Opening position, one row per Unit x house, from already-filtered summary rows."""
    cols = ['unit', 'house', 'spend_to_date', 'commitments', 'budget_to_date', 'remaining_budget',
            'remaining_after_commitments', 'current_fy_actuals', 'current_fy_budget', 'first_period',
            'last_period', 'hais_count', 'truncated']
    if summary is None or summary.empty:
        return pd.DataFrame(columns=cols)
    cur = bounds.get('current_fy')
    s = summary.assign(_cur_act=np.where(summary['fiscal_year'] == cur, summary['actuals'], 0.0),
                       _cur_bud=np.where(summary['fiscal_year'] == cur, summary['budget'], 0.0),
                       _act_code=summary['hais_code'].where(summary['first_active'].notna()))
    pos = s.groupby(['unit', 'house']).agg(
        spend_to_date=('actuals', 'sum'), commitments=('committed', 'sum'), budget_to_date=('budget', 'sum'),
        current_fy_actuals=('_cur_act', 'sum'), current_fy_budget=('_cur_bud', 'sum'),
        first_period=('first_active', 'min'), last_period=('last_active', 'max'),
        hais_count=('_act_code', 'nunique')).reset_index()
    pos = pos[pos['first_period'].notna()]
    pos['remaining_budget'] = pos['budget_to_date'] - pos['spend_to_date']
    pos['remaining_after_commitments'] = pos['remaining_budget'] - pos['commitments']
    if bounds.get('first') is not None:
        start = period_index(pd.Series([bounds['first']])).iloc[0]
        pos['truncated'] = (period_index(pos['first_period']) - start) < TRUNCATED_WINDOW_MONTHS
    else:
        pos['truncated'] = False
    return pos.merge(attrs, on='unit', how='left')


def unit_history(lines: pd.DataFrame) -> pd.DataFrame:
    """One row per Unit x house x financial year, with running totals."""
    if lines is None or lines.empty:
        return pd.DataFrame(columns=['unit', 'house', 'fiscal_year', 'fy_label', 'actuals', 'budget', 'committed',
                                     'cumulative_actuals', 'cumulative_budget', 'remaining_budget'])
    h = lines.groupby(['unit', 'house', 'fiscal_year']).agg(
        actuals=('actuals', 'sum'), budget=('budget', 'sum'), committed=('committed', 'sum')).reset_index()
    h = h.sort_values(['unit', 'house', 'fiscal_year'])
    h['cumulative_actuals'] = h.groupby(['unit', 'house'])['actuals'].cumsum()
    h['cumulative_budget'] = h.groupby(['unit', 'house'])['budget'].cumsum()
    h['remaining_budget'] = h['cumulative_budget'] - h['cumulative_actuals']
    h['fy_label'] = h['fiscal_year'].map(fy_label)
    return h


def _build_commitments(lines: pd.DataFrame, bounds: dict) -> pd.DataFrame:
    on = lines[lines['on_list'] & (lines['committed'].abs() >= 0.005)]
    keys = ['hais_code', 'hais_desc', 'unit', 'unit_desc', 'project_type', 'house', 'account', 'account_desc',
            'fiscal_year', 'fy_label', 'period']
    if on.empty:
        return pd.DataFrame(columns=keys + ['committed', 'age_months'])
    c = on.groupby(keys, dropna=False)['committed'].sum().reset_index()
    latest = period_index(pd.Series([bounds['latest']])).iloc[0]
    c['age_months'] = (latest - period_index(c['period'])).astype(int)
    return c


# Views are cached per filter combination (there are only 12), and coverage /
# profile once, because the source frames never change while the app runs.
# build_project_frames clears the cache whenever the data is (re)loaded.
_CACHE: dict = {}


def _cached(frames, key, fn):
    k = (id(frames.get('project_summary')), key)
    if k not in _CACHE:
        _CACHE[k] = fn()
    return _CACHE[k]


def build_project_frames(frames: dict) -> None:
    """Adds project_lines, project_summary, project_unit_attrs, project_codes,
    project_units and project_commitments. Rebuilt on every load (never
    pickled), like the asset NBV frames."""
    lst, fin = frames.get('project_list'), frames.get('project_financials')
    if lst is None and fin is None:
        return
    _CACHE.clear()
    lst = _prepare_list(lst) if lst is not None else pd.DataFrame(columns=['hais_code', 'unit', 'status', 'house'])
    frames['project_list'] = lst
    lines = _prepare_lines(fin, lst) if fin is not None else None
    if lines is None:
        return
    bounds = extract_bounds(lines)
    summary = _summarise(lines)
    codes = _build_codes(lst, summary, lines)
    attrs = unit_attributes(codes)
    frames['project_lines'] = lines
    frames['project_summary'] = summary
    frames['project_unit_attrs'] = attrs
    frames['project_codes'] = codes
    frames['project_units'] = unit_positions(filter_lines(summary), attrs, bounds)
    frames['project_commitments'] = _build_commitments(lines, bounds)


# ── Views used by the tab, the drill-downs and the SI extract ─────────────────

def scope_view(frames: dict, include_annual=True, expenditure_only=False, houses=None) -> dict:
    """Everything the scope sections need, for one set of filter choices.
    'lines' is the filtered project_summary (no account / period detail)."""
    houses = tuple(houses) if houses else None

    def build():
        summary, codes = frames.get('project_summary'), frames.get('project_codes')
        bounds = extract_bounds(frames.get('project_lines'))
        attrs = frames.get('project_unit_attrs')
        f = filter_lines(summary, include_annual, expenditure_only, houses)
        listed = attrs if include_annual else attrs[attrs['project_type'] != 'Annual Requirements']
        view = {'lines': f, 'positions': unit_positions(f, attrs, bounds), 'history': unit_history(f),
                'listed_units': listed, 'bounds': bounds,
                'codes': codes if include_annual else codes[codes['project_type'] != 'Annual Requirements']}
        view['table'] = opening_table(view)
        return view

    return _cached(frames, ('view', include_annual, expenditure_only, houses), build)


def raw_lines(frames: dict, unit=None, include_annual=True, expenditure_only=False, houses=None) -> pd.DataFrame:
    """Account / period level lines (project_lines), optionally for one Unit, with the filters applied."""
    lines = frames.get('project_lines')
    if unit is not None:
        lines = lines[lines['unit'] == unit]
    return filter_lines(lines, include_annual, expenditure_only, houses)


def opening_table(view: dict) -> pd.DataFrame:
    """One row per listed Unit: HoC / HoL / total opening position side by side.
    Units on the list with no activity are kept, with zeros, so scope is complete."""
    if 'table' in view:
        return view['table']
    pos, listed = view['positions'], view['listed_units']
    figs = ['spend_to_date', 'commitments', 'budget_to_date', 'remaining_budget']
    if listed.empty:
        return pd.DataFrame()
    out = listed[['unit', 'unit_desc', 'project_type', 'projgrp_desc', 'directorate', 'hais_listed']].copy()
    for h in HOUSES:
        p = pos[pos['house'] == h].set_index('unit')
        for c in ('spend_to_date', 'commitments', 'remaining_budget'):
            out[f'{h.lower()}_{c}'] = out['unit'].map(p[c]) if not p.empty else np.nan
    tot = pos.groupby('unit')[figs].sum() if not pos.empty else pd.DataFrame(columns=figs)
    for c in figs:
        out[c] = out['unit'].map(tot[c]).fillna(0.0) if not tot.empty else 0.0
    if not pos.empty:
        g = pos.groupby('unit')
        n_house = g['house'].nunique()
        span = pd.DataFrame({'first_period': g['first_period'].min(), 'last_period': g['last_period'].max(),
                             'houses': g['house'].first().where(n_house == 1, 'Shared')})
        for c in span.columns:
            out[c] = out['unit'].map(span[c])
    else:
        out['first_period'] = out['last_period'] = out['houses'] = np.nan
    out['houses'] = out['houses'].fillna('No activity')
    out['signal'] = activity_signal(out['last_period'], view['bounds'])
    out['first_activity'] = out['first_period'].map(period_label)
    out['last_activity'] = out['last_period'].map(period_label)
    out['_order'] = out['project_type'].map({t: i for i, t in enumerate(TYPE_ORDER)}).fillna(99)
    return out.sort_values(['_order', 'spend_to_date'], ascending=[True, False]).drop(columns='_order')


def activity_signal(last_period: pd.Series, bounds: dict) -> pd.Series:
    """Live = activity in the last LIVE_MONTHS months of the extract, Dormant = older, No activity = none."""
    if bounds.get('latest') is None:
        return pd.Series('No activity', index=last_period.index)
    latest = period_index(pd.Series([bounds['latest']])).iloc[0]
    age = latest - period_index(last_period)
    return pd.Series(np.where(last_period.isna(), 'No activity', np.where(age <= LIVE_MONTHS, 'Live', 'Dormant')),
                     index=last_period.index)


def unit_detail(frames: dict, unit: str, include_annual=True, expenditure_only=False, houses=None) -> dict:
    """Everything the project modal shows for one Unit."""
    view = scope_view(frames, include_annual, expenditure_only, houses)
    lines = view['lines'][view['lines']['unit'] == unit]
    codes = frames['project_codes'][frames['project_codes']['unit'] == unit]
    hist = unit_history(lines)
    tasks = lines.groupby(['hais_code', 'hais_desc', 'house']).agg(
        spend_to_date=('actuals', 'sum'), commitments=('committed', 'sum'), budget_to_date=('budget', 'sum'),
        first_period=('first_active', 'min'), last_period=('last_active', 'max')).reset_index() \
        if not lines.empty else pd.DataFrame()
    if not tasks.empty:
        tasks = tasks[tasks['first_period'].notna()]
        tasks['remaining_budget'] = tasks['budget_to_date'] - tasks['spend_to_date']
    listed = codes[['hais_code', 'hais_desc', 'status']].drop_duplicates('hais_code')
    idle = listed[~listed['hais_code'].isin(tasks['hais_code'] if not tasks.empty else [])]
    raw = raw_lines(frames, unit, include_annual, expenditure_only, houses)
    by_type = raw.groupby(['mipck_l1', 'mipck_l1_desc', 'account', 'account_desc'], dropna=False).agg(
        actuals=('actuals', 'sum'), budget=('budget', 'sum'), committed=('committed', 'sum')).reset_index() \
        if not raw.empty else pd.DataFrame()
    attrs = frames['project_unit_attrs']
    attrs = attrs[attrs['unit'] == unit]
    return {'attrs': attrs.iloc[0].to_dict() if not attrs.empty else {'unit': unit},
            'positions': view['positions'][view['positions']['unit'] == unit],
            'history': hist, 'tasks': tasks, 'idle_codes': idle, 'by_account': by_type,
            'codes': codes, 'bounds': view['bounds']}


def drill_records(frames: dict, kind: str, key, include_annual=True, expenditure_only=False, houses=None) -> pd.DataFrame:
    """Rows behind a clicked chart bar, tile or panel. Returns display-ready columns."""
    view = scope_view(frames, include_annual, expenditure_only, houses)
    table = view['table']
    money = ['spend_to_date', 'commitments', 'budget_to_date', 'remaining_budget']
    unit_cols = ['unit', 'unit_desc', 'project_type', 'projgrp_desc', 'directorate', 'houses', 'signal'] + money + \
                ['first_activity', 'last_activity']

    if kind == 'all':
        return table[unit_cols]
    if kind == 'signal':
        return table[table['signal'] == key][unit_cols]

    if kind == 'type':
        return table[table['project_type'] == key][unit_cols]
    if kind == 'portfolio':
        return table[table['projgrp_desc'].fillna('(blank)') == key][unit_cols]
    if kind == 'house':
        pos = view['positions']
        units = pos[pos['house'] == key]['unit'] if key in HOUSES else \
            table[table['houses'] == key]['unit']
        return table[table['unit'].isin(units)][unit_cols]
    if kind == 'fy':
        h = view['history']
        h = h[h['fy_label'] == key].merge(view['listed_units'][['unit', 'unit_desc', 'project_type']], on='unit', how='left')
        return h.sort_values('actuals', ascending=False)[
            ['unit', 'unit_desc', 'project_type', 'house', 'fy_label', 'actuals', 'budget', 'committed',
             'cumulative_actuals', 'cumulative_budget']]
    if kind == 'commit_age':
        c = frames.get('project_commitments', pd.DataFrame())
        if not include_annual:
            c = c[c['project_type'] != 'Annual Requirements']
        if houses:
            c = c[c['house'].isin(houses)]
        c = c[c['fy_label'] == key] if key != 'residual' else c[c['committed'].between(0.005, RESIDUAL_COMMITMENT_MAX)]
        return c.sort_values('committed', ascending=False)[
            ['unit', 'unit_desc', 'hais_code', 'hais_desc', 'house', 'account', 'account_desc', 'period',
             'committed', 'age_months']]
    if kind == 'coverage':
        return coverage(frames)['detail'].query('bucket == @key').drop(columns='bucket')
    if kind == 'cost_type':
        lines = frames['project_lines']
        lines = lines[lines['on_list'] & (lines['mipck_l1_desc'].fillna('(blank)') == key)]
        return lines.groupby(['unit', 'unit_desc', 'hais_code', 'hais_desc', 'account', 'account_desc']).agg(
            actuals=('actuals', 'sum'), budget=('budget', 'sum'), committed=('committed', 'sum')
        ).reset_index().sort_values('actuals', ascending=False)
    if kind == 'truncated':
        pos = frames.get('project_units', pd.DataFrame())
        pos = pos[pos['truncated']]
        return pos.sort_values('spend_to_date', ascending=False)[
            ['unit', 'unit_desc', 'project_type', 'house', 'first_period', 'spend_to_date']]
    if kind == 'idle':
        return table[table['houses'] == 'No activity'][unit_cols]
    return pd.DataFrame()


def coverage(frames: dict) -> dict:
    """How the two files line up, by HAIS code. Cached: the frames don't change while the app runs."""
    return _cached(frames, 'coverage', lambda: _coverage(frames))


def _coverage(frames: dict) -> dict:
    summary, codes = frames.get('project_summary'), frames.get('project_codes')
    listed = codes.drop_duplicates('hais_code')
    fin = summary.groupby('hais_code').agg(
        hais_desc=('hais_desc', 'first'), unit=('unit', 'first'), actuals=('actuals', 'sum'),
        budget=('budget', 'sum'), committed=('committed', 'sum')).reset_index()
    on_fin = fin[fin['hais_code'].isin(listed['hais_code'])]
    off_fin = fin[~fin['hais_code'].isin(listed['hais_code'])]
    idle = listed[~listed['has_activity']]
    cols = ['hais_code', 'hais_desc', 'unit', 'actuals_total', 'budget_total', 'committed_total']
    detail = pd.concat([
        listed[listed['has_activity']][cols].assign(bucket='matched'),
        idle[cols].assign(bucket='idle'),
        off_fin.rename(columns={'actuals': 'actuals_total', 'budget': 'budget_total', 'committed': 'committed_total'})
        [cols].assign(bucket='off_list'),
    ], ignore_index=True)
    on_actuals = float(summary.loc[summary['on_list'], 'actuals'].sum())
    pos = frames.get('project_units', pd.DataFrame())
    pos_actuals = float(pos['spend_to_date'].sum()) if not pos.empty else 0.0
    return {
        'matched': len(listed[listed['has_activity']]), 'idle': len(idle), 'off_list': len(off_fin),
        'matched_actuals': float(on_fin['actuals'].sum()), 'off_list_actuals': float(off_fin['actuals'].sum()),
        'listed_codes': len(listed), 'fin_codes': len(fin), 'invariant_ok': abs(on_actuals - pos_actuals) < TOLERANCE,
        'on_list_actuals': on_actuals, 'position_actuals': pos_actuals, 'detail': detail,
    }


def profile(frames: dict) -> dict:
    """Data Profile panels: how Ben's file behaves (answers Q3-Q6). Cached."""
    return _cached(frames, 'profile', lambda: _profile(frames))


def _profile(frames: dict) -> dict:
    lines = frames.get('project_lines')
    on = lines[lines['on_list']]
    summ = frames['project_summary']
    summ = summ[summ['on_list']]
    bounds = extract_bounds(lines)

    by_year = summ.groupby('fiscal_year').agg(actuals=('actuals', 'sum'), budget=('budget', 'sum'),
                                            committed=('committed', 'sum')).reset_index()
    by_year['fy_label'] = by_year['fiscal_year'].map(fy_label)
    years_with_budget = int((by_year['budget'].abs() >= 0.005).sum())

    by_type = summ.groupby('mipck_l1_desc').agg(
        actuals=('actuals', 'sum'), budget=('budget', 'sum'), committed=('committed', 'sum'),
        is_income=('is_income', 'max')).reset_index().rename(columns={'mipck_l1_desc': 'cost_type'})
    by_type = by_type.sort_values('actuals', ascending=False)

    absd = on[['hais_code', 'account', 'house', 'unit']].assign(a=on['actuals'].abs(), b=on['budget'].abs())

    def placement(keys):
        g = absd.groupby(keys)[['a', 'b']].sum()
        has_a, has_b = g['a'] >= 0.005, g['b'] >= 0.005
        return {'Actuals only': int((has_a & ~has_b).sum()), 'Budget only': int((~has_a & has_b).sum()),
                'Both': int((has_a & has_b).sum())}

    place = {'Account x cost line': placement(['hais_code', 'account', 'house']),
             'Cost line': placement(['hais_code', 'house']),
             'Project (Unit)': placement(['unit', 'house'])}

    # Commitment repeat test: the same amount on the same account and cost line in back-to-back periods
    c = on[on['committed'].abs() >= 0.005][['hais_code', 'account', 'house', 'period', 'committed']]
    c = c.groupby(['hais_code', 'account', 'house', 'period'])['committed'].sum().reset_index()
    c['idx'] = period_index(c['period'])
    c = c.sort_values(['hais_code', 'account', 'house', 'idx'])
    prev = c.groupby(['hais_code', 'account', 'house']).shift(1)
    repeats = int(((c['idx'] - prev['idx'] == 1) & ((c['committed'] - prev['committed']).abs() < 0.005)).sum())

    com = frames.get('project_commitments', pd.DataFrame())
    age = com.groupby(['fiscal_year', 'fy_label'])['committed'].agg(['sum', 'size']).reset_index() \
        if not com.empty else pd.DataFrame(columns=['fiscal_year', 'fy_label', 'sum', 'size'])
    stale = com[com['age_months'] > STALE_COMMITMENT_MONTHS] if not com.empty else com
    residual = com[com['committed'].between(0.005, RESIDUAL_COMMITMENT_MAX)] if not com.empty else com

    pos = frames.get('project_units', pd.DataFrame())
    trunc = pos[pos['truncated']] if not pos.empty else pos
    return {
        'bounds': bounds, 'by_year': by_year, 'years_with_budget': years_with_budget, 'years': len(by_year),
        'by_type': by_type, 'placement': place, 'commit_rows': len(c), 'commit_repeats': repeats,
        'commit_age': age, 'stale_count': len(stale), 'stale_value': float(stale['committed'].sum()) if len(stale) else 0.0,
        'residual_count': len(residual), 'residual_value': float(residual['committed'].sum()) if len(residual) else 0.0,
        'commit_total': float(com['committed'].sum()) if not com.empty else 0.0,
        'truncated_units': int(trunc['unit'].nunique()) if not trunc.empty else 0,
        'truncated_spend': float(trunc['spend_to_date'].sum()) if not trunc.empty else 0.0,
        'units_total': int(pos['unit'].nunique()) if not pos.empty else 0,
    }


# ── DQ populations and evidence ───────────────────────────────────────────────

def project_population(df: pd.DataFrame, check_id: str) -> pd.DataFrame:
    """Population for each PRJ_* check. Shared by run_dq_analysis and get_failing_records."""
    if check_id in ('PRJ_LIST_DUP_DESC', 'PRJ_LIST_DO_NOT_USE_ACTIVE'):
        return df[df['status'] == 'N']
    if check_id in ('PRJ_ATTR_MISMATCH',):
        return df[df['has_activity']]
    if check_id == 'PRJ_SPLIT_INCONSISTENT':
        return df[df['split_by_year'] != '']
    if check_id == 'PRJ_NO_BUDGET':
        return df[df['current_fy_actuals'].abs() >= TOLERANCE]
    if check_id == 'PRJ_OVERSPEND':
        return df[df['budget_to_date'] > TOLERANCE]
    return df


PROJECT_EVIDENCE_COLS = {
    'project_codes': ['hais_code', 'hais_desc', 'unit', 'unit_desc', 'project_type', 'projcat', 'projgrp',
                      'projgrp_desc', 'costc', 'directorate', 'status', 'houses', 'actuals_total', 'committed_total'],
    'project_units': ['unit', 'unit_desc', 'project_type', 'projgrp_desc', 'house', 'spend_to_date', 'commitments',
                      'budget_to_date', 'remaining_budget', 'current_fy_actuals', 'current_fy_budget',
                      'first_period', 'last_period'],
    'project_commitments': ['hais_code', 'hais_desc', 'unit', 'unit_desc', 'project_type', 'house', 'account',
                            'account_desc', 'period', 'committed', 'age_months'],
}
# Extra columns that explain each check's flag
PROJECT_CHECK_COLS = {
    'PRJ_LIST_DUP_HAIS': ['dup_count'],
    'PRJ_LIST_MISSING_CLASS': ['projcat', 'projgrp'],
    'PRJ_LIST_HAIS_UNIT_PREFIX': ['hais_code', 'unit'],
    'PRJ_LIST_DO_NOT_USE_ACTIVE': ['hais_desc', 'unit_desc', 'status'],
    'PRJ_LIST_DUP_DESC': ['desc_dup_units'],
    'PRJ_LIST_PROJGRP_DUP_DESC': ['projgrp_desc_codes'],
    'PRJ_UNIT_MULTI_CLASS': ['unit_class_variants'],
    'PRJ_NO_ACTIVITY': ['has_activity'],
    'PRJ_ATTR_MISMATCH': ['attr_mismatch'],
    'PRJ_SPLIT_INCONSISTENT': ['split_by_year', 'split_range_pp'],
    'PRJ_NO_BUDGET': ['current_fy_actuals', 'current_fy_budget'],
    'PRJ_OVERSPEND': ['spend_to_date', 'budget_to_date', 'remaining_budget'],
    'PRJ_NEG_SPEND_TO_DATE': ['spend_to_date'],
    'PRJ_NEG_COMMITMENT': ['committed'],
    'PRJ_HISTORY_TRUNCATED': ['first_period', 'truncated'],
    'PRJ_STALE_COMMITMENT': ['period', 'age_months', 'committed'],
    'PRJ_RESIDUAL_COMMITMENT': ['committed'],
}


def project_evidence(failing: pd.DataFrame, table: str, check_id: str, for_export=False) -> pd.DataFrame:
    extra = [c for c in PROJECT_CHECK_COLS.get(check_id, []) if c not in PROJECT_EVIDENCE_COLS[table]]
    cols = [c for c in PROJECT_EVIDENCE_COLS[table] + extra if c in failing.columns]
    out = failing[cols].copy()
    for c in ('first_period', 'last_period'):
        if c in out.columns:
            out[c] = out[c].map(period_label)
    money = out.select_dtypes('number').columns.drop(['age_months', 'dup_count', 'split_range_pp'], errors='ignore')
    out[money] = out[money].round(2)
    if for_export:
        return out.rename(columns=COLUMN_LABELS)
    return out.rename(columns={c: f'PROJECTS.{COLUMN_LABELS.get(c, c)}' for c in cols})
