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


def _badge(text, bg, color):
    return html.Span(text, style={
        'background': bg, 'color': color,
        'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.1em',
        'padding': '3px 9px', 'borderRadius': '4px',
        'textTransform': 'uppercase', 'display': 'inline-block', 'lineHeight': '1.6',
    })


def _card_header(seq, name, source_table, filter_desc, type_label, is_migration):
    return html.Div(style={
        'background': _CARD_HEADER if is_migration else _CARD_HEADER2,
        'padding': '18px 20px',
    }, children=[
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'marginBottom': '10px'}, children=[
            _badge(f'SEQ {seq}', _SEQ_BG, _SEQ_TEXT) if seq else None,
            _badge(type_label, _SEQ_BG if is_migration else _SUP_BG, _SEQ_TEXT if is_migration else _SUP_TEXT),
        ]),
        html.Div(name, style={
            'fontSize': '15px', 'fontWeight': '700', 'color': '#f4f0fc',
            'lineHeight': '1.3', 'marginBottom': '8px',
        }),
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '6px'}, children=[
            html.Span(source_table, style={
                'fontSize': '11px', 'color': '#9080b8',
                'fontFamily': "'Courier New', monospace",
                'background': '#1a1030', 'padding': '2px 7px', 'borderRadius': '3px',
            }),
            html.Span('·', style={'color': '#5a4a78', 'fontSize': '12px'}),
            html.Span(filter_desc, style={'fontSize': '11px', 'color': '#7a6a9a'}),
        ]),
    ])


def _scope_breakdown_col(house, m):
    """Per-house breakdown column for the Seq 10 card."""
    colour    = HOUSE_HEX[house]
    total     = m.get('total', 0)
    active    = m.get('active', 0)
    inc_rec   = m.get('inactive_recent', 0)
    in_scope  = m.get('migration_scope', 0)
    archive   = m.get('archive', 0)

    def row(label, value, bold=False, accent=False, muted=False, top_border=False):
        return html.Div(style={
            'display': 'flex', 'justifyContent': 'space-between',
            'alignItems': 'baseline', 'padding': '4px 0',
            'borderTop': f'1px solid {UI["border"]}' if top_border else 'none',
        }, children=[
            html.Span(label, style={
                'fontSize': '12px',
                'color': UI['text_secondary'] if muted else UI['text_primary'],
                'fontWeight': '600' if bold else '400',
            }),
            html.Span(f'{value:,}', style={
                'fontSize': '13px' if not bold else '15px',
                'fontWeight': '800' if bold else '500',
                'color': colour if accent else (UI['text_secondary'] if muted else UI['text_primary']),
                'fontFamily': DISPLAY_FONT,
            }),
        ])

    return html.Div(style={
        'flex': '1',
        'padding': '20px 24px',
        'borderRight': f'1px solid {UI["border"]}' if house == 'HOC' else 'none',
    }, children=[
        # House label + total extracted
        html.Div(style={'marginBottom': '16px'}, children=[
            html.Div(house, style={
                'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.12em',
                'color': colour, 'textTransform': 'uppercase', 'marginBottom': '6px',
            }),
            html.Div(style={'display': 'flex', 'alignItems': 'baseline', 'gap': '8px'}, children=[
                html.Span(f'{total:,}', style={
                    'fontSize': '36px', 'fontWeight': '900', 'lineHeight': '1',
                    'color': UI['text_primary'], 'fontFamily': DISPLAY_FONT,
                    'letterSpacing': '-0.02em',
                }),
                html.Span('extracted', style={
                    'fontSize': '12px', 'color': UI['text_secondary'],
                }),
            ]),
        ]),

        # Breakdown rows
        html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '0px'}, children=[
            row('Active  (status ≠ C)',          active),
            row('Inactive + recent history',      inc_rec),
            # Scope total — highlighted
            html.Div(style={
                'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'baseline',
                'margin': '8px 0', 'padding': '8px 10px',
                'background': f'{colour}18',
                'borderRadius': '6px',
                'border': f'1px solid {colour}40',
            }, children=[
                html.Span('Migration scope', style={
                    'fontSize': '12px', 'fontWeight': '700', 'color': colour,
                }),
                html.Span(f'{in_scope:,}', style={
                    'fontSize': '16px', 'fontWeight': '900',
                    'color': colour, 'fontFamily': DISPLAY_FONT,
                }),
            ]),
            # Divider
            html.Div(style={'borderTop': f'1px dashed {UI["border"]}', 'margin': '4px 0'}),
            # Archive
            html.Div(style={
                'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'baseline',
                'padding': '4px 0',
            }, children=[
                html.Span('Archive candidates', style={
                    'fontSize': '12px', 'color': UI['text_secondary'],
                }),
                html.Span(f'{archive:,}', style={
                    'fontSize': '13px', 'fontWeight': '500',
                    'color': UI['text_secondary'], 'fontFamily': DISPLAY_FONT,
                }),
            ]),
        ]),
    ])


