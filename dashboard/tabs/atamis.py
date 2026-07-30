"""
Parliament Finance Systems Programme
Atamis / Unit4-via-Atamis — Contracts & Procurement Reconciliation
====================================================================
Atamis is Parliament's procurement/contracts system. Two of its four extracts
are Atamis's own data (contracts, suppliers); the other two are Unit4 views of
the same contract spend, pulled in for reconciliation. Unlike every other
domain, none of these four files are split into HOC/HOL extracts — house is
derived post-load (see _derive_atamis_houses in data_engine.py) by
cross-referencing the Unit4 supplier master, and atamis_contracts carries a
third 'Joint' category from its own Organisation field.
"""

from dash import html, dcc
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from dashboard.core.theme import DISPLAY_FONT, HOUSE_HEX, PLOTLY_HOVER_CONFIG
from dashboard.shared.dimensions import render_dimension_scorecard, render_dimension_grid

# ── Design tokens — dark navy + Parliament green, distinct from every other tab ──
_HDR_BG    = '#0a1628'
_HDR2_BG   = '#0f2a44'
_ACCENT    = '#00703c'   # Parliament green (matches HOC house color)
_ACCENT_LT = '#28a367'
_NAVY      = '#1e3a5f'   # matches HOUSE_HEX['Joint']
_WARN_C    = '#d97706'
_CRIT_C    = '#c0392b'
_CARD_BG   = '#ffffff'
_CARD_BOR  = '#e2e8f0'
_TRACK      = '#e8f0f6'
_TRACK_DARK = '#16324d'

_ORG_ORDER  = ['HOC', 'HOL', 'Joint']
_ORG_COLORS = {'HOC': HOUSE_HEX['HOC'], 'HOL': HOUSE_HEX['HOL'], 'Joint': _NAVY, 'Unknown': HOUSE_HEX['Unknown']}

# Excluded from the Unresolved Records section only (per direct request) —
# these are largely tautological for a contract that's already unresolved:
# a blank Contract Reference or an invalid Organisation value is very often
# the exact reason the contract couldn't be resolved to a house in the first
# place, so flagging it again under Unknown mostly restates the Organisation
# Field Reliability card's own 'No Reference' signal rather than adding new
# information. Still scored normally for HOC/HOL, where they're meaningful.
_UNRESOLVED_EXCLUDED_CHECKS = {
    'ATAMIS_CONTRACT_NO_SUPPLIER', 'ATAMIS_CONTRACT_NO_REF',
    'ATAMIS_CONTRACT_NO_DATES', 'ATAMIS_CONTRACT_ORG_INVALID',
}


# ── Formatters ────────────────────────────────────────────────────────────────

