import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc

from hr_dashboard.shared.dimensions import render_dimension_scorecard, render_dimension_grid
from hr_dashboard.core.theme import UI, DISPLAY_FONT
from hr_dashboard.shared.ui import fmt_gbp

_ACCENT = '#CC092F'
_BAR_BG = '#f4e6e8'

_SECTION_HEADER = {
    'borderTop': '1px solid #e3dcd6',
    'margin': '8px 0 20px',
    'paddingTop': '20px',
    'display': 'flex',
    'alignItems': 'center',
    'gap': '12px',
}
_SECTION_TITLE = {'fontSize': '15px', 'fontWeight': '700', 'color': '#1a1a1a'}
_SECTION_BADGE = {
    'fontSize': '11px', 'color': '#9a7a7e',
    'background': '#f4e6e8', 'padding': '2px 8px', 'borderRadius': '4px',
}

_PALETTE = ['#CC092F', '#e6a817', '#1a1a1a', '#7c5cbf', '#0891b2', '#5c5450']


def _badge(text, bg=_BAR_BG, color=_ACCENT):
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


def _bar_row(label, color, count, total, suffix=''):
    pct = (count / total * 100) if total > 0 else 0
    return html.Div(style={
        'display': 'flex', 'alignItems': 'center', 'gap': '10px', 'padding': '4px 0',
    }, children=[
        html.Span(label, style={
            'fontSize': '11px', 'color': UI['text_secondary'], 'minWidth': '160px',
        }),
        html.Div(style={
            'flex': '1', 'height': '8px', 'background': _BAR_BG,
            'borderRadius': '4px', 'overflow': 'hidden',
        }, children=[
            html.Div(style={
                'height': '100%', 'width': f'{min(pct, 100):.1f}%',
                'background': color, 'borderRadius': '4px',
                'minWidth': '3px' if count > 0 else '0',
            })
        ]),
        html.Span(f'{count:,}{suffix}', style={
            'fontSize': '12px', 'fontWeight': '700',
            'minWidth': '56px', 'textAlign': 'right', 'color': UI['text_primary'],
        }),
        html.Span(f'{pct:.0f}%', style={
            'fontSize': '10px', 'color': UI['text_secondary'], 'minWidth': '32px',
        }),
    ])


def _stat_tile(value, label, color=None):
    return html.Div(style={
        'flex': '1', 'padding': '14px 18px',
        'background': (color or _ACCENT) + '0d', 'borderRadius': '10px',
        'border': f'1px solid {(color or _ACCENT)}30',
    }, children=[
        html.Div(f'{value}', style={
            'fontSize': '30px', 'fontWeight': '900', 'lineHeight': '1',
            'color': color or _ACCENT, 'fontFamily': DISPLAY_FONT,
        }),
        html.Div(label, style={
            'fontSize': '11px', 'color': UI['text_secondary'], 'marginTop': '6px',
        }),
    ])


def _card(children):
    return html.Div(style={
        'borderRadius': '10px', 'overflow': 'hidden',
        'border': f'1px solid {UI["border"]}',
        'boxShadow': '0 2px 12px rgba(26,26,26,0.08)',
        'background': '#ffffff', 'padding': '24px 28px',
    }, children=children)


def _card_header(name, source):
    return html.Div(style={'marginBottom': '16px'}, children=[
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'marginBottom': '6px'}, children=[
            _badge('Migration Object'),
        ]),
        html.Div(name, style={'fontSize': '15px', 'fontWeight': '700', 'color': UI['text_primary']}),
        html.Span(source, style={
            'fontSize': '11px', 'color': '#9a7a7e',
            'fontFamily': "'Courier New', monospace",
        }),
    ])


def _compute_metrics(frames):
    df = frames.get('employee_master')
    if df is None or df.empty:
        return {}

    total = len(df)
    active = df[df['employment_status'] == 'Active']
    leavers = df[df['employment_status'] == 'Leaver']

    bu_counts = active['business_unit'].value_counts().to_dict()
    contract_counts = active['contract_type'].value_counts().to_dict()
    basis_counts = active['employment_basis'].value_counts().to_dict()
    union_counts = active['union_member'].value_counts().to_dict()

    now = pd.Timestamp.now()
    ages = (now - active['dob']).dt.days / 365.25
    ages = ages[(ages >= 0) & (ages <= 100)]

    tenure_years = (now - active['start_date']).dt.days / 365.25
    tenure_buckets = pd.cut(
        tenure_years, bins=[-0.01, 1, 3, 5, 10, 100],
        labels=['<1 yr', '1–3 yrs', '3–5 yrs', '5–10 yrs', '10+ yrs']
    ).value_counts().reindex(['<1 yr', '1–3 yrs', '3–5 yrs', '5–10 yrs', '10+ yrs']).fillna(0).astype(int)

    return {
        'total': total,
        'active': len(active),
        'leavers': len(leavers),
        'bu_counts': bu_counts,
        'contract_counts': contract_counts,
        'basis_counts': basis_counts,
        'union_counts': union_counts,
        'ages': ages,
        'tenure_buckets': tenure_buckets,
    }


