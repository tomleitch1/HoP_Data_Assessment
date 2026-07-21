from dash import html
from hr_dashboard.core.theme import DISPLAY_FONT

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS & STYLES
# ═══════════════════════════════════════════════════════════════════════════════

RAG_HEX = {'Red': '#E74C3C', 'Amber': '#F39C12', 'Green': '#27AE60'}
SEV_HEX = {'Critical': '#C0392B', 'High': '#E67E22', 'Medium': '#F1C40F', 'Low': '#3498DB'}
HOUSE_HEX = {'Royal Mail Group': '#CC092F'}

CHART_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(family='Inter, sans-serif', color='#64748B', size=11),
    margin=dict(t=20, b=40, l=10, r=10),
    showlegend=True,
)

# ═══════════════════════════════════════════════════════════════════════════════
# UI COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════

def kpi_card(value, label, colour, sublabel=''):
    return html.Div([
        html.Div(style={'display': 'flex', 'alignItems': 'flex-start', 'gap': '16px'}, children=[
            html.Div(style={'width': '4px', 'height': '40px', 'background': colour, 'borderRadius': '2px', 'marginTop': '4px'}),
            html.Div([
                html.Div(str(value), style={
                    'fontSize': '32px', 'fontWeight': '800', 'color': '#1E293B',
                    'lineHeight': '1.1', 'fontFamily': DISPLAY_FONT, 'letterSpacing': '-0.5px'
                }),
                html.Div(label, style={
                    'fontSize': '10px', 'fontWeight': '700', 'color': '#94A3B8',
                    'textTransform': 'uppercase', 'letterSpacing': '1px', 'marginTop': '8px'
                }),
                html.Div(sublabel, style={
                    'fontSize': '13px', 'fontWeight': '700', 'color': '#475569',
                    'marginTop': '2px', 'letterSpacing': '-0.2px'
                }) if sublabel else html.Div(),
            ])
        ])
    ], style={
        'background': 'white', 'border': '1px solid #E2E8F0',
        'borderRadius': '12px', 'padding': '20px 24px',
        'flex': '1', 'minWidth': '220px',
        'boxShadow': '0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03)',
    })


def card(children, style=None):
    base = {
        'background': 'white', 'border': '1px solid #E2E8F0',
        'borderRadius': '8px', 'padding': '24px',
        'boxShadow': '0 1px 3px rgba(0,0,0,0.05)',
    }
    if style:
        base.update(style)
    return html.Div(children, style=base)


def section_header(title, subtitle=''):
    return html.Div([
        html.Div(title, style={
            'fontSize': '14px', 'fontWeight': '700', 'color': '#1E293B',
            'textTransform': 'uppercase', 'letterSpacing': '1px',
        }),
        html.Div(subtitle, style={
            'fontSize': '12px', 'color': '#64748B', 'marginTop': '3px'
        }) if subtitle else html.Div(),
        html.Hr(style={'border': 'none', 'borderTop': '1px solid #E2E8F0', 'margin': '12px 0 20px'}),
    ])


def header_bar():
    return html.Div(style={
        'background': '#1a1a1a',
        'borderBottom': '3px solid #CC092F', 'padding': '0',
        'boxShadow': '0 1px 2px rgba(0,0,0,0.2)',
    }, children=[
        html.Div(style={
            'maxWidth': '1440px', 'margin': '0 auto',
            'padding': '16px 32px',
            'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
        }, children=[
            html.Div([
                html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'marginBottom': '2px'}, children=[
                    html.Div('HR & PAYROLL SYSTEMS — BID DEMONSTRATION', style={
                        'fontSize': '11px', 'fontWeight': '700', 'color': '#d9a5ac',
                        'letterSpacing': '2px',
                    }),
                    html.Div('DUMMY DATA', style={
                        'fontSize': '10px', 'fontWeight': '800', 'color': '#ffffff',
                        'letterSpacing': '1px', 'background': 'rgba(255,255,255,0.15)',
                        'border': '1px solid rgba(255,255,255,0.3)',
                        'padding': '2px 8px', 'borderRadius': '4px',
                    }),
                ]),
                html.Div('Data Quality Assessment', style={
                    'fontSize': '22px', 'fontWeight': '700', 'color': '#ffffff',
                    'letterSpacing': '-0.5px',
                }),
            ]),
            html.Div(style={'display': 'flex', 'gap': '12px', 'alignItems': 'center'}, children=[
                html.Div([
                    html.Div('ROYAL MAIL GROUP', style={'fontSize': '11px', 'fontWeight': '700', 'letterSpacing': '1px'}),
                ], style={
                    'background': '#CC092F', 'padding': '8px 16px',
                    'borderRadius': '4px', 'color': 'white', 'textAlign': 'center',
                }),
                html.Div([
                    html.Div('VERAN PERFORMANCE', style={'fontSize': '11px', 'fontWeight': '700', 'letterSpacing': '1px', 'color': '#ffffff'}),
                ], style={'padding': '8px 16px', 'textAlign': 'center', 'borderLeft': '1px solid rgba(255,255,255,0.2)', 'marginLeft': '8px'}),
            ]),
        ]),
    ])


def fmt_gbp(val: float) -> str:
    if abs(val) >= 1_000_000:
        return f'£{val / 1_000_000:.1f}M'
    if abs(val) >= 1_000:
        return f'£{val / 1_000:.0f}k'
    return f'£{val:,.0f}'
