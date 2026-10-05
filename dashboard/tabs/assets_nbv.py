"""Net Book Value section of the Assets tab — HoC only.

Built on frames['asset_nbv'] / ['asset_nbv_books'] from core/asset_nbv.py.
Drill-downs (chart bars, origin tiles) open the shared modal via app.py's
handle_asset_nbv_click, using get_nbv_records() below.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc, dash_table

from dashboard.core.asset_nbv import (
    ACCOUNT_CLASS_LABELS, COLUMN_LABELS, NBV_BANDS, NBV_HOUSE, TOLERANCE, active, asset_account_detail,
)
from dashboard.core.theme import UI, HOUSE_HEX, DISPLAY_FONT
from dashboard.shared.dimensions import render_dimension_scorecard, render_dimension_grid
from dashboard.shared.ui import CHART_LAYOUT

_HDR = '#1f1a0f'
_AMBER = '#c07820'
_CURR = '#1f1a0f'
_HIST = '#d9b777'
_NEG = '#c0392b'
_GREEN = '#1a7a4a'

ORIGINS = ['Capitalised in Unit4', 'Migrated (OS)', 'Migrated + Unit4 additions']
ORIGIN_NOTES = {
    'Capitalised in Unit4': 'Bought and capitalised after migration (CA/PC).',
    'Migrated (OS)': 'Opening position imported from the predecessor system at 31 Mar 2013.',
    'Migrated + Unit4 additions': 'Imported through OS, with further capitalisation since.',
}

RECORD_COLUMNS = [(c, COLUMN_LABELS[c]) for c in (
    'asset_id', 'description', 'asset_group', 'origin', 'curr_depr_method',
    'curr_cost', 'curr_depreciation', 'curr_nbv',
    'hist_cost', 'hist_depreciation', 'hist_nbv',
    'reval_reserve', 'trans_types',
)]
_MONEY = {'curr_cost', 'curr_depreciation', 'curr_nbv', 'hist_cost', 'hist_depreciation', 'hist_nbv', 'reval_reserve'}


def gbp(v, short=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return '—'
    sign = '-' if v < 0 else ''
    a = abs(v)
    if short and a >= 1_000_000:
        return f'{sign}£{a / 1_000_000:,.1f}m'
    if short and a >= 10_000:
        return f'{sign}£{a / 1_000:,.0f}k'
    return f'{sign}£{a:,.0f}'


def active_assets(frames):
    """Active, capitalised assets. Abandoned capitalisations (DQ-AB-V02) are excluded."""
    nbv = frames.get('asset_nbv', pd.DataFrame())
    if nbv.empty:
        return nbv
    return nbv[active(nbv)]


def not_capitalised_count(frames):
    nbv = frames.get('asset_nbv', pd.DataFrame())
    if nbv.empty:
        return 0
    return int(((nbv['status'] == 'N') & nbv['not_capitalised']).sum())


def get_nbv_records(frames, kind, key):
    """Assets behind one clicked chart bar or origin tile."""
    a = active_assets(frames)
    if a.empty:
        return a
    col = {'group': 'asset_group', 'band': 'nbv_band', 'origin': 'origin'}.get(kind)
    if not col:
        return a.iloc[0:0]
    out = a[a[col] == key].sort_values('curr_nbv', ascending=False)
    return out[[c for c, _ in RECORD_COLUMNS if c in out.columns]]


def records_table(df, page_size=15):
    shown = df.copy()
    for c in _MONEY & set(shown.columns):
        shown[c] = pd.to_numeric(shown[c], errors='coerce').map(gbp)
    shown = shown.fillna('—')
    cols = [(c, label) for c, label in RECORD_COLUMNS if c in shown.columns]
    return dash_table.DataTable(
        data=shown.to_dict('records'),
        columns=[{'name': label, 'id': c} for c, label in cols],
        sort_action='native', filter_action='native', page_size=page_size,
        style_table={'overflowX': 'auto', 'border': 'none'},
        style_cell={'textAlign': 'left', 'padding': '9px 14px', 'fontSize': '12px',
                    'fontFamily': "'Source Sans Pro', sans-serif", 'color': '#1a1523',
                    'borderColor': '#f0edf8', 'borderLeft': 'none', 'borderRight': 'none',
                    'maxWidth': '260px', 'overflow': 'hidden', 'textOverflow': 'ellipsis'},
        style_cell_conditional=[{'if': {'column_id': c}, 'textAlign': 'right'} for c in _MONEY],
        style_header={'backgroundColor': '#1e1528', 'fontWeight': '600', 'color': 'rgba(255,255,255,0.65)',
                      'fontSize': '11px', 'letterSpacing': '0.05em', 'textTransform': 'uppercase',
                      'borderColor': '#2a1f3d', 'padding': '9px 14px'},
        style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#faf9fd'}],
    )


# ── Building blocks ───────────────────────────────────────────────────────────

def _panel(title, subtitle, children, style=None):
    base = {'background': 'white', 'border': f'1px solid {UI["border"]}', 'borderRadius': '10px',
            'padding': '18px 20px', 'boxShadow': '0 2px 8px rgba(31,26,15,0.06)'}
    base.update(style or {})
    return html.Div(style=base, children=[
        html.Div(title, style={'fontSize': '13px', 'fontWeight': '700', 'color': UI['text_primary']}),
        html.Div(subtitle, style={'fontSize': '11px', 'color': UI['text_secondary'], 'marginTop': '2px',
                                  'marginBottom': '12px', 'lineHeight': '1.5'}) if subtitle else None,
        *children,
    ])


def _kpi(label, value, note, colour=None):
    return html.Div(style={'flex': '1', 'minWidth': '170px', 'background': 'white',
                           'border': f'1px solid {UI["border"]}', 'borderRadius': '10px',
                           'padding': '14px 16px', 'borderTop': f'3px solid {colour or _HDR}'}, children=[
        html.Div(label, style={'fontSize': '10px', 'fontWeight': '700', 'color': UI['text_secondary'],
                               'textTransform': 'uppercase', 'letterSpacing': '0.08em'}),
        html.Div(value, style={'fontSize': '24px', 'fontWeight': '800', 'fontFamily': DISPLAY_FONT,
                               'color': colour or UI['text_primary'], 'marginTop': '6px', 'lineHeight': '1.1'}),
        html.Div(note, style={'fontSize': '11px', 'color': UI['text_secondary'], 'marginTop': '4px'}),
    ])


def _header():
    return html.Div(style={'borderTop': f'1px solid {UI["border"]}', 'paddingTop': '20px', 'marginBottom': '14px',
                           'display': 'flex', 'alignItems': 'center', 'gap': '10px', 'flexWrap': 'wrap'}, children=[
        html.Div('Net Book Value', style={'fontSize': '13px', 'fontWeight': '800', 'color': UI['text_primary'],
                                          'textTransform': 'uppercase', 'letterSpacing': '0.01em'}),
        html.Span(NBV_HOUSE, style={'background': HOUSE_HEX[NBV_HOUSE], 'color': 'white', 'fontSize': '10px',
                                    'fontWeight': '800', 'padding': '2px 8px', 'borderRadius': '4px',
                                    'letterSpacing': '0.1em'}),
        html.Span('HOL not included: its NBV calculation has not been confirmed yet', style={
            'fontSize': '11px', 'color': _AMBER, 'fontWeight': '600'}),
    ])


def _rule_banner():
    def legend(code, label, colour, included):
        return html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px'}, children=[
            html.Span(code, style={'fontFamily': "'Courier New', monospace", 'fontSize': '12px', 'fontWeight': '700',
                                   'background': colour + '1a', 'color': colour, 'padding': '2px 8px',
                                   'borderRadius': '4px', 'minWidth': '64px', 'textAlign': 'center'}),
            html.Span(label, style={'fontSize': '12px', 'color': UI['text_primary']}),
            html.Span('in NBV' if included else 'excluded', style={
                'fontSize': '10px', 'fontWeight': '700', 'color': _GREEN if included else UI['text_secondary']}),
        ])
    return html.Div(style={'background': '#fffbf2', 'border': f'1px solid {_AMBER}40', 'borderLeft': f'4px solid {_AMBER}',
                           'borderRadius': '8px', 'padding': '14px 18px', 'marginBottom': '16px',
                           'display': 'flex', 'gap': '28px', 'flexWrap': 'wrap', 'alignItems': 'center'}, children=[
        html.Div(style={'maxWidth': '520px'}, children=[
            html.Div('How NBV is calculated', style={'fontSize': '12px', 'fontWeight': '700', 'color': '#7a4a00'}),
            html.Div('For each asset and depreciation book (CURR and HIST), add up every posting of any transaction '
                     'type to accounts that start with 1 and end in 00 or 15. Rule confirmed by the asset team and '
                     'checked against 1 Parliament Street and 22 John Islip. Figures cover active assets (status N), '
                     'excluding capitalisations abandoned before the journal was posted.',
                     style={'fontSize': '12px', 'color': UI['text_secondary'], 'lineHeight': '1.6', 'marginTop': '4px'}),
        ]),
        html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '6px'}, children=[
            legend('1xx00', 'Cost / valuation', _GREEN, True),
            legend('1xx15', 'Accumulated depreciation', _GREEN, True),
            legend('70000', 'Revaluation reserve (should equal CURR − HIST)', _AMBER, False),
            legend('other', 'Control, P&L and disposal contra accounts', '#64748b', False),
        ]),
    ])


def _kpis(a, excluded):
    valued = a[a['has_nbv_account']]
    curr = valued['curr_nbv'].sum()
    hist = valued['hist_nbv'].sum()
    reserve = valued['reval_reserve'].sum()
    nil = int((valued['curr_nbv'].abs() < TOLERANCE).sum())
    return html.Div(style={'display': 'flex', 'gap': '12px', 'flexWrap': 'wrap', 'marginBottom': '16px'}, children=[
        _kpi('NBV — CURR book', gbp(curr, short=True), f'Cost / valuation {gbp(valued["curr_cost"].sum(), True)} less '
             f'depreciation {gbp(-valued["curr_depreciation"].sum(), True)}'),
        _kpi('NBV — HIST book', gbp(hist, short=True), f'Cost {gbp(valued["hist_cost"].sum(), True)} less '
             f'depreciation {gbp(-valued["hist_depreciation"].sum(), True)}', _AMBER),
        _kpi('Revaluation reserve', gbp(reserve, short=True), f'CURR − HIST = {gbp(curr - hist, True)}', '#0891b2'),
        _kpi('Assets valued', f'{len(valued):,}', f'of {len(a):,} active assets with postings. '
             f'{excluded:,} never capitalised, excluded (DQ-AB-V02)', _GREEN),
        _kpi('Nil NBV', f'{nil:,}', 'Active, fully written down (CURR)', _AMBER if nil else _GREEN),
    ])


def _band_chart(a):
    valued = a[a['has_nbv_account']]
    g = valued.groupby('nbv_band').agg(n=('asset_id', 'count'), v=('curr_nbv', 'sum')).reindex(NBV_BANDS).fillna(0)
    colours = [_NEG, _AMBER] + ['#8a6d3b'] * (len(NBV_BANDS) - 2)
    fig = go.Figure(go.Bar(
        x=g.index, y=g['n'], marker_color=colours, customdata=g.index,
        text=[f'{int(n):,}' for n in g['n']], textposition='outside',
        hovertext=[gbp(v, True) for v in g['v']],
        hovertemplate='<b>%{x}</b><br>%{y} assets<br>CURR NBV %{hovertext}<br>Click to see the assets<extra></extra>',
    ))
    fig.update_layout(**CHART_LAYOUT)
    fig.update_layout(height=300, showlegend=False, margin=dict(t=24, b=40, l=10, r=10),
                      yaxis=dict(showgrid=True, gridcolor='#f1ede4', title='Assets'))
    return _panel('Assets by NBV band (CURR)', 'Negative and nil bands are the ones to review. Click a bar to see the assets.', [
        dcc.Graph(id={'type': 'nbv-chart', 'index': 'band'}, figure=fig, config={'displayModeBar': False}),
    ], style={'flex': '1', 'minWidth': '420px'})


def _origin_tiles(a):
    valued = a[a['has_nbv_account']]
    tiles = []
    for o in ORIGINS:
        s = valued[valued['origin'] == o]
        tiles.append(html.Button(id={'type': 'nbv-origin-btn', 'index': o}, n_clicks=0, style={
            'flex': '1', 'minWidth': '220px', 'textAlign': 'left', 'cursor': 'pointer',
            'background': 'white', 'border': f'1px solid {UI["border"]}', 'borderRadius': '10px',
            'padding': '14px 16px', 'fontFamily': 'inherit',
        }, children=[
            html.Div(o, style={'fontSize': '12px', 'fontWeight': '700', 'color': UI['text_primary']}),
            html.Div(ORIGIN_NOTES[o], style={'fontSize': '11px', 'color': UI['text_secondary'], 'marginTop': '2px'}),
            html.Div(style={'display': 'flex', 'gap': '18px', 'marginTop': '10px', 'alignItems': 'baseline'}, children=[
                html.Span(f'{len(s):,} assets', style={'fontSize': '18px', 'fontWeight': '800', 'fontFamily': DISPLAY_FONT}),
                html.Span(f'CURR {gbp(s["curr_nbv"].sum(), True)}', style={'fontSize': '12px', 'fontWeight': '700', 'color': _CURR}),
                html.Span(f'HIST {gbp(s["hist_nbv"].sum(), True)}', style={'fontSize': '12px', 'fontWeight': '700', 'color': '#8a6d3b'}),
            ]),
        ]))
    return _panel('Where the value comes from', 'Legacy assets carry their 2013 opening position through OS. '
                  'Click a tile to see the assets.', [
        html.Div(style={'display': 'flex', 'gap': '12px', 'flexWrap': 'wrap'}, children=tiles),
    ])


# ── Entry point ───────────────────────────────────────────────────────────────

def render_nbv_section(frames, nbv_dq):
    a = active_assets(frames)
    if a.empty:
        return html.Div([
            _header(),
            html.Div('NBV needs the account-level asset_balances extract (asset_balances_HOC_run.sql with the '
                     'account column). Re-run it and reload.', style={'fontSize': '12px', 'color': _AMBER,
                                                                      'padding': '12px 0 24px'}),
        ])
    return html.Div(style={'marginBottom': '28px'}, children=[
        _header(),
        _rule_banner(),
        _kpis(a, not_capitalised_count(frames)),
        html.Div(style={'display': 'flex', 'gap': '16px', 'flexWrap': 'wrap', 'marginBottom': '16px'},
                 children=[_band_chart(a)]),
        html.Div(style={'marginBottom': '20px'}, children=[_origin_tiles(a)]),
        html.Div('NBV data quality', style={'fontSize': '12px', 'fontWeight': '800', 'color': UI['text_primary'],
                                            'textTransform': 'uppercase', 'margin': '8px 0 12px'}),
        render_dimension_scorecard(nbv_dq),
        render_dimension_grid(nbv_dq, key_prefix='nbv-'),
    ])
