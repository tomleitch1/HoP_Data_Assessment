from dash import html
from dashboard.shared.dimensions import render_dimension_scorecard, render_dimension_grid
from dashboard.core.volumetrics import get_ar_volumetrics
from dashboard.core.theme import UI, HOUSE_HEX, DISPLAY_FONT
from dashboard.tabs.aging import render_aging
from dashboard.data_engine import build_aging_analysis

# ── Design tokens ─────────────────────────────────────────────────────────────
_HDR     = '#0f2744'
_HDR2    = '#0a1e35'
_SEQ_BG  = '#1a3a5c'
_CUS_BG  = '#091825'
_SEQ_TXT = '#a8c8e8'
_CUS_TXT = '#5a7a9a'
_BODY_BG = '#ffffff'
_BAR_BG  = '#e8f0f8'
_DIV     = '#1e3550'

# ── Status visual config (AR statuses) ───────────────────────────────────────
_STATUS = {
    'N': {'color': '#1a7a4a', 'label': 'Normal',       'risk': None},
    'H': {'color': '#c0711b', 'label': 'On Hold',       'risk': 'medium'},
    'P': {'color': '#c0392b', 'label': 'Parked',        'risk': 'high'},
    'T': {'color': '#d4820a', 'label': 'Terminated',    'risk': 'medium'},
    'R': {'color': '#d4820a', 'label': 'On Proposal',   'risk': None},
    'I': {'color': '#4a7cbf', 'label': 'Identified',    'risk': None},
}


def _fmt_bal(v):
    sign = '-' if v < 0 else ''
    a = abs(v)
    if a >= 1_000_000:
        return f'{sign}£{a / 1_000_000:.1f}m'
    if a >= 1_000:
        return f'{sign}£{a / 1_000:.0f}k'
    return f'{sign}£{a:,.0f}'


def _badge(text, bg, color):
    return html.Span(text, style={
        'background': bg, 'color': color,
        'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.1em',
        'padding': '3px 9px', 'borderRadius': '4px',
        'textTransform': 'uppercase', 'display': 'inline-block', 'lineHeight': '1.6',
    })


def _card_header(seq, name, source, filter_desc, type_label, is_mig, right_content=None):
    left = html.Div(style={'flex': '1'}, children=[
        html.Div(style={
            'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'marginBottom': '10px',
        }, children=[
            _badge(f'SEQ {seq}', _SEQ_BG, _SEQ_TXT) if seq else None,
            _badge(type_label, _SEQ_BG if is_mig else _CUS_BG, _SEQ_TXT if is_mig else _CUS_TXT),
        ]),
        html.Div(name, style={
            'fontSize': '15px', 'fontWeight': '700', 'color': '#f0f6fc',
            'lineHeight': '1.3', 'marginBottom': '8px',
        }),
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '6px'}, children=[
            html.Span(source, style={
                'fontSize': '11px', 'color': '#7090b8',
                'fontFamily': "'Courier New', monospace",
                'background': '#071220', 'padding': '2px 7px', 'borderRadius': '3px',
            }),
            html.Span('·', style={'color': '#3a5a78', 'fontSize': '12px'}),
            html.Span(filter_desc, style={'fontSize': '11px', 'color': _CUS_TXT}),
        ]),
    ])
    return html.Div(style={
        'background': _HDR if is_mig else _HDR2,
        'padding': '18px 28px',
        'display': 'flex', 'alignItems': 'flex-start', 'gap': '24px',
    }, children=[left, right_content] if right_content else [left])


def _status_bar_row(status, count, total):
    cfg   = _STATUS.get(status, {'color': '#94a3b8', 'label': status, 'risk': None})
    pct   = (count / total * 100) if total > 0 else 0
    color = cfg['color']
    risk  = cfg['risk']
    return html.Div(style={
        'display': 'flex', 'alignItems': 'center', 'gap': '10px', 'padding': '5px 0',
    }, children=[
        html.Span(status, style={
            'background': color + '1a', 'color': color,
            'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.06em',
            'padding': '2px 7px', 'borderRadius': '3px',
            'minWidth': '22px', 'textAlign': 'center',
        }),
        html.Span(cfg['label'], style={
            'fontSize': '11px', 'color': UI['text_secondary'], 'minWidth': '88px',
        }),
        html.Div(style={
            'flex': '1', 'height': '7px', 'background': _BAR_BG,
            'borderRadius': '4px', 'overflow': 'hidden',
        }, children=[
            html.Div(style={
                'height': '100%',
                'width': f'{min(pct, 100):.1f}%',
                'background': color, 'borderRadius': '4px',
                'minWidth': '3px' if count > 0 else '0',
            })
        ]),
        html.Span(f'{count:,}', style={
            'fontSize': '12px', 'fontWeight': '700',
            'minWidth': '48px', 'textAlign': 'right',
            'color': color if risk == 'high' else UI['text_primary'],
        }),
        html.Span(f'{pct:.0f}%', style={
            'fontSize': '10px', 'color': UI['text_secondary'], 'minWidth': '34px',
        }),
        html.Span('⚠', style={'color': color, 'fontSize': '12px', 'minWidth': '14px'})
        if risk == 'high' else html.Div(style={'minWidth': '14px'}),
    ])


