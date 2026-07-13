import pandas as pd
from dash import html
import sys
import os

# Add root directory to sys path to import the new modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dashboard.shared.ui import fmt_gbp
from dashboard.core.config import Scope
from dashboard.core.theme import UI, RAG_HEX, HOUSE_HEX, DISPLAY_FONT
from dashboard.core.volumetrics import get_ap_volumetrics, get_ar_volumetrics, get_gl_volumetrics
from dashboard.tabs.assets import get_asset_intro_data

HOUSES = ['HOC', 'HOL']


def render_summary(dq: pd.DataFrame, frames: dict, master_tab=None) -> html.Div:
    """
    One-slide exec summary: a 2x2 grid, one box per in-scope domain
    (Suppliers, Customers, General Ledger, Fixed Assets). Each box shows
    HOC/HOL volumetrics side by side with that domain's current DQ score.
    Designed to be screenshotted whole for the delivery leadership pack.
    """
    if dq.empty:
        return html.Div(style={'padding': '60px', 'textAlign': 'center', 'color': '#94A3B8'}, children=[
            html.Div("No data available.", style={'fontSize': '18px', 'fontWeight': '600'})
        ])

    domains = [
        ('Suppliers',       [Scope.SUPPLIERS, Scope.AP_INVOICES],                              _supplier_stats(frames)),
        ('Customers',       [Scope.CUSTOMERS, Scope.AR_OPEN_TRANSACTIONS, Scope.AR_HISTORY],    _customer_stats(frames)),
        ('General Ledger',  [Scope.GL_ACCOUNTS, Scope.GL_DIMENSIONS, Scope.GL_BALANCES, Scope.GL_TRANSACTIONS], _gl_stats(frames)),
        ('Fixed Assets',    [Scope.ASSETS],                                                    _asset_stats(frames)),
    ]

    cards = [_domain_card(label, scope_ids, dq, stats) for label, scope_ids, stats in domains]

    return html.Div(style={
        'display': 'grid', 'gridTemplateColumns': 'repeat(2, 1fr)', 'gap': '16px',
    }, children=cards)


# ── Per-domain volumetric stat pickers ────────────────────────────────────────
# Each returns {house: [(label, value_str), ...]} using the same computation
# already used by that domain's own tab, so the numbers always match.

def _supplier_stats(frames: dict) -> dict:
    vol = get_ap_volumetrics(frames)
    out = {}
    for house in HOUSES:
        m = vol.get(house, {}).get('master', {})
        t = vol.get(house, {}).get('transactions', {})
        out[house] = [
            ('Supplier Master',      f"{m.get('total', 0):,}"),
            ('Open AP Invoices',     f"{t.get('open_count', 0):,}"),
            ('Outstanding Balance',  fmt_gbp(t.get('balance', 0))),
        ]
    return out


def _customer_stats(frames: dict) -> dict:
    vol = get_ar_volumetrics(frames)
    out = {}
    for house in HOUSES:
        m = vol.get(house, {}).get('master', {})
        t = vol.get(house, {}).get('transactions', {})
        out[house] = [
            ('Customer Master',     f"{m.get('total', 0):,}"),
            ('Open AR Invoices',    f"{t.get('open_count', 0):,}"),
            ('Outstanding Balance', fmt_gbp(t.get('balance', 0))),
        ]
    return out


def _gl_stats(frames: dict) -> dict:
    vol = get_gl_volumetrics(frames)
    out = {}
    for house in HOUSES:
        acc = vol.get(house, {}).get('accounts', {})
        dv  = vol.get(house, {}).get('dimvalue', {})
        out[house] = [
            ('GL Accounts (Active)',  f"{acc.get('active', 0):,}"),
            ('Dimension Attributes',  f"{dv.get('attr_count', 0):,}"),
            ('Dimension Values',      f"{dv.get('total', 0):,}"),
        ]
    return out


def _asset_stats(frames: dict) -> dict:
    data = get_asset_intro_data(frames)
    out = {}
    for house in HOUSES:
        m = data.get(house, {}).get('master', {})
        g = data.get(house, {}).get('groups', {})
        d = data.get(house, {}).get('depr', {})
        out[house] = [
            ('Asset Register',        f"{m.get('total', 0):,}"),
            ('Asset Groups',          f"{g.get('total', 0):,}"),
            ('Depreciation Records',  f"{d.get('total', 0):,}"),
        ]
    return out


