"""
Supplier master: rules, loader and the scoping pipeline.

Layers (each kept on the result and shown in the record drawer):
  Raw            the extract rows, one per House + client + supplier ID
  Standardised   cleaned name / postcode / VAT / company no / bank details
  Categorised    commercial, non-commercial (held) or policy (held)
  Scoped         Keep / Fix / Monitor / Close with the rules that produced it,
                 and any steward decision that overrides it
  Target         placeholder for SI mapping (not built yet)

Classification is made per supplier (House + supplier ID). In HoC the same
supplier ID can sit under client CA and CM; those rows are one supplier, and
any disagreement between them is raised as a Consistency issue.
"""
import hashlib
import json

import numpy as np
import pandas as pd

from migration_scope import config
from migration_scope.core import standardise as std
from migration_scope.core.duplicates import key_matches, build_groups, possible_pairs
from migration_scope.core.model import (
    Rule, KEEP, FIX, MONITOR, CLOSE, HOLD_NONCOMMERCIAL, HOLD_POLICY, OUT_OF_SCOPE, NOT_IN_EXTRACT,
    IN_SCOPE, HELD, NO_DECISION_NEEDED, AWAITING, DECIDED, OVERRIDDEN,
)

OBJECT = 'suppliers'
LABEL = 'Suppliers'

RULES = [
    # Population
    Rule('MS-POP-01', 'In-scope status', 'Only suppliers with status {in_scope_statuses} are in the population. '
         'Closed (C) and terminated (T) suppliers are never migrated.', OBJECT, 'Population',
         ['in_scope_statuses']),
    Rule('MS-POP-02', 'In-scope clients', 'Only these Unit4 clients are assessed: {clients}.', OBJECT, 'Population',
         ['clients']),
    Rule('MS-POP-03', 'Legacy exclusions', 'Supplier IDs starting {legacy_excluded_id_prefixes} and names '
         '{legacy_excluded_names} are excluded, as on the DQA suppliers tab.', OBJECT, 'Population',
         ['legacy_excluded_id_prefixes', 'legacy_excluded_names']),
    # Categorisation
    Rule('MS-CAT-01', 'Non-commercial supplier group', 'Suppliers in these groups are people paid through AP, not '
         'trading suppliers. They are held for a policy decision: {noncommercial_groups}.', OBJECT, 'Supplier type',
         ['noncommercial_groups'], outcome=HOLD_NONCOMMERCIAL),
    Rule('MS-CAT-02', 'Non-commercial ID range', 'Supplier IDs starting with these digits belong to people, not '
         'trading suppliers: {noncommercial_id_prefixes}.', OBJECT, 'Supplier type',
         ['noncommercial_id_prefixes'], outcome=HOLD_NONCOMMERCIAL),
    Rule('MS-CAT-03', 'Card accounts', 'These groups are held separately for a policy decision: {policy_groups}.',
         OBJECT, 'Supplier type', ['policy_groups'], outcome=HOLD_POLICY),
    Rule('MS-CAT-04', 'Individual contractor', 'Suppliers in groups {individual_groups} are individual '
         'contractors. A decision is needed on their treatment.', OBJECT, 'Supplier type', ['individual_groups']),
    # Duplicates
    Rule('MS-DUP-01', 'Confirmed duplicate', 'Two suppliers in the same House are the same company if they share '
         'any of: {duplicate_keys}. Placeholder bank accounts are ignored.', OBJECT, 'Duplicates',
         ['duplicate_keys']),
    Rule('MS-DUP-02', 'Possible duplicate', 'Supplier names at least {possible_duplicate_similarity}% similar, '
         'not already confirmed. A steward confirms or rejects; classification is not changed.', OBJECT,
         'Duplicates', ['possible_duplicate_similarity']),
    Rule('MS-DUP-03', 'Preferred record', 'In each duplicate group the preferred record is the one with the fewest '
         'blocking issues, then open items or POs, then most recent activity, then most complete. If records are '
         'level on all of these, the rules do not pick one: they stay Monitor until a steward chooses.',
         OBJECT, 'Duplicates'),
    Rule('MS-XH-01', 'Cross-House match', 'A HoC and a HoL supplier share a VAT number, company number, bank '
         'details or name and postcode. Tagged for tracking; not a duplicate until the target design is agreed.',
         OBJECT, 'Duplicates', ['cross_house_as_duplicate']),
    # Classification
    Rule('MS-CLS-01', 'Dormant', 'No invoice, credit note or PO in the last {dormancy_months} months, and nothing '
         'open (no unpaid invoices, no open POs). Recommended Close.', OBJECT, 'Classification',
         ['dormancy_months', 'activity_voucher_types', 'open_po_statuses'], outcome=CLOSE),
    Rule('MS-CLS-02', 'Non-preferred, inactive', 'Non-preferred member of a duplicate group with no activity in the '
         'last {monitor_months} months and nothing open. Recommended Close.', OBJECT, 'Classification', ['monitor_months'],
         outcome=CLOSE),
    Rule('MS-CLS-03', 'Non-preferred, still active', 'Non-preferred member of a duplicate group with activity in the '
         'last {monitor_months} months or open items. Monitor until it can be closed.', OBJECT, 'Classification',
         ['monitor_months'], outcome=MONITOR),
    Rule('MS-CLS-04', 'Data issue to fix', 'Data quality issue that must be fixed before migration: bank details, '
         'VAT, company number, payment terms or method, name, street or postcode. Stays in scope.', OBJECT,
         'Classification', ['blocking_tests'], outcome=FIX),
    Rule('MS-CLS-05', 'Keep', 'Active in the last {dormancy_months} months or has open items, no duplicates and no '
         'blocking issues. Migrates as is.', OBJECT, 'Classification', ['dormancy_months'], outcome=KEEP),
    # Open items
    Rule('MS-TRN-01', 'Stuck open item', 'Open item more than {stuck_item_months} months past its transaction date. '
         'Likely stuck: a steward decides whether it migrates. Counted in scope until decided.', OBJECT,
         'Open items', ['stuck_item_months']),
    Rule('MS-TRN-02', "All open items won't migrate", "A dormant supplier whose open items are all marked "
         "don't migrate is closed.", OBJECT, 'Open items', outcome=CLOSE),
    # Data quality
]
RULES_BY_ID = {r.id: r for r in RULES}

_KEY_LABELS = {
    'vat': ('Same VAT number', 'SUP_VAT_DUP'),
    'company_no': ('Same company number', 'SUP_XHOUSE_COMP_REG_DUP'),
    'bank': ('Same bank details', 'SUP_BANK_SORT_DUP'),
    'name_postcode': ('Same name and postcode', 'SUP_NAME_DUP'),
    'steward': ('Linked by a steward', ''),
}