def _balance_bar_row(status, bal, total_b):
    cfg   = _STATUS.get(status, {'color': '#94a3b8', 'label': status, 'risk': None})
    pct   = (abs(bal) / abs(total_b) * 100) if total_b != 0 else 0
    color = cfg['color']
    risk  = cfg['risk']
    return html.Div(style={
        'display': 'flex', 'alignItems': 'center', 'gap': '10px', 'padding': '5px 0',
    }, children=[
        html.Span(status, style={
            'background': color + '1a', 'color': color,
            'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.06em',
            'padding': '2px 7px', 'borderRadius': '3px',
            'minWidth': '22px', 'textAlign': 'center',
        }),
        html.Span(cfg['label'], style={
            'fontSize': '11px', 'color': UI['text_secondary'], 'minWidth': '88px',
        }),
        html.Div(style={
            'flex': '1', 'height': '7px', 'background': _BAR_BG,
            'borderRadius': '4px', 'overflow': 'hidden',
        }, children=[
            html.Div(style={
                'height': '100%',
                'width': f'{min(pct, 100):.1f}%',
                'background': color,
                'borderRadius': '4px',
                'minWidth': '3px' if bal > 0 else '0',
            })
        ]),
        html.Span(_fmt_bal(bal), style={
            'fontSize': '12px', 'fontWeight': '700',
            'minWidth': '52px', 'textAlign': 'right',
            'color': color if risk == 'high' else UI['text_primary'],
        }),
        html.Span(f'{pct:.0f}%', style={
            'fontSize': '10px', 'color': UI['text_secondary'], 'minWidth': '34px',
        }),
        html.Div(style={'minWidth': '14px'}),
    ])


def _section_label(text):
    return html.Div(text, style={
        'fontSize': '10px', 'fontWeight': '700', 'color': UI['text_secondary'],
        'textTransform': 'uppercase', 'letterSpacing': '0.08em', 'marginBottom': '10px',
    })


# ── Seq 11 column ─────────────────────────────────────────────────────────────

