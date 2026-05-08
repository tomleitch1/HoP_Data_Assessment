from dash import html, dcc, dash_table
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import textwrap
from dashboard.shared.ui import card, section_header, kpi_card, RAG_HEX, HOUSE_HEX, CHART_LAYOUT
from dashboard.core.theme import DISPLAY_FONT

DIMENSION_DESCRIPTIONS = {
    'Completeness': 'Ensuring all required data fields are populated. Missing values in critical fields like Bank Accounts or Tax Codes will cause payment failures in Unit4.',
    'Validity': 'Ensuring data follows the correct format and business rules. For example, sort codes must follow the XX-XX-XX format for UK banking.',
    'Uniqueness': 'Identifying duplicate records. Duplicate suppliers or customers lead to fragmented spend analysis and potential double payments.',
    'Timeliness': 'Assessing how up-to-date the records are, particularly regarding aged debt and overdue invoices which need resolution before migration.',
    'Referential Integrity': 'Ensuring consistency between related tables. For example, all open transactions must belong to an active and valid supplier master record.',
    'Consistency': 'Ensuring data is consistent across different systems or modules.'
}

def _house_scorecard_row(scored_dq, house, house_color):
    total_checks = len(scored_dq)
    checks_green = int((scored_dq['rag'] == 'Green').sum())
    checks_amber = int((scored_dq['rag'] == 'Amber').sum())
    checks_red   = int((scored_dq['rag'] == 'Red').sum())
    overall_pct  = round(checks_green / total_checks * 100, 1) if total_checks > 0 else 0.0
    rag_color    = RAG_HEX['Green'] if overall_pct >= 90 else RAG_HEX['Amber'] if overall_pct >= 70 else RAG_HEX['Red']

    # CSS conic-gradient donut ring
    donut = html.Div(style={
        'width': '96px', 'height': '96px', 'borderRadius': '50%', 'flexShrink': '0',
        'background': f'conic-gradient({rag_color} {overall_pct}%, #E2E8F0 0%)',
        'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center',
    }, children=[
        html.Div(style={
            'width': '68px', 'height': '68px', 'borderRadius': '50%', 'background': 'white',
            'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center',
        }, children=[
            html.Span(f"{overall_pct:.0f}%", style={
                'fontSize': '18px', 'fontWeight': '800', 'color': rag_color, 'fontFamily': DISPLAY_FONT,
            }),
        ]),
    ])

    circle_card = html.Div(style={
        'flex': '1', 'background': 'white', 'borderRadius': '12px',
        'border': '1px solid #E2E8F0', 'padding': '16px',
        'display': 'flex', 'flexDirection': 'column', 'alignItems': 'center', 'justifyContent': 'center', 'gap': '8px',
    }, children=[
        donut,
        html.Div('Overall DQ Score', style={
            'fontSize': '10px', 'fontWeight': '700', 'color': '#94A3B8',
            'letterSpacing': '0.08em', 'textTransform': 'uppercase', 'textAlign': 'center',
        }),
    ])

    # Severity breakdown
    sev_counts = scored_dq['severity'].value_counts()
    sev_items  = [('Critical', '#E74C3C'), ('High', '#E67E22'), ('Medium', '#F59E0B'), ('Low', '#64748B')]
    sev_rows   = [
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px'}, children=[
            html.Div(style={'width': '8px', 'height': '8px', 'borderRadius': '50%', 'background': col, 'flexShrink': '0'}),
            html.Span(f"{int(sev_counts.get(sev, 0))} {sev}", style={'fontSize': '12px', 'color': '#475569', 'fontWeight': '500'}),
        ])
        for sev, col in sev_items if sev_counts.get(sev, 0) > 0
    ]

    checks_card = html.Div(style={
        'flex': '1', 'background': 'white', 'borderRadius': '12px',
        'border': '1px solid #E2E8F0', 'padding': '16px',
    }, children=[
        html.Div(f"{total_checks}", style={
            'fontSize': '32px', 'fontWeight': '800', 'color': '#1E293B', 'lineHeight': '1', 'fontFamily': DISPLAY_FONT,
        }),
        html.Div('Total Checks', style={
            'fontSize': '10px', 'fontWeight': '700', 'color': '#94A3B8',
            'letterSpacing': '0.08em', 'textTransform': 'uppercase', 'marginBottom': '12px', 'marginTop': '4px',
        }),
        html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '6px'}, children=sev_rows),
    ])

    # RAG bar card — full width, below the two cards
    bar_segs = [
        html.Div(style={'flex': str(n / total_checks), 'background': c, 'minWidth': '2px'})
        for n, c in [(checks_green, RAG_HEX['Green']), (checks_amber, RAG_HEX['Amber']), (checks_red, RAG_HEX['Red'])]
        if n > 0
    ]
    rag_legend = [
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '6px'}, children=[
            html.Div(style={'width': '10px', 'height': '10px', 'borderRadius': '2px', 'background': c}),
            html.Span(f"{n} {label}", style={'fontSize': '12px', 'color': '#475569', 'fontWeight': '600'}),
        ])
        for n, label, c in [(checks_green, 'Green', RAG_HEX['Green']), (checks_amber, 'Amber', RAG_HEX['Amber']), (checks_red, 'Red', RAG_HEX['Red'])]
    ]

    rag_card = html.Div(style={
        'background': 'white', 'borderRadius': '12px', 'border': '1px solid #E2E8F0',
        'padding': '16px', 'marginTop': '12px',
    }, children=[
        html.Div(style={
            'display': 'flex', 'height': '8px', 'borderRadius': '4px',
            'overflow': 'hidden', 'marginBottom': '10px', 'gap': '2px',
        }, children=bar_segs),
        html.Div(style={'display': 'flex', 'gap': '20px', 'flexWrap': 'wrap'}, children=rag_legend),
    ])

    return html.Div(style={'flex': '1', 'minWidth': '320px'}, children=[
        html.Div(house, style={
            'background': house_color, 'color': '#fff',
            'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.1em',
            'padding': '5px 12px', 'borderRadius': '6px 6px 0 0',
            'display': 'inline-block', 'marginBottom': '8px',
        }),
        html.Div(style={'display': 'flex', 'gap': '12px'}, children=[circle_card, checks_card]),
        rag_card,
    ])

