import re

import dash
from dash import dcc, html, Input, Output, State, dash_table
from dash_iconify import DashIconify
import pandas as pd

from hr_dashboard.data_engine import load_data, run_dq_analysis, get_failing_records, get_check_columns
from hr_dashboard.core.config import RAG_THRESHOLDS, Scope
from hr_dashboard.shared.ui import header_bar

from hr_dashboard.tabs.employee import render_tab as render_employee
from hr_dashboard.tabs.payroll import render_tab as render_payroll

# ═══════════════════════════════════════════════════════════════════════════════
# DATA INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

print("Loading HR/Payroll dummy data...")
frames = load_data()
print("Running DQ analysis...")
dq_results = run_dq_analysis(frames)
check_col_map = get_check_columns()

# ═══════════════════════════════════════════════════════════════════════════════
# APP SETUP
# ═══════════════════════════════════════════════════════════════════════════════

external_stylesheets = [
    'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap'
]

app = dash.Dash(__name__, title='Royal Mail HR & Payroll DQA | Veran Performance',
                external_stylesheets=external_stylesheets,
                suppress_callback_exceptions=True)

_TAB_STYLE = {'background': 'transparent', 'border': 'none', 'color': '#64748B', 'padding': '18px 24px', 'fontSize': '14px', 'fontWeight': '600'}
_TAB_SELECTED = {'background': 'transparent', 'border': 'none', 'borderBottom': '3px solid #CC092F', 'color': '#CC092F', 'padding': '18px 24px', 'fontSize': '14px', 'fontWeight': '700'}

# Dash replaces the entire 'style' dict on every Output update — it does not
# merge. The modal-overlay's fixed positioning/centering/backdrop only exist
# in its initial layout style, so every callback that opens the modal must
# re-assert the full style (not just {'display': 'flex'}), or the div falls
# back into normal page flow and renders inline below whatever was clicked.
_MODAL_OPEN_STYLE = {
    'display': 'flex', 'position': 'fixed', 'top': 0, 'left': 0,
    'width': '100%', 'height': '100%',
    'background': 'rgba(8, 4, 4, 0.75)', 'backdropFilter': 'blur(8px)',
    'zIndex': 1000, 'justifyContent': 'center', 'alignItems': 'center',
    'padding': '24px', 'boxSizing': 'border-box',
}
_MODAL_CLOSED_STYLE = {**_MODAL_OPEN_STYLE, 'display': 'none'}

app.layout = html.Div(style={
    'background': '#F4F7F9', 'minHeight': '100vh',
    'fontFamily': "'Inter', sans-serif",
    'color': '#1a1a1a',
}, children=[
    header_bar(),

    html.Div(style={
        'background': 'white', 'borderBottom': '1px solid #E2E8F0', 'padding': '0 32px'
    }, children=[
        html.Div(style={'maxWidth': '1440px', 'margin': '0 auto'}, children=[
            dcc.Tabs(id='master-tabs', value='employee', style={'height': '60px'}, children=[
                dcc.Tab(label='Employee Master', value='employee', style=_TAB_STYLE, selected_style=_TAB_SELECTED),
                dcc.Tab(label='Payroll', value='payroll', style=_TAB_STYLE, selected_style=_TAB_SELECTED),
            ]),
        ])
    ]),

    html.Div(style={'maxWidth': '1440px', 'margin': '0 auto', 'padding': '24px 32px'}, children=[
        html.Div(id='main-tab-content'),
    ]),

    html.Div(
        dash_table.DataTable(
            id='hidden-table-for-assets',
            columns=[{"name": "i", "id": "i"}],
            data=[{"i": 1}]
        ),
        style={'display': 'none'}
    ),

    # ── POPUP MODAL (Record Detail) ───────────────────────────────────────────
    html.Div(id='modal-overlay', style=_MODAL_CLOSED_STYLE, children=[
        html.Div(style={
            'width': '100%', 'maxWidth': '1480px', 'maxHeight': 'calc(100vh - 48px)',
            'borderRadius': '16px',
            'boxShadow': '0 40px 80px -16px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.06)',
            'display': 'flex', 'flexDirection': 'column', 'overflow': 'hidden',
            'background': '#ffffff',
        }, children=[
            html.Div(style={
                'padding': '14px 24px', 'background': '#1a1a1a',
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
                    dcc.Download(id='download-modal-csv'),
                ]),
            ]),
            html.Div(id='modal-content', style={
                'overflowY': 'auto', 'flex': '1', 'background': '#ffffff',
            }),
        ])
    ])
])

