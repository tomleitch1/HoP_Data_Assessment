# ═══════════════════════════════════════════════════════════════════════════════
# charts.py  —  Pure chart factories.
#               All colours come from dashboard.core.config — change them there.
# ═══════════════════════════════════════════════════════════════════════════════

import textwrap
import plotly.graph_objects as go
import pandas as pd
from dashboard.core.config import AGING_BUCKETS, RAG_ORDER, CLIENTS
from dashboard.core.theme  import RAG_HEX, HOUSE_HEX, AGING_COLOURS, CHART_LAYOUT, PLOTLY_HOVER_CONFIG, PLOTLY_STATIC_CONFIG, UI, DISPLAY_FONT


def _wrap(text: str, width: int = 28) -> str:
    return '<br>'.join(textwrap.wrap(text, width))


def _truncate(text: str, max_len: int = 35) -> str:
    """Truncate long strings with ellipsis — keeps y-axis labels to a single line."""
    return text if len(text) <= max_len else text[:max_len - 1] + '…'


def rag_bar_house(subset: pd.DataFrame, house: str) -> go.Figure:
    subset     = subset.copy().sort_values('pass_rate')
    colour     = HOUSE_HEX.get(house, UI['purple_mid'])
    labels     = subset['description'].apply(_wrap)
    bar_height = max(500, len(subset) * 52)

    fig = go.Figure(go.Bar(
        x=subset['pass_rate'],
        y=labels,
        orientation='h',
        marker_color=colour,
        marker_line_width=0,
        opacity=0.85,
        text=[f'{v:.0f}%' for v in subset['pass_rate']],
        textposition='outside',
        textfont=dict(size=11, color=UI['text_secondary']),
        hovertemplate='<b>%{y}</b><br>Pass Rate: %{x:.1f}%<extra></extra>',
    ))
    fig.update_layout(
        **CHART_LAYOUT,
        height=bar_height,
        margin=dict(t=10, b=60, l=10, r=70),
        showlegend=False,
        xaxis=dict(
            range=[0, 140], ticksuffix='%', showgrid=True,
            gridcolor=UI['border'], gridwidth=1, color=UI['text_secondary'],
            tickfont=dict(size=12), side='bottom', fixedrange=True,
        ),
        yaxis=dict(
            automargin=True, color=UI['text_primary'], tickfont=dict(size=12),
            ticklabeloverflow='allow', ticklabelstandoff=10, fixedrange=True,
        ),
        bargap=0.35,
        dragmode=False,
    )
    fig.add_shape(type='line', x0=90, x1=90, y0=0, y1=1, yref='paper',
                  line=dict(dash='dash', width=1, color='rgba(26,122,74,0.5)'))
    fig.add_shape(type='line', x0=70, x1=70, y0=0, y1=1, yref='paper',
                  line=dict(dash='dash', width=1, color='rgba(212,130,10,0.5)'))
    fig.add_annotation(x=90, y=-0.06, yref='paper', xref='x', text='90% target',
                       showarrow=False, font=dict(color='rgba(26,122,74,0.9)', size=11), xanchor='center')
    fig.add_annotation(x=70, y=-0.06, yref='paper', xref='x', text='70% min',
                       showarrow=False, font=dict(color='rgba(212,130,10,0.9)', size=11), xanchor='center')
    return fig


