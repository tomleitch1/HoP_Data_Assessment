from dash import dcc, html
import pandas as pd
import plotly.graph_objects as go
from dashboard.shared.dimensions import render_dimension_scorecard, render_dimension_grid, render_dimensions_table
from dashboard.core.theme import DISPLAY_FONT, HOUSE_HEX

def get_asset_volumetrics(frames, dq_results=None):
    vols = {'HOC': {}, 'HOL': {}}
    am = frames.get('asset_master', pd.DataFrame())
    ab = frames.get('asset_balances', pd.DataFrame())
    ad = frames.get('asset_depreciation', pd.DataFrame())

    for house in ['HOC', 'HOL']:
        h_am = am[am['house'] == house] if not am.empty else pd.DataFrame()
        h_ab = ab[ab['house'] == house] if not ab.empty else pd.DataFrame()
        h_ad = ad[ad['house'] == house] if not ad.empty else pd.DataFrame()
        
        count = len(h_am)
        # Treat both 'N' (Normal) and 'T' (Transferred) as in-scope for migration
        mig_scope = len(h_am[h_am['status'].isin(['N', 'T'])]) if count > 0 else 0
        archive = len(h_am[h_am['status'] == 'C']) if count > 0 else 0
        grant_funded = len(h_am[pd.to_numeric(h_am.get('grant_flag', 0), errors='coerce') == 1]) if count > 0 else 0
        
        status_counts = h_am['status'].value_counts().to_dict() if count > 0 else {}
        
        # Balance scope and Business Metrics
        nbv_by_client = {}
        total_nbv = 0
        total_cost = 0
        total_depr = 0
        zero_value_count = 0
        
        if not h_ab.empty:
            # NBV = (CA + PC + VN + ZU) - (ND + ED + FD + SA)
            cost_types = ['CA', 'PC']
            depr_types = ['ND', 'ED', 'FD']
            pos_types = ['CA', 'PC', 'VN', 'ZU']
            neg_types = ['ND', 'ED', 'FD', 'SA']
            
            total_cost = h_ab[h_ab['trans_type'].isin(cost_types)]['total_amount'].sum()
            total_depr = h_ab[h_ab['trans_type'].isin(depr_types)]['total_amount'].sum()
            
            asset_pos = h_ab[h_ab['trans_type'].isin(pos_types)].groupby('asset_id')['total_amount'].sum()
            asset_neg = h_ab[h_ab['trans_type'].isin(neg_types)].groupby('asset_id')['total_amount'].sum()
            
            asset_nbv = asset_pos.add(-asset_neg, fill_value=0)
            total_nbv = asset_nbv.sum()
            zero_value_count = len(asset_nbv[asset_nbv.abs() < 0.01])
            
            if 'client' in h_ab.columns:
                for client in h_ab['client'].dropna().unique():
                    c_ab = h_ab[h_ab['client'] == client]
                    c_pos = c_ab[c_ab['trans_type'].isin(pos_types)]['total_amount'].sum()
                    c_neg = c_ab[c_ab['trans_type'].isin(neg_types)]['total_amount'].sum()
                    nbv_by_client[client] = c_pos - c_neg

        # Books and Depreciation Scope
        multi_book = len(h_ad.groupby('asset_id').filter(lambda g: len(g) > 1).drop_duplicates('asset_id')) if not h_ad.empty else 0
        indexed = len(h_ad[h_ad.get('index_id', '').notna() & (h_ad.get('index_id', '') != '')]) if not h_ad.empty else 0
        
        # DQ-AB-S01: CA only (Non-depreciating)
        non_depr_count = 0
        if not h_ab.empty:
            # Group by book level
            grp = h_ab.groupby(['client', 'asset_id', 'depr_book_id'])['trans_type'].unique()
            # Count where 'CA' is present but no depreciation types ('ND', 'ED', 'FD')
            non_depr_count = sum(grp.apply(lambda x: 'CA' in x and not any(d in x for d in ['ND', 'ED', 'FD'])))

        # Readiness Calculation
        readiness_pct = 100.0
        if dq_results is not None and not dq_results.empty:
            asset_dq = dq_results[(dq_results['house'] == house) & 
                                  (dq_results['object'].str.contains('Asset')) & 
                                  (dq_results['severity'].isin(['Critical', 'High']))]
            if not asset_dq.empty:
                max_failing = asset_dq['failing'].max()
                readiness_pct = max(0, (count - max_failing) / count * 100) if count > 0 else 100.0

        # GL Reconciliation
        gl_bal = 0
        gl_df = frames.get('aglyearend', pd.DataFrame())
        if not gl_df.empty:
            house_gl = gl_df[gl_df['house'] == house]
            asset_gl = house_gl[house_gl['account'].isin(['1300', '1301'])]
            gl_bal = asset_gl['amount'].sum()

        vols[house] = {
            'Total Assets': count,
            'Migration Scope (N)': mig_scope,
            'Archive Candidates': archive,
            'Grant Funded': grant_funded,
            'Multi-book Assets': multi_book,
            'Indexed Assets': indexed,
            'Disposals (SA)': len(h_ab[h_ab['trans_type'] == 'SA']) if not h_ab.empty else 0,
            'Disposals Value': h_ab[h_ab['trans_type'] == 'SA']['total_amount'].sum() if not h_ab.empty else 0,
            'Status Counts': status_counts,
            'NBV by Client': nbv_by_client,
            'Total NBV': total_nbv,
            'Total Cost': total_cost,
            'Total Depr': total_depr,
            'Zero Value Assets': zero_value_count,
            'Readiness %': readiness_pct,
            'GL Balance': gl_bal,
            'Variance': total_nbv - gl_bal,
            'Non-depreciating Assets': non_depr_count
        }
            
    return vols