_OWN_TESTS = {
    'MS-DQ-NAME': ('Completeness', 'High', 'Supplier name is missing'),
    'MS-DQ-LTD-COMPNO': ('Completeness', 'High', 'Name says Ltd / PLC / LLP but no company number is held'),
    'MS-DQ-CLIENT-DIFF': ('Consistency', 'Medium', 'CA and CM hold different details for this supplier'),
    'MS-DQ-GROUP-ID': ('Consistency', 'Medium', 'Supplier group and ID range disagree'),
}

MASTER_FIELDS = [
    'client', 'apar_id', 'apar_name', 'short_name', 'apar_gr_id', 'status', 'apar_once', 'vat_reg_no',
    'comp_reg_no', 'country_code', 'tax_code', 'tax_system', 'terms_id', 'pay_method', 'currency', 'pay_delay',
    'clearing_code', 'bank_account', 'iban', 'swift', 'address', 'place', 'zip_code', 'province', 'expired_date',
    'last_update', 'last_trans_date',
]
STD_FIELDS = ['name_std', 'postcode_std', 'vat_std', 'compno_std', 'sort_std', 'acct_std', 'iban_std']


# ═════════════════════════════════════════════════════════════════════════════
# LOADING (read-only reuse of the dashboard's frames, or the module's dummy set)
# ═════════════════════════════════════════════════════════════════════════════

def load_inputs(frames=None, source='dashboard'):
    if source == 'dummy':
        return _load_dummy()
    frames = frames or {}
    po = frames.get('apoheader')
    if po is None:
        # Tab-scoped runs (e.g. run_dashboard.py suppliers) don't load POs, but open POs keep a
        # supplier in scope. Load them with the dashboard's own loader (honours the data version).
        try:
            from dashboard.data_engine import load_data
            po = load_data(tab='po').get('apoheader')
        except Exception as exc:
            print(f'Migration Scope: could not load PO header ({exc}); open POs will not be counted')
    return {
        'master': frames.get('asuheader', pd.DataFrame()),
        'open_trans': frames.get('asutrans', pd.DataFrame()),
        'history': frames.get('asuhistr', pd.DataFrame()),
        'po': po if po is not None else pd.DataFrame(),
        'source': 'Live extract (dashboard data)',
    }


def _load_dummy():
    d = config.DUMMY_DIR
    if not (d / 'supplier_master_HOC.csv').exists():
        from migration_scope.dummy.generate import generate
        generate()

    def read(stem, houses=('HOC', 'HOL')):
        parts = []
        for h in houses:
            p = d / f'{stem}_{h}.csv'
            if p.exists():
                parts.append(pd.read_csv(p, dtype=str, keep_default_na=True).assign(house=h))
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

    out = {'master': read('supplier_master'), 'open_trans': read('supplier_open_trans'),
           'history': read('supplier_history'), 'po': read('po_header', ('HOC',)),
           'source': 'Dummy dataset (edge cases)'}
    for k, cols in {'master': ['last_update', 'expired_date', 'last_trans_date'],
                    'open_trans': ['trans_date', 'due_date', 'voucher_date'],
                    'history': ['trans_date', 'voucher_date'], 'po': ['order_date']}.items():
        for c in cols:
            if c in out[k]:
                out[k][c] = pd.to_datetime(out[k][c], errors='coerce')
    for k in ('open_trans', 'history'):
        for c in ('amount', 'rest_amount'):
            if c in out[k]:
                out[k][c] = pd.to_numeric(out[k][c], errors='coerce')
    return out


# ═════════════════════════════════════════════════════════════════════════════
# PIPELINE
# ═════════════════════════════════════════════════════════════════════════════

class Result:
    """Everything one run produces. All frames are keyed by entity_key (House|supplier ID)."""

    def __init__(self, **kw):
        self.__dict__.update(kw)

    def entity(self, key):
        e = self.entities[self.entities['entity_key'] == key]
        return None if e.empty else e.iloc[0]


def _col(df, c, default=np.nan):
    return df[c] if c in df else pd.Series(default, index=df.index)


def _clean_ids(df):
    df = df.copy()
    for c in ('apar_id', 'client', 'voucher_no', 'order_id'):
        if c in df:
            df[c] = std.text(df[c])
    return df


def _months_ago(as_of, months):
    return as_of - pd.DateOffset(months=int(months))


def _fy(d):
    if pd.isna(d):
        return ''
    y = d.year if d.month >= 4 else d.year - 1
    return f'FY{y}/{(y + 1) % 100:02d}'


def _prefix_lookup(ids: pd.Series, mapping: dict):
    """Longest matching prefix -> label, else ''."""
    out = pd.Series('', index=ids.index)
    for p in sorted(mapping, key=len):
        out = out.where(~ids.str.startswith(p), mapping[p])
    return out


def standardise(master: pd.DataFrame, params) -> pd.DataFrame:
    m = _clean_ids(master)
    for c in MASTER_FIELDS:
        if c not in m:
            m[c] = np.nan
    m['status'] = std.text(m['status']).str.upper()
    m['record_key'] = m['house'] + '|' + m['client'] + '|' + m['apar_id']
    m['entity_key'] = m['house'] + '|' + m['apar_id']
    m['name_std'] = std.name(m['apar_name'])
    m['name_core'] = std.name_core(m['apar_name'])
    m['postcode_std'] = std.postcode(m['zip_code'])
    m['vat_std'] = std.vat(m['vat_reg_no'])
    m['compno_std'] = std.company_no(m['comp_reg_no'])
    m['sort_std'] = std.digits(m['clearing_code'])
    acct = std.digits(m['bank_account'])
    m['acct_std'] = acct.where(~acct.isin(params['placeholder_bank_accounts']) & ~acct.str.fullmatch(r'0*'), '')
    m['iban_std'] = std.iban(m['iban'])
    bank = (m['sort_std'] + ':' + m['acct_std']).where((m['sort_std'] != '') & (m['acct_std'] != ''), '')
    m['k_bank'] = bank.where(bank != '', m['iban_std'])
    m['k_vat'] = m['vat_std'].where(m['vat_std'].str.fullmatch(r'\d{9}(\d{3})?'), '')
    m['k_company_no'] = m['compno_std'].where(m['compno_std'].str.len().ge(6) & ~m['compno_std'].str.fullmatch(r'0*'), '')
    m['k_name_postcode'] = (m['name_std'] + '@' + m['postcode_std']).where(
        (m['name_std'] != '') & (m['postcode_std'] != ''), '')
    return m


_EVIDENCE_SKIP = {'status', 'house', 'apar_id', 'client'}