def _seq11_col(house, m):
    colour   = HOUSE_HEX[house]
    total    = m.get('total', 0)
    active   = m.get('active', 0)
    inc_rec  = m.get('inactive_recent', 0)
    in_scope = m.get('migration_scope', 0)
    archive  = m.get('archive', 0)
    sb       = m.get('status_breakdown', {})

    scope_pct = int(in_scope / total * 100) if total else 0

    status_rows = [
        _status_bar_row(s, sb.get(s, 0), in_scope)
        for s in ['N', 'P', 'T']
        if sb.get(s, 0) > 0
    ]

    return html.Div(style={
        'flex': '1', 'padding': '28px 36px',
        'borderRight': f'1px solid {UI["border"]}' if house == 'HOC' else 'none',
    }, children=[

        html.Div(house, style={
            'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.15em',
            'color': colour, 'textTransform': 'uppercase', 'marginBottom': '6px',
        }),

        html.Div(style={
            'display': 'flex', 'alignItems': 'baseline', 'gap': '12px', 'marginBottom': '6px',
        }, children=[
            html.Span(f'{in_scope:,}', style={
                'fontSize': '52px', 'fontWeight': '900', 'lineHeight': '1',
                'color': UI['text_primary'], 'fontFamily': DISPLAY_FONT,
                'letterSpacing': '-0.03em',
            }),
            html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '2px'}, children=[
                html.Span('in migration scope', style={
                    'fontSize': '12px', 'fontWeight': '600', 'color': UI['text_primary'],
                }),
                html.Span(f'of {total:,} extracted  ({scope_pct}%)', style={
                    'fontSize': '11px', 'color': UI['text_secondary'],
                }),
            ]),
        ]),

        html.Div(style={
            'height': '4px', 'background': UI['border'],
            'borderRadius': '2px', 'marginBottom': '24px',
        }, children=[
            html.Div(style={
                'height': '100%', 'width': f'{scope_pct}%',
                'background': colour, 'borderRadius': '2px',
            })
        ]),

        _section_label('Scope composition'),
        html.Div(style={
            'display': 'flex', 'gap': '12px', 'marginBottom': '24px',
        }, children=[
            html.Div(style={
                'flex': '1', 'padding': '12px 16px',
                'background': colour + '0d', 'borderRadius': '8px',
                'border': f'1px solid {colour}30',
            }, children=[
                html.Div(f'{active:,}', style={
                    'fontSize': '22px', 'fontWeight': '900',
                    'color': colour, 'fontFamily': DISPLAY_FONT,
                }),
                html.Div('Active  (status ≠ C)', style={
                    'fontSize': '11px', 'color': UI['text_secondary'], 'marginTop': '2px',
                }),
            ]),
            html.Div(style={
                'flex': '1', 'padding': '12px 16px',
                'background': UI['purple_light'], 'borderRadius': '8px',
                'border': f'1px solid {UI["border"]}',
            }, children=[
                html.Div(f'{inc_rec:,}', style={
                    'fontSize': '22px', 'fontWeight': '900',
                    'color': UI['text_primary'], 'fontFamily': DISPLAY_FONT,
                }),
                html.Div('Inactive + recent history', style={
                    'fontSize': '11px', 'color': UI['text_secondary'], 'marginTop': '2px',
                }),
            ]),
        ]),

        _section_label('Status breakdown  (in-scope population)'),
        html.Div(style={'marginBottom': '20px'}, children=status_rows if status_rows else [
            html.Div('No status data available', style={
                'fontSize': '12px', 'color': UI['text_secondary'], 'fontStyle': 'italic',
            })
        ]),

        html.Div(style={
            'borderTop': f'1px dashed {UI["border"]}', 'paddingTop': '14px',
            'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
        }, children=[
            html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '2px'}, children=[
                html.Span('Archive candidates', style={
                    'fontSize': '12px', 'color': UI['text_secondary'],
                }),
                html.Span('Status C — no recent history', style={
                    'fontSize': '10px', 'color': UI['text_secondary'], 'opacity': '0.7',
                }),
            ]),
            html.Span(f'{archive:,}', style={
                'fontSize': '18px', 'fontWeight': '700',
                'color': UI['text_secondary'], 'fontFamily': DISPLAY_FONT,
            }),
        ]),
    ])


# ── Seq 17/18 AR invoices column ──────────────────────────────────────────────

def _seq17_col(house, t):
    colour   = HOUSE_HEX[house]
    count    = t.get('open_count', 0)
    sb       = t.get('status_breakdown', {})
    bb       = t.get('balance_by_status', {})
    statuses = [s for s in ['N', 'H', 'R', 'I', 'P'] if sb.get(s, 0) > 0]
    total_b  = sum(bb.get(s, 0.0) for s in statuses)

    return html.Div(style={
        'flex': '1', 'padding': '24px 28px',
        'borderRight': f'1px solid {UI["border"]}' if house == 'HOC' else 'none',
    }, children=[

        html.Div(house, style={
            'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.15em',
            'color': colour, 'textTransform': 'uppercase', 'marginBottom': '8px',
        }),

        html.Div(style={
            'display': 'flex', 'alignItems': 'baseline', 'gap': '8px', 'marginBottom': '22px',
        }, children=[
            html.Span(f'{count:,}', style={
                'fontSize': '42px', 'fontWeight': '900', 'lineHeight': '1',
                'color': UI['text_primary'], 'fontFamily': DISPLAY_FONT,
                'letterSpacing': '-0.02em',
            }),
            html.Span('open AR items', style={'fontSize': '12px', 'color': UI['text_secondary']}),
        ]),

        _section_label('Count by status'),
        html.Div(
            [_status_bar_row(s, sb.get(s, 0), count) for s in statuses],
            style={'marginBottom': '20px'},
        ) if statuses else html.Div(),

        _section_label('Outstanding balance by status'),
        html.Div([_balance_bar_row(s, bb.get(s, 0.0), total_b) for s in statuses]) if statuses else html.Div(),
    ])


