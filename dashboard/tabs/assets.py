from dash import html
from dashboard.shared.ui import render_asset_volumetrics_card
from dashboard.shared.dimensions import render_dimension_scorecard, render_dimension_grid, render_dimensions_table
from dashboard.core.volumetrics import get_asset_volumetrics

def render_tab(dq_results, frames):
    asset_vol = get_asset_volumetrics(frames)
    hoc_cards = render_asset_volumetrics_card(asset_vol['HOC'])
    hol_cards = render_asset_volumetrics_card(asset_vol['HOL'])

    return html.Div([
        render_dimension_scorecard(dq_results),
        html.Div(style={'marginBottom': '24px'}, children=[
            html.Div(style={'display': 'flex', 'gap': '20px', 'marginBottom': '20px'}, children=hoc_cards),
            html.Div(style={'display': 'flex', 'gap': '20px'}, children=hol_cards),
        ]),
        render_dimension_grid(dq_results),
        render_dimensions_table(dq_results),
        html.Div(id='dim-drill-down-container', style={'marginTop': '24px'})
    ])