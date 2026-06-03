import pandas as pd
import plotly.express as px
from dash import html, dcc
from dashboard.shared.dimensions import render_dimension_scorecard, render_dimension_grid, render_dimensions_table
from dashboard.core.volumetrics import get_gl_volumetrics
from dashboard.core.theme import UI, HOUSE_HEX, DISPLAY_FONT

# ── Design tokens (match suppliers.py) ───────────────────────────────────────
_HDR     = '#2a1f3d'
_SEQ_BG  = '#3d2f5c'
_SEQ_TXT = '#d4c4f0'
_BAR_BG  = '#ede9f8'

# ── GL-specific type / classification colours ─────────────────────────────────
_TYPE_COLOR = {'GL': '#4f46e5', 'AP': '#d97706', 'AR': '#059669'}
_TYPE_LABEL = {'GL': 'General Ledger', 'AP': 'Accounts Payable', 'AR': 'Accounts Receivable'}
_RES_COLOR  = {'B': '#3b82f6', 'R': '#7c5cbf'}
_RES_LABEL  = {'B': 'Balance Sheet', 'R': 'Profit & Loss'}

# ── DQ section chrome ─────────────────────────────────────────────────────────
_SECTION_HEADER = {
    'borderTop': '1px solid #e2d9f3',
    'margin': '8px 0 20px',
    'paddingTop': '20px',
    'display': 'flex',
    'alignItems': 'center',
    'gap': '12px',
}
_SECTION_TITLE = {'fontSize': '15px', 'fontWeight': '700', 'color': '#2a1f3d'}
_SECTION_BADGE = {
    'fontSize': '11px', 'color': '#9080b0',
    'background': '#f0ebfa', 'padding': '2px 8px', 'borderRadius': '4px',
}

_GL_POSITIONS = {'0', '1', '2', '3', '4', '5', '6', '7'}

# Voucher type labels and colours for the journals breakdown bars
_VTYPE_LABEL = {
    'AC': 'Accrual journals',     'BF': 'Bank funding',
    'BI': 'Batch input',          'DJ': 'Drawn down',
    'EI': 'EPOS interface',       'FZ': 'Fixed assets',
    'JL': 'Adjustment journals',  'JO': 'Opening balances',
    'MI': 'Micros interface',     'MM': 'Manual matching',
    'PA': 'Absence entry',        'PC': 'Payroll manual cheque',
    'PE': 'Posting expenses',     'PJ': 'Prepayment journals',
    'PP': 'Posting payroll',      'PY': 'Payments',
    'PV': 'Variable payroll',     'RE': 'Registering expenses',
    'RJ': 'Recurring journals',   'RP': 'Reshared staff posting',
    'RS': 'Staff expenses',       'TC': 'Members travel card',
    'TD': 'Expenses templates',   'YE': 'Year end transfer',
    'AB': 'Absence transfer',     'BA': 'Batch input adj',
}
_VTYPE_COLOR = {
    'PY': '#7c3aed', 'PP': '#6d28d9', 'PA': '#8b5cf6',
    'JL': '#2563eb', 'RJ': '#3b82f6', 'AC': '#0891b2',
    'PE': '#059669', 'RE': '#65a30d', 'RS': '#16a34a',
    'FZ': '#d97706', 'YE': '#b45309', 'BF': '#0e7490',
    'MM': '#9333ea', 'PJ': '#7e22ce', 'EI': '#0f766e',
    'MI': '#0f766e', 'JO': '#475569',
}


# ═══════════════════════════════════════════════════════════════════════════════
# Intro section — GL Foundation Data
# ═══════════════════════════════════════════════════════════════════════════════

def _badge(text, bg, color='#f4f0fc'):
    return html.Span(text, style={
        'background': bg, 'color': color,
        'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.1em',
        'padding': '3px 9px', 'borderRadius': '4px',
        'textTransform': 'uppercase', 'display': 'inline-block', 'lineHeight': '1.6',
    })


def _section_label(text):
    return html.Div(text, style={
        'fontSize': '10px', 'fontWeight': '700', 'color': UI['text_secondary'],
        'textTransform': 'uppercase', 'letterSpacing': '0.08em', 'marginBottom': '8px',
    })


