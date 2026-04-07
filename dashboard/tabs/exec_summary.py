import pandas as pd
from dash import dcc, html, dash_table
import sys
import os

# Add root directory to sys path to import the new modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dashboard.shared.ui import card, section_header
from dashboard.core.charts import donut, dimension_bar, scope_heatmap, severity_stack, object_score_bar
from dashboard.core.config import SCOPE_CONFIG, SCOPE_LABELS, RAG_ORDER, SEV_ORDER, SEV_WEIGHT
from dashboard.core.theme import UI, RAG_HEX, SEV_HEX, HOUSE_HEX, PLOTLY_STATIC_CONFIG, PLOTLY_HOVER_CONFIG, DISPLAY_FONT
from dashboard.core.volumetrics import get_overview_volumetrics

TABLE_CELL_STYLE = {
    'textAlign': 'left', 
    'fontFamily': 'Poppins, sans-serif', 
    'color': '#1E293B',
    'whiteSpace': 'normal',
    'height': 'auto'
}

TABLE_HEADER_STYLE = {
    'backgroundColor': '#F8FAFC', 
    'fontWeight': 'bold', 
    'color': '#64748B',
    'borderBottom': '1px solid #E2E8F0'
}

def table_conditional_styles():
    return [
        {'if': {'column_id': 'RAG', 'filter_query': '{RAG} eq "Red"'}, 'color': '#E74C3C', 'fontWeight': 'bold'},
        {'if': {'column_id': 'RAG', 'filter_query': '{RAG} eq "Amber"'}, 'color': '#F39C12', 'fontWeight': 'bold'},
        {'if': {'column_id': 'RAG', 'filter_query': '{RAG} eq "Green"'}, 'color': '#006548', 'fontWeight': 'bold'}
    ]

def render_summary(dq: pd.DataFrame, frames: dict, master_tab=None) -> html.Div:
    if dq.empty:
        return html.Div(style={'padding': '60px', 'textAlign': 'center', 'color': '#94A3B8'}, children=[
            html.Div("No data available.", style={'fontSize': '18px', 'fontWeight': '600'})
        ])

    total = len(dq)
    avg   = round(dq['pass_rate'].mean(), 1) if 'pass_rate' in dq.columns else 0
    red   = int((dq['rag'] == 'Red').sum())
    amber = int((dq['rag'] == 'Amber').sum())
    green = int((dq['rag'] == 'Green').sum())

    vol_stats = get_overview_volumetrics(frames)

    row0 = _data_snapshot(vol_stats, frames)

    row1 = html.Div(style={'display': 'flex', 'gap': '16px', 'marginBottom': '16px', 'flexWrap': 'wrap'}, children=[
        card([
            section_header('RAG Overview', f'{total} checks assessed'),
            dcc.Graph(figure=donut(red, amber, green, f'{avg}%'), config=PLOTLY_HOVER_CONFIG),
            html.Div(style={'display': 'flex', 'justifyContent': 'space-around', 'marginTop': '8px'}, children=[
                _rag_legend_item(str(red),   'Red',   RAG_HEX.get('Red', '#c0392b')),
                _rag_legend_item(str(amber), 'Amber', RAG_HEX.get('Amber', '#d4820a')),
                _rag_legend_item(str(green), 'Green', RAG_HEX.get('Green', '#1a7a4a')),
            ]),
        ], style={'flex': '0 0 260px', 'minWidth': '220px'}),
        card([
            section_header('Score by Data Quality Dimensions'),
            dcc.Graph(figure=dimension_bar(dq), config=PLOTLY_HOVER_CONFIG),
        ], style={'flex': '1', 'minWidth': '280px'}),
        card([
            section_header('Score by Datasets'),
            dcc.Graph(figure=object_score_bar(dq, SCOPE_LABELS), config=PLOTLY_HOVER_CONFIG),
        ], style={'flex': '1', 'minWidth': '280px'}),
    ])

    row2 = html.Div(style={'display': 'flex', 'gap': '16px', 'marginBottom': '16px', 'flexWrap': 'wrap'}, children=[
        card([
            section_header('Scope Item Heatmap', 'Average score by data object and house'),
            dcc.Graph(figure=scope_heatmap(dq, SCOPE_LABELS), config=PLOTLY_HOVER_CONFIG),
        ], style={'flex': '1', 'minWidth': '280px'}),
        card([
            section_header('Risk Exposure by Severity'),
            dcc.Graph(figure=severity_stack(dq), config=PLOTLY_HOVER_CONFIG),
        ], style={'flex': '1', 'minWidth': '280px'}),
    ])

    row3 = card([
        section_header('List of Checks Performed', 'Click the scope to see all checks assessed'),
        _checks_accordion(dq),
    ])

    return html.Div([row0, row1, row2, row3])


