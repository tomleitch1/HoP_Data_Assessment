"""
Planning, Budgeting & Forecasting (PBF) tab.

Source: budgets_report.csv — pre-built Finance report covering HOC + HOL,
one row per (account × period × HAIS code × cost centre), with budget
versions (ORIG, CURR, CFSTSP) and GL actuals side by side.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html
from dash_iconify import DashIconify

from dashboard.core.theme import (
    CHART_LAYOUT,
    DISPLAY_FONT,
    HOUSE_HEX,
    PLOTLY_STATIC_CONFIG,
    UI,
)
from dashboard.shared.dimensions import render_dimension_grid, render_dimension_scorecard

# ── Design tokens ─────────────────────────────────────────────────────────────
_HDR     = '#0D3B52'
_HDR_MID = '#0F4A65'
_ACCENT  = '#C9832A'

_CURR    = '#1a7a4a'   # current budget — Parliament green
_ORIG    = '#3b82f6'   # original budget — blue
_FCST    = '#d4820a'   # live forecast   — amber
_ACTUAL  = '#4a3d6b'   # GL actuals      — purple
_BORDER  = '#dde8e4'

_HOUSES  = ['HOC', 'HOL']


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_gbp(v, dp=1):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return '—'
    v = float(v)
    neg = v < 0
    a = abs(v)
    if a >= 1_000_000:
        s = f'£{a / 1_000_000:.{dp}f}m'
    elif a >= 1_000:
        s = f'£{a / 1_000:.1f}k'
    else:
        s = f'£{a:,.0f}'
    return f'−{s}' if neg else s


def _fmt_pct(v, dp=1):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return '—'
    return f'{float(v):.{dp}f}%'


def _badge(text, bg='#1a3547', color='#e8f4f0'):
    return html.Span(text, style={
        'background': bg, 'color': color,
        'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.1em',
        'padding': '3px 9px', 'borderRadius': '4px',
        'textTransform': 'uppercase', 'display': 'inline-block',
    })


def _card(children, style=None):
    base = {
        'background': 'white', 'borderRadius': '12px',
        'border': f'1px solid {_BORDER}', 'overflow': 'hidden',
    }
    if style:
        base.update(style)
    return html.Div(style=base, children=children)


def _card_header(title, subtitle=None, color=None):
    return html.Div(style={
        'background': (color or _HDR) + '18',
        'borderBottom': f'1px solid {color or _HDR}28',
        'padding': '10px 16px', 'display': 'flex', 'alignItems': 'center',
        'justifyContent': 'space-between',
    }, children=[
        html.Div(title, style={'fontSize': '12px', 'fontWeight': '700', 'color': color or _HDR}),
        html.Div(subtitle, style={'fontSize': '10px', 'color': UI['text_secondary']}) if subtitle else None,
    ])


def _stat_row(label, value, color=None, bold=False, last=False):
    return html.Div(style={
        'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
        'padding': '5px 0',
        'borderBottom': 'none' if last else f'1px solid {_BORDER}',
    }, children=[
        html.Span(label, style={'fontSize': '12px', 'color': UI['text_secondary']}),
        html.Span(value, style={
            'fontSize': '12px', 'fontWeight': '700' if bold else '500',
            'color': color or UI['text_primary'],
        }),
    ])


def _progress_bar(pct, color, height=6):
    pct = max(0.0, min(100.0, float(pct) if pct else 0.0))
    return html.Div(style={
        'background': '#e8ecf0', 'borderRadius': '3px',
        'height': f'{height}px', 'overflow': 'hidden',
    }, children=[
        html.Div(style={
            'background': color, 'width': f'{pct:.1f}%',
            'height': '100%', 'borderRadius': '3px',
        })
    ])


def _section_header(title, badge=None, icon='lucide:bar-chart-2'):
    return html.Div(style={
        'borderTop': f'1px solid {_BORDER}', 'paddingTop': '20px',
        'marginBottom': '16px', 'display': 'flex', 'alignItems': 'center', 'gap': '10px',
    }, children=[
        DashIconify(icon=icon, width=15, color=_HDR),
        html.Div(title, style={'fontSize': '14px', 'fontWeight': '700', 'color': _HDR}),
        html.Span(badge, style={
            'fontSize': '11px', 'color': '#5a78a0',
            'background': '#e8f0f8', 'padding': '2px 8px', 'borderRadius': '4px',
        }) if badge else None,
    ])


# ═══════════════════════════════════════════════════════════════════════════════
# Metric computation
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_metrics(frames):
    df = frames.get('budgets_report')
    if df is None or df.empty:
        return {}

    out = {}
    for house in _HOUSES:
        h = df[df['house'] == house]
        if h.empty:
            out[house] = None
            continue

        def _s(col):
            return pd.to_numeric(h[col], errors='coerce').sum() if col in h.columns else 0.0

        curr  = _s('curr_budget')
        orig  = _s('orig_budget')
        actls = _s('gl_actuals')
        fcst  = _s('live_forecast')
        q1    = _s('q1_forecast')
        q2    = _s('q2_forecast')
        q3    = _s('q3_forecast')

        util_pct  = (actls / curr  * 100) if curr  else 0.0
        vir_amt   = curr - orig
        vir_pct   = (vir_amt / orig * 100) if orig  else 0.0
        remaining = curr - actls
        fcst_var  = fcst - curr

        out[house] = dict(
            curr_budget=curr, orig_budget=orig, gl_actuals=actls,
            live_forecast=fcst, q1_forecast=q1, q2_forecast=q2, q3_forecast=q3,
            util_pct=util_pct, vir_amt=vir_amt, vir_pct=vir_pct,
            remaining=remaining, fcst_var=fcst_var,
            lines=len(h),
            accounts=int(h['account'].dropna().nunique()) if 'account' in h.columns else 0,
            hais_cnt=int(h['haiscode'].dropna().nunique()) if 'haiscode' in h.columns else 0,
            periods=int(h['period'].dropna().nunique()) if 'period' in h.columns else 0,
        )
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# Hero
# ═══════════════════════════════════════════════════════════════════════════════

def _render_hero(metrics, df):
    total_curr  = sum(m['curr_budget']   for m in metrics.values() if m) or 0
    total_actls = sum(m['gl_actuals']    for m in metrics.values() if m) or 0
    total_fcst  = sum(m['live_forecast'] for m in metrics.values() if m) or 0
    total_util  = (total_actls / total_curr * 100) if total_curr else 0.0
    line_count  = len(df) if df is not None else 0

    def _kpi(label, value, sub=None, val_color='white'):
        return html.Div(style={
            'display': 'flex', 'flexDirection': 'column', 'gap': '2px', 'minWidth': '120px',
        }, children=[
            html.Div(value, style={
                'fontFamily': DISPLAY_FONT, 'fontWeight': '800',
                'fontSize': '22px', 'color': val_color, 'lineHeight': '1.1',
            }),
            html.Div(label, style={'fontSize': '11px', 'color': '#9ecfca', 'fontWeight': '500'}),
            html.Div(sub, style={'fontSize': '10px', 'color': '#6ba0a0', 'marginTop': '1px'}) if sub else None,
        ])

    def _house_pill(house, m):
        col = HOUSE_HEX[house]
        return html.Div(style={
            'background': col + '15', 'border': f'1px solid {col}35',
            'borderRadius': '8px', 'padding': '8px 14px',
            'display': 'flex', 'flexDirection': 'column', 'gap': '2px', 'minWidth': '100px',
        }, children=[
            html.Div(house, style={'fontSize': '9px', 'fontWeight': '800', 'color': col,
                                   'letterSpacing': '0.1em', 'textTransform': 'uppercase'}),
            html.Div(_fmt_pct(m['util_pct']), style={
                'fontFamily': DISPLAY_FONT, 'fontWeight': '800', 'fontSize': '17px', 'color': 'white',
            }),
            html.Div('utilised', style={'fontSize': '10px', 'color': 'rgba(255,255,255,0.5)'}),
        ])

    return html.Div(style={
        'background': f'linear-gradient(135deg, {_HDR} 0%, {_HDR_MID} 60%, #0c3d50 100%)',
        'borderRadius': '14px', 'padding': '28px 32px', 'marginBottom': '20px',
        'boxShadow': '0 4px 20px rgba(13,59,82,0.22)',
    }, children=[
        html.Div(style={
            'display': 'flex', 'alignItems': 'flex-start', 'gap': '12px', 'marginBottom': '24px',
        }, children=[
            DashIconify(icon='lucide:bar-chart-2', width=22, color=_ACCENT,
                        style={'marginTop': '3px', 'flexShrink': '0'}),
            html.Div(children=[
                html.Div('Planning, Budgeting & Forecasting', style={
                    'fontSize': '19px', 'fontWeight': '800', 'color': 'white', 'lineHeight': '1.2',
                }),
                html.Div(style={'display': 'flex', 'gap': '8px', 'marginTop': '7px', 'flexWrap': 'wrap'}, children=[
                    _badge('Seq 23', _ACCENT, 'white'),
                    _badge('GL Budgets & Forecasts', '#1a4f6a', '#9ecfca'),
                    _badge('FY 2025/26', '#1a4f6a', '#9ecfca'),
                    _badge(f'{line_count:,} lines', '#1a4f6a', '#9ecfca'),
                ]),
            ]),
        ]),
        html.Div(style={
            'display': 'flex', 'gap': '32px', 'flexWrap': 'wrap',
            'borderTop': '1px solid rgba(255,255,255,0.1)', 'paddingTop': '20px',
            'alignItems': 'flex-end',
        }, children=[
            _kpi('Total Current Budget', _fmt_gbp(total_curr), f'{line_count:,} budget lines'),
            _kpi('GL Actuals to Date', _fmt_gbp(total_actls), f'{_fmt_pct(total_util)} utilised'),
            _kpi('Live Forecast (CFSTSP)', _fmt_gbp(total_fcst),
                 f'{("+" if total_fcst >= total_curr else "")}{_fmt_gbp(total_fcst - total_curr)} vs budget',
                 _ACCENT),
            html.Div(style={'display': 'flex', 'gap': '10px', 'alignItems': 'flex-end'}, children=[
                _house_pill(h, m) for h, m in metrics.items() if m
            ]),
        ]),
    ])


# ═══════════════════════════════════════════════════════════════════════════════
# Per-house overview cards
# ═══════════════════════════════════════════════════════════════════════════════

def _render_house_card(house, m):
    col        = HOUSE_HEX[house]
    util       = m['util_pct']
    util_color = '#1a7a4a' if util <= 90 else ('#d4820a' if util <= 100 else '#c0392b')
    vir_color  = '#059669' if m['vir_amt'] >= 0 else '#c0392b'
    rem_color  = '#1a7a4a' if m['remaining'] >= 0 else '#c0392b'
    vir_sign   = '+' if m['vir_amt'] >= 0 else ''

    return _card(style={'flex': '1'}, children=[
        html.Div(style={
            'background': col, 'padding': '12px 16px',
            'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
        }, children=[
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px'}, children=[
                html.Div(house, style={
                    'fontSize': '13px', 'fontWeight': '800', 'color': 'white', 'letterSpacing': '0.05em',
                }),
                html.Div('Budget Overview', style={'fontSize': '12px', 'color': 'rgba(255,255,255,0.7)'}),
            ]),
            html.Div(
                f'{m["accounts"]} accounts · {m["hais_cnt"]} HAIS · {m["periods"]} periods',
                style={'fontSize': '10px', 'color': 'rgba(255,255,255,0.6)'},
            ),
        ]),
        html.Div(style={'padding': '16px'}, children=[
            # Utilisation bar
            html.Div(style={'marginBottom': '14px'}, children=[
                html.Div(style={
                    'display': 'flex', 'justifyContent': 'space-between', 'marginBottom': '5px',
                }, children=[
                    html.Span('Budget utilisation', style={'fontSize': '11px', 'color': UI['text_secondary']}),
                    html.Span(_fmt_pct(util), style={
                        'fontSize': '14px', 'fontWeight': '800', 'color': util_color,
                    }),
                ]),
                _progress_bar(util, util_color, height=8),
                html.Div(style={
                    'display': 'flex', 'justifyContent': 'space-between', 'marginTop': '4px',
                }, children=[
                    html.Span(_fmt_gbp(m['gl_actuals']) + ' actuals',
                              style={'fontSize': '10px', 'color': util_color}),
                    html.Span(_fmt_gbp(m['curr_budget']) + ' budget',
                              style={'fontSize': '10px', 'color': UI['text_secondary']}),
                ]),
            ]),
            _stat_row('Current Budget',            _fmt_gbp(m['curr_budget']),  _CURR,      True),
            _stat_row('Original Budget',           _fmt_gbp(m['orig_budget']),  _ORIG),
            _stat_row('Virements / Adjustments',
                      f'{vir_sign}{_fmt_gbp(m["vir_amt"])} ({_fmt_pct(abs(m["vir_pct"]))})',
                      vir_color),
            _stat_row('GL Actuals',                _fmt_gbp(m['gl_actuals']),   _ACTUAL),
            _stat_row('Remaining Budget',          _fmt_gbp(m['remaining']),    rem_color,  True),
            _stat_row('Live Forecast',             _fmt_gbp(m['live_forecast']), _FCST, last=True),
        ]),
    ])


# ═══════════════════════════════════════════════════════════════════════════════
# Budget version comparison (waterfall-style cards)
# ═══════════════════════════════════════════════════════════════════════════════

def _render_version_cards(metrics):
    items = []
    for house in _HOUSES:
        m = metrics.get(house)
        if not m:
            continue
        col = HOUSE_HEX[house]

        def _ver_row(label, val, color, code, bold=False, show_delta=False, base=None):
            delta_el = None
            if show_delta and base is not None and base:
                d = val - base
                dsign = '+' if d >= 0 else ''
                delta_el = html.Span(
                    f'{dsign}{_fmt_gbp(d)} ({_fmt_pct(d / base * 100)})',
                    style={'fontSize': '10px',
                           'color': '#059669' if d <= 0 else '#c0392b',
                           'fontWeight': '600'},
                )
            return html.Div(style={'padding': '6px 0'}, children=[
                html.Div(style={
                    'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
                    'marginBottom': '3px',
                }, children=[
                    html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '6px'}, children=[
                        html.Span(label, style={
                            'fontSize': '11px', 'color': UI['text_secondary'],
                            'fontWeight': '700' if bold else '400',
                        }),
                        delta_el,
                    ]),
                    html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '6px'}, children=[
                        html.Span(code, style={
                            'fontSize': '9px', 'background': color + '18', 'color': color,
                            'padding': '1px 5px', 'borderRadius': '3px', 'fontWeight': '700',
                        }),
                        html.Span(_fmt_gbp(val), style={
                            'fontSize': '13px' if bold else '12px',
                            'fontWeight': '800' if bold else '600',
                            'color': color, 'fontFamily': DISPLAY_FONT,
                        }),
                    ]),
                ]),
                html.Div(style={'background': '#f0f4f0', 'borderRadius': '3px', 'height': '3px', 'overflow': 'hidden'}, children=[
                    html.Div(style={'background': color, 'width': '100%', 'height': '100%'}),
                ]),
            ])

        def _connector(text, color):
            return html.Div(style={
                'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'padding': '3px 0 3px 12px',
            }, children=[
                html.Div('│', style={'color': '#d0d0d0', 'fontSize': '13px', 'lineHeight': '1'}),
                html.Span(text, style={'fontSize': '11px', 'color': color, 'fontWeight': '600'}),
            ])

        vir_sign = '▲' if m['vir_amt'] >= 0 else '▼'
        fv_sign  = '▲' if m['fcst_var'] >= 0 else '▼'
        vir_color = '#059669' if m['vir_amt'] >= 0 else '#c0392b'
        fv_color  = '#c0392b' if m['fcst_var'] > 0 else '#059669'

        items.append(_card(style={'flex': '1'}, children=[
            html.Div(style={
                'background': col + '18', 'borderBottom': f'1px solid {col}28',
                'padding': '10px 14px',
            }, children=[
                html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px'}, children=[
                    html.Div(house, style={'fontSize': '12px', 'fontWeight': '800', 'color': col}),
                    html.Div('Budget version progression', style={
                        'fontSize': '11px', 'color': UI['text_secondary'],
                    }),
                ]),
            ]),
            html.Div(style={'padding': '14px'}, children=[
                _ver_row('Original Budget', m['orig_budget'], _ORIG, '2026ORIG'),
                _connector(f'{vir_sign} Virements: {_fmt_gbp(m["vir_amt"])} ({_fmt_pct(abs(m["vir_pct"]))})', vir_color),
                _ver_row('Current Budget', m['curr_budget'], _CURR, '2026CURR', bold=True),
                _connector(f'{fv_sign} Forecast movement: {_fmt_gbp(m["fcst_var"])} ({_fmt_pct(abs(m["fcst_var"] / m["curr_budget"] * 100) if m["curr_budget"] else 0)})', fv_color),
                _ver_row('Live Forecast', m['live_forecast'], _FCST, '2026CFSTSP'),
            ]),
        ]))
    return html.Div(style={'display': 'flex', 'gap': '16px', 'flexWrap': 'wrap'}, children=items)


# ═══════════════════════════════════════════════════════════════════════════════
# Period profile chart
# ═══════════════════════════════════════════════════════════════════════════════

def _render_period_chart(df):
    if df is None or df.empty or 'period' not in df.columns:
        return None

    agg = (
        df.groupby(['house', 'period'])[['curr_budget', 'gl_actuals', 'live_forecast']]
        .sum().reset_index().sort_values(['house', 'period'])
    )
    if agg.empty:
        return None
    agg['period_label'] = 'P' + agg['period'].astype(int).astype(str).str.zfill(2)

    fig = go.Figure()
    specs = [
        ('curr_budget',   'Current Budget', _CURR,   0.85),
        ('gl_actuals',    'GL Actuals',      _ACTUAL, 0.85),
        ('live_forecast', 'Live Forecast',   _FCST,   0.55),
    ]
    for house in _HOUSES:
        h = agg[agg['house'] == house].sort_values('period')
        if h.empty:
            continue
        hcol = HOUSE_HEX[house]
        for col_key, col_name, bar_color, op in specs:
            use_color = hcol if col_name == 'Current Budget' else bar_color
            fig.add_trace(go.Bar(
                x=h['period_label'], y=h[col_key],
                name=f'{house} · {col_name}',
                marker_color=use_color, opacity=op,
                legendgroup=col_name, showlegend=True,
                hovertemplate=f'<b>{house} · {col_name}</b><br>%{{x}}: £%{{y:,.0f}}<extra></extra>',
            ))
    fig.update_layout(
        **CHART_LAYOUT, barmode='group', height=320,
        margin=dict(l=0, r=0, t=6, b=36),
        legend=dict(orientation='h', yanchor='bottom', y=1.01, xanchor='left', x=0,
                    bgcolor='rgba(0,0,0,0)', font=dict(size=10)),
        xaxis=dict(title='', tickfont=dict(size=11)),
        yaxis=dict(title='£', tickprefix='£', tickformat=',.0f', tickfont=dict(size=11)),
    )
    return dcc.Graph(figure=fig, config=PLOTLY_STATIC_CONFIG, style={'width': '100%'})


# ═══════════════════════════════════════════════════════════════════════════════
# Version summary bar (HOC vs HOL)
# ═══════════════════════════════════════════════════════════════════════════════

def _render_version_bar(metrics):
    rows = []
    labels = ['Original Budget', 'Current Budget', 'Live Forecast', 'GL Actuals']
    keys   = ['orig_budget',     'curr_budget',    'live_forecast', 'gl_actuals']
    colors = [_ORIG, _CURR, _FCST, _ACTUAL]
    for house in _HOUSES:
        m = metrics.get(house)
        if not m:
            continue
        for lbl, k in zip(labels, keys):
            rows.append({'House': house, 'Version': lbl, 'Amount': m[k]})
    if not rows:
        return None
    df_plot = pd.DataFrame(rows)
    fig = go.Figure()
    for lbl, color in zip(labels, colors):
        sub = df_plot[df_plot['Version'] == lbl]
        fig.add_trace(go.Bar(
            x=sub['House'], y=sub['Amount'], name=lbl,
            marker_color=color, opacity=0.88,
            hovertemplate='<b>%{x}</b><br>' + lbl + ': £%{y:,.0f}<extra></extra>',
        ))
    fig.update_layout(
        **CHART_LAYOUT, barmode='group', height=280,
        margin=dict(l=0, r=0, t=6, b=24),
        legend=dict(orientation='h', yanchor='bottom', y=1.01, xanchor='left', x=0,
                    bgcolor='rgba(0,0,0,0)', font=dict(size=10)),
        xaxis=dict(tickfont=dict(size=13, color='#2a1f3d')),
        yaxis=dict(title='£', tickprefix='£', tickformat=',.0f', tickfont=dict(size=11)),
    )
    return dcc.Graph(figure=fig, config=PLOTLY_STATIC_CONFIG, style={'width': '100%'})


# ═══════════════════════════════════════════════════════════════════════════════
# MIPCK category chart
# ═══════════════════════════════════════════════════════════════════════════════

def _render_mipck_chart(df):
    if df is None or df.empty:
        return None
    label_col = 'mipck_l1_desc' if 'mipck_l1_desc' in df.columns else 'mipck_l1'
    if label_col not in df.columns:
        return None

    agg = (
        df.groupby([label_col, 'house'])['curr_budget']
        .sum().reset_index()
        .rename(columns={label_col: 'cat', 'curr_budget': 'budget'})
    )
    totals = agg.groupby('cat')['budget'].sum().sort_values(ascending=True).tail(15)
    if totals.empty:
        return None
    agg_top = agg[agg['cat'].isin(totals.index)]

    fig = go.Figure()
    for house in _HOUSES:
        h = agg_top[agg_top['house'] == house].set_index('cat')['budget']
        y_vals = list(totals.index)
        fig.add_trace(go.Bar(
            y=y_vals, x=[h.get(y, 0) for y in y_vals],
            name=house, orientation='h',
            marker_color=HOUSE_HEX[house], opacity=0.85,
            hovertemplate='<b>%{y}</b><br>' + house + ': £%{x:,.0f}<extra></extra>',
        ))
    fig.update_layout(
        **CHART_LAYOUT, barmode='stack',
        height=max(300, len(totals) * 28 + 60),
        margin=dict(l=0, r=0, t=6, b=24),
        legend=dict(orientation='h', yanchor='bottom', y=1.01, xanchor='left', x=0,
                    bgcolor='rgba(0,0,0,0)', font=dict(size=10)),
        xaxis=dict(title='Current Budget (£)', tickprefix='£', tickformat=',.0f', tickfont=dict(size=11)),
        yaxis=dict(tickfont=dict(size=11), automargin=True),
    )
    return dcc.Graph(figure=fig, config=PLOTLY_STATIC_CONFIG, style={'width': '100%'})


# ═══════════════════════════════════════════════════════════════════════════════
# Top HAIS codes chart
# ═══════════════════════════════════════════════════════════════════════════════

def _render_hais_chart(df):
    if df is None or df.empty or 'haiscode' not in df.columns:
        return None
    label_col = 'haiscode_desc' if 'haiscode_desc' in df.columns else 'haiscode'

    agg = (
        df.dropna(subset=['haiscode'])
        .groupby([label_col, 'house'])['curr_budget']
        .sum().reset_index()
        .rename(columns={label_col: 'hais', 'curr_budget': 'budget'})
    )
    totals = agg.groupby('hais')['budget'].sum().nlargest(10).sort_values(ascending=True)
    if totals.empty:
        return None
    agg_top = agg[agg['hais'].isin(totals.index)]

    fig = go.Figure()
    for house in _HOUSES:
        h = agg_top[agg_top['house'] == house].set_index('hais')['budget']
        y_vals = list(totals.index)
        fig.add_trace(go.Bar(
            y=y_vals, x=[h.get(y, 0) for y in y_vals],
            name=house, orientation='h',
            marker_color=HOUSE_HEX[house], opacity=0.85,
            hovertemplate='<b>%{y}</b><br>' + house + ': £%{x:,.0f}<extra></extra>',
        ))
    fig.update_layout(
        **CHART_LAYOUT, barmode='stack', height=360,
        margin=dict(l=0, r=0, t=6, b=24),
        legend=dict(orientation='h', yanchor='bottom', y=1.01, xanchor='left', x=0,
                    bgcolor='rgba(0,0,0,0)', font=dict(size=10)),
        xaxis=dict(title='Current Budget (£)', tickprefix='£', tickformat=',.0f', tickfont=dict(size=11)),
        yaxis=dict(tickfont=dict(size=10), automargin=True),
    )
    return dcc.Graph(figure=fig, config=PLOTLY_STATIC_CONFIG, style={'width': '100%'})


# ═══════════════════════════════════════════════════════════════════════════════
# Forecast recast progression
# ═══════════════════════════════════════════════════════════════════════════════

def _render_forecast_recasts(metrics):
    items = []
    for house in _HOUSES:
        m = metrics.get(house)
        if not m:
            continue
        col  = HOUSE_HEX[house]
        curr = m['curr_budget']
        recasts = [
            ('Q1 Forecast', m['q1_forecast'],   '#3b82f6'),
            ('Q2 Forecast', m['q2_forecast'],   '#0891b2'),
            ('Q3 Forecast', m['q3_forecast'],   '#059669'),
            ('Live (CFSTSP)', m['live_forecast'], _FCST),
        ]
        rows = []
        for lbl, val, c in recasts:
            d = val - curr
            dsign = '+' if d >= 0 else ''
            dpct  = (d / curr * 100) if curr else 0.0
            rows.append(html.Div(style={
                'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
                'padding': '5px 0', 'borderBottom': f'1px solid {_BORDER}',
            }, children=[
                html.Span(lbl, style={'fontSize': '11px', 'color': UI['text_secondary']}),
                html.Div(style={'display': 'flex', 'gap': '8px', 'alignItems': 'center'}, children=[
                    html.Span(
                        f'{dsign}{_fmt_gbp(d)} ({_fmt_pct(abs(dpct))})',
                        style={'fontSize': '10px',
                               'color': '#059669' if d <= 0 else '#c0392b',
                               'fontWeight': '600'},
                    ),
                    html.Span(_fmt_gbp(val), style={
                        'fontSize': '12px', 'fontWeight': '700', 'color': c, 'fontFamily': DISPLAY_FONT,
                    }),
                ]),
            ]))

        items.append(_card(style={'flex': '1'}, children=[
            html.Div(style={
                'background': col + '18', 'borderBottom': f'1px solid {col}28', 'padding': '10px 14px',
            }, children=[
                html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px'}, children=[
                    html.Div(house, style={'fontSize': '12px', 'fontWeight': '800', 'color': col}),
                    html.Div('Forecast recast progression vs current budget', style={
                        'fontSize': '11px', 'color': UI['text_secondary'],
                    }),
                ]),
            ]),
            html.Div(style={'padding': '12px 14px'}, children=[
                html.Div(style={
                    'display': 'flex', 'justifyContent': 'space-between',
                    'padding': '6px 0', 'borderBottom': f'1px solid {_BORDER}', 'marginBottom': '6px',
                }, children=[
                    html.Span('Current Budget (2026CURR)', style={'fontSize': '11px', 'fontWeight': '700', 'color': _CURR}),
                    html.Span(_fmt_gbp(curr), style={
                        'fontSize': '13px', 'fontWeight': '800', 'color': _CURR, 'fontFamily': DISPLAY_FONT,
                    }),
                ]),
                *rows,
            ]),
        ]))
    return html.Div(style={'display': 'flex', 'gap': '16px', 'flexWrap': 'wrap'}, children=items)


# ═══════════════════════════════════════════════════════════════════════════════
# Chart wrapper card
# ═══════════════════════════════════════════════════════════════════════════════

def _chart_card(title, chart, flex='1', min_width='300px'):
    return html.Div(style={
        'flex': flex, 'minWidth': min_width,
        'background': 'white', 'borderRadius': '12px',
        'border': f'1px solid {_BORDER}', 'padding': '16px',
    }, children=[
        html.Div(title, style={
            'fontSize': '12px', 'fontWeight': '700', 'color': _HDR, 'marginBottom': '12px',
        }),
        chart if chart is not None else html.Div(
            'No data available', style={'fontSize': '12px', 'color': UI['text_secondary']},
        ),
    ])


# ═══════════════════════════════════════════════════════════════════════════════
# Main render
# ═══════════════════════════════════════════════════════════════════════════════

def render_tab(dq_results, frames):
    df      = frames.get('budgets_report')
    metrics = _compute_metrics(frames)

    if df is None or df.empty:
        return html.Div(style={'padding': '48px 0', 'textAlign': 'center', 'color': UI['text_secondary']}, children=[
            DashIconify(icon='lucide:bar-chart-2', width=40, color='#c0c0d8'),
            html.Div('No budget data loaded.', style={'marginTop': '12px', 'fontSize': '14px'}),
            html.Div('Place budgets_report.csv in data/budgets/ and restart the dashboard.',
                     style={'fontSize': '12px', 'marginTop': '4px'}),
        ])

    period_chart  = _render_period_chart(df)
    version_chart = _render_version_bar(metrics)
    mipck_chart   = _render_mipck_chart(df)
    hais_chart    = _render_hais_chart(df)

    return html.Div(children=[

        # ── Hero ──────────────────────────────────────────────────────────────
        _render_hero(metrics, df),

        # ── HOC / HOL overview cards ──────────────────────────────────────────
        html.Div(style={'display': 'flex', 'gap': '16px', 'flexWrap': 'wrap', 'marginBottom': '20px'}, children=[
            _render_house_card(h, m) for h, m in metrics.items() if m
        ]),

        # ── Period profile + version summary ──────────────────────────────────
        html.Div(style={'marginBottom': '20px'}, children=[
            _section_header('Budget vs Actuals by Period', 'Current budget · GL actuals · Live forecast'),
            html.Div(style={'display': 'flex', 'gap': '20px', 'flexWrap': 'wrap'}, children=[
                _chart_card('Period-by-Period Profile', period_chart, flex='2', min_width='320px'),
                _chart_card('Budget Version Summary (HOC vs HOL)', version_chart, flex='1', min_width='280px'),
            ]),
        ]),

        # ── Budget version waterfall cards ────────────────────────────────────
        html.Div(style={'marginBottom': '20px'}, children=[
            _section_header('Budget Version Progression', 'ORIG → CURR → FORECAST', 'lucide:arrow-right'),
            _render_version_cards(metrics),
        ]),

        # ── MIPCK + HAIS charts ───────────────────────────────────────────────
        html.Div(style={'marginBottom': '20px'}, children=[
            _section_header('Spend Distribution', 'MIPCK L1 categories · Top HAIS codes', 'lucide:layers'),
            html.Div(style={'display': 'flex', 'gap': '20px', 'flexWrap': 'wrap'}, children=[
                _chart_card('Current Budget by MIPCK L1 Category', mipck_chart, flex='1', min_width='300px'),
                _chart_card('Top 10 HAIS Codes by Current Budget', hais_chart, flex='1', min_width='300px'),
            ]),
        ]),

        # ── Forecast recast progression ───────────────────────────────────────
        html.Div(style={'marginBottom': '20px'}, children=[
            _section_header('Forecast Recast Progression', 'Q1 → Q2 → Q3 → Live (CFSTSP)', 'lucide:trending-up'),
            _render_forecast_recasts(metrics),
        ]),

        # ── DQ section ────────────────────────────────────────────────────────
        html.Div(children=[
            _section_header('Data Quality Checks', icon='lucide:shield-check'),
            render_dimension_scorecard(dq_results),
            html.Div(style={'height': '16px'}),
            render_dimension_grid(dq_results),
        ]),

    ])