def _evidence(hit: pd.DataFrame, fields) -> pd.Series:
    """The values each failing row holds in the fields its test looks at,
    e.g. 'comp_reg_no: ABC123 · country_code: GB'. Blanks show as '(blank)'."""
    fields = [f for f in fields if f in hit.columns and f not in _EVIDENCE_SKIP]
    if not fields or hit.empty:
        return pd.Series('', index=hit.index, dtype=object)
    parts = [f + ': ' + std.text(hit[f]).replace('', '(blank)') for f in fields]
    out = parts[0]
    for p in parts[1:]:
        out = out + ' · ' + p
    return out


def _issues(rows: pd.DataFrame, params):
    """Existing DQA supplier tests (reused as-is, keyed by their test ID) plus
    the engine's own, run on the in-population client rows."""
    from dashboard.core.rules.ap_rules import get_ap_checks
    from dashboard.data_engine import get_check_columns
    check_cols = get_check_columns()
    out, errors = [], []
    blocking = set(params['blocking_tests'])
    test_df = rows.copy()
    for col in ('vat_reg_no', 'comp_reg_no', 'bank_account', 'clearing_code', 'iban', 'swift', 'address', 'place',
                'zip_code', 'province', 'terms_id', 'pay_method', 'currency', 'apar_name'):
        test_df[col] = test_df[col].where(~std.blank(test_df[col]), np.nan)
    for c in get_ap_checks():
        test_id, dim, sev, desc, table, fn = c[0], c[3], c[4], c[5], c[8], c[11]
        if table != 'asuheader' or test_id in params['ignored_tests'] or fn.__code__.co_argcount != 1:
            continue
        try:
            mask = fn(test_df).fillna(False).astype(bool)
        except Exception as exc:          # a test that can't run on this data is reported, not fatal
            errors.append(f'{test_id}: {exc}')
            continue
        hit = test_df[mask]
        out.append(pd.DataFrame({'record_key': hit['record_key'], 'entity_key': hit['entity_key'],
                                 'client': hit['client'], 'test_id': test_id,
                                 'dimension': 'Duplicate' if dim == 'Uniqueness' else dim,
                                 'severity': sev, 'description': desc, 'source': 'DQA test',
                                 'evidence': _evidence(rows.loc[hit.index], check_cols.get(test_id, []))}))

    def own(mask, test_id, detail=None, fields=()):
        dim, sev, desc = _OWN_TESTS[test_id]
        hit = test_df[mask]
        out.append(pd.DataFrame({'record_key': hit['record_key'], 'entity_key': hit['entity_key'],
                                 'client': hit['client'], 'test_id': test_id, 'dimension': dim, 'severity': sev,
                                 'description': desc if detail is None else detail[mask], 'source': 'Scope engine',
                                 'evidence': _evidence(rows.loc[hit.index], fields)}))

    own(std.blank(rows['apar_name']), 'MS-DQ-NAME', fields=['apar_name'])
    org = rows['name_std'].str.contains(r'\b(?:LTD|PLC|LLP)\b', regex=True)
    own(org & (rows['compno_std'] == ''), 'MS-DQ-LTD-COMPNO', fields=['apar_name', 'comp_reg_no'])

    # CA and CM rows of the same supplier that disagree
    multi = rows[rows.duplicated('entity_key', keep=False)]
    if not multi.empty:
        fields = {'k_bank': 'bank details', 'vat_std': 'VAT number', 'compno_std': 'company number',
                  'name_std': 'name', 'postcode_std': 'postcode'}
        raw_of = {'k_bank': ['clearing_code', 'bank_account'], 'vat_std': ['vat_reg_no'], 'compno_std': ['comp_reg_no'],
                  'name_std': ['apar_name'], 'postcode_std': ['zip_code']}
        diff, shown = {}, {}
        for f, label in fields.items():
            n = multi.groupby('entity_key')[f].nunique()
            for k in n[n > 1].index:
                diff.setdefault(k, []).append(label)
                shown.setdefault(k, []).extend(raw_of[f])
        mask = rows['entity_key'].isin(diff) & rows.duplicated('entity_key', keep='first').eq(False)
        detail = rows['entity_key'].map(lambda k: 'CA and CM hold different ' + ', '.join(diff.get(k, [])))
        own(mask, 'MS-DQ-CLIENT-DIFF', detail)
        # Evidence: each client's value for every field that differs
        sub = multi[multi['entity_key'].isin(diff)]
        ev = {k: ' · '.join(f"{c} {f}: {std.text(pd.Series([r[f]])).iloc[0] or '(blank)'}"
                            for f in shown[k] for c, r in zip(g['client'], g.to_dict('records')))
              for k, g in sub.groupby('entity_key')}
        out[-1]['evidence'] = out[-1]['entity_key'].map(ev).fillna('')

    issues = pd.concat(out, ignore_index=True) if out else pd.DataFrame(
        columns=['record_key', 'entity_key', 'client', 'test_id', 'dimension', 'severity', 'description', 'source',
                 'evidence'])
    issues['blocking'] = issues['test_id'].isin(blocking)
    return issues, errors


def _categorise(ent: pd.DataFrame, params):
    house, grp, ids = ent['house'], std.text(ent['apar_gr_id']), ent['apar_id']
    cat = pd.Series('Commercial', index=ent.index)
    detail = pd.Series('', index=ent.index)
    rule = pd.Series('', index=ent.index)
    by_group = pd.Series('', index=ent.index)
    by_prefix = pd.Series('', index=ent.index)
    for h in ('HOC', 'HOL'):
        hm = house == h
        by_group[hm] = grp[hm].map(params['noncommercial_groups'].get(h, {})).fillna('')
        by_prefix[hm] = _prefix_lookup(ids[hm], params['noncommercial_id_prefixes'].get(h, {}))
    nc_g, nc_p = by_group != '', by_prefix != ''
    cat[nc_g | nc_p] = 'Non-commercial'
    detail[nc_p] = by_prefix[nc_p]
    detail[nc_g] = by_group[nc_g]
    rule[nc_p] = 'MS-CAT-02'
    rule[nc_g] = 'MS-CAT-01'
    for h, groups in params['policy_groups'].items():
        pm = (house == h) & grp.isin(groups) & ~(nc_g | nc_p)
        cat[pm], detail[pm], rule[pm] = 'Policy', grp[pm].map(groups), 'MS-CAT-03'
    individual = pd.Series(False, index=ent.index)
    for h, groups in params['individual_groups'].items():
        individual |= (house == h) & grp.isin(groups)
    check = house.isin(params['group_id_check_houses'])
    mismatch = check & (nc_g != nc_p)
    return cat, detail, rule, individual, mismatch, by_group, by_prefix


