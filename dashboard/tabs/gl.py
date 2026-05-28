from dash import html
from dashboard.shared.dimensions import render_dimension_scorecard, render_dimension_grid, render_dimensions_table


def render_tab(dq_results, frames):
    return html.Div([
        render_dimension_scorecard(dq_results),
        html.Div(style={
            'borderTop': '1px solid #e2d9f3',
            'margin': '8px 0 20px',
            'paddingTop': '20px',
            'display': 'flex',
            'alignItems': 'center',
            'gap': '12px',
        }, children=[
            html.Span('Data Quality Checks', style={
                'fontSize': '15px', 'fontWeight': '700', 'color': '#2a1f3d',
            }),
            html.Span('Being configured against live data', style={
                'fontSize': '11px', 'color': '#9080b0',
                'background': '#f0ebfa', 'padding': '2px 8px',
                'borderRadius': '4px',
            }),
        ]),
        render_dimension_grid(dq_results),
        render_dimensions_table(dq_results),
    ])