def _fmt_period(p):
    """Convert YYYYPP integer to 'P01 / 2025' display string."""
    if p is None:
        return '—'
    year = p // 100
    per  = p % 100
    return f'P{per:02d} / {year}'


def _fmt_net(v):
    sign = '−' if v < 0 else '+'
    a = abs(v)
    if a >= 1_000_000:
        return f'{sign}£{a / 1_000_000:.2f}m'
    if a >= 1_000:
        return f'{sign}£{a / 1_000:.1f}k'
    return f'{sign}£{a:,.0f}'


def _gl_bar_row(code, label, color, count, total):
    """Proportional bar for a named GL category (account type, classification)."""
    pct = (count / total * 100) if total > 0 else 0
    return html.Div(style={
        'display': 'flex', 'alignItems': 'center', 'gap': '10px', 'padding': '4px 0',
    }, children=[
        html.Span(code, style={
            'background': color + '1a', 'color': color,
            'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.06em',
            'padding': '2px 7px', 'borderRadius': '3px',
            'minWidth': '26px', 'textAlign': 'center',
        }),
        html.Span(label, style={
            'fontSize': '11px', 'color': UI['text_secondary'], 'minWidth': '130px',
        }),
        html.Div(style={
            'flex': '1', 'height': '6px', 'background': _BAR_BG,
            'borderRadius': '3px', 'overflow': 'hidden',
        }, children=[
            html.Div(style={
                'height': '100%', 'width': f'{min(pct, 100):.1f}%',
                'background': color, 'borderRadius': '3px',
                'minWidth': '3px' if count > 0 else '0',
            })
        ]),
        html.Span(f'{count:,}', style={
            'fontSize': '12px', 'fontWeight': '700',
            'minWidth': '52px', 'textAlign': 'right', 'color': UI['text_primary'],
        }),
        html.Span(f'{pct:.0f}%', style={
            'fontSize': '10px', 'color': UI['text_secondary'], 'minWidth': '32px',
        }),
    ])


def _gl_card_header(seq, name, source, filter_desc):
    return html.Div(style={
        'background': _HDR, 'padding': '16px 28px',
    }, children=[
        html.Div(style={
            'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'marginBottom': '10px',
        }, children=[
            _badge(f'SEQ {seq}', _SEQ_BG, _SEQ_TXT) if seq else None,
            _badge('Migration Object', _SEQ_BG, _SEQ_TXT),
        ]),
        html.Div(name, style={
            'fontSize': '15px', 'fontWeight': '700', 'color': '#f4f0fc', 'marginBottom': '8px',
        }),
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '6px'}, children=[
            html.Span(source, style={
                'fontSize': '11px', 'color': '#9080b8',
                'fontFamily': "'Courier New', monospace",
                'background': '#1a1030', 'padding': '2px 7px', 'borderRadius': '3px',
            }),
            html.Span('·', style={'color': '#5a4a78', 'fontSize': '12px'}),
            html.Span(filter_desc, style={'fontSize': '11px', 'color': '#7a6a9a'}),
        ]),
    ])


# ── Chart of Accounts column ──────────────────────────────────────────────────

