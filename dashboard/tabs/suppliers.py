from dash import html
from dashboard.shared.ui import render_volumetrics_card
from dashboard.shared.dimensions import render_dimension_scorecard, render_dimension_grid, render_dimensions_table
from dashboard.tabs.aging import render_aging
from dashboard.data_engine import build_aging_analysis
from dashboard.core.volumetrics import get_ap_volumetrics
from dashboard.core.theme import UI, HOUSE_HEX, DISPLAY_FONT

# ── colour tokens local to this card ─────────────────────────────────────────
_CARD_HEADER  = '#2a1f3d'   # very dark purple — richer than header_start
_CARD_HEADER2 = '#231a34'   # slightly darker for supporting card
_SEQ_BG       = '#3d2f5c'   # seq badge background
_SUP_BG       = '#1e1830'   # "supporting" badge background
_SEQ_TEXT     = '#d4c4f0'   # seq badge text
_SUP_TEXT     = '#7a6a9a'   # supporting badge text
_DIVIDER      = '#3a2f52'   # internal card divider
_BODY_BG      = '#ffffff'
_FOOTER_BG    = '#f8f7fc'   # very slight purple tint on footer


def _badge(text, bg, color, size='10px'):
    return html.Span(text, style={
        'background': bg, 'color': color,
        'fontSize': size, 'fontWeight': '800',
        'letterSpacing': '0.1em',
        'padding': '3px 9px', 'borderRadius': '4px',
        'textTransform': 'uppercase', 'display': 'inline-block',
        'lineHeight': '1.6',
    })


def _house_count(house, count, label):
    colour = HOUSE_HEX[house]
    return html.Div(style={
        'flex': '1', 'padding': '18px 20px',
        'borderRight': f'1px solid {UI["border"]}' if house == 'HOC' else 'none',
    }, children=[
        html.Div(house, style={
            'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.12em',
            'color': colour, 'marginBottom': '6px', 'textTransform': 'uppercase',
        }),
        html.Div(f'{count:,}', style={
            'fontSize': '32px', 'fontWeight': '900',
            'color': UI['text_primary'], 'lineHeight': '1',
            'fontFamily': DISPLAY_FONT, 'letterSpacing': '-0.02em',
        }),
        html.Div(label, style={
            'fontSize': '11px', 'color': UI['text_secondary'],
            'marginTop': '4px',
        }),
    ])


def _footer_stat(label, value, highlight=False):
    return html.Div(style={
        'display': 'flex', 'flexDirection': 'column', 'gap': '1px',
        'flex': '1',
    }, children=[
        html.Div(value, style={
            'fontSize': '13px', 'fontWeight': '700',
            'color': '#c0392b' if highlight else UI['text_primary'],
        }),
        html.Div(label, style={
            'fontSize': '10px', 'color': UI['text_secondary'],
            'textTransform': 'uppercase', 'letterSpacing': '0.05em',
        }),
    ])


def _scope_card(seq, name, type_label, is_migration,
                source_table, filter_desc,
                hoc_count, hol_count, count_label,
                footer_stats):
    header_bg = _CARD_HEADER if is_migration else _CARD_HEADER2
    seq_display = f'SEQ {seq}' if seq else None

    header_children = [
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'marginBottom': '10px'}, children=[
            _badge(seq_display, _SEQ_BG, _SEQ_TEXT) if seq_display else None,
            _badge(type_label,
                   _SEQ_BG if is_migration else _SUP_BG,
                   _SEQ_TEXT if is_migration else _SUP_TEXT),
        ]),
        html.Div(name, style={
            'fontSize': '15px', 'fontWeight': '700',
            'color': '#f4f0fc', 'lineHeight': '1.3', 'marginBottom': '8px',
        }),
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '6px'}, children=[
            html.Span(source_table, style={
                'fontSize': '11px', 'color': '#9080b8',
                'fontFamily': "'Courier New', monospace",
                'background': '#1a1030', 'padding': '2px 7px',
                'borderRadius': '3px',
            }),
            html.Span('·', style={'color': '#5a4a78', 'fontSize': '12px'}),
            html.Span(filter_desc, style={'fontSize': '11px', 'color': '#7a6a9a'}),
        ]),
    ]

    return html.Div(style={
        'flex': '1', 'display': 'flex', 'flexDirection': 'column',
        'borderRadius': '10px', 'overflow': 'hidden',
        'border': f'1px solid {UI["border"]}',
        'boxShadow': '0 2px 12px rgba(42,31,61,0.10)',
    }, children=[
        # Header
        html.Div(style={
            'background': header_bg,
            'padding': '18px 20px',
        }, children=header_children),

        # House counts
        html.Div(style={
            'display': 'flex', 'background': _BODY_BG,
            'borderBottom': f'1px solid {UI["border"]}',
        }, children=[
            _house_count('HOC', hoc_count, count_label),
            _house_count('HOL', hol_count, count_label),
        ]),

        # Footer stats
        html.Div(style={
            'display': 'flex', 'background': _FOOTER_BG,
            'padding': '12px 20px', 'gap': '12px',
            'borderTop': f'1px solid {UI["border"]}',
            'flex': '1', 'alignItems': 'center',
        }, children=[
            _footer_stat(label, value, highlight)
            for label, value, highlight in footer_stats
        ]),
    ])


