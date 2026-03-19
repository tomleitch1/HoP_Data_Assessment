from dash import html, dcc
import plotly.graph_objects as go
from dashboard.core.theme import DISPLAY_FONT, HOUSE_HEX

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS & STYLES
# ═══════════════════════════════════════════════════════════════════════════════

RAG_HEX = {'Red': '#E74C3C', 'Amber': '#F39C12', 'Green': '#27AE60'}
SEV_HEX = {'Critical': '#C0392B', 'High': '#E67E22', 'Medium': '#F1C40F', 'Low': '#3498DB'}
DIMENSION_HEX = {
    'Completeness': '#3498DB',
    'Uniqueness': '#9B59B6',
    'Validity': '#F1C40F',
    'Timeliness': '#E67E22',
    'Referential Integrity': '#E74C3C',
    'Consistency': '#1ABC9C'
}

CHART_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(family='Poppins, sans-serif', color='#64748B', size=11),
    margin=dict(t=20, b=40, l=10, r=10),
    showlegend=True,
)

# ═══════════════════════════════════════════════════════════════════════════════
# UI COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════

def kpi_card(value, label, colour, sublabel=''):
    return html.Div([
        html.Div(style={'display': 'flex', 'alignItems': 'flex-start', 'gap': '16px'}, children=[
            # Aesthetic Accent Line
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
        'background': 'white',
        'borderBottom': '1px solid #E2E8F0', 'padding': '0',
        'boxShadow': '0 1px 2px rgba(0,0,0,0.03)',
    }, children=[
        html.Div(style={
            'maxWidth': '1440px', 'margin': '0 auto',
            'padding': '16px 32px',
            'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
        }, children=[
            html.Div([
                html.Div('PARLIAMENT FINANCE SYSTEMS PROGRAMME', style={
                    'fontSize': '11px', 'fontWeight': '700', 'color': '#64748B',
                    'letterSpacing': '2px', 'marginBottom': '2px',
                }),
                html.Div('Data Quality Assessment', style={
                    'fontSize': '22px', 'fontWeight': '700', 'color': '#0F172A',
                    'letterSpacing': '-0.5px',
                }),
            ]),
            html.Div(style={'display': 'flex', 'gap': '12px', 'alignItems': 'center'}, children=[
                html.Div([
                    html.Div('HOUSE OF COMMONS', style={'fontSize': '11px', 'fontWeight': '700', 'letterSpacing': '1px'}),
                ], style={
                    'background': '#006548', 'padding': '8px 16px',
                    'borderRadius': '4px', 'color': 'white', 'textAlign': 'center',
                }),
                html.Div([
                    html.Div('HOUSE OF LORDS', style={'fontSize': '11px', 'fontWeight': '700', 'letterSpacing': '1px'}),
                ], style={
                    'background': '#C60018', 'padding': '8px 16px',
                    'borderRadius': '4px', 'color': 'white', 'textAlign': 'center',
                }),
                html.Div([
                    html.Div('VERAN PERFORMANCE', style={'fontSize': '11px', 'fontWeight': '700', 'letterSpacing': '1px', 'color': '#006548'}),
                ], style={'padding': '8px 16px', 'textAlign': 'center', 'borderLeft': '1px solid #E2E8F0', 'marginLeft': '8px'}),
            ]),
        ]),
    ])


def fmt_gbp(val: float) -> str:
    """Format large numbers as GBP strings (e.g. £1.2M, £450k)."""
    if abs(val) >= 1_000_000:
        return f'£{val / 1_000_000:.1f}M'
    if abs(val) >= 1_000:
        return f'£{val / 1_000:.0f}k'
    return f'£{val:,.0f}'


def render_volumetrics_card(house_data: dict, master_title: str = 'Supplier Master'):
    """
    Renders two distinct cards for a single house: 
    1. Supplier Master Volumetrics (with Donut chart and full status breakdown)
    2. AP Transaction Volumetrics (with Horizontal Bar chart and visible legend)
    """
    house = house_data['house']
    master = house_data['master']
    trans = house_data['transactions']
    hist = house_data['history']
    house_color = HOUSE_HEX.get(house, '#00703c')
    
    # Colors for statuses
    colors = ['#00703c', '#28a367', '#d4820a', '#c0392b', '#5c5470', '#3498DB', '#9B59B6', '#F1C40F']
    
    # ── 1. SUPPLIER MASTER CARD ──────────────────────────────────────────────
    
    # Full Master Status Breakdown
    m_status_counts = master.get('status_breakdown', {})
    m_sorted = sorted(m_status_counts.items(), key=lambda x: x[1], reverse=True)
    
    master_fig = go.Figure(go.Pie(
        labels=[s for s, c in m_sorted],
        values=[c for s, c in m_sorted],
        hole=0.7,
        marker_colors=colors,
        textinfo='none',
        hovertemplate='<b>Status %{label}</b>: %{value:,}<extra></extra>'
    ))
    master_fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        height=140, margin=dict(t=0, b=0, l=0, r=0), showlegend=False,
        annotations=[dict(text=f"<b>{master['total']:,}</b><br><span style='font-size:9px'>TOTAL</span>", 
                          x=0.5, y=0.5, showarrow=False, font=dict(size=16, color='#1E293B', family=DISPLAY_FONT))]
    )
    
    # Create a visible list for Master statuses
    m_status_list = []
    for i, (status, count) in enumerate(m_sorted):
        m_status_list.append(html.Div([
            html.Span('●', style={'color': colors[i % len(colors)], 'marginRight': '8px'}),
            html.Span(f"Status {status}: ", style={'fontSize': '11px', 'fontWeight': '600', 'color': '#64748B'}),
            html.Span(f"{count:,}", style={'fontSize': '11px', 'fontWeight': '700', 'color': '#1E293B'})
        ], style={'marginBottom': '4px', 'display': 'inline-block', 'width': '50%', 'whiteSpace': 'nowrap'}))

    master_card = html.Div(style={
        'background': 'white', 'border': '1px solid #D0CCE0', 'borderRadius': '12px',
        'flex': '1', 'display': 'flex', 'flexDirection': 'column', 'overflow': 'hidden',
        'boxShadow': '0 4px 6px -1px rgba(0,0,0,0.05)'
    }, children=[
        # Refined Header
        html.Div(style={
            'background': '#F8FAFC', 'padding': '14px 20px', 'borderBottom': '1px solid #E2E8F0', 
            'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center'
        }, children=[
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '12px'}, children=[
                # Aesthetic Accent Line
                html.Div(style={'width': '3px', 'height': '16px', 'background': house_color, 'borderRadius': '2px'}),
                html.Div(f"{house} — {master_title}", style={
                    'fontSize': '13px', 'fontWeight': '600', 'color': '#475569', 
                    'textTransform': 'uppercase', 'letterSpacing': '0.5px'
                }),
            ]),
            html.Div(master.get('extract_date', '—'), style={'fontSize': '10px', 'color': '#94A3B8', 'fontWeight': '600'})
        ]),
        # Body
        html.Div(style={'padding': '20px', 'display': 'flex', 'flexDirection': 'column'}, children=[
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '20px', 'marginBottom': '16px'}, children=[
                html.Div(style={'flex': '1'}, children=[dcc.Graph(figure=master_fig, config={'displayModeBar': False})]),
                html.Div(style={'flex': '1.2'}, children=[
                    html.Div('Population Status', style={'fontSize': '10px', 'fontWeight': '700', 'color': '#64748B', 'textTransform': 'uppercase', 'marginBottom': '8px'}),
                    html.Div(m_status_list, style={'display': 'flex', 'flexWrap': 'wrap'})
                ])
            ])
        ])
    ])
    
    # ── 2. AP TRANSACTION CARD ───────────────────────────────────────────────
    
    # Status Breakdown Horizontal Bar Chart
    t_status_counts = trans.get('status_breakdown', {})
    t_sorted = sorted(t_status_counts.items(), key=lambda x: x[1], reverse=True)
    
    trans_fig = go.Figure()
    for i, (status, count) in enumerate(t_sorted):
        if count == 0: continue
        trans_fig.add_trace(go.Bar(
            name=f"Status {status}", y=['Status'], x=[count], orientation='h',
            marker_color=colors[i % len(colors)], marker_line_width=0,
            hovertemplate=f"<b>Status {status}</b>: {count:,}<extra></extra>"
        ))
    
    trans_fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        height=50, margin=dict(t=0, b=0, l=0, r=0), showlegend=False, barmode='stack',
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False)
    )

    # Create a visible legend for Transaction statuses
    t_legend = []
    for i, (status, count) in enumerate(t_sorted):
        t_legend.append(html.Div([
            html.Span('●', style={'color': colors[i % len(colors)], 'marginRight': '6px'}),
            html.Span(f"{status}: {count:,}", style={'fontSize': '10px', 'fontWeight': '700', 'color': '#64748B'})
        ], style={'marginRight': '12px', 'display': 'inline-block'}))

    trans_card = html.Div(style={
        'background': 'white', 'border': '1px solid #D0CCE0', 'borderRadius': '12px',
        'flex': '2', 'display': 'flex', 'flexDirection': 'column', 'overflow': 'hidden',
        'boxShadow': '0 4px 6px -1px rgba(0,0,0,0.05)'
    }, children=[
        # Refined Header
        html.Div(style={
            'background': '#F8FAFC', 'padding': '14px 20px', 'borderBottom': '1px solid #E2E8F0', 
            'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center'
        }, children=[
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '12px'}, children=[
                # Aesthetic Accent Line
                html.Div(style={'width': '3px', 'height': '16px', 'background': house_color, 'borderRadius': '2px'}),
                html.Div(f"{house} — AP Transactions", style={
                    'fontSize': '13px', 'fontWeight': '600', 'color': '#475569', 
                    'textTransform': 'uppercase', 'letterSpacing': '0.5px'
                }),
            ]),
            html.Div(trans.get('extract_date', '—'), style={'fontSize': '10px', 'color': '#94A3B8', 'fontWeight': '600'})
        ]),
        # Body
        html.Div(style={'padding': '20px'}, children=[
            html.Div(style={'display': 'grid', 'gridTemplateColumns': 'repeat(4, 1fr)', 'gap': '16px', 'marginBottom': '20px'}, children=[
                html.Div([
                    html.Div(f"{trans['open_count']:,}", style={'fontSize': '22px', 'fontWeight': '800', 'color': '#1E293B', 'fontFamily': DISPLAY_FONT}),
                    html.Div('Open Count', style={'fontSize': '10px', 'fontWeight': '600', 'color': '#64748B', 'textTransform': 'uppercase'})
                ]),
                html.Div([
                    html.Div(fmt_gbp(trans['balance']), style={'fontSize': '22px', 'fontWeight': '800', 'color': '#00703c', 'fontFamily': DISPLAY_FONT}),
                    html.Div('Open Bal', style={'fontSize': '10px', 'fontWeight': '600', 'color': '#64748B', 'textTransform': 'uppercase'})
                ]),
                html.Div([
                    html.Div(f"{trans['overdue_count']:,}", style={'fontSize': '22px', 'fontWeight': '800', 'color': '#c0392b', 'fontFamily': DISPLAY_FONT}),
                    html.Div('Overdue', style={'fontSize': '10px', 'fontWeight': '600', 'color': '#64748B', 'textTransform': 'uppercase'})
                ]),
                html.Div([
                    html.Div(f"{int(trans['avg_days_old'])}d", style={'fontSize': '22px', 'fontWeight': '800', 'color': '#1E293B', 'fontFamily': DISPLAY_FONT}),
                    html.Div('Avg Age', style={'fontSize': '10px', 'fontWeight': '600', 'color': '#64748B', 'textTransform': 'uppercase'})
                ]),
            ]),
            html.Div([
                html.Div(style={'display': 'flex', 'justifyContent': 'space-between', 'marginBottom': '8px'}, children=[
                    html.Div('Status Distribution', style={'fontSize': '10px', 'fontWeight': '700', 'color': '#64748B', 'textTransform': 'uppercase'}),
                    html.Div(f"Total: {sum(t_status_counts.values()):,} items", style={'fontSize': '9px', 'color': '#94A3B8'})
                ]),
                dcc.Graph(figure=trans_fig, config={'displayModeBar': False}),
                html.Div(t_legend, style={'marginTop': '8px', 'display': 'flex', 'flexWrap': 'wrap'})
            ])
        ]),
        html.Div(style={'background': '#F1F5F9', 'padding': '8px 20px', 'fontSize': '11px', 'color': '#64748B', 'borderTop': '1px solid #E2E8F0'}, children=[
            html.Span('AP History (asuhistr) · ', style={'fontWeight': '600'}),
            html.Span(f"{hist['total']:,} records", style={'color': '#1E293B', 'fontWeight': '700'})
        ])
    ])
    
    return [master_card, trans_card]