def render_dimension_scorecard(dq_results):
    if dq_results is None or dq_results.empty:
        return html.Div(style={'padding': '60px', 'textAlign': 'center', 'color': '#94A3B8'}, children=[
            html.Div("No dimension analysis available.", style={'fontSize': '18px', 'fontWeight': '600'}),
        ])

    scored_dq = dq_results[dq_results['severity'] != 'Info']
    houses    = sorted(scored_dq['house'].unique()) if 'house' in scored_dq.columns else []

    if not houses:
        return html.Div()

    rows = []
    for h in houses:
        color = HOUSE_HEX.get(h, '#4a3d6b')
        rows.append(_house_scorecard_row(scored_dq[scored_dq['house'] == h], h, color))

    return html.Div(style={'display': 'flex', 'gap': '24px', 'marginBottom': '24px', 'flexWrap': 'wrap'}, children=rows)

def render_dimension_grid(dq_results):
    if dq_results is None or dq_results.empty: return html.Div()
    
    dim_summary = dq_results.groupby('dimension').agg({
        'error_rate': 'mean'
    }).reset_index().sort_values('error_rate', ascending=False)

    return html.Div(style={
        'display': 'grid', 
        'gridTemplateColumns': 'repeat(auto-fill, minmax(480px, 1fr))', 
        'gap': '20px',
        'marginBottom': '24px',
        'alignItems': 'start'
    }, children=[
        render_dimension_widget(dim, dq_results) for dim in dim_summary['dimension']
    ])