def _fmt_val(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return '—'
    sign = '−' if v < 0 else ''
    a = abs(v)
    if a >= 1_000_000_000:
        return f'{sign}£{a / 1_000_000_000:.2f}bn'
    if a >= 1_000_000:
        return f'{sign}£{a / 1_000_000:.1f}m'
    if a >= 1_000:
        return f'{sign}£{a / 1_000:.0f}k'
    return f'{sign}£{a:,.0f}'


def _fmt_count(v):
    if v >= 1_000_000:
        return f'{v / 1_000_000:.1f}m'
    if v >= 1_000:
        return f'{v / 1_000:.1f}k'
    return f'{v:,}'


def _badge(text, bg, color='#f4f0fc'):
    return html.Span(text, style={
        'background': bg, 'color': color,
        'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.1em',
        'padding': '3px 9px', 'borderRadius': '4px',
        'textTransform': 'uppercase', 'display': 'inline-block',
    })


def _section_div(title, subtitle=''):
    return html.Div(style={
        'borderTop': '1px solid #e2e8f0',
        'margin': '4px 0 20px',
        'paddingTop': '20px',
        'display': 'flex', 'alignItems': 'center', 'gap': '12px',
    }, children=[
        html.Div(title, style={'fontSize': '15px', 'fontWeight': '700', 'color': '#1e293b'}),
        html.Span(subtitle, style={'fontSize': '11px', 'color': '#94a3b8'}) if subtitle else None,
    ])


def _stat_box(value, label, color=None, sub=None):
    accent = color or '#e2e8f0'
    return html.Div(style={
        'flex': '1', 'minWidth': '150px',
        'background': _CARD_BG, 'border': f'1px solid {_CARD_BOR}',
        'borderTop': f'3px solid {accent}',
        'borderRadius': '10px', 'padding': '16px 18px',
        'boxShadow': '0 2px 6px rgba(0,0,0,0.03)',
    }, children=[
        html.Div(value, style={
            'fontSize': '24px', 'fontWeight': '800', 'color': color or '#1e293b',
            'fontFamily': DISPLAY_FONT, 'lineHeight': '1',
        }),
        html.Div(label, style={
            'fontSize': '10px', 'fontWeight': '700', 'color': '#94a3b8',
            'textTransform': 'uppercase', 'letterSpacing': '0.07em', 'marginTop': '8px',
        }),
        html.Div(sub, style={'fontSize': '11px', 'color': '#64748b', 'marginTop': '3px'}) if sub else None,
    ])


def _card(title, subtitle, children, flex=None):
    return html.Div(style={
        'background': _CARD_BG, 'border': f'1px solid {_CARD_BOR}',
        'borderRadius': '12px', 'padding': '20px 24px',
        'boxShadow': '0 2px 8px rgba(0,0,0,0.04)',
        **({'flex': flex} if flex else {}),
    }, children=[
        html.Div(title, style={'fontSize': '13px', 'fontWeight': '700', 'color': '#1e293b', 'marginBottom': '4px'}),
        html.Div(subtitle, style={'fontSize': '11px', 'color': '#94a3b8', 'marginBottom': '16px'}) if subtitle else None,
        *children,
    ])


# ── Organisation Field Reliability — shared by the tab's summary crosstab and ─
# ── app.py's modal drill-down, so both use identical matching logic ──────────

def _blank_series(s):
    return s.isna() | (s.astype(str).str.strip().isin(['', 'nan', 'None']))


def org_reliability_detail(frames: dict) -> pd.DataFrame:
    """Per-contract detail behind the Organisation Field Reliability card.

    Covers EVERY Atamis contract, including ones with no Contract Reference
    at all (verdict 'No Reference') — so this frame's row totals per
    Organisation always reconcile exactly with the Contracts by Organisation
    card above it. (An earlier version silently dropped blank-reference
    contracts and only reported their count in a footnote, which is why the
    two cards' totals used to disagree by a handful of records per house —
    found directly by the user comparing the two.)

    For every contract with a populated reference, traces whether it matches
    a Unit4 Commitments record (and if so, that record's own supplier-derived
    house) and/or HOL's Contract Number GL dimension value (see
    _build_unit4_contract_refs in data_engine.py) — independent of what the
    contract's own Organisation field already says. Returns one row per
    contract with:
      _org_clean   — Organisation normalised to HOC/HOL/Joint/Unknown
      _derived     — verdict: HOC/HOL/Unknown/Conflicting/No Match/No Reference
      commitment_id, commitment_supplier_id, commitment_supplier_name,
        commitment_house — the matched Commitments record, if any
      gl_dim_match — whether contract_ref also matches HOL's GL dimension

    Module-level (not nested in _compute_metrics) specifically so app.py's
    modal drill-down callback can call get_org_reliability_records() below
    and get the exact same per-contract rows the summary counts came from.
    """
    contracts = frames.get('atamis_contracts', pd.DataFrame()).copy()
    if contracts.empty:
        return pd.DataFrame()
    if 'contract_ref' not in contracts.columns:
        contracts['contract_ref'] = None

    _org_map = {'HOC': 'HOC', 'HOL': 'HOL', 'JOINT': 'Joint'}
    contracts['_org_clean'] = contracts['organisation'].astype(str).str.strip().str.upper().map(_org_map).fillna('Unknown')

    blank_ref = _blank_series(contracts['contract_ref'])
    contracts['_ref_clean'] = contracts['contract_ref'].astype(str).str.strip()
    contracts.loc[blank_ref, '_ref_clean'] = None

    contracts['commitment_id'] = None
    contracts['commitment_supplier_id'] = None
    contracts['commitment_supplier_name'] = None
    contracts['commitment_house'] = None
    contracts['gl_dim_match'] = False
    contracts['_derived'] = 'No Match'
    contracts.loc[blank_ref, '_derived'] = 'No Reference'

    no_ref_rows = contracts[blank_ref]
    with_ref = contracts[~blank_ref].copy()

    unit4_refs = frames.get('unit4_contract_refs', pd.DataFrame())
    if unit4_refs.empty or 'u4_contract_id' not in unit4_refs.columns or with_ref.empty:
        return pd.concat([no_ref_rows, with_ref], ignore_index=True)

    refs = unit4_refs[~_blank_series(unit4_refs['u4_contract_id'])].copy()
    refs['_ref_clean'] = refs['u4_contract_id'].astype(str).str.strip()

    commit_extra_cols = [c for c in ['supplier_id', 'supplier_name'] if c in refs.columns]
    commit_side = (
        refs[refs['_source'] == 'unit4_commitments'][['_ref_clean', 'u4_contract_id', 'house'] + commit_extra_cols]
        .rename(columns={'u4_contract_id': 'commitment_id', 'house': 'commitment_house',
                          'supplier_id': 'commitment_supplier_id', 'supplier_name': 'commitment_supplier_name'})
        .drop_duplicates(subset=['_ref_clean'])
    )

    gl_side = refs[refs['_source'] == 'gl_dimension_values'][['_ref_clean']].drop_duplicates()
    gl_side['gl_dim_match'] = True

    with_ref = with_ref.drop(columns=['commitment_id', 'commitment_supplier_id', 'commitment_supplier_name',
                                       'commitment_house', 'gl_dim_match'])
    merged = with_ref.merge(commit_side, on='_ref_clean', how='left').merge(gl_side, on='_ref_clean', how='left')
    merged['gl_dim_match'] = merged['gl_dim_match'].eq(True)

    def _verdict(row):
        houses = set()
        if pd.notna(row.get('commitment_id')):
            houses.add(row['commitment_house'])
        if row['gl_dim_match']:
            houses.add('HOL')
        if not houses:
            return 'No Match'
        if len(houses) > 1:
            return 'Conflicting'
        return next(iter(houses))

    merged['_derived'] = merged.apply(_verdict, axis=1)
    return pd.concat([no_ref_rows, merged], ignore_index=True)


def get_org_reliability_records(frames: dict, organisation: str, verdict: str) -> pd.DataFrame:
    """Contracts behind one cell of the Organisation Field Reliability matrix
    — used by app.py's modal drill-down callback when a cell is clicked."""
    df = org_reliability_detail(frames)
    if df.empty:
        return df
    return df[(df['_org_clean'] == organisation) & (df['_derived'] == verdict)]


# ── Metric computation ────────────────────────────────────────────────────────

def _compute_metrics(frames: dict) -> dict:
    contracts   = frames.get('atamis_contracts', pd.DataFrame()).copy()
    suppliers   = frames.get('atamis_suppliers', pd.DataFrame()).copy()
    commitments = frames.get('unit4_commitments', pd.DataFrame()).copy()
    spend       = frames.get('unit4_spend', pd.DataFrame()).copy()
    asuheader   = frames.get('asuheader', pd.DataFrame())
    apodetail   = frames.get('apodetail', pd.DataFrame())

    if contracts.empty and suppliers.empty and commitments.empty:
        return {}

    today = pd.Timestamp.today()

    def _blank(s):
        return s.isna() | (s.astype(str).str.strip().isin(['', 'nan', 'None']))

    # ---- Contracts ----
    for col in ['total_award_value', 'current_value']:
        if col in contracts.columns:
            contracts[col] = pd.to_numeric(contracts[col], errors='coerce').fillna(0)

    total_contracts = len(contracts)
    total_award_value = float(contracts['total_award_value'].sum()) if 'total_award_value' in contracts.columns else 0.0
    total_current_value = float(contracts['current_value'].sum()) if 'current_value' in contracts.columns else 0.0

    # Grouped on the RAW Organisation field, not the resolved 'house' column —
    # 'house' now resolves Joint contracts down to a specific HOC/HOL/Unknown
    # for DQ purposes (see _derive_atamis_houses in data_engine.py), but this
    # chart is about what Atamis itself actually recorded, which is a
    # genuinely separate, still-useful three-way split.
    _org_map = {'HOC': 'HOC', 'HOL': 'HOL', 'JOINT': 'Joint'}
    org_clean = contracts['organisation'].astype(str).str.strip().str.upper().map(_org_map).fillna('Unknown')
    org_mix = (
        contracts.assign(_org_clean=org_clean).groupby('_org_clean').agg(
            contract_count=('_org_clean', 'size'),
            total_value=('total_award_value', 'sum'),
        ).reindex(_ORG_ORDER + ['Unknown']).fillna(0).reset_index().rename(columns={'_org_clean': 'house'})
    )

    # ---- Organisation field reliability ----
    # Does the raw Organisation field (HOC/HOL/Joint) agree with what the
    # underlying data actually implies — checked independently for EVERY
    # contract, not just the Joint/blank ones _derive_atamis_houses resolves.
    # A contract cleanly labelled HOC or HOL can still disagree with its own
    # commitment's supplier chain or with HOL's GL Contract Number dimension;
    # that disagreement is exactly what this surfaces. The per-contract detail
    # (org_reliability_detail, module-level so app.py's modal drill-down can
    # reuse the identical matching logic) is computed once and both the
    # summary crosstab here and the modal's per-cell records come from it.
    org_detail = org_reliability_detail(frames)
    org_reliability = pd.DataFrame()
    if not org_detail.empty:
        org_reliability = pd.crosstab(org_detail['_org_clean'], org_detail['_derived'])
        org_reliability = org_reliability.reindex(index=_ORG_ORDER + ['Unknown'], fill_value=0)
        org_reliability = org_reliability.reindex(
            columns=['HOC', 'HOL', 'Unknown', 'Conflicting', 'No Match', 'No Reference'], fill_value=0
        )

    if 'end_date' in contracts.columns:
        active_mask = contracts['end_date'] >= today
        active_count = int(active_mask.sum())
        expired_count = int((~active_mask & contracts['end_date'].notna()).sum())
        no_date_count = int(contracts['end_date'].isna().sum())
        expiring_soon = contracts[active_mask & (contracts['end_date'] <= today + pd.Timedelta(days=90))]
        expiring_soon_count = int(len(expiring_soon))
    else:
        active_count = expired_count = no_date_count = expiring_soon_count = 0

    # ---- Supplier reconciliation (the flagship cross-system view) ----
    atamis_sup = suppliers[~_blank(suppliers['creditor_ref'])] if 'creditor_ref' in suppliers.columns else pd.DataFrame()
    atamis_sup_total = len(atamis_sup)
    atamis_matched = int((atamis_sup['house'] != 'Unknown').sum()) if not atamis_sup.empty else 0
    atamis_only = atamis_sup_total - atamis_matched

    unit4_total = unit4_matched = 0
    if not asuheader.empty:
        unit4_total = int(asuheader['apar_id'].nunique())
        atamis_ids = set(atamis_sup['creditor_ref'].astype(str).str.strip()) if not atamis_sup.empty else set()
        unit4_matched = int(
            asuheader[asuheader['apar_id'].astype(str).str.strip().isin(atamis_ids)]['apar_id'].nunique()
        )
    unit4_only = unit4_total - unit4_matched

    # ---- Contract <-> PO linkage (HOC only — PO is HoC-only. 'house' never
    # resolves to 'Joint' any more, see _derive_atamis_houses in data_engine.py) ----
    po_refs = set(apodetail['contract_id'].dropna().astype(str).str.strip()) if not apodetail.empty else set()
    hoc_joint = contracts[contracts['house'] == 'HOC'] if 'house' in contracts.columns else pd.DataFrame()
    hj_with_ref = hoc_joint[~_blank(hoc_joint['contract_ref'])] if not hoc_joint.empty else pd.DataFrame()
    contract_po_total = len(hj_with_ref)
    contract_po_matched = int(hj_with_ref['contract_ref'].astype(str).str.strip().isin(po_refs).sum()) if contract_po_total else 0
    contract_po_unmatched = contract_po_total - contract_po_matched

    # ---- Contract <-> Commitments linkage ----
    # Confirmed direct join on Contract Reference == Contract Id for HOC.
    # HOL has no usable Commitments extract of its own (real data resolves it
    # almost entirely to HOC), so its side of this join instead comes from the
    # Contract Number GL dimension value (agldimvalue, dim_position 5) — see
    # _build_unit4_contract_refs() in data_engine.py. unit4_contract_refs
    # combines both sources into one column shape so this reconciliation
    # matches the ATAMIS_CONTRACT_NOT_IN_COMMITMENTS / UNIT4_COMMIT_NOT_IN_CONTRACTS
    # DQ checks exactly — same source, same blank-exclusion, same membership
    # test either direction.
    unit4_refs = frames.get('unit4_contract_refs', commitments)
    commit_ids = set(unit4_refs['u4_contract_id'].dropna().astype(str).str.strip()) if 'u4_contract_id' in unit4_refs.columns else set()
    contracts_with_ref = contracts[~_blank(contracts['contract_ref'])] if 'contract_ref' in contracts.columns else pd.DataFrame()
    contract_commit_total = len(contracts_with_ref)
    contract_commit_matched = int(contracts_with_ref['contract_ref'].astype(str).str.strip().isin(commit_ids).sum()) if contract_commit_total else 0
    contract_commit_unmatched = contract_commit_total - contract_commit_matched

    contract_refs = set(contracts['contract_ref'].dropna().astype(str).str.strip()) if 'contract_ref' in contracts.columns else set()
    unit4_refs_with_id = unit4_refs[~_blank(unit4_refs['u4_contract_id'])] if 'u4_contract_id' in unit4_refs.columns else pd.DataFrame()
    commit_total_all = len(unit4_refs_with_id)
    commit_not_in_contracts = int((~unit4_refs_with_id['u4_contract_id'].astype(str).str.strip().isin(contract_refs)).sum()) if commit_total_all else 0

    value_mismatch_count = 0
    if contract_commit_matched and 'award_amount' in commitments.columns:
        cm = commitments[['u4_contract_id', 'award_amount']].drop_duplicates(subset=['u4_contract_id']).rename(columns={'u4_contract_id': 'contract_ref'})
        vm = contracts_with_ref[['contract_ref', 'total_award_value']].merge(cm, on='contract_ref', how='inner')
        a = pd.to_numeric(vm['total_award_value'], errors='coerce')
        b = pd.to_numeric(vm['award_amount'], errors='coerce')
        diff = (a - b).abs()
        tol = (a.abs() * 0.02).clip(lower=1.00)
        value_mismatch_count = int((diff > tol).sum())

    # ---- Commitments / Spend cross-checks ----
    commit_with_sup = commitments[~_blank(commitments['supplier_id'])] if 'supplier_id' in commitments.columns else pd.DataFrame()
    commit_orphan = int((commit_with_sup['house'] == 'Unknown').sum()) if not commit_with_sup.empty else 0

    spend_total = len(spend)
    spend_orphan = int((spend['house'] == 'Unknown').sum()) if 'house' in spend.columns else 0

    mismatch_count = 0
    mismatch_gap = 0.0
    if not spend.empty and not commitments.empty:
        merged = spend.merge(
            commitments[['u4_contract_id', 'posted_amount']], on='u4_contract_id', how='inner'
        )
        commit_p = pd.to_numeric(merged['posted_amount'], errors='coerce')
        spend_p = pd.to_numeric(merged['posted'], errors='coerce')
        diff = (commit_p - spend_p).abs()
        mismatch_count = int((diff > 1.00).sum())
        mismatch_gap = float(diff[diff > 1.00].sum())

    # ---- Financial totals (Commitments view) ----
    total_limit = float(pd.to_numeric(commitments.get('amount_limit', pd.Series(dtype=float)), errors='coerce').sum())
    total_committed = float(pd.to_numeric(commitments.get('committed_amount', pd.Series(dtype=float)), errors='coerce').sum())
    total_posted = float(pd.to_numeric(commitments.get('posted_amount', pd.Series(dtype=float)), errors='coerce').sum())
    total_remaining = float(pd.to_numeric(commitments.get('remaining_amount', pd.Series(dtype=float)), errors='coerce').sum())

    return {
        'total_contracts': total_contracts,
        'total_award_value': total_award_value,
        'total_current_value': total_current_value,
        'org_mix': org_mix,
        'org_reliability': org_reliability,
        'active_count': active_count,
        'expired_count': expired_count,
        'no_date_count': no_date_count,
        'expiring_soon_count': expiring_soon_count,
        'atamis_sup_total': atamis_sup_total,
        'atamis_matched': atamis_matched,
        'atamis_only': atamis_only,
        'unit4_total': unit4_total,
        'unit4_matched': unit4_matched,
        'unit4_only': unit4_only,
        'contract_po_total': contract_po_total,
        'contract_po_matched': contract_po_matched,
        'contract_po_unmatched': contract_po_unmatched,
        'contract_commit_total': contract_commit_total,
        'contract_commit_matched': contract_commit_matched,
        'contract_commit_unmatched': contract_commit_unmatched,
        'commit_not_in_contracts': commit_not_in_contracts,
        'commit_total_all': commit_total_all,
        'value_mismatch_count': value_mismatch_count,
        'commit_orphan': commit_orphan,
        'commit_total': len(commit_with_sup),
        'spend_total': spend_total,
        'spend_orphan': spend_orphan,
        'mismatch_count': mismatch_count,
        'mismatch_gap': mismatch_gap,
        'total_limit': total_limit,
        'total_committed': total_committed,
        'total_posted': total_posted,
        'total_remaining': total_remaining,
        'commitments_count': len(commitments),
    }


# ── Hero banner ───────────────────────────────────────────────────────────────

def _render_hero(m: dict) -> html.Div:
    def _secondary_stat(value, label):
        return html.Div(style={'minWidth': '110px'}, children=[
            html.Div(value, style={
                'fontSize': '22px', 'fontWeight': '800', 'color': 'rgba(255,255,255,0.92)',
                'lineHeight': '1', 'fontFamily': DISPLAY_FONT,
            }),
            html.Div(label, style={
                'fontSize': '10px', 'fontWeight': '700', 'color': 'rgba(255,255,255,0.4)',
                'textTransform': 'uppercase', 'letterSpacing': '0.1em', 'marginTop': '5px',
            }),
        ])

    return html.Div(style={
        'background': (
            f'radial-gradient(ellipse 900px 420px at 12% 8%, rgba(0,112,60,0.22), transparent 60%), '
            f'linear-gradient(155deg, {_HDR_BG}, {_HDR2_BG})'
        ),
        'borderRadius': '14px', 'padding': '34px 40px', 'marginBottom': '24px',
        'boxShadow': '0 8px 32px rgba(0,0,0,0.18)',
    }, children=[
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'marginBottom': '28px'}, children=[
            _badge('ATAMIS', '#0d3d24', '#7ee2ae'),
            _badge('Both Houses', '#12283f', '#8fc9f0'),
        ]),
        html.Div(style={'display': 'flex', 'alignItems': 'flex-end', 'gap': '48px', 'flexWrap': 'wrap'}, children=[
            html.Div(children=[
                html.Div('Total contract award value', style={
                    'fontSize': '11px', 'fontWeight': '700', 'color': 'rgba(255,255,255,0.45)',
                    'textTransform': 'uppercase', 'letterSpacing': '0.12em', 'marginBottom': '8px',
                }),
                html.Div(_fmt_val(m.get('total_award_value', 0)), style={
                    'fontSize': '52px', 'fontWeight': '800', 'color': '#ffffff',
                    'lineHeight': '1', 'fontFamily': DISPLAY_FONT, 'letterSpacing': '-1.5px',
                }),
                html.Div(style={
                    'width': '48px', 'height': '4px', 'background': _ACCENT_LT,
                    'borderRadius': '2px', 'marginTop': '14px',
                }),
            ]),
            html.Div(style={'display': 'flex', 'gap': '32px', 'paddingBottom': '6px'}, children=[
                _secondary_stat(_fmt_count(m.get('total_contracts', 0)), 'Contracts'),
                _secondary_stat(_fmt_count(m.get('atamis_sup_total', 0)), 'Atamis suppliers'),
                _secondary_stat(_fmt_count(m.get('commitments_count', 0)), 'Unit4 commitments'),
            ]),
        ]),
    ])


