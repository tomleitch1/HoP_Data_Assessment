import pandas as pd
import plotly.express as px
from dash import html, dcc, dash_table
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

    # Normalise Out of Scope display size to a fixed fraction of GL total so
    # both houses have equal-width OOS blocks regardless of absolute value counts.
    # Real counts are preserved in tooltips; only the visual weight is adjusted.
    _OOS_FRACTION = 0.22
    gl_total = sum(r['active'] for r in rows if 'GL Posting' in r['scope'])
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
        pathbar=dict(
            thickness=22,
            textfont=dict(size=11, color='#4a3d6b'),
        ),
    )

    fig.update_layout(
        margin=dict(t=8, l=4, r=4, b=32),
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


_HOUSE_LABEL = {'HOC': 'HoC', 'HOL': 'HoL'}
_HOUSE_COLOR = {'HOC': '#16a34a', 'HOL': '#dc2626'}


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
                html.Div(
                    _HOUSE_LABEL[house],
                    style={
                        'fontSize': '13px', 'fontWeight': '700',
                        'color': color,
                        'borderBottom': f'2px solid {color}',
                        'paddingBottom': '5px', 'marginBottom': '2px',
                    },
                ),
                dcc.Graph(
                    figure=fig,
                    style={'minWidth': 0, 'overflow': 'visible'},
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
            ], style={'flex': '1', 'minWidth': 0, 'display': 'flex', 'flexDirection': 'column'}))

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
            'Click any rectangle to drill in and zoom. Use the home button (↺) to reset. '
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


def _compute_hierarchy_stats(frames, house):
    """
    For each GL dimension attribute in one house, compute:
      - Root nodes  : values with no parent (rel_value blank)
      - Leaf nodes  : values that are never someone else's parent
      - Parent nodes: values that have at least one child
      - Max depth   : deepest level in the hierarchy tree
      - Posted to Parent: count of distinct (client, dim_position, dim_value)
        combinations in gl_transact_dim that map to a parent/summary node
        (postings should land on leaves only)
    Returns a DataFrame with one row per attribute, sorted by position.
    """
    if 'agldimvalue' not in frames:
        return pd.DataFrame()

    dv = frames['agldimvalue'][frames['agldimvalue']['house'] == house].copy()
    if dv.empty:
        return pd.DataFrame()

    # Normalise rel_value: blank/nan → '' (root indicator)
    dv['_rel'] = dv['rel_value'].astype(str).str.strip().replace({'nan': '', 'None': ''})
    dv['_is_root'] = dv['_rel'] == ''

    # Composite key: attribute_id || client || dim_value
    dv['_key']  = dv['attribute_id'].astype(str) + '||' + dv['client'].astype(str) + '||' + dv['dim_value'].astype(str)
    dv['_pkey'] = dv['attribute_id'].astype(str) + '||' + dv['client'].astype(str) + '||' + dv['_rel']

    # Parent nodes = those whose _key appears as someone else's _pkey
    parent_keys = set(dv.loc[~dv['_is_root'], '_pkey'])
    dv['_is_parent'] = dv['_key'].isin(parent_keys)

    # Depth — iterative level assignment from roots outward
    depth = pd.Series(float('nan'), index=dv.index)
    depth[dv['_is_root']] = 1.0
    key_to_depth = dv.loc[dv['_is_root'], '_key'].reset_index().set_index('_key')['index'].map(lambda i: 1.0).to_dict()
    key_to_depth = {k: 1.0 for k in dv.loc[dv['_is_root'], '_key']}

    for _ in range(15):
        un_mask = depth.isna()
        if not un_mask.any():
            break
        un = dv.loc[un_mask]
        parent_d = un['_pkey'].map(key_to_depth)
        resolved = parent_d.dropna()
        if resolved.empty:
            break
        new_d = resolved + 1.0
        depth.update(new_d)
        for idx in new_d.index:
            key_to_depth[dv.at[idx, '_key']] = new_d[idx]

    dv['_depth'] = depth

    # Cross-reference with posted dimension codes
    has_transact = 'gl_transact_dim' in frames and not frames['gl_transact_dim'].empty
    posted_parent_keys = set()
    if has_transact:
        td = frames['gl_transact_dim'][frames['gl_transact_dim']['house'] == house].copy()
        td['_td_key'] = (
            td['client'].astype(str) + '||' +
            td['dim_position'].astype(str) + '||' +
            td['dim_value'].astype(str).str.strip()
        )
        posted_parent_keys = set(td['_td_key'])

    rows = []
    for (attr_id, dim_desc, dim_pos), grp in dv.groupby(
        ['attribute_id', 'dim_description', 'dim_position'], sort=False
    ):
        total    = len(grp)
        parents  = int(grp['_is_parent'].sum())
        leaves   = total - parents
        roots    = int(grp['_is_root'].sum())
        valid_d  = grp['_depth'].dropna()
        max_depth = int(valid_d.max()) if not valid_d.empty else 1

        posted_to_parent = '—'
        if has_transact:
            # Build the set of parent node keys for this attribute at this position
            parent_vals = set(grp.loc[grp['_is_parent'], 'dim_value'].astype(str))
            parent_clients = set(grp['client'].astype(str))
            count = 0
            for cl in parent_clients:
                for pv in parent_vals:
                    if f"{cl}||{dim_pos}||{pv}" in posted_parent_keys:
                        count += 1
            posted_to_parent = count

        rows.append({
            'Attribute':        dim_desc,
            'Position':         f"dim_{dim_pos}",
            'Total Active':     total,
            'Root Nodes':       roots,
            'Leaf Nodes':       leaves,
            'Parent Nodes':     parents,
            'Max Depth':        max_depth,
            'Posted to Parent': posted_to_parent,
        })

    df_out = pd.DataFrame(rows)
    if not df_out.empty:
        df_out = df_out.sort_values('Position').reset_index(drop=True)
    return df_out


