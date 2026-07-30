import dash
import os
import re
import numpy as np

from dash import dcc, html, Input, Output, callback, State, dash_table
from dash_iconify import DashIconify
import pandas as pd
import io

from dashboard.data_engine import load_data, run_dq_analysis, get_failing_records, build_aging_analysis, get_check_columns
from dashboard.core.config import RAG_THRESHOLDS
from dashboard.shared.ui import header_bar, card, section_header, HOUSE_HEX

from dashboard.tabs.exec_summary import render_summary
from dashboard.tabs.suppliers import render_tab as render_suppliers
from dashboard.tabs.customers import render_tab as render_customers
from dashboard.tabs.gl import render_tab as render_gl
from dashboard.tabs.assets import render_tab as render_assets
from dashboard.tabs.po import render_tab as render_po, _compute_metrics as _po_compute_metrics
from dashboard.tabs.pbf import render_tab as render_pbf
from dashboard.tabs.atamis import (
    render_tab as render_atamis,
    get_org_reliability_records as get_atamis_org_reliability_records,
    RELIABILITY_VERDICT_LABELS as ATAMIS_RELIABILITY_VERDICT_LABELS,
)

# Keep these in case they are needed for drill-downs or future features
from dashboard.tabs.explorer import render_explorer_layout, render_explorer_summary
from dashboard.tabs.findings import render_findings_log
from dashboard.tabs.aging import render_aging

# ═══════════════════════════════════════════════════════════════════════════════
# DATA INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

_active_tab = os.environ.get('DASHBOARD_TAB')  # None = load all tabs
if _active_tab:
    print(f"Tab filter active: loading '{_active_tab}' data only")