# ── Organisation split (HOC / HOL / Joint) ───────────────────────────────────

def _render_org_split(m: dict) -> html.Div:
    mix = m.get('org_mix')
    if mix is None or mix.empty:
        return html.Div()

    mix = mix[mix['house'].isin(_ORG_ORDER)]
    total_val = mix['total_value'].sum() or 1
    total_n = mix['contract_count'].sum() or 1

    rows = []
    for _, r in mix.iterrows():
        h = r['house']
        pct = r['total_value'] / total_val * 100
        rows.append(html.Div(style={
            'display': 'flex', 'alignItems': 'center', 'gap': '10px',
            'padding': '6px 0', 'borderBottom': '1px solid #f1f5f9',
        }, children=[
            html.Span(h, style={
                'fontSize': '10px', 'fontWeight': '800', 'color': '#fff',
                'background': _ORG_COLORS[h], 'padding': '2px 8px', 'borderRadius': '4px',
                'minWidth': '46px', 'textAlign': 'center',
            }),
            html.Div(style={'flex': '1', 'height': '8px', 'background': _TRACK, 'borderRadius': '4px', 'overflow': 'hidden'}, children=[
                html.Div(style={'height': '100%', 'width': f'{min(pct, 100):.1f}%', 'background': _ORG_COLORS[h], 'borderRadius': '4px'}),
            ]),
            html.Span(_fmt_val(r['total_value']), style={'fontSize': '12px', 'fontWeight': '700', 'color': _ORG_COLORS[h], 'minWidth': '58px', 'textAlign': 'right'}),
            html.Span(f"{int(r['contract_count']):,}", style={'fontSize': '11px', 'color': '#94a3b8', 'minWidth': '38px', 'textAlign': 'right'}),
        ]))

    return _card(
        'Contracts by Organisation', 'Number of contracts and Total Award Value by organisation',
        [
            html.Div(f'{int(total_n):,} contracts total', style={
                'fontSize': '13px', 'fontWeight': '700', 'color': '#1e293b', 'marginBottom': '12px',
            }),
            html.Div(rows),
        ],
    )