def _render_hierarchy_section(frames):
    """Side-by-side hierarchy analysis tables for HOC and HOL."""
    if 'agldimvalue' not in frames:
        return html.Div()

    has_transact = 'gl_transact_dim' in frames and not frames['gl_transact_dim'].empty

    columns = [
        {'name': 'Attribute',        'id': 'Attribute'},
        {'name': 'Position',         'id': 'Position'},
        {'name': 'Total Active',     'id': 'Total Active',     'type': 'numeric'},
        {'name': 'Root Nodes',       'id': 'Root Nodes',       'type': 'numeric'},
        {'name': 'Leaf Nodes',       'id': 'Leaf Nodes',       'type': 'numeric'},
        {'name': 'Parent Nodes',     'id': 'Parent Nodes',     'type': 'numeric'},
        {'name': 'Max Depth',        'id': 'Max Depth',        'type': 'numeric'},
        {'name': 'Posted to Parent', 'id': 'Posted to Parent'},
    ]

    _TBL_STYLE = {
        'fontSize': '12px',
        'fontFamily': "'Poppins', sans-serif",
        'border': 'none',
    }
    _HDR_STYLE = [{'if': {'column_id': c['id']}, 'textAlign': 'left'} for c in columns]

    panels = []
    for house in ['HOC', 'HOL']:
        color = _HOUSE_COLOR[house]
        df = _compute_hierarchy_stats(frames, house)

        if df.empty:
            panels.append(html.Div(
                f"No dimension value data for {_HOUSE_LABEL[house]}",
                style={'color': '#9080b0', 'fontSize': '12px', 'padding': '16px'},
            ))
            continue

        # Conditional row style: amber highlight when postings land on parent nodes
        style_data_conditional = [
            {
                'if': {'filter_query': '{Posted to Parent} > 0'},
                'backgroundColor': '#fffbeb',
                'borderLeft': '3px solid #f59e0b',
            },
            {'if': {'row_index': 'odd'}, 'backgroundColor': '#faf9fd'},
        ]

        panels.append(html.Div([
            html.Div(
                _HOUSE_LABEL[house],
                style={
                    'fontSize': '13px', 'fontWeight': '700', 'color': color,
                    'borderBottom': f'2px solid {color}',
                    'paddingBottom': '5px', 'marginBottom': '10px',
                },
            ),
            dash_table.DataTable(
                data=df.to_dict('records'),
                columns=columns,
                style_table={'overflowX': 'auto'},
                style_cell={
                    'padding': '6px 10px', 'whiteSpace': 'normal',
                    'height': 'auto', 'border': 'none',
                    'fontFamily': "'Poppins', sans-serif", 'fontSize': '12px',
                    'color': '#2a1f3d',
                },
                style_header={
                    'backgroundColor': '#f0ebfa',
                    'fontWeight': '600', 'fontSize': '11px',
                    'color': '#4a3d6b', 'border': 'none',
                    'textAlign': 'left',
                },
                style_data={'border': 'none'},
                style_data_conditional=style_data_conditional,
                style_cell_conditional=_HDR_STYLE,
                page_action='none',
                sort_action='native',
            ),
        ], style={'flex': '1', 'minWidth': 0}))

    caption_parts = [
        'Root Nodes have no parent. Leaf Nodes are posting targets — they have no children. '
        'Parent Nodes sit above leaves in the hierarchy and should not receive direct postings.',
    ]
    if has_transact:
        caption_parts.append(
            'Posted to Parent counts dimension codes used on actual GL transactions '
            'that map to a parent (non-leaf) node — these rows are highlighted amber.'
        )
    else:
        caption_parts.append(
            'Posted to Parent requires gl_transact_dimensions_HOC/HOL.csv in data/gl/ — run the SQL extract to populate this column.'
        )

    return html.Div([
        html.Div(style={**_SECTION_HEADER, 'marginTop': '8px'}, children=[
            html.Span('Dimension Hierarchy Structure', style=_SECTION_TITLE),
            html.Span('Volumetrics — not a DQ check', style=_SECTION_BADGE),
        ]),
        html.Div(
            style={'display': 'flex', 'gap': '24px', 'alignItems': 'flex-start'},
            children=panels,
        ),
        html.P(
            ' '.join(caption_parts),
            style={
                'fontSize': '11px', 'color': '#9080b0',
                'margin': '10px 4px 0', 'lineHeight': '1.6',
            },
        ),
    ])


def render_tab(dq_results, frames):
    return html.Div([
        render_dimension_scorecard(dq_results),
        _render_dim_structure(frames),
        _render_hierarchy_section(frames),
        html.Div(style=_SECTION_HEADER, children=[
            html.Span('Data Quality Checks', style=_SECTION_TITLE),
            html.Span('Being configured against live data', style=_SECTION_BADGE),
        ]),
        render_dimension_grid(dq_results),
        render_dimensions_table(dq_results),
    ])