def render_house_asset_cards(house, data):
    house_color = HOUSE_HEX.get(house, '#00703c')
    colors = ['#00703c', '#28a367', '#d4820a', '#c0392b', '#5c5470', '#3498DB', '#9B59B6', '#F1C40F']

    def fmt_gbp(val):
        if abs(val) >= 1_000_000: return f"£{val/1_000_000:.2f}M"
        if abs(val) >= 1_000: return f"£{val/1_000:.1f}k"
        return f"£{val:,.2f}"

    # ── 1. ASSET MASTER CARD ──────────────────────────────────────────────
    status_counts = data.get('Status Counts', {})
    m_sorted = sorted(status_counts.items(), key=lambda x: x[1], reverse=True)

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
        annotations=[dict(text=f"<b>{data['Total Assets']:,}</b><br><span style='font-size:9px'>TOTAL</span>",
                          x=0.5, y=0.5, showarrow=False, font=dict(size=16, color='#1E293B', family=DISPLAY_FONT))]
    )

    m_status_list = []
    for i, (status, count) in enumerate(m_sorted):
        m_status_list.append(html.Div([
            html.Span('●', style={'color': colors[i % len(colors)], 'marginRight': '8px'}),
            html.Span(f"Status {status}: ", style={'fontSize': '11px', 'fontWeight': '600', 'color': '#64748B'}),
            html.Span(f"{count:,}", style={'fontSize': '11px', 'fontWeight': '700', 'color': '#1E293B'})
        ], style={'marginBottom': '4px', 'display': 'inline-block', 'width': '50%', 'whiteSpace': 'nowrap'}))

    master_card = html.Div(style={
        'background': 'white', 'border': '1px solid #D0CCE0', 'borderRadius': '12px',
        'flex': '1.4', 'display': 'flex', 'flexDirection': 'column', 'overflow': 'hidden',
        'boxShadow': '0 4px 6px -1px rgba(0,0,0,0.05)'
    }, children=[
        html.Div(style={
            'background': '#F8FAFC', 'padding': '14px 20px', 'borderBottom': '1px solid #E2E8F0',
            'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center'
        }, children=[
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '12px'}, children=[
                html.Div(style={'width': '3px', 'height': '16px', 'background': house_color, 'borderRadius': '2px'}),
                html.Div(f"{house} — Asset Master", style={
                    'fontSize': '13px', 'fontWeight': '600', 'color': '#475569',
                    'textTransform': 'uppercase', 'letterSpacing': '0.5px'
                }),
            ]),
            html.Div("asset_master", style={'fontSize': '10px', 'color': '#94A3B8', 'fontWeight': '600'})
        ]),
        html.Div(style={'padding': '20px', 'display': 'flex', 'flexDirection': 'column'}, children=[
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '20px', 'marginBottom': '16px'}, children=[
                html.Div(style={'flex': '1'}, children=[dcc.Graph(figure=master_fig, config={'displayModeBar': False})]),
                html.Div(style={'flex': '1.2'}, children=[
                    html.Div('Population Status', style={'fontSize': '10px', 'fontWeight': '700', 'color': '#64748B', 'textTransform': 'uppercase', 'marginBottom': '8px'}),
                    html.Div(m_status_list, style={'display': 'flex', 'flexWrap': 'wrap'})
                ])
            ]),
            # Scope Metrics underneath pie chart
            html.Div(style={'display': 'flex', 'gap': '20px', 'paddingTop': '12px', 'borderTop': '1px dashed #E2E8F0'}, children=[
                html.Div([
                    html.Div(f"{data['Migration Scope (N)']:,}", style={'fontSize': '18px', 'fontWeight': '800', 'color': '#00703c', 'fontFamily': DISPLAY_FONT}),
                    html.Div('Migration Scope (N+T)', style={'fontSize': '9px', 'fontWeight': '600', 'color': '#64748B', 'textTransform': 'uppercase'})
                ], style={'flex': '1'}),
                html.Div([
                    html.Div(f"{data['Archive Candidates']:,}", style={'fontSize': '18px', 'fontWeight': '800', 'color': '#c0392b', 'fontFamily': DISPLAY_FONT}),
                    html.Div('Archive Candidates (C)', style={'fontSize': '9px', 'fontWeight': '600', 'color': '#64748B', 'textTransform': 'uppercase'})
                ], style={'flex': '1'}),
            ])
        ])
    ])

    # ── 2. BALANCES / DEPRECIATION CARD ───────────────────────────────────────
    clients = list(data['NBV by Client'].keys())
    nbvs = list(data['NBV by Client'].values())

    nbv_fig = go.Figure()
    for i, (client, val) in enumerate(zip(clients, nbvs)):
        if val == 0: continue
        nbv_fig.add_trace(go.Bar(
            name=str(client), y=['NBV'], x=[val], orientation='h',
            marker_color=colors[i % len(colors)], marker_line_width=0,
            hovertemplate=f"<b>{client}</b>: £{val:,.0f}<extra></extra>"
        ))

    nbv_fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        height=50, margin=dict(t=0, b=0, l=0, r=0), barmode='stack', showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False)
    )

    nbv_legend = []
    for i, (client, val) in enumerate(zip(clients, nbvs)):
        lbl = f"£{val/1000:,.0f}k" if abs(val) >= 1000 else f"£{val:,.0f}"
        nbv_legend.append(html.Div([
            html.Span('●', style={'color': colors[i % len(colors)], 'marginRight': '6px'}),
            html.Span(f"{client}: {lbl}", style={'fontSize': '10px', 'fontWeight': '700', 'color': '#64748B'})
        ], style={'marginRight': '12px', 'display': 'inline-block'}))

    trans_card = html.Div(style={
        'background': 'white', 'border': '1px solid #D0CCE0', 'borderRadius': '12px',
        'flex': '1.6', 'display': 'flex', 'flexDirection': 'column', 'overflow': 'hidden',
        'boxShadow': '0 4px 6px -1px rgba(0,0,0,0.05)'
    }, children=[
        html.Div(style={
            'background': '#F8FAFC', 'padding': '14px 20px', 'borderBottom': '1px solid #E2E8F0',
            'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center'
        }, children=[
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '12px'}, children=[
                html.Div(style={'width': '3px', 'height': '16px', 'background': house_color, 'borderRadius': '2px'}),
                html.Div(f"{house} — Asset Balances & Metrics", style={
                    'fontSize': '13px', 'fontWeight': '600', 'color': '#475569',
                    'textTransform': 'uppercase', 'letterSpacing': '0.5px'
                }),
            ]),
            html.Div("asset_balances, asset_depreciation", style={'fontSize': '10px', 'color': '#94A3B8', 'fontWeight': '600'})
        ]),
        html.Div(style={'padding': '20px'}, children=[
            html.Div(style={'display': 'grid', 'gridTemplateColumns': 'repeat(4, 1fr)', 'gap': '12px', 'marginBottom': '20px'}, children=[
                html.Div([
                    html.Div(fmt_gbp(data['Total Cost']), style={'fontSize': '18px', 'fontWeight': '800', 'color': '#1E293B', 'fontFamily': DISPLAY_FONT}),
                    html.Div('Original Cost', style={'fontSize': '9px', 'fontWeight': '600', 'color': '#64748B', 'textTransform': 'uppercase'})
                ]),
                html.Div([
                    html.Div(fmt_gbp(data['Total Depr']), style={'fontSize': '18px', 'fontWeight': '800', 'color': '#c0392b', 'fontFamily': DISPLAY_FONT}),
                    html.Div('Accum Depr', style={'fontSize': '9px', 'fontWeight': '600', 'color': '#64748B', 'textTransform': 'uppercase'})
                ]),
                html.Div([
                    html.Div(fmt_gbp(data['Total NBV']), style={'fontSize': '18px', 'fontWeight': '800', 'color': '#3498DB', 'fontFamily': DISPLAY_FONT}),
                    html.Div('Total NBV', style={'fontSize': '9px', 'fontWeight': '600', 'color': '#64748B', 'textTransform': 'uppercase'})
                ]),
                html.Div([
                    html.Div(f"{data['Disposals (SA)']:,}", style={'fontSize': '18px', 'fontWeight': '800', 'color': '#F59E0B', 'fontFamily': DISPLAY_FONT}),
                    html.Div(f"Disposals ({fmt_gbp(data['Disposals Value'])})", style={'fontSize': '9px', 'fontWeight': '600', 'color': '#64748B', 'textTransform': 'uppercase'})
                ]),
            ]),
            html.Div([
                html.Div(style={'display': 'flex', 'justifyContent': 'space-between', 'marginBottom': '8px'}, children=[
                    html.Div('Net Book Value by Client', style={'fontSize': '10px', 'fontWeight': '700', 'color': '#64748B', 'textTransform': 'uppercase'}),
                    html.Div(f"Total: {fmt_gbp(data['Total NBV'])}", style={'fontSize': '9px', 'color': '#94A3B8'})
                ]),
                dcc.Graph(figure=nbv_fig, config={'displayModeBar': False}),
                html.Div(nbv_legend, style={'marginTop': '8px', 'display': 'flex', 'flexWrap': 'wrap'})
            ])
        ]),
        html.Div(style={'background': '#F1F5F9', 'padding': '8px 20px', 'fontSize': '11px', 'color': '#64748B', 'borderTop': '1px solid #E2E8F0', 'display': 'flex', 'gap': '16px'}, children=[
            html.Span([html.Strong('Grant Funded: ', style={'fontWeight': '600'}), html.Span(f"{data['Grant Funded']:,}", style={'color': '#1E293B', 'fontWeight': '700'})]),
            html.Span([html.Strong('Multi-book: ', style={'fontWeight': '600'}), html.Span(f"{data['Multi-book Assets']:,}", style={'color': '#1E293B', 'fontWeight': '700'})]),
            html.Span([html.Strong('Indexed: ', style={'fontWeight': '600'}), html.Span(f"{data['Indexed Assets']:,}", style={'color': '#1E293B', 'fontWeight': '700'})]),
            html.Span([html.Strong('Non-depreciating: ', style={'fontWeight': '600'}), html.Span(f"{data['Non-depreciating Assets']:,}", style={'color': '#1E293B', 'fontWeight': '700'})])
        ])
    ])

    return [master_card, trans_card]