def rag_bar(subset: pd.DataFrame) -> go.Figure:
    subset     = subset.copy().sort_values('pass_rate')
    colours    = [RAG_HEX[r] for r in subset['rag']]
    labels     = subset['description'].apply(_wrap)
    bar_height = max(600, len(subset) * 56)

    fig = go.Figure(go.Bar(
        x=subset['pass_rate'],
        y=labels,
        orientation='h',
        marker_color=colours,
        marker_line_width=0,
        text=[f'{v:.0f}%' for v in subset['pass_rate']],
        textposition='outside',
        textfont=dict(size=11, color=UI['text_secondary']),
        hovertemplate='<b>%{y}</b><br>Pass Rate: %{x:.1f}%<extra></extra>',
    ))
    fig.update_layout(
        **CHART_LAYOUT,
        height=bar_height,
        margin=dict(t=20, b=70, l=10, r=80),
        showlegend=False,
        xaxis=dict(
            range=[0, 140], ticksuffix='%', showgrid=True,
            gridcolor=UI['border'], gridwidth=1, color=UI['text_secondary'],
            tickfont=dict(size=12), side='bottom', fixedrange=True,
        ),
        yaxis=dict(
            automargin=True, color=UI['text_primary'], tickfont=dict(size=12),
            ticklabeloverflow='allow', ticklabelstandoff=10, fixedrange=True,
        ),
        bargap=0.35,
        dragmode=False,
    )
    fig.add_shape(type='line', x0=90, x1=90, y0=0, y1=1, yref='paper',
                  line=dict(dash='dash', width=1, color='rgba(26,122,74,0.6)'))
    fig.add_shape(type='line', x0=70, x1=70, y0=0, y1=1, yref='paper',
                  line=dict(dash='dash', width=1, color='rgba(212,130,10,0.6)'))
    fig.add_annotation(x=90, y=-0.06, yref='paper', xref='x', text='90% target',
                       showarrow=False, font=dict(color='rgba(26,122,74,0.9)', size=11), xanchor='center')
    fig.add_annotation(x=70, y=-0.06, yref='paper', xref='x', text='70% min',
                       showarrow=False, font=dict(color='rgba(212,130,10,0.9)', size=11), xanchor='center')
    return fig


def aging_chart(agg_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for house in CLIENTS:
        h = (
            agg_df[agg_df['house'] == house]
            .set_index('bucket').reindex(AGING_BUCKETS).fillna(0).reset_index()
        )
        fig.add_trace(go.Bar(
            name=house,
            x=h['bucket'],
            y=h['balance'],
            marker_color=HOUSE_HEX.get(house, UI['purple_mid']),
            marker_line_width=0,
            opacity=0.9,
            customdata=h['count'],
            hovertemplate=(
                f'<b>{house}</b><br>%{{x}}<br>'
                'Balance: £%{y:,.0f}<br>'
                'Invoices: %{customdata:,}<extra></extra>'
            ),
        ))
    fig.update_layout(
        **CHART_LAYOUT,
        height=320,
        margin=dict(t=20, b=40, l=10, r=10),
        showlegend=True,
        barmode='group',
        xaxis=dict(color=UI['text_secondary'], showgrid=False, tickfont=dict(size=12)),
        yaxis=dict(
            automargin=True, color=UI['text_secondary'], tickprefix='£',
            showgrid=True, gridcolor=UI['border'], tickfont=dict(size=12),
        ),
        legend=dict(orientation='h', y=-0.15, font=dict(color=UI['text_primary'], size=12)),
    )
    return fig


def donut(red: int, amber: int, green: int, centre_label: str) -> go.Figure:
    fig = go.Figure(go.Pie(
        labels=['Red', 'Amber', 'Green'],
        values=[red, amber, green],
        hole=0.72,
        marker_colors=[RAG_HEX['Red'], RAG_HEX['Amber'], RAG_HEX['Green']],
        marker=dict(line=dict(color=UI['card_bg'], width=3)),
        textinfo='none',
        hovertemplate='<b>%{label}</b>: %{value} checks<extra></extra>',
    ))
    fig.update_layout(
        **CHART_LAYOUT,
        height=210,
        margin=dict(t=10, b=10, l=10, r=10),
        showlegend=False,
        dragmode=False,
        annotations=[dict(
            text=f'<b>{centre_label}</b>',
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=26, color=UI['tab_indicator'], family="'Inter', sans-serif"),
        )],
    )
    return fig


