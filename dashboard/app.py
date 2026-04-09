import dash

from dash import dcc, html, Input, Output, callback, State, dash_table
import pandas as pd
import io

from dashboard.data_engine import load_data, run_dq_analysis, get_failing_records, build_aging_analysis, get_check_columns
from dashboard.shared.ui import header_bar, card, section_header, HOUSE_HEX

from dashboard.tabs.exec_summary import render_summary
from dashboard.tabs.suppliers import render_tab as render_suppliers
from dashboard.tabs.customers import render_tab as render_customers
from dashboard.tabs.gl import render_tab as render_gl
from dashboard.tabs.assets import render_tab as render_assets
from dashboard.tabs.pbf import render_tab as render_pbf

# Keep these in case they are needed for drill-downs or future features
from dashboard.tabs.explorer import render_explorer_layout, render_explorer_summary
from dashboard.tabs.findings import render_findings_log
from dashboard.tabs.aging import render_aging

# ═══════════════════════════════════════════════════════════════════════════════
# DATA INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

print("Loading data...")
frames = load_data()
print("Running DQ analysis...")
dq_results = run_dq_analysis(frames)
print("Building aging analysis...")
aging_results = build_aging_analysis(frames)
check_col_map = get_check_columns()

# ═══════════════════════════════════════════════════════════════════════════════
# APP SETUP
# ═══════════════════════════════════════════════════════════════════════════════

external_stylesheets = [
    'https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap'
]

app = dash.Dash(__name__, title='Parliament DQA | Veran Performance',
                external_stylesheets=external_stylesheets,
                suppress_callback_exceptions=True)

app.layout = html.Div(style={
    'background': '#F4F7F9', 'minHeight': '100vh',
    'fontFamily': "'Poppins', sans-serif",
    'color': '#2C3E50',
}, children=[
    header_bar(),
    
    # ── MASTER NAVIGATION ─────────────────────────────────────────────────────
    html.Div(style={
        'background': 'white', 'borderBottom': '1px solid #E2E8F0', 'padding': '0 32px'
    }, children=[
        html.Div(style={'maxWidth': '1440px', 'margin': '0 auto'}, children=[
            dcc.Tabs(id='master-tabs', value='exec-summary', style={'height': '60px'}, children=[
                dcc.Tab(label='Executive summary', value='exec-summary',
                        style={'background': 'transparent', 'border': 'none', 'color': '#64748B', 'padding': '18px 24px', 'fontSize': '14px', 'fontWeight': '600'},
                        selected_style={'background': 'transparent', 'border': 'none', 'borderBottom': '3px solid #006548', 'color': '#006548', 'padding': '18px 24px', 'fontSize': '14px', 'fontWeight': '700'}),
                dcc.Tab(label='General Ledger', value='gl',
                        style={'background': 'transparent', 'border': 'none', 'color': '#64748B', 'padding': '18px 24px', 'fontSize': '14px', 'fontWeight': '600'},
                        selected_style={'background': 'transparent', 'border': 'none', 'borderBottom': '3px solid #006548', 'color': '#006548', 'padding': '18px 24px', 'fontSize': '14px', 'fontWeight': '700'}),
                dcc.Tab(label='Suppliers', value='suppliers',
                        style={'background': 'transparent', 'border': 'none', 'color': '#64748B', 'padding': '18px 24px', 'fontSize': '14px', 'fontWeight': '600'},
                        selected_style={'background': 'transparent', 'border': 'none', 'borderBottom': '3px solid #006548', 'color': '#006548', 'padding': '18px 24px', 'fontSize': '14px', 'fontWeight': '700'}),
                dcc.Tab(label='Customers', value='customers',
                        style={'background': 'transparent', 'border': 'none', 'color': '#64748B', 'padding': '18px 24px', 'fontSize': '14px', 'fontWeight': '600'},
                        selected_style={'background': 'transparent', 'border': 'none', 'borderBottom': '3px solid #006548', 'color': '#006548', 'padding': '18px 24px', 'fontSize': '14px', 'fontWeight': '700'}),
                dcc.Tab(label='Assets', value='assets',
                        style={'background': 'transparent', 'border': 'none', 'color': '#64748B', 'padding': '18px 24px', 'fontSize': '14px', 'fontWeight': '600'},
                        selected_style={'background': 'transparent', 'border': 'none', 'borderBottom': '3px solid #006548', 'color': '#006548', 'padding': '18px 24px', 'fontSize': '14px', 'fontWeight': '700'}),
                dcc.Tab(label='PBF', value='pbf',
                        style={'background': 'transparent', 'border': 'none', 'color': '#64748B', 'padding': '18px 24px', 'fontSize': '14px', 'fontWeight': '600'},
                        selected_style={'background': 'transparent', 'border': 'none', 'borderBottom': '3px solid #006548', 'color': '#006548', 'padding': '18px 24px', 'fontSize': '14px', 'fontWeight': '700'}),
            ]),
        ])
    ]),

    # ── SUB NAVIGATION & CONTENT ──────────────────────────────────────────────
    html.Div(style={'maxWidth': '1440px', 'margin': '0 auto', 'padding': '24px 32px'}, children=[
        html.Div(id='main-tab-content'),
    ]),

    # Hidden div to force load dash_table assets
    html.Div(
        dash_table.DataTable(
            id='hidden-table-for-assets',
            columns=[{"name": "i", "id": "i"}],
            data=[{"i": 1}]
        ), 
        style={'display': 'none'}
    ),

    # ── POPUP MODAL (Record Detail) ───────────────────────────────────────────
    html.Div(id='modal-overlay', style={
        'display': 'none', 'position': 'fixed', 'top': 0, 'left': 0, 'width': '100%', 'height': '100%',
        'background': 'rgba(15, 23, 42, 0.6)', 'backdropFilter': 'blur(4px)', 'zIndex': 1000,
        'justifyContent': 'center', 'alignItems': 'center', 'padding': '20px', 'boxSizing': 'border-box'
    }, children=[
        html.Div(style={
            'background': 'white', 'width': '100%', 'maxWidth': '1400px', 'maxHeight': 'calc(100vh - 40px)',
            'borderRadius': '12px', 'boxShadow': '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
            'display': 'flex', 'flexDirection': 'column', 'overflow': 'hidden'
        }, children=[
            # Modal Header
            html.Div(style={
                'padding': '20px 32px', 'borderBottom': '1px solid #E2E8F0', 'display': 'flex',
                'justifyContent': 'space-between', 'alignItems': 'center', 'background': '#F8FAFC'
            }, children=[
                html.Div([
                    html.Div("DETAILED RECORD INSPECTION", style={'fontSize': '10px', 'fontWeight': '800', 'color': '#64748B', 'letterSpacing': '1px'}),
                    html.Div(id='modal-title', style={'fontSize': '20px', 'fontWeight': '700', 'color': '#1E293B', 'display': 'flex', 'alignItems': 'center', 'gap': '12px'}),
                ]),
                html.Div(style={'display': 'flex', 'gap': '12px'}, children=[
                    html.Button('📥 Export to CSV', id='btn-export-modal', n_clicks=0, style={
                        'background': '#F1F5F9', 'color': '#475569', 'border': '1px solid #E2E8F0', 'padding': '8px 20px',
                        'borderRadius': '6px', 'fontWeight': '700', 'cursor': 'pointer', 'fontSize': '14px'
                    }),
                    html.Button('✕ Close', id='btn-close-modal', n_clicks=0, style={
                        'background': '#EF4444', 'color': 'white', 'border': 'none', 'padding': '8px 24px',
                        'borderRadius': '6px', 'fontWeight': '700', 'cursor': 'pointer', 'fontSize': '14px'
                    }),
                ]),
                dcc.Download(id="download-modal-csv"),
            ]),
            # Modal Body
            html.Div(id='modal-content', style={'padding': '32px', 'overflowY': 'auto', 'flex': '1'}),
        ])
    ])
])