def _acc_col(house, acc):
    colour     = HOUSE_HEX[house]
    total      = acc.get('total', 0)
    active     = acc.get('active', 0)
    closed     = acc.get('closed', 0)
    by_type    = acc.get('by_type', {})
    by_res     = acc.get('by_res_bal', {})
    active_pct = int(active / total * 100) if total else 0

    type_rows = [
        _gl_bar_row(code, _TYPE_LABEL.get(code, code), _TYPE_COLOR.get(code, '#94a3b8'),
                    by_type.get(code, 0), active)
        for code in ['GL', 'AP', 'AR']
        if by_type.get(code, 0) > 0
    ]
    res_rows = [
        _gl_bar_row(code, _RES_LABEL.get(code, code), _RES_COLOR.get(code, '#94a3b8'),
                    by_res.get(code, 0), active)
        for code in ['B', 'R']
        if by_res.get(code, 0) > 0
    ]

    return html.Div(style={
        'flex': '1', 'padding': '24px 32px',
        'borderRight': f'1px solid {UI["border"]}' if house == 'HOC' else 'none',
    }, children=[
        html.Div(house, style={
            'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.15em',
            'color': colour, 'textTransform': 'uppercase', 'marginBottom': '6px',
        }),
        html.Div(style={
            'display': 'flex', 'alignItems': 'baseline', 'gap': '12px', 'marginBottom': '4px',
        }, children=[
            html.Span(f'{active:,}', style={
                'fontSize': '48px', 'fontWeight': '900', 'lineHeight': '1',
                'color': UI['text_primary'], 'fontFamily': DISPLAY_FONT, 'letterSpacing': '-0.03em',
            }),
            html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '2px'}, children=[
                html.Span('active accounts', style={
                    'fontSize': '12px', 'fontWeight': '600', 'color': UI['text_primary'],
                }),
                html.Span(f'{closed:,} closed  ·  {total:,} total  ({active_pct}% active)', style={
                    'fontSize': '11px', 'color': UI['text_secondary'],
                }),
            ]),
        ]),
        html.Div(style={
            'height': '4px', 'background': UI['border'],
            'borderRadius': '2px', 'marginBottom': '20px',
        }, children=[
            html.Div(style={
                'height': '100%', 'width': f'{active_pct}%',
                'background': colour, 'borderRadius': '2px',
            })
        ]),
        _section_label('Account type'),
        html.Div(style={'marginBottom': '16px'}, children=type_rows or [
            html.Div('No type data', style={'fontSize': '11px', 'color': UI['text_secondary']}),
        ]),
        _section_label('Classification'),
        html.Div(children=res_rows or [
            html.Div('No classification data', style={'fontSize': '11px', 'color': UI['text_secondary']}),
        ]),
    ])


# ── GL Opening Balances column ────────────────────────────────────────────────

def _bal_col(house, bal):
    colour  = HOUSE_HEX[house]
    total   = bal.get('total', 0)
    net     = bal.get('net_amount', 0.0)
    pmin    = bal.get('period_min')
    pmax    = bal.get('period_max')
    accs    = bal.get('account_count', 0)

    abs_net = abs(net)
    if abs_net < 100:
        net_color = '#1a7a4a'
        net_label = 'balanced'
    elif abs_net < 100_000:
        net_color = '#d97706'
        net_label = 'slight variance'
    else:
        net_color = '#c0392b'
        net_label = 'imbalance detected'

    return html.Div(style={
        'flex': '1', 'padding': '24px 32px',
        'borderRight': f'1px solid {UI["border"]}' if house == 'HOC' else 'none',
    }, children=[
        html.Div(house, style={
            'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.15em',
            'color': colour, 'textTransform': 'uppercase', 'marginBottom': '6px',
        }),
        html.Div(style={
            'display': 'flex', 'alignItems': 'baseline', 'gap': '12px', 'marginBottom': '20px',
        }, children=[
            html.Span(f'{total:,}', style={
                'fontSize': '48px', 'fontWeight': '900', 'lineHeight': '1',
                'color': UI['text_primary'], 'fontFamily': DISPLAY_FONT, 'letterSpacing': '-0.03em',
            }),
            html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '2px'}, children=[
                html.Span('posting lines', style={
                    'fontSize': '12px', 'fontWeight': '600', 'color': UI['text_primary'],
                }),
                html.Span(f'across {accs:,} distinct accounts', style={
                    'fontSize': '11px', 'color': UI['text_secondary'],
                }),
            ]),
        ]),
        _section_label('Period range'),
        html.Div(style={
            'display': 'flex', 'alignItems': 'center', 'gap': '10px', 'marginBottom': '20px',
        }, children=[
            html.Span(_fmt_period(pmin), style={
                'fontSize': '13px', 'fontWeight': '700',
                'color': UI['text_primary'], 'fontFamily': DISPLAY_FONT,
            }),
            html.Span('→', style={'color': UI['text_secondary'], 'fontSize': '14px'}),
            html.Span(_fmt_period(pmax), style={
                'fontSize': '13px', 'fontWeight': '700',
                'color': UI['text_primary'], 'fontFamily': DISPLAY_FONT,
            }),
        ]),
        _section_label('Net balance  (should equal zero)'),
        html.Div(style={'display': 'flex', 'alignItems': 'baseline', 'gap': '10px'}, children=[
            html.Span(_fmt_net(net), style={
                'fontSize': '22px', 'fontWeight': '900',
                'color': net_color, 'fontFamily': DISPLAY_FONT, 'lineHeight': '1',
            }),
            html.Span(net_label, style={
                'fontSize': '11px', 'color': net_color, 'fontWeight': '600',
            }),
        ]),
    ])