print("Loading data...")
frames = load_data(tab=_active_tab)
print("Running DQ analysis...")
dq_results = run_dq_analysis(frames, tab=_active_tab)
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
                dcc.Tab(label='Summary', value='exec-summary',
                        style={'background': 'transparent', 'border': 'none', 'color': '#64748B', 'padding': '18px 24px', 'fontSize': '14px', 'fontWeight': '600'},
                        selected_style={'background': 'transparent', 'border': 'none', 'borderBottom': '3px solid #006548', 'color': '#006548', 'padding': '18px 24px', 'fontSize': '14px', 'fontWeight': '700'}),
                dcc.Tab(label='GL', value='gl',
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
                dcc.Tab(label='POs', value='po',
                        style={'background': 'transparent', 'border': 'none', 'color': '#64748B', 'padding': '18px 24px', 'fontSize': '14px', 'fontWeight': '600'},
                        selected_style={'background': 'transparent', 'border': 'none', 'borderBottom': '3px solid #006548', 'color': '#006548', 'padding': '18px 24px', 'fontSize': '14px', 'fontWeight': '700'}),
                dcc.Tab(label='PBF', value='pbf',
                        style={'background': 'transparent', 'border': 'none', 'color': '#64748B', 'padding': '18px 24px', 'fontSize': '14px', 'fontWeight': '600'},
                        selected_style={'background': 'transparent', 'border': 'none', 'borderBottom': '3px solid #006548', 'color': '#006548', 'padding': '18px 24px', 'fontSize': '14px', 'fontWeight': '700'}),
                dcc.Tab(label='Atamis', value='atamis',
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

    # Tracks which modal-populating callback most recently filled modal-content,
    # and with what — the shared modal chrome's single Export button (below)
    # needs this to know what to export, since it has no other way to tell a
    # DQ-check drill-down apart from an Organisation Field Reliability cell
    # click or a PO leakage "View all" click.
    dcc.Store(id='modal-export-context'),

    # ── POPUP MODAL (Record Detail) ───────────────────────────────────────────
    html.Div(id='modal-overlay', style={
        'display': 'none', 'position': 'fixed', 'top': 0, 'left': 0,
        'width': '100%', 'height': '100%',
        'background': 'rgba(8, 4, 18, 0.75)', 'backdropFilter': 'blur(8px)',
        'zIndex': 1000, 'justifyContent': 'center', 'alignItems': 'center',
        'padding': '24px', 'boxSizing': 'border-box',
    }, children=[
        html.Div(style={
            'width': '100%', 'maxWidth': '1480px', 'maxHeight': 'calc(100vh - 48px)',
            'borderRadius': '16px',
            'boxShadow': '0 40px 80px -16px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.06)',
            'display': 'flex', 'flexDirection': 'column', 'overflow': 'hidden',
            'background': '#ffffff',
        }, children=[
            # Single dark header — the only dark element
            html.Div(style={
                'padding': '14px 24px', 'background': '#1e1528',
                'display': 'flex', 'justifyContent': 'space-between',
                'alignItems': 'center', 'flexShrink': '0',
                'borderBottom': '1px solid rgba(255,255,255,0.06)',
            }, children=[
                html.Div(style={
                    'display': 'flex', 'alignItems': 'center', 'gap': '10px', 'minWidth': 0,
                }, children=[
                    html.Span('DQ', style={
                        'background': 'rgba(255,255,255,0.08)',
                        'color': 'rgba(255,255,255,0.45)',
                        'fontSize': '9px', 'fontWeight': '800', 'letterSpacing': '0.15em',
                        'padding': '3px 8px', 'borderRadius': '4px',
                        'flexShrink': '0',
                    }),
                    html.Div(id='modal-title', style={
                        'display': 'flex', 'alignItems': 'center', 'gap': '8px',
                        'minWidth': 0, 'overflow': 'hidden',
                    }),
                ]),
                html.Div(style={
                    'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'flexShrink': '0',
                }, children=[
                    html.Button(style={
                        'display': 'flex', 'alignItems': 'center', 'gap': '6px',
                        'background': 'rgba(255,255,255,0.07)',
                        'color': 'rgba(255,255,255,0.55)',
                        'border': '1px solid rgba(255,255,255,0.12)',
                        'padding': '6px 14px', 'borderRadius': '7px',
                        'fontWeight': '600', 'cursor': 'pointer', 'fontSize': '12px',
                    }, id='btn-export-modal', n_clicks=0, children=[
                        DashIconify(icon='lucide:download', width=13, color='rgba(255,255,255,0.55)'),
                        'Export',
                    ]),
                    html.Button(style={
                        'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center',
                        'background': 'rgba(255,255,255,0.07)',
                        'color': 'rgba(255,255,255,0.55)',
                        'border': '1px solid rgba(255,255,255,0.12)',
                        'width': '30px', 'height': '30px', 'borderRadius': '7px',
                        'cursor': 'pointer', 'padding': '0',
                    }, id='btn-close-modal', n_clicks=0, children=[
                        DashIconify(icon='lucide:x', width=14, color='rgba(255,255,255,0.55)'),
                    ]),
                    dcc.Download(id="download-modal-csv"),
                ]),
            ]),
            # Scrollable body
            html.Div(id='modal-content', style={
                'overflowY': 'auto', 'flex': '1', 'background': '#ffffff',
            }),
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
    if master_tab not in ['suppliers', 'customers', 'exec-summary', 'gl', 'assets', 'po', 'pbf', 'atamis']:
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
    elif master_tab == 'po':
        filtered_dq = dq_results[dq_results['scope_id'] == 15]
        return render_po(filtered_dq, frames)
    elif master_tab == 'pbf':
        filtered_dq = dq_results[dq_results['scope_id'] == -1] # Adjust logic as needed later
        return render_pbf(filtered_dq, frames)
    elif master_tab == 'atamis':
        filtered_dq = dq_results[dq_results['scope_id'].isin([30, 31, 32, 33])]
        return render_atamis(filtered_dq, frames)

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
        module_dq = dq_results[dq_results['scope_id'].isin([11, 17, 12])]
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
    [Output('modal-overlay', 'style', allow_duplicate=True),
     Output('modal-title', 'children', allow_duplicate=True),
     Output('modal-content', 'children', allow_duplicate=True),
     Output('modal-export-context', 'data', allow_duplicate=True),
     Output({'type': 'dim-widget-chart', 'index': dash.ALL}, 'clickData')],
    Input('btn-close-modal', 'n_clicks'),
    State({'type': 'dim-widget-chart', 'index': dash.ALL}, 'clickData'),
    prevent_initial_call=True
)
def close_modal(n_clicks, chart_clicks):
    return {'display': 'none'}, "", "", None, [None] * len(chart_clicks)


@app.callback(
    [Output('modal-overlay', 'style'),
     Output('modal-title', 'children'),
     Output('modal-content', 'children'),
     Output('modal-export-context', 'data', allow_duplicate=True)],
    [Input({'type': 'dim-widget-chart', 'index': dash.ALL}, 'clickData'),
     Input({'type': 'dim-results-table', 'index': dash.ALL}, 'active_cell')],
    [State({'type': 'dim-results-table', 'index': dash.ALL}, 'derived_viewport_data')],
    prevent_initial_call=True
)
def handle_modal_logic(chart_clicks, table_cells, tables_data):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    trigger_id = ctx.triggered[0]['prop_id']

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
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    # ── RENDER CONTENT ──
    is_xhouse = False
    df = get_failing_records(check_id, house, frames)
    check_info = dq_results[(dq_results['check_id'] == check_id) & (dq_results['house'] == house)]

    if check_info.empty:
        return {'display': 'flex'}, f"Error: {check_id}", "Check metadata not found.", dash.no_update

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

    # Ensure the table only shows rows for the requested house.
    # get_failing_records may return rows for both houses if house filtering
    # behaves unexpectedly on the real data.
    if not is_xhouse and 'house' in df.columns:
        df = df[df['house'] == house]

    # ── COLOURS ──
    rag_color = {'Green': '#1a7a4a', 'Amber': '#d4820a', 'Red': '#c0392b'}.get(row.get('rag', 'Red'), '#c0392b')
    pass_rate = row.get('pass_rate', 0)
    # Use the pre-computed count from dq_results (same source as the charts)
    # rather than len(df) which can be inflated by dimension-split rows.
    failing   = int(row['failing'])
    assessed  = int(row['total'])

    # ── HELPERS ──
    def _divider():
        return html.Div(style={'height': '1px', 'background': '#f0edf8', 'margin': '20px 0'})

    def _section_title(text):
        return html.Div(text, style={
            'fontSize': '10px', 'fontWeight': '700', 'color': '#a090c0',
            'textTransform': 'uppercase', 'letterSpacing': '0.1em', 'marginBottom': '10px',
        })

    # ── LEFT SIDEBAR ──
    sev_colors_light = {'Critical': '#fef2f2', 'High': '#fff7ed', 'Medium': '#fefce8', 'Low': '#f5f3ff'}
    sev_colors_dark  = {'Critical': '#ef4444', 'High': '#f97316', 'Medium': '#eab308', 'Low': '#8b5cf6'}
    sev_bg    = sev_colors_light.get(row.get('severity', ''), '#f5f3ff')
    sev_color = sev_colors_dark.get(row.get('severity', ''), '#8b5cf6')

    def _stat_card(value, label, icon, value_color, icon_color=None, extra=None):
        return html.Div(style={
            'background': '#faf9fd', 'border': '1px solid #ede9f8',
            'borderRadius': '12px', 'padding': '16px 18px',
        }, children=[
            html.Div(value, style={
                'fontSize': '28px', 'fontWeight': '800', 'lineHeight': '1',
                'color': value_color, 'fontFamily': "'Inter', sans-serif",
                'letterSpacing': '-0.02em', 'marginBottom': '6px',
            }),
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '4px'}, children=[
                DashIconify(icon=icon, width=11, color=icon_color or '#a090c0'),
                html.Span(label, style={'fontSize': '10px', 'color': '#a090c0', 'fontWeight': '500'}),
            ]),
            *([extra] if extra else []),
        ])

    error_pct = (failing / assessed * 100) if assessed > 0 else 0
    thresholds = RAG_THRESHOLDS.get(row.get('severity', 'Medium'), (5, 15))

    left_sidebar = html.Div(style={
        'width': '380px', 'flexShrink': '0', 'padding': '20px 20px',
        'borderRight': '1px solid #f0edf8',
        'display': 'flex', 'flexDirection': 'column', 'gap': '12px',
    }, children=[
        # Dimension + severity inline
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '10px'}, children=[
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '4px'}, children=[
                DashIconify(icon='lucide:layers', width=11, color='#a090c0'),
                html.Span(row.get('dimension', '—').upper(), style={
                    'fontSize': '10px', 'fontWeight': '700', 'color': '#a090c0',
                    'letterSpacing': '0.05em',
                }),
            ]),
            html.Div(style={
                'width': '1px', 'height': '16px',
                'background': 'linear-gradient(to bottom, transparent, #CBD5E1, transparent)',
            }),
            html.Span('severity', style={
                'fontSize': '10px', 'fontWeight': '500', 'color': '#94A3B8', 'letterSpacing': '0.04em',
            }),
            html.Span(row.get('severity', '—'), style={
                'fontSize': '10px', 'fontWeight': '700', 'color': sev_color,
                'background': sev_bg, 'padding': '4px 12px',
                'borderRadius': '6px', 'border': f'1px solid {sev_color}30',
                'letterSpacing': '0.04em',
            }),
        ]),

        # ── Records bar card ──
        html.Div(style={
            'background': '#faf9fd', 'border': '1px solid #ede9f8',
            'borderRadius': '12px', 'padding': '14px 16px',
        }, children=[
            html.Div(style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'marginBottom': '8px'}, children=[
                html.Span(style={'fontSize': '10px', 'fontWeight': '700', 'color': '#a090c0', 'letterSpacing': '0.05em', 'textTransform': 'uppercase', 'display': 'flex', 'alignItems': 'center', 'gap': '4px'}, children=[
                    DashIconify(icon='lucide:bar-chart-2', width=11, color='#a090c0'),
                    html.Span('Records assessed'),
                ]),
                html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '6px'}, children=[
                    html.Span(f'{assessed:,} total', style={'fontSize': '10px', 'fontWeight': '600', 'color': '#94A3B8'}),
                    html.Span(row.get('rag', '—'), style={
                        'fontSize': '9px', 'fontWeight': '700', 'color': rag_color,
                        'background': rag_color + '18', 'padding': '2px 8px',
                        'borderRadius': '6px', 'border': f'1px solid {rag_color}40',
                    }),
                ]),
            ]),
            html.Div(style={
                'height': '28px', 'borderRadius': '6px',
                'background': '#E2E8F0', 'overflow': 'hidden',
            }, children=[
                html.Div(style={
                    'height': '100%',
                    'width': f'{error_pct:.1f}%',
                    'background': rag_color, 'borderRadius': '6px',
                    'minWidth': '2px' if failing > 0 else '0',
                }),
            ]),
            html.Div(style={
                'display': 'flex', 'justifyContent': 'space-between',
                'marginTop': '6px', 'paddingLeft': '2px', 'paddingRight': '2px',
            }, children=[
                html.Span(f'{failing:,} flagged', style={
                    'fontSize': '11px', 'fontWeight': '600', 'color': rag_color,
                }),
                html.Span(f'{error_pct:.1f}%', style={
                    'fontSize': '11px', 'fontWeight': '600', 'color': '#94A3B8',
                }),
            ]),
        ]),

        # ── RAG threshold card (full width) ──
        html.Div(style={
            'background': '#faf9fd', 'border': '1px solid #ede9f8',
            'borderRadius': '12px', 'padding': '14px 16px',
        }, children=[
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '4px', 'marginBottom': '10px'}, children=[
                DashIconify(icon='lucide:sliders', width=11, color='#a090c0'),
                html.Span('RAG Thresholds', style={'fontSize': '10px', 'color': '#a090c0', 'fontWeight': '700', 'letterSpacing': '0.05em', 'textTransform': 'uppercase'}),
            ]),
            html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '7px'}, children=[
                html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px'}, children=[
                    html.Span('Green', style={
                        'fontSize': '10px', 'fontWeight': '800', 'color': '#27AE60',
                        'background': '#27AE6018', 'padding': '2px 8px',
                        'borderRadius': '6px', 'border': '1px solid #27AE6040',
                        'minWidth': '48px', 'textAlign': 'center',
                    }),
                    html.Span(f'< {thresholds[0]}% flagged', style={'fontSize': '12px', 'color': '#64748B', 'fontWeight': '500'}),
                ]),
                html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px'}, children=[
                    html.Span('Amber', style={
                        'fontSize': '10px', 'fontWeight': '800', 'color': '#F39C12',
                        'background': '#F39C1218', 'padding': '2px 8px',
                        'borderRadius': '6px', 'border': '1px solid #F39C1240',
                        'minWidth': '48px', 'textAlign': 'center',
                    }),
                    html.Span(f'{thresholds[0]}–{thresholds[1]}% flagged', style={'fontSize': '12px', 'color': '#64748B', 'fontWeight': '500'}),
                ]),
                html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px'}, children=[
                    html.Span('Red', style={
                        'fontSize': '10px', 'fontWeight': '800', 'color': '#E74C3C',
                        'background': '#E74C3C18', 'padding': '2px 8px',
                        'borderRadius': '6px', 'border': '1px solid #E74C3C40',
                        'minWidth': '48px', 'textAlign': 'center',
                    }),
                    html.Span(f'> {thresholds[1]}% flagged', style={'fontSize': '12px', 'color': '#64748B', 'fontWeight': '500'}),
                ]),
            ]),
        ]),
    ])

    # ── RIGHT CONTENT ──
    right_content = html.Div(style={'flex': '1', 'padding': '20px 32px', 'paddingTop': '56px', 'minWidth': 0}, children=[

        # Why this matters — full width
        html.Div(style={
            'background': '#faf9fd', 'border': '1px solid #ede9f8',
            'borderRadius': '12px', 'padding': '14px 16px', 'marginBottom': '12px',
        }, children=[
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '4px', 'marginBottom': '10px'}, children=[
                DashIconify(icon='lucide:alert-circle', width=11, color='#a090c0'),
                html.Span('Why this matters', style={'fontSize': '10px', 'color': '#a090c0', 'fontWeight': '700', 'letterSpacing': '0.05em', 'textTransform': 'uppercase'}),
            ]),
            html.Div(row.get('intent', '—'), style={
                'fontSize': '14px', 'color': '#4a3d6b', 'fontWeight': '400',
                'lineHeight': '1.7',
            }),
        ]),

        # Rule definition + Critical fields — side by side outer cards, content-width
        html.Div(style={'display': 'flex', 'gap': '16px', 'alignItems': 'stretch'}, children=[
            html.Div(style={
                'background': '#faf9fd', 'border': '1px solid #ede9f8',
                'borderRadius': '12px', 'padding': '14px 16px',
                'display': 'flex', 'flexDirection': 'column',
                'width': 'fit-content',
            }, children=[
                html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '4px', 'marginBottom': '10px'}, children=[
                    DashIconify(icon='lucide:code', width=11, color='#a090c0'),
                    html.Span('Rule definition', style={'fontSize': '10px', 'color': '#a090c0', 'fontWeight': '700', 'letterSpacing': '0.05em', 'textTransform': 'uppercase'}),
                ]),
                html.Div(logic, style={
                    'fontFamily': "'Courier New', monospace", 'fontSize': '12px',
                    'background': '#ede8f5', 'color': '#4a3d6b',
                    'padding': '12px 16px', 'borderRadius': '8px',
                    'border': '1px solid #d8d0ee', 'lineHeight': '1.7',
                    'flex': '1',
                }),
            ]),
            html.Div(style={
                'background': '#faf9fd', 'border': '1px solid #ede9f8',
                'borderRadius': '12px', 'padding': '14px 16px',
                'display': 'flex', 'flexDirection': 'column',
                'width': 'fit-content',
            }, children=[
                html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '4px', 'marginBottom': '10px'}, children=[
                    DashIconify(icon='lucide:tag', width=11, color='#a090c0'),
                    html.Span('Critical fields', style={'fontSize': '10px', 'color': '#a090c0', 'fontWeight': '700', 'letterSpacing': '0.05em', 'textTransform': 'uppercase'}),
                ]),
                html.Div(style={
                    'display': 'flex', 'gap': '6px', 'flexWrap': 'wrap',
                    'background': '#ede8f5', 'border': '1px solid #d8d0ee',
                    'borderRadius': '8px', 'padding': '12px 16px', 'flex': '1',
                    'alignContent': 'flex-start',
                }, children=[
                    html.Span(c, style={
                        'fontSize': '12px', 'fontWeight': '400', 'color': '#4a3d6b',
                        'background': '#e6e0f4', 'padding': '4px 12px',
                        'borderRadius': '5px', 'border': '1px solid #cdc4e8',
                        'fontFamily': "'Courier New', monospace",
                    }) for c in base_cols
                ] if base_cols else [
                    html.Span('Automatic check', style={
                        'fontSize': '12px', 'color': '#a090c0', 'fontStyle': 'italic',
                    })
                ]),
            ]),
        ]),
    ])

    # ── TWO-PANEL ROW ──
    kpi_bar     = None   # removed — metrics now in sidebar
    tech_details = html.Div(style={
        'display': 'flex', 'borderBottom': '1px solid #f0edf8',
    }, children=[left_sidebar, right_content])

    # ── TABLE DATA PREPARATION ──
    prefixed_tables = ['ASSET_DEPRECIATION.', 'ASSET_MASTER.', 'ASSET_MASTER (TARGET).', 'ASSET_BALANCES.', 
                       'ASSET_GROUPS.', 'ASSET_TRANS_FLAGS.', 'SUPPLIER_MASTER.',
                       'AR_INVOICES.', 'CUSTOMER_MASTER.',
                       'AP_INVOICES.', 'AP_HISTORY.',
                       'GL_BALANCES.', 'GL_ACCOUNTS.', 'GL_TRANSACTIONS.', 'GL_DIMENSIONS.']
    is_prefixed = any(any(p in c for p in prefixed_tables) for c in df.columns)

    if not is_xhouse and not is_prefixed:
        key_fields = ['asset_id', 'apar_id', 'account', 'voucher_no', 'client', 'sequence_no', 'status', 'BRIDGE_Asset_Group']
        if table_name == 'apodetail':
            # Standard financial fields always shown for PO line checks, so the
            # reviewer can assess the full amount/receipt/match/invoice picture
            # regardless of which specific field triggered the check.
            key_fields = key_fields + ['amount', 'vow_amount', 'vow_val', 'arr_amount', 'arr_val', 'invoiced', 'unit_price']
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

    

    _dt_shared_style = dict(
        style_table={'overflowX': 'auto', 'border': 'none'},
        style_cell={
            'textAlign': 'left', 'padding': '10px 16px',
            'fontSize': '12px', 'fontFamily': "'Source Sans Pro', sans-serif",
            'minWidth': '100px', 'color': '#1a1523',
            'borderColor': '#f0edf8', 'borderLeft': 'none', 'borderRight': 'none',
        },
        style_header={
            'backgroundColor': '#1e1528', 'fontWeight': '600',
            'color': 'rgba(255,255,255,0.65)', 'textAlign': 'left',
            'fontSize': '11px', 'letterSpacing': '0.05em',
            'borderColor': '#2a1f3d', 'padding': '10px 16px',
            'textTransform': 'uppercase',
        },
        style_data={'borderColor': '#f0edf8'},
        sort_action='native',
        page_size=15,
    )

    if is_xhouse and not df.empty:
        show_cols = list(dict.fromkeys(
            ['client', 'apar_id', 'status', 'apar_name'] +
            [c for c in base_cols if c != 'apar_name']
        ))
        avail_cols = [c for c in show_cols if c in df.columns]
        dedup_cols = [c for c in base_cols if c in df.columns]
        hoc_df = df[df['house'] == 'HOC'][avail_cols].copy()
        hol_df = df[df['house'] == 'HOL'][avail_cols].copy()
        if dedup_cols:
            hoc_df = hoc_df.drop_duplicates(subset=dedup_cols)
            hol_df = hol_df.drop_duplicates(subset=dedup_cols)
            # Normalise key case-insensitively so "APPLE LTD" and "Apple Ltd" align
            def _norm_key(row):
                return tuple(v.strip().upper() if isinstance(v, str) else v for v in [row[c] for c in dedup_cols])
            hoc_key = hoc_df.apply(_norm_key, axis=1)
            hol_key = hol_df.apply(_norm_key, axis=1)
            all_keys = sorted(set(hoc_key) | set(hol_key))
            hoc_df = hoc_df.set_index(hoc_key).reindex(all_keys).reset_index(drop=True)
            hol_df = hol_df.set_index(hol_key).reindex(all_keys).reset_index(drop=True)
        hoc_df = hoc_df.fillna('—').reset_index(drop=True)
        hol_df = hol_df.fillna('—').reset_index(drop=True)
        xh_cols = [{'name': c.replace('_', ' ').title(), 'id': c} for c in hoc_df.columns]
        xh_style = [
            {'if': {'column_id': c}, 'backgroundColor': '#FEF2F2', 'color': '#991B1B', 'fontWeight': 'bold'}
            for c in base_cols if c in hoc_df.columns
        ] + [{'if': {'row_index': 'odd'}, 'backgroundColor': '#faf9fd'}]

        def _xh_table(hdf):
            return dash_table.DataTable(data=hdf.to_dict('records'), columns=xh_cols,
                                        style_data_conditional=xh_style,
                                        filter_action='native', **_dt_shared_style)

        table_body = html.Div(style={'padding': '12px 16px 16px', 'display': 'flex', 'gap': '16px'}, children=[
            html.Div(style={'flex': '1', 'minWidth': 0}, children=[
                html.Div('HOC', style={
                    'background': '#00703c', 'color': '#fff',
                    'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.1em',
                    'padding': '5px 12px', 'borderRadius': '4px 4px 0 0', 'display': 'inline-block',
                }),
                _xh_table(hoc_df),
            ]),
            html.Div(style={'flex': '1', 'minWidth': 0}, children=[
                html.Div('HOL', style={
                    'background': '#9b2335', 'color': '#fff',
                    'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.1em',
                    'padding': '5px 12px', 'borderRadius': '4px 4px 0 0', 'display': 'inline-block',
                }),
                _xh_table(hol_df),
            ]),
        ])
    else:
        table_body = html.Div(style={'padding': '0'}, children=[
            dash_table.DataTable(
                data=df.fillna('—').to_dict('records'),
                columns=dt_cols,
                merge_duplicate_headers=True,
                style_data_conditional=style_data_conditional + [
                    {'if': {'row_index': 'odd'}, 'backgroundColor': '#faf9fd'},
                ],
                filter_action='native',
                **_dt_shared_style,
            ),
        ])

    content = html.Div([
        tech_details,
        join_map,
        table_body,
    ])

    house_color = HOUSE_HEX.get(house, '#7c5cbf')

    modal_title = html.Div(style={
        'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'minWidth': 0,
    }, children=[
        html.Span(house, style={
            'background': house_color, 'color': '#fff',
            'fontSize': '9px', 'fontWeight': '800', 'letterSpacing': '0.12em',
            'padding': '3px 8px', 'borderRadius': '4px', 'flexShrink': '0',
        }),
        html.Span(check_id, style={
            'color': 'rgba(255,255,255,0.5)',
            'fontSize': '11px', 'fontWeight': '600',
            'fontFamily': "'Courier New', monospace", 'flexShrink': '0',
        }),
        html.Span('/', style={'color': 'rgba(255,255,255,0.2)', 'fontSize': '14px', 'flexShrink': '0'}),
        html.Span(row['description'], style={
            'fontSize': '13px', 'fontWeight': '500', 'color': 'rgba(255,255,255,0.85)',
            'overflow': 'hidden', 'textOverflow': 'ellipsis', 'whiteSpace': 'nowrap',
        }),
        html.Span(row.get('severity', ''), style={
            'background': sev_color + '25', 'color': sev_color,
            'fontSize': '9px', 'fontWeight': '700', 'letterSpacing': '0.08em',
            'padding': '3px 8px', 'borderRadius': '4px',
            'textTransform': 'uppercase', 'flexShrink': '0',
            'border': f'1px solid {sev_color}40',
        }),
    ])

    export_context = {'type': 'dq', 'check_id': check_id, 'house': house}
    return {'display': 'flex', 'zIndex': 1000, 'position': 'fixed', 'top': 0, 'left': 0, 'width': '100%', 'height': '100%', 'background': 'rgba(15, 23, 42, 0.6)', 'backdropFilter': 'blur(4px)', 'justifyContent': 'center', 'alignItems': 'center', 'padding': '20px', 'boxSizing': 'border-box'},            modal_title,            content,            export_context


