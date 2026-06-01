import pandas as pd
import plotly.express as px
from dash import html, dcc
from dashboard.shared.dimensions import render_dimension_scorecard, render_dimension_grid, render_dimensions_table

_GL_POSITIONS = {'0', '1', '2', '3', '4', '5', '6', '7'}

_SECTION_HEADER = {
    'borderTop': '1px solid #e2d9f3',
    'margin': '8px 0 20px',
    'paddingTop': '20px',
    'display': 'flex',
    'alignItems': 'center',
    'gap': '12px',
}

_SECTION_TITLE = {'fontSize': '15px', 'fontWeight': '700', 'color': '#2a1f3d'}
_SECTION_BADGE = {
    'fontSize': '11px', 'color': '#9080b0',
    'background': '#f0ebfa', 'padding': '2px 8px', 'borderRadius': '4px',
}


def _build_treemap(df_config, house):
    """Return a px.treemap figure for one house, or None if no data."""
    clients = ['CA', 'CM'] if house == 'HOC' else ['LA']
    raw = df_config[df_config['client'].isin(clients)].copy()
    if raw.empty:
        return None

    raw['dim_position'] = raw['dim_position'].astype(str).str.strip()
    raw['total_values'] = pd.to_numeric(raw['total_values'], errors='coerce').fillna(0).astype(int)
    raw['active']       = pd.to_numeric(raw['active'],       errors='coerce').fillna(0).astype(int)
    raw['closed']       = pd.to_numeric(raw['closed'],       errors='coerce').fillna(0).astype(int)

    # Combine CA + CM counts for HOC (same attributes, separate reporting entities)
    df = (
        raw.groupby(['attribute_id', 'description', 'dim_position'], as_index=False)
        [['total_values', 'active', 'closed']].sum()
    )

    rows = []

    # GL posting dimensions — one leaf per attribute
    df_gl = df[df['dim_position'].isin(_GL_POSITIONS)].copy()
    for _, r in df_gl.iterrows():
        total = max(int(r['total_values']), 1)
        rows.append({
            'scope': f"GL Dimensions · {len(df_gl)} attributes",
            'label': r['description'],
            'active': max(int(r['active']), 1),
            'closed_pct': round(int(r['closed']) / total * 100, 1),
            'tip': (f"<b>{r['description']}</b><br>"
                    f"dim_{r['dim_position']} &nbsp;·&nbsp; {r['attribute_id']}<br>"
                    f"Active: {int(r['active']):,} &nbsp; Closed: {int(r['closed']):,}"),
        })

    # X-position — aggregate into one block
    df_x = df[df['dim_position'] == 'X']
    if not df_x.empty:
        t = max(int(df_x['total_values'].sum()), 1)
        rows.append({
            'scope': 'Out of Scope',
            'label': f"X-position ({len(df_x)} attributes)",
            'active': max(int(df_x['active'].sum()), 1),
            'closed_pct': round(int(df_x['closed'].sum()) / t * 100, 1),
            'tip': (f"<b>X-position ({len(df_x)} attributes)</b><br>"
                    f"Not mapped to any GL journal line<br>"
                    f"Active values: {int(df_x['active'].sum()):,}"),
        })

    # Letter-coded (not 0-7 and not X) — aggregate
    df_letter = df[~df['dim_position'].isin(_GL_POSITIONS) & (df['dim_position'] != 'X')]
    if not df_letter.empty:
        t = max(int(df_letter['total_values'].sum()), 1)
        rows.append({
            'scope': 'Out of Scope',
            'label': f"Other ({len(df_letter)} attributes)",
            'active': max(int(df_letter['active'].sum()), 1),
            'closed_pct': round(int(df_letter['closed'].sum()) / t * 100, 1),
            'tip': (f"<b>Other coded ({len(df_letter)} attributes)</b><br>"
                    f"Non-GL positions (G, F, ...)<br>"
                    f"Active values: {int(df_letter['active'].sum()):,}"),
        })

    if not rows:
        return None

    # Normalise Out of Scope display size to a fixed fraction of GL total so
    # both houses have equal-width OOS blocks regardless of absolute value counts.
    # Real counts are preserved in tooltips; only the visual weight is adjusted.
    _OOS_FRACTION = 0.22
    gl_total = sum(r['active'] for r in rows if 'GL Dimensions' in r['scope'])
    oos_total = sum(r['active'] for r in rows if r['scope'] == 'Out of Scope')
    if gl_total > 0 and oos_total > 0:
        target = gl_total * _OOS_FRACTION / (1 - _OOS_FRACTION)
        scale = target / oos_total
        for r in rows:
            if r['scope'] == 'Out of Scope':
                r['active'] = max(1, round(r['active'] * scale))

    df_tree = pd.DataFrame(rows)

    fig = px.treemap(
        df_tree,
        path=['scope', 'label'],
        values='active',
        color='closed_pct',
        color_continuous_scale=[
            [0.0,  '#059669'],
            [0.35, '#d97706'],
            [1.0,  '#dc2626'],
        ],
        range_color=[0, 80],
        custom_data=['tip'],
    )

    fig.update_traces(
        hovertemplate='%{customdata[0]}<extra></extra>',
        texttemplate='%{label}',
        textfont=dict(size=12, color='white'),
        insidetextfont=dict(size=11, color='white'),
        marker=dict(line=dict(width=2, color='white')),
        pathbar=dict(visible=False),
    )

    fig.update_layout(
        margin=dict(t=0, l=0, r=0, b=0),
        height=360,
        coloraxis_showscale=False,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
    )

    return fig


