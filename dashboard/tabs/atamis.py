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


# ── Metric computation ────────────────────────────────────────────────────────

def _compute_metrics(frames: dict) -> dict:
    contracts   = frames.get('atamis_contracts', pd.DataFrame()).copy()
    suppliers   = frames.get('atamis_suppliers', pd.DataFrame()).copy()
    commitments = frames.get('atamis_commitments', pd.DataFrame()).copy()
    spend       = frames.get('atamis_spend', pd.DataFrame()).copy()
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

    if 'end_date' in contracts.columns:
        active_mask = contracts['end_date'] >= today
        active_count = int(active_mask.sum())
        expired_count = int((~active_mask & contracts['end_date'].notna()).sum())
        no_date_count = int(contracts['end_date'].isna().sum())
        expiring_soon = contracts[active_mask & (contracts['end_date'] <= today + pd.Timedelta(days=90))]
        expiring_soon_count = int(len(expiring_soon))
    else:
        active_count = expired_count = no_date_count = expiring_soon_count = 0

    top_contracts = (
        contracts[contracts['total_award_value'] > 0]
        .nlargest(15, 'total_award_value')[['contract_title', 'supplier_name', 'total_award_value', 'house']]
        if 'total_award_value' in contracts.columns and not contracts.empty else pd.DataFrame()
    )

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

    # ---- Contract <-> Commitments linkage (any house — confirmed direct join
    # on Contract Reference == Contract Id) ----
    commit_ids = set(commitments['u4_contract_id'].dropna().astype(str).str.strip()) if 'u4_contract_id' in commitments.columns else set()
    contracts_with_ref = contracts[~_blank(contracts['contract_ref'])] if 'contract_ref' in contracts.columns else pd.DataFrame()
    contract_commit_total = len(contracts_with_ref)
    contract_commit_matched = int(contracts_with_ref['contract_ref'].astype(str).str.strip().isin(commit_ids).sum()) if contract_commit_total else 0
    contract_commit_unmatched = contract_commit_total - contract_commit_matched

    contract_refs = set(contracts['contract_ref'].dropna().astype(str).str.strip()) if 'contract_ref' in contracts.columns else set()
    commit_total_all = len(commitments)
    commit_not_in_contracts = int((~commitments['u4_contract_id'].astype(str).str.strip().isin(contract_refs)).sum()) if commit_total_all else 0

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
    overspend_count = int((pd.to_numeric(commitments.get('remaining_amount', pd.Series(dtype=float)), errors='coerce') < -1).sum())
    total_spend_posted = float(pd.to_numeric(spend.get('posted', pd.Series(dtype=float)), errors='coerce').sum())

    return {
        'total_contracts': total_contracts,
        'total_award_value': total_award_value,
        'total_current_value': total_current_value,
        'org_mix': org_mix,
        'active_count': active_count,
        'expired_count': expired_count,
        'no_date_count': no_date_count,
        'expiring_soon_count': expiring_soon_count,
        'top_contracts': top_contracts,
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
        'total_spend_posted': total_spend_posted,
        'overspend_count': overspend_count,
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
        html.Div(style={
            'marginTop': '26px', 'paddingTop': '18px',
            'borderTop': '1px solid rgba(255,255,255,0.08)',
            'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'flexWrap': 'wrap', 'gap': '8px',
        }, children=[
            html.Span('Atamis (procurement) reconciled against Unit4 (Agresso) — see Cross-System Reconciliation below', style={
                'fontSize': '11px', 'color': 'rgba(255,255,255,0.35)',
            }),
            html.Span('Single combined extract — house derived, not filename-split', style={
                'fontSize': '12px', 'fontWeight': '600', 'color': 'rgba(255,255,255,0.55)',
            }),
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

    fig = go.Figure(data=[go.Pie(
        labels=mix['house'], values=mix['contract_count'], hole=0.62,
        marker=dict(colors=[_ORG_COLORS[h] for h in mix['house']], line=dict(color='#ffffff', width=2)),
        textinfo='label+percent', textfont=dict(size=11, color='#334155'),
        hovertemplate='<b>%{label}</b><br>%{value:,.0f} contracts (%{percent})<extra></extra>',
        sort=False,
    )])
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(t=10, b=10, l=10, r=10), height=220, showlegend=False,
        font=dict(family="'Inter', sans-serif"),
        annotations=[dict(text=_fmt_count(int(total_n)), showarrow=False,
                           font=dict(size=18, color='#1e293b', family=DISPLAY_FONT))],
    )

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
        'Contracts by Organisation', 'Only Atamis dataset carrying a genuine three-way HOC / HOL / Joint split',
        [
            html.Div(style={'display': 'flex', 'gap': '24px', 'alignItems': 'center', 'flexWrap': 'wrap'}, children=[
                html.Div(dcc.Graph(figure=fig, config=PLOTLY_HOVER_CONFIG, style={'height': '220px', 'width': '220px'}), style={'flex': '0 0 220px'}),
                html.Div(style={'flex': '1', 'minWidth': '280px'}, children=rows),
            ]),
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


def _reconciliation_stat(value, label, sublabel, color):
    return html.Div(style={
        'flex': '1', 'minWidth': '190px',
        'background': _CARD_BG, 'border': f'1px solid {_CARD_BOR}',
        'borderRadius': '12px', 'padding': '18px 20px',
        'borderLeft': f'4px solid {color}',
        'boxShadow': '0 2px 8px rgba(0,0,0,0.04)',
    }, children=[
        html.Div(value, style={'fontSize': '26px', 'fontWeight': '800', 'color': color, 'fontFamily': DISPLAY_FONT, 'lineHeight': '1'}),
        html.Div(label, style={'fontSize': '12px', 'fontWeight': '700', 'color': '#1e293b', 'marginTop': '8px'}),
        html.Div(sublabel, style={'fontSize': '11px', 'color': '#94a3b8', 'marginTop': '3px'}),
    ])


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
            html.Div('Atamis-only suppliers exist in procurement records with no counterpart Unit4 supplier ever created. '
                     'Unit4-only suppliers transact in Agresso but were never registered in Atamis — common for payroll, tax, and individual-type suppliers, but still worth a second look.',
                     style={'fontSize': '11px', 'color': '#64748b', 'marginTop': '10px', 'lineHeight': '1.6'}),
        ],
    )

    contract_card = _card(
        'Contract Overlap: Atamis ↔ Commitments', 'Contract Reference (Atamis) matched directly against Contract Id (Unit4 Commitments view)',
        [
            _overlap_bar(
                'Atamis only', m.get('contract_commit_unmatched', 0),
                'Matched (both systems)', m.get('contract_commit_matched', 0),
                'Unit4 only', m.get('commit_not_in_contracts', 0),
                HOUSE_HEX['Unknown'], _ACCENT, _NAVY,
            ),
            html.Div('Atamis-only contracts may simply be newly awarded with no financial activity posted yet. '
                     'Unit4-only commitments are more surprising — a financial commitment should trace back to a real contract record.',
                     style={'fontSize': '11px', 'color': '#64748b', 'marginTop': '10px', 'lineHeight': '1.6'}),
        ],
    )

    overlap_row = html.Div(style={'display': 'flex', 'gap': '20px', 'flexWrap': 'wrap', 'alignItems': 'stretch'}, children=[
        html.Div(sup_card, style={'flex': '1', 'minWidth': '420px'}),
        html.Div(contract_card, style={'flex': '1', 'minWidth': '420px'}),
    ])

    stat_row = html.Div(style={'display': 'flex', 'gap': '16px', 'flexWrap': 'wrap', 'marginTop': '16px'}, children=[
        _reconciliation_stat(
            f"{m.get('contract_po_unmatched', 0):,}", 'Contracts with no matching PO',
            f"of {m.get('contract_po_total', 0):,} HOC contracts checked", _WARN_C,
        ),
        _reconciliation_stat(
            f"{m.get('value_mismatch_count', 0):,}", 'Award value disagrees with Unit4',
            f"of {m.get('contract_commit_matched', 0):,} matched contracts", _WARN_C,
        ),
        _reconciliation_stat(
            f"{m.get('commit_orphan', 0):,}", 'Commitments with unknown supplier',
            f"of {m.get('commit_total', 0):,} commitment records", _CRIT_C,
        ),
        _reconciliation_stat(
            f"{m.get('spend_orphan', 0):,}", 'Spend records with no matching contract',
            f"of {m.get('spend_total', 0):,} spend records", _CRIT_C,
        ),
        _reconciliation_stat(
            f"{m.get('mismatch_count', 0):,}", 'Commitments vs Spend disagree',
            f"{_fmt_val(m.get('mismatch_gap', 0))} total gap across matched contracts", _WARN_C,
        ),
    ])

    return html.Div(style={'marginBottom': '24px'}, children=[overlap_row, stat_row])


# ── Top contracts by value ────────────────────────────────────────────────────

def _render_top_contracts(m: dict) -> html.Div:
    tc = m.get('top_contracts')
    if tc is None or tc.empty:
        return html.Div()

    tc = tc.sort_values('total_award_value', ascending=True)
    labels = tc['contract_title'].astype(str).str.slice(0, 55).tolist()
    values = tc['total_award_value'].tolist()
    colors = [_ORG_COLORS.get(h, '#94a3b8') for h in tc['house']]
    suppliers = tc['supplier_name'].fillna('—').tolist()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=labels, x=values, orientation='h',
        marker=dict(color=colors, opacity=0.9, line=dict(width=0)),
        customdata=suppliers,
        hovertemplate='<b>%{y}</b><br>%{customdata}<br>£%{x:,.0f}<extra></extra>',
        text=[_fmt_val(v) for v in values],
        textposition='outside', textfont=dict(size=10, color='#475569'),
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(t=10, b=30, l=10, r=80), height=max(340, len(labels) * 26), bargap=0.25,
        xaxis=dict(showgrid=True, gridcolor='#f1f5f9', tickfont=dict(size=10, color='#94a3b8'), zeroline=False),
        yaxis=dict(showgrid=False, tickfont=dict(size=11, color='#475569')),
        showlegend=False, font=dict(family="'Inter', sans-serif"),
    )

    legend = html.Div(style={'display': 'flex', 'gap': '16px', 'marginTop': '8px'}, children=[
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '6px'}, children=[
            html.Div(style={'width': '10px', 'height': '10px', 'borderRadius': '2px', 'background': _ORG_COLORS[h]}),
            html.Span(h, style={'fontSize': '11px', 'color': '#475569', 'fontWeight': '600'}),
        ]) for h in _ORG_ORDER
    ])

    return _card(
        'Top 15 Contracts by Award Value', 'Bar color denotes Organisation (HOC / HOL / Joint)',
        [dcc.Graph(figure=fig, config=PLOTLY_HOVER_CONFIG, style={'height': f'{max(340, len(labels) * 26)}px'}), legend],
    )


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
    overspend = m.get('overspend_count', 0)
    spend_posted = m.get('total_spend_posted', 0)

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
            html.Div(style={'display': 'flex', 'gap': '14px', 'flexWrap': 'wrap', 'marginTop': '18px'}, children=[
                _stat_box(f'{overspend:,}', 'Contracts overspent', _CRIT_C, sub='Posted exceeds authorised limit'),
                _stat_box(_fmt_val(spend_posted), 'Spend Details view — total posted', _NAVY, sub='Second Unit4 view, for comparison'),
                _stat_box(_fmt_val(posted - spend_posted), 'Views\' net difference', _WARN_C if abs(posted - spend_posted) > 1 else _ACCENT),
            ]),
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

    # 'Unknown' is not a house — see _render_unresolved_section below — so it's
    # split out of the main per-house DQ scorecard/grid entirely.
    if 'house' in dq_results.columns:
        resolved_dq = dq_results[dq_results['house'].isin(['HOC', 'HOL'])]
        unresolved_dq = dq_results[dq_results['house'] == 'Unknown']
    else:
        resolved_dq, unresolved_dq = dq_results, dq_results.iloc[0:0]

    return html.Div(children=[

        _render_hero(m),

        _section_div('Contracts by Organisation', 'Atamis contract data spans both houses plus a Joint category'),
        html.Div(style={'marginBottom': '24px'}, children=[_render_org_split(m)]),

        _section_div('Cross-System Reconciliation', 'Where Atamis (procurement) and Unit4 (Agresso) agree — and where they don\'t'),
        _render_reconciliation(m),

        _section_div('Contract Value & Lifecycle', 'Highest-value contracts and where each sits in its lifecycle'),
        html.Div(style={'display': 'flex', 'gap': '20px', 'flexWrap': 'wrap', 'marginBottom': '24px', 'alignItems': 'stretch'}, children=[
            html.Div(style={'flex': '3', 'minWidth': '420px'}, children=[_render_top_contracts(m)]),
            html.Div(style={'flex': '2', 'minWidth': '340px'}, children=[_render_lifecycle(m)]),
        ]),

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
        html.Div(style={
            'background': '#f8fafc', 'border': f'1px solid {_CARD_BOR}', 'borderLeft': f'4px solid {HOUSE_HEX["Unknown"]}',
            'borderRadius': '10px', 'padding': '14px 18px', 'marginBottom': '18px',
        }, children=[
            html.Div(
                "'Unknown' is not a third house — it's the absence of a resolvable one. Every record below has a "
                "Creditor Ref, Supplier ID, or Contract Reference that didn't match anything in the Unit4 supplier "
                "master (or, for contracts, a Joint contract whose supplier name couldn't be matched either). "
                "Investigate the underlying identifier for each before assuming which house it actually belongs to — "
                "the checks below are about the record's own data quality, not a per-house comparison.",
                style={'fontSize': '12px', 'color': '#475569', 'lineHeight': '1.6'},
            ),
        ]),
        render_dimension_scorecard(unresolved_dq),
        render_dimension_grid(unresolved_dq, key_prefix='unresolved:'),
    ])