def evaluate(inputs, params, decisions: pd.DataFrame, as_of, cache=None):
    """One pass of the pipeline. decisions = effective decisions (may be empty).
    cache holds the steps that don't depend on decisions, shared between passes."""
    cache = {} if cache is None else cache
    as_of = pd.Timestamp(as_of).normalize()
    dec = decisions if decisions is not None else pd.DataFrame()
    if dec.empty:
        dec = pd.DataFrame(columns=['target_type', 'target_key', 'related_key', 'decision', 'family', 'recorded_at',
                                    'steward', 'reason', 'recommendation', 'record_label'])

    # ── Raw + standardised ───────────────────────────────────────────────────
    if 'm' not in cache:
        cache['m'] = standardise(inputs['master'], params)
    m = cache['m']
    client_ok = pd.Series(False, index=m.index)
    for h, cl in params['clients'].items():
        client_ok |= (m['house'] == h) & m['client'].isin(cl)
    m = m[client_ok].copy()
    legacy = m['apar_name'].astype(str).str.strip().str.upper().isin(params['legacy_excluded_names'])
    for h, prefixes in params['legacy_excluded_id_prefixes'].items():
        if prefixes:
            legacy |= (m['house'] == h) & m['apar_id'].str.startswith(tuple(prefixes))
    m['legacy_excluded'] = legacy
    m['status_ok'] = m['status'].isin(params['in_scope_statuses'])
    m['row_in_pop'] = m['status_ok'] & ~legacy

    # ── Entities: one row per House + supplier ID ────────────────────────────
    order = m.assign(_n=(m['status'] == 'N').astype(int), _p=m['row_in_pop'].astype(int)) \
             .sort_values(['entity_key', '_p', '_n', 'client'], ascending=[True, False, False, True])
    ent = order.drop_duplicates('entity_key').drop(columns=['_n', '_p']).reset_index(drop=True)
    g = m.groupby('entity_key')
    # Most suppliers sit under one client: only group the ones with CA and CM rows
    multi = m[m.duplicated('entity_key', keep=False)].sort_values('client')
    clients = m.set_index('entity_key')['client'].copy()
    statuses = (m['client'] + ': ' + m['status']).set_axis(m['entity_key'])
    if not multi.empty:
        mg = multi.groupby('entity_key')
        clients = pd.concat([clients[~clients.index.isin(multi['entity_key'])],
                             mg['client'].agg(lambda s: ', '.join(dict.fromkeys(s)))])
        statuses = pd.concat([statuses[~statuses.index.isin(multi['entity_key'])],
                              (multi['client'] + ': ' + multi['status']).groupby(multi['entity_key']).agg(' · '.join)])
    ent['clients'] = ent['entity_key'].map(clients)
    ent['client_statuses'] = ent['entity_key'].map(statuses)
    ent['in_population'] = ent['entity_key'].map(g['row_in_pop'].any())
    ent['last_movement'] = ent['entity_key'].map(g['last_trans_date'].max()) if 'last_trans_date' in m else pd.NaT
    ent['last_movement'] = pd.to_datetime(ent['last_movement'], errors='coerce')
    pop_rows = m[m['row_in_pop']]

    # ── Activity: invoices / credit notes (history + open) and POs ───────────
    act_types = set(params['activity_voucher_types'])
    trans_parts = []
    for k in ('history', 'open_trans'):
        t = inputs.get(k, pd.DataFrame())
        if t is not None and not t.empty:
            t = _clean_ids(t)
            t = t[t['voucher_type'].astype(str).str.strip().isin(act_types)]
            trans_parts.append(t.assign(entity_key=t['house'] + '|' + t['apar_id'])[
                ['entity_key', 'trans_date', 'voucher_no', 'voucher_type']])
    if trans_parts:
        tr = pd.concat(trans_parts).dropna(subset=['trans_date']).sort_values('trans_date')
        last_inv = tr.drop_duplicates('entity_key', keep='last').set_index('entity_key')
    else:
        last_inv = pd.DataFrame(columns=['trans_date', 'voucher_no', 'voucher_type'])
    ent['last_invoice_date'] = ent['entity_key'].map(last_inv['trans_date'])
    ent['last_invoice_ref'] = ent['entity_key'].map(
        (last_inv['voucher_type'].astype(str) + ' ' + last_inv['voucher_no'].astype(str)) if len(last_inv) else {})

    po = inputs.get('po', pd.DataFrame())
    if po is not None and not po.empty:
        po = _clean_ids(po)
        po['entity_key'] = po['house'] + '|' + po['apar_id']
        po['order_date'] = pd.to_datetime(po['order_date'], errors='coerce')
        po_last = po.dropna(subset=['order_date']).sort_values('order_date').drop_duplicates('entity_key', keep='last') \
                    .set_index('entity_key')
        po_open = po[po['status'].astype(str).str.strip().isin(params['open_po_statuses'])]
        ent['last_po_date'] = ent['entity_key'].map(po_last['order_date'])
        ent['last_po_ref'] = ent['entity_key'].map(po_last['order_id'])
        ent['open_pos'] = ent['entity_key'].map(po_open.groupby('entity_key').size()).fillna(0).astype(int)
    else:
        po_open = pd.DataFrame(columns=['entity_key', 'order_id', 'order_date', 'status'])
        ent['last_po_date'], ent['last_po_ref'], ent['open_pos'] = pd.NaT, '', 0
    for c in ('last_invoice_date', 'last_po_date'):
        ent[c] = pd.to_datetime(ent[c], errors='coerce')
    ent['last_activity'] = ent[['last_invoice_date', 'last_po_date']].max(axis=1)

    # ── Open items (grouped per voucher) ─────────────────────────────────────
    ot = inputs.get('open_trans', pd.DataFrame())
    items = pd.DataFrame(columns=['item_key', 'entity_key', 'client', 'voucher_no', 'voucher_type', 'trans_date',
                                  'due_date', 'rest_amount', 'amount', 'ext_inv_ref'])
    if ot is not None and not ot.empty:
        ot = _clean_ids(ot)
        ot['entity_key'] = ot['house'] + '|' + ot['apar_id']
        ot = ot[ot['entity_key'].isin(ent['entity_key'])]
        for c in ('ext_inv_ref', 'due_date', 'amount'):
            if c not in ot:
                ot[c] = np.nan
        items = ot.groupby(['house', 'client', 'apar_id', 'entity_key', 'voucher_no'], as_index=False).agg(
            voucher_type=('voucher_type', 'first'), trans_date=('trans_date', 'min'), due_date=('due_date', 'min'),
            rest_amount=('rest_amount', 'sum'), amount=('amount', 'sum'), ext_inv_ref=('ext_inv_ref', 'first'))
        items = items[items['rest_amount'].round(2) != 0]
        items['item_key'] = items['house'] + '|' + items['client'] + '|' + items['apar_id'] + '|' + items['voucher_no']
    items = items.copy()
    items['age_days'] = (as_of - pd.to_datetime(items['trans_date'])).dt.days
    items['stuck'] = pd.to_datetime(items['trans_date']) < _months_ago(as_of, params['stuck_item_months'])
    items['fy'] = items['trans_date'].map(_fy)
    item_dec = dec[dec['family'] == 'item'].set_index('target_key')
    items['decision'] = items['item_key'].map(item_dec['decision']).fillna('')
    items['item_status'] = np.select(
        [items['decision'] == 'MIGRATE', items['decision'] == 'DONT_MIGRATE', items['stuck']],
        ['Migrate (steward)', "Don't migrate (steward)", 'Needs review'], 'Recent: no action')
    counted = items[items['decision'] != 'DONT_MIGRATE']
    ent['open_items'] = ent['entity_key'].map(counted.groupby('entity_key').size()).fillna(0).astype(int)
    ent['open_balance'] = ent['entity_key'].map(counted.groupby('entity_key')['rest_amount'].sum()).fillna(0.0)
    ent['stuck_items'] = ent['entity_key'].map(items[items['stuck']].groupby('entity_key').size()).fillna(0).astype(int)
    ent['stuck_undecided'] = ent['entity_key'].map(
        items[items['stuck'] & (items['decision'] == '')].groupby('entity_key').size()).fillna(0).astype(int)
    all_items = items.groupby('entity_key').size()
    dont = items[items['decision'] == 'DONT_MIGRATE'].groupby('entity_key').size()
    ent['all_items_dont_migrate'] = ent['entity_key'].map(dont.reindex(all_items.index).fillna(0) == all_items).eq(True)
    ent['has_open'] = (ent['open_items'] > 0) | (ent['open_pos'] > 0)

    # ── Categorisation ───────────────────────────────────────────────────────
    cat, cat_detail, cat_rule, individual, mismatch, by_group, by_prefix = _categorise(ent, params)
    ent['category'], ent['category_detail'], ent['category_rule'] = cat, cat_detail, cat_rule
    ent['individual'] = individual
    ent.loc[~ent['in_population'], 'category'] = ''

    # ── Data quality issues ──────────────────────────────────────────────────
    if 'issues' not in cache:
        cache['issues'] = _issues(pop_rows, params)
    issues, test_errors = cache['issues']
    issues = issues.copy()
    pop_ent = ent[ent['in_population']]
    mm = pop_ent[mismatch[ent['in_population']]]
    if not mm.empty:
        d = mm.apply(lambda r: f"Group {r['apar_gr_id']} says "
                               f"{by_group[r.name] or 'trading supplier'} but ID range says "
                               f"{by_prefix[r.name] or 'trading supplier'}", axis=1)
        issues = pd.concat([issues, pd.DataFrame({
            'record_key': mm['record_key'], 'entity_key': mm['entity_key'], 'client': mm['client'],
            'test_id': 'MS-DQ-GROUP-ID', 'dimension': 'Consistency', 'severity': 'Medium', 'description': d,
            'source': 'Scope engine', 'blocking': False,
            'evidence': 'apar_gr_id: ' + std.text(mm['apar_gr_id']) + ' · apar_id: ' + mm['apar_id'].astype(str)})],
            ignore_index=True)
    per = issues.drop_duplicates(['entity_key', 'test_id'])
    ent['issues'] = ent['entity_key'].map(per.groupby('entity_key').size()).fillna(0).astype(int)
    ent['blocking'] = ent['entity_key'].map(per[per['blocking']].groupby('entity_key').size()).fillna(0).astype(int)
    for dim in ('Completeness', 'Validity', 'Consistency'):
        ent[f'has_{dim.lower()}'] = ent['entity_key'].isin(per[per['dimension'] == dim]['entity_key'])
    fields = ['vat_reg_no', 'comp_reg_no', 'bank_account', 'address', 'zip_code', 'place', 'terms_id', 'pay_method']
    ent['completeness'] = sum((~std.blank(ent[f])).astype(int) for f in fields)

    # ── Duplicates ───────────────────────────────────────────────────────────
    commercial = ent[ent['in_population'] & (ent['category'] == 'Commercial')]
    not_dup = set(dec[(dec['family'] == 'dup') & (dec['decision'] == 'NOT_DUPLICATE')]['target_key'])
    key_cols = [f'k_{k}' for k in params['duplicate_keys']]
    krows = pop_rows[pop_rows['entity_key'].isin(commercial['entity_key'])].rename(columns={'entity_key': 'key'})
    pairs_all = key_matches(krows[['key', 'house'] + key_cols], key_cols)
    if not pairs_all.empty:
        pairs_all['house_a'] = pairs_all['a'].str.split('|').str[0]
        pairs_all['house_b'] = pairs_all['b'].str.split('|').str[0]
        pairs_all['key_type'] = pairs_all['key_type'].str[2:]
    else:
        pairs_all = pd.DataFrame(columns=['a', 'b', 'key_type', 'value', 'house_a', 'house_b'])
    same_house = pairs_all[pairs_all['house_a'] == pairs_all['house_b']]
    xhouse = pairs_all[pairs_all['house_a'] != pairs_all['house_b']].copy()
    grouping = same_house if not params['cross_house_as_duplicate'] else pairs_all
    grouping = grouping[~grouping['a'].isin(not_dup) & ~grouping['b'].isin(not_dup)]
    pair_dec = dec[dec['family'] == 'pair']
    same_sup = pair_dec[pair_dec['decision'] == 'SAME_SUPPLIER'][['target_key', 'related_key']]
    extra = [(a, b) for a, b in same_sup.itertuples(index=False) if a not in not_dup and b not in not_dup]
    group_of = build_groups(sorted(set(commercial['entity_key']) - not_dup), grouping, extra)
    ent['dup_group'] = ent['entity_key'].map(group_of).fillna('')

    reasons = {}
    steward_pairs = pd.DataFrame(extra, columns=['a', 'b']).assign(key_type='steward', value='')
    for a, b, kt, val in pd.concat([grouping[['a', 'b', 'key_type', 'value']], steward_pairs]).itertuples(index=False):
        if group_of.get(a) and group_of.get(a) == group_of.get(b):
            label, ref = _KEY_LABELS[kt]
            suffix = f' [{ref}]' if ref else ''
            reasons.setdefault(a, set()).add(f'{label} as {b}{suffix}')
            reasons.setdefault(b, set()).add(f'{label} as {a}{suffix}')
    ent['match_reasons'] = ent['entity_key'].map(lambda k: '; '.join(sorted(reasons.get(k, []))))

    # Preferred record per group
    ent['preferred'] = False
    ent['group_confirmed'] = False
    ent['confirmed_at'] = pd.NaT
    ent['preferred_rank'] = 0
    ent['preferred_tie'] = False
    confirm = dec[(dec['family'] == 'dup') & (dec['decision'] == 'CONFIRM_PREFERRED')]
    grouped = ent[ent['dup_group'] != ''].copy()
    if not grouped.empty:
        grouped['_act'] = grouped['last_activity'].fillna(pd.Timestamp('1900-01-01'))
        grouped = grouped.sort_values(['dup_group', 'blocking', 'has_open', '_act', 'completeness', 'apar_id'],
                                      ascending=[True, True, False, False, False, True])
        grouped['preferred_rank'] = grouped.groupby('dup_group').cumcount() + 1
        # Records level with the best on every criterion: the rules don't choose, a steward does
        crit = ['blocking', 'has_open', '_act', 'completeness']
        best = grouped[grouped['preferred_rank'] == 1].set_index('dup_group')[crit]
        level = (grouped[crit] == best.reindex(grouped['dup_group']).set_axis(grouped.index)).all(axis=1)
        counts = grouped.loc[level, 'dup_group'].value_counts()
        tied_groups = set(counts[counts > 1].index)
        grouped.loc[level, 'preferred_rank'] = 1
        pref = grouped[(grouped['preferred_rank'] == 1) & ~grouped['dup_group'].isin(tied_groups)] \
            .set_index('dup_group')['entity_key'].to_dict()
        tie_keys = set(grouped.loc[level & grouped['dup_group'].isin(tied_groups), 'entity_key'])
        for gid, rows in confirm[confirm['target_key'].isin(grouped['entity_key'])].assign(
                g=lambda d: d['target_key'].map(group_of)).groupby('g'):
            latest = rows.sort_values('recorded_at').iloc[-1]
            pref[gid] = latest['target_key']
            ent.loc[ent['dup_group'] == gid, 'group_confirmed'] = True
            ent.loc[ent['dup_group'] == gid, 'confirmed_at'] = pd.Timestamp(latest['recorded_at'])
        ent.loc[ent['entity_key'].isin(pref.values()), 'preferred'] = True
        unresolved = tied_groups - set(confirm['target_key'].map(group_of).dropna())
        ent['preferred_tie'] = ent['entity_key'].isin(tie_keys) & ent['dup_group'].isin(unresolved)
        ent['preferred_rank'] = ent['entity_key'].map(grouped.set_index('entity_key')['preferred_rank']).fillna(0) \
            .astype(int)
    ent['group_size'] = ent['dup_group'].map(ent[ent['dup_group'] != ''].groupby('dup_group').size()).fillna(0) \
        .astype(int)

    # Possible duplicates
    # Name similarity is computed once; decisions and groups only filter the pairs
    if 'poss' not in cache:
        cache['poss'] = possible_pairs(commercial.rename(columns={'entity_key': 'key'})[['key', 'house', 'name_core']],
                                       params['possible_duplicate_similarity'])
    decided_pairs = set(map(tuple, pair_dec[['target_key', 'related_key']].values))
    poss = cache['poss']
    keep = [(a, b) not in decided_pairs and a not in not_dup and b not in not_dup
            and not (group_of.get(a) and group_of.get(a) == group_of.get(b)) for a, b in zip(poss['a'], poss['b'])]
    poss = poss[keep] if len(poss) else poss
    poss_any = set(poss['a']) | set(poss['b'])
    ent['possible_dup'] = ent['entity_key'].isin(poss_any)

    # Cross-House matches
    xl = {}
    for a, b, kt in xhouse[['a', 'b', 'key_type']].itertuples(index=False):
        xl.setdefault(a, set()).add(f'{_KEY_LABELS[kt][0]} as {b}')
        xl.setdefault(b, set()).add(f'{_KEY_LABELS[kt][0]} as {a}')
    ent['cross_house'] = ent['entity_key'].map(lambda k: '; '.join(sorted(xl.get(k, []))))

    # ── Classification ───────────────────────────────────────────────────────
    dormant_cut = _months_ago(as_of, params['dormancy_months'])
    monitor_cut = _months_ago(as_of, params['monitor_months'])
    active = ent['last_activity'] >= dormant_cut
    recent = ent['last_activity'] >= monitor_cut
    for c in ('in_population', 'legacy_excluded', 'preferred', 'preferred_tie', 'has_open'):   # keep bool dtype on empty extracts
        ent[c] = ent[c].astype(bool)
    tie = ent['preferred_tie']
    in_grp_np = (ent['dup_group'] != '') & ~ent['preferred'] & ~tie
    pop = ent['in_population']
    cls = np.select(
        [~pop & ent['legacy_excluded'], ~pop,
         ent['category'] == 'Non-commercial', ent['category'] == 'Policy',
         ~active & ~ent['has_open'], tie,
         in_grp_np & (recent | ent['has_open']), in_grp_np,
         ent['blocking'] > 0],
        [OUT_OF_SCOPE, OUT_OF_SCOPE, HOLD_NONCOMMERCIAL, HOLD_POLICY, CLOSE, MONITOR, MONITOR, CLOSE, FIX], KEEP)
    rule = np.select(
        [~pop, ent['category'] != 'Commercial', ~active & ~ent['has_open'] & ent['all_items_dont_migrate'],
         ~active & ~ent['has_open'], tie, in_grp_np & (recent | ent['has_open']), in_grp_np, ent['blocking'] > 0],
        ['MS-POP-01', ent['category_rule'], 'MS-TRN-02', 'MS-CLS-01', 'MS-DUP-03', 'MS-CLS-03', 'MS-CLS-02',
         'MS-CLS-04'],
        'MS-CLS-05')
    ent['classification'] = cls
    ent['class_rule'] = rule

    # ── Steward decisions on the record ──────────────────────────────────────
    scope_dec = dec[dec['family'] == 'scope'].set_index('target_key')
    ent['decision'] = ent['entity_key'].map(scope_dec['decision']).fillna('')
    ent['decision_by'] = ent['entity_key'].map(scope_dec['steward']).fillna('')
    ent['decision_at'] = ent['entity_key'].map(scope_dec['recorded_at']).fillna('')
    ent['decision_reason'] = ent['entity_key'].map(scope_dec['reason']).fillna('')
    ent['decision_recommendation'] = ent['entity_key'].map(scope_dec['recommendation']).fillna('')
    base = ent['classification'].copy()
    d = ent['decision']
    keepish = np.where(ent['blocking'] > 0, FIX, KEEP)
    final = base.copy()
    final = final.where(~((d == 'KEEP') & pop), pd.Series(keepish, index=ent.index))
    final = final.where(~((d == 'CLOSE') & pop), CLOSE)
    final = final.where(~((d == 'ACCEPT_AS_IS') & pop & (base == FIX)), KEEP)
    ent['classification'] = final
    ent['overridden'] = (final != base) & (d != '')

    pending = []
    for r in ent[['classification', 'decision', 'dup_group', 'group_confirmed', 'possible_dup', 'stuck_undecided',
                  'in_population', 'class_rule']].itertuples(index=False):
        p = []
        if r.in_population:
            # A Close that follows from the steward's own item decisions needs no second confirmation
            if r.classification in (CLOSE, MONITOR, FIX) + tuple(HELD) and not r.decision                     and r.class_rule != 'MS-TRN-02':
                p.append('Confirm classification')
            if r.dup_group and not r.group_confirmed:
                p.append('Confirm preferred record')
            if r.possible_dup:
                p.append('Review possible duplicate')
            if r.stuck_undecided:
                p.append(f'{r.stuck_undecided} stuck open item' + ('s' if r.stuck_undecided > 1 else ''))
        pending.append('; '.join(p))
    ent['pending'] = pending
    ent['decision_status'] = np.select(
        [ent['overridden'], ent['pending'] != '', (ent['decision'] != '') | (ent['class_rule'] == 'MS-TRN-02')],
        [OVERRIDDEN, AWAITING, DECIDED], NO_DECISION_NEEDED)

    # ── Follow-through against Unit4 ─────────────────────────────────────────
    intent_close = (d == 'CLOSE') | ((d == 'AGREE') & (ent['decision_recommendation'] == CLOSE))
    intent_keep = d.isin(['KEEP', 'WILL_FIX', 'ACCEPT_AS_IS']) | (
        (d == 'AGREE') & ent['decision_recommendation'].isin(IN_SCOPE))
    ent['follow_through'] = np.select(
        [intent_close & ~pop, intent_close & pop, intent_keep & ~pop],
        ['Actioned in Unit4', 'Not yet actioned in Unit4', 'Conflict: closed in Unit4 against a Keep decision'], '')
    used_after = in_grp_np & ent['group_confirmed'] & (ent['last_activity'] > ent['confirmed_at'])
    ent['alert'] = np.where(used_after, 'Non-preferred supplier used after the preferred record was confirmed', '')

    # Decided entities that are now missing from the extract altogether
    gone = dec[(dec['family'] == 'scope') & (dec['target_type'] == 'record') & ~dec['target_key'].isin(ent['entity_key'])]
    if not gone.empty:
        ghost = pd.DataFrame({
            'entity_key': gone['target_key'], 'house': gone['target_key'].str.split('|').str[0],
            'apar_id': gone['target_key'].str.split('|').str[1], 'apar_name': gone['record_label'],
            'classification': NOT_IN_EXTRACT, 'class_rule': '', 'in_population': False, 'decision': gone['decision'],
            'decision_by': gone['steward'], 'decision_at': gone['recorded_at'], 'decision_reason': gone['reason'],
            'follow_through': 'Not in latest extract', 'decision_status': DECIDED})
        ent = pd.concat([ent, ghost], ignore_index=True)
    for c in ('open_items', 'open_pos', 'issues', 'blocking', 'stuck_items', 'stuck_undecided', 'group_size',
              'completeness'):
        ent[c] = ent[c].fillna(0).astype(int)
    for c in ('dup_group', 'cross_house', 'pending', 'alert', 'category', 'category_detail', 'match_reasons',
              'clients', 'client_statuses', 'follow_through', 'last_invoice_ref', 'last_po_ref'):
        ent[c] = ent[c].fillna('')
    for c in ('possible_dup', 'preferred', 'individual', 'overridden', 'group_confirmed', 'in_population',
              'has_completeness', 'has_validity', 'has_consistency'):
        ent[c] = ent[c].fillna(False).astype(bool)
    ent['has_duplicate'] = (ent['dup_group'] != '') | ent['possible_dup']
    ent['in_scope'] = ent['classification'].isin(IN_SCOPE)

    return dict(raw=m, entities=ent, issues=issues, items=items, open_pos=po_open, possible=poss,
                xhouse=xhouse, test_errors=test_errors)