def render_gl_reconciliation(house, data):
    house_color = HOUSE_HEX.get(house, '#00703c')
    recon_color = '#00703c' if abs(data['Variance']) < 0.01 else '#c0392b'

    def fmt_gbp(val):
        if abs(val) >= 1_000_000: return f"£{val/1_000_000:.2f}M"
        if abs(val) >= 1_000: return f"£{val/1_000:.1f}k"
        return f"£{val:,.2f}"
    
    return html.Div(style={
        'background': 'white', 'border': '1px solid #D0CCE0', 'borderRadius': '12px',
        'padding': '20px', 'flex': '1', 'boxShadow': '0 4px 6px -1px rgba(0,0,0,0.05)',
        'display': 'flex', 'flexDirection': 'column', 'justifyContent': 'center'
    }, children=[
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '12px', 'marginBottom': '12px'}, children=[
            html.Div(style={'width': '3px', 'height': '16px', 'background': house_color, 'borderRadius': '2px'}),
            html.Div(f"{house} — GL Reconciliation", style={
                'fontSize': '13px', 'fontWeight': '600', 'color': '#475569',
                'textTransform': 'uppercase', 'letterSpacing': '0.5px'
            }),
        ]),
        
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '40px'}, children=[
            html.Div([
                html.Div('Asset Sub-Ledger', style={'fontSize': '10px', 'fontWeight': '700', 'color': '#64748B', 'textTransform': 'uppercase', 'marginBottom': '2px'}),
                html.Div(fmt_gbp(data['Total NBV']), style={'fontSize': '20px', 'fontWeight': '800', 'color': '#1E293B', 'fontFamily': DISPLAY_FONT}),
            ]),
            html.Div([
                html.Div('General Ledger', style={'fontSize': '10px', 'fontWeight': '700', 'color': '#64748B', 'textTransform': 'uppercase', 'marginBottom': '2px'}),
                html.Div(fmt_gbp(data['GL Balance']), style={'fontSize': '20px', 'fontWeight': '800', 'color': '#1E293B', 'fontFamily': DISPLAY_FONT}),
            ]),
            html.Div(style={
                'marginLeft': 'auto', 'padding': '10px 24px', 'borderRadius': '8px', 
                'background': '#F8FAFC' if abs(data['Variance']) < 0.01 else '#FEF2F2',
                'border': '1px solid ' + ('#E2E8F0' if abs(data['Variance']) < 0.01 else '#FEE2E2'),
                'textAlign': 'right'
            }, children=[
                html.Div('Variance', style={'fontSize': '10px', 'fontWeight': '700', 'color': '#64748B', 'textTransform': 'uppercase'}),
                html.Div(fmt_gbp(data['Variance']), style={'fontSize': '22px', 'fontWeight': '900', 'color': recon_color, 'fontFamily': DISPLAY_FONT}),
            ])
        ])
    ])