# ── Domain card ────────────────────────────────────────────────────────────────

_CARD_HDR = '#0f2744'

def _domain_card(title: str, scope_ids: list, dq: pd.DataFrame, stats_by_house: dict) -> html.Div:
    sub = dq[dq['scope_id'].isin(scope_ids)]

    columns = []
    for i, house in enumerate(HOUSES):
        columns.append(_house_column(house, stats_by_house.get(house, []), sub[sub['house'] == house]))
        if i == 0:
            columns.append(html.Div(style={
                'width': '1px', 'alignSelf': 'stretch',
                'background': 'linear-gradient(to bottom, transparent, #d0cce0, transparent)',
            }))

    return html.Div(style={
        'background': UI['card_bg'], 'border': f"1px solid {UI['border']}",
        'borderRadius': '10px', 'overflow': 'hidden',
        'boxShadow': '0 1px 4px rgba(59,26,110,0.06)',
    }, children=[
        html.Div(style={
            'padding': '10px 18px', 'background': _CARD_HDR,
        }, children=[
            html.Span(title.upper(), style={
                'fontSize': '12px', 'fontWeight': '800', 'letterSpacing': '1.2px',
                'color': '#ffffff',
            }),
        ]),
        html.Div(style={'display': 'flex', 'padding': '16px 18px', 'gap': '18px'}, children=columns),
    ])


def _house_column(house: str, stats: list, house_dq: pd.DataFrame) -> html.Div:
    house_hex = HOUSE_HEX.get(house, '#4a3d6b')
    house_rgb = ','.join(str(int(house_hex[i:i + 2], 16)) for i in (1, 3, 5))

    total = len(house_dq)
    green = int((house_dq['rag'] == 'Green').sum()) if total else 0
    amber = int((house_dq['rag'] == 'Amber').sum()) if total else 0
    red   = int((house_dq['rag'] == 'Red').sum())   if total else 0
    score = round(green / total * 100) if total else 0
    score_color = RAG_HEX['Green'] if score >= 90 else RAG_HEX['Amber'] if score >= 70 else RAG_HEX['Red']

    stat_rows = [
        html.Div(style={
            'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'baseline', 'padding': '3px 0',
        }, children=[
            html.Span(label, style={'fontSize': '11px', 'color': UI['text_secondary']}),
            html.Span(value, style={
                'fontSize': '13px', 'fontWeight': '700', 'color': UI['text_primary'], 'fontFamily': DISPLAY_FONT,
            }),
        ])
        for label, value in stats
    ]

    rag_dots = html.Div(style={'display': 'flex', 'gap': '10px', 'marginTop': '4px'}, children=[
        _rag_dot(red,   'Red',   RAG_HEX['Red']),
        _rag_dot(amber, 'Amber', RAG_HEX['Amber']),
        _rag_dot(green, 'Green', RAG_HEX['Green']),
    ])

    return html.Div(style={'flex': '1', 'minWidth': '0'}, children=[
        html.Span(house, style={
            'fontSize': '9px', 'fontWeight': '800', 'letterSpacing': '1.5px',
            'color': house_hex, 'background': f'rgba({house_rgb},0.12)',
            'padding': '2px 7px', 'borderRadius': '3px',
        }),
        html.Div(stat_rows, style={'marginTop': '8px', 'marginBottom': '10px'}),
        html.Div(style={'borderTop': f"1px solid {UI['border']}", 'paddingTop': '8px'}, children=[
            html.Div(style={'display': 'flex', 'alignItems': 'baseline', 'gap': '6px'}, children=[
                html.Span(f'{score}%' if total else '—', style={
                    'fontSize': '20px', 'fontWeight': '800', 'color': score_color if total else UI['text_secondary'],
                    'fontFamily': DISPLAY_FONT,
                }),
                html.Span('DQ Score', style={
                    'fontSize': '9px', 'color': UI['text_secondary'],
                    'textTransform': 'uppercase', 'letterSpacing': '0.06em',
                }),
            ]),
            rag_dots,
        ]),
    ])


def _rag_dot(count: int, label: str, colour: str) -> html.Span:
    return html.Span([
        html.Span('●', style={'color': colour, 'marginRight': '3px'}),
        f'{count} {label}',
    ], style={'fontSize': '10px', 'color': UI['text_secondary'], 'fontWeight': '600'})