# ── GL Journals column ───────────────────────────────────────────────────────

def _jnl_col(house, jnl):
    colour   = HOUSE_HEX[house]
    lines    = jnl.get('lines', 0)
    vouchers = jnl.get('vouchers', 0)
    accounts = jnl.get('accounts', 0)
    users    = jnl.get('users', 0)
    by_type  = jnl.get('by_type', {})
    pmin        = jnl.get('period_min')
    pmax        = jnl.get('period_max')
    unbalanced  = jnl.get('unbalanced', 0)
    net         = jnl.get('net_amount', 0.0)

    if unbalanced == 0:
        bal_color, bal_label = '#1a7a4a', 'all vouchers balance'
    elif unbalanced <= 10:
        bal_color, bal_label = '#d97706', f'{unbalanced} voucher{"s" if unbalanced != 1 else ""} unbalanced'
    else:
        bal_color, bal_label = '#c0392b', f'{unbalanced:,} vouchers unbalanced'

    abs_net = abs(net)
    if abs_net < 100:
        net_color, net_label = '#1a7a4a', 'balanced'
    elif abs_net < 100_000:
        net_color, net_label = '#d97706', 'slight variance'
    else:
        net_color, net_label = '#c0392b', 'imbalance'

    sorted_types = sorted(by_type.items(), key=lambda x: -x[1])
    top_n        = sorted_types[:8]
    other_count  = sum(v for _, v in sorted_types[8:])
    total        = sum(by_type.values()) or 1

    type_rows = [
        _gl_bar_row(code, _VTYPE_LABEL.get(code, code),
                    _VTYPE_COLOR.get(code, '#94a3b8'), count, total)
        for code, count in top_n
    ]
    if other_count:
        other_n = len(sorted_types) - 8
        type_rows.append(_gl_bar_row(
            '…', f'{other_n} other type{"s" if other_n != 1 else ""}',
            '#94a3b8', other_count, total,
        ))

    return html.Div(style={
        'flex': '1', 'padding': '24px 32px',
        'borderRight': f'1px solid {UI["border"]}' if house == 'HOC' else 'none',
    }, children=[
        html.Div(house, style={
            'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.15em',
            'color': colour, 'textTransform': 'uppercase', 'marginBottom': '6px',
        }),
        html.Div(style={
            'display': 'flex', 'alignItems': 'baseline', 'gap': '12px', 'marginBottom': '4px',
        }, children=[
            html.Span(f'{lines:,}', style={
                'fontSize': '48px', 'fontWeight': '900', 'lineHeight': '1',
                'color': UI['text_primary'], 'fontFamily': DISPLAY_FONT, 'letterSpacing': '-0.03em',
            }),
            html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '2px'}, children=[
                html.Span('transaction lines', style={
                    'fontSize': '12px', 'fontWeight': '600', 'color': UI['text_primary'],
                }),
                html.Span(
                    f'{vouchers:,} vouchers  ·  {accounts:,} accounts  ·  {users:,} users',
                    style={'fontSize': '11px', 'color': UI['text_secondary']},
                ),
            ]),
        ]),
        html.Div(style={
            'height': '4px', 'background': UI['border'],
            'borderRadius': '2px', 'marginBottom': '20px',
        }),
        _section_label('Period range'),
        html.Div(style={
            'display': 'flex', 'alignItems': 'center', 'gap': '10px', 'marginBottom': '20px',
        }, children=[
            html.Span(_fmt_period(pmin), style={
                'fontSize': '13px', 'fontWeight': '700',
                'color': UI['text_primary'], 'fontFamily': DISPLAY_FONT,
            }),
            html.Span('→', style={'color': UI['text_secondary'], 'fontSize': '14px'}),
            html.Span(_fmt_period(pmax), style={
                'fontSize': '13px', 'fontWeight': '700',
                'color': UI['text_primary'], 'fontFamily': DISPLAY_FONT,
            }),
        ]),
        _section_label('Voucher balance integrity  (periods 01–13, excl. opening b/f)'),
        html.Div(style={
            'display': 'flex', 'alignItems': 'center', 'gap': '24px', 'marginBottom': '20px',
        }, children=[
            html.Div(style={'display': 'flex', 'alignItems': 'baseline', 'gap': '8px'}, children=[
                html.Span(f'{unbalanced:,}' if unbalanced else '✓', style={
                    'fontSize': '22px', 'fontWeight': '900',
                    'color': bal_color, 'fontFamily': DISPLAY_FONT, 'lineHeight': '1',
                }),
                html.Span(bal_label, style={
                    'fontSize': '11px', 'color': bal_color, 'fontWeight': '600',
                }),
            ]),
            html.Div(style={'width': '1px', 'background': UI['border'], 'alignSelf': 'stretch'}),
            html.Div(style={'display': 'flex', 'alignItems': 'baseline', 'gap': '8px'}, children=[
                html.Span(_fmt_net(net), style={
                    'fontSize': '22px', 'fontWeight': '900',
                    'color': net_color, 'fontFamily': DISPLAY_FONT, 'lineHeight': '1',
                }),
                html.Span(f'net  ({net_label})', style={
                    'fontSize': '11px', 'color': net_color, 'fontWeight': '600',
                }),
            ]),
        ]),
        _section_label('By voucher type'),
        html.Div(children=type_rows or [
            html.Div('No data', style={'fontSize': '11px', 'color': UI['text_secondary']}),
        ]),
    ])