# ── History note ──────────────────────────────────────────────────────────────

def _history_note(hoc_h, hol_h):
    hoc_total = hoc_h.get('total', 0)
    hol_total = hol_h.get('total', 0)
    return html.Div(style={
        'borderLeft': f'1px solid {_DIV}', 'paddingLeft': '20px',
        'display': 'flex', 'flexDirection': 'column', 'justifyContent': 'center',
        'minWidth': '180px',
    }, children=[
        html.Div('Scoping extract', style={
            'fontSize': '9px', 'fontWeight': '700', 'color': _CUS_TXT,
            'textTransform': 'uppercase', 'letterSpacing': '0.1em', 'marginBottom': '8px',
        }),
        html.Span('acuhistr  ·  18 months', style={
            'fontSize': '10px', 'color': '#7090b8',
            'fontFamily': "'Courier New', monospace",
            'background': '#071220', 'padding': '2px 6px',
            'borderRadius': '3px', 'display': 'inline-block', 'marginBottom': '10px',
        }),
        *[
            html.Div(style={'display': 'flex', 'justifyContent': 'space-between', 'gap': '16px', 'marginBottom': '4px'}, children=[
                html.Span(house, style={
                    'fontSize': '10px', 'fontWeight': '700',
                    'color': HOUSE_HEX[house], 'letterSpacing': '0.08em',
                }),
                html.Span(f'{count:,}', style={
                    'fontSize': '12px', 'fontWeight': '700', 'color': '#a8c8e8',
                    'fontFamily': DISPLAY_FONT,
                }),
            ])
            for house, count in [('HOC', hoc_total), ('HOL', hol_total)]
        ],
        html.Div('closed transactions', style={
            'fontSize': '10px', 'color': '#3a5a78', 'marginTop': '2px',
        }),
    ])


# ── Total migration banner ────────────────────────────────────────────────────

def _migration_footer(hoc_m, hol_m, hoc_t, hol_t):

    def _house_row(house, m, t, border_bottom):
        colour    = HOUSE_HEX[house]
        customers = m.get('migration_scope', 0)
        invoices  = t.get('open_count', 0)
        total     = customers + invoices

        items = [
            ('Seq 11  ·  Customers',    customers),
            ('Seq 17/18  ·  Open AR',   invoices),
        ]

        return html.Div(style={
            'display': 'flex', 'alignItems': 'center',
            'padding': '16px 28px',
            'borderBottom': f'1px solid {UI["border"]}' if border_bottom else 'none',
        }, children=[

            html.Div(style={
                'background': colour, 'borderRadius': '4px',
                'padding': '4px 10px', 'marginRight': '24px',
            }, children=[
                html.Span(house, style={
                    'fontSize': '11px', 'fontWeight': '800',
                    'color': '#ffffff', 'letterSpacing': '0.1em',
                }),
            ]),

            html.Div(style={
                'display': 'flex', 'gap': '48px', 'flex': '1', 'alignItems': 'center',
            }, children=[
                html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '2px'}, children=[
                    html.Span(f'{cnt:,}', style={
                        'fontSize': '20px', 'fontWeight': '800',
                        'color': UI['text_primary'], 'fontFamily': DISPLAY_FONT, 'lineHeight': '1',
                    }),
                    html.Span(label, style={
                        'fontSize': '10px', 'color': UI['text_secondary'], 'letterSpacing': '0.04em',
                    }),
                ]) for label, cnt in items
            ]),

            html.Div(style={
                'width': '1px', 'height': '36px',
                'background': UI['border'], 'margin': '0 28px',
            }),

            html.Div(style={'textAlign': 'right', 'minWidth': '120px'}, children=[
                html.Div(f'{total:,}', style={
                    'fontSize': '30px', 'fontWeight': '900', 'lineHeight': '1',
                    'color': colour, 'fontFamily': DISPLAY_FONT, 'letterSpacing': '-0.02em',
                }),
                html.Div('total records', style={
                    'fontSize': '11px', 'color': UI['text_secondary'], 'marginTop': '3px',
                }),
            ]),
        ])

    return html.Div(style={
        'borderRadius': '10px', 'overflow': 'hidden',
        'border': f'1px solid {UI["border"]}',
        'boxShadow': '0 2px 8px rgba(15,39,68,0.08)',
        'background': UI['card_bg'], 'marginTop': '16px',
    }, children=[
        html.Div(style={
            'padding': '14px 28px',
            'borderBottom': f'1px solid {_DIV}',
            'display': 'flex', 'alignItems': 'center', 'gap': '12px',
            'background': _HDR,
        }, children=[
            _badge('Scope', _SEQ_BG, _SEQ_TXT),
            html.Span('Total Migration', style={
                'fontSize': '13px', 'fontWeight': '700', 'color': '#f0f6fc',
            }),
            html.Span('Seq 11  +  Seq 17/18', style={
                'fontSize': '11px', 'color': _CUS_TXT, 'marginLeft': 'auto',
            }),
        ]),
        _house_row('HOC', hoc_m, hoc_t, border_bottom=True),
        _house_row('HOL', hol_m, hol_t, border_bottom=False),
    ])


