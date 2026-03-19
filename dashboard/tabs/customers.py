from dash import html
from dashboard.shared.ui import render_volumetrics_card
from dashboard.shared.dimensions import render_dimension_scorecard, render_dimension_grid, render_dimensions_table
from dashboard.tabs.aging import render_aging
from dashboard.data_engine import build_aging_analysis
from dashboard.core.volumetrics import get_ar_volumetrics

def render_tab(dq_results, frames):
    ar_vol = get_ar_volumetrics(frames)
    hoc_cards = render_volumetrics_card(ar_vol['HOC'], 'Customer Master')
    hol_cards = render_volumetrics_card(ar_vol['HOL'], 'Customer Master')
    
    # We need aging results
    aging_results = build_aging_analysis(frames)
    
    return html.Div([
        render_dimension_scorecard(dq_results),
        html.Div(style={'marginBottom': '24px'}, children=[
            html.Div(style={'display': 'flex', 'gap': '20px', 'marginBottom': '20px'}, children=hoc_cards),
            html.Div(style={'display': 'flex', 'gap': '20px'}, children=hol_cards),
        ]),
        render_dimension_grid(dq_results),
        render_dimensions_table(dq_results),
        render_aging(aging_results, module='ar'),
        html.Div(id='dim-drill-down-container', style={'marginTop': '24px'})
    ])
