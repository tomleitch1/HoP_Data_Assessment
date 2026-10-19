"""
Projects tab (Seq 22): migration scope viewer.

Answers, top to bottom:
  1. What is in scope?            hero, scope filter, headline, category / portfolio
  2. What is the opening position? opening position table (click a project), spend history
  3. Can the data be trusted?      coverage and reconciliation, DQ checks, Data Profile

Every chart bar, tile and table row drills into the shared modal. A project
(Unit) opens a project view; any list of projects in the modal can be clicked
through to that view too. Callbacks live in app.py; the figures come from
dashboard/core/projects.py. Design: build_spec/projects_tab.md.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import dash_table, dcc, html
from dash.dash_table.Format import Format, Group, Scheme, Symbol
from dash_iconify import DashIconify

from dashboard.core.projects import (
    COLUMN_LABELS, HOUSES, LIVE_MONTHS, RESIDUAL_COMMITMENT_MAX, SIGNAL_HEX, SIGNAL_ORDER, STALE_COMMITMENT_MONTHS,
    TRUNCATED_WINDOW_MONTHS, TYPE_HEX, TYPE_ORDER, coverage, opening_table, period_label, profile,
    project_population, scope_view, unit_detail,
)
from dashboard.core.rules.project_rules import get_project_checks
from dashboard.core.theme import DISPLAY_FONT, HOUSE_HEX, PLOTLY_HOVER_CONFIG
from dashboard.shared.dimensions import render_dimension_grid, render_dimension_scorecard

# ── Design tokens: deep ink blue with an amber accent ─────────────────────────
_HDR_BG, _HDR2_BG = '#0b1733', '#14285a'
_ACCENT = '#f2a93b'
_INK = '#0f172a'
_MUTED = '#64748b'
_FAINT = '#94a3b8'
_BORDER = '#e2e8f0'
_PANEL = '#f8fafc'
_NEG = '#c0392b'
_OK = '#16a34a'
_WARN = '#d97706'

DEFAULT_FILTERS = {'scope': 'all', 'cost': 'all', 'house': 'both'}

KIND_LABELS = {
    'all': 'All projects', 'type': 'Category', 'portfolio': 'Portfolio', 'house': 'House', 'signal': 'Activity',
    'fy': 'Financial year', 'commit_age': 'Open commitments', 'coverage': 'Coverage', 'cost_type': 'Cost type',
    'truncated': 'History may be incomplete', 'idle': 'No activity', 'unit': 'Project',
}
COVERAGE_LABELS = {'matched': 'Listed, with activity', 'idle': 'Listed, no activity since April 2020',
                   'off_list': 'In financials, not on the list'}

_MONEY_COLS = {'spend_to_date', 'commitments', 'budget_to_date', 'remaining_budget', 'remaining_after_commitments',
               'actuals', 'budget', 'committed', 'cumulative_actuals', 'cumulative_budget', 'actuals_total',
               'budget_total', 'committed_total', 'current_fy_actuals', 'current_fy_budget',
               'hoc_spend_to_date', 'hol_spend_to_date', 'hoc_commitments', 'hol_commitments',
               'hoc_remaining_budget', 'hol_remaining_budget'}
_MONEY_FMT = Format(precision=0, scheme=Scheme.fixed, group=Group.yes, symbol=Symbol.yes, symbol_prefix='£')


# ── Formatting helpers ────────────────────────────────────────────────────────

def gbp(v, dp=1):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return '—'
    v = float(v)
    sign = '−' if v < 0 else ''
    a = abs(v)
    if a >= 1_000_000_000:
        return f'{sign}£{a / 1e9:.2f}bn'
    if a >= 1_000_000:
        return f'{sign}£{a / 1e6:.{dp}f}m'
    if a >= 1_000:
        return f'{sign}£{a / 1e3:.{dp}f}k'
    return f'{sign}£{a:,.0f}'


def filters_from(states) -> dict:
    """Pattern-matching State list ({'id': {'index': ...}, 'value': ...}) -> filter dict."""
    f = dict(DEFAULT_FILTERS)
    for s in states or []:
        try:
            f[s['id']['index']] = s.get('value') or f[s['id']['index']]
        except (KeyError, TypeError):
            continue
    return f


def filter_args(f: dict) -> dict:
    return {'include_annual': f.get('scope') != 'projects', 'expenditure_only': f.get('cost') == 'exp',
            'houses': None if f.get('house') in (None, 'both') else [f['house']]}


def filter_summary(f: dict) -> str:
    parts = ['Projects only (Annual Requirements excluded)' if f.get('scope') == 'projects' else 'All listed codes',
             'expenditure only' if f.get('cost') == 'exp' else 'all cost types',
             {'both': 'both houses', 'HOC': 'House of Commons', 'HOL': 'House of Lords'}.get(f.get('house'), 'both houses')]
    return ' · '.join(parts)


def _badge(text, bg, color):
    return html.Span(text, style={'background': bg, 'color': color, 'fontSize': '10px', 'fontWeight': '800',
                                  'letterSpacing': '0.1em', 'padding': '3px 9px', 'borderRadius': '4px',
                                  'textTransform': 'uppercase'})


def _section(title, subtitle='', icon='lucide:folder-kanban'):
    return html.Div(style={'borderTop': f'1px solid {_BORDER}', 'margin': '8px 0 18px', 'paddingTop': '22px',
                                      'display': 'flex', 'alignItems': 'center', 'gap': '10px'}, children=[
        DashIconify(icon=icon, width=18, color='#334155'),
        html.Div(title, style={'fontSize': '16px', 'fontWeight': '700', 'color': '#1e293b'}),
        html.Span(subtitle, style={'fontSize': '12px', 'color': _FAINT}) if subtitle else None,
    ])


def _card(title, subtitle, children, flex='1', question=None):
    return html.Div(style={'background': 'white', 'border': f'1px solid {_BORDER}', 'borderRadius': '12px',
                           'padding': '20px 22px', 'boxShadow': '0 2px 8px rgba(15,23,42,0.04)', 'flex': flex,
                           'minWidth': '320px', 'display': 'flex', 'flexDirection': 'column'}, children=[
        html.Div(question, style={'fontSize': '10px', 'fontWeight': '800', 'color': _ACCENT, 'letterSpacing': '0.1em',
                                  'textTransform': 'uppercase', 'marginBottom': '6px'}) if question else None,
        html.Div(title, style={'fontSize': '14px', 'fontWeight': '700', 'color': '#1e293b'}),
        html.Div(subtitle, style={'fontSize': '12px', 'color': _FAINT, 'margin': '3px 0 14px'}) if subtitle else None,
        *children,
    ])


def _reading(text, tone='info'):
    colour = {'info': '#1e40af', 'ok': _OK, 'warn': _WARN, 'bad': _NEG}[tone]
    icon = {'info': 'lucide:info', 'ok': 'lucide:check-circle-2', 'warn': 'lucide:alert-triangle',
            'bad': 'lucide:alert-octagon'}[tone]
    return html.Div(style={'display': 'flex', 'gap': '8px', 'alignItems': 'flex-start', 'background': _PANEL,
                           'border': f'1px solid {_BORDER}', 'borderLeft': f'3px solid {colour}',
                           'borderRadius': '8px', 'padding': '10px 12px', 'marginTop': '12px'}, children=[
        DashIconify(icon=icon, width=15, color=colour, style={'flexShrink': '0', 'marginTop': '2px'}),
        html.Div(text, style={'fontSize': '12.5px', 'color': '#334155', 'lineHeight': '1.5'}),
    ])


def _drill_button(kind, key, children, style=None):
    base = {'background': 'none', 'border': 'none', 'padding': '0', 'margin': '0', 'cursor': 'pointer',
            'textAlign': 'left', 'font': 'inherit', 'color': 'inherit', 'width': '100%'}
    return html.Button(children, id={'type': 'prj-drill', 'kind': kind, 'key': str(key)}, n_clicks=0,
                       style={**base, **(style or {})}, title='Click to see the records')


def _chart_layout(fig, height, **kw):
    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=height,
                      font=dict(family="'Poppins', sans-serif", size=11, color=_MUTED),
                      margin=dict(t=10, b=30, l=10, r=10), hoverlabel=dict(font_size=12),
                      legend=dict(orientation='h', y=-0.18, x=0, font=dict(size=11)), **kw)
    fig.update_xaxes(gridcolor='#f1f5f9', zeroline=False)
    fig.update_yaxes(gridcolor='#f1f5f9', zeroline=False)
    return fig


def _graph(kind, fig):
    return dcc.Graph(id={'type': 'prj-chart', 'index': kind}, figure=fig, config=PLOTLY_HOVER_CONFIG,
                     style={'cursor': 'pointer'})


def records_table(df: pd.DataFrame, table_index='drill', page_size=15, clickable_units=True) -> html.Div:
    """A sortable, filterable table for any project records. Rows with a Unit can be
    clicked to open that project."""
    if df is None or df.empty:
        return html.Div('No records.', style={'padding': '40px', 'textAlign': 'center', 'color': _FAINT})
    df = df.copy()
    for c in ('first_period', 'last_period', 'period'):
        if c in df.columns and pd.api.types.is_numeric_dtype(df[c]):
            df[c] = df[c].map(period_label) if c != 'period' else df[c].map(lambda p: '' if pd.isna(p) else str(int(p)))
    for c in df.columns:
        if df[c].dtype == bool:
            df[c] = df[c].map({True: 'Yes', False: 'No'})
    cols = []
    for c in df.columns:
        col = {'name': COLUMN_LABELS.get(c, c), 'id': c}
        if c in _MONEY_COLS:
            col.update(type='numeric', format=_MONEY_FMT)
        cols.append(col)
    neg_rules = [{'if': {'filter_query': f'{{{c}}} < 0', 'column_id': c}, 'color': _NEG, 'fontWeight': '600'}
                 for c in df.columns if c in _MONEY_COLS]
    signal_rules = [{'if': {'filter_query': f'{{signal}} = "{s}"', 'column_id': 'signal'}, 'color': SIGNAL_HEX[s],
                     'fontWeight': '700'} for s in SIGNAL_ORDER] if 'signal' in df.columns else []
    can_click = clickable_units and 'unit' in df.columns
    return html.Div([
        html.Div('Click any row to open that project.' if can_click else '',
                 style={'fontSize': '11px', 'color': _FAINT, 'margin': '0 0 6px'}),
        dash_table.DataTable(
            id={'type': 'prj-table', 'index': table_index},
            columns=cols, data=df.to_dict('records'), page_size=page_size,
            sort_action='native', filter_action='native', page_action='native',
            style_table={'overflowX': 'auto'},
            style_cell={'fontFamily': "'Poppins', sans-serif", 'fontSize': '12px', 'padding': '9px 12px',
                        'textAlign': 'left', 'border': 'none', 'borderBottom': '1px solid #f1f5f9',
                        'maxWidth': '320px', 'overflow': 'hidden', 'textOverflow': 'ellipsis',
                        'cursor': 'pointer' if can_click else 'default'},
            style_cell_conditional=[{'if': {'column_id': c}, 'textAlign': 'right'} for c in df.columns if c in _MONEY_COLS],
            style_header={'backgroundColor': '#1e1528', 'color': 'white', 'fontWeight': '600', 'fontSize': '11px',
                          'border': 'none', 'whiteSpace': 'normal', 'height': 'auto'},
            style_filter={'backgroundColor': '#faf9fd', 'fontSize': '11px'},
            style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#fbfcfe'},
                                    {'if': {'state': 'active'}, 'backgroundColor': '#eef2ff', 'border': '1px solid #c7d2fe'},
                                    *neg_rules, *signal_rules],
            tooltip_duration=None,
        ),
    ])


# ── Hero and filters ──────────────────────────────────────────────────────────

def _render_hero(frames, view, cov) -> html.Div:
    pos, bounds = view['positions'], view['bounds']
    listed = view['listed_units']

    def stat(value, label):
        return html.Div(style={'minWidth': '120px'}, children=[
            html.Div(value, style={'fontSize': '22px', 'fontWeight': '800', 'color': 'rgba(255,255,255,0.94)',
                                   'lineHeight': '1', 'fontFamily': DISPLAY_FONT}),
            html.Div(label, style={'fontSize': '10px', 'fontWeight': '700', 'color': 'rgba(255,255,255,0.45)',
                                   'textTransform': 'uppercase', 'letterSpacing': '0.1em', 'marginTop': '6px'}),
        ])

    fin = frames.get('project_financials')
    return html.Div(style={
        'background': (f'radial-gradient(ellipse 900px 420px at 10% 0%, rgba(242,169,59,0.18), transparent 60%), '
                       f'linear-gradient(155deg, {_HDR_BG}, {_HDR2_BG})'),
        'borderRadius': '14px', 'padding': '32px 40px', 'marginBottom': '20px',
        'boxShadow': '0 8px 32px rgba(11,23,51,0.25)'}, children=[
        html.Div(style={'display': 'flex', 'gap': '8px', 'marginBottom': '22px', 'flexWrap': 'wrap'}, children=[
            _badge('Seq 22', '#2b3d70', '#ffd591'), _badge('Projects', '#1d3366', '#b9cdfa'),
            _badge('Both houses', '#1d3366', '#b9cdfa'), _badge('Scope viewer', '#3a2f12', '#ffd591'),
        ]),
        html.Div('Opening cumulative position (spend to date, commitments and remaining budget) as at cutover '
                 'for all projects active at go-live.',
                 style={'fontSize': '14px', 'color': 'rgba(255,255,255,0.72)', 'maxWidth': '780px',
                        'marginBottom': '24px', 'lineHeight': '1.6'}),
        html.Div(style={'display': 'flex', 'alignItems': 'flex-end', 'gap': '48px', 'flexWrap': 'wrap'}, children=[
            html.Div([
                html.Div('Spend to date, all listed projects', style={
                    'fontSize': '11px', 'fontWeight': '700', 'color': 'rgba(255,255,255,0.5)',
                    'textTransform': 'uppercase', 'letterSpacing': '0.12em', 'marginBottom': '8px'}),
                html.Div(gbp(pos['spend_to_date'].sum()), style={
                    'fontSize': '50px', 'fontWeight': '800', 'color': 'white', 'lineHeight': '1',
                    'fontFamily': DISPLAY_FONT, 'letterSpacing': '-1.5px'}),
                html.Div(style={'width': '48px', 'height': '4px', 'background': _ACCENT, 'borderRadius': '2px',
                                'marginTop': '14px'}),
            ]),
            html.Div(style={'display': 'flex', 'gap': '34px', 'paddingBottom': '6px', 'flexWrap': 'wrap'}, children=[
                stat(f"{len(listed):,}", 'Projects listed'),
                stat(f"{cov['listed_codes']:,}", 'Cost lines listed'),
                stat(gbp(pos['commitments'].sum()), 'Open commitments'),
                stat(period_label(bounds.get('latest')), 'Data as at'),
                stat(period_label(bounds.get('first')), 'History from'),
            ]),
        ]),
        html.Div(f"Sources: project list ({cov['listed_codes']:,} cost lines across {len(listed):,} projects) · "
                 f"financials ({len(fin):,} rows, {cov['fin_codes']:,} cost lines)" if fin is not None else '',
                 style={'fontSize': '11px', 'color': 'rgba(255,255,255,0.4)', 'marginTop': '22px'}),
    ])


def _segmented(index, label, options, value):
    return html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '6px'}, children=[
        html.Div(label, style={'fontSize': '10px', 'fontWeight': '800', 'color': _FAINT, 'letterSpacing': '0.1em',
                               'textTransform': 'uppercase'}),
        dcc.RadioItems(
            id={'type': 'prj-filter', 'index': index}, options=options, value=value, inline=True,
            className='prj-segmented',
            inputStyle={'display': 'none'},
            labelStyle={'padding': '7px 14px', 'border': f'1px solid {_BORDER}', 'marginRight': '-1px',
                        'fontSize': '12px', 'fontWeight': '600', 'color': '#334155', 'cursor': 'pointer',
                        'background': 'white'},
        ),
    ])


def _render_filters() -> html.Div:
    return html.Div(style={'position': 'sticky', 'top': '0', 'zIndex': 20, 'background': 'rgba(244,247,249,0.94)',
                           'backdropFilter': 'blur(6px)', 'padding': '12px 0 14px', 'marginBottom': '6px'}, children=[
        html.Div(style={'display': 'flex', 'gap': '28px', 'alignItems': 'flex-end', 'flexWrap': 'wrap',
                        'background': 'white', 'border': f'1px solid {_BORDER}', 'borderRadius': '12px',
                        'padding': '14px 18px', 'boxShadow': '0 2px 8px rgba(15,23,42,0.04)'}, children=[
            DashIconify(icon='lucide:sliders-horizontal', width=18, color='#334155', style={'marginBottom': '8px'}),
            _segmented('scope', 'Scope', [{'label': 'All listed codes', 'value': 'all'},
                                          {'label': 'Projects only', 'value': 'projects'}], DEFAULT_FILTERS['scope']),
            _segmented('cost', 'Cost types', [{'label': 'All', 'value': 'all'},
                                              {'label': 'Expenditure only', 'value': 'exp'}], DEFAULT_FILTERS['cost']),
            _segmented('house', 'House', [{'label': 'Both', 'value': 'both'}, {'label': 'HoC', 'value': 'HOC'},
                                          {'label': 'HoL', 'value': 'HOL'}], DEFAULT_FILTERS['house']),
            html.Div(style={'flex': '1', 'minWidth': '260px', 'fontSize': '11.5px', 'color': _MUTED,
                            'lineHeight': '1.5'}, children=[
                html.B('Scope decision pending. ', style={'color': _WARN}),
                "Are Annual Requirements Units (staff, property running costs) projects for the new projects module? "
                "Switch Scope to compare. 'Expenditure only' leaves out income and recharge cost types (provisional rule). "
                'Filters apply to every section except Data Quality and Data Profile.',
            ]),
        ]),
    ])


# ── Scope sections (re-rendered when the filters change) ──────────────────────

def _kpi(label, value, sub_rows, accent, drill=None):
    body = html.Div(style={'background': 'white', 'border': f'1px solid {_BORDER}', 'borderTop': f'3px solid {accent}',
                           'borderRadius': '10px', 'padding': '16px 18px', 'height': '100%',
                           'boxShadow': '0 2px 6px rgba(15,23,42,0.03)'}, children=[
        html.Div(value, style={'fontSize': '24px', 'fontWeight': '800', 'color': _INK, 'fontFamily': DISPLAY_FONT,
                               'lineHeight': '1'}),
        html.Div(label, style={'fontSize': '10px', 'fontWeight': '700', 'color': _FAINT, 'textTransform': 'uppercase',
                               'letterSpacing': '0.07em', 'marginTop': '8px'}),
        html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '3px', 'marginTop': '10px'}, children=sub_rows),
    ])
    wrap = {'flex': '1', 'minWidth': '170px'}
    return html.Div(_drill_button(drill[0], drill[1], body, {'height': '100%'}) if drill else body, style=wrap)


def _sub(label, value, colour=None, drill=None):
    row = html.Div(style={'display': 'flex', 'justifyContent': 'space-between', 'gap': '8px', 'fontSize': '11.5px'},
                   children=[html.Span(style={'color': _MUTED, 'display': 'flex', 'alignItems': 'center', 'gap': '5px'},
                                       children=[html.Span(style={'width': '7px', 'height': '7px', 'borderRadius': '50%',
                                                                  'background': colour or '#cbd5e1'}), label]),
                             html.Span(value, style={'color': '#1e293b', 'fontWeight': '600'})])
    return _drill_button(drill[0], drill[1], row) if drill else row


def _render_headline(view, table) -> html.Div:
    pos = view['positions']
    by_house = pos.groupby('house')[['spend_to_date', 'commitments', 'budget_to_date', 'remaining_budget']].sum()

    def house_rows(col):
        return [_sub(h, gbp(by_house[col].get(h, 0.0)), HOUSE_HEX[h], ('house', h)) for h in HOUSES]

    sig = table['signal'].value_counts()
    houses = table['houses'].value_counts()
    return html.Div(style={'display': 'flex', 'gap': '14px', 'flexWrap': 'wrap', 'marginBottom': '22px'}, children=[
        _kpi('Projects in this view', f"{len(table):,}",
             [_sub(s, f"{int(sig.get(s, 0)):,}", SIGNAL_HEX[s], ('signal', s)) for s in SIGNAL_ORDER],
             '#0f4c81', ('all', 'all')),
        _kpi('Where they sit', f"{int(houses.get('Shared', 0)):,} shared",
             [_sub(h, f"{int(houses.get(h, 0)):,}", HOUSE_HEX.get(h, '#94a3b8'), ('house', h))
              for h in ('HOC', 'HOL', 'Shared', 'No activity')], '#6d28d9'),
        _kpi('Spend to date', gbp(pos['spend_to_date'].sum()), house_rows('spend_to_date'), _ACCENT),
        _kpi('Open commitments', gbp(pos['commitments'].sum()), house_rows('commitments'), '#0891b2'),
        _kpi('Budget to date', gbp(pos['budget_to_date'].sum()), house_rows('budget_to_date'), '#16a34a'),
        _kpi('Remaining budget', gbp(pos['remaining_budget'].sum()), house_rows('remaining_budget'),
             _NEG if pos['remaining_budget'].sum() < 0 else '#16a34a'),
    ])


def _bar_by(table, field, keys, kind, height_per=34):
    """Horizontal bars of spend to date, stacked by house, for each key of `field`."""
    t = table.copy()
    t[field] = t[field].fillna('(blank)')
    order = [k for k in keys if k in set(t[field])] + sorted(set(t[field]) - set(keys))
    fig = go.Figure()
    for h in HOUSES:
        col = f'{h.lower()}_spend_to_date'
        vals = t.groupby(field)[col].sum().reindex(order).fillna(0.0)
        fig.add_trace(go.Bar(y=order, x=vals.values, name=h, orientation='h', marker_color=HOUSE_HEX[h],
                             customdata=order, hovertemplate=f'<b>%{{y}}</b><br>{h} spend to date: £%{{x:,.0f}}<extra></extra>'))
    counts = t.groupby(field)['unit'].nunique().reindex(order).fillna(0).astype(int)
    totals = t.groupby(field)['spend_to_date'].sum().reindex(order).fillna(0.0)
    fig.add_trace(go.Scatter(y=order, x=totals.values, mode='text', text=[f'  {gbp(v)} · {n} projects' for v, n in zip(totals, counts)],
                             textposition='middle right', showlegend=False, hoverinfo='skip', customdata=order,
                             textfont=dict(size=11, color='#334155')))
    _chart_layout(fig, max(220, len(order) * height_per + 60), barmode='stack')
    fig.update_layout(legend_traceorder='normal')   # HOC before HOL
    fig.update_yaxes(autorange='reversed')
    fig.update_xaxes(range=[0, max(totals.max(), 1) * 1.45], tickprefix='£', showgrid=True)
    return _graph(kind, fig)


def _render_breakdowns(table) -> html.Div:
    portfolios = table.groupby(table['projgrp_desc'].fillna('(blank)'))['spend_to_date'].sum().sort_values(ascending=False)
    return html.Div(style={'display': 'flex', 'gap': '18px', 'flexWrap': 'wrap', 'marginBottom': '22px'}, children=[
        _card('By category (Projcat)', 'Spend to date by house. The EPMO focuses on CAT A. Click a bar for its projects.',
              [_bar_by(table, 'project_type', TYPE_ORDER, 'type')], question='What kind of projects?'),
        _card('By portfolio (Projgrp)', 'Each portfolio has an allocated director. Click a bar for its projects.',
              [_bar_by(table, 'projgrp_desc', list(portfolios.index), 'portfolio', 30)], question='Who owns them?'),
    ])


def _render_opening(table) -> html.Div:
    cols = ['unit', 'unit_desc', 'project_type', 'projgrp_desc', 'houses', 'signal', 'spend_to_date', 'commitments',
            'budget_to_date', 'remaining_budget', 'hoc_spend_to_date', 'hol_spend_to_date', 'last_activity']
    return _card('Opening position by project', f'One row per project (Unit), sorted by category then spend. '
                 f'Activity signal: Live = activity in the last {LIVE_MONTHS} months of the data.',
                 [records_table(table[cols], 'opening', page_size=12)], question='What does each project carry over?')


def _render_history(view) -> html.Div:
    h = view['history'].merge(view['listed_units'][['unit', 'project_type']], on='unit', how='left')
    if h.empty:
        return html.Div()
    years = sorted(h['fiscal_year'].unique())
    labels = [f'{int(y)}/{str(int(y) + 1)[2:]}' for y in years]
    fig = go.Figure()
    for t in TYPE_ORDER:
        s = h[h['project_type'] == t].groupby('fiscal_year')['actuals'].sum().reindex(years).fillna(0.0)
        if s.abs().sum() < 1:
            continue
        fig.add_trace(go.Bar(x=labels, y=s.values, name=t, marker_color=TYPE_HEX[t], customdata=labels,
                             hovertemplate=f'<b>%{{x}}</b><br>{t}: £%{{y:,.0f}}<extra></extra>'))
    yearly = h.groupby('fiscal_year')[['actuals', 'budget']].sum().reindex(years).fillna(0.0)
    fig.add_trace(go.Scatter(x=labels, y=yearly['actuals'].cumsum(), name='Spend to date', mode='lines+markers',
                             line=dict(color=_ACCENT, width=3), yaxis='y2', customdata=labels,
                             hovertemplate='<b>%{x}</b><br>Spend to date: £%{y:,.0f}<extra></extra>'))
    fig.add_trace(go.Scatter(x=labels, y=yearly['budget'].cumsum(), name='Budget to date', mode='lines',
                             line=dict(color='#16a34a', width=2, dash='dot'), yaxis='y2', customdata=labels,
                             hovertemplate='<b>%{x}</b><br>Budget to date: £%{y:,.0f}<extra></extra>'))
    _chart_layout(fig, 340, barmode='stack',
                  yaxis=dict(title='Actuals in year', tickprefix='£'),
                  yaxis2=dict(title='To date', overlaying='y', side='right', tickprefix='£', showgrid=False))
    return _card('How the position built up', 'Actuals per financial year by category (bars), with spend and '
                 'budget to date (lines). Click a year for the projects that spent in it.',
                 [_graph('fy', fig)], question='How did it build up?')


def _render_coverage(cov) -> html.Div:
    def tile(key, n, value, colour, note):
        return html.Div(style={'flex': '1', 'minWidth': '210px'}, children=[_drill_button('coverage', key, html.Div(style={
            'border': f'1px solid {_BORDER}', 'borderLeft': f'4px solid {colour}', 'borderRadius': '10px',
            'padding': '14px 16px', 'background': 'white'}, children=[
            html.Div(f'{n:,}', style={'fontSize': '24px', 'fontWeight': '800', 'color': _INK, 'fontFamily': DISPLAY_FONT}),
            html.Div(COVERAGE_LABELS[key], style={'fontSize': '11px', 'fontWeight': '700', 'color': _MUTED,
                                                  'textTransform': 'uppercase', 'letterSpacing': '0.05em', 'marginTop': '4px'}),
            html.Div(value, style={'fontSize': '12px', 'color': '#334155', 'marginTop': '6px'}),
            html.Div(note, style={'fontSize': '11px', 'color': _FAINT, 'marginTop': '4px'}),
        ]))])

    ok = cov['invariant_ok']
    return _card('Do the two files agree?', 'Project list matched to the financials on HAIS code. Click a tile for the cost lines.', [
        html.Div(style={'display': 'flex', 'gap': '12px', 'flexWrap': 'wrap'}, children=[
            tile('matched', cov['matched'], f"{gbp(cov['matched_actuals'])} actuals", _OK, 'In scope and carrying money'),
            tile('idle', cov['idle'], 'Nothing since April 2020', _WARN, 'Candidates to leave out (PRJ_NO_ACTIVITY)'),
            tile('off_list', cov['off_list'], f"{gbp(cov['off_list_actuals'])} actuals", '#94a3b8',
                 'Excluded: ordinary running cost, not projects'),
        ]),
        _reading(f"Reconciliation {'passes' if ok else 'FAILS'}: spend to date across every project position "
                 f"({gbp(cov['position_actuals'], 2)}) {'equals' if ok else 'does not equal'} the actuals on listed cost "
                 f"lines in the raw file ({gbp(cov['on_list_actuals'], 2)}).", 'ok' if ok else 'bad'),
    ], question='Can we trust the join?')


def render_scope_body(frames, f: dict) -> list:
    view = scope_view(frames, **filter_args(f))
    table = opening_table(view)
    cov = coverage(frames)
    return [
        html.Div(f'Showing: {filter_summary(f)}', style={'fontSize': '12px', 'color': _MUTED, 'margin': '4px 0 14px'}),
        _render_headline(view, table),
        _render_breakdowns(table),
        html.Div(style={'marginBottom': '22px'}, children=[_render_opening(table)]),
        html.Div(style={'marginBottom': '22px'}, children=[_render_history(view)]),
        html.Div(style={'marginBottom': '8px'}, children=[_render_coverage(cov)]),
    ]


# ── Data Profile (how the source data behaves; answers Q3-Q6) ─────────────────

def _render_profile(frames) -> html.Details:
    p = profile(frames)
    by_year, by_type = p['by_year'], p['by_type']

    fig_year = go.Figure([
        go.Bar(x=by_year['fy_label'], y=by_year['actuals'], name='Actuals', marker_color=_ACCENT),
        go.Bar(x=by_year['fy_label'], y=by_year['budget'], name='Current budget', marker_color='#16a34a'),
    ])
    _chart_layout(fig_year, 260, barmode='group')
    fig_year.update_yaxes(tickprefix='£')
    yb, yn = p['years_with_budget'], p['years']
    year_read = (_reading(f'Budget exists in all {yn} years, so budget to date and remaining budget can be '
                          'calculated from this file.', 'ok') if yb == yn else
                 _reading(f'Budget exists in {yb} of {yn} years. Budget for the other years is not in this file, so '
                          '"budget for each year since the project started" needs another source.', 'warn'))

    t = by_type.head(12)
    fig_type = go.Figure([
        go.Bar(y=t['cost_type'], x=t['actuals'], name='Actuals', orientation='h', marker_color=_ACCENT,
               customdata=t['cost_type']),
        go.Bar(y=t['cost_type'], x=t['budget'], name='Current budget', orientation='h', marker_color='#16a34a',
               customdata=t['cost_type']),
    ])
    _chart_layout(fig_type, max(240, len(t) * 46 + 60), barmode='group')
    fig_type.update_yaxes(autorange='reversed')
    fig_type.update_xaxes(tickprefix='£')
    unbudgeted = by_type[(by_type['actuals'].abs() > 1000) & (by_type['budget'].abs() < 1)]
    income = by_type[by_type['is_income']]
    type_read = [
        _reading('No budget against: ' + '; '.join(f"{r.cost_type.title()} ({gbp(r.actuals)} spend)"
                                                    for r in unbudgeted.itertuples()) +
                 '. Budget for these is held on other lines, or not at all (see Budget placement).', 'warn')
        if not unbudgeted.empty else _reading('Every cost type with spend has some budget.', 'ok'),
        _reading('Treated as income / recharge by "Expenditure only": ' +
                 (', '.join(r.cost_type.title() for r in income.itertuples()) or 'none found') +
                 '. Confirm this is the right definition (Q5).', 'info'),
    ]

    place = p['placement']
    place_rows = [html.Tr([html.Th(lvl, style={'textAlign': 'left', 'padding': '6px 10px', 'fontWeight': '600',
                                              'color': '#334155'})] +
                          [html.Td(f"{v[k]:,}", style={'padding': '6px 10px', 'textAlign': 'right'})
                           for k in ('Actuals only', 'Budget only', 'Both')]) for lvl, v in place.items()]
    unit_both = place['Project (Unit)']['Both'] / max(1, sum(place['Project (Unit)'].values()))
    line_both = place['Account x cost line']['Both'] / max(1, sum(place['Account x cost line'].values()))
    place_read = _reading(
        f"{line_both:.0%} of account × cost line combinations have both spend and budget, against {unit_both:.0%} "
        "of projects. Budget is often held on different accounts from spend, so the scope compares them at project "
        "level only." if unit_both > line_both + 0.1 else
        f"Budget and spend mostly sit on the same lines ({line_both:.0%} of account × cost line combinations have both).",
        'info')

    age = p['commit_age']
    fig_age = go.Figure(go.Bar(x=age['fy_label'], y=age['sum'], marker_color='#0891b2', customdata=age['fy_label'],
                               text=[f"{n} lines" for n in age['size']], textposition='outside',
                               hovertemplate='<b>Posted to %{x}</b><br>£%{y:,.0f} open<extra></extra>'))
    _chart_layout(fig_age, 240, showlegend=False)
    fig_age.update_yaxes(tickprefix='£')

    rep = p['commit_repeats']
    trunc_read = _reading(
        f"{p['truncated_units']} of {p['units_total']} projects were already spending in the first "
        f"{TRUNCATED_WINDOW_MONTHS} months of the data ({gbp(p['truncated_spend'])} spend to date). Their spend before "
        f"{period_label(p['bounds'].get('first'))} is probably missing from the opening position.",
        'warn' if p['truncated_units'] else 'ok')

    panels = html.Div(style={'display': 'grid', 'gridTemplateColumns': 'repeat(auto-fill, minmax(460px, 1fr))',
                             'gap': '16px', 'padding': '6px 0 4px'}, children=[
        _card('Budget by year', 'Actuals vs current budget per financial year, listed cost lines only.',
              [dcc.Graph(figure=fig_year, config=PLOTLY_HOVER_CONFIG), year_read],
              question='Q4 · Is budget held for past years?'),
        _card('Cost types', 'Actuals vs budget by Mipck-l1. Click a bar for its cost lines.',
              [_graph('cost_type', fig_type), *type_read], question='Q4 / Q5 · Which costs have budget?'),
        _card('Budget placement', 'Where spend and budget sit, at three levels of detail.', [
            html.Table([html.Thead(html.Tr([html.Th('')] + [html.Th(k, style={'textAlign': 'right', 'padding': '6px 10px',
                                                                              'fontSize': '11px', 'color': _MUTED})
                                                           for k in ('Actuals only', 'Budget only', 'Both')])),
                        html.Tbody(place_rows)], style={'width': '100%', 'fontSize': '12.5px', 'borderCollapse': 'collapse'}),
            place_read], question='Q4 · Is budget on different lines from spend?'),
        _card('Commitment repeat test', 'Does the same commitment amount repeat in back-to-back periods on the same '
              'account and cost line? If it did, summing would double count.', [
            html.Div(style={'display': 'flex', 'alignItems': 'baseline', 'gap': '10px'}, children=[
                html.Div(f'{rep:,}', style={'fontSize': '40px', 'fontWeight': '800', 'fontFamily': DISPLAY_FONT,
                                            'color': _OK if rep == 0 else _NEG}),
                html.Div(f"repeats in {p['commit_rows']:,} commitment rows", style={'color': _MUTED, 'fontSize': '13px'}),
            ]),
            _reading('No repeats: each row is the amount still open on that account and period, so summing gives the '
                     'current open commitment (Q3, confirmed).' if rep == 0 else
                     f'{rep} rows repeat the previous period\'s amount. Check those before trusting the commitment total.',
                     'ok' if rep == 0 else 'bad')], question='Q3 · Is it safe to sum commitments?'),
        _card('Commitment age', 'Open commitment by the financial year it is posted to. Click a year for the lines.', [
            _graph('commit_age', fig_age),
            _reading(f"{gbp(p['commit_total'])} open in total. {p['stale_count']:,} lines ({gbp(p['stale_value'])}) are "
                     f"more than {STALE_COMMITMENT_MONTHS} months old: probably POs never closed.",
                     'warn' if p['stale_count'] else 'ok'),
            _drill_button('commit_age', 'residual', _reading(
                f"{p['residual_count']:,} residual lines under £{RESIDUAL_COMMITMENT_MAX:.0f} "
                f"({gbp(p['residual_value'], 2)} in total). Click to see them.", 'info')),
        ], question='How old are open commitments?'),
        _card('History start', 'Projects already spending when the data starts.', [
            html.Div(style={'display': 'flex', 'alignItems': 'baseline', 'gap': '10px'}, children=[
                html.Div(f"{p['truncated_units']:,}", style={'fontSize': '40px', 'fontWeight': '800',
                                                            'fontFamily': DISPLAY_FONT, 'color': _WARN}),
                html.Div(f"of {p['units_total']:,} projects", style={'color': _MUTED, 'fontSize': '13px'}),
            ]),
            _drill_button('truncated', 'all', trunc_read)], question='Q6 · Is spend before April 2020 missing?'),
    ])
    summary = html.Summary(style={'cursor': 'pointer', 'listStyle': 'none', 'padding': '16px 20px',
                                  'display': 'flex', 'alignItems': 'center', 'gap': '12px'}, children=[
        DashIconify(icon='lucide:microscope', width=20, color='#334155'),
        html.Div([
            html.Div('Data Profile: how the source data behaves', style={'fontSize': '15px', 'fontWeight': '700',
                                                                          'color': '#1e293b'}),
            html.Div(f"Budget in {yb} of {yn} years · {rep} commitment repeats · {p['stale_count']} stale commitment "
                     f"lines · {p['truncated_units']} projects may pre-date the data. Expand for the evidence.",
                     style={'fontSize': '12px', 'color': _FAINT, 'marginTop': '2px'}),
        ]),
    ])
    return html.Details([summary, html.Div(panels, style={'padding': '0 20px 20px'})],
                        style={'background': 'white', 'border': f'1px solid {_BORDER}', 'borderRadius': '12px',
                               'boxShadow': '0 2px 8px rgba(15,23,42,0.04)', 'marginBottom': '22px'})


def _render_export() -> html.Div:
    sheets = [('README', 'definitions, filters, known gaps'), ('Project_Header', 'one row per project'),
              ('Project_Tasks', 'one row per cost line'), ('Opening_Position', 'per project and house'),
              ('Task_Position', 'per cost line and house'), ('Annual_History', 'per project, house and year'),
              ('Reconciliation', 'totals against the raw file')]
    return _card('SI extract', 'The workbook for the System Integrator, built with the filters currently selected at '
                 'the top of the page. Same content as scripts/generate_projects_export.py.', [
        html.Div(style={'display': 'flex', 'gap': '24px', 'flexWrap': 'wrap', 'alignItems': 'center'}, children=[
            html.Button([DashIconify(icon='lucide:download', width=16, color='white'), 'Download SI extract (.xlsx)'],
                        id='btn-prj-export', n_clicks=0, style={
                    'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'background': _HDR2_BG, 'color': 'white',
                    'border': 'none', 'borderRadius': '8px', 'padding': '11px 18px', 'fontWeight': '600',
                    'fontSize': '13px', 'cursor': 'pointer'}),
            dcc.Download(id='download-prj-extract'),
            html.Div(style={'display': 'flex', 'flexWrap': 'wrap', 'gap': '6px 18px', 'flex': '1'}, children=[
                html.Div([html.B(n, style={'color': '#334155'}), html.Span(f' · {d}', style={'color': _FAINT})],
                         style={'fontSize': '12px'}) for n, d in sheets]),
        ]),
        _reading('Project manager and start / end dates are not in either source file, so they are blank on '
                 'Project_Header and listed as a known gap (Q7).', 'warn'),
    ], question='What goes to the SI?')


def render_tab(dq_results, frames) -> html.Div:
    if 'project_lines' not in frames:
        return html.Div('No project data loaded. Place project_list.csv and project_financials.csv in '
                        'data/projects/ and restart.',
                        style={'padding': '48px', 'textAlign': 'center', 'color': _FAINT, 'fontSize': '14px'})
    view = scope_view(frames)
    cov = coverage(frames)
    return html.Div([
        _render_hero(frames, view, cov),
        _render_filters(),
        html.Div(id={'type': 'prj-body', 'index': 'scope'}, children=render_scope_body(frames, DEFAULT_FILTERS)),
        _section('Data Quality Checks', 'On the project list (Parliament) and on each house\'s positions and '
                 'commitments. Click a bar for the records.', 'lucide:shield-check'),
        render_dimension_scorecard(dq_results),
        render_dimension_grid(dq_results, key_prefix='prj:'),
        _section('Data Profile', 'Evidence for the open questions about the source data (Q3 to Q6)', 'lucide:microscope'),
        _render_profile(frames),
        _section('Export', 'For the System Integrator', 'lucide:file-spreadsheet'),
        _render_export(),
    ])


# ── Modal content ─────────────────────────────────────────────────────────────

def unit_flags(frames, unit) -> pd.DataFrame:
    """Every PRJ_* check that flags this project, with the number of rows flagged."""
    rows = []
    for (cid, _s, _o, dim, sev, desc, *_rest, table, _j, _l, fn) in get_project_checks():
        df = frames.get(table)
        if df is None or df.empty or 'unit' not in df.columns:
            continue
        sub = df[df['unit'] == unit]
        for house, g in sub.groupby('house'):
            pop = project_population(g, cid)
            if pop.empty:
                continue
            n = int(fn(pop).sum())
            if n:
                rows.append({'check_id': cid, 'house': house, 'severity': sev, 'dimension': dim,
                             'description': desc, 'rows': n})
    return pd.DataFrame(rows)


_SEV_HEX = {'Critical': '#c0392b', 'High': '#e67e22', 'Medium': '#d4a017', 'Low': '#3b82f6'}


def render_unit_modal(frames, unit, f: dict) -> html.Div:
    d = unit_detail(frames, unit, **filter_args(f))
    a, pos, hist = d['attrs'], d['positions'], d['history']

    def chip(label, value):
        return html.Div(style={'background': _PANEL, 'border': f'1px solid {_BORDER}', 'borderRadius': '8px',
                               'padding': '8px 12px'}, children=[
            html.Div(label, style={'fontSize': '9.5px', 'fontWeight': '800', 'color': _FAINT, 'letterSpacing': '0.08em',
                                   'textTransform': 'uppercase'}),
            html.Div(value or '—', style={'fontSize': '13px', 'fontWeight': '600', 'color': '#1e293b', 'marginTop': '2px'}),
        ])

    def position_card(title, rows, colour):
        s = rows[['spend_to_date', 'commitments', 'budget_to_date', 'remaining_budget']].sum()
        return html.Div(style={'flex': '1', 'minWidth': '220px', 'border': f'1px solid {_BORDER}',
                               'borderTop': f'3px solid {colour}', 'borderRadius': '10px', 'padding': '14px 16px'},
                        children=[html.Div(title, style={'fontSize': '11px', 'fontWeight': '800', 'color': colour,
                                                         'letterSpacing': '0.08em', 'marginBottom': '8px'})] + [
            html.Div(style={'display': 'flex', 'justifyContent': 'space-between', 'fontSize': '12.5px', 'padding': '3px 0'},
                     children=[html.Span(lbl, style={'color': _MUTED}),
                               html.Span(gbp(s[col], 2), style={'fontWeight': '700',
                                                                'color': _NEG if s[col] < 0 else _INK})])
            for col, lbl in [('spend_to_date', 'Spend to date'), ('commitments', 'Open commitments'),
                             ('budget_to_date', 'Budget to date'), ('remaining_budget', 'Remaining budget')]])

    cards = [position_card(h, pos[pos['house'] == h], HOUSE_HEX[h]) for h in HOUSES if (pos['house'] == h).any()]
    if len(cards) > 1:
        cards.append(position_card('TOTAL', pos, _INK))
    if not cards:
        cards = [html.Div('No financial activity for this project in the current view.',
                          style={'color': _FAINT, 'padding': '12px'})]

    fig = go.Figure()
    if not hist.empty:
        for h in HOUSES:
            hh = hist[hist['house'] == h]
            if not hh.empty:
                fig.add_trace(go.Bar(x=hh['fy_label'], y=hh['actuals'], name=f'{h} actuals', marker_color=HOUSE_HEX[h]))
        tot = hist.groupby(['fiscal_year', 'fy_label'])[['actuals', 'budget']].sum().reset_index()
        fig.add_trace(go.Scatter(x=tot['fy_label'], y=tot['actuals'].cumsum(), name='Spend to date',
                                 line=dict(color=_ACCENT, width=3), yaxis='y2'))
        fig.add_trace(go.Scatter(x=tot['fy_label'], y=tot['budget'].cumsum(), name='Budget to date',
                                 line=dict(color='#16a34a', width=2, dash='dot'), yaxis='y2'))
    _chart_layout(fig, 300, barmode='stack', yaxis=dict(tickprefix='£', title='In year'),
                  yaxis2=dict(overlaying='y', side='right', tickprefix='£', showgrid=False, title='To date'))

    flags = unit_flags(frames, unit)
    flag_children = [html.Div(style={'display': 'flex', 'gap': '8px', 'alignItems': 'center', 'padding': '6px 0',
                                     'borderBottom': '1px solid #f1f5f9'}, children=[
        html.Span(r.severity, style={'background': _SEV_HEX.get(r.severity, _FAINT), 'color': 'white', 'fontSize': '9.5px',
                                     'fontWeight': '800', 'padding': '2px 7px', 'borderRadius': '4px'}),
        html.Span(r.house, style={'fontSize': '10px', 'fontWeight': '700', 'color': HOUSE_HEX.get(r.house, '#4a3d6b')}),
        html.Span(r.description, style={'fontSize': '12.5px', 'color': '#334155', 'flex': '1'}),
        html.Span(f'{r.check_id} · {r.rows} row{"s" if r.rows != 1 else ""}', style={'fontSize': '11px', 'color': _FAINT}),
    ]) for r in flags.itertuples()] if not flags.empty else [
        html.Div('No data quality checks flag this project.', style={'fontSize': '12.5px', 'color': _OK})]

    tasks = d['tasks']
    task_tbl = records_table(tasks[['hais_code', 'hais_desc', 'house', 'spend_to_date', 'commitments', 'budget_to_date',
                                    'remaining_budget', 'first_period', 'last_period']] if not tasks.empty else tasks,
                             'unit-tasks', page_size=10, clickable_units=False)
    acct = d['by_account']
    acct_tbl = records_table(acct.sort_values('actuals', ascending=False) if not acct.empty else acct, 'unit-accounts',
                             page_size=10, clickable_units=False)
    idle = d['idle_codes']

    def block(title, children):
        return html.Div(style={'marginTop': '22px'}, children=[
            html.Div(title, style={'fontSize': '12px', 'fontWeight': '800', 'color': '#334155', 'letterSpacing': '0.06em',
                                   'textTransform': 'uppercase', 'marginBottom': '10px'}), *children])

    return html.Div(style={'padding': '20px 24px 28px'}, children=[
        html.Div(style={'display': 'flex', 'gap': '10px', 'flexWrap': 'wrap'}, children=[
            chip('Category', a.get('project_type')), chip('Portfolio', a.get('projgrp_desc')),
            chip('Cost centre', a.get('costc_desc') or a.get('costc')),
            chip('Directorate', a.get('directorate_desc') or a.get('directorate')),
            chip('Department', a.get('department_desc') or a.get('department')),
            chip('Cost lines listed', f"{len(d['codes'].drop_duplicates('hais_code')):,}"),
        ]),
        html.Div(f'Showing: {filter_summary(f)}', style={'fontSize': '11px', 'color': _FAINT, 'margin': '10px 0 0'}),
        block('Opening position', [html.Div(style={'display': 'flex', 'gap': '12px', 'flexWrap': 'wrap'}, children=cards)]),
        block('How it built up', [dcc.Graph(figure=fig, config=PLOTLY_HOVER_CONFIG)]),
        block('Data quality flags', flag_children),
        block('Cost lines (tasks)', [task_tbl] + ([html.Div(
            f"Listed with no activity: {', '.join(idle['hais_code'])}", style={'fontSize': '12px', 'color': _WARN,
                                                                           'marginTop': '8px'})] if not idle.empty else [])),
        block('By cost type and account', [acct_tbl]),
    ])


def drill_title(kind, key) -> str:
    if kind == 'coverage':
        return COVERAGE_LABELS.get(key, key)
    if kind == 'commit_age':
        return f'Residual commitments under £{RESIDUAL_COMMITMENT_MAX:.0f}' if key == 'residual' else f'Open commitments posted to {key}'
    if kind in ('all', 'truncated', 'idle'):
        return KIND_LABELS[kind]
    return f'{KIND_LABELS.get(kind, kind)}: {key}'


def drill_summary(df: pd.DataFrame) -> str:
    parts = [f'{len(df):,} rows']
    for c, lbl in [('spend_to_date', 'spend to date'), ('actuals', 'actuals'), ('actuals_total', 'actuals'),
                   ('commitments', 'commitments'), ('committed', 'committed'), ('committed_total', 'committed')]:
        if c in df.columns:
            parts.append(f'{lbl} {gbp(df[c].sum())}')
    return ' · '.join(parts)