# ── GL Dimension Structure column ─────────────────────────────────────────────

def _dim_col(house, dv, dc):
    colour   = HOUSE_HEX[house]
    dv_total = dv.get('total', 0)
    dv_attrs = dv.get('attr_count', 0)
    dc_gl    = dc.get('gl_count', 0)
    dc_oos   = dc.get('oos_count', 0)
    dc_act   = dc.get('gl_active', 0)

    return html.Div(style={
        'flex': '1', 'padding': '24px 32px',
        'borderRight': f'1px solid {UI["border"]}' if house == 'HOC' else 'none',
    }, children=[
        html.Div(house, style={
            'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.15em',
            'color': colour, 'textTransform': 'uppercase', 'marginBottom': '12px',
        }),
        html.Div(style={'display': 'flex', 'gap': '14px', 'marginBottom': '20px'}, children=[
            html.Div(style={
                'flex': '1', 'padding': '14px 18px',
                'background': colour + '0d', 'borderRadius': '10px',
                'border': f'1px solid {colour}30',
            }, children=[
                html.Div(f'{dc_gl}', style={
                    'fontSize': '38px', 'fontWeight': '900', 'lineHeight': '1',
                    'color': colour, 'fontFamily': DISPLAY_FONT,
                }),
                html.Div('GL-mapped attributes', style={
                    'fontSize': '11px', 'color': UI['text_secondary'], 'marginTop': '4px',
                }),
                html.Div(f'{dc_act:,} active values', style={
                    'fontSize': '10px', 'color': colour, 'fontWeight': '700', 'marginTop': '6px',
                }),
            ]),
            html.Div(style={
                'flex': '1', 'padding': '14px 18px',
                'background': UI['purple_light'], 'borderRadius': '10px',
                'border': f'1px solid {UI["border"]}',
            }, children=[
                html.Div(f'{dc_oos}', style={
                    'fontSize': '38px', 'fontWeight': '900', 'lineHeight': '1',
                    'color': UI['text_secondary'], 'fontFamily': DISPLAY_FONT,
                }),
                html.Div('out-of-scope attributes', style={
                    'fontSize': '11px', 'color': UI['text_secondary'], 'marginTop': '4px',
                }),
                html.Div('X-position + other', style={
                    'fontSize': '10px', 'color': UI['text_secondary'],
                    'fontWeight': '600', 'marginTop': '6px',
                }),
            ]),
        ]),
        _section_label('Total active values  (GL attributes)'),
        html.Div(style={'display': 'flex', 'alignItems': 'baseline', 'gap': '8px'}, children=[
            html.Span(f'{dv_total:,}', style={
                'fontSize': '34px', 'fontWeight': '900', 'lineHeight': '1',
                'color': UI['text_primary'], 'fontFamily': DISPLAY_FONT, 'letterSpacing': '-0.02em',
            }),
            html.Span(f'values across {dv_attrs} attributes', style={
                'fontSize': '11px', 'color': UI['text_secondary'],
            }),
        ]),
    ])