@app.callback(
    [Output('modal-overlay', 'style', allow_duplicate=True),
     Output('modal-title', 'children', allow_duplicate=True),
     Output('modal-content', 'children', allow_duplicate=True),
     Output('modal-export-context', 'data', allow_duplicate=True)],
    Input({'type': 'atamis-org-rel-cell', 'org': dash.ALL, 'verdict': dash.ALL}, 'n_clicks'),
    prevent_initial_call=True,
)
def handle_atamis_org_reliability_click(n_clicks_list):
    """Drill-down for the Atamis tab's Organisation Field Reliability matrix
    (see dashboard/tabs/atamis.py). Reuses the same modal-overlay/title/content
    shell as the DQ drill-down (handle_modal_logic above) via allow_duplicate,
    but this isn't a DQ check — there's no severity/RAG/threshold data — so it
    renders a simpler content: just the actual contracts behind the clicked
    cell, tracing exactly which source(s) (Commitments supplier chain, HOL's
    GL Contract Number dimension) resolved each one and to what house.
    """
    if not any(n_clicks_list):
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    triggered = dash.ctx.triggered_id
    if not triggered:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    org = triggered['org']
    verdict = triggered['verdict']

    df = get_atamis_org_reliability_records(frames, org, verdict)
    if df.empty:
        content = html.Div('No records found for this combination.', style={
            'padding': '48px', 'textAlign': 'center', 'color': '#94a3b8', 'fontSize': '13px',
        })
    else:
        display_cols = [
            ('contract_ref', 'Contract Reference'),
            ('contract_title', 'Contract Title'),
            ('organisation', 'Organisation (raw)'),
            ('commitment_id', 'Matched Commitment Id'),
            ('commitment_supplier_id', 'Commitment Supplier ID'),
            ('commitment_supplier_name', 'Commitment Supplier Name'),
            ('commitment_house', 'Commitment House'),
            ('gl_dim_match', 'Matches HOL GL Contract Number'),
        ]
        avail = [(c, label) for c, label in display_cols if c in df.columns]
        table_df = df[[c for c, _ in avail]].copy()
        if 'gl_dim_match' in table_df.columns:
            table_df['gl_dim_match'] = table_df['gl_dim_match'].map({True: 'Yes', False: 'No'})
        table_df = table_df.fillna('—')

        content = html.Div(style={'padding': '0'}, children=[
            dash_table.DataTable(
                data=table_df.to_dict('records'),
                columns=[{'name': label, 'id': c} for c, label in avail],
                style_table={'overflowX': 'auto', 'border': 'none'},
                style_cell={
                    'textAlign': 'left', 'padding': '10px 16px',
                    'fontSize': '12px', 'fontFamily': "'Source Sans Pro', sans-serif",
                    'minWidth': '100px', 'color': '#1a1523',
                    'borderColor': '#f0edf8', 'borderLeft': 'none', 'borderRight': 'none',
                },
                style_header={
                    'backgroundColor': '#1e1528', 'fontWeight': '600',
                    'color': 'rgba(255,255,255,0.65)', 'textAlign': 'left',
                    'fontSize': '11px', 'letterSpacing': '0.05em',
                    'borderColor': '#2a1f3d', 'padding': '10px 16px',
                    'textTransform': 'uppercase',
                },
                style_data={'borderColor': '#f0edf8'},
                style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#faf9fd'}],
                filter_action='native',
                sort_action='native',
                page_size=15,
            ),
        ])

    verdict_label = ATAMIS_RELIABILITY_VERDICT_LABELS.get(verdict, verdict)
    org_color = HOUSE_HEX.get(org, '#7c5cbf')
    modal_title = html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'minWidth': 0}, children=[
        html.Span(org, style={
            'background': org_color, 'color': '#fff',
            'fontSize': '9px', 'fontWeight': '800', 'letterSpacing': '0.12em',
            'padding': '3px 8px', 'borderRadius': '4px', 'flexShrink': '0',
        }),
        html.Span('/', style={'color': 'rgba(255,255,255,0.2)', 'fontSize': '14px', 'flexShrink': '0'}),
        html.Span(f'Organisation says {org} — {verdict_label}', style={
            'fontSize': '13px', 'fontWeight': '500', 'color': 'rgba(255,255,255,0.85)',
            'overflow': 'hidden', 'textOverflow': 'ellipsis', 'whiteSpace': 'nowrap',
        }),
    ])

    modal_style = {
        'display': 'flex', 'zIndex': 1000, 'position': 'fixed', 'top': 0, 'left': 0,
        'width': '100%', 'height': '100%', 'background': 'rgba(15, 23, 42, 0.6)',
        'backdropFilter': 'blur(4px)', 'justifyContent': 'center', 'alignItems': 'center',
        'padding': '20px', 'boxSizing': 'border-box',
    }
    export_context = {'type': 'atamis_org_rel', 'org': org, 'verdict': verdict}
    return modal_style, modal_title, content, export_context