def _render_intro(m):
    if not m:
        return html.Div()

    headline = _card([
        _card_header('Employee Master — Headcount Overview', 'employee_master.csv'),
        html.Div(style={'display': 'flex', 'gap': '14px', 'marginBottom': '20px'}, children=[
            _stat_tile(f"{m['total']:,}", 'Total employee records'),
            _stat_tile(f"{m['active']:,}", 'Active', color='#1a7a4a'),
            _stat_tile(f"{m['leavers']:,}", 'Leavers (last ~18 months)', color='#94a3b8'),
        ]),
        html.Div(style={'display': 'flex', 'gap': '32px'}, children=[
            html.Div(style={'flex': '1'}, children=[
                _section_label('Business unit'),
                html.Div([
                    _bar_row(bu, _PALETTE[i % len(_PALETTE)], cnt, m['active'])
                    for i, (bu, cnt) in enumerate(sorted(m['bu_counts'].items(), key=lambda x: -x[1]))
                ]),
            ]),
            html.Div(style={'flex': '1'}, children=[
                _section_label('Contract type'),
                html.Div([
                    _bar_row(ct, _PALETTE[i % len(_PALETTE)], cnt, m['active'])
                    for i, (ct, cnt) in enumerate(sorted(m['contract_counts'].items(), key=lambda x: -x[1]))
                ]),
            ]),
        ]),
    ])

    # Age histogram
    age_fig = go.Figure(go.Histogram(
        x=m['ages'], nbinsx=18, marker_color=_ACCENT, opacity=0.85,
        hovertemplate='Age %{x}<br>%{y} employees<extra></extra>',
    ))
    age_fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        height=200, margin=dict(t=10, b=30, l=10, r=10), showlegend=False,
        font=dict(family='Inter, sans-serif', color='#5c5450', size=10),
        xaxis=dict(title='Age', showgrid=False),
        yaxis=dict(title='Employees', showgrid=True, gridcolor='#F1F5F9'),
    )

    # Tenure bar
    tenure_fig = go.Figure(go.Bar(
        x=list(m['tenure_buckets'].index), y=list(m['tenure_buckets'].values),
        marker_color=_ACCENT, opacity=0.85,
        hovertemplate='%{x}<br>%{y} employees<extra></extra>',
    ))
    tenure_fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        height=200, margin=dict(t=10, b=30, l=10, r=10), showlegend=False,
        font=dict(family='Inter, sans-serif', color='#5c5450', size=10),
        xaxis=dict(showgrid=False),
        yaxis=dict(title='Employees', showgrid=True, gridcolor='#F1F5F9'),
    )

    demographics = _card([
        _card_header('Workforce Composition', 'employee_master.csv'),
        html.Div(style={'display': 'flex', 'gap': '32px', 'marginBottom': '20px'}, children=[
            html.Div(style={'flex': '1'}, children=[
                _section_label('Age distribution (active employees)'),
                dcc.Graph(figure=age_fig, config={'displayModeBar': False}),
            ]),
            html.Div(style={'flex': '1'}, children=[
                _section_label('Length of service'),
                dcc.Graph(figure=tenure_fig, config={'displayModeBar': False}),
            ]),
        ]),
        html.Div(style={'display': 'flex', 'gap': '32px'}, children=[
            html.Div(style={'flex': '1'}, children=[
                _section_label('Employment basis'),
                html.Div([
                    _bar_row(b, _PALETTE[i % len(_PALETTE)], cnt, m['active'])
                    for i, (b, cnt) in enumerate(sorted(m['basis_counts'].items(), key=lambda x: -x[1]))
                ]),
            ]),
            html.Div(style={'flex': '1'}, children=[
                _section_label('Union membership'),
                html.Div([
                    _bar_row(u, _PALETTE[i % len(_PALETTE)], cnt, m['active'])
                    for i, (u, cnt) in enumerate(sorted(m['union_counts'].items(), key=lambda x: -x[1]))
                ]),
            ]),
        ]),
    ])

    return html.Div(style={'marginBottom': '28px'}, children=[
        html.Div(style={
            'display': 'flex', 'alignItems': 'baseline', 'gap': '10px', 'marginBottom': '14px',
        }, children=[
            html.Div('Employee Master', style={
                'fontSize': '13px', 'fontWeight': '800', 'color': UI['text_primary'],
                'textTransform': 'uppercase', 'letterSpacing': '0.01em',
            }),
            html.Div('Volumetrics, not a DQ check', style=_SECTION_BADGE),
        ]),
        html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '16px'}, children=[
            headline,
            demographics,
        ]),
    ])


def render_tab(dq_results, frames):
    m = _compute_metrics(frames)
    return html.Div([
        _render_intro(m),
        render_dimension_scorecard(dq_results),
        html.Div(style=_SECTION_HEADER, children=[
            html.Span('Data Quality Checks', style=_SECTION_TITLE),
        ]),
        render_dimension_grid(dq_results, key_prefix='emp-'),
    ])
