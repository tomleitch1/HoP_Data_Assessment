from dash import html, dcc, dash_table, Input, Output, callback
import pandas as pd
from dashboard.shared.ui import card, section_header, RAG_HEX, HOUSE_HEX

def render_explorer_layout(dq_results):
    # Get unique checks and houses
    checks = dq_results[['check_id', 'description']].drop_duplicates()
    check_options = [{'label': f"{row['check_id']} - {row['description'][:80]}", 'value': row['check_id']} 
                     for _, row in checks.sort_values('check_id').iterrows()]
    
    return html.Div([
        card([
            section_header('Data Record Explorer', 'Select a check and house to drill down into failing records'),
            
            html.Div(style={'display': 'flex', 'gap': '20px', 'marginBottom': '20px'}, children=[
                html.Div([
                    html.Label('DQ Check', style={'fontSize': '11px', 'fontWeight': '700', 'color': '#5A7A9A', 'letterSpacing': '1px', 'marginBottom': '6px', 'display': 'block'}),
                    dcc.Dropdown(
                        id='explorer-check-id',
                        options=check_options,
                        value=check_options[0]['value'] if check_options else None,
                        placeholder='Select check...',
                        style={'width': '500px'}
                    ),
                ]),
                html.Div([
                    html.Label('House', style={'fontSize': '11px', 'fontWeight': '700', 'color': '#5A7A9A', 'letterSpacing': '1px', 'marginBottom': '6px', 'display': 'block'}),
                    dcc.Dropdown(
                        id='explorer-house',
                        options=[{'label': 'House of Commons (HOC)', 'value': 'HOC'}, {'label': 'House of Lords (HOL)', 'value': 'HOL'}],
                        value='HOC',
                        style={'width': '220px'}
                    ),
                ]),
            ]),
            
            html.Div(id='explorer-result-summary', style={'marginBottom': '20px'}),
            
            html.Div(style={'display': 'flex', 'justifyContent': 'flex-end', 'marginBottom': '12px'}, children=[
                html.Button('Download Failing Records (Excel)', id='btn-export-explorer', n_clicks=0,
                            style={'background': '#27AE60', 'color': 'white', 'border': 'none', 'padding': '8px 16px', 'borderRadius': '4px', 'fontWeight': '700', 'cursor': 'pointer'}),
                dcc.Download(id="download-explorer-csv")
            ]),

            dash_table.DataTable(
                id='explorer-table',
                style_table={'overflowX': 'auto', 'minHeight': '400px'},
                style_cell={
                    'background': '#0A1628', 'color': '#A0B8D0',
                    'border': '1px solid #1E3352', 'padding': '10px 14px',
                    'fontSize': '12px', 'fontFamily': 'Helvetica Neue, Arial',
                    'textAlign': 'left', 'whiteSpace': 'normal', 'maxWidth': '300px',
                },
                style_header={
                    'background': '#071220', 'color': '#4A7FBF',
                    'fontWeight': '700', 'fontSize': '10px',
                    'letterSpacing': '1.5px', 'textTransform': 'uppercase',
                    'border': '1px solid #1E3352', 'padding': '10px 14px',
                },
                sort_action='native',
                page_size=20,
            ),
        ])
    ])

def render_explorer_summary(check_info):
    if check_info.empty:
        return html.Div()
    
    row = check_info.iloc[0]
    error = row['error_rate']
    rag = row['rag']
    table = row['table']
    logic = row['technical_logic']
    
    return html.Div([
        # KPI Row
        html.Div(style={'display': 'flex', 'gap': '30px', 'padding': '20px', 'background': '#F8FAFC', 'borderRadius': '6px 6px 0 0', 'border': f'1px solid #E2E8F0', 'borderLeft': f'5px solid {RAG_HEX[rag]}'}, children=[
            html.Div([
                html.Div('ERROR RATE', style={'fontSize': '9px', 'fontWeight': '700', 'color': '#64748B', 'letterSpacing': '1px'}),
                html.Div(f"{error:.1f}%", style={'fontSize': '24px', 'fontWeight': '800', 'color': RAG_HEX[rag]})
            ]),
            html.Div([
                html.Div('FAILING RECORDS', style={'fontSize': '9px', 'fontWeight': '700', 'color': '#64748B', 'letterSpacing': '1px'}),
                html.Div(f"{row['failing']:,}", style={'fontSize': '24px', 'fontWeight': '800', 'color': RAG_HEX[rag]})
            ]),
            html.Div([
                html.Div('RECOMMENDED REMEDIATION', style={'fontSize': '9px', 'fontWeight': '700', 'color': '#64748B', 'letterSpacing': '1px'}),
                html.Div(row['remediation'], style={'fontSize': '14px', 'color': '#1E293B', 'marginTop': '4px', 'fontWeight': '600'})
            ]),
        ]),
        
        # Technical Logic Row
        html.Div(style={'padding': '15px 20px', 'background': '#F1F5F9', 'borderRadius': '0 0 6px 6px', 'border': '1px solid #E2E8F0', 'borderTop': 'none', 'display': 'flex', 'gap': '40px'}, children=[
            html.Div([
                html.Div('SOURCE TABLE', style={'fontSize': '9px', 'fontWeight': '700', 'color': '#64748B', 'letterSpacing': '1px'}),
                html.Code(table, style={'fontSize': '12px', 'color': '#006548', 'fontWeight': '700', 'background': '#DCFCE7', 'padding': '2px 6px', 'borderRadius': '4px'})
            ]),
            html.Div([
                html.Div('TECHNICAL VALIDATION LOGIC', style={'fontSize': '9px', 'fontWeight': '700', 'color': '#64748B', 'letterSpacing': '1px'}),
                html.Code(logic, style={'fontSize': '12px', 'color': '#475569', 'fontWeight': '600'})
            ]),
        ])
    ])