def _trail(e, params, as_of):
    """Plain-English route the record took to its classification, step by step."""
    steps = []
    fmt = lambda d: d.strftime('%d %b %Y') if pd.notna(d) else 'none'

    def add(rule_id, ok, text):
        steps.append({'rule': rule_id, 'result': ok, 'text': text})

    if not e['in_population']:
        add('MS-POP-01', 'stop', f"Not in the population: status {e.get('client_statuses', '')}. "
                                 'Only N and P suppliers are migrated.')
        return steps
    add('MS-POP-01', 'pass', f"In the population: {e['client_statuses']}")
    if e['category'] != 'Commercial':
        add(e['category_rule'], 'stop', f"{e['category']}: {e['category_detail']}. Held for a policy decision, "
                                        'not classified.')
        return steps
    add('MS-CAT-01', 'pass', 'Commercial supplier' + (' (individual contractor: a decision is needed on their '
                                                      'treatment)'
                                                      if e['individual'] else ''))
    cut = _months_ago(as_of, params['dormancy_months'])
    act = (f"Last activity {fmt(e['last_activity'])}"
           + (f" ({e['last_invoice_ref']})" if pd.notna(e['last_invoice_date']) and
              e['last_activity'] == e['last_invoice_date'] else
              (f" (PO {e['last_po_ref']})" if pd.notna(e['last_activity']) else '')))
    opens = f"{e['open_items']} open items, {e['open_pos']} open POs"
    if pd.isna(e['last_activity']) or e['last_activity'] < cut:
        if not e['has_open']:
            extra = " All open items were marked don't migrate." if e['all_items_dont_migrate'] else ''
            add(e['class_rule'], 'fail', f"Dormant: {act}, before {fmt(cut)} ({params['dormancy_months']} months), "
                                         f"and nothing open.{extra} Recommended Close.")
            return steps
        add('MS-CLS-01', 'pass', f"{act}, older than {params['dormancy_months']} months, but kept because it has "
                                 f'{opens}.')
    else:
        add('MS-CLS-01', 'pass', f"Active: {act}, within {params['dormancy_months']} months. {opens}.")
    if e['dup_group']:
        if e.get('preferred_tie'):
            add('MS-DUP-03', 'fail', f"Level with another record in duplicate group {e['dup_group']} on blocking "
                                     'issues, open items, activity and completeness, so the rules do not pick a '
                                     'preferred record. Monitor until a steward chooses.')
            return steps
        if e['preferred']:
            how = 'confirmed by a steward' if e['group_confirmed'] else 'proposed by the engine'
            add('MS-DUP-03', 'pass', f"Preferred record of duplicate group {e['dup_group']} ({how}).")
        else:
            mcut = _months_ago(as_of, params['monitor_months'])
            if e['class_rule'] == 'MS-CLS-03':
                why = (f"used within the last {params['monitor_months']} months (last activity "
                       f"{fmt(e['last_activity'])})" if pd.notna(e['last_activity']) and e['last_activity'] >= mcut
                       else f"still has {opens}")
                add('MS-CLS-03', 'fail', f"Non-preferred member of {e['dup_group']}, but {why}. Monitor: it can be "
                                         f"closed once it has nothing open and no activity for "
                                         f"{params['monitor_months']} months.")
            else:
                add('MS-CLS-02', 'fail', f"Non-preferred member of {e['dup_group']} with no activity since "
                                         f"{fmt(mcut)} ({params['monitor_months']} months). Recommended Close.")
            return steps
    else:
        add('MS-DUP-01', 'pass', 'Not in a duplicate group.')
    if e['blocking']:
        add('MS-CLS-04', 'fail', f"{e['blocking']} blocking data issue(s). Fix before migration.")
    else:
        add('MS-CLS-05', 'pass', 'No blocking data issues. Keep.')
    return steps