RELIABILITY_VERDICT_LABELS = {
    'HOC': 'Resolves to HOC', 'HOL': 'Resolves to HOL',
    'Unknown': 'Supplier unresolved',
    'Conflicting': 'Conflicting signals', 'No Match': 'No match either source',
    'No Reference': 'No Contract Reference',
}


def _render_org_reliability(m: dict) -> html.Div:
    tbl = m.get('org_reliability')
    if tbl is None or tbl.empty:
        return html.Div()

    def _cell_style(org, verdict, val):
        base = {'fontSize': '13px', 'fontWeight': '700', 'textAlign': 'center', 'padding': '10px 8px', 'borderBottom': '1px solid #f1f5f9'}
        if val == 0:
            # Genuinely empty — kept hollow so it visually recedes against
            # every other, filled cell below.
            return {**base, 'color': '#cbd5e1', 'background': '#f8fafc'}
        if verdict == 'Conflicting':
            return {**base, 'color': '#fff', 'background': _CRIT_C, 'borderRadius': '6px'}
        if verdict == org:
            # Organisation agrees with the underlying data.
            return {**base, 'color': '#fff', 'background': _ACCENT, 'borderRadius': '6px'}
        if verdict in ('HOC', 'HOL'):
            # Org says one house, underlying data resolves to the other — a
            # genuine label/data disagreement, not just an unresolved case.
            return {**base, 'color': '#fff', 'background': _WARN_C, 'borderRadius': '6px'}
        if verdict == 'Unknown':
            # Matched something, but that record's own supplier doesn't
            # resolve either — a genuinely different situation from No Match/
            # No Reference (there IS a link, it just dead-ends), so it gets
            # its own hue (violet) rather than another shade of grey.
            return {**base, 'color': '#fff', 'background': '#7c5cbf', 'borderRadius': '6px'}
        if verdict == 'No Match':
            # Had a reference, checked it, found nothing in either source —
            # a genuine (if inconclusive) attempt, so a distinct hue (blue)
            # rather than a shade shared with Unknown or No Reference.
            return {**base, 'color': '#fff', 'background': '#2563eb', 'borderRadius': '6px'}
        # No Reference — nothing was even attempted (no Contract Reference to
        # look up at all; see ATAMIS_CONTRACT_NO_REF). Genuinely neutral, so
        # this is the one that stays grey — but a single, solid grey rather
        # than a shade shared with the other two inconclusive outcomes.
        return {**base, 'color': '#fff', 'background': '#94a3b8', 'borderRadius': '6px'}

    header = html.Tr([
        html.Th('Organisation', style={'fontSize': '11px', 'color': '#94a3b8', 'textAlign': 'left', 'padding': '8px', 'borderBottom': f'2px solid {_CARD_BOR}'}),
    ] + [
        html.Th(RELIABILITY_VERDICT_LABELS.get(c, c), style={'fontSize': '11px', 'color': '#94a3b8', 'textAlign': 'center', 'padding': '8px', 'borderBottom': f'2px solid {_CARD_BOR}'})
        for c in tbl.columns
    ] + [
        html.Th('Total', style={'fontSize': '11px', 'color': '#94a3b8', 'textAlign': 'center', 'padding': '8px', 'borderBottom': f'2px solid {_CARD_BOR}'}),
    ])

    def _cell(org, verdict, val):
        style = _cell_style(org, verdict, val)
        if val == 0:
            return html.Td(f'{val:,}', style=style)
        # Clickable — opens the same modal used for DQ drill-downs, showing
        # the actual contracts behind this cell (see app.py's
        # handle_atamis_org_reliability_click). Only non-zero cells are
        # buttons; a 0 has nothing to drill into.
        return html.Td(
            html.Button(
                f'{val:,}',
                id={'type': 'atamis-org-rel-cell', 'org': org, 'verdict': verdict},
                n_clicks=0,
                title='Click to see the underlying contracts',
                style={
                    'background': 'transparent', 'border': 'none', 'cursor': 'pointer',
                    'font': 'inherit', 'color': 'inherit', 'width': '100%', 'padding': '0',
                },
            ),
            style=style,
        )

    rows = []
    for org in tbl.index:
        row_total = int(tbl.loc[org].sum())
        cells = [html.Td(html.Span(org, style={
            'fontSize': '11px', 'fontWeight': '800', 'color': '#fff',
            'background': _ORG_COLORS.get(org, '#64748b'), 'padding': '2px 8px', 'borderRadius': '4px',
        }), style={'padding': '10px 8px', 'borderBottom': '1px solid #f1f5f9'})]
        for verdict in tbl.columns:
            val = int(tbl.loc[org, verdict])
            cells.append(_cell(org, verdict, val))
        cells.append(html.Td(f'{row_total:,}', style={'fontSize': '13px', 'fontWeight': '700', 'color': '#334155', 'textAlign': 'center', 'padding': '10px 8px', 'borderBottom': '1px solid #f1f5f9'}))
        rows.append(html.Tr(cells))

    def _legend_item(bg, text_color, label):
        return html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '6px'}, children=[
            html.Div(style={'width': '14px', 'height': '14px', 'borderRadius': '4px', 'background': bg,
                             'border': f'1px solid {bg}' if bg != '#f8fafc' else '1px solid #e2e8f0'}),
            html.Span(label, style={'fontSize': '11px', 'color': '#64748b'}),
        ])

    legend = html.Div(style={
        'display': 'flex', 'flexWrap': 'wrap', 'gap': '16px', 'alignItems': 'center',
        'marginTop': '14px', 'paddingTop': '12px', 'borderTop': f'1px solid {_CARD_BOR}',
    }, children=[
        _legend_item(_ACCENT, '#fff', 'Agrees'),
        _legend_item(_WARN_C, '#fff', 'Disagrees'),
        _legend_item(_CRIT_C, '#fff', 'Conflicting'),
        _legend_item('#7c5cbf', '#fff', 'Unresolved'),
        _legend_item('#2563eb', '#fff', 'No match'),
        _legend_item('#94a3b8', '#fff', 'No reference'),
        html.Span('Click a cell for the underlying contracts', style={'fontSize': '11px', 'color': '#cbd5e1', 'marginLeft': 'auto'}),
    ])

    return _card(
        'Organisation Field Reliability',
        "Does Atamis's own Organisation field (HOC/HOL/Joint) agree with what the Supplier ID / Contract Number data actually implies?",
        [
            html.Table(style={'width': '100%', 'borderCollapse': 'collapse'}, children=[
                html.Thead(header), html.Tbody(rows),
            ]),
            legend,
        ],
    )


