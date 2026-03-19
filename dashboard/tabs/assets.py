from dash import html
from dashboard.shared.dimensions import render_dimension_scorecard, render_dimension_grid, render_dimensions_table

def render_tab(dq_results, frames):
    return html.Div([
        render_dimension_scorecard(dq_results),
        render_dimension_grid(dq_results),
        render_dimensions_table(dq_results),
        html.Div(id='dim-drill-down-container', style={'marginTop': '24px'})
    ])
