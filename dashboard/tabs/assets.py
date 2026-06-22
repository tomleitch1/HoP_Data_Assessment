from dash import html
import pandas as pd
from dashboard.shared.dimensions import render_dimension_scorecard, render_dimension_grid, render_dimensions_table
from dashboard.core.theme import UI, HOUSE_HEX, DISPLAY_FONT

# ── Design tokens (warm amber) ─────────────────────────────────────────────────
_HDR     = '#1f1a0f'
_HDR2    = '#181408'
_SEQ_BG  = '#3d2d0a'
_AST_BG  = '#150f04'
_SEQ_TXT = '#e8b86a'
_AST_TXT = '#7a6030'
_BODY_BG = '#ffffff'
_BAR_BG  = '#f5eedc'
_DIV     = '#3a2f18'

_CONFIRMED_TYPES = {'CA', 'PC', 'ND', 'ED', 'FD', 'SA', 'VN', 'CI'}
_UNKNOWN_TYPES   = {'NF', 'NT', 'TF', 'TT', 'RF', 'RT', 'OS', 'WU', 'TC'}

_METHOD_COLORS = {
    'LNA': '#1a7a4a', 'LNB': '#3a7abf',
    'MAN': '#c07820', 'NOD': '#7c5cbf',
    'LIN': '#1a7a4a', 'BAL': '#3a7abf',
    'EXP': '#c07820', 'SYD': '#7c5cbf',
}


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _badge(text, bg, color='#f8f0e0'):
    return html.Span(text, style={
        'background': bg, 'color': color,
        'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.08em',
        'padding': '2px 8px', 'borderRadius': '4px',
        'textTransform': 'uppercase', 'display': 'inline-block', 'lineHeight': '1.6',
    })


def _status_badge(confirmed):
    if confirmed:
        return html.Span('Confirmed', style={
            'background': '#1a7a4a', 'color': '#ffffff',
            'fontSize': '10px', 'fontWeight': '700', 'letterSpacing': '0.06em',
            'padding': '2px 9px', 'borderRadius': '4px',
            'textTransform': 'uppercase',
        })
    return html.Span('Pending clarification', style={
        'background': '#c07820', 'color': '#ffffff',
        'fontSize': '10px', 'fontWeight': '700', 'letterSpacing': '0.06em',
        'padding': '2px 9px', 'borderRadius': '4px',
        'textTransform': 'uppercase',
    })


def _table_chip(name):
    return html.Span(name, style={
        'fontSize': '10px', 'color': '#c09060',
        'fontFamily': "'Courier New', monospace",
        'background': '#0f0a04', 'padding': '2px 7px', 'borderRadius': '3px',
    })


def _section_label(text):
    return html.Div(text, style={
        'fontSize': '10px', 'fontWeight': '700', 'color': UI['text_secondary'],
        'textTransform': 'uppercase', 'letterSpacing': '0.08em', 'marginBottom': '8px',
    })


def _kv(label, value, value_color=None):
    """Key/value row used inside card bodies."""
    return html.Div(style={
        'display': 'flex', 'justifyContent': 'space-between',
        'alignItems': 'baseline', 'padding': '3px 0',
    }, children=[
        html.Span(label, style={'fontSize': '11px', 'color': UI['text_secondary']}),
        html.Span(f'{value:,}' if isinstance(value, int) else str(value), style={
            'fontSize': '13px', 'fontWeight': '700', 'fontFamily': DISPLAY_FONT,
            'color': value_color or UI['text_primary'],
        }),
    ])


def _bar_row(code, count, total, color):
    pct = (count / total * 100) if total > 0 else 0
    return html.Div(style={
        'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'padding': '3px 0',
    }, children=[
        html.Span(code, style={
            'background': color + '1a', 'color': color,
            'fontSize': '10px', 'fontWeight': '800',
            'padding': '1px 6px', 'borderRadius': '3px',
            'minWidth': '34px', 'textAlign': 'center', 'flexShrink': '0',
        }),
        html.Div(style={
            'flex': '1', 'height': '5px', 'background': _BAR_BG,
            'borderRadius': '3px', 'overflow': 'hidden',
        }, children=[
            html.Div(style={
                'height': '100%', 'width': f'{min(pct,100):.1f}%',
                'background': color, 'borderRadius': '3px',
                'minWidth': '3px' if count > 0 else '0',
            })
        ]),
        html.Span(f'{count:,}', style={
            'fontSize': '11px', 'fontWeight': '700',
            'minWidth': '44px', 'textAlign': 'right',
            'color': UI['text_primary'], 'flexShrink': '0',
        }),
    ])