# ── Cross-system reconciliation — the flagship section ───────────────────────

def _overlap_bar(left_label, left_n, mid_label, mid_n, right_label, right_n, left_color, mid_color, right_color):
    total = (left_n + mid_n + right_n) or 1
    segs = [(left_label, left_n, left_color), (mid_label, mid_n, mid_color), (right_label, right_n, right_color)]

    bar = html.Div(style={
        'display': 'flex', 'height': '40px', 'borderRadius': '8px', 'overflow': 'hidden',
        'gap': '2px', 'marginBottom': '12px',
    }, children=[
        html.Div(style={
            'flex': str(max(n, 0.0001)), 'background': color,
            'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center',
            'minWidth': '2px',
        }, title=f'{label}: {n:,}', children=[
            html.Span(f'{n:,}', style={'color': '#fff', 'fontSize': '13px', 'fontWeight': '800'}) if n / total > 0.08 else None
        ])
        for label, n, color in segs
    ])

    legend = html.Div(style={'display': 'flex', 'gap': '20px', 'flexWrap': 'wrap'}, children=[
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '6px'}, children=[
            html.Div(style={'width': '10px', 'height': '10px', 'borderRadius': '2px', 'background': color}),
            html.Span(f'{label} ({n:,})', style={'fontSize': '11px', 'color': '#475569', 'fontWeight': '600'}),
        ])
        for label, n, color in segs
    ])

    return html.Div([bar, legend])