def render_gl_volumetrics_card(house_data: dict):
    """
    Renders GL volumetrics as a list of three distinct cards for a single house:
    1. Chart of Accounts (coa_card)
    2. Dimension Values (dim_card)
    3. Opening Balances (ob_card)
    """
    from dash import html, dcc
    import plotly.graph_objects as go
    from dashboard.core.theme import DISPLAY_FONT, HOUSE_HEX

    house = house_data['house']
    coa = house_data['coa']
    ob = house_data['ob']
    dim = house_data['dim']
    house_color = HOUSE_HEX.get(house, '#00703c')

    # Colors for various elements
    colors = ['#00703c', '#28a367', '#d4820a', '#c0392b', '#5c5470', '#3498DB', '#9B59B6', '#F1C40F']

    # ── 1. CHART OF ACCOUNTS CARD ──────────────────────────────────────────────
    
    coa_types = sorted(coa.get('type_breakdown', {}).items(), key=lambda x: x[1], reverse=True)
    
    # We will do a simple horizontal bar for COA types
    coa_fig = go.Figure()
    for i, (ctype, count) in enumerate(coa_types):
        if count == 0: continue
        coa_fig.add_trace(go.Bar(
            name=str(ctype), y=['Type'], x=[count], orientation='h',
            marker_color=colors[i % len(colors)], marker_line_width=0,
            hovertemplate=f"<b>{ctype}</b>: {count:,}<extra></extra>"
        ))
    coa_fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        height=40, margin=dict(t=0, b=0, l=0, r=0), showlegend=False, barmode='stack',
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False)
    )
    
    coa_legend = []
    for i, (ctype, count) in enumerate(coa_types):
        coa_legend.append(html.Div([
            html.Span('●', style={'color': colors[i % len(colors)], 'marginRight': '6px'}),
            html.Span(f"{ctype}: {count:,}", style={'fontSize': '10px', 'fontWeight': '700', 'color': '#64748B'})
        ], style={'marginRight': '12px', 'display': 'inline-block'}))

    coa_card = html.Div(style={
        'background': 'white', 'border': '1px solid #D0CCE0', 'borderRadius': '12px',
        'flex': '1', 'display': 'flex', 'flexDirection': 'column', 'overflow': 'hidden',
        'boxShadow': '0 4px 6px -1px rgba(0,0,0,0.05)'
    }, children=[
        html.Div(style={
            'background': '#F8FAFC', 'padding': '14px 20px', 'borderBottom': '1px solid #E2E8F0',
            'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center'
        }, children=[
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '12px'}, children=[
                html.Div(style={'width': '3px', 'height': '16px', 'background': house_color, 'borderRadius': '2px'}),
                html.Div(f"{house} — Chart of Accounts", style={
                    'fontSize': '13px', 'fontWeight': '600', 'color': '#475569',
                    'textTransform': 'uppercase', 'letterSpacing': '0.5px'
                }),
            ]),
            html.Div(coa.get('extract_date', '—'), style={'fontSize': '10px', 'color': '#94A3B8', 'fontWeight': '600'})
        ]),
        html.Div(style={'padding': '20px'}, children=[
            html.Div(style={'display': 'flex', 'justifyContent': 'space-between', 'marginBottom': '20px'}, children=[
                html.Div([
                    html.Div(f"{coa['total']:,}", style={'fontSize': '28px', 'fontWeight': '800', 'color': '#1E293B', 'fontFamily': DISPLAY_FONT}),
                    html.Div('Total Accounts', style={'fontSize': '10px', 'fontWeight': '600', 'color': '#64748B', 'textTransform': 'uppercase'})
                ]),
                html.Div(style={'textAlign': 'right'}, children=[
                    html.Div([
                        html.Span(f"{coa['active']:,} ", style={'fontWeight': '700', 'color': '#006548'}),
                        html.Span("Active", style={'fontSize': '10px', 'color': '#64748B', 'textTransform': 'uppercase'})
                    ], style={'marginBottom': '4px'}),
                    html.Div([
                        html.Span(f"{coa['inactive']:,} ", style={'fontWeight': '700', 'color': '#c0392b'}),
                        html.Span("Inactive", style={'fontSize': '10px', 'color': '#64748B', 'textTransform': 'uppercase'})
                    ])
                ])
            ]),
            html.Div([
                html.Div('Account Type Breakdown', style={'fontSize': '10px', 'fontWeight': '700', 'color': '#64748B', 'textTransform': 'uppercase', 'marginBottom': '8px'}),
                dcc.Graph(figure=coa_fig, config={'displayModeBar': False}),
                html.Div(coa_legend, style={'marginTop': '8px', 'display': 'flex', 'flexWrap': 'wrap'})
            ])
        ])
    ])

    # ── 2. DIMENSION VALUES CARD ──────────────────────────────────────────────
    
    dim_types = sorted(dim.get('type_breakdown', {}).items(), key=lambda x: x[1], reverse=True)
    
    dim_fig = go.Figure()
    for i, (dtype, count) in enumerate(dim_types):
        if count == 0: continue
        dim_fig.add_trace(go.Bar(
            name=str(dtype), y=['Type'], x=[count], orientation='h',
            marker_color=colors[(i+3) % len(colors)], marker_line_width=0,
            hovertemplate=f"<b>{dtype}</b>: {count:,}<extra></extra>"
        ))
    dim_fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        height=40, margin=dict(t=0, b=0, l=0, r=0), showlegend=False, barmode='stack',
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False)
    )
    
    dim_legend = []
    for i, (dtype, count) in enumerate(dim_types):
        dim_legend.append(html.Div([
            html.Span('●', style={'color': colors[(i+3) % len(colors)], 'marginRight': '6px'}),
            html.Span(f"{dtype}: {count:,}", style={'fontSize': '10px', 'fontWeight': '700', 'color': '#64748B'})
        ], style={'marginRight': '12px', 'display': 'inline-block'}))

    dim_card = html.Div(style={
        'background': 'white', 'border': '1px solid #D0CCE0', 'borderRadius': '12px',
        'flex': '1', 'display': 'flex', 'flexDirection': 'column', 'overflow': 'hidden',
        'boxShadow': '0 4px 6px -1px rgba(0,0,0,0.05)'
    }, children=[
        html.Div(style={
            'background': '#F8FAFC', 'padding': '14px 20px', 'borderBottom': '1px solid #E2E8F0',
            'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center'
        }, children=[
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '12px'}, children=[
                html.Div(style={'width': '3px', 'height': '16px', 'background': house_color, 'borderRadius': '2px'}),
                html.Div(f"{house} — Dimensions", style={
                    'fontSize': '13px', 'fontWeight': '600', 'color': '#475569',
                    'textTransform': 'uppercase', 'letterSpacing': '0.5px'
                }),
            ]),
            html.Div(dim.get('extract_date', '—'), style={'fontSize': '10px', 'color': '#94A3B8', 'fontWeight': '600'})
        ]),
        html.Div(style={'padding': '20px'}, children=[
            html.Div(style={'display': 'flex', 'justifyContent': 'space-between', 'marginBottom': '20px'}, children=[
                html.Div([
                    html.Div(f"{dim['total']:,}", style={'fontSize': '28px', 'fontWeight': '800', 'color': '#1E293B', 'fontFamily': DISPLAY_FONT}),
                    html.Div('Total Dimensions', style={'fontSize': '10px', 'fontWeight': '600', 'color': '#64748B', 'textTransform': 'uppercase'})
                ]),
                html.Div(style={'textAlign': 'right'}, children=[
                    html.Div([
                        html.Span(f"{dim['active']:,} ", style={'fontWeight': '700', 'color': '#006548'}),
                        html.Span("Active", style={'fontSize': '10px', 'color': '#64748B', 'textTransform': 'uppercase'})
                    ], style={'marginBottom': '4px'}),
                    html.Div([
                        html.Span(f"{dim['inactive']:,} ", style={'fontWeight': '700', 'color': '#c0392b'}),
                        html.Span("Inactive", style={'fontSize': '10px', 'color': '#64748B', 'textTransform': 'uppercase'})
                    ])
                ])
            ]),
            html.Div([
                html.Div('Attribute Breakdown', style={'fontSize': '10px', 'fontWeight': '700', 'color': '#64748B', 'textTransform': 'uppercase', 'marginBottom': '8px'}),
                dcc.Graph(figure=dim_fig, config={'displayModeBar': False}),
                html.Div(dim_legend, style={'marginTop': '8px', 'display': 'flex', 'flexWrap': 'wrap'})
            ])
        ])
    ])

    # ── 3. OPENING BALANCES CARD ──────────────────────────────────────────────
    
    def fmt_gbp_gl(val: float) -> str:
        """Format numbers as GBP strings specifically for GL."""
        if abs(val) >= 1_000_000:
            return f'£{val / 1_000_000:.1f}M'
        if abs(val) >= 1_000:
            return f'£{val / 1_000:.0f}k'
        return f'£{val:,.0f}'

    net_color = '#00703c' if ob['net_balance'] <= 0.01 else '#c0392b'

    ob_card = html.Div(style={
        'background': 'white', 'border': '1px solid #D0CCE0', 'borderRadius': '12px',
        'flex': '1.2', 'display': 'flex', 'flexDirection': 'column', 'overflow': 'hidden',
        'boxShadow': '0 4px 6px -1px rgba(0,0,0,0.05)'
    }, children=[
        html.Div(style={
            'background': '#F8FAFC', 'padding': '14px 20px', 'borderBottom': '1px solid #E2E8F0',
            'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center'
        }, children=[
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '12px'}, children=[
                html.Div(style={'width': '3px', 'height': '16px', 'background': house_color, 'borderRadius': '2px'}),
                html.Div(f"{house} — Opening Balances", style={
                    'fontSize': '13px', 'fontWeight': '600', 'color': '#475569',
                    'textTransform': 'uppercase', 'letterSpacing': '0.5px'
                }),
            ]),
            html.Div(ob.get('extract_date', '—'), style={'fontSize': '10px', 'color': '#94A3B8', 'fontWeight': '600'})
        ]),
        html.Div(style={'padding': '20px'}, children=[
            html.Div(style={'display': 'grid', 'gridTemplateColumns': 'repeat(2, 1fr)', 'gap': '16px', 'marginBottom': '20px'}, children=[
                html.Div([
                    html.Div(fmt_gbp_gl(ob['debits']), style={'fontSize': '24px', 'fontWeight': '800', 'color': '#1E293B', 'fontFamily': DISPLAY_FONT}),
                    html.Div('Total Debits', style={'fontSize': '10px', 'fontWeight': '600', 'color': '#64748B', 'textTransform': 'uppercase'})
                ]),
                html.Div([
                    html.Div(fmt_gbp_gl(ob['credits']), style={'fontSize': '24px', 'fontWeight': '800', 'color': '#1E293B', 'fontFamily': DISPLAY_FONT}),
                    html.Div('Total Credits', style={'fontSize': '10px', 'fontWeight': '600', 'color': '#64748B', 'textTransform': 'uppercase'})
                ]),
                html.Div([
                    html.Div(f"{ob['total_rows']:,}", style={'fontSize': '24px', 'fontWeight': '800', 'color': '#1E293B', 'fontFamily': DISPLAY_FONT}),
                    html.Div('Ledger Rows', style={'fontSize': '10px', 'fontWeight': '600', 'color': '#64748B', 'textTransform': 'uppercase'})
                ]),
                html.Div([
                    html.Div(fmt_gbp_gl(ob['net_balance']), style={'fontSize': '24px', 'fontWeight': '800', 'color': net_color, 'fontFamily': DISPLAY_FONT}),
                    html.Div('Net Diff (Dr-Cr)', style={'fontSize': '10px', 'fontWeight': '600', 'color': '#64748B', 'textTransform': 'uppercase'})
                ]),
            ]),
            html.Div(style={'background': '#F8FAFC', 'padding': '12px', 'borderRadius': '6px', 'fontSize': '11px', 'color': '#64748B'}, children=[
                html.Span('Ledger balances should ideally net to zero. Any Net Diff > £0.01 indicates an out-of-balance Trial Balance.', style={'lineHeight': '1.4'})
            ])
        ])
    ])

    return [coa_card, dim_card, ob_card]