def dimension_bar(dq: pd.DataFrame) -> go.Figure:
    # ── Scoring methodology ───────────────────────────────────────────────────
    # Info checks are volume counts (always 0 failing) — excluding them prevents
    # artificial inflation of dimension scores toward 100%.
    # Weighted by total records: a check over 3,000 records outweighs one over 5.
    # Formula per dimension: sum(passing records) / sum(total records) * 100
    scored = dq[dq['severity'] != 'Info']

    agg = (
        scored.groupby('dimension')
        .apply(lambda g: (g['total'] - g['failing']).sum() / g['total'].sum() * 100
               if g['total'].sum() > 0 else 0.0)
        .reset_index(name='pass_rate')
        .sort_values('pass_rate')
    )

    # RAG counts also exclude Info (consistent with scoring)
    rag_counts = scored.groupby(['dimension', 'rag']).size().unstack(fill_value=0)
    for col in ['Red', 'Amber', 'Green']:
        if col not in rag_counts.columns:
            rag_counts[col] = 0

    colours = [
        RAG_HEX['Green'] if v >= 90 else RAG_HEX['Amber'] if v >= 70 else RAG_HEX['Red']
        for v in agg['pass_rate']
    ]
    hover_texts = []
    for dim in agg['dimension']:
        rc    = rag_counts.loc[dim] if dim in rag_counts.index else pd.Series({'Red': 0, 'Amber': 0, 'Green': 0})
        score = agg.loc[agg['dimension'] == dim, 'pass_rate'].values[0]
        hover_texts.append(
            f'<b>{dim}</b><br>Score: {score:.0f}%<br>'
            f'(weighted by record count, Info checks excluded)<br>'
            f'Red: {int(rc.get("Red", 0))} checks  |  '
            f'Amber: {int(rc.get("Amber", 0))} checks  |  '
            f'Green: {int(rc.get("Green", 0))} checks'
        )

    fig = go.Figure(go.Bar(
        x=agg['pass_rate'], y=agg['dimension'],
        orientation='h',
        marker_color=colours, marker_line_width=0,
        text=[f'{v:.0f}%' for v in agg['pass_rate']],
        textposition='outside',
        textfont=dict(size=12, color=UI['text_secondary']),
        customdata=hover_texts,
        hovertemplate='%{customdata}<extra></extra>',
    ))
    fig.update_layout(
        **CHART_LAYOUT,
        height=280,
        margin=dict(t=20, b=40, l=10, r=60),
        showlegend=False,
        dragmode=False,
        xaxis=dict(range=[0, 120], ticksuffix='%', color=UI['text_secondary'],
                   showgrid=True, gridcolor=UI['border'], tickfont=dict(size=12)),
        yaxis=dict(automargin=True, color=UI['text_primary'], tickfont=dict(size=13), ticklabelstandoff=10),
        bargap=0.35,
    )
    return fig


def scope_heatmap(dq: pd.DataFrame, scope_labels: dict) -> go.Figure:
    # Group by parent tab (e.g. GL = scopes 20+21+22+23 combined) not individual scope_id
    from dashboard.core.config import SCOPE_TO_TAB
    dq_copy = dq.copy()
    dq_copy['tab_label'] = dq_copy['scope_id'].map(SCOPE_TO_TAB)
    agg = (
        dq_copy.groupby(['tab_label', 'house'])
        .apply(lambda g: g['passing'].sum() / g['total'].sum() * 100 if g['total'].sum() > 0 else 0.0)
        .reset_index(name='pass_rate')
    )
    agg.rename(columns={'tab_label': 'label'}, inplace=True)
    pivot = agg.pivot(index='label', columns='house', values='pass_rate').fillna(0)

    hover_matrix = []
    for tab_label in pivot.index:
        row_hovers = []
        for house in pivot.columns:
            sub = dq_copy[(dq_copy['tab_label'] == tab_label) & (dq_copy['house'] == house)]
            if sub.empty:
                row_hovers.append(f'<b>{tab_label} | {house}</b><br>No data')
            else:
                r, a, g = (int((sub['rag'] == k).sum()) for k in ('Red', 'Amber', 'Green'))
                row_hovers.append(
                    f'<b>{tab_label} | {house}</b><br>'
                    f'Score: {sub["passing"].sum() / sub["total"].sum() * 100:.0f}%<br>'
                    f'Red: {r}  |  Amber: {a}  |  Green: {g}'
                )
        hover_matrix.append(row_hovers)

    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale=[
            [0.00, RAG_HEX['Red']],
            [0.35, '#e8834a'],
            [0.65, '#f0c040'],
            [0.85, '#6ab187'],
            [1.00, RAG_HEX['Green']],
        ],
        zmin=60, zmax=100,
        text=[[f'{v:.0f}%' for v in row] for row in pivot.values],
        texttemplate='%{text}',
        textfont=dict(size=22, color='white', family=DISPLAY_FONT),
        customdata=hover_matrix,
        hovertemplate='%{customdata}<extra></extra>',
        showscale=True,
        colorbar=dict(
            thickness=14, len=0.9, ticksuffix='%',
            tickfont=dict(color=UI['text_secondary'], size=11),
            outlinewidth=0, bgcolor='rgba(0,0,0,0)',
        ),
    ))
    fig.update_layout(
        **CHART_LAYOUT,
        height=260,
        margin=dict(t=20, b=20, l=10, r=60),
        showlegend=False,
        dragmode=False,
        xaxis=dict(
            color=UI['text_primary'], side='top',
            tickfont=dict(size=17, color=UI['text_primary'], family="'Source Sans Pro', sans-serif"),
            showgrid=False,
        ),
        yaxis=dict(
            automargin=True, color=UI['text_primary'],
            tickfont=dict(size=14, color=UI['text_primary'], family="'Source Sans Pro', sans-serif"),
            showgrid=False, ticklabelstandoff=10,
        ),
    )
    return fig