# ── Intro assembly ────────────────────────────────────────────────────────────

def _render_gl_intro(gl_vol):
    hoc_acc = gl_vol.get('HOC', {}).get('accounts', {})
    hol_acc = gl_vol.get('HOL', {}).get('accounts', {})
    hoc_jnl = gl_vol.get('HOC', {}).get('journals', {})
    hol_jnl = gl_vol.get('HOL', {}).get('journals', {})
    hoc_dv  = gl_vol.get('HOC', {}).get('dimvalue', {})
    hol_dv  = gl_vol.get('HOL', {}).get('dimvalue', {})
    hoc_dc  = gl_vol.get('HOC', {}).get('dimconfig', {})
    hol_dc  = gl_vol.get('HOL', {}).get('dimconfig', {})

    def _card(children):
        return html.Div(style={
            'borderRadius': '10px', 'overflow': 'hidden',
            'border': f'1px solid {UI["border"]}',
            'boxShadow': '0 2px 12px rgba(42,31,61,0.10)',
            'background': '#ffffff',
        }, children=children)

    coa_card = _card([
        _gl_card_header('1', 'Chart of Accounts', 'aglaccounts', 'Full population — all statuses'),
        html.Div(style={'display': 'flex'}, children=[
            _acc_col('HOC', hoc_acc),
            _acc_col('HOL', hol_acc),
        ]),
    ])

    jnl_card = _card([
        _gl_card_header('21', 'Current Year Journals', 'agltransact', 'Actuals only — BU/BV excluded · status blank/null'),
        html.Div(style={'display': 'flex'}, children=[
            _jnl_col('HOC', hoc_jnl),
            _jnl_col('HOL', hol_jnl),
        ]),
    ])

    dim_card = _card([
        _gl_card_header(None, 'GL Dimension Structure', 'agldimvalue  ·  agldimension', 'GL-mapped positions only  (0 – 7)'),
        html.Div(style={'display': 'flex'}, children=[
            _dim_col('HOC', hoc_dv, hoc_dc),
            _dim_col('HOL', hol_dv, hol_dc),
        ]),
    ])

    return html.Div(style={'marginBottom': '28px'}, children=[
        html.Div(style={
            'display': 'flex', 'alignItems': 'baseline', 'gap': '10px', 'marginBottom': '14px',
        }, children=[
            html.Div('GL Foundation Data', style={
                'fontSize': '13px', 'fontWeight': '800', 'color': UI['text_primary'],
                'textTransform': 'uppercase', 'letterSpacing': '0.01em',
            }),
            html.Div('Extracts loaded and assessed', style={
                'fontSize': '12px', 'color': UI['text_secondary'],
            }),
        ]),
        html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '16px'}, children=[
            coa_card,
            jnl_card,
            dim_card,
        ]),
    ])


# ═══════════════════════════════════════════════════════════════════════════════
# Treemap — dimension structure (at bottom of tab)
# ═══════════════════════════════════════════════════════════════════════════════

