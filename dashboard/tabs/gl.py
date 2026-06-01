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
    client = 'CA' if house == 'HOC' else 'LA'
    df = df_config[df_config['client'] == client].copy()
    if df.empty:
        return None

    df['dim_position'] = df['dim_position'].astype(str).str.strip()
    df['total_values'] = pd.to_numeric(df['total_values'], errors='coerce').fillna(0).astype(int)
    df['active']       = pd.to_numeric(df['active'],       errors='coerce').fillna(0).astype(int)
    df['closed']       = pd.to_numeric(df['closed'],       errors='coerce').fillna(0).astype(int)

    rows = []

    # GL posting dimensions — one leaf per attribute
    df_gl = df[df['dim_position'].isin(_GL_POSITIONS)].copy()
    for _, r in df_gl.iterrows():
        total = max(int(r['total_values']), 1)
        rows.append({
            'scope': f"GL Posting Dimensions ({len(df_gl)} attributes)",
            'label': f"{r['description']}<br>dim {r['dim_position']} · {int(r['active']):,} active",
            'active': max(int(r['active']), 1),
            'closed_pct': round(int(r['closed']) / total * 100, 1),
            'tip': (f"<b>{r['description']}</b><br>"
                    f"Attribute: {r['attribute_id']} | Position: dim_{r['dim_position']}<br>"
                    f"Active: {int(r['active']):,} &nbsp; Closed: {int(r['closed']):,} &nbsp; "
                    f"Total: {int(r['total_values']):,}"),
        })

    # X-position — aggregate into one block
    df_x = df[df['dim_position'] == 'X']
    if not df_x.empty:
        t = max(int(df_x['total_values'].sum()), 1)
        rows.append({
            'scope': 'Out of Scope',
            'label': f"X-position<br>{len(df_x):,} attributes",
            'active': max(int(df_x['active'].sum()), 1),
            'closed_pct': round(int(df_x['closed'].sum()) / t * 100, 1),
            'tip': (f"<b>X-position attributes ({len(df_x):,})</b><br>"
                    f"Not mapped to any GL journal line dimension<br>"
                    f"Active values: {int(df_x['active'].sum()):,} &nbsp; "
                    f"Total values: {int(df_x['total_values'].sum()):,}"),
        })

    # Letter-coded (not 0-7 and not X) — aggregate
    df_letter = df[~df['dim_position'].isin(_GL_POSITIONS) & (df['dim_position'] != 'X')]
    if not df_letter.empty:
        t = max(int(df_letter['total_values'].sum()), 1)
        rows.append({
            'scope': 'Out of Scope',
            'label': f"Other coded<br>{len(df_letter)} attributes",
            'active': max(int(df_letter['active'].sum()), 1),
            'closed_pct': round(int(df_letter['closed'].sum()) / t * 100, 1),
            'tip': (f"<b>Other letter-coded attributes ({len(df_letter)})</b><br>"
                    f"Mapped to non-GL positions (e.g. G, F, ...)<br>"
                    f"Active values: {int(df_letter['active'].sum()):,} &nbsp; "
                    f"Total values: {int(df_letter['total_values'].sum()):,}"),
        })

    if not rows:
        return None

    df_tree = pd.DataFrame(rows)

    fig = px.treemap(
        df_tree,
        path=['scope', 'label'],
        values='active',
        color='closed_pct',
        color_continuous_scale=[
            [0.0,  '#4ade80'],
            [0.35, '#facc15'],
            [1.0,  '#f87171'],
        ],
        range_color=[0, 80],
        custom_data=['tip'],
    )

    fig.update_traces(
        hovertemplate='%{customdata[0]}<extra></extra>',
        textfont_size=12,
        insidetextfont_size=11,
    )

    house_label = 'House of Commons' if house == 'HOC' else 'House of Lords'
    fig.update_layout(
        title=dict(
            text=f'<b>{house_label}</b>',
            font=dict(size=13, color='#2a1f3d'),
            x=0.02, xanchor='left',
        ),
        margin=dict(t=36, l=4, r=4, b=4),
        height=440,
        coloraxis_colorbar=dict(
            title='% closed',
            tickformat='.0f',
            ticksuffix='%',
            thickness=12,
            len=0.6,
        ),
        paper_bgcolor='white',
    )

    return fig


def _render_dim_structure(frames):
    """Treemap section showing GL vs out-of-scope dimension attributes."""
    if 'gl_dimconfig' not in frames or frames['gl_dimconfig'].empty:
        return html.Div()

    df = frames['gl_dimconfig']
    charts = []
    for house in ['HOC', 'HOL']:
        fig = _build_treemap(df, house)
        if fig:
            charts.append(
                dcc.Graph(
                    figure=fig,
                    style={'flex': '1', 'minWidth': 0},
                    config={'displayModeBar': False},
                )
            )

    if not charts:
        return html.Div()

    return html.Div([
        html.Div(style={**_SECTION_HEADER, 'marginTop': '24px'}, children=[
            html.Span('Dimension Structure', style=_SECTION_TITLE),
            html.Span('Volumetrics — not a DQ check', style=_SECTION_BADGE),
        ]),
        html.Div(
            style={'display': 'flex', 'gap': '16px'},
            children=charts,
        ),
        html.P(
            'Rectangle size = active dimension values (migration volume). '
            'Colour = % of all values that are closed (green = mostly active · red = high closed ratio). '
            'Out of Scope groups are aggregated — X-position and letter-coded attributes are not '
            'mapped to GL journal lines and are not in migration scope.',
            style={
                'fontSize': '11px', 'color': '#9080b0',
                'margin': '8px 4px 0', 'textAlign': 'center',
                'lineHeight': '1.6',
            },
        ),
    ])


def render_tab(dq_results, frames):
    return html.Div([
        render_dimension_scorecard(dq_results),
        _render_dim_structure(frames),
        html.Div(style=_SECTION_HEADER, children=[
            html.Span('Data Quality Checks', style=_SECTION_TITLE),
            html.Span('Being configured against live data', style=_SECTION_BADGE),
        ]),
        render_dimension_grid(dq_results),
        render_dimensions_table(dq_results),
    ])