def _simple_house_col(house, count, count_label, footer_rows):
    """Simpler per-house column for Seq 16 and history cards."""
    colour = HOUSE_HEX[house]
    return html.Div(style={
        'flex': '1', 'display': 'flex', 'flexDirection': 'column',
        'borderRight': f'1px solid {UI["border"]}' if house == 'HOC' else 'none',
    }, children=[
        # Count
        html.Div(style={'padding': '18px 20px', 'flex': '1'}, children=[
            html.Div(house, style={
                'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.12em',
                'color': colour, 'textTransform': 'uppercase', 'marginBottom': '6px',
            }),
            html.Div(style={'display': 'flex', 'alignItems': 'baseline', 'gap': '8px', 'marginBottom': '4px'}, children=[
                html.Span(f'{count:,}', style={
                    'fontSize': '32px', 'fontWeight': '900', 'lineHeight': '1',
                    'color': UI['text_primary'], 'fontFamily': DISPLAY_FONT,
                    'letterSpacing': '-0.02em',
                }),
                html.Span(count_label, style={'fontSize': '12px', 'color': UI['text_secondary']}),
            ]),
        ]),
        # Footer stats
        html.Div(style={
            'background': _FOOTER_BG, 'padding': '10px 20px',
            'borderTop': f'1px solid {UI["border"]}',
            'display': 'flex', 'flexDirection': 'column', 'gap': '4px',
        }, children=[
            html.Div(style={'display': 'flex', 'justifyContent': 'space-between'}, children=[
                html.Span(lbl, style={'fontSize': '11px', 'color': UI['text_secondary']}),
                html.Span(val, style={
                    'fontSize': '11px', 'fontWeight': '700',
                    'color': '#c0392b' if hi else UI['text_primary'],
                }),
            ]) for lbl, val, hi in footer_rows
        ]),
    ])


def _render_intro(ap_vol):
    hoc_m = ap_vol.get('HOC', {}).get('master', {})
    hol_m = ap_vol.get('HOL', {}).get('master', {})
    hoc_t = ap_vol.get('HOC', {}).get('transactions', {})
    hol_t = ap_vol.get('HOL', {}).get('transactions', {})
    hoc_h = ap_vol.get('HOC', {}).get('history', {})
    hol_h = ap_vol.get('HOL', {}).get('history', {})

    _card = lambda children: html.Div(style={
        'borderRadius': '10px', 'overflow': 'hidden',
        'border': f'1px solid {UI["border"]}',
        'boxShadow': '0 2px 12px rgba(42,31,61,0.10)',
        'background': _BODY_BG,
    }, children=children)

    # ── Seq 10: full-width card ───────────────────────────────────────────────
    seq10 = _card([
        _card_header('10', 'Suppliers (Headers & Sites)', 'asuheader',
                     'Full population — no status filter', 'Migration Object', True),
        html.Div(style={'display': 'flex'}, children=[
            _scope_breakdown_col('HOC', hoc_m),
            _scope_breakdown_col('HOL', hol_m),
        ]),
    ])

    # ── Seq 16: open AP invoices ──────────────────────────────────────────────
    seq16 = _card([
        _card_header('16', 'Open AP Invoices', 'asutrans',
                     'Open only — status ≠ C', 'Migration Object', True),
        html.Div(style={'display': 'flex'}, children=[
            _simple_house_col('HOC', hoc_t.get('open_count', 0), 'open invoices', [
                ('Outstanding',  f'£{hoc_t.get("balance", 0):,.0f}',         False),
                ('Overdue',      f'{hoc_t.get("overdue_count", 0):,}',        hoc_t.get('overdue_count', 0) > 0),
            ]),
            _simple_house_col('HOL', hol_t.get('open_count', 0), 'open invoices', [
                ('Outstanding',  f'£{hol_t.get("balance", 0):,.0f}',         False),
                ('Overdue',      f'{hol_t.get("overdue_count", 0):,}',        hol_t.get('overdue_count', 0) > 0),
            ]),
        ]),
    ])

    # ── AP history: scoping extract ───────────────────────────────────────────
    hist = _card([
        _card_header(None, 'AP Transaction History', 'asuhistr',
                     '18-month window — closed transactions', 'Scoping Extract', False),
        html.Div(style={'display': 'flex'}, children=[
            _simple_house_col('HOC', hoc_h.get('total', 0), 'transactions', [
                ('Purpose', 'Scope Seq 10', False),
                ('Criterion', '≤ 18 months', False),
            ]),
            _simple_house_col('HOL', hol_h.get('total', 0), 'transactions', [
                ('Purpose', 'Scope Seq 10', False),
                ('Criterion', '≤ 18 months', False),
            ]),
        ]),
    ])

    return html.Div(style={'marginBottom': '28px'}, children=[
        html.Div(style={
            'display': 'flex', 'alignItems': 'baseline', 'gap': '10px', 'marginBottom': '14px',
        }, children=[
            html.Div('Migration Scope', style={
                'fontSize': '13px', 'fontWeight': '800', 'color': UI['text_primary'],
                'textTransform': 'uppercase', 'letterSpacing': '0.01em',
            }),
            html.Div('Extracts aligned to programme scope objects', style={
                'fontSize': '12px', 'color': UI['text_secondary'],
            }),
        ]),
        # Seq 10 full width
        html.Div(style={'marginBottom': '16px'}, children=[seq10]),
        # Seq 16 + history side by side
        html.Div(style={'display': 'flex', 'gap': '16px'}, children=[seq16, hist]),
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
