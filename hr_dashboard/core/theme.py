# ═══════════════════════════════════════════════════════════════════════════════
# theme.py  —  All visual design tokens: colours, styles, chart config.
#
#  One-off bid-demo build (Veran Performance x Royal Mail). Mirrors the design
#  language of the Parliament finance dashboard's theme.py, restyled around
#  Royal Mail's brand red instead of HOC/HOL green/red.
#
#  Nothing in here affects data logic — it is purely cosmetic.
# ═══════════════════════════════════════════════════════════════════════════════

DISPLAY_FONT = "'Inter', sans-serif"

RAG_HEX = {
    'Red':   '#c0392b',
    'Amber': '#d4820a',
    'Green': '#1a7a4a',
}

SEV_HEX = {
    'Critical': '#c0392b',
    'High':     '#d4820a',
    'Medium':   '#e6a817',
    'Low':      '#7c5cbf',
}

# Single-entity dataset (no HOC/HOL-style split) — one brand-coloured chip
# reused everywhere the shared scorecard/grid components expect a "house".
HOUSE_HEX = {
    'Royal Mail Group': '#CC092F',  # Royal Mail red
}

UI = {
    'page_bg':        '#f4f2f0',
    'card_bg':        '#ffffff',
    'card_bg_dark':   '#f4f2f0',
    'border':         '#e3dcd6',

    'header_start':   '#1a1a1a',
    'header_end':     '#1a1a1a',
    'header_subtitle':'#d9a5ac',
    'header_muted':   '#a0a0a0',

    'text_primary':   '#1a1a1a',
    'text_secondary': '#5c5450',
    'text_accent':    '#f4f3f7',

    'tab_unselected': '#a0a0a0',
    'tab_indicator':  '#CC092F',
    'tab_action':     '#CC092F',

    'purple_mid':     '#CC092F',
    'purple_light':   '#fbe7ea',

    'modal_chrome_bg':   '#f4f2f0',
    'modal_border':      '#1a1a1a',
}

CHART_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(family="'Inter', sans-serif", color='#5c5450', size=12),
)

PLOTLY_STATIC_CONFIG = {'displayModeBar': False, 'scrollZoom': False, 'staticPlot': True}
PLOTLY_HOVER_CONFIG  = {'displayModeBar': False, 'scrollZoom': False, 'staticPlot': False}

APP_TITLE = 'Royal Mail HR & Payroll DQA | Veran Performance'