def _render_intro(ap_vol):
    hoc_m = ap_vol.get('HOC', {}).get('master', {})
    hol_m = ap_vol.get('HOL', {}).get('master', {})
    hoc_t = ap_vol.get('HOC', {}).get('transactions', {})
    hol_t = ap_vol.get('HOL', {}).get('transactions', {})
    hoc_h = ap_vol.get('HOC', {}).get('history', {})
    hol_h = ap_vol.get('HOL', {}).get('history', {})

    hoc_active   = hoc_m.get('active', 0)
    hoc_inactive = hoc_m.get('total', 0) - hoc_active
    hol_active   = hol_m.get('active', 0)
    hol_inactive = hol_m.get('total', 0) - hol_active

    hoc_balance = hoc_t.get('balance', 0.0)
    hol_balance = hol_t.get('balance', 0.0)
    hoc_overdue = hoc_t.get('overdue_count', 0)
    hol_overdue = hol_t.get('overdue_count', 0)
    total_overdue = hoc_overdue + hol_overdue

    cards = [
        _scope_card(
            seq='10',
            name='Suppliers (Headers & Sites)',
            type_label='Migration Object',
            is_migration=True,
            source_table='asuheader',
            filter_desc='Full population — no status filter',
            hoc_count=hoc_m.get('total', 0),
            hol_count=hol_m.get('total', 0),
            count_label='suppliers extracted',
            footer_stats=[
                ('Active (status N)', f'{hoc_active + hol_active:,}', False),
                ('Inactive', f'{hoc_inactive + hol_inactive:,}', False),
                ('Extract date', hoc_m.get('extract_date') or '—', False),
            ],
        ),
        _scope_card(
            seq='16',
            name='Open AP Invoices',
            type_label='Migration Object',
            is_migration=True,
            source_table='asutrans',
            filter_desc='Open only — status ≠ C',
            hoc_count=hoc_t.get('open_count', 0),
            hol_count=hol_t.get('open_count', 0),
            count_label='open invoices extracted',
            footer_stats=[
                ('Outstanding balance', f'£{hoc_balance + hol_balance:,.0f}', False),
                ('Overdue invoices', f'{total_overdue:,}', total_overdue > 0),
                ('Extract date', hoc_t.get('extract_date') or '—', False),
            ],
        ),
        _scope_card(
            seq=None,
            name='AP Transaction History',
            type_label='Scoping Extract',
            is_migration=False,
            source_table='asuhistr',
            filter_desc='18-month window — closed transactions',
            hoc_count=hoc_h.get('total', 0),
            hol_count=hol_h.get('total', 0),
            count_label='historical transactions',
            footer_stats=[
                ('Purpose', 'Scope Seq 10', False),
                ('Determines', 'Active suppliers', False),
                ('Criterion', 'Activity ≤ 18 months', False),
            ],
        ),
    ]

    return html.Div(style={'marginBottom': '28px'}, children=[
        # Section label
        html.Div(style={
            'display': 'flex', 'alignItems': 'baseline',
            'gap': '10px', 'marginBottom': '14px',
        }, children=[
            html.Div('Migration Scope', style={
                'fontSize': '13px', 'fontWeight': '800',
                'color': UI['text_primary'], 'letterSpacing': '0.01em',
                'textTransform': 'uppercase',
            }),
            html.Div('Extracts aligned to programme scope objects', style={
                'fontSize': '12px', 'color': UI['text_secondary'],
            }),
        ]),
        # Cards row
        html.Div(style={
            'display': 'flex', 'gap': '16px', 'alignItems': 'stretch',
        }, children=cards),
    ])


def render_tab(dq_results, frames):
    ap_vol = get_ap_volumetrics(frames)
    hoc_cards = render_volumetrics_card(ap_vol['HOC'])
    hol_cards = render_volumetrics_card(ap_vol['HOL'])

    aging_results = build_aging_analysis(frames)

    return html.Div([
        _render_intro(ap_vol),
        render_dimension_scorecard(dq_results),
        html.Div(style={'marginBottom': '24px'}, children=[
            html.Div(style={'display': 'flex', 'gap': '20px', 'marginBottom': '20px'}, children=hoc_cards),
            html.Div(style={'display': 'flex', 'gap': '20px'}, children=hol_cards),
        ]),
        render_dimension_grid(dq_results),
        render_dimensions_table(dq_results),
        render_aging(aging_results, module='ap'),
        html.Div(id='dim-drill-down-container', style={'marginTop': '24px'})
    ])