def _render_reconciliation(m: dict) -> html.Div:
    sup_card = _card(
        'Supplier Overlap: Atamis ↔ Unit4', 'Creditor Ref (Atamis) matched against apar_id (Unit4 supplier master, both houses)',
        [
            _overlap_bar(
                'Atamis only', m.get('atamis_only', 0),
                'Matched (both systems)', m.get('atamis_matched', 0),
                'Unit4 only', m.get('unit4_only', 0),
                HOUSE_HEX['Unknown'], _ACCENT, _NAVY,
            ),
        ],
    )

    contract_card = _card(
        'Contract Overlap: Atamis ↔ Commitments', 'Contract Reference (Atamis) matched against Contract Id (Unit4 Commitments view for HOC, GL Contract Number dimension for HOL)',
        [
            _overlap_bar(
                'Atamis only', m.get('contract_commit_unmatched', 0),
                'Matched (both systems)', m.get('contract_commit_matched', 0),
                'Unit4 only', m.get('commit_not_in_contracts', 0),
                HOUSE_HEX['Unknown'], _ACCENT, _NAVY,
            ),
        ],
    )

    overlap_row = html.Div(style={'display': 'flex', 'gap': '20px', 'flexWrap': 'wrap', 'alignItems': 'stretch'}, children=[
        html.Div(sup_card, style={'flex': '1', 'minWidth': '420px'}),
        html.Div(contract_card, style={'flex': '1', 'minWidth': '420px'}),
    ])

    return html.Div(style={'marginBottom': '24px'}, children=[overlap_row])