def _reason_tags(ent):
    """Short tags for what lies behind each record's position, e.g. 'Validity, Duplicate'."""
    def tags(e):
        if e['classification'] == NOT_IN_EXTRACT:
            return ['Not in extract']
        if not e['in_population']:
            return ['Legacy exclusion' if e.get('legacy_excluded') is True else 'Closed in Unit4']
        out = []
        if e['category_rule'] in ('MS-CAT-01', 'MS-CAT-02'):
            out.append('Non-commercial')
        if e['category_rule'] == 'MS-CAT-03':
            out.append('Policy')
        if e['individual']:
            out.append('Individual contractor')
        if e['class_rule'] in ('MS-CLS-01', 'MS-TRN-02'):
            out.append('Dormant')
        if e['dup_group']:
            out.append('Duplicate')
        if e['possible_dup']:
            out.append('Possible duplicate')
        out += [d for d in ('Validity', 'Completeness', 'Consistency') if e[f'has_{d.lower()}']]
        if e['stuck_items']:
            out.append('Stuck item')
        if e['cross_house']:
            out.append('Cross-House')
        return out or ['Active']
    cols = ['classification', 'in_population', 'legacy_excluded', 'category_rule', 'individual', 'class_rule',
            'dup_group', 'possible_dup', 'has_validity', 'has_completeness', 'has_consistency', 'stuck_items',
            'cross_house']
    return [', '.join(tags(e)) for e in ent.reindex(columns=cols).to_dict('records')]


