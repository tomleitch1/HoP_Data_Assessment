from dash import html
from dashboard.shared.ui import render_volumetrics_card
from dashboard.shared.dimensions import render_dimension_scorecard, render_dimension_grid, render_dimensions_table
from dashboard.tabs.aging import render_aging
from dashboard.data_engine import build_aging_analysis
from dashboard.core.volumetrics import get_ap_volumetrics
from dashboard.core.theme import UI, HOUSE_HEX


def _stat(label, value):
    return html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '2px'}, children=[
        html.Span(value, style={'fontSize': '20px', 'fontWeight': '700', 'color': UI['text_primary']}),
        html.Span(label, style={'fontSize': '11px', 'color': UI['text_secondary'], 'textTransform': 'uppercase', 'letterSpacing': '0.04em'}),
    ])


def _dataset_row(name, seq, description, total, active, extract_date, house_colour):
    return html.Div(style={
        'display': 'flex', 'alignItems': 'center', 'gap': '20px',
        'padding': '14px 16px', 'background': UI['card_bg'],
        'border': f'1px solid {UI["border"]}', 'borderRadius': '6px',
        'borderLeft': f'4px solid {house_colour}',
    }, children=[
        html.Div(style={'minWidth': '180px'}, children=[
            html.Div(name, style={'fontWeight': '700', 'fontSize': '13px', 'color': UI['text_primary']}),
            html.Div(f'Seq {seq} — {description}', style={'fontSize': '11px', 'color': UI['text_secondary'], 'marginTop': '2px'}),
        ]),
        html.Div(style={'display': 'flex', 'gap': '32px', 'flex': '1'}, children=[
            _stat('Total records', f'{total:,}'),
            _stat('Active', f'{active:,}' if active is not None else '—'),
            _stat('Inactive', f'{total - active:,}' if active is not None else '—'),
            _stat('Extract date', extract_date or 'Unknown'),
        ]),
    ])


def _render_intro(ap_vol):
    blocks = []
    for house in ['HOC', 'HOL']:
        v = ap_vol.get(house, {})
        m = v.get('master', {})
        t = v.get('transactions', {})
        h = v.get('history', {})
        colour = HOUSE_HEX[house]

        rows = [
            _dataset_row(
                'Supplier Master', '10', 'asuheader — all suppliers regardless of status',
                m.get('total', 0), m.get('active', 0), m.get('extract_date'), colour
            ),
            _dataset_row(
                'Open AP Transactions', '16', 'asutrans — open invoices and credit notes',
                t.get('open_count', 0), None, t.get('extract_date'), colour
            ),
            _dataset_row(
                'AP History', '18', 'asuhistr — closed transactions (18 month window)',
                h.get('total', 0), None, None, colour
            ),
        ]

        overdue = t.get('overdue_count', 0)
        balance = t.get('balance', 0.0)
        sundry  = m.get('status_breakdown', {})

        summary_chips = [
            html.Span(f'£{balance:,.0f} outstanding balance',
                      style={'padding': '3px 10px', 'background': UI['purple_light'],
                             'borderRadius': '12px', 'fontSize': '12px', 'color': UI['text_primary']}),
            html.Span(f'{overdue:,} invoices overdue',
                      style={'padding': '3px 10px', 'background': '#fef3cd',
                             'borderRadius': '12px', 'fontSize': '12px', 'color': '#7a5800'}),
        ]

        blocks.append(html.Div(style={'marginBottom': '24px'}, children=[
            html.Div(style={
                'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between',
                'marginBottom': '10px'
            }, children=[
                html.Div(house, style={
                    'fontWeight': '800', 'fontSize': '13px', 'letterSpacing': '0.08em',
                    'color': colour, 'textTransform': 'uppercase',
                }),
                html.Div(style={'display': 'flex', 'gap': '8px'}, children=summary_chips),
            ]),
            html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '8px'}, children=rows),
        ]))

    return html.Div(style={
        'background': UI['card_bg_dark'], 'borderRadius': '8px',
        'padding': '20px', 'marginBottom': '24px',
        'border': f'1px solid {UI["border"]}',
    }, children=[
        html.Div(style={'marginBottom': '16px'}, children=[
            html.Div('Data Extract Summary', style={
                'fontWeight': '700', 'fontSize': '15px', 'color': UI['text_primary'], 'marginBottom': '4px'
            }),
            html.Div(
                'Three datasets extracted from Agresso covering the full supplier and AP lifecycle. '
                'DQ checks below apply to the active supplier population and open transactions.',
                style={'fontSize': '12px', 'color': UI['text_secondary']}
            ),
        ]),
        *blocks,
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