# ── Data extraction ────────────────────────────────────────────────────────────

def get_asset_intro_data(frames):
    am = frames.get('asset_master',      pd.DataFrame())
    ad = frames.get('asset_depreciation', pd.DataFrame())
    ag = frames.get('asset_groups',       pd.DataFrame())
    ab = frames.get('asset_balances',     pd.DataFrame())
    af = frames.get('asset_trans_flags',  pd.DataFrame())

    result = {}
    for house in ['HOC', 'HOL']:
        h_am = am[am['house'] == house] if not am.empty else pd.DataFrame()
        h_ad = ad[ad['house'] == house] if not ad.empty else pd.DataFrame()
        h_ag = ag[ag['house'] == house] if not ag.empty else pd.DataFrame()
        h_ab = ab[ab['house'] == house] if not ab.empty else pd.DataFrame()
        h_af = af[af['house'] == house] if not af.empty else pd.DataFrame()

        # ── Asset master ───────────────────────────────────────────────────────
        am_total  = len(h_am)
        am_status = h_am['status'].value_counts().to_dict() if am_total > 0 else {}

        # ── Asset groups ───────────────────────────────────────────────────────
        ag_total   = len(h_ag)
        ag_active  = int((h_ag['grp_status'] == 'N').sum()) if ag_total > 0 else 0
        ag_methods = h_ag['depr_method'].value_counts().to_dict() if ag_total > 0 else {}

        # ── Depreciation books ─────────────────────────────────────────────────
        ad_total   = len(h_ad)
        ad_active  = int((h_ad['status'] != 'C').sum()) if ad_total > 0 else 0
        ad_methods = h_ad['depr_method'].value_counts().to_dict() if ad_total > 0 else {}
        multi_book = int(h_ad.groupby('asset_id').size().gt(1).sum()) if ad_total > 0 else 0

        # ── Balance history ────────────────────────────────────────────────────
        ab_total       = len(h_ab)
        ab_confirmed   = h_ab[h_ab['trans_type'].isin(_CONFIRMED_TYPES)] if ab_total > 0 else pd.DataFrame()
        ab_unknown     = h_ab[h_ab['trans_type'].isin(_UNKNOWN_TYPES)]   if ab_total > 0 else pd.DataFrame()
        conf_txn       = int(ab_confirmed['transaction_count'].sum()) if not ab_confirmed.empty and 'transaction_count' in ab_confirmed.columns else 0
        unkn_txn       = int(ab_unknown['transaction_count'].sum())   if not ab_unknown.empty  and 'transaction_count' in ab_unknown.columns  else 0
        conf_by_type   = ab_confirmed.groupby('trans_type')['transaction_count'].sum().to_dict() if not ab_confirmed.empty else {}
        unkn_types_seen = sorted(ab_unknown['trans_type'].unique().tolist()) if not ab_unknown.empty else []

        # ── Transaction flags ──────────────────────────────────────────────────
        af_total = len(h_af)
        af_ca    = int((h_af['trans_type'] == 'CA').sum()) if af_total > 0 and 'trans_type' in h_af.columns else 0
        af_sa    = int((h_af['trans_type'] == 'SA').sum()) if af_total > 0 and 'trans_type' in h_af.columns else 0

        result[house] = {
            'master': {
                'total':    am_total,
                'active':   am_status.get('N', 0),
                'transferred': am_status.get('T', 0),
                'closed':   am_status.get('C', 0),
                'status_breakdown': am_status,
            },
            'groups': {
                'total':          ag_total,
                'active':         ag_active,
                'method_breakdown': ag_methods,
            },
            'depr': {
                'total':           ad_total,
                'active':          ad_active,
                'multi_book':      multi_book,
                'method_breakdown': ad_methods,
            },
            'balances': {
                'total_rows':       ab_total,
                'confirmed_txns':   conf_txn,
                'unknown_txns':     unkn_txn,
                'conf_by_type':     conf_by_type,
                'unknown_types':    unkn_types_seen,
            },
            'trans_flags': {
                'ca_rows': af_ca,
                'sa_rows': af_sa,
            },
        }
    return result


# ── Card shell ─────────────────────────────────────────────────────────────────

def _extract_card(header_children, body_children, pending=False):
    border_color = '#c07820' if pending else UI['border']
    return html.Div(style={
        'borderRadius': '10px', 'overflow': 'hidden',
        'border': f'1px solid {border_color}',
        'boxShadow': '0 2px 8px rgba(31,26,15,0.08)',
        'background': _BODY_BG, 'flex': '1',
    }, children=[
        html.Div(style={'background': _HDR, 'padding': '14px 20px'}, children=header_children),
        html.Div(style={'padding': '18px 20px'}, children=body_children),
    ])