# ═══════════════════════════════════════════════════════════════════════════════
# CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════════

_SCOPE_MAP = {
    'employee': [int(Scope.EMPLOYEE)],
    'payroll':  [int(Scope.PAYROLL)],
}


@app.callback(
    Output('main-tab-content', 'children'),
    Input('master-tabs', 'value')
)
def render_tab_content(master_tab):
    scope_ids = _SCOPE_MAP.get(master_tab)
    if scope_ids is None:
        return html.Div("Tab not found")

    filtered_dq = dq_results[dq_results['scope_id'].isin(scope_ids)]
    if master_tab == 'employee':
        return render_employee(filtered_dq, frames)
    return render_payroll(filtered_dq, frames)


@app.callback(
    [Output('modal-overlay', 'style', allow_duplicate=True),
     Output('modal-title', 'children', allow_duplicate=True),
     Output('modal-content', 'children', allow_duplicate=True),
     Output({'type': 'dim-widget-chart', 'index': dash.ALL}, 'clickData')],
    Input('btn-close-modal', 'n_clicks'),
    State({'type': 'dim-widget-chart', 'index': dash.ALL}, 'clickData'),
    prevent_initial_call=True
)
def close_modal(n_clicks, chart_clicks):
    return _MODAL_CLOSED_STYLE, "", "", [None] * len(chart_clicks)


@app.callback(
    [Output('modal-overlay', 'style'),
     Output('modal-title', 'children'),
     Output('modal-content', 'children')],
    Input({'type': 'dim-widget-chart', 'index': dash.ALL}, 'clickData'),
    prevent_initial_call=True
)
def handle_modal_logic(chart_clicks):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update, dash.no_update

    click_data = ctx.triggered[0]['value']
    if not click_data:
        return dash.no_update, dash.no_update, dash.no_update

    point = click_data['points'][0]
    if 'customdata' not in point:
        return dash.no_update, dash.no_update, dash.no_update

    check_id = point['customdata'][0]
    return _build_modal_for_check(check_id)