def severity_stack(dq: pd.DataFrame) -> go.Figure:
    severity_order   = ['Critical', 'High', 'Medium', 'Low']
    severity_opacity = {'Critical': 1.00, 'High': 0.95, 'Medium': 0.85, 'Low': 0.75}

    risk  = dq[dq['rag'] != 'Green'].copy()
    risk['severity'] = pd.Categorical(risk['severity'], categories=severity_order, ordered=True)

    pivot = (
        risk.groupby(['severity', 'rag']).size().reset_index(name='count')
        .pivot(index='severity', columns='rag', values='count')
        .reindex(severity_order).fillna(0)
    )
    for col in ['Red', 'Amber']:
        if col not in pivot.columns:
            pivot[col] = 0

    fig = go.Figure()
    for rag, label in [('Red', 'Failing'), ('Amber', 'At Risk')]:
        hover = [
            f'<b>{label} | {sev}</b><br>{int(pivot.loc[sev, rag])} issues'
            for sev in severity_order
        ]
        fig.add_trace(go.Bar(
            name=rag,
            x=severity_order,
            y=pivot[rag],
            marker_color=RAG_HEX[rag],
            marker_line_width=0,
            marker=dict(opacity=[severity_opacity[s] for s in severity_order]),
            customdata=hover,
            hovertemplate='%{customdata}<extra></extra>',
        ))

    fig.update_layout(
        **CHART_LAYOUT,
        height=260,
        margin=dict(t=20, b=50, l=10, r=10),
        showlegend=True,
        barmode='stack',
        dragmode=False,
        xaxis=dict(color=UI['text_secondary'], showgrid=False, tickfont=dict(size=13)),
        yaxis=dict(
            automargin=True, color=UI['text_secondary'],
            showgrid=True, gridcolor=UI['border'], tickfont=dict(size=12),
            title='Number of Issues',
        ),
        legend=dict(orientation='h', y=-0.2, font=dict(color=UI['text_primary'], size=12)),
    )
    return fig