def _card_header_row(title, table_name, status_confirmed, description):
    return [
        html.Div(style={
            'display': 'flex', 'justifyContent': 'space-between',
            'alignItems': 'flex-start', 'marginBottom': '8px',
        }, children=[
            html.Div(title, style={
                'fontSize': '13px', 'fontWeight': '700', 'color': '#f8f0e0',
            }),
            _status_badge(status_confirmed),
        ]),
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'marginBottom': '6px'}, children=[
            _table_chip(table_name),
        ]),
        html.Div(description, style={
            'fontSize': '11px', 'color': _AST_TXT, 'lineHeight': '1.5',
        }),
    ]


def _house_col(house, children, border_right=False):
    colour = HOUSE_HEX[house]
    return html.Div(style={
        'flex': '1',
        'borderRight': f'1px solid {UI["border"]}' if border_right else 'none',
        'paddingRight': '16px' if border_right else '0',
        'paddingLeft': '0' if border_right else '16px',
    }, children=[
        html.Div(house, style={
            'fontSize': '9px', 'fontWeight': '800', 'letterSpacing': '0.15em',
            'color': colour, 'textTransform': 'uppercase', 'marginBottom': '10px',
        }),
        *children,
    ])


# ── Card 1: Asset Register ─────────────────────────────────────────────────────

def _card_master(hoc, hol):
    def _col(house, m):
        total = m['total']
        return _house_col(house, [
            _kv('Total extracted', total),
            _kv('Active  (N)', m['active'],      '#1a7a4a'),
            _kv('Transferred  (T)', m['transferred'], '#c07820'),
            _kv('Closed  (C)', m['closed'],      '#94a3b8'),
        ], border_right=(house == 'HOC'))

    return _extract_card(
        _card_header_row(
            'Asset Register', 'aatasset', True,
            'Every asset on the fixed asset register. Status N = active and in scope for migration. Status C = closed / disposed — excluded from DQ checks.',
        ),
        [html.Div(style={'display': 'flex', 'gap': '16px'}, children=[
            _col('HOC', hoc), _col('HOL', hol),
        ])],
    )


# ── Card 2: Group Configuration ────────────────────────────────────────────────

def _card_groups(hoc, hol):
    def _col(house, g):
        mb = g['method_breakdown']
        total = g['total']
        method_rows = [
            _bar_row(m, mb[m], total, _METHOD_COLORS.get(m, '#94a3b8'))
            for m in sorted(mb, key=lambda x: -mb[x])
        ] if mb else [html.Div('No data', style={'fontSize': '11px', 'color': UI['text_secondary']})]
        return _house_col(house, [
            _kv('Groups extracted', g['total']),
            _kv('Active', g['active'], '#1a7a4a'),
            html.Div(style={'marginTop': '10px'}, children=[
                _section_label('Method distribution'),
                *method_rows,
            ]),
        ], border_right=(house == 'HOC'))

    return _extract_card(
        _card_header_row(
            'Group Configuration', 'aatassetgroup + aatassetgrbook', True,
            'Asset categories defining default depreciation rules. Every asset inherits its method and useful life from its group unless overridden at asset level.',
        ),
        [html.Div(style={'display': 'flex', 'gap': '16px'}, children=[
            _col('HOC', hoc), _col('HOL', hol),
        ])],
    )


# ── Card 3: Transaction Flags ──────────────────────────────────────────────────

def _card_trans_flags(hoc, hol):
    def _col(house, t):
        return _house_col(house, [
            _kv('Capitalisation  (CA)', t['ca_rows']),
            _kv('Disposal  (SA)', t['sa_rows']),
        ], border_right=(house == 'HOC'))

    return _extract_card(
        _card_header_row(
            'Transaction Flags', 'aattrans  (individual rows)', True,
            'Capitalisation and disposal transactions extracted at individual row level from aattrans. Used to check for zero-cost capitalisations, multiple capitalisation events, and disposal transactions against assets still marked active.',
        ),
        [html.Div(style={'display': 'flex', 'gap': '16px'}, children=[
            _col('HOC', hoc), _col('HOL', hol),
        ])],
    )


# ── Card 4: Depreciation Books ─────────────────────────────────────────────────

