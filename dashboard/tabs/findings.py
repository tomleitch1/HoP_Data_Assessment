from dash import html, dcc, dash_table
import pandas as pd
from dashboard.shared.ui import card, section_header, RAG_HEX, SEV_HEX, HOUSE_HEX

def render_findings_log(dq_results):
    tbl = dq_results[['dimension', 'severity', 'object', 'house', 'description', 'total', 'failing', 'pass_rate', 'rag', 'remediation']].copy()
    tbl['pass_rate'] = tbl['pass_rate'].apply(lambda x: f'{x:.1f}%')
    tbl.columns = ['Dimension', 'Severity', 'Data Object', 'House', 'Check Description', 'Total Records', 'Failing Records', 'Score', 'RAG', 'Recommended Action']
    
    return html.Div([
        card([
            section_header('Findings Log', 'Full record of all data quality checks and identified issues'),
            
            html.Div(style={'display': 'flex', 'justifyContent': 'flex-end', 'marginBottom': '12px'}, children=[
                html.Button('Export All Checks (Excel)', id='btn-export-all', n_clicks=0,
                            style={'background': '#27AE60', 'color': 'white', 'border': 'none', 'padding': '8px 16px', 'borderRadius': '4px', 'fontWeight': '700', 'cursor': 'pointer'}),
                dcc.Download(id="download-all-csv")
            ]),

            dash_table.DataTable(
                data=tbl.to_dict('records'),
                columns=[{'name': c, 'id': c} for c in tbl.columns],
                style_table={'overflowX': 'auto', 'minHeight': '500px'},
                style_cell={
                    'background': '#FFFFFF', 'color': '#1E293B',
                    'border': '1px solid #E2E8F0', 'padding': '10px 14px',
                    'fontSize': '12px', 'fontFamily': 'Poppins, sans-serif',
                    'textAlign': 'left', 'whiteSpace': 'normal', 'maxWidth': '400px',
                },
                style_header={
                    'background': '#F8FAFC', 'color': '#64748B',
                    'fontWeight': '700', 'fontSize': '10px',
                    'letterSpacing': '1.5px', 'textTransform': 'uppercase',
                    'border': '1px solid #E2E8F0', 'padding': '10px 14px',
                },
                
                style_data_conditional=[
                    {'if': {'filter_query': '{RAG} = Red', 'column_id': 'RAG'}, 'color': RAG_HEX['Red'], 'fontWeight': '700'},
                    {'if': {'filter_query': '{RAG} = Amber', 'column_id': 'RAG'}, 'color': RAG_HEX['Amber'], 'fontWeight': '700'},
                    {'if': {'filter_query': '{RAG} = Green', 'column_id': 'RAG'}, 'color': RAG_HEX['Green'], 'fontWeight': '700'},
                    {'if': {'filter_query': '{Severity} = Critical', 'column_id': 'Severity'}, 'color': SEV_HEX['Critical'], 'fontWeight': '700'},
                    {'if': {'filter_query': '{Severity} = High', 'column_id': 'Severity'}, 'color': SEV_HEX['High']},
                ],
                sort_action='native',
                filter_action='native',
                page_size=30,
            ),
        ])
    ])