# ═══════════════════════════════════════════════════════════════════════════════
# CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════════

@app.callback(
    Output('main-tab-content', 'children'),
    Input('master-tabs', 'value')
)
def render_tab_content(master_tab):
    if master_tab not in ['suppliers', 'customers', 'exec-summary', 'gl', 'assets', 'pbf']:
        return html.Div(style={'padding': '100px', 'textAlign': 'center', 'color': '#94A3B8'}, children=[
            html.Div(f"{master_tab.upper()} Module Data Not Loaded", style={'fontSize': '18px', 'fontWeight': '600'}),
            html.Div("Please select 'Executive summary', 'General Ledger', 'Suppliers', or 'Customers' to view current migration data.", style={'marginTop': '8px'})
        ])

    # Filter results for the selected module
    if master_tab == 'exec-summary':
        filtered_dq = dq_results # All data for executive summary
        return render_summary(filtered_dq, frames, master_tab)
    elif master_tab == 'gl':
        filtered_dq = dq_results[dq_results['scope_id'] >= 20]
        return render_gl(filtered_dq, frames)
    elif master_tab == 'suppliers':
        filtered_dq = dq_results[dq_results['scope_id'].isin([10, 16, 18])]
        return render_suppliers(filtered_dq, frames)
    elif master_tab == 'customers':
        filtered_dq = dq_results[dq_results['scope_id'].isin([11, 17, 12])]
        return render_customers(filtered_dq, frames)
    elif master_tab == 'assets':
        filtered_dq = dq_results[dq_results['scope_id'] == 19]
        return render_assets(filtered_dq, frames)
    elif master_tab == 'pbf':
        filtered_dq = dq_results[dq_results['scope_id'] == -1] # Adjust logic as needed later
        return render_pbf(filtered_dq, frames)

    return html.Div("Tab not found")