def _card_depr(hoc, hol):
    def _col(house, d):
        mb = d['method_breakdown']
        total = d['total']
        method_rows = [
            _bar_row(m, mb[m], total, _METHOD_COLORS.get(m, '#c07820'))
            for m in sorted(mb, key=lambda x: -mb[x])
        ] if mb else [html.Div('No data', style={'fontSize': '11px', 'color': UI['text_secondary']})]
        return _house_col(house, [
            _kv('Books extracted', d['total']),
            _kv('Non-closed', d['active']),
            _kv('Multi-book assets', d['multi_book']),
            html.Div(style={'marginTop': '10px'}, children=[
                _section_label('Method codes found'),
                *method_rows,
            ]),
        ], border_right=(house == 'HOC'))

    return _extract_card(
        _card_header_row(
            'Depreciation Books', 'aatassetbook', False,
            'Per-asset depreciation configuration — one row per asset per book. The method codes in this data (LNA, LNB, MAN, NOD) do not match the standard Unit4 specification. Meanings are unconfirmed.',
        ),
        [html.Div(style={'display': 'flex', 'gap': '16px'}, children=[
            _col('HOC', hoc), _col('HOL', hol),
        ])],
        pending=True,
    )


# ── Card 5: Balance History ────────────────────────────────────────────────────

def _card_balances(hoc, hol):
    _CONF_COLORS = {
        'CA': '#1a7a4a', 'PC': '#3a7abf', 'ND': '#7c5cbf',
        'ED': '#c07820', 'FD': '#c0392b', 'SA': '#94a3b8',
        'VN': '#0891b2', 'CI': '#64748b',
    }

    def _col(house, b):
        total_txns = b['confirmed_txns'] + b['unknown_txns']
        conf_rows = [
            _bar_row(t, b['conf_by_type'].get(t, 0), max(total_txns, 1),
                     _CONF_COLORS.get(t, '#94a3b8'))
            for t in ['CA', 'ND', 'SA', 'PC', 'FD', 'ED', 'VN']
            if b['conf_by_type'].get(t, 0) > 0
        ]
        unkn_chips = [
            html.Span(t, style={
                'background': '#c0782020', 'color': '#c07820',
                'fontSize': '10px', 'fontWeight': '700',
                'padding': '1px 6px', 'borderRadius': '3px',
                'marginRight': '4px', 'marginBottom': '4px',
                'display': 'inline-block',
            }) for t in b['unknown_types']
        ]
        return _house_col(house, [
            _kv('Confirmed transactions', b['confirmed_txns'], '#1a7a4a'),
            _kv('Unconfirmed transactions', b['unknown_txns'], '#c07820'),
            html.Div(style={'marginTop': '10px'}, children=[
                _section_label('Confirmed type breakdown'),
                *(conf_rows if conf_rows else [html.Div('No confirmed types', style={'fontSize': '11px', 'color': UI['text_secondary']})]),
            ]),
            html.Div(style={'marginTop': '10px'}, children=[
                _section_label('Unconfirmed types found'),
                html.Div(style={'display': 'flex', 'flexWrap': 'wrap', 'marginTop': '4px'}, children=unkn_chips) if unkn_chips else
                html.Div('None', style={'fontSize': '11px', 'color': '#1a7a4a'}),
            ]),
        ], border_right=(house == 'HOC'))

    return _extract_card(
        _card_header_row(
            'Balance History', 'aattrans  (aggregated)', False,
            'Lifetime financial transactions aggregated to one row per asset / book / transaction type. Used to derive cost, accumulated depreciation, and NBV. Several transaction type codes are unexplained and currently excluded from balance calculations.',
        ),
        [html.Div(style={'display': 'flex', 'gap': '16px'}, children=[
            _col('HOC', hoc), _col('HOL', hol),
        ])],
        pending=True,
    )


# ── Known gaps panels ──────────────────────────────────────────────────────────