def render_dimension_widget(dim_name, dq_results):
    sub = dq_results[dq_results['dimension'] == dim_name].copy()
    if sub.empty: return html.Div()

    total_checks = len(sub['check_id'].unique())
    desc = DIMENSION_DESCRIPTIONS.get(dim_name, 'No description available.')
    hoc_error = sub[sub['house'] == 'HOC']['error_rate'].mean() if 'HOC' in sub['house'].values else None
    hol_error = sub[sub['house'] == 'HOL']['error_rate'].mean() if 'HOL' in sub['house'].values else None
    worst_error = max(e for e in [hoc_error, hol_error] if e is not None)
    
    dim_checks = sub[['check_id', 'description', 'object']].drop_duplicates('check_id').sort_values('check_id')
    check_ids = dim_checks['check_id'].tolist()
    
    # Create unique labels by combining object and description
    # This prevents Plotly from stacking bars with identical descriptions
    check_descs = []
    for _, r in dim_checks.iterrows():
        clean_desc = r['description'].replace('<br>', ' ')
        label = f"<b>{r['object']}</b>: {clean_desc}"
        wrapped_label = "<br>".join(textwrap.wrap(label, width=75))
        check_descs.append(wrapped_label)
    
    fig = go.Figure()
    for house in ['HOC', 'HOL']:
        h_data = sub[sub['house'] == house].set_index('check_id').reindex(check_ids)
        fig.add_trace(go.Bar(
            name=f"{house} (Ready)", x=[100] * len(check_ids), y=check_descs, orientation='h',
            marker_color='rgba(226, 232, 240, 0.3)', showlegend=False,
            hovertemplate=f'<b>{house}</b>: Click anywhere to inspect records<extra></extra>',
            offsetgroup=house, customdata=np.stack((check_ids, [house] * len(check_ids)), axis=-1),
        ))
        rates = h_data['error_rate'].fillna(0).tolist()
        pos = ['inside' if v > 75 else 'outside' for v in rates]
        col = ['white' if v > 75 else '#1E293B' for v in rates]
        fig.add_trace(go.Bar(
            name=house, x=rates, y=check_descs, orientation='h', marker_color=HOUSE_HEX.get(house),
            offsetgroup=house, customdata=np.stack((check_ids, [house] * len(check_ids)), axis=-1),
            hovertemplate=f'<b>{house}</b><br>%{{y}}<br>Error Rate: %{{x}}%<extra></extra>',
            text=[f"{v:.1f}%" if v > 0 else "" for v in rates], textposition=pos, textfont=dict(size=10, color=col, family='Poppins')
        ))

    fig.update_layout(**CHART_LAYOUT)
    fig.update_layout(height=max(250, len(check_ids) * 70), barmode='group', margin=dict(t=10, b=10, l=20, r=50),
                      xaxis=dict(range=[0, 100], showgrid=True, gridcolor='#F1F5F9', ticksuffix='%'),
                      yaxis=dict(automargin=True, color='#64748B', tickfont=dict(size=10)),
                      legend=dict(orientation='h', y=-0.05, x=1, xanchor='right', font=dict(size=10)))
    
    accent_color = RAG_HEX['Green'] if worst_error <= 5 else RAG_HEX['Amber'] if worst_error <= 15 else RAG_HEX['Red']

    def _house_score(error, house):
        if error is None:
            return html.Div()
        house_color = HOUSE_HEX.get(house, '#4a3d6b')
        score_color = RAG_HEX['Green'] if error <= 5 else RAG_HEX['Amber'] if error <= 15 else RAG_HEX['Red']
        return html.Div(style={
            'display': 'flex', 'alignItems': 'center', 'gap': '6px',
            'border': f'1.5px solid rgba({int(house_color[1:3],16)},{int(house_color[3:5],16)},{int(house_color[5:7],16)},0.2)', 'borderRadius': '8px',
            'padding': '4px 10px',
        }, children=[
            html.Span(house, style={
                'fontSize': '9px', 'fontWeight': '700', 'color': '#64748B',
                'background': '#F1F5F9', 'padding': '2px 6px',
                'borderRadius': '3px', 'letterSpacing': '0.08em',
            }),
            html.Span(f"{error:.1f}%", style={
                'fontSize': '17px', 'fontWeight': '800', 'color': score_color, 'fontFamily': DISPLAY_FONT,
            }),
        ])

    divider = html.Div(style={
        'width': '1px', 'height': '22px',
        'background': 'linear-gradient(to bottom, transparent, #CBD5E1, transparent)',
    })

    summary_content = html.Div(style={
        'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'width': '100%',
        'padding': '14px 20px', 'cursor': 'pointer', 'boxSizing': 'border-box',
    }, children=[
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '12px'}, children=[
            html.Div(style={'width': '4px', 'height': '28px', 'background': accent_color, 'borderRadius': '2px', 'flexShrink': '0'}),
            html.Div([
                html.Div(dim_name.upper(), style={
                    'fontSize': '12px', 'fontWeight': '700', 'color': '#334155',
                    'letterSpacing': '1.2px', 'marginBottom': '3px',
                }),
                html.Div(f"{total_checks} migration checks", style={
                    'fontSize': '10px', 'color': '#94A3B8', 'fontWeight': '600', 'textTransform': 'uppercase',
                }),
            ])
        ]),
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '12px'}, children=[
            _house_score(hoc_error, 'HOC'),
            divider,
            _house_score(hol_error, 'HOL'),
            html.Span('avg error', style={
                'fontSize': '9px', 'fontWeight': '600', 'color': '#94A3B8',
                'textTransform': 'uppercase', 'letterSpacing': '0.05em', 'marginLeft': '2px',
            }),
        ])
    ])

    expanded_content = html.Div(style={'padding': '0 24px 24px 24px', 'borderTop': '1px solid #F1F5F9'}, children=[
        html.Div(desc, style={
            'fontSize': '12px', 'color': '#64748B', 'marginTop': '16px', 
            'lineHeight': '1.6', 'maxWidth': '800px'
        }),
        html.Div(style={'marginTop': '24px'}, children=[
            dcc.Graph(id={'type': 'dim-widget-chart', 'index': dim_name}, figure=fig, config={'displayModeBar': False})
        ])
    ])

    return html.Details([
        html.Summary(summary_content, style={'listStyle': 'none', 'outline': 'none'}),
        expanded_content
    ], style={
        'background': 'white', 'border': '1px solid #E2E8F0', 'borderRadius': '12px',
        'marginBottom': '16px', 'overflow': 'hidden',
        'boxShadow': '0 1px 3px rgba(0,0,0,0.05)'
    })