def _build_modal_for_check(check_id):
    df = get_failing_records(check_id, frames)
    check_info = dq_results[dq_results['check_id'] == check_id]
    if check_info.empty:
        return _MODAL_OPEN_STYLE, f"Error: {check_id}", "Check metadata not found."

    row = check_info.iloc[0]
    base_cols = check_col_map.get(check_id, [])
    logic = row['technical_logic']

    rag_color = {'Green': '#1a7a4a', 'Amber': '#d4820a', 'Red': '#c0392b'}.get(row.get('rag', 'Red'), '#c0392b')
    failing = int(row['failing'])
    assessed = int(row['total'])
    error_pct = (failing / assessed * 100) if assessed > 0 else 0
    thresholds = RAG_THRESHOLDS.get(row.get('severity', 'Medium'), (5, 15))

    sev_colors_light = {'Critical': '#fef2f2', 'High': '#fff7ed', 'Medium': '#fefce8', 'Low': '#f5f3ff'}
    sev_colors_dark = {'Critical': '#ef4444', 'High': '#f97316', 'Medium': '#eab308', 'Low': '#8b5cf6'}
    sev_bg = sev_colors_light.get(row.get('severity', ''), '#f5f3ff')
    sev_color = sev_colors_dark.get(row.get('severity', ''), '#8b5cf6')

    left_sidebar = html.Div(style={
        'width': '380px', 'flexShrink': '0', 'padding': '20px 20px',
        'borderRight': '1px solid #f0edf8',
        'display': 'flex', 'flexDirection': 'column', 'gap': '12px',
    }, children=[
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '10px'}, children=[
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '4px'}, children=[
                DashIconify(icon='lucide:layers', width=11, color='#a090c0'),
                html.Span(row.get('dimension', '—').upper(), style={
                    'fontSize': '10px', 'fontWeight': '700', 'color': '#a090c0', 'letterSpacing': '0.05em',
                }),
            ]),
            html.Div(style={'width': '1px', 'height': '16px', 'background': 'linear-gradient(to bottom, transparent, #CBD5E1, transparent)'}),
            html.Span('severity', style={'fontSize': '10px', 'fontWeight': '500', 'color': '#94A3B8', 'letterSpacing': '0.04em'}),
            html.Span(row.get('severity', '—'), style={
                'fontSize': '10px', 'fontWeight': '700', 'color': sev_color,
                'background': sev_bg, 'padding': '4px 12px', 'borderRadius': '6px',
                'border': f'1px solid {sev_color}30', 'letterSpacing': '0.04em',
            }),
        ]),
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
                        'background': rag_color + '18', 'padding': '2px 8px', 'borderRadius': '6px',
                        'border': f'1px solid {rag_color}40',
                    }),
                ]),
            ]),
            html.Div(style={'height': '28px', 'borderRadius': '6px', 'background': '#E2E8F0', 'overflow': 'hidden'}, children=[
                html.Div(style={
                    'height': '100%', 'width': f'{error_pct:.1f}%',
                    'background': rag_color, 'borderRadius': '6px',
                    'minWidth': '2px' if failing > 0 else '0',
                }),
            ]),
            html.Div(style={'display': 'flex', 'justifyContent': 'space-between', 'marginTop': '6px', 'paddingLeft': '2px', 'paddingRight': '2px'}, children=[
                html.Span(f'{failing:,} flagged', style={'fontSize': '11px', 'fontWeight': '600', 'color': rag_color}),
                html.Span(f'{error_pct:.1f}%', style={'fontSize': '11px', 'fontWeight': '600', 'color': '#94A3B8'}),
            ]),
        ]),
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
                    html.Span('Green', style={'fontSize': '10px', 'fontWeight': '800', 'color': '#27AE60', 'background': '#27AE6018', 'padding': '2px 8px', 'borderRadius': '6px', 'border': '1px solid #27AE6040', 'minWidth': '48px', 'textAlign': 'center'}),
                    html.Span(f'< {thresholds[0]}% flagged', style={'fontSize': '12px', 'color': '#64748B', 'fontWeight': '500'}),
                ]),
                html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px'}, children=[
                    html.Span('Amber', style={'fontSize': '10px', 'fontWeight': '800', 'color': '#F39C12', 'background': '#F39C1218', 'padding': '2px 8px', 'borderRadius': '6px', 'border': '1px solid #F39C1240', 'minWidth': '48px', 'textAlign': 'center'}),
                    html.Span(f'{thresholds[0]}–{thresholds[1]}% flagged', style={'fontSize': '12px', 'color': '#64748B', 'fontWeight': '500'}),
                ]),
                html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px'}, children=[
                    html.Span('Red', style={'fontSize': '10px', 'fontWeight': '800', 'color': '#E74C3C', 'background': '#E74C3C18', 'padding': '2px 8px', 'borderRadius': '6px', 'border': '1px solid #E74C3C40', 'minWidth': '48px', 'textAlign': 'center'}),
                    html.Span(f'> {thresholds[1]}% flagged', style={'fontSize': '12px', 'color': '#64748B', 'fontWeight': '500'}),
                ]),
            ]),
        ]),
    ])

    right_content = html.Div(style={'flex': '1', 'padding': '20px 32px', 'paddingTop': '56px', 'minWidth': 0}, children=[
        html.Div(style={
            'background': '#faf9fd', 'border': '1px solid #ede9f8',
            'borderRadius': '12px', 'padding': '14px 16px', 'marginBottom': '12px',
        }, children=[
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '4px', 'marginBottom': '10px'}, children=[
                DashIconify(icon='lucide:alert-circle', width=11, color='#a090c0'),
                html.Span('Why this matters', style={'fontSize': '10px', 'color': '#a090c0', 'fontWeight': '700', 'letterSpacing': '0.05em', 'textTransform': 'uppercase'}),
            ]),
            html.Div(row.get('intent', '—'), style={'fontSize': '14px', 'color': '#4a3d6b', 'fontWeight': '400', 'lineHeight': '1.7'}),
        ]),
        html.Div(style={'display': 'flex', 'gap': '16px', 'alignItems': 'stretch'}, children=[
            html.Div(style={
                'background': '#faf9fd', 'border': '1px solid #ede9f8', 'borderRadius': '12px',
                'padding': '14px 16px', 'display': 'flex', 'flexDirection': 'column', 'width': 'fit-content',
            }, children=[
                html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '4px', 'marginBottom': '10px'}, children=[
                    DashIconify(icon='lucide:code', width=11, color='#a090c0'),
                    html.Span('Rule definition', style={'fontSize': '10px', 'color': '#a090c0', 'fontWeight': '700', 'letterSpacing': '0.05em', 'textTransform': 'uppercase'}),
                ]),
                html.Div(logic, style={
                    'fontFamily': "'Courier New', monospace", 'fontSize': '12px',
                    'background': '#ede8f5', 'color': '#4a3d6b', 'padding': '12px 16px',
                    'borderRadius': '8px', 'border': '1px solid #d8d0ee', 'lineHeight': '1.7', 'flex': '1',
                }),
            ]),
            html.Div(style={
                'background': '#faf9fd', 'border': '1px solid #ede9f8', 'borderRadius': '12px',
                'padding': '14px 16px', 'display': 'flex', 'flexDirection': 'column', 'width': 'fit-content',
            }, children=[
                html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '4px', 'marginBottom': '10px'}, children=[
                    DashIconify(icon='lucide:tag', width=11, color='#a090c0'),
                    html.Span('Critical fields', style={'fontSize': '10px', 'color': '#a090c0', 'fontWeight': '700', 'letterSpacing': '0.05em', 'textTransform': 'uppercase'}),
                ]),
                html.Div(style={
                    'display': 'flex', 'gap': '6px', 'flexWrap': 'wrap', 'background': '#ede8f5',
                    'border': '1px solid #d8d0ee', 'borderRadius': '8px', 'padding': '12px 16px',
                    'flex': '1', 'alignContent': 'flex-start',
                }, children=[
                    html.Span(c, style={
                        'fontSize': '12px', 'fontWeight': '400', 'color': '#4a3d6b', 'background': '#e6e0f4',
                        'padding': '4px 12px', 'borderRadius': '5px', 'border': '1px solid #cdc4e8',
                        'fontFamily': "'Courier New', monospace",
                    }) for c in base_cols
                ] if base_cols else [
                    html.Span('Automatic check', style={'fontSize': '12px', 'color': '#a090c0', 'fontStyle': 'italic'})
                ]),
            ]),
        ]),
    ])

    tech_details = html.Div(style={'display': 'flex', 'borderBottom': '1px solid #f0edf8'}, children=[left_sidebar, right_content])

    style_data_conditional = [
        {'if': {'column_id': c}, 'backgroundColor': '#FEF2F2', 'color': '#991B1B', 'fontWeight': 'bold'}
        for c in base_cols if c in df.columns
    ]

    display_cols = [c for c in df.columns]
    table = dash_table.DataTable(
        columns=[{"name": c, "id": c} for c in display_cols],
        data=df.head(500).to_dict('records'),
        page_size=15, sort_action='native', filter_action='native',
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left', 'padding': '10px', 'fontFamily': 'Inter', 'fontSize': '12px'},
        style_header={'backgroundColor': '#F8FAFC', 'fontWeight': 'bold', 'color': '#64748B', 'borderBottom': '2px solid #E2E8F0'},
        style_data_conditional=style_data_conditional,
    ) if not df.empty else html.Div('No failing records found for this check.', style={'padding': '24px', 'color': '#94A3B8'})

    modal_title = html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'overflow': 'hidden'}, children=[
        html.Span(check_id, style={'fontFamily': "'Courier New', monospace", 'fontSize': '13px', 'fontWeight': '700', 'color': '#ffffff'}),
        html.Span('·', style={'color': 'rgba(255,255,255,0.3)'}),
        html.Span(row.get('description', ''), style={'fontSize': '13px', 'color': 'rgba(255,255,255,0.7)', 'overflow': 'hidden', 'textOverflow': 'ellipsis', 'whiteSpace': 'nowrap'}),
    ])

    modal_content = html.Div([
        tech_details,
        html.Div(style={'padding': '20px 32px'}, children=[table]),
    ])

    return _MODAL_OPEN_STYLE, modal_title, modal_content


@app.callback(
    Output('download-modal-csv', 'data'),
    Input('btn-export-modal', 'n_clicks'),
    State({'type': 'dim-widget-chart', 'index': dash.ALL}, 'clickData'),
    prevent_initial_call=True,
)
def export_modal_to_csv(n_clicks, chart_clicks):
    check_id = None
    for click in chart_clicks:
        if click:
            point = click['points'][0]
            if 'customdata' in point:
                check_id = point['customdata'][0]
                break

    if not check_id:
        return None

    df = get_failing_records(check_id, frames, for_export=True)

    check_row = dq_results[dq_results['check_id'] == check_id]
    description = check_row.iloc[0]['description'] if not check_row.empty else check_id
    safe_desc = re.sub(r'[^\w\s\-]', '', description).strip().replace(' ', '_')
    filename = f"{check_id}_{safe_desc}.csv"

    return dcc.send_data_frame(df.to_csv, filename, index=False)