def _build_treemap(df_config, house):
    """Return a px.treemap figure for one house, or None if no data."""
    clients = ['CA', 'CM'] if house == 'HOC' else ['LA']
    raw = df_config[df_config['client'].isin(clients)].copy()
    if raw.empty:
        return None

    raw['dim_position'] = raw['dim_position'].astype(str).str.strip()
    raw['total_values'] = pd.to_numeric(raw['total_values'], errors='coerce').fillna(0).astype(int)
    raw['active']       = pd.to_numeric(raw['active'],       errors='coerce').fillna(0).astype(int)
    raw['closed']       = pd.to_numeric(raw['closed'],       errors='coerce').fillna(0).astype(int)

    df = (
        raw.groupby(['attribute_id', 'description', 'dim_position'], as_index=False)
        [['total_values', 'active', 'closed']].sum()
    )

    rows = []

    df_gl = df[df['dim_position'].isin(_GL_POSITIONS)].copy()
    for _, r in df_gl.iterrows():
        total = max(int(r['total_values']), 1)
        rows.append({
            'scope': f"GL Dimensions · {len(df_gl)} attributes",
            'label': r['description'],
            'active': max(int(r['active']), 1),
            'closed_pct': round(int(r['closed']) / total * 100, 1),
            'tip': (f"<b>{r['description']}</b><br>"
                    f"dim_{r['dim_position']} &nbsp;·&nbsp; {r['attribute_id']}<br>"
                    f"Active: {int(r['active']):,} &nbsp; Closed: {int(r['closed']):,}"),
        })

    df_x = df[df['dim_position'] == 'X']
    if not df_x.empty:
        t = max(int(df_x['total_values'].sum()), 1)
        rows.append({
            'scope': 'Out of Scope',
            'label': f"X-position ({len(df_x)} attributes)",
            'active': max(int(df_x['active'].sum()), 1),
            'closed_pct': round(int(df_x['closed'].sum()) / t * 100, 1),
            'tip': (f"<b>X-position ({len(df_x)} attributes)</b><br>"
                    f"Not mapped to any GL journal line<br>"
                    f"Active values: {int(df_x['active'].sum()):,}"),
        })

    df_letter = df[~df['dim_position'].isin(_GL_POSITIONS) & (df['dim_position'] != 'X')]
    if not df_letter.empty:
        t = max(int(df_letter['total_values'].sum()), 1)
        rows.append({
            'scope': 'Out of Scope',
            'label': f"Other ({len(df_letter)} attributes)",
            'active': max(int(df_letter['active'].sum()), 1),
            'closed_pct': round(int(df_letter['closed'].sum()) / t * 100, 1),
            'tip': (f"<b>Other coded ({len(df_letter)} attributes)</b><br>"
                    f"Non-GL positions (G, F, ...)<br>"
                    f"Active values: {int(df_letter['active'].sum()):,}"),
        })

    if not rows:
        return None

    _OOS_FRACTION = 0.22
    gl_total  = sum(r['active'] for r in rows if 'GL Dimensions' in r['scope'])
    oos_total = sum(r['active'] for r in rows if r['scope'] == 'Out of Scope')
    if gl_total > 0 and oos_total > 0:
        target = gl_total * _OOS_FRACTION / (1 - _OOS_FRACTION)
        scale  = target / oos_total
        for r in rows:
            if r['scope'] == 'Out of Scope':
                r['active'] = max(1, round(r['active'] * scale))

    df_tree = pd.DataFrame(rows)

    fig = px.treemap(
        df_tree,
        path=['scope', 'label'],
        values='active',
        color='closed_pct',
        color_continuous_scale=[
            [0.0,  '#059669'],
            [0.35, '#d97706'],
            [1.0,  '#dc2626'],
        ],
        range_color=[0, 80],
        custom_data=['tip'],
    )

    fig.update_traces(
        hovertemplate='%{customdata[0]}<extra></extra>',
        texttemplate='%{label}',
        textfont=dict(size=12, color='white'),
        insidetextfont=dict(size=11, color='white'),
        marker=dict(line=dict(width=2, color='white')),
        pathbar=dict(visible=False),
    )

    fig.update_layout(
        margin=dict(t=0, l=0, r=0, b=0),
        height=360,
        coloraxis_showscale=False,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
    )

    return fig


_HOUSE_LABEL = {'HOC': 'HoC', 'HOL': 'HoL'}
_HOUSE_COLOR = {'HOC': '#16a34a', 'HOL': '#dc2626'}