def render_dimensions_table(dq_results):
    if dq_results is None or dq_results.empty: return html.Div()
    df = dq_results.copy()
    df['action'] = '🔍 Inspect'
    # Include check_id in the DataFrame so it's in the 'data' but not in 'columns'
    tbl_cols = ["action", "check_id", "house", "object", "dimension", "severity", "description", "failing", "total", "error_rate", "rag"]
    df_display = df[tbl_cols].copy()
    
    return card([
        section_header('Full Rule Breakdown', 'Detailed results for every DQ rule applied'),
        html.Div([
            dash_table.DataTable(
                id={'type': 'dim-results-table', 'index': 'main'},
                # Only include visible columns here
                columns=[{"name": i, "id": i} for i in ["Action", "House", "Object", "Dimension", "Severity", "Description", "Failing", "Total", "Error %", "RAG"]],
                # Rename columns for display purposes in the DataTable data dict mapping
                data=df_display.rename(columns={
                    "action": "Action", "house": "House", "object": "Object", 
                    "dimension": "Dimension", "severity": "Severity", 
                    "description": "Description", "failing": "Failing", 
                    "total": "Total", "error_rate": "Error %", "rag": "RAG"
                }).to_dict('records'),
                sort_action="native", filter_action="native", cell_selectable=True, column_selectable="single", page_size=15,
                style_table={'overflowX': 'auto'}, style_cell={'textAlign': 'left', 'padding': '12px', 'fontFamily': 'Poppins', 'fontSize': '12px'},
                style_header={'backgroundColor': '#F8FAFC', 'fontWeight': 'bold', 'color': '#64748B', 'borderBottom': '2px solid #E2E8F0'},
                style_data_conditional=[
                    {'if': {'column_id': 'Action'}, 'color': '#006548', 'fontWeight': '700', 'cursor': 'pointer', 'textDecoration': 'underline', 'backgroundColor': '#F0FDF4'},
                    {'if': {'column_id': 'RAG', 'filter_query': '{RAG} eq "Red"'}, 'color': '#E74C3C', 'fontWeight': 'bold'},
                    {'if': {'column_id': 'RAG', 'filter_query': '{RAG} eq "Amber"'}, 'color': '#F39C12', 'fontWeight': 'bold'},
                    {'if': {'column_id': 'RAG', 'filter_query': '{RAG} eq "Green"'}, 'color': '#006548', 'fontWeight': 'bold'}
                ],
            ),
            html.Div(style={'marginTop': '20px', 'textAlign': 'right'}, children=[
                html.Span("Tip: Select a row in the Record Explorer tab to inspect specific failing records and export to Excel.", style={'fontSize': '12px', 'color': '#94A3B8', 'fontStyle': 'italic'})
            ])
        ])
    ])