@app.callback(
    [Output('modal-overlay', 'style', allow_duplicate=True),
     Output('modal-title', 'children', allow_duplicate=True),
     Output('modal-content', 'children', allow_duplicate=True),
     Output('modal-export-context', 'data', allow_duplicate=True)],
    Input('btn-po-leakage-view-all', 'n_clicks'),
    prevent_initial_call=True,
)
def handle_po_leakage_view_all(n_clicks):
    """Full drill-down for the PO tab's 'Untagged Spend for Contracted
    Suppliers' card (see dashboard/tabs/po.py) — the card itself only
    previews the top 10 suppliers; this shows every (supplier, contract)
    row via the same modal shell as the DQ drill-down, reusing dash_table's
    own pagination/filter to make "everything" actually browsable rather
    than truncating in the card itself."""
    if not n_clicks:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    m = _po_compute_metrics(frames)
    detail = m.get('contract_leakage_detail', pd.DataFrame())

    if detail.empty:
        content = html.Div('No untagged spend found for contracted suppliers.', style={
            'padding': '48px', 'textAlign': 'center', 'color': '#94a3b8', 'fontSize': '13px',
        })
    else:
        display_cols = [
            ('display_name', 'Supplier'),
            ('contract_ref', 'Contract Ref'),
            ('total_award_value', 'Contract Award Value'),
            ('contract_tagged_spend', 'Tagged Spend (this contract)'),
            ('untagged_spend', "Supplier's Total Untagged Spend"),
            ('untagged_pct', 'Untagged %'),
        ]
        table_df = detail[[c for c, _ in display_cols]].copy()
        for col in ('total_award_value', 'contract_tagged_spend', 'untagged_spend'):
            table_df[col] = pd.to_numeric(table_df[col], errors='coerce').map(lambda v: f'£{v:,.0f}' if pd.notna(v) else '—')
        table_df['untagged_pct'] = pd.to_numeric(detail['untagged_pct'], errors='coerce').map(lambda v: f'{v:.0f}%' if pd.notna(v) else '—')
        table_df = table_df.fillna('—')

        content = html.Div(style={'padding': '0'}, children=[
            dash_table.DataTable(
                data=table_df.to_dict('records'),
                columns=[{'name': label, 'id': c} for c, label in display_cols],
                style_table={'overflowX': 'auto', 'border': 'none'},
                style_cell={
                    'textAlign': 'left', 'padding': '10px 16px',
                    'fontSize': '12px', 'fontFamily': "'Source Sans Pro', sans-serif",
                    'minWidth': '100px', 'color': '#1a1523',
                    'borderColor': '#f0edf8', 'borderLeft': 'none', 'borderRight': 'none',
                },
                style_header={
                    'backgroundColor': '#1e1528', 'fontWeight': '600',
                    'color': 'rgba(255,255,255,0.65)', 'textAlign': 'left',
                    'fontSize': '11px', 'letterSpacing': '0.05em',
                    'borderColor': '#2a1f3d', 'padding': '10px 16px',
                    'textTransform': 'uppercase',
                },
                style_data={'borderColor': '#f0edf8'},
                style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#faf9fd'}],
                filter_action='native',
                sort_action='native',
                page_size=20,
            ),
        ])

    supplier_count = m.get('contract_leakage_supplier_count', 0)
    total_untagged = m.get('contract_leakage_total_untagged', 0)
    modal_title = html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'minWidth': 0}, children=[
        html.Span(f'{supplier_count:,} suppliers', style={
            'background': '#0d9488', 'color': '#fff',
            'fontSize': '9px', 'fontWeight': '800', 'letterSpacing': '0.12em',
            'padding': '3px 8px', 'borderRadius': '4px', 'flexShrink': '0',
        }),
        html.Span('/', style={'color': 'rgba(255,255,255,0.2)', 'fontSize': '14px', 'flexShrink': '0'}),
        html.Span(f'Untagged Spend for Contracted Suppliers — £{total_untagged:,.0f} untagged in total', style={
            'fontSize': '13px', 'fontWeight': '500', 'color': 'rgba(255,255,255,0.85)',
            'overflow': 'hidden', 'textOverflow': 'ellipsis', 'whiteSpace': 'nowrap',
        }),
    ])

    modal_style = {
        'display': 'flex', 'zIndex': 1000, 'position': 'fixed', 'top': 0, 'left': 0,
        'width': '100%', 'height': '100%', 'background': 'rgba(15, 23, 42, 0.6)',
        'backdropFilter': 'blur(4px)', 'justifyContent': 'center', 'alignItems': 'center',
        'padding': '20px', 'boxSizing': 'border-box',
    }
    export_context = {'type': 'po_leakage'}
    return modal_style, modal_title, content, export_context