_CARD = {
    'flex': '1', 'minWidth': 0,
    'background': '#ffffff',
    'border': '1px solid #ede9f8',
    'borderRadius': '12px',
    'padding': '16px 16px 12px',
    'display': 'flex',
    'flexDirection': 'column',
}


def _render_dim_structure(frames):
    """Treemap section showing GL vs out-of-scope dimension attributes."""
    if 'gl_dimconfig' not in frames or frames['gl_dimconfig'].empty:
        return html.Div()

    df = frames['gl_dimconfig']
    charts = []
    for house in ['HOC', 'HOL']:
        fig = _build_treemap(df, house)
        if fig:
            color = _HOUSE_COLOR[house]
            charts.append(html.Div([
                html.Div([
                    html.Div(style={
                        'width': '8px', 'height': '8px', 'borderRadius': '50%',
                        'background': color, 'flexShrink': '0',
                    }),
                    html.Span(_HOUSE_LABEL[house], style={
                        'fontSize': '13px', 'fontWeight': '700', 'color': color,
                    }),
                ], style={
                    'display': 'flex', 'alignItems': 'center', 'gap': '7px',
                    'marginBottom': '10px',
                }),
                dcc.Graph(
                    figure=fig,
                    style={'minWidth': 0, 'flex': '1'},
                    config={
                        'displayModeBar': True,
                        'modeBarButtonsToRemove': [
                            'toImage', 'sendDataToCloud', 'zoom2d', 'pan2d',
                            'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d',
                            'autoScale2d',
                        ],
                        'displaylogo': False,
                    },
                ),
            ], style=_CARD))

    if not charts:
        return html.Div()

    legend = html.Div([
        html.Div([
            html.Div(style={'width': '10px', 'height': '10px', 'borderRadius': '2px',
                            'background': '#059669', 'flexShrink': '0'}),
            html.Span('mostly active', style={'fontSize': '11px', 'color': '#9080b0'}),
        ], style={'display': 'flex', 'alignItems': 'center', 'gap': '5px'}),
        html.Div([
            html.Div(style={'width': '10px', 'height': '10px', 'borderRadius': '2px',
                            'background': '#d97706', 'flexShrink': '0'}),
            html.Span('~35% closed', style={'fontSize': '11px', 'color': '#9080b0'}),
        ], style={'display': 'flex', 'alignItems': 'center', 'gap': '5px'}),
        html.Div([
            html.Div(style={'width': '10px', 'height': '10px', 'borderRadius': '2px',
                            'background': '#dc2626', 'flexShrink': '0'}),
            html.Span('mostly closed', style={'fontSize': '11px', 'color': '#9080b0'}),
        ], style={'display': 'flex', 'alignItems': 'center', 'gap': '5px'}),
        html.Div(style={'width': '1px', 'background': '#e2d9f3', 'alignSelf': 'stretch', 'margin': '0 6px'}),
        html.Span('tile area ∝ active value count · click to drill in · ↺ to reset',
                  style={'fontSize': '11px', 'color': '#9080b0'}),
    ], style={
        'display': 'flex', 'alignItems': 'center', 'gap': '14px',
        'justifyContent': 'center', 'marginTop': '12px',
    })

    return html.Div([
        html.Div(style={**_SECTION_HEADER, 'marginTop': '32px'}, children=[
            html.Span('Dimension Structure', style=_SECTION_TITLE),
            html.Span('Volumetrics — not a DQ check', style=_SECTION_BADGE),
        ]),
        html.Div(
            style={'display': 'flex', 'gap': '16px'},
            children=charts,
        ),
        legend,
    ])


# ═══════════════════════════════════════════════════════════════════════════════
# Tab renderer
# ═══════════════════════════════════════════════════════════════════════════════

def render_tab(dq_results, frames):
    gl_vol = get_gl_volumetrics(frames)
    return html.Div([
        _render_gl_intro(gl_vol),
        render_dimension_scorecard(dq_results),
        html.Div(style=_SECTION_HEADER, children=[
            html.Span('Data Quality Checks', style=_SECTION_TITLE),
            html.Span('Being configured against live data', style=_SECTION_BADGE),
        ]),
        render_dimension_grid(dq_results),
        render_dimensions_table(dq_results),
        _render_dim_structure(frames),
    ])