_HOUSE_LABEL = {'HOC': 'HoC', 'HOL': 'HoL'}
_HOUSE_COLOR = {'HOC': '#16a34a', 'HOL': '#dc2626'}

_CARD = {
    'flex': '1', 'minWidth': 0,
    'background': '#ffffff',
    'border': '1px solid #ede9f8',
    'borderRadius': '12px',
    'padding': '16px 16px 12px',
    'display': 'flex',
    'flexDirection': 'column',
}


def _render_dim_structure(frames):
    """Treemap section showing GL vs out-of-scope dimension attributes."""
    if 'gl_dimconfig' not in frames or frames['gl_dimconfig'].empty:
        return html.Div()

    df = frames['gl_dimconfig']
    charts = []
    for house in ['HOC', 'HOL']:
        fig = _build_treemap(df, house)
        if fig:
            color = _HOUSE_COLOR[house]
            charts.append(html.Div([
                html.Div([
                    html.Div(style={
                        'width': '8px', 'height': '8px', 'borderRadius': '50%',
                        'background': color, 'flexShrink': '0',
                    }),
                    html.Span(_HOUSE_LABEL[house], style={
                        'fontSize': '13px', 'fontWeight': '700', 'color': color,
                    }),
                ], style={
                    'display': 'flex', 'alignItems': 'center', 'gap': '7px',
                    'marginBottom': '10px',
                }),
                dcc.Graph(
                    figure=fig,
                    style={'minWidth': 0, 'flex': '1'},
                    config={
                        'displayModeBar': True,
                        'modeBarButtonsToRemove': [
                            'toImage', 'sendDataToCloud', 'zoom2d', 'pan2d',
                            'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d',
                            'autoScale2d',
                        ],
                        'displaylogo': False,
                    },
                ),
            ], style=_CARD))

    if not charts:
        return html.Div()

    legend = html.Div([
        html.Div([
            html.Div(style={'width': '10px', 'height': '10px', 'borderRadius': '2px',
                            'background': '#059669', 'flexShrink': '0'}),
            html.Span('mostly active', style={'fontSize': '11px', 'color': '#9080b0'}),
        ], style={'display': 'flex', 'alignItems': 'center', 'gap': '5px'}),
        html.Div([
            html.Div(style={'width': '10px', 'height': '10px', 'borderRadius': '2px',
                            'background': '#d97706', 'flexShrink': '0'}),
            html.Span('~35% closed', style={'fontSize': '11px', 'color': '#9080b0'}),
        ], style={'display': 'flex', 'alignItems': 'center', 'gap': '5px'}),
        html.Div([
            html.Div(style={'width': '10px', 'height': '10px', 'borderRadius': '2px',
                            'background': '#dc2626', 'flexShrink': '0'}),
            html.Span('mostly closed', style={'fontSize': '11px', 'color': '#9080b0'}),
        ], style={'display': 'flex', 'alignItems': 'center', 'gap': '5px'}),
        html.Div(style={'width': '1px', 'background': '#e2d9f3', 'alignSelf': 'stretch', 'margin': '0 6px'}),
        html.Span('tile area ∝ active value count · click to drill in · ↺ to reset',
                  style={'fontSize': '11px', 'color': '#9080b0'}),
    ], style={
        'display': 'flex', 'alignItems': 'center', 'gap': '14px',
        'justifyContent': 'center', 'marginTop': '12px',
    })

    return html.Div([
        html.Div(style={**_SECTION_HEADER, 'marginTop': '32px'}, children=[
            html.Span('Dimension Structure', style=_SECTION_TITLE),
            html.Span('Volumetrics — not a DQ check', style=_SECTION_BADGE),
        ]),
        html.Div(
            style={'display': 'flex', 'gap': '16px'},
            children=charts,
        ),
        legend,
    ])


def render_tab(dq_results, frames):
    return html.Div([
        render_dimension_scorecard(dq_results),
        html.Div(style=_SECTION_HEADER, children=[
            html.Span('Data Quality Checks', style=_SECTION_TITLE),
            html.Span('Being configured against live data', style=_SECTION_BADGE),
        ]),
        render_dimension_grid(dq_results),
        render_dimensions_table(dq_results),
        _render_dim_structure(frames),
    ])