def _known_gaps_section():
    def _gap_panel(title, body_items):
        return html.Div(style={
            'flex': '1',
            'background': '#fffbf2',
            'border': '1px solid #c07820',
            'borderLeft': '4px solid #c07820',
            'borderRadius': '8px',
            'padding': '16px 20px',
        }, children=[
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '10px', 'marginBottom': '10px'}, children=[
                html.Span('⚠', style={'fontSize': '14px', 'color': '#c07820'}),
                html.Div(title, style={
                    'fontSize': '13px', 'fontWeight': '700', 'color': '#7a4a00',
                }),
            ]),
            *[html.Div(item, style={
                'fontSize': '12px', 'color': UI['text_secondary'],
                'lineHeight': '1.6', 'marginBottom': '4px',
            }) for item in body_items],
        ])

    return html.Div(style={'marginTop': '16px'}, children=[
        html.Div(style={
            'fontSize': '11px', 'fontWeight': '700', 'color': '#7a4a00',
            'textTransform': 'uppercase', 'letterSpacing': '0.08em', 'marginBottom': '10px',
        }, children='Known gaps — checks affected until resolved'),
        html.Div(style={'display': 'flex', 'gap': '16px'}, children=[
            _gap_panel(
                'Depreciation method codes not confirmed',
                [
                    'The depreciation books use codes LNA, LNB, MAN, NOD. These do not appear in the Unit4 standard specification and their meanings have not been confirmed by Parliament.',
                    'Until confirmed: 7 DQ checks are unreliable — including whether the correct supporting fields (useful life, depreciation rate) are present for each method.',
                    'Affected: DQ-AD-V01, DQ-AD-V04, DQ-AD-C04, DQ-AD-C05, DQ-AG-V01, DQ-AG-C05, DQ-AG-C06. See Q4 in Questions for Parliament.',
                ],
            ),
            _gap_panel(
                'Unknown transaction types in balance history',
                [
                    'The following transaction type codes appear in aattrans but their meanings are unconfirmed: NF, NT, TF, TT, RF, RT, OS, WU, TC.',
                    'These are excluded from the current NBV formula. TF/TT alone represents approximately £178m at HOL and £15m at HOC.',
                    'Affected: all balance-derived DQ checks (DQ-AB-K01, K02, K03) and the valid transaction type check (DQ-AB-V01). See Q3 in Questions for Parliament.',
                ],
            ),
        ]),
    ])


# ── Intro assembly ─────────────────────────────────────────────────────────────

def _render_intro(intro_data):
    hoc_m = intro_data['HOC']['master']
    hol_m = intro_data['HOL']['master']
    hoc_g = intro_data['HOC']['groups']
    hol_g = intro_data['HOL']['groups']
    hoc_d = intro_data['HOC']['depr']
    hol_d = intro_data['HOL']['depr']
    hoc_b = intro_data['HOC']['balances']
    hol_b = intro_data['HOL']['balances']
    hoc_f = intro_data['HOC']['trans_flags']
    hol_f = intro_data['HOL']['trans_flags']

    return html.Div(style={'marginBottom': '28px'}, children=[
        html.Div(style={
            'display': 'flex', 'alignItems': 'baseline', 'gap': '10px', 'marginBottom': '14px',
        }, children=[
            html.Div('What we extracted', style={
                'fontSize': '13px', 'fontWeight': '800', 'color': UI['text_primary'],
                'textTransform': 'uppercase', 'letterSpacing': '0.01em',
            }),
            html.Div('Five datasets from the Unit4 fixed asset module — what each contains and what is still unconfirmed', style={
                'fontSize': '12px', 'color': UI['text_secondary'],
            }),
        ]),

        # Row 1
        html.Div(style={'display': 'flex', 'gap': '16px', 'marginBottom': '16px'}, children=[
            _card_master(hoc_m, hol_m),
            _card_groups(hoc_g, hol_g),
        ]),

        # Row 2
        html.Div(style={'display': 'flex', 'gap': '16px', 'marginBottom': '16px'}, children=[
            _card_trans_flags(hoc_f, hol_f),
            _card_depr(hoc_d, hol_d),
        ]),

        # Row 3 — balance history full width
        _card_balances(hoc_b, hol_b),

        _known_gaps_section(),
    ])


# ── DQ section header ──────────────────────────────────────────────────────────

def _dq_section_header():
    return html.Div(style={
        'borderTop': f'1px solid {UI["border"]}',
        'paddingTop': '20px', 'marginBottom': '20px',
        'display': 'flex', 'alignItems': 'baseline', 'gap': '10px',
    }, children=[
        html.Div('Data Quality Checks', style={
            'fontSize': '13px', 'fontWeight': '800', 'color': UI['text_primary'],
            'textTransform': 'uppercase', 'letterSpacing': '0.01em',
        }),
        html.Div('All rule categories across asset register and configuration tables', style={
            'fontSize': '12px', 'color': UI['text_secondary'],
        }),
    ])


# ── Tab entry point ────────────────────────────────────────────────────────────

def render_tab(dq_results, frames):
    intro_data = get_asset_intro_data(frames)
    return html.Div([
        _render_intro(intro_data),
        _dq_section_header(),
        render_dimension_scorecard(dq_results),
        render_dimension_grid(dq_results),
        render_dimensions_table(dq_results),
        html.Div(id='dim-drill-down-container', style={'marginTop': '24px'}),
    ])