# ── Contract lifecycle ────────────────────────────────────────────────────────

def _render_lifecycle(m: dict) -> html.Div:
    active = m.get('active_count', 0)
    expired = m.get('expired_count', 0)
    no_date = m.get('no_date_count', 0)
    expiring = m.get('expiring_soon_count', 0)
    total = active + expired + no_date or 1

    segs = [('Active', active, _ACCENT), ('Expired', expired, '#94a3b8'), ('No end date', no_date, _CRIT_C)]

    rows = []
    for label, n, color in segs:
        pct = n / total * 100
        rows.append(html.Div(style={
            'display': 'flex', 'alignItems': 'center', 'gap': '10px', 'padding': '6px 0', 'borderBottom': '1px solid #f1f5f9',
        }, children=[
            html.Span(label, style={'fontSize': '12px', 'color': '#475569', 'minWidth': '100px'}),
            html.Div(style={'flex': '1', 'height': '8px', 'background': _TRACK, 'borderRadius': '4px', 'overflow': 'hidden'}, children=[
                html.Div(style={'height': '100%', 'width': f'{min(pct, 100):.1f}%', 'background': color, 'borderRadius': '4px', 'minWidth': '3px' if n else '0'}),
            ]),
            html.Span(f'{n:,}', style={'fontSize': '13px', 'fontWeight': '700', 'color': color, 'minWidth': '40px', 'textAlign': 'right'}),
            html.Span(f'{pct:.0f}%', style={'fontSize': '11px', 'color': '#94a3b8', 'minWidth': '34px', 'textAlign': 'right'}),
        ]))

    return _card(
        'Contract Lifecycle', 'By End Date, relative to today',
        [
            html.Div(style={'display': 'flex', 'gap': '14px', 'flexWrap': 'wrap', 'marginBottom': '18px'}, children=[
                _stat_box(f'{expiring:,}', 'Expiring within 90 days', _WARN_C, sub='Still active, renewal window closing'),
                _stat_box(f'{active:,}', 'Currently active', _ACCENT),
                _stat_box(f'{expired:,}', 'Expired', '#94a3b8'),
            ]),
            html.Div(rows),
        ],
    )