def run(inputs, params, decisions, as_of=None):
    """Run the pipeline twice: once on the rules alone (the recommendation) and
    once with steward decisions applied (the final position)."""
    as_of = pd.Timestamp(as_of or pd.Timestamp.today()).normalize()
    cache = {}
    rec = evaluate(inputs, params, None, as_of, cache)
    fin = evaluate(inputs, params, decisions, as_of, cache)
    ent = fin['entities']
    ent['recommended'] = ent['entity_key'].map(rec['entities'].set_index('entity_key')['classification']) \
        .fillna(ent['classification'])
    ent['recommended_rule'] = ent['entity_key'].map(rec['entities'].set_index('entity_key')['class_rule']) \
        .fillna('')
    ent['reasons'] = _reason_tags(ent)
    ent['fingerprint'] = [hashlib.md5(json.dumps([str(a), int(o), int(p), int(b), g, bool(i)]).encode()).hexdigest()[:12]
                          for a, o, p, b, g, i in zip(ent['last_activity'], ent['open_items'], ent['open_pos'],
                                                      ent['blocking'], ent['dup_group'], ent['in_population'])]

    # Which rules fired on each record (drives the rule cards)
    fired = []
    for e in ent.itertuples(index=False):
        k = e.entity_key
        if e.in_population:
            fired.append((k, 'MS-POP-01'))
            fired.append((k, 'MS-POP-02'))
            if e.category_rule:
                fired.append((k, e.category_rule))
            if e.individual:
                fired.append((k, 'MS-CAT-04'))
            if e.recommended_rule and e.recommended_rule.startswith(('MS-CLS', 'MS-TRN')):
                fired.append((k, e.recommended_rule))
            if e.dup_group:
                fired.append((k, 'MS-DUP-01'))
                if e.preferred or e.preferred_tie:
                    fired.append((k, 'MS-DUP-03'))
            if e.possible_dup:
                fired.append((k, 'MS-DUP-02'))
            if e.cross_house:
                fired.append((k, 'MS-XH-01'))
            if e.stuck_items:
                fired.append((k, 'MS-TRN-01'))
        elif e.legacy_excluded is True:
            fired.append((k, 'MS-POP-03'))
    fired = pd.DataFrame(fired, columns=['entity_key', 'rule_id']).drop_duplicates()

    return Result(object=OBJECT, as_of=as_of, params=params, source=inputs.get('source', ''),
                  rules=RULES, fired=fired, trail=lambda e: _trail(e, params, as_of),
                  recommended_entities=rec['entities'], **fin)


def funnel(entities: pd.DataFrame, raw: pd.DataFrame, house=None):
    """Counts per stage for the overview. Out-of-population rows are counted from raw."""
    e = entities if house is None else entities[entities['house'] == house]
    real = e[e['classification'] != NOT_IN_EXTRACT]
    pop = real[real['in_population']]
    commercial = pop[pop['category'] == 'Commercial']
    counts = real['classification'].value_counts()
    return {
        'unit4': len(real),
        'closed_terminated': int((~real['in_population'] & ~real['legacy_excluded'].fillna(False).astype(bool)).sum()),
        'legacy': int((~real['in_population'] & real['legacy_excluded'].fillna(False).astype(bool)).sum()),
        'population': len(pop),
        'noncommercial': int(counts.get(HOLD_NONCOMMERCIAL, 0)),
        'policy': int(counts.get(HOLD_POLICY, 0)),
        'classified': len(commercial),
        KEEP: int(counts.get(KEEP, 0)), FIX: int(counts.get(FIX, 0)),
        MONITOR: int(counts.get(MONITOR, 0)), CLOSE: int((commercial['classification'] == CLOSE).sum()),
        'in_scope': int(real['in_scope'].sum()),
    }