@app.callback(
    Output("download-modal-csv", "data"),
    Input("btn-export-modal", "n_clicks"),
    State('modal-export-context', 'data'),
    prevent_initial_call=True,
)
def export_modal_to_csv(n_clicks, export_context):
    """Exports whatever is currently shown in the shared modal — a DQ check
    drill-down, an Organisation Field Reliability cell, or the PO 'Untagged
    Spend' full list. The modal's single Export button is fixed chrome
    shared by all three (see modal-overlay in the layout), so it can't tell
    them apart on its own; each modal-populating callback stamps
    'modal-export-context' with what it just showed, and this reads that
    back rather than re-deriving it from chart/table click state (which only
    ever reflected the DQ case and silently did nothing for the other two —
    the bug the user reported)."""
    if not export_context:
        return None

    kind = export_context.get('type')

    if kind == 'dq':
        check_id = export_context.get('check_id')
        house = export_context.get('house')
        if not check_id or not house:
            return None
        df = get_failing_records(check_id, house, frames, for_export=True)
        check_row = dq_results[(dq_results['check_id'] == check_id) & (dq_results['house'] == house)]
        description = check_row.iloc[0]['description'] if not check_row.empty else check_id
        safe_desc = re.sub(r'[^\w\s\-]', '', description).strip().replace(' ', '_')
        filename = f"{house}_{safe_desc}.csv"
        return dcc.send_data_frame(df.to_csv, filename, index=False)

    if kind == 'atamis_org_rel':
        org = export_context.get('org')
        verdict = export_context.get('verdict')
        df = get_atamis_org_reliability_records(frames, org, verdict)
        if df.empty:
            return None
        safe_verdict = re.sub(r'[^\w\s\-]', '', str(verdict)).strip().replace(' ', '_')
        filename = f"Org_Reliability_{org}_{safe_verdict}.csv"
        return dcc.send_data_frame(df.to_csv, filename, index=False)

    if kind == 'po_leakage':
        m = _po_compute_metrics(frames)
        df = m.get('contract_leakage_detail', pd.DataFrame())
        if df.empty:
            return None
        return dcc.send_data_frame(df.to_csv, 'PO_Untagged_Spend_Contracted_Suppliers.csv', index=False)

    return None

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
    Output('aging-ap-graph', 'figure'),
    Input('aging-ap-chart-toggle', 'value'),
)
def update_aging_ap_chart(house_filter):
    from dashboard.tabs.aging import make_aging_chart
    return make_aging_chart(aging_results.get('AP', pd.DataFrame()), house_filter or 'Both')