def object_score_bar(dq: pd.DataFrame, scope_labels: dict) -> go.Figure:
    # Group by parent tab (e.g. GL = scopes 20+21+22+23 combined) not individual scope_id
    from dashboard.core.config import SCOPE_TO_TAB
    dq_copy = dq.copy()
    dq_copy['tab_label'] = dq_copy['scope_id'].map(SCOPE_TO_TAB)
    agg = (
        dq_copy.groupby('tab_label')['pass_rate'].mean().reset_index()
        .rename(columns={'tab_label': 'label'})
        .sort_values('pass_rate')
    )
    colours = [
        RAG_HEX['Green'] if v >= 90 else RAG_HEX['Amber'] if v >= 70 else RAG_HEX['Red']
        for v in agg['pass_rate']
    ]
    hover_texts = []
    for _, row in agg.iterrows():
        sub  = dq_copy[dq_copy['tab_label'] == row['label']]
        r, a, g = (int((sub['rag'] == k).sum()) for k in ('Red', 'Amber', 'Green'))
        hover_texts.append(
            f'<b>{row["label"]}</b><br>Score: {row["pass_rate"]:.0f}%<br>'
            f'Red: {r} checks  |  Amber: {a} checks  |  Green: {g} checks'
        )

    fig = go.Figure(go.Bar(
        x=agg['pass_rate'], y=agg['label'],
        orientation='h',
        marker_color=colours, marker_line_width=0,
        text=[f'{v:.0f}%' for v in agg['pass_rate']],
        textposition='outside',
        textfont=dict(size=12, color=UI['text_secondary']),
        customdata=hover_texts,
        hovertemplate='%{customdata}<extra></extra>',
    ))
    fig.update_layout(
        **CHART_LAYOUT,
        height=240,
        margin=dict(t=20, b=40, l=10, r=60),
        showlegend=False,
        dragmode=False,
        xaxis=dict(range=[0, 120], ticksuffix='%', color=UI['text_secondary'],
                   showgrid=True, gridcolor=UI['border'], tickfont=dict(size=12)),
        yaxis=dict(automargin=True, color=UI['text_primary'], tickfont=dict(size=13), ticklabelstandoff=10),
        bargap=0.4,
    )
    return fig


# ── Dimension-grouped bar charts ──────────────────────────────────────────────
DIMENSION_ORDER = [
    'Completeness', 'Validity', 'Uniqueness',
    'Consistency', 'Timeliness', 'Referential Integrity',
]


