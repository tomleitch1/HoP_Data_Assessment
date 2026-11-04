"""Visual tokens and small building blocks for the Migration Scope screens."""
from dash import html
from dash_iconify import DashIconify

from migration_scope.core.model import (
    KEEP, FIX, MONITOR, CLOSE, HOLD_NONCOMMERCIAL, HOLD_POLICY, OUT_OF_SCOPE, NOT_IN_EXTRACT,
    AWAITING, DECIDED, OVERRIDDEN, NO_DECISION_NEEDED,
)

INK, MUTED, FAINT, LINE, BG = '#0F172A', '#64748B', '#94A3B8', '#E2E8F0', '#F8FAFC'
BRAND = '#006548'
HOUSE = {'HOC': '#00703c', 'HOL': '#9b2335'}
HOUSE_NAME = {'HOC': 'House of Commons', 'HOL': 'House of Lords'}

CLASS_COLOUR = {
    KEEP: '#15803D', FIX: '#C2410C', MONITOR: '#7C3AED', CLOSE: '#475569',
    HOLD_NONCOMMERCIAL: '#0369A1', HOLD_POLICY: '#0E7490', OUT_OF_SCOPE: '#94A3B8', NOT_IN_EXTRACT: '#94A3B8',
}
CLASS_BG = {
    KEEP: '#DCFCE7', FIX: '#FFEDD5', MONITOR: '#EDE9FE', CLOSE: '#E2E8F0',
    HOLD_NONCOMMERCIAL: '#E0F2FE', HOLD_POLICY: '#CFFAFE', OUT_OF_SCOPE: '#F1F5F9', NOT_IN_EXTRACT: '#F1F5F9',
}
CLASS_HELP = {
    KEEP: 'Migrates as is', FIX: 'Migrates once fixed', MONITOR: 'Duplicate still in use',
    CLOSE: 'Recommended for closure', HOLD_NONCOMMERCIAL: 'Members, staff, witnesses',
    HOLD_POLICY: 'Card accounts', OUT_OF_SCOPE: 'Closed or terminated', NOT_IN_EXTRACT: 'Missing from extract',
}
STATUS_COLOUR = {AWAITING: '#B45309', DECIDED: '#15803D', OVERRIDDEN: '#7C3AED', NO_DECISION_NEEDED: FAINT}
DIM_COLOUR = {'Completeness': '#2563EB', 'Validity': '#CA8A04', 'Consistency': '#0D9488', 'Duplicate': '#9333EA'}

CARD = {'background': 'white', 'border': f'1px solid {LINE}', 'borderRadius': '14px',
        'boxShadow': '0 1px 2px rgba(15,23,42,0.04)'}


def icon(name, size=16, colour=MUTED):
    return DashIconify(icon=name, width=size, color=colour)


def pill(text, colour, bg=None, size='11px'):
    return html.Span(text, className='ms-pill', style={
        'color': colour, 'background': bg or f'{colour}14', 'fontSize': size})


def class_pill(c, size='11px'):
    return pill(c, CLASS_COLOUR.get(c, MUTED), CLASS_BG.get(c), size)


def house_pill(h):
    return pill('HoC' if h == 'HOC' else 'HoL', HOUSE.get(h, MUTED))


def card(children, style=None, **kw):
    return html.Div(children, style={**CARD, 'padding': '20px', **(style or {})}, **kw)


def section_title(title, sub=None, right=None, ic=None):
    return html.Div(className='ms-section-title', children=[
        html.Div([
            html.Div([icon(ic, 17, BRAND) if ic else None, html.Span(title)],
                     style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'fontSize': '15px',
                            'fontWeight': '700', 'color': INK}),
            html.Div(sub, style={'fontSize': '12px', 'color': MUTED, 'marginTop': '2px'}) if sub else None,
        ]),
        right,
    ])


def delta(n, good_when_up=True):
    if n is None:
        return html.Span('no previous snapshot', className='ms-delta', style={'color': FAINT})
    if n == 0:
        return html.Span('no change', className='ms-delta', style={'color': FAINT})
    up = n > 0
    good = up == good_when_up
    return html.Span(f"{'▲' if up else '▼'} {abs(n):,} since last snapshot", className='ms-delta',
                     style={'color': '#15803D' if good else '#B91C1C'})


def fmt_money(v):
    try:
        return f'£{v:,.0f}'
    except (TypeError, ValueError):
        return ''


def fmt_date(d):
    try:
        return d.strftime('%d %b %Y')
    except (AttributeError, ValueError):
        return '—'