# ── Intro assembly ────────────────────────────────────────────────────────────

def _render_intro(ar_vol):
    hoc_m = ar_vol.get('HOC', {}).get('master', {})
    hol_m = ar_vol.get('HOL', {}).get('master', {})
    hoc_t = ar_vol.get('HOC', {}).get('transactions', {})
    hol_t = ar_vol.get('HOL', {}).get('transactions', {})
    hoc_h = ar_vol.get('HOC', {}).get('history', {})
    hol_h = ar_vol.get('HOL', {}).get('history', {})

    def _card(children):
        return html.Div(style={
            'borderRadius': '10px', 'overflow': 'hidden',
            'border': f'1px solid {UI["border"]}',
            'boxShadow': '0 2px 12px rgba(15,39,68,0.10)',
            'background': _BODY_BG,
        }, children=children)

    seq11 = _card([
        _card_header('11', 'Customers (Headers & Sites)', 'acuheader',
                     'Full population — no status filter', 'Migration Object', True,
                     right_content=_history_note(hoc_h, hol_h)),
        html.Div(style={'display': 'flex'}, children=[
            _seq11_col('HOC', hoc_m),
            _seq11_col('HOL', hol_m),
        ]),
    ])

    seq17 = _card([
        _card_header('17/18', 'Open AR Invoices & On-Account Receipts', 'acutrans',
                     'Open only — status ≠ C', 'Migration Object', True),
        html.Div(style={'display': 'flex'}, children=[
            _seq17_col('HOC', hoc_t),
            _seq17_col('HOL', hol_t),
        ]),
    ])

    return html.Div(style={'marginBottom': '28px'}, children=[
        html.Div(style={
            'display': 'flex', 'alignItems': 'baseline', 'gap': '10px', 'marginBottom': '14px',
        }, children=[
            html.Div('Migration Scope', style={
                'fontSize': '13px', 'fontWeight': '800', 'color': UI['text_primary'],
                'textTransform': 'uppercase', 'letterSpacing': '0.01em',
            }),
            html.Div('Extracts aligned to programme scope objects', style={
                'fontSize': '12px', 'color': UI['text_secondary'],
            }),
        ]),
        html.Div(style={'marginBottom': '16px'}, children=[seq11]),
        seq17,
        _migration_footer(hoc_m, hol_m, hoc_t, hol_t),
    ])


# ── DQ section header ─────────────────────────────────────────────────────────

def _dq_section_header():
    return html.Div(style={
        'display': 'flex', 'alignItems': 'baseline', 'gap': '10px',
        'margin': '32px 0 14px',
        'paddingTop': '8px',
        'borderTop': f'1px solid {UI["border"]}',
    }, children=[
        html.Div('Data Quality Checks', style={
            'fontSize': '13px', 'fontWeight': '800', 'color': UI['text_primary'],
            'textTransform': 'uppercase', 'letterSpacing': '0.01em',
        }),
        html.Div('DQ rules applied against the extracted population', style={
            'fontSize': '12px', 'color': UI['text_secondary'],
        }),
    ])


# ── Tab renderer ──────────────────────────────────────────────────────────────

def render_tab(dq_results, frames):
    ar_vol = get_ar_volumetrics(frames)

    return html.Div([
        _render_intro(ar_vol),
        _dq_section_header(),
        render_dimension_scorecard(dq_results),
        render_dimension_grid(dq_results),
        html.Div(id='dim-drill-down-container', style={'marginTop': '24px'}),
    ])