def render_tab(dq_results, frames):
    vols = get_asset_volumetrics(frames, dq_results)

    hoc_cards = render_house_asset_cards('HOC', vols['HOC'])
    hol_cards = render_house_asset_cards('HOL', vols['HOL'])
    
    hoc_recon = render_gl_reconciliation('HOC', vols['HOC'])
    hol_recon = render_gl_reconciliation('HOL', vols['HOL'])

    return html.Div([
        render_dimension_scorecard(dq_results),
        
        # Row 1: HOC Volumetrics
        html.Div(style={'marginBottom': '20px'}, children=[
            html.Div(style={'display': 'flex', 'gap': '20px'}, children=hoc_cards),
        ]),
        
        # Row 2: HOL Volumetrics
        html.Div(style={'marginBottom': '24px'}, children=[
            html.Div(style={'display': 'flex', 'gap': '20px'}, children=hol_cards),
        ]),

        # Row 3: Reconciliation (Horizontal Row)
        html.Div(style={'marginBottom': '24px', 'display': 'flex', 'gap': '20px'}, children=[
            hoc_recon, hol_recon
        ]),
        
        render_dimension_grid(dq_results),
        render_dimensions_table(dq_results),
        html.Div(id='dim-drill-down-container', style={'marginTop': '24px'})
    ])