@app.callback(
    Output('aging-ar-graph', 'figure'),
    Input('aging-ar-chart-toggle', 'value'),
)
def update_aging_ar_chart(house_filter):
    from dashboard.tabs.aging import make_aging_chart
    return make_aging_chart(aging_results.get('AR', pd.DataFrame()), house_filter or 'Both')

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
# FUZZY NAME SEARCH
# ═══════════════════════════════════════════════════════════════════════════════

@app.callback(
    Output('fuzzy-results-container', 'children'),
    Output('fuzzy-results-store', 'data'),
    Input('fuzzy-run-btn', 'n_clicks'),
    [State('fuzzy-house-select', 'value'),
     State('fuzzy-threshold', 'value')],
    prevent_initial_call=True,
)
def run_fuzzy_match(n_clicks, house, threshold):
    try:
        from rapidfuzz import fuzz as _fuzz, process as _rfprocess
    except ImportError:
        return html.Div(
            'rapidfuzz is not installed. Run: pip install rapidfuzz',
            style={'fontSize': '12px', 'color': '#991B1B', 'padding': '12px 0'},
        ), None

    df = frames.get('asuheader', pd.DataFrame())
    if df.empty:
        return html.Div('No supplier data loaded.', style={'fontSize': '12px', 'color': '#94A3B8'}), None

    h_df = df[(df['house'] == house) & (df['status'] != 'C')].copy()
    deduped = h_df.drop_duplicates(subset=['apar_id'])[['client', 'apar_id', 'apar_name']].copy().reset_index(drop=True)
    deduped['_norm'] = deduped['apar_name'].fillna('').str.strip().str.upper()

    pairs = []
    for _, group in deduped.groupby(deduped['_norm'].str[:1]):
        if len(group) < 2:
            continue
        idxs = group.index.tolist()
        names = group['_norm'].tolist()
        scores = _rfprocess.cdist(names, names, scorer=_fuzz.token_sort_ratio,
                                  score_cutoff=threshold, workers=-1)
        np.fill_diagonal(scores, 0)
        for ii in range(len(idxs)):
            for jj in range(ii + 1, len(idxs)):
                if scores[ii][jj] >= threshold:
                    a, b = deduped.loc[idxs[ii]], deduped.loc[idxs[jj]]
                    pairs.append({
                        'Supplier A — Client':  a['client'],
                        'Supplier A — ID':      a['apar_id'],
                        'Supplier A — Name':    a['apar_name'],
                        'Supplier B — Client':  b['client'],
                        'Supplier B — ID':      b['apar_id'],
                        'Supplier B — Name':    b['apar_name'],
                        'Score':                int(round(scores[ii][jj])),
                    })

    result_df = pd.DataFrame(pairs).sort_values('Score', ascending=False).reset_index(drop=True)
    result_df = result_df[result_df['Score'] < 100]

    if not pairs or result_df.empty:
        return html.Div(
            f'No near-duplicate names found in {house} at {threshold}% threshold.',
            style={'fontSize': '12px', 'color': '#64748B', 'padding': '12px 0'},
        ), None

    house_color = HOUSE_HEX.get(house, '#7c5cbf')

    return html.Div([
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '10px', 'marginBottom': '10px'}, children=[
            html.Span(house, style={
                'background': house_color, 'color': '#fff',
                'fontSize': '9px', 'fontWeight': '800', 'letterSpacing': '0.1em',
                'padding': '3px 8px', 'borderRadius': '4px',
            }),
            html.Span(
                f'{len(result_df)} matched pair{"s" if len(result_df) != 1 else ""} at {threshold}% threshold',
                style={'fontSize': '12px', 'color': '#64748B'},
            ),
            html.Button('Export to CSV', id='fuzzy-export-btn', n_clicks=0, style={
                'marginLeft': 'auto', 'background': 'none', 'border': '1px solid #CBD5E1',
                'borderRadius': '6px', 'padding': '5px 12px',
                'fontSize': '11px', 'fontWeight': '600', 'color': '#475569', 'cursor': 'pointer',
            }),
        ]),
        dash_table.DataTable(
            data=result_df.to_dict('records'),
            columns=[{'name': c, 'id': c} for c in result_df.columns],
            filter_action='native',
            sort_action='native',
            sort_by=[{'column_id': 'Score', 'direction': 'desc'}],
            page_size=25,
            style_table={'overflowX': 'auto', 'border': 'none'},
            style_cell={
                'fontFamily': 'Inter, sans-serif', 'fontSize': '12px',
                'padding': '8px 12px', 'border': 'none',
                'borderBottom': '1px solid #F1F5F9', 'textAlign': 'left',
            },
            style_header={
                'background': '#F8FAFC', 'fontWeight': '700',
                'fontSize': '11px', 'color': '#475569',
                'borderBottom': '2px solid #E2E8F0', 'border': 'none',
            },
            style_data_conditional=[
                {'if': {'column_id': 'Supplier A — Name'}, 'color': '#991B1B', 'fontWeight': '600'},
                {'if': {'column_id': 'Supplier B — Name'}, 'color': '#991B1B', 'fontWeight': '600'},
                {'if': {'column_id': 'Score'}, 'color': '#92400E', 'fontWeight': '700'},
                {'if': {'row_index': 'odd'}, 'backgroundColor': '#faf9fd'},
            ],
        ),
    ]), result_df.to_dict('records')


@app.callback(
    Output('fuzzy-download', 'data'),
    Input('fuzzy-export-btn', 'n_clicks'),
    State('fuzzy-results-store', 'data'),
    State('fuzzy-house-select', 'value'),
    prevent_initial_call=True,
)
def export_fuzzy_results(n_clicks, store_data, house):
    if not store_data:
        return dash.no_update
    df = pd.DataFrame(store_data)
    return dcc.send_data_frame(df.to_csv, f'{house}_fuzzy_name_matches.csv', index=False)


# ═══════════════════════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    app.run(debug=True, port=8050)