# ── Financial summary ─────────────────────────────────────────────────────────

def _render_financials(m: dict) -> html.Div:
    limit = m.get('total_limit', 0)
    committed = m.get('total_committed', 0)
    posted = m.get('total_posted', 0)
    remaining = m.get('total_remaining', 0)

    total = max(limit, 1)
    segs = [('Posted', posted, _ACCENT), ('Committed (uninvoiced)', max(committed - posted, 0), _ACCENT_LT), ('Remaining', max(remaining, 0), _TRACK)]

    rows = []
    for label, v, color in segs:
        pct = v / total * 100
        rows.append(html.Div(style={
            'display': 'flex', 'alignItems': 'center', 'gap': '10px', 'padding': '6px 0', 'borderBottom': '1px solid #f1f5f9',
        }, children=[
            html.Span(label, style={'fontSize': '12px', 'color': '#475569', 'minWidth': '170px'}),
            html.Div(style={'flex': '1', 'height': '8px', 'background': _TRACK, 'borderRadius': '4px', 'overflow': 'hidden'}, children=[
                html.Div(style={'height': '100%', 'width': f'{min(max(pct,0), 100):.1f}%', 'background': color, 'borderRadius': '4px'}),
            ]),
            html.Span(_fmt_val(v), style={'fontSize': '13px', 'fontWeight': '700', 'color': color if color != _TRACK else '#94a3b8', 'minWidth': '64px', 'textAlign': 'right'}),
        ]))

    return _card(
        'Contract Financials (Unit4 Commitments view)', f'Amount Limit totals {_fmt_val(limit)} across {m.get("commitments_count",0):,} commitments',
        [
            html.Div(rows),
        ],
    )


# ── Main renderer ─────────────────────────────────────────────────────────────

def render_tab(dq_results, frames: dict) -> html.Div:
    contracts = frames.get('atamis_contracts', pd.DataFrame())
    suppliers = frames.get('atamis_suppliers', pd.DataFrame())
    if contracts.empty and suppliers.empty:
        return html.Div(
            'No Atamis data loaded. Place contracts_report.csv, contract_total_commitments.csv, '
            'contracts_spend_details.csv, and supplier_data_report.csv in data/atamis/ then restart.',
            style={'padding': '48px', 'textAlign': 'center', 'color': '#94a3b8', 'fontSize': '14px'},
        )

    m = _compute_metrics(frames)

    # 'Unknown' is not a house — every record that couldn't be traced to a
    # real Unit4 supplier/contract/commitment at all — so it's split out of
    # the main per-house DQ scorecard/grid into its own section below. Every
    # other resolved row (including the Unit4 Commitments/Spend checks that
    # were previously reported separately as house-independent) now resolves
    # cleanly to HOC or HOL and is scored in the normal scorecard.
    if 'house' in dq_results.columns:
        resolved_dq = dq_results[dq_results['house'].isin(['HOC', 'HOL'])]
        unresolved_dq = dq_results[
            (dq_results['house'] == 'Unknown') & ~dq_results['check_id'].isin(_UNRESOLVED_EXCLUDED_CHECKS)
        ]
    else:
        resolved_dq, unresolved_dq = dq_results, dq_results.iloc[0:0]

    return html.Div(children=[

        _render_hero(m),

        html.Div(style={'marginTop': '24px', 'marginBottom': '24px'}, children=[_render_org_split(m)]),
        html.Div(style={'marginBottom': '24px'}, children=[_render_org_reliability(m)]),

        _section_div('Cross-System Reconciliation'),
        _render_reconciliation(m),

        html.Div(style={'marginBottom': '24px'}, children=[_render_lifecycle(m)]),

        _section_div('Contract Financials', 'Committed, posted, and remaining value — reconciled across both Unit4 views'),
        html.Div(style={'marginBottom': '24px'}, children=[_render_financials(m)]),

        _section_div('Data Quality Checks', 'DQ rules applied across all four Atamis / Unit4-via-Atamis extracts, scored per house'),
        render_dimension_scorecard(resolved_dq),
        render_dimension_grid(resolved_dq, key_prefix='resolved:'),

        _render_unresolved_section(unresolved_dq),

    ])


def _render_unresolved_section(unresolved_dq) -> html.Div:
    """'Unknown' isn't a third house — it's every record whose Creditor Ref,
    Supplier ID, or Contract Reference couldn't be matched to a real Unit4
    record in either house at all. Reporting it inside the same HOC/HOL
    scorecard misrepresents it as a peer category with its own comparable DQ
    score. Instead it gets its own section, reusing the same scorecard/grid
    components (so the visual language stays consistent) under framing that
    makes clear these are unresolved records to investigate, not a segment
    of the migration population to score alongside HOC and HOL."""
    if unresolved_dq is None or unresolved_dq.empty:
        return html.Div()

    return html.Div(children=[
        _section_div(
            'Unresolved Records',
            "Could not be matched to a Unit4 supplier, contract, or commitment in either house",
        ),
        render_dimension_scorecard(unresolved_dq),
        render_dimension_grid(unresolved_dq, key_prefix='unresolved:'),
    ])