def dimension_rag_bars(sub: pd.DataFrame, scope_id: int) -> dict[str, go.Figure]:
    """
    Build one grouped bar chart per DQ dimension.

    Each bar's customdata carries a pipe-delimited payload (split on '|||')
    consumed by the click popup in callbacks.py:

      [0]  check_name
      [1]  plain_english   — non-technical explanation
      [2]  logic           — Python test logic
      [3]  source_table    — Unit4 table(s)
      [4]  source_fields   — comma-separated field list
      [5]  fail_rate       — e.g. "14.3"
      [6]  failing         — integer count
      [7]  total           — integer count
      [8]  rag             — Red / Amber / Green
      [9]  house           — e.g. HOC
      [10] row_id          — DOM id of the matching Check Detail table row

    Hover is intentionally suppressed — all detail is shown via the click popup.
    """
    houses = sorted(sub['house'].unique())

    result = {}
    for dim in DIMENSION_ORDER:
        dim_data = sub[sub['dimension'] == dim].copy()
        if dim_data.empty:
            continue

        all_checks = sorted(dim_data['description'].unique())

        def _max_fail(chk):
            rows = dim_data[dim_data['description'] == chk]
            return max((100 - float(r['pass_rate'])) for _, r in rows.iterrows())

        failing_checks = sorted([c for c in all_checks if _max_fail(c) > 0],
                                 key=_max_fail)
        passing_checks = sorted([c for c in all_checks if _max_fail(c) == 0])
        ordered_checks = passing_checks + failing_checks

        fig = go.Figure()

        for house in houses:
            # Use the raw filtered DataFrame — NOT .set_index('description') —
            # to avoid a bug where two checks share the same description text
            # (possible in AR which spans scopes 11, 17 and 12). With a duplicate
            # index, hd.loc[chk] returns a DataFrame instead of a Series, causing
            # float(row['pass_rate']) to raise TypeError.
            hd_df        = dim_data[dim_data['house'] == house].copy()
            house_colour = HOUSE_HEX.get(house, UI['purple_mid'])

            fail_rates  = []
            custom_data = []
            label_texts = []

            for chk in ordered_checks:
                rows = hd_df[hd_df['description'] == chk]
                if not rows.empty:
                    # Multiple checks sharing a description → show worst case.
                    row       = rows.loc[rows['pass_rate'].idxmin()]
                    fail_rate = round(100 - float(row['pass_rate']), 1)
                    rag       = row['rag']
                    failing   = int(row['failing'])
                    total     = int(row['total'])
                    plain_english = str(row.get('plain_english', ''))
                    logic         = str(row.get('logic', ''))
                    source_table  = str(row.get('source_table', ''))
                    source_fields = row.get('source_fields', [])
                    if isinstance(source_fields, list):
                        source_fields_str = ', '.join(source_fields)
                    else:
                        source_fields_str = str(source_fields)
                else:
                    fail_rate         = 0.0
                    rag               = 'Green'
                    failing           = 0
                    total             = 0
                    plain_english     = ''
                    logic             = ''
                    source_table      = ''
                    source_fields_str = ''

                fail_rates.append(fail_rate)
                label_texts.append(f'{fail_rate:.0f}%' if fail_rate > 0 else '')

                row_id = f'check-row-{scope_id}-{hash(chk) & 0xFFFFFF}'

                # actual_scope_id: the real scope_id of the matched check row,
                # NOT the primary_scope_id of the tab. This matters for combined
                # tabs (AR spans scopes 11/17/12) where the callback must look
                # up the right row in dq.  Falls back to scope_id when no row
                # was found (e.g. a house that has no data for this check).
                if not rows.empty:
                    actual_scope_id = int(row['scope_id'])
                else:
                    actual_scope_id = scope_id

                custom_data.append('|||'.join([
                    chk,             # [0]  check description
                    plain_english,   # [1]  plain English explanation
                    logic,           # [2]  check logic
                    source_table,    # [3]  source table(s)
                    source_fields_str, # [4] fields checked
                    f'{fail_rate:.1f}',# [5] fail rate
                    str(failing),    # [6]  failing count
                    str(total),      # [7]  total count
                    rag,             # [8]  RAG status
                    house,           # [9]  house code
                    row_id,          # [10] DOM row id
                    str(actual_scope_id),  # [11] actual scope_id for modal lookup
                ]))

            wrapped_labels = ['<br>'.join(textwrap.wrap(c, 32)) for c in ordered_checks]

            fig.add_trace(go.Bar(
                name=house,
                y=wrapped_labels,
                x=fail_rates,
                orientation='h',
                marker_color=house_colour,
                marker_line_width=0,
                opacity=0.9,
                text=label_texts,
                textposition='outside',
                textfont=dict(size=12, color=UI['text_primary'],
                              family="'Source Sans Pro', sans-serif"),
                customdata=custom_data,
                # customdata layout (split on '|||'):
                #   [0] check_name  [1] plain_english  [2] logic
                #   [3] source_table  [4] source_fields
                #   [5] fail_rate  [6] failing  [7] total  [8] rag  [9] house
                hovertemplate='<extra></extra>',
                showlegend=True,
            ))

        n_checks   = len(ordered_checks)
        bar_height = max(160, n_checks * 62)

        fig.update_layout(
            **CHART_LAYOUT,
            height=bar_height,
            margin=dict(t=10, b=40, l=10, r=55),
            showlegend=True,
            barmode='group',
            bargap=0.18,
            bargroupgap=0.05,
            xaxis=dict(
                range=[0, 105],
                ticksuffix='%',
                showgrid=True,
                gridcolor=UI['border'],
                color=UI['text_secondary'],
                tickfont=dict(size=10),
                title=dict(text='Fail Rate',
                           font=dict(size=10, color=UI['text_secondary'])),
                fixedrange=True,
                showline=False,
            ),
            yaxis=dict(
                automargin=True,
                color=UI['text_primary'],
                tickfont=dict(size=12),
                ticklabelstandoff=6,
                fixedrange=True,
                showline=False,
                zeroline=False,
            ),
            legend=dict(
                orientation='h',
                y=-0.10,
                font=dict(color=UI['text_primary'], size=12),
                bgcolor='rgba(0,0,0,0)',
            ),
        )

        result[dim] = fig

    return result