# ── Data Snapshot ─────────────────────────────────────────────────────────────

def _data_snapshot(vol_stats: dict, frames: dict) -> html.Div:
    """
    One card per dataset — shows total records, HOC/HOL split, and extract date.
    Datasets with no data yet show 0 records and a 'No data loaded' note.
    """
    DATASETS = [
        {
            'label':      'AP Ledger',
            'icon':       '🏢',
            'combined':   True,
            'keys_a':     ('suppliers_total',   'supplier_extract_date'),
            'keys_b':     ('ap_invoices_open',  'ap_extract_date'),
            'tables':     ('asuheader', 'asutrans'),
        },
        {
            'label':      'AR Ledger',
            'icon':       '🏛️',
            'combined':   True,
            'keys_a':     ('customers_total',   'customer_extract_date'),
            'keys_b':     ('ar_invoices_open',  'ar_extract_date'),
            'tables':     ('acuheader', 'acutrans'),
        },
        {
            'label':    'General Ledger',
            'icon':     '📒',
            'hoc_key':  'gl_total_records',
            'hol_key':  'gl_total_records',
            'date_key': 'gl_extract_date',
            'table':    'aglaccounts',
        },
        {
            'label':    'Assets',
            'icon':     '🏗️',
            'hoc_key':  None,
            'hol_key':  None,
            'date_key': None,
            'table':    'asset_master',
        },
        {
            'label':    'Planning, Budgeting & Forecasting',
            'icon':     '📊',
            'hoc_key':  None,
            'hol_key':  None,
            'date_key': None,
            'table':    'pbf_data',
        },
    ]

    cards = []
    for ds in DATASETS:
        hoc = vol_stats.get('HOC', {})
        hol = vol_stats.get('HOL', {})

        if ds.get('combined'):
            # Sum counts and pick the latest date across both constituent datasets
            key_a, date_a = ds['keys_a']
            key_b, date_b = ds['keys_b']
            hoc_n = hoc.get(key_a, 0) + hoc.get(key_b, 0)
            hol_n = hol.get(key_a, 0) + hol.get(key_b, 0)
            dates = [d for d in [hoc.get(date_a), hol.get(date_a),
                                  hoc.get(date_b), hol.get(date_b)] if d]
            date_str = max(dates) if dates else '—'
        elif ds.get('hoc_key') and ds.get('hol_key'):
            hoc_n = hoc.get(ds['hoc_key'], 0)
            hol_n = hol.get(ds['hol_key'], 0)
            hoc_date = hoc.get(ds['date_key']) if ds.get('date_key') else None
            hol_date = hol.get(ds['date_key']) if ds.get('date_key') else None
            date_str = hoc_date or hol_date or '—'
        else:
            # Pending scopes — fall back to counting directly from frames
            table = ds.get('table')
            if table and table in frames and not frames[table].empty:
                df    = frames[table]
                if 'house' in df.columns:
                    hoc_n = int((df['house'] == 'HOC').sum())
                    hol_n = int((df['house'] == 'HOL').sum())
                elif 'client' in df.columns:
                    hoc_n = int((df['client'] == 'HOC').sum())
                    hol_n = int((df['client'] == 'HOL').sum())
                else:
                    hoc_n = len(df)
                    hol_n = 0
                date_col = 'last_update' if 'last_update' in df.columns else None
                date_str = pd.to_datetime(df[date_col], errors='coerce').loc[lambda x: x <= pd.Timestamp.now()].max().strftime('%d %b %Y').lstrip('0') if date_col else '—'
            else:
                hoc_n = 0
                hol_n = 0
                date_str = '—'

        total = hoc_n + hol_n

        has_data  = total > 0

        hoc_hex = HOUSE_HEX.get('HOC', '#1a7a4a')
        hol_hex = HOUSE_HEX.get('HOL', '#8b1a1a')
        hoc_rgb = ','.join(str(int(hoc_hex[i:i+2], 16)) for i in (1, 3, 5))
        hol_rgb = ','.join(str(int(hol_hex[i:i+2], 16)) for i in (1, 3, 5))

        # Body content differs slightly for pending scopes
        if has_data:
            body_content = [
                # Total — large
                html.Div([
                    html.Div(f'{total:,}', style={
                        'fontSize': '32px', 'fontWeight': '800',
                        'color': UI['text_primary'], 'fontFamily': DISPLAY_FONT,
                        'lineHeight': '1',
                    }),
                    html.Div('Total records', style={
                        'fontSize': '11px', 'color': UI['text_secondary'],
                        'marginTop': '3px',
                    }),
                ], style={'marginBottom': '14px'}),

                # HOC / HOL split
                html.Div([
                    html.Div([
                        html.Span('HOC', style={
                            'fontSize': '9px', 'fontWeight': '800', 'letterSpacing': '1.5px',
                            'color': hoc_hex, 'background': f'rgba({hoc_rgb},0.12)',
                            'padding': '2px 6px', 'borderRadius': '3px',
                            'marginRight': '6px',
                        }),
                        html.Span(f'{hoc_n:,}', style={
                            'fontSize': '16px', 'fontWeight': '700',
                            'color': UI['text_primary'], 'fontFamily': DISPLAY_FONT,
                        }),
                    ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '6px'}),
                    html.Div([
                        html.Span('HOL', style={
                            'fontSize': '9px', 'fontWeight': '800', 'letterSpacing': '1.5px',
                            'color': hol_hex, 'background': f'rgba({hol_rgb},0.12)',
                            'padding': '2px 6px', 'borderRadius': '3px',
                            'marginRight': '6px',
                        }),
                        html.Span(f'{hol_n:,}', style={
                            'fontSize': '16px', 'fontWeight': '700',
                            'color': UI['text_primary'], 'fontFamily': DISPLAY_FONT,
                        }),
                    ], style={'display': 'flex', 'alignItems': 'center'}),
                ], style={'marginBottom': '14px'}),

                # Extract date
                html.Div([
                    html.Span('Extract date  ', style={
                        'fontSize': '10px', 'color': UI['text_secondary'],
                    }),
                    html.Span(date_str, style={
                        'fontSize': '10px', 'color': UI['text_secondary'],
                        'fontWeight': '600',
                    }),
                ], style={
                    'borderTop':  f"1px solid {UI['border']}",
                    'paddingTop': '10px',
                }),
            ]
        else:
            body_content = [
                # Placeholder total
                html.Div([
                    html.Div('—', style={
                        'fontSize': '32px', 'fontWeight': '800',
                        'color': UI['text_secondary'], 'fontFamily': DISPLAY_FONT,
                        'lineHeight': '1',
                    }),
                    html.Div('No data loaded yet', style={
                        'fontSize': '11px', 'color': UI['text_secondary'],
                        'marginTop': '3px',
                    }),
                ], style={'marginBottom': '14px'}),

                # HOC / HOL placeholders
                html.Div([
                    html.Div([
                        html.Span('HOC', style={
                            'fontSize': '9px', 'fontWeight': '800', 'letterSpacing': '1.5px',
                            'color': hoc_hex, 'background': f'rgba({hoc_rgb},0.12)',
                            'padding': '2px 6px', 'borderRadius': '3px',
                            'marginRight': '6px',
                        }),
                        html.Span('—', style={
                            'fontSize': '16px', 'fontWeight': '700',
                            'color': UI['text_secondary'], 'fontFamily': DISPLAY_FONT,
                        }),
                    ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '6px'}),
                    html.Div([
                        html.Span('HOL', style={
                            'fontSize': '9px', 'fontWeight': '800', 'letterSpacing': '1.5px',
                            'color': hol_hex, 'background': f'rgba({hol_rgb},0.12)',
                            'padding': '2px 6px', 'borderRadius': '3px',
                            'marginRight': '6px',
                        }),
                        html.Span('—', style={
                            'fontSize': '16px', 'fontWeight': '700',
                            'color': UI['text_secondary'], 'fontFamily': DISPLAY_FONT,
                        }),
                    ], style={'display': 'flex', 'alignItems': 'center'}),
                ], style={'marginBottom': '14px'}),

                # Pending note
                html.Div([
                    html.Span('Awaiting data extract', style={
                        'fontSize': '10px', 'color': UI['text_secondary'],
                        'fontStyle': 'italic',
                    }),
                ], style={
                    'borderTop':  f"1px solid {UI['border']}",
                    'paddingTop': '10px',
                }),
            ]

        cards.append(html.Div([
            # Header
            html.Div([
                html.Span(ds['icon'], style={'marginRight': '6px'}),
                html.Span(ds['label'], style={
                    'fontSize': '10px', 'fontWeight': '800',
                    'letterSpacing': '1.5px', 'textTransform': 'uppercase',
                    'color': UI['text_secondary'],
                }),
            ], style={
                'padding':      '8px 14px',
                'borderBottom': f"1px solid {UI['border']}",
                'background':   UI['card_bg_dark'] if has_data else UI['card_bg_dark'],
            }),

            # Body
            html.Div(body_content, style={'padding': '14px'}),

        ], style={
            'flex':         '1',
            'background':   UI['card_bg'],
            'border':       f"1px solid {UI['border']}",
            'borderRadius': '6px',
            'overflow':     'hidden',
            'boxShadow':    '0 1px 4px rgba(59,26,110,0.05)',
            'opacity':      '1' if has_data else '0.65',
        }))

    return card([
        section_header(
            'Data Snapshot',
            'Volume of source data under assessment · extracted from the Unit4 ERP system',
        ),
        html.Div(cards, style={'display': 'flex', 'gap': '12px', 'flexWrap': 'wrap'}),
    ], style={'marginBottom': '16px'})


