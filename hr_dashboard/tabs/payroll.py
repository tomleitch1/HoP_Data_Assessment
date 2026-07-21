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

_COMPONENT_COLOR = {'Basic pay': '#CC092F', 'Overtime': '#e6a817', 'Shift allowance': '#7c5cbf', 'Bonus': '#0891b2'}
_DEDUCTION_COLOR = {'Tax': '#1a1a1a', 'National Insurance': '#5c5450', 'Pension': '#CC092F', 'Other': '#9a7a7e'}
_STATUS_COLOR = {'Processed': '#1a7a4a', 'Pending': '#d4820a'}


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


def _bar_row(label, color, count, total, is_currency=False):
    pct = (count / total * 100) if total > 0 else 0
    display_val = fmt_gbp(count) if is_currency else f'{count:,}'
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
        html.Span(display_val, style={
            'fontSize': '12px', 'fontWeight': '700',
            'minWidth': '64px', 'textAlign': 'right', 'color': UI['text_primary'],
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
            'fontSize': '28px', 'fontWeight': '900', 'lineHeight': '1',
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
    df = frames.get('payroll_transactions')
    if df is None or df.empty:
        return {}

    total = len(df)
    employees_paid = df['employee_id'].nunique()
    total_gross = df['gross_pay'].sum()
    total_net = df['net_pay'].sum()

    components = {
        'Basic pay': df['basic_pay'].sum(),
        'Overtime': df['overtime_pay'].sum(),
        'Shift allowance': df['shift_allowance'].sum(),
        'Bonus': df['bonus'].sum(),
    }
    deductions = {
        'Tax': df['tax_deducted'].sum(),
        'National Insurance': df['ni_deducted'].sum(),
        'Pension': df['pension_deducted'].sum(),
        'Other': df['other_deductions'].sum(),
    }
    status_counts = df['status'].value_counts().to_dict()

    weekly = df.groupby('pay_period', as_index=False).agg(
        gross=('gross_pay', 'sum'), net=('net_pay', 'sum')
    )
    # pay_period is "YYYY-Www" — sortable as a plain string
    weekly = weekly.sort_values('pay_period')

    return {
        'total': total,
        'employees_paid': employees_paid,
        'total_gross': total_gross,
        'total_net': total_net,
        'components': components,
        'deductions': deductions,
        'status_counts': status_counts,
        'weekly': weekly,
    }


def _render_intro(m):
    if not m:
        return html.Div()

    total_components = sum(m['components'].values()) or 1
    total_deductions = sum(m['deductions'].values()) or 1
    total_status = sum(m['status_counts'].values()) or 1

    headline = _card([
        _card_header('Payroll Transactions — Cost Overview (12 weekly pay runs)', 'payroll_transactions.csv'),
        html.Div(style={'display': 'flex', 'gap': '14px', 'marginBottom': '20px'}, children=[
            _stat_tile(f"{m['total']:,}", 'Payroll transactions'),
            _stat_tile(f"{m['employees_paid']:,}", 'Employees paid'),
            _stat_tile(fmt_gbp(m['total_gross']), 'Total gross paid', color='#1a1a1a'),
            _stat_tile(fmt_gbp(m['total_net']), 'Total net paid', color='#1a7a4a'),
        ]),
        html.Div(style={'display': 'flex', 'gap': '32px'}, children=[
            html.Div(style={'flex': '1'}, children=[
                _section_label('Pay component breakdown (% of gross)'),
                html.Div([
                    _bar_row(k, _COMPONENT_COLOR.get(k, _ACCENT), v, total_components, is_currency=True)
                    for k, v in sorted(m['components'].items(), key=lambda x: -x[1])
                ]),
            ]),
            html.Div(style={'flex': '1'}, children=[
                _section_label('Deduction breakdown (% of total deducted)'),
                html.Div([
                    _bar_row(k, _DEDUCTION_COLOR.get(k, _ACCENT), v, total_deductions, is_currency=True)
                    for k, v in sorted(m['deductions'].items(), key=lambda x: -x[1])
                ]),
            ]),
        ]),
    ])

    weekly = m['weekly']
    trend_fig = go.Figure()
    trend_fig.add_trace(go.Scatter(
        x=weekly['pay_period'], y=weekly['gross'], name='Gross', mode='lines+markers',
        line=dict(color='#1a1a1a', width=2), marker=dict(size=5),
        hovertemplate='%{x}<br>Gross: £%{y:,.0f}<extra></extra>',
    ))
    trend_fig.add_trace(go.Scatter(
        x=weekly['pay_period'], y=weekly['net'], name='Net', mode='lines+markers',
        line=dict(color=_ACCENT, width=2), marker=dict(size=5),
        hovertemplate='%{x}<br>Net: £%{y:,.0f}<extra></extra>',
    ))
    trend_fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        height=220, margin=dict(t=10, b=30, l=10, r=10),
        font=dict(family='Inter, sans-serif', color='#5c5450', size=10),
        xaxis=dict(title='Pay period', showgrid=False),
        yaxis=dict(title='£', showgrid=True, gridcolor='#F1F5F9'),
        legend=dict(orientation='h', y=1.15, x=0),
    )

    status_fig = go.Figure()
    for status, count in sorted(m['status_counts'].items(), key=lambda x: -x[1]):
        status_fig.add_trace(go.Bar(
            name=status, y=['Status'], x=[count], orientation='h',
            marker_color=_STATUS_COLOR.get(status, '#94a3b8'), marker_line_width=0,
            hovertemplate=f"<b>{status}</b>: {count:,}<extra></extra>",
        ))
    status_fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        height=50, margin=dict(t=0, b=0, l=0, r=0), showlegend=False, barmode='stack',
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False),
    )
    status_legend = [
        html.Div([
            html.Span('●', style={'color': _STATUS_COLOR.get(s, '#94a3b8'), 'marginRight': '6px'}),
            html.Span(f"{s}: {c:,}", style={'fontSize': '10px', 'fontWeight': '700', 'color': UI['text_secondary']}),
        ], style={'marginRight': '12px', 'display': 'inline-block'})
        for s, c in sorted(m['status_counts'].items(), key=lambda x: -x[1])
    ]

    trend_card = _card([
        _card_header('Weekly Pay Trend', 'payroll_transactions.csv'),
        html.Div(style={'display': 'flex', 'gap': '32px'}, children=[
            html.Div(style={'flex': '2'}, children=[
                _section_label('Gross vs net, by weekly pay run'),
                dcc.Graph(figure=trend_fig, config={'displayModeBar': False}),
            ]),
            html.Div(style={'flex': '1'}, children=[
                _section_label('Transaction status'),
                dcc.Graph(figure=status_fig, config={'displayModeBar': False}),
                html.Div(status_legend, style={'marginTop': '8px'}),
            ]),
        ]),
    ])

    return html.Div(style={'marginBottom': '28px'}, children=[
        html.Div(style={
            'display': 'flex', 'alignItems': 'baseline', 'gap': '10px', 'marginBottom': '14px',
        }, children=[
            html.Div('Payroll Transactions', style={
                'fontSize': '13px', 'fontWeight': '800', 'color': UI['text_primary'],
                'textTransform': 'uppercase', 'letterSpacing': '0.01em',
            }),
            html.Div('Volumetrics', style=_SECTION_BADGE),
        ]),
        html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '16px'}, children=[
            headline,
            trend_card,
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
        render_dimension_grid(dq_results, key_prefix='pay-'),
    ])
