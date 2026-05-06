from dash import html, dcc, dash_table
import plotly.graph_objects as go
import pandas as pd
from dashboard.shared.ui import card, section_header, HOUSE_HEX, CHART_LAYOUT
from dashboard.core.theme import UI

AGING_COLOURS = {
    'Not Yet Due': '#27AE60',
    '0-30 Days': '#2ECC71',
    '31-60 Days': '#F1C40F',
    '61-90 Days': '#E67E22',
    '91-180 Days': '#E74C3C',
    '180+ Days': '#7B241C',
}


def _house_toggle(toggle_id, initial='Both'):
    """Styled HOC / HOL / Both toggle buttons."""
    options = [
        {'label': 'Both', 'value': 'Both'},
        {'label': 'HOC',  'value': 'HOC'},
        {'label': 'HOL',  'value': 'HOL'},
    ]
    return dcc.RadioItems(
        id=toggle_id,
        options=options,
        value=initial,
        inline=True,
        inputStyle={'display': 'none'},
        labelStyle={
            'cursor': 'pointer',
            'padding': '5px 16px',
            'fontSize': '12px',
            'fontWeight': '600',
            'borderRadius': '6px',
            'border': f'1px solid {UI["border"]}',
            'background': UI['card_bg'],
            'color': UI['text_secondary'],
            'marginRight': '6px',
            'userSelect': 'none',
        },
    )


def render_aging(aging_results, module):
    if module == 'ap':
        agg        = aging_results.get('AP', pd.DataFrame())
        title      = 'AP Aging Analysis'
        desc       = 'Outstanding payables by age band'
        graph_id   = 'aging-ap-graph'
        toggle_id  = 'aging-ap-chart-toggle'
        house_id   = 'aging-ap-house'
        bucket_id  = 'aging-ap-bucket'
        table_id   = 'aging-ap-table'
    elif module == 'ar':
        agg        = aging_results.get('AR', pd.DataFrame())
        title      = 'AR Aging Analysis'
        desc       = 'Outstanding receivables by age band'
        graph_id   = 'aging-ar-graph'
        toggle_id  = 'aging-ar-chart-toggle'
        house_id   = 'aging-ar-house'
        bucket_id  = 'aging-ar-bucket'
        table_id   = 'aging-ar-table'
    else:
        return html.Div()

    return card([
        # Header row with toggle inline
        html.Div(style={
            'display': 'flex', 'alignItems': 'center',
            'justifyContent': 'space-between', 'marginBottom': '16px',
        }, children=[
            section_header(title, desc),
            _house_toggle(toggle_id),
        ]),

        dcc.Graph(id=graph_id, figure=make_aging_chart(agg, 'Both'),
                  config={'displayModeBar': False}),

        html.Div(style={'display': 'flex', 'gap': '20px', 'marginTop': '20px', 'marginBottom': '20px'}, children=[
            html.Div([
                html.Label('House', style={'fontSize': '11px', 'fontWeight': '700', 'color': '#5A7A9A', 'letterSpacing': '1px', 'marginBottom': '6px', 'display': 'block'}),
                dcc.Dropdown(id=house_id, options=[{'label': 'HOC', 'value': 'HOC'}, {'label': 'HOL', 'value': 'HOL'}], value='HOC', style={'width': '200px'}),
            ]),
            html.Div([
                html.Label('Bucket', style={'fontSize': '11px', 'fontWeight': '700', 'color': '#5A7A9A', 'letterSpacing': '1px', 'marginBottom': '6px', 'display': 'block'}),
                dcc.Dropdown(id=bucket_id, options=[{'label': b, 'value': b} for b in AGING_COLOURS.keys()], value='180+ Days', style={'width': '200px'}),
            ]),
        ]),

        dash_table.DataTable(
            id=table_id,
            style_table={'overflowX': 'auto', 'minHeight': '300px'},
            style_cell={
                'background': 'white', 'color': '#1E293B',
                'border': '1px solid #E2E8F0', 'padding': '10px 14px',
                'fontSize': '12px', 'textAlign': 'left', 'fontFamily': 'Poppins'
            },
            style_header={'background': '#F8FAFC', 'color': '#64748B', 'fontWeight': 'bold'},
            page_size=15,
        )
    ], style={'marginTop': '24px'})

def make_aging_chart(agg_df, house_filter='Both'):
    if agg_df is None or agg_df.empty:
        return go.Figure()

    buckets = ['Not Yet Due', '0-30 Days', '31-60 Days', '61-90 Days', '91-180 Days', '180+ Days']
    houses  = ['HOC', 'HOL'] if house_filter == 'Both' else [house_filter]
    fig     = go.Figure()

    for house in houses:
        h = agg_df[agg_df['house'] == house]
        h = h.set_index('aging_bucket').reindex(buckets).fillna(0).reset_index()
        fig.add_trace(go.Bar(
            name=house,
            x=h['aging_bucket'],
            y=h['balance'],
            marker_color=HOUSE_HEX.get(house, '#4A7FBF'),
            opacity=0.85,
            hovertemplate=f'<b>{house}</b><br>%{{x}}<br>£%{{y:,.0f}}<extra></extra>',
        ))

    fig.update_layout(
        **CHART_LAYOUT,
        height=320,
        barmode='group',
        xaxis=dict(color='#64748B', showgrid=False),
        yaxis=dict(color='#64748B', tickprefix='£', showgrid=True, gridcolor='#F1F5F9'),
        legend=dict(orientation='h', y=-0.15, font=dict(color='#64748B')),
    )
    return fig