def _fmt_bal(val: float) -> str:
    if abs(val) >= 1_000_000:
        return f'£{val / 1_000_000:.1f}m'
    if abs(val) >= 1_000:
        return f'£{val / 1_000:.0f}k'
    return f'£{val:,.0f}'


# ── RAG legend item ───────────────────────────────────────────────────────────

def _rag_legend_item(value: str, label: str, colour: str) -> html.Div:
    return html.Div([
        html.Div(value, style={'fontSize': '20px', 'fontWeight': '800', 'color': colour, 'textAlign': 'center'}),
        html.Div(label, style={'fontSize': '10px', 'color': UI['text_secondary'], 'textAlign': 'center', 'letterSpacing': '1px'}),
    ])


# ── Checks accordion ──────────────────────────────────────────────────────────

def _checks_accordion(dq: pd.DataFrame) -> html.Div:
    """
    One panel per tab (SCOPE_CONFIG entry), not per individual scope_id.
    This matches the tab structure: AP = Suppliers + AP Invoices combined,
    AR = Customers + AR Invoices combined, GL / Assets / PBF as single scopes.
    """
    panels = []

    for tab_key, cfg in SCOPE_CONFIG.items():
        label      = cfg['label']
        scope_ids  = cfg['scope_ids']

        sub = dq[dq['scope_id'].isin(scope_ids)].copy()

        n_red   = int((sub['rag'] == 'Red').sum())   if not sub.empty else 0
        n_amber = int((sub['rag'] == 'Amber').sum()) if not sub.empty else 0
        n_green = int((sub['rag'] == 'Green').sum()) if not sub.empty else 0
        n_total = len(sub)

        # Pending scopes — no checks defined yet
        if sub.empty:
            panels.append(html.Details([
                html.Summary(
                    style={
                        'display': 'flex', 'alignItems': 'center', 'gap': '14px',
                        'padding': '14px 18px', 'cursor': 'pointer',
                        'background': UI['card_bg_dark'], 'borderRadius': '8px',
                        'marginBottom': '2px', 'listStyle': 'none', 'userSelect': 'none',
                        'opacity': '0.65',
                    },
                    children=[
                        html.Div(label, style={
                            'fontSize': '14px', 'fontWeight': '700',
                            'color': UI['text_primary'], 'minWidth': '120px',
                        }),
                        html.Div('0 checks', style={
                            'fontSize': '12px', 'color': UI['text_secondary'], 'minWidth': '70px',
                        }),
                        html.Div('Awaiting data extract', style={
                            'fontSize': '11px', 'color': UI['text_secondary'],
                            'fontStyle': 'italic',
                        }),
                        html.Div('▸ expand', style={
                            'marginLeft': 'auto', 'fontSize': '11px', 'color': UI['text_secondary'],
                        }),
                    ],
                ),
                html.Div(
                    html.Div('No checks defined yet for this scope.', style={
                        'fontSize': '13px', 'color': UI['text_secondary'],
                        'fontStyle': 'italic', 'padding': '16px 4px',
                    }),
                    style={'padding': '12px 4px 4px'},
                ),
            ], style={'marginBottom': '8px'}))
            continue

        display = sub[['house', 'object', 'dimension', 'severity', 'description', 'pass_rate', 'failing', 'total', 'rag']].copy()
        display['pass_rate'] = display['pass_rate'].apply(lambda x: f'{x:.0f}%')
        display = (
            display.assign(_rank=display['rag'].map({'Red': 0, 'Amber': 1, 'Green': 2}))
            .sort_values(['_rank', 'pass_rate']).drop(columns='_rank')
        )
        display.columns = ['House', 'Source', 'Dimension', 'Severity', 'Check', 'Score', 'Failing', 'Total', 'RAG']

        panels.append(html.Details([
            html.Summary(
                style={
                    'display': 'flex', 'alignItems': 'center', 'gap': '14px',
                    'padding': '14px 18px', 'cursor': 'pointer',
                    'background': UI['card_bg_dark'], 'borderRadius': '8px',
                    'marginBottom': '2px', 'listStyle': 'none', 'userSelect': 'none',
                },
                children=[
                    html.Div(label,               style={'fontSize': '14px', 'fontWeight': '700', 'color': UI['text_primary'], 'minWidth': '120px'}),
                    html.Div(f'{n_total} checks', style={'fontSize': '12px', 'color': UI['text_secondary'], 'minWidth': '70px'}),
                    *([
                        _mini_pill(f'● {n_red} Red',     RAG_HEX['Red'])   if n_red   else html.Span(),
                        _mini_pill(f'● {n_amber} Amber', RAG_HEX['Amber']) if n_amber else html.Span(),
                        _mini_pill(f'● {n_green} Green', RAG_HEX['Green']) if n_green else html.Span(),
                    ]),
                    html.Div('▸ expand', style={'marginLeft': 'auto', 'fontSize': '11px', 'color': UI['text_secondary']}),
                ],
            ),
            html.Div(style={'padding': '12px 4px 4px'}, children=[
                dash_table.DataTable(
                    data=display.to_dict('records'),
                    columns=[{'name': c, 'id': c} for c in display.columns],
                    style_table={'overflowX': 'auto'},
                    style_cell={**TABLE_CELL_STYLE, 'padding': '8px 12px', 'fontSize': '12px'},
                    style_header={**TABLE_HEADER_STYLE, 'padding': '8px 12px', 'fontSize': '10px'},
                    style_data_conditional=table_conditional_styles(),
                    style_cell_conditional=[
                        {'if': {'column_id': 'Check'}, 'maxWidth': '400px'},
                    ],
                    sort_action='native',
                    page_size=50,
                ),
            ]),
        ], style={'marginBottom': '8px'}))

    return html.Div(panels)

def _mini_pill(text: str, colour: str) -> html.Span:
    return html.Span(text, style={
        'color': colour, 'fontWeight': '700', 'fontSize': '12px', 'marginRight': '4px',
    })