@app.callback(
    Output('summary-drill-down-container', 'children'),
    [Input('summary-dim-chart', 'clickData'),
     Input('summary-rag-chart', 'clickData')],
    [State('master-tabs', 'value')]
)
def drill_down_from_summary(dim_click, rag_click, master_tab):
    ctx = dash.callback_context
    if not ctx.triggered:
        return None
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # Filter base data by module
    if master_tab == 'exec-summary':
        module_dq = dq_results
    elif master_tab == 'gl':
        module_dq = dq_results[dq_results['scope_id'] >= 20]
    elif master_tab == 'suppliers':
        module_dq = dq_results[dq_results['scope_id'].isin([10, 16, 18])]
    elif master_tab == 'customers':
        module_dq = dq_results[dq_results['scope_id'].isin([11, 17, 19])]
    else:
        module_dq = dq_results

    title = ""
    subtitle = ""
    filtered_df = pd.DataFrame()

    if trigger_id == 'summary-dim-chart' and dim_click:
        dim_name = dim_click['points'][0]['label']
        filtered_df = module_dq[module_dq['dimension'] == dim_name]
        title = f"Dimension Detail: {dim_name}"
        subtitle = f"Showing all quality checks for the {dim_name} dimension within the {master_tab.upper()} module."
    
    elif trigger_id == 'summary-rag-chart' and rag_click:
        rag_status = rag_click['points'][0]['label']
        filtered_df = module_dq[module_dq['rag'] == rag_status]
        title = f"Health Detail: {rag_status} Status"
        subtitle = f"Showing all quality checks currently flagged as {rag_status}."

    if filtered_df.empty:
        return None

    # Render a detailed summary card
    from dashboard.shared.ui import RAG_HEX
    
    avg_error = filtered_df['error_rate'].mean()
    total_failing = int(filtered_df['failing'].sum())
    
    return card([
        html.Div(style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'marginBottom': '20px'}, children=[
            html.Div([
                html.Div(title.upper(), style={'fontSize': '18px', 'fontWeight': '800', 'color': '#1E293B', 'letterSpacing': '0.5px'}),
                html.Div(subtitle, style={'fontSize': '12px', 'color': '#64748B', 'marginTop': '4px'}),
            ]),
            html.Button('Close Detail', id='btn-close-summary-drill', n_clicks=0,
                        style={'background': '#F1F5F9', 'border': '1px solid #E2E8F0', 'padding': '6px 12px', 'borderRadius': '4px', 'fontSize': '11px', 'fontWeight': '700', 'cursor': 'pointer'})
        ]),
        
        # Mini Scorecard
        html.Div(style={'display': 'flex', 'gap': '16px', 'marginBottom': '24px'}, children=[
            html.Div([
                html.Div('AVG ERROR RATE', style={'fontSize': '9px', 'fontWeight': '700', 'color': '#64748B', 'letterSpacing': '1px'}),
                html.Div(f"{avg_error:.1f}%", style={'fontSize': '20px', 'fontWeight': '800', 'color': '#1E293B'})
            ], style={'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '6px', 'flex': '1', 'border': '1px solid #F1F5F9'}),
            html.Div([
                html.Div('FAILING RECORDS', style={'fontSize': '9px', 'fontWeight': '700', 'color': '#64748B', 'letterSpacing': '1px'}),
                html.Div(f"{total_failing:,}", style={'fontSize': '20px', 'fontWeight': '800', 'color': '#E74C3C'})
            ], style={'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '6px', 'flex': '1', 'border': '1px solid #F1F5F9'}),
            html.Div([
                html.Div('RULES APPLIED', style={'fontSize': '9px', 'fontWeight': '700', 'color': '#64748B', 'letterSpacing': '1px'}),
                html.Div(f"{len(filtered_df['check_id'].unique())}", style={'fontSize': '20px', 'fontWeight': '800', 'color': '#1E293B'})
            ], style={'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '6px', 'flex': '1', 'border': '1px solid #F1F5F9'}),
        ]),

        # Detailed Table
        dash_table.DataTable(
            columns=[
                {"name": "House", "id": "house"},
                {"name": "Check Description", "id": "description"},
                {"name": "Failing", "id": "failing"},
                {"name": "Total", "id": "total"},
                {"name": "Error %", "id": "error_rate"},
                {"name": "RAG", "id": "rag"}
            ],
            data=filtered_df.to_dict('records'),
            style_table={'overflowX': 'auto', 'minWidth': '100%'},
            style_cell={'textAlign': 'center', 'padding': '12px', 'fontSize': '12px', 'fontFamily': 'Poppins', 'minWidth': '160px', 'maxWidth': '300px'},
            style_header={'backgroundColor': '#F8FAFC', 'fontWeight': 'bold', 'color': '#64748B'},
            style_data_conditional=[
                {'if': {'column_id': 'rag', 'filter_query': '{rag} eq "Red"'}, 'color': '#E74C3C', 'fontWeight': 'bold'},
                {'if': {'column_id': 'rag', 'filter_query': '{rag} eq "Amber"'}, 'color': '#F39C12', 'fontWeight': 'bold'},
                {'if': {'column_id': 'rag', 'filter_query': '{rag} eq "Green"'}, 'color': '#006548', 'fontWeight': 'bold'}
            ],
            page_size=10
        ),
        html.Div(style={'marginTop': '15px', 'fontSize': '11px', 'color': '#94A3B8', 'fontStyle': 'italic'}, 
                 children="Tip: To inspect individual records, click the magnifying glass action button in the detailed table.")
    ], style={'border': '2px solid #006548', 'boxShadow': '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'})

@app.callback(
    Output('summary-drill-down-container', 'children', allow_duplicate=True),
    Input('btn-close-summary-drill', 'n_clicks'),
    prevent_initial_call=True
)
def close_summary_drill(n_clicks):
    return None

@app.callback(
    [Output('modal-overlay', 'style'),
     Output('modal-title', 'children'),
     Output('modal-content', 'children')],
    [Input({'type': 'dim-widget-chart', 'index': dash.ALL}, 'clickData'),
     Input({'type': 'dim-results-table', 'index': dash.ALL}, 'active_cell'),
     Input('btn-close-modal', 'n_clicks')],
    [State({'type': 'dim-results-table', 'index': dash.ALL}, 'derived_viewport_data'),
     State('modal-overlay', 'style')],
    prevent_initial_call=True
)
def handle_modal_logic(chart_clicks, table_cells, close_clicks, tables_data, current_style):
    ctx = dash.callback_context
    if not ctx.triggered:
        return current_style, "", ""
    
    trigger_id = ctx.triggered[0]['prop_id']
    
    # ── CLOSE MODAL ──
    if 'btn-close-modal' in trigger_id:
        return {'display': 'none'}, "", ""
    
    check_id = None
    house = None
    
    # ── CHART CLICK ──
    if 'dim-widget-chart' in trigger_id:
        # Use the specific triggered value to avoid 'memory' from other charts
        click_data = ctx.triggered[0]['value']
        if click_data:
            point = click_data['points'][0]
            if 'customdata' in point:
                # customdata is [check_id, house]
                check_id = point['customdata'][0]
                house = point['customdata'][1]
    
    # ── TABLE CLICK ──
    elif 'dim-results-table' in trigger_id:
        # Get the first active cell found in the list of triggered tables
        active_cell = next((c for c in table_cells if c), None)
        table_data = next((t for t in tables_data if t), None)
        
        if active_cell and table_data:
            row_idx = active_cell['row']
            if row_idx < len(table_data):
                row_data = table_data[row_idx]
                # Check IDs are kept as 'check_id' (hidden), House is renamed for display
                check_id = row_data.get('check_id')
                house = row_data.get('House') or row_data.get('house')

    if not check_id or not house:
        # Don't update if we don't have enough info
        return current_style, dash.no_update, dash.no_update

    # ── RENDER CONTENT ──
    df = get_failing_records(check_id, house, frames)
    check_info = dq_results[(dq_results['check_id'] == check_id) & (dq_results['house'] == house)]
    
    if check_info.empty:
        return {'display': 'flex'}, f"Error: {check_id}", "Check metadata not found."

    row = check_info.iloc[0]
    table_name = row['table']
    joined_table = row.get('joined_table')
    logic = row['technical_logic']
    base_cols = check_col_map.get(check_id, [])
    highlight_cols = [f"{table_name}.{c}" for c in base_cols]
    
    style_data_conditional = [
        {
            'if': {'column_id': c},
            'backgroundColor': '#FEF2F2',
            'color': '#991B1B',
            'fontWeight': 'bold'
        } for c in highlight_cols
    ]

    # ── METADATA ROW 1: KPIs ──
    kpi_bar = html.Div(style={'display': 'flex', 'gap': '24px', 'marginBottom': '24px'}, children=[
        html.Div([
            html.Div(style={'display': 'flex', 'alignItems': 'flex-start', 'gap': '12px'}, children=[
                html.Div(style={'width': '3px', 'height': '32px', 'background': '#64748B', 'borderRadius': '2px', 'marginTop': '2px'}),
                html.Div([
                    html.Div(f"{int(row['total']):,}", style={'fontSize': '24px', 'fontWeight': '800', 'color': '#1E293B', 'lineHeight': '1.1'}),
                    html.Div('RECORDS ASSESSED', style={'fontSize': '9px', 'fontWeight': '700', 'color': '#94A3B8', 'letterSpacing': '1px', 'marginTop': '2px'})
                ])
            ])
        ], style={'background': 'white', 'padding': '16px 24px', 'borderRadius': '8px', 'border': '1px solid #E2E8F0', 'flex': '1', 'boxShadow': '0 1px 2px rgba(0,0,0,0.05)'}),
        
        html.Div([
            html.Div(style={'display': 'flex', 'alignItems': 'flex-start', 'gap': '12px'}, children=[
                html.Div(style={'width': '3px', 'height': '32px', 'background': '#EF4444', 'borderRadius': '2px', 'marginTop': '2px'}),
                html.Div([
                    html.Div(f"{int(len(df)):,}", style={'fontSize': '24px', 'fontWeight': '800', 'color': '#B91C1C', 'lineHeight': '1.1'}),
                    html.Div('FAILING RECORDS', style={'fontSize': '9px', 'fontWeight': '700', 'color': '#94A3B8', 'letterSpacing': '1px', 'marginTop': '2px'})
                ])
            ])
        ], style={'background': 'white', 'padding': '16px 24px', 'borderRadius': '8px', 'border': '1px solid #E2E8F0', 'flex': '1', 'boxShadow': '0 1px 2px rgba(0,0,0,0.05)'}),
        
        html.Div([
            html.Div(style={'display': 'flex', 'alignItems': 'flex-start', 'gap': '12px'}, children=[
                html.Div(style={'width': '3px', 'height': '32px', 'background': '#F59E0B', 'borderRadius': '2px', 'marginTop': '2px'}),
                html.Div([
                    html.Div(f"{row['error_rate']:.1f}%", style={'fontSize': '24px', 'fontWeight': '800', 'color': '#92400E', 'lineHeight': '1.1'}),
                    html.Div('DATA QUALITY SCORE', style={'fontSize': '9px', 'fontWeight': '700', 'color': '#94A3B8', 'letterSpacing': '1px', 'marginTop': '2px'})
                ])
            ])
        ], style={'background': 'white', 'padding': '16px 24px', 'borderRadius': '8px', 'border': '1px solid #E2E8F0', 'flex': '1', 'boxShadow': '0 1px 2px rgba(0,0,0,0.05)'}),
    ])

    # ── METADATA ROW 2: ENHANCED RULE CONTEXT ──
    tech_details = html.Div(style={'display': 'flex', 'gap': '20px', 'marginBottom': '32px'}, children=[
        # Left: The 'What & Why'
        html.Div(style={
            'background': '#F8FAFC', 'padding': '24px', 'borderRadius': '12px', 
            'border': '1px solid #E2E8F0', 'flex': '1.5'
        }, children=[
            html.Div('PURPOSE', style={'fontSize': '10px', 'fontWeight': '800', 'color': '#64748B', 'letterSpacing': '1px', 'marginBottom': '12px'}),
            html.Div(row.get('intent', 'Purpose not articulated.'), style={
                'fontSize': '15px', 'color': '#1E293B', 'fontWeight': '600', 'lineHeight': '1.5', 'marginBottom': '20px'
            }),
            
            html.Div('RULE DEFINITION', style={'fontSize': '10px', 'fontWeight': '800', 'color': '#64748B', 'letterSpacing': '1px', 'marginBottom': '8px'}),
            html.Div(logic, style={
                'fontFamily': 'monospace', 'fontSize': '12px', 'background': '#F1F5F9', 
                'padding': '10px 14px', 'borderRadius': '6px', 'color': '#475569', 'border': '1px solid #E2E8F0'
            })
        ]),

        # Right: The 'How & Action'
        html.Div(style={
            'background': '#F1F5F9', 'padding': '24px', 'borderRadius': '12px', 
            'border': '1px solid #E2E8F0', 'flex': '1'
        }, children=[
            html.Div('CRITICAL FIELDS', style={'fontSize': '10px', 'fontWeight': '800', 'color': '#64748B', 'letterSpacing': '1px', 'marginBottom': '12px'}),
            html.Div(style={'display': 'flex', 'gap': '8px', 'flexWrap': 'wrap', 'marginBottom': '20px'}, children=[
                html.Span(c, style={
                    'fontSize': '11px', 'fontWeight': '700', 'color': '#475569', 'background': 'white', 
                    'padding': '4px 14px', 'borderRadius': '20px', 'border': '1px solid #E2E8F0'
                }) for c in base_cols
            ] if base_cols else [html.Div("Automatic Check", style={'fontSize': '11px', 'color': '#94A3B8'})]),

            html.Div('REMEDIATION ACTION', style={'fontSize': '10px', 'fontWeight': '800', 'color': '#92400E', 'letterSpacing': '1px', 'marginBottom': '8px'}),
            html.Div(row['remediation'], style={
                'fontSize': '13px', 'color': '#78350F', 'fontWeight': '600', 'lineHeight': '1.5',
                'background': '#FFFBEB', 'padding': '12px 16px', 'borderRadius': '8px', 'border': '1px solid #FEF3C7'
            })
        ]),
    ])

    # ── TABLE DATA PREPARATION ──
    prefixed_tables = ['ASSET_DEPRECIATION.', 'ASSET_MASTER.', 'ASSET_MASTER (TARGET).', 'ASSET_BALANCES.', 
                       'ASSET_GROUPS.', 'ASSET_TRANS_FLAGS.', 'SUPPLIER_MASTER.',
                       'AR_INVOICES.', 'CUSTOMER_MASTER.',
                       'AP_INVOICES.', 'AP_HISTORY.',
                       'GL_BALANCES.', 'GL_ACCOUNTS.', 'GL_TRANSACTIONS.', 'GL_DIMENSIONS.']
    is_prefixed = any(any(p in c for p in prefixed_tables) for c in df.columns)

    if not is_prefixed:
        key_fields = ['asset_id', 'apar_id', 'account', 'voucher_no', 'BRIDGE_Asset_Group']
        evidence_cols = []
        
        for c in df.columns:
            bare = c.split('.', 1)[-1] if '.' in c else c
            if any(bare == k for k in key_fields) or 'STANDARD_' in c or 'Ref_' in c:
                evidence_cols.append(c)
        
        for c in df.columns:
            if any(base in c for base in base_cols) and c not in evidence_cols:
                evidence_cols.append(c)
                
        if evidence_cols:
            df = df[evidence_cols]

    # ── TABLE HIGHLIGHTING & HEADERS ──
    style_data_conditional = []
    dt_cols = []
    
    # ── JOIN MAP HEADER (FOR CONTEXT) ──
    join_map = None
    if table_name == 'asset_depreciation' and check_id in ['DQ-AG-X03', 'DQ-AG-X04']:
        target = "Group Lifetime" if check_id == 'DQ-AG-X04' else "Depr Method"
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px', 
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex', 
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("Asset Depreciation [Asset ID]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Asset Master [Group Code]", style={'color': '#475569'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span(f"Asset Groups [{target}]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'asset_depreciation' and check_id == 'DQ-AD-K05':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px', 
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex', 
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("Asset Depreciation [Asset ID]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Asset Master [Org Amount]", style={'color': '#1E40AF'}),
        ])
    
    elif table_name == 'asset_master' and check_id == 'DQ-AG-X01':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("Asset Master [Asset Group]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Asset Groups [Asset Group]", style={'color': '#1E40AF'}),
        ])
    
    elif table_name == 'asset_balances' and check_id == 'DQ-AM-R01':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("Asset Balances [Asset ID]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Asset Master [Asset ID]", style={'color': '#1E40AF'}),
        ])
    
    elif table_name == 'asset_depreciation' and check_id == 'DQ-AM-R02':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("Asset Depreciation [Asset ID]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Asset Master [Asset ID]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'asset_depreciation' and check_id == 'DQ-AD-X01':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("Asset Depreciation [Asset ID]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Asset Master [Asset ID]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'asset_balances' and check_id == 'DQ-AM-R03':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("Asset Balances [Asset ID]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Asset Master [Status]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'asset_master' and check_id == 'DQ-AM-R04':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("Asset Master [parent_asset]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Asset Master [asset_id]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'asset_master' and check_id == 'DQ-AM-R05':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("Asset Master [apar_id]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Supplier Master [apar_id]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'asset_master' and check_id == 'DQ-AD-X02':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("Asset Master [Asset ID]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Asset Depreciation [Asset ID]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'asset_depreciation' and check_id == 'DQ-AD-X03':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("Asset Depreciation [cap_date_from]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Asset Master [cap_date_from]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'asset_depreciation' and check_id == 'DQ-AD-X05':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("Asset Depreciation [Asset ID / Book ID]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Asset Balances [Asset ID / Book ID]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'asset_balances' and check_id == 'DQ-AB-X01':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("Asset Balances [Asset ID]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Asset Master [Asset ID]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'asset_balances' and check_id == 'DQ-AB-X02':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("Asset Balances [Asset ID / Book ID]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Asset Depreciation [Asset ID / Book ID]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'asset_master' and check_id == 'DQ-AB-X03':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("Asset Master [Asset ID]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Asset Balances [Asset ID]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'asset_balances' and check_id == 'DQ-AB-X04':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("Asset Balances [NBV]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("GL Opening Balances [Fixed Assets]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'asset_trans_flags' and check_id == 'DQ-AF-X01':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("Asset Trans Flags [Asset ID]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Asset Master [Status]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'asset_trans_flags' and check_id == 'DQ-AF-X02':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("Asset Trans Flags [trans_date]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Asset Master [date_to]", style={'color': '#1E40AF'}),
        ])
    
    elif table_name == 'asset_master' and check_id == 'DQ-AM-C06':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("Asset Master [cap_date_from]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Asset Depreciation [cap_flag]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'acutrans' and check_id == 'AR_ORPHANED_TRANS':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("AR Invoices [apar_id]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Customer Master [apar_id]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'acutrans' and check_id == 'AR_TRANS_CUS_CLOSED':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("AR Invoices [apar_id]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Customer Master [apar_id, status]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'asutrans' and check_id == 'AP_ORPHANED_TRANS':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("AP Invoices [apar_id]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Supplier Master [apar_id]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'asutrans' and check_id == 'AP_TRANS_SUP_CLOSED':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("AP Invoices [apar_id]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Supplier Master [apar_id, status]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'asuhistr' and check_id == 'HIS_ORPHANED':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("AP History [apar_id]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("Supplier Master [apar_id]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'aglyearend' and check_id == 'GL_BAL_ORPHAN_ACC':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("GL Balances [account]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("GL Accounts [account]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'aglyearend' and check_id == 'GL_BAL_PL_NONZERO':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("GL Balances [account]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("GL Accounts [account, res_bal]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'agltransact' and check_id == 'GL_TRA_ORPHAN_DIM1':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("GL Transactions [dim_1]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("GL Dimensions [dim_value, status]", style={'color': '#1E40AF'}),
        ])

    elif table_name == 'agldimvalue' and check_id == 'GL_DIM_ORPHAN_REL':
        join_map = html.Div(style={
            'background': '#F8FAFC', 'padding': '12px 20px', 'borderRadius': '8px',
            'border': '1px solid #E2E8F0', 'marginBottom': '20px', 'display': 'flex',
            'alignItems': 'center', 'gap': '15px', 'fontSize': '12px', 'fontWeight': '600'
        }, children=[
            html.Div("JOIN PATH:", style={'color': '#64748B', 'fontSize': '10px', 'fontWeight': '800'}),
            html.Span("GL Dimensions [rel_value]", style={'color': '#991B1B'}),
            html.Span("➔", style={'color': '#CBD5E1'}),
            html.Span("GL Dimensions [dim_value]", style={'color': '#1E40AF'}),
        ])

    ref_cols_to_drop = [
        c for c in df.columns if 'Ref_' in c
        and df[c].isna().all()
    ]
    if ref_cols_to_drop:
        df = df.drop(columns=ref_cols_to_drop)

    # Reorder df columns so same-source columns are consecutive,
    # preserving the original group order (source table first, joined table second)
    if is_prefixed:
        def col_source_key(c):
            if '.' in c: return c.split('.', 1)[0]
            if 'Ref_' in c: return 'Ref_' + c[4:].split('_', 1)[0]
            return 'SYSTEM'
        seen = {}
        for i, c in enumerate(df.columns):
            key = col_source_key(c)
            if key not in seen:
                seen[key] = i
        df = df[sorted(df.columns, key=lambda c: (seen[col_source_key(c)], list(df.columns).index(c)))]

    for c in df.columns:
        source = "SYSTEM"
        name = c
        
        # Explicit Mapping for Asset Chain of Evidence
        if 'ASSET_DEPRECIATION.' in c:
            if check_id in ['DQ-AM-C06', 'DQ-AD-X02', 'DQ-AB-X02']:
                source = "ASSET DEPRECIATION (TARGET)"
            else:
                source = "ASSET DEPRECIATION"
            name = c.split('.', 1)[1].replace('_', ' ').title()
        elif 'ASSET_TRANS_FLAGS.' in c:
            source = "ASSET TRANS FLAGS"
            name = c.split('.', 1)[1].replace('_', ' ').title()
        elif 'GL_OPENING_BALANCES.' in c:
            source = "GL OPENING BALANCES (TARGET)"
            name = c.split('.', 1)[1].replace('_', ' ').title()
        elif 'ASSET_MASTER (TARGET).' in c:
            source = "ASSET MASTER (TARGET)"
            name = c.split('.', 1)[1].replace('_', ' ').title()
        elif 'ASSET_MASTER.' in c:
            if check_id in ['DQ-AG-X03', 'DQ-AG-X04']:
                source = "ASSET MASTER (BRIDGE)"
            elif check_id in ['DQ-AG-X01', 'DQ-AM-R05', 'DQ-AD-X02', 'DQ-AB-X03', 'DQ-AM-C06']:
                source = "ASSET MASTER"
            elif check_id in ['DQ-AD-K05', 'DQ-AD-X03', 'DQ-AF-X01', 'DQ-AF-X02','DQ-AM-R01', 'DQ-AM-R02', 'DQ-AM-R03', 'DQ-AM-C06','DQ-AD-X01', 'DQ-AB-X01']:
                source = "ASSET MASTER (TARGET)"
            elif check_id.startswith('DQ-AM-') or check_id.startswith('DQ-AD-') or check_id.startswith('DQ-AB-') or check_id.startswith('DQ-AF-') or check_id.startswith('DQ-AG-'):
                source = "ASSET MASTER"
            else:
                source = "ASSET MASTER (TARGET)"
            name = c.split('.', 1)[1].replace('_', ' ').title()
        elif 'ASSET_GROUPS.' in c:
            if check_id in ['DQ-AG-X01', 'DQ-AG-X03', 'DQ-AG-X04']:
                source = "ASSET GROUP (TARGET)"
            else:
                source = "ASSET GROUPS"
            name = "Group " + c.split('.', 1)[1].replace('_', ' ').title()
        elif 'ASSET_BALANCES.' in c:
            if check_id in ['DQ-AM-R01', 'DQ-AM-R03', 'DQ-AB-X01', 'DQ-AB-X02',
                            'DQ-AB-C01', 'DQ-AB-C02', 'DQ-AB-C03', 'DQ-AB-C04',
                            'DQ-AB-V01', 'DQ-AB-V02', 'DQ-AB-V03',
                            'DQ-AB-K01', 'DQ-AB-K02', 'DQ-AB-K03']:
                source = "ASSET BALANCES"
            else:
                source = "ASSET BALANCES (TARGET)"
            name = c.split('.', 1)[1].replace('_', ' ').title()
        elif 'SUPPLIER_MASTER.' in c:
            source = "SUPPLIER MASTER (TARGET)"
            name = c.split('.', 1)[1].replace('_', ' ').title()
        elif 'AR_INVOICES.' in c:
            source = "AR INVOICES"
            name = c.split('.', 1)[1].replace('_', ' ').title()
        elif 'CUSTOMER_MASTER.' in c:
            source = "CUSTOMER MASTER (TARGET)"
            name = c.split('.', 1)[1].replace('_', ' ').title()
        elif 'AP_INVOICES.' in c:
            source = "AP INVOICES"
            name = c.split('.', 1)[1].replace('_', ' ').title()
        elif 'AP_HISTORY.' in c:
            source = "AP HISTORY"
            name = c.split('.', 1)[1].replace('_', ' ').title()
        elif 'GL_BALANCES.' in c:
            source = "GL BALANCES"
            name = c.split('.', 1)[1].replace('_', ' ').title()
        elif 'GL_ACCOUNTS.' in c:
            source = "GL ACCOUNTS (TARGET)"
            name = c.split('.', 1)[1].replace('_', ' ').title()
        elif 'GL_TRANSACTIONS.' in c:
            source = "GL TRANSACTIONS"
            name = c.split('.', 1)[1].replace('_', ' ').title()
        elif 'GL_DIMENSIONS (TARGET).' in c:
            source = "GL DIMENSIONS (TARGET)"
            name = c.split('.', 1)[1].replace('_', ' ').title()
        elif 'GL_DIMENSIONS.' in c:
            if check_id == 'GL_TRA_ORPHAN_DIM1':
                source = "GL DIMENSIONS (TARGET)"
            else:
                source = "GL DIMENSIONS"
            name = c.split('.', 1)[1].replace('_', ' ').title()
        elif 'Ref_' in c:
            ref_start = c.index('Ref_')
            remainder = c[ref_start + 4:]
            parts = remainder.split('_', 1)
            source = parts[0].upper() + " (REFERENCE)" if parts else "REFERENCE"
            name = parts[1].replace('_', ' ').title() if len(parts) > 1 else remainder
        elif '.' in c:
            source, name = c.split('.', 1)
            source = source.replace('_', ' ').upper()
            name = name.replace('_', ' ').title()
            
        dt_cols.append({"name": [source, name], "id": c})

        # Apply Surgical Highlighting
        # 1. FAILING SOURCE (Red)
        # Matches: explicitly prefixed source columns, prefixed critical-field columns,
        # or plain (unprefixed) columns whose name exactly matches a critical field.
        if source in ("ASSET DEPRECIATION", "ASSET MASTER", "ASSET BALANCES", "ASSET TRANS FLAGS", "ASSET GROUPS", "AR INVOICES", "AP INVOICES", "AP HISTORY", "GL BALANCES", "GL TRANSACTIONS", "GL DIMENSIONS") or (any(base in c for base in base_cols) and source.lower().replace(' ', '_') == table_name.lower()) or (c in base_cols and source == "SYSTEM") or "REFERENCE" in source:
            style_data_conditional.append({
                'if': {'column_id': c}, 'backgroundColor': '#FEF2F2', 'color': '#991B1B', 'fontWeight': 'bold'
            })
        # 2. TARGET STANDARD (Blue)
        elif "TARGET" in source:
            style_data_conditional.append({
                'if': {'column_id': c}, 'backgroundColor': '#EFF6FF', 'color': '#1E40AF', 'fontWeight': 'bold'
            })
        # 3. BRIDGE LINK (Gray)
        elif "BRIDGE" in source:
            style_data_conditional.append({
                'if': {'column_id': c}, 'backgroundColor': '#F8FAFC', 'color': '#475569', 'fontWeight': '600'
            })

    
    content = html.Div([
        kpi_bar,
        tech_details,
        join_map,
        section_header('Chain of Evidence Inspection', 'Follow the join trail from left to right to validate the exception.'),
        
        dash_table.DataTable(
            data=df.fillna('—').to_dict('records'),
            columns=dt_cols,
            merge_duplicate_headers=True,
            style_table={'overflowX': 'auto'},
            style_cell={'textAlign': 'center', 'padding': '12px', 'fontSize': '12px', 'fontFamily': 'Poppins', 'minWidth': '160px'},
            style_header={'backgroundColor': '#F1F5F9', 'fontWeight': 'bold', 'color': '#475569', 'textAlign': 'center'},
            style_data_conditional=style_data_conditional,
            sort_action="native",
            filter_action="native",
            page_size=15
        )
    ])

    house_color = HOUSE_HEX.get(house, '#64748B')
    modal_title = html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '12px'}, children=[
        html.Div(house, style={
            'background': house_color, 'color': 'white', 'fontSize': '11px', 'fontWeight': '800',
            'padding': '4px 10px', 'borderRadius': '4px', 'letterSpacing': '0.5px'
        }),
        html.Div(f"{check_id}: {row['description']}", style={'fontSize': '20px', 'fontWeight': '700', 'color': '#1E293B'})
    ])

    return {'display': 'flex', 'zIndex': 1000, 'position': 'fixed', 'top': 0, 'left': 0, 'width': '100%', 'height': '100%', 'background': 'rgba(15, 23, 42, 0.6)', 'backdropFilter': 'blur(4px)', 'justifyContent': 'center', 'alignItems': 'center', 'padding': '20px', 'boxSizing': 'border-box'},            modal_title,            content

@app.callback(
    Output("download-modal-csv", "data"),
    Input("btn-export-modal", "n_clicks"),
    [State({'type': 'dim-widget-chart', 'index': dash.ALL}, 'clickData'),
     State({'type': 'dim-results-table', 'index': dash.ALL}, 'active_cell'),
     State({'type': 'dim-results-table', 'index': dash.ALL}, 'derived_viewport_data')],
    prevent_initial_call=True,
)
def export_modal_to_csv(n_clicks, chart_clicks, table_cells, tables_data):
    ctx = dash.callback_context
    if not ctx.triggered: return None
    
    check_id = None
    house = None
    
    for click in chart_clicks:
        if click:
            point = click['points'][0]
            if 'customdata' in point:
                check_id = point['customdata'][0]
                house = point['customdata'][1]
                break
    
    if not check_id:
        active_cell = next((c for c in table_cells if c), None)
        table_data = next((t for t in tables_data if t), None)
        if active_cell and table_data:
            row_idx = active_cell['row']
            if row_idx < len(table_data):
                check_id = table_data[row_idx].get('check_id')
                house = table_data[row_idx].get('House') or table_data[row_idx].get('house')

    if not check_id or not house: return None
    
    df = get_failing_records(check_id, house, frames, base_cols)
    return dcc.send_data_frame(df.to_csv, f"DQ_Failing_Records_{check_id}_{house}.csv", index=False)

# --- Explorer Callbacks ---

@app.callback(
    Output("download-dim-drill-csv", "data"),
    Input("btn-export-dim-drill", "n_clicks"),
    [State({'type': 'dim-results-table', 'index': dash.ALL}, 'active_cell'),
     State({'type': 'dim-results-table', 'index': dash.ALL}, 'derived_viewport_data')],
    prevent_initial_call=True,
)
def export_dim_drill(n_clicks, table_cells, tables_data):
    active_cell = next((c for c in table_cells if c), None)
    table_data = next((t for t in tables_data if t), None)
    
    if not active_cell or not table_data: return None
    row_idx = active_cell['row']
    row_data = table_data[row_idx]
    df = get_failing_records(row_data['check_id'], row_data['house'], frames)
    return dcc.send_data_frame(df.to_csv, f"DQ_Inspection_{row_data['check_id']}_{row_data['house']}.csv", index=False)

@app.callback(
    [Output('explorer-table', 'data'),
     Output('explorer-table', 'columns'),
     Output('explorer-result-summary', 'children')],
    [Input('explorer-check-id', 'value'),
     Input('explorer-house', 'value')]
)
def update_explorer_table(check_id, house):
    if not check_id or not house:
        return [], [], ""
    
    df = get_failing_records(check_id, house, frames)
    check_info = dq_results[(dq_results['check_id'] == check_id) & (dq_results['house'] == house)]
    summary = render_explorer_summary(check_info)
    
    if df.empty:
        return [], [], summary
        
    cols = [{'name': c, 'id': c} for c in df.columns]
    data = df.to_dict('records')
    return data, cols, summary

@app.callback(
    Output("download-explorer-csv", "data"),
    Input("btn-export-explorer", "n_clicks"),
    [State('explorer-check-id', 'value'),
     State('explorer-house', 'value')],
    prevent_initial_call=True,
)
def export_explorer(n_clicks, check_id, house):
    df = get_failing_records(check_id, house, frames)
    return dcc.send_data_frame(df.to_csv, f"DQ_Failing_Records_{check_id}_{house}.csv", index=False)

# --- Findings Log Callbacks ---

@app.callback(
    Output("download-all-csv", "data"),
    Input("btn-export-all", "n_clicks"),
    prevent_initial_call=True,
)
def export_all_checks(n_clicks):
    return dcc.send_data_frame(dq_results.to_csv, "Parliament_DQA_Findings_Log.csv", index=False)

# --- Aging Callbacks ---

@app.callback(
    [Output('aging-ap-table', 'data'),
     Output('aging-ap-table', 'columns')],
    [Input('aging-ap-house', 'value'),
     Input('aging-ap-bucket', 'value')]
)
def update_aging_ap_table(house, bucket):
    raw = aging_results.get('AP_raw', pd.DataFrame())
    if raw.empty: return [], []
    
    df = raw[(raw['house'] == house) & (raw['aging_bucket'] == bucket)]
    cols_to_show = ['apar_id', 'voucher_no', 'voucher_type', 'trans_date', 'due_date', 'rest_amount', 'currency', 'description']
    df = df[cols_to_show]
    
    return df.to_dict('records'), [{'name': c, 'id': c} for c in df.columns]

@app.callback(
    [Output('aging-ar-table', 'data'),
     Output('aging-ar-table', 'columns')],
    [Input('aging-ar-house', 'value'),
     Input('aging-ar-bucket', 'value')]
)
def update_aging_ar_table(house, bucket):
    raw = aging_results.get('AR_raw', pd.DataFrame())
    if raw.empty: return [], []
    
    df = raw[(raw['house'] == house) & (raw['aging_bucket'] == bucket)]
    cols_to_show = ['apar_id', 'voucher_no', 'voucher_type', 'trans_date', 'due_date', 'rest_amount', 'currency', 'description']
    df = df[cols_to_show]
    
    return df.to_dict('records'), [{'name': c, 'id': c} for c in df.columns]

# ═══════════════════════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    app.run(debug=True, port=8050)
