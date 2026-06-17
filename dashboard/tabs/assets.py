from dash import html
import pandas as pd
from dashboard.shared.dimensions import render_dimension_scorecard, render_dimension_grid, render_dimensions_table
from dashboard.core.theme import UI, HOUSE_HEX, DISPLAY_FONT

# ── Design tokens (warm amber — distinct from supplier purple / customer blue) ─
_HDR     = '#1f1a0f'
_HDR2    = '#181408'
_SEQ_BG  = '#3d2d0a'
_AST_BG  = '#150f04'
_SEQ_TXT = '#e8b86a'
_AST_TXT = '#7a6030'
_BODY_BG = '#ffffff'
_BAR_BG  = '#f5eedc'
_DIV     = '#3a2f18'

# ── Status visual config ───────────────────────────────────────────────────────
_STATUS = {
    'N': {'color': '#1a7a4a', 'label': 'Normal',      'risk': None},
    'T': {'color': '#c07820', 'label': 'Transferred',  'risk': None},
    'C': {'color': '#94a3b8', 'label': 'Closed',       'risk': None},
}

# ── Depreciation method config ─────────────────────────────────────────────────
_METHODS = {
    'LIN': {'color': '#1a7a4a', 'label': 'Straight-line'},
    'BAL': {'color': '#3a7abf', 'label': 'Reducing balance'},
    'EXP': {'color': '#c07820', 'label': 'Expanding'},
    'SYD': {'color': '#7c5cbf', 'label': 'Sum-of-years digits'},
}


# ── Shared helpers ─────────────────────────────────────────────────────────────

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
            _badge(type_label, _SEQ_BG if is_mig else _AST_BG, _SEQ_TXT if is_mig else _AST_TXT),
        ]),
        html.Div(name, style={
            'fontSize': '15px', 'fontWeight': '700', 'color': '#f8f0e0',
            'lineHeight': '1.3', 'marginBottom': '8px',
        }),
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '6px'}, children=[
            html.Span(source, style={
                'fontSize': '11px', 'color': '#c09060',
                'fontFamily': "'Courier New', monospace",
                'background': '#0f0a04', 'padding': '2px 7px', 'borderRadius': '3px',
            }),
            html.Span('·', style={'color': '#5a4a28', 'fontSize': '12px'}),
            html.Span(filter_desc, style={'fontSize': '11px', 'color': _AST_TXT}),
        ]),
    ])
    return html.Div(style={
        'background': _HDR if is_mig else _HDR2,
        'padding': '18px 28px',
        'display': 'flex', 'alignItems': 'flex-start', 'gap': '24px',
    }, children=[left, right_content] if right_content else [left])


def _section_label(text):
    return html.Div(text, style={
        'fontSize': '10px', 'fontWeight': '700', 'color': UI['text_secondary'],
        'textTransform': 'uppercase', 'letterSpacing': '0.08em', 'marginBottom': '10px',
    })


def _status_bar_row(status, count, total):
    cfg   = _STATUS.get(status, {'color': '#94a3b8', 'label': status, 'risk': None})
    pct   = (count / total * 100) if total > 0 else 0
    color = cfg['color']
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
            'color': UI['text_primary'],
        }),
        html.Span(f'{pct:.0f}%', style={
            'fontSize': '10px', 'color': UI['text_secondary'], 'minWidth': '34px',
        }),
        html.Div(style={'minWidth': '14px'}),
    ])


def _method_bar_row(method, count, total):
    cfg   = _METHODS.get(method, {'color': '#94a3b8', 'label': method})
    pct   = (count / total * 100) if total > 0 else 0
    color = cfg['color']
    return html.Div(style={
        'display': 'flex', 'alignItems': 'center', 'gap': '10px', 'padding': '5px 0',
    }, children=[
        html.Span(method, style={
            'background': color + '1a', 'color': color,
            'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.06em',
            'padding': '2px 7px', 'borderRadius': '3px',
            'minWidth': '34px', 'textAlign': 'center',
        }),
        html.Span(cfg['label'], style={
            'fontSize': '11px', 'color': UI['text_secondary'], 'minWidth': '130px',
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
            'color': UI['text_primary'],
        }),
        html.Span(f'{pct:.0f}%', style={
            'fontSize': '10px', 'color': UI['text_secondary'], 'minWidth': '34px',
        }),
        html.Div(style={'minWidth': '14px'}),
    ])


# ── Data extraction ────────────────────────────────────────────────────────────

def get_asset_intro_data(frames):
    am = frames.get('asset_master', pd.DataFrame())
    ad = frames.get('asset_depreciation', pd.DataFrame())
    ag = frames.get('asset_groups', pd.DataFrame())

    result = {}
    for house in ['HOC', 'HOL']:
        h_am = am[am['house'] == house] if not am.empty else pd.DataFrame()
        h_ad = ad[ad['house'] == house] if not ad.empty else pd.DataFrame()
        h_ag = ag[ag['house'] == house] if not ag.empty else pd.DataFrame()

        # ── Seq 12 — asset master ──────────────────────────────────────────────
        total        = len(h_am)
        status_counts = h_am['status'].value_counts().to_dict() if total > 0 else {}
        normal       = status_counts.get('N', 0)
        transferred  = status_counts.get('T', 0)
        archive      = status_counts.get('C', 0)
        in_scope     = normal + transferred

        grant_funded = 0
        if total > 0 and 'grant_flag' in h_am.columns:
            grant_funded = int((pd.to_numeric(h_am['grant_flag'], errors='coerce') == 1).sum())

        # ── Seq 13 — depreciation configuration ───────────────────────────────
        total_books      = len(h_ad)
        method_breakdown = h_ad['depr_method'].value_counts().to_dict() if total_books > 0 else {}

        multi_book = 0
        if total_books > 0:
            multi_book = int(
                h_ad.groupby('asset_id').size().gt(1).sum()
            )

        indexed = 0
        if total_books > 0 and 'index_id' in h_ad.columns:
            indexed = int(
                h_ad[h_ad['index_id'].notna() & (h_ad['index_id'].astype(str).str.strip() != '')]
                ['asset_id'].nunique()
            )

        # Assets in master with no depreciation record at all
        assets_in_master = set(h_am['asset_id'].tolist()) if total > 0 else set()
        assets_with_depr = set(h_ad['asset_id'].tolist()) if total_books > 0 else set()
        assets_without_depr = len(assets_in_master - assets_with_depr)

        # Per-asset configuration overrides vs group defaults
        method_overrides  = 0
        lifetime_overrides = 0
        if total_books > 0 and not h_am.empty and not h_ag.empty and 'asset_group' in h_am.columns:
            merged = (
                h_ad
                .merge(h_am[['asset_id', 'asset_group']].drop_duplicates('asset_id'),
                       on='asset_id', how='left')
                .merge(h_ag[['asset_group', 'depr_method', 'lifetime']].drop_duplicates('asset_group'),
                       on='asset_group', how='inner', suffixes=('', '_grp'))
            )
            if 'depr_method_grp' in merged.columns:
                method_overrides = int((merged['depr_method'] != merged['depr_method_grp']).sum())
            if 'lifetime_grp' in merged.columns and 'lifetime' in merged.columns:
                both_present = merged['lifetime'].notna() & merged['lifetime_grp'].notna()
                lifetime_overrides = int(
                    (merged.loc[both_present, 'lifetime'] != merged.loc[both_present, 'lifetime_grp']).sum()
                )

        result[house] = {
            'master': {
                'total':            total,
                'migration_scope':  in_scope,
                'active':           normal,
                'transferred':      transferred,
                'archive':          archive,
                'status_breakdown': status_counts,
                'grant_funded':     grant_funded,
            },
            'depr': {
                'total_books':        total_books,
                'method_breakdown':   method_breakdown,
                'multi_book':         multi_book,
                'indexed':            indexed,
                'assets_without_depr': assets_without_depr,
                'method_overrides':   method_overrides,
                'lifetime_overrides': lifetime_overrides,
            },
        }
    return result


# ── Seq 12 column — Fixed Asset Registry ──────────────────────────────────────

def _seq12_col(house, m):
    colour      = HOUSE_HEX[house]
    total       = m.get('total', 0)
    in_scope    = m.get('migration_scope', 0)
    normal      = m.get('active', 0)
    transferred = m.get('transferred', 0)
    archive     = m.get('archive', 0)
    sb          = m.get('status_breakdown', {})
    grant       = m.get('grant_funded', 0)

    scope_pct = int(in_scope / total * 100) if total else 0

    status_rows = [
        _status_bar_row(s, sb.get(s, 0), in_scope)
        for s in ['N', 'T']
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
                html.Div(f'{normal:,}', style={
                    'fontSize': '22px', 'fontWeight': '900',
                    'color': colour, 'fontFamily': DISPLAY_FONT,
                }),
                html.Div('Active  (status N)', style={
                    'fontSize': '11px', 'color': UI['text_secondary'], 'marginTop': '2px',
                }),
            ]),
            html.Div(style={
                'flex': '1', 'padding': '12px 16px',
                'background': UI['purple_light'], 'borderRadius': '8px',
                'border': f'1px solid {UI["border"]}',
            }, children=[
                html.Div(f'{transferred:,}', style={
                    'fontSize': '22px', 'fontWeight': '900',
                    'color': UI['text_primary'], 'fontFamily': DISPLAY_FONT,
                }),
                html.Div('Transferred  (status T)', style={
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
        }, children=[
            html.Div(style={
                'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
                'marginBottom': '8px',
            }, children=[
                html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '2px'}, children=[
                    html.Span('Archive candidates', style={
                        'fontSize': '12px', 'color': UI['text_secondary'],
                    }),
                    html.Span('Status C — disposed or written off', style={
                        'fontSize': '10px', 'color': UI['text_secondary'], 'opacity': '0.7',
                    }),
                ]),
                html.Span(f'{archive:,}', style={
                    'fontSize': '18px', 'fontWeight': '700',
                    'color': UI['text_secondary'], 'fontFamily': DISPLAY_FONT,
                }),
            ]),
            html.Div(style={
                'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
            }, children=[
                html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '2px'}, children=[
                    html.Span('Grant-funded assets', style={
                        'fontSize': '12px', 'color': UI['text_secondary'],
                    }),
                    html.Span('Require special handling at migration', style={
                        'fontSize': '10px', 'color': UI['text_secondary'], 'opacity': '0.7',
                    }),
                ]),
                html.Span(f'{grant:,}', style={
                    'fontSize': '18px', 'fontWeight': '700',
                    'color': '#c07820' if grant > 0 else UI['text_secondary'],
                    'fontFamily': DISPLAY_FONT,
                }),
            ]),
        ]),
    ])


# ── Seq 13 column — Depreciation Rules ────────────────────────────────────────

def _seq13_col(house, d):
    colour      = HOUSE_HEX[house]
    total_books = d.get('total_books', 0)
    mb          = d.get('method_breakdown', {})
    multi_book  = d.get('multi_book', 0)
    indexed     = d.get('indexed', 0)
    no_depr     = d.get('assets_without_depr', 0)
    m_overrides = d.get('method_overrides', 0)
    l_overrides = d.get('lifetime_overrides', 0)

    method_rows = [
        _method_bar_row(m, mb.get(m, 0), total_books)
        for m in ['LIN', 'BAL', 'EXP', 'SYD']
        if mb.get(m, 0) > 0
    ]

    def _complexity_row(label, sublabel, value, color):
        return html.Div(style={
            'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
            'padding': '6px 0', 'borderBottom': f'1px solid {UI["border"]}',
        }, children=[
            html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '1px'}, children=[
                html.Span(label, style={'fontSize': '12px', 'color': UI['text_primary']}),
                html.Span(sublabel, style={
                    'fontSize': '10px', 'color': UI['text_secondary'], 'opacity': '0.8',
                }),
            ]),
            html.Span(f'{value:,}', style={
                'fontSize': '16px', 'fontWeight': '800',
                'color': color, 'fontFamily': DISPLAY_FONT,
            }),
        ])

    return html.Div(style={
        'flex': '1', 'padding': '28px 36px',
        'borderRight': f'1px solid {UI["border"]}' if house == 'HOC' else 'none',
    }, children=[

        html.Div(house, style={
            'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.15em',
            'color': colour, 'textTransform': 'uppercase', 'marginBottom': '6px',
        }),

        html.Div(style={
            'display': 'flex', 'alignItems': 'baseline', 'gap': '10px', 'marginBottom': '22px',
        }, children=[
            html.Span(f'{total_books:,}', style={
                'fontSize': '40px', 'fontWeight': '900', 'lineHeight': '1',
                'color': UI['text_primary'], 'fontFamily': DISPLAY_FONT,
                'letterSpacing': '-0.02em',
            }),
            html.Span('depreciation books', style={'fontSize': '12px', 'color': UI['text_secondary']}),
        ]),

        _section_label('Method breakdown'),
        html.Div(style={'marginBottom': '24px'}, children=method_rows if method_rows else [
            html.Div('No depreciation data available', style={
                'fontSize': '12px', 'color': UI['text_secondary'], 'fontStyle': 'italic',
            })
        ]),

        html.Div(style={'borderTop': f'1px dashed {UI["border"]}', 'paddingTop': '14px'}, children=[
            _section_label('Migration configuration complexity'),
            _complexity_row(
                'Method overrides', 'Asset-level method differs from group default',
                m_overrides, '#c07820' if m_overrides > 0 else UI['text_secondary'],
            ),
            _complexity_row(
                'Lifetime overrides', 'Asset-level useful life differs from group default',
                l_overrides, '#c07820' if l_overrides > 0 else UI['text_secondary'],
            ),
            _complexity_row(
                'Multi-book assets', 'Assets with more than one depreciation book',
                multi_book, '#3a7abf' if multi_book > 0 else UI['text_secondary'],
            ),
            _complexity_row(
                'Indexed assets', 'Linked to an indexation rate',
                indexed, UI['text_secondary'],
            ),
            html.Div(style={
                'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
                'padding': '6px 0',
            }, children=[
                html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '1px'}, children=[
                    html.Span('Assets without depreciation config', style={
                        'fontSize': '12px', 'color': UI['text_primary'],
                    }),
                    html.Span('In master but no depreciation record', style={
                        'fontSize': '10px', 'color': UI['text_secondary'], 'opacity': '0.8',
                    }),
                ]),
                html.Span(f'{no_depr:,}', style={
                    'fontSize': '16px', 'fontWeight': '800',
                    'color': '#c0392b' if no_depr > 0 else UI['text_secondary'],
                    'fontFamily': DISPLAY_FONT,
                }),
            ]),
        ]),
    ])


# ── Total migration footer ─────────────────────────────────────────────────────

def _migration_footer(hoc_m, hol_m, hoc_d, hol_d):
    def _house_row(house, m, d, border_bottom):
        colour = HOUSE_HEX[house]
        assets = m.get('migration_scope', 0)
        books  = d.get('total_books', 0)
        total  = assets + books
        items  = [
            ('Seq 12  ·  Fixed Assets',       assets),
            ('Seq 13  ·  Depreciation Books', books),
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
        'boxShadow': '0 2px 8px rgba(31,26,15,0.08)',
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
                'fontSize': '13px', 'fontWeight': '700', 'color': '#f8f0e0',
            }),
            html.Span('Seq 12  +  Seq 13', style={
                'fontSize': '11px', 'color': _AST_TXT, 'marginLeft': 'auto',
            }),
        ]),
        _house_row('HOC', hoc_m, hoc_d, border_bottom=True),
        _house_row('HOL', hol_m, hol_d, border_bottom=False),
    ])


# ── Intro assembly ─────────────────────────────────────────────────────────────

def _render_intro(intro_data):
    hoc_m = intro_data.get('HOC', {}).get('master', {})
    hol_m = intro_data.get('HOL', {}).get('master', {})
    hoc_d = intro_data.get('HOC', {}).get('depr', {})
    hol_d = intro_data.get('HOL', {}).get('depr', {})

    def _card(children):
        return html.Div(style={
            'borderRadius': '10px', 'overflow': 'hidden',
            'border': f'1px solid {UI["border"]}',
            'boxShadow': '0 2px 12px rgba(31,26,15,0.10)',
            'background': _BODY_BG,
        }, children=children)

    seq12 = _card([
        _card_header('12', 'Fixed Asset Registry', 'asset_master',
                     'Active + Transferred (N + T) in scope', 'Migration Object', True),
        html.Div(style={'display': 'flex'}, children=[
            _seq12_col('HOC', hoc_m),
            _seq12_col('HOL', hol_m),
        ]),
    ])

    seq13 = _card([
        _card_header('13', 'Asset Depreciation Rules', 'asset_depreciation  +  asset_groups',
                     'All active depreciation books', 'Migration Object', True),
        html.Div(style={'display': 'flex'}, children=[
            _seq13_col('HOC', hoc_d),
            _seq13_col('HOL', hol_d),
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
        html.Div(style={'marginBottom': '16px'}, children=[seq12]),
        seq13,
        _migration_footer(hoc_m, hol_m, hoc_d, hol_d),
    ])


# ── DQ section header ──────────────────────────────────────────────────────────

def _dq_section_header():
    return html.Div(style={
        'borderTop': f'1px solid {UI["border"]}',
        'paddingTop': '20px', 'marginBottom': '20px',
        'display': 'flex', 'alignItems': 'baseline', 'gap': '10px',
    }, children=[
        html.Div('Data Quality Checks', style={
            'fontSize': '13px', 'fontWeight': '800', 'color': UI['text_primary'],
            'textTransform': 'uppercase', 'letterSpacing': '0.01em',
        }),
        html.Div('All rule categories across asset register and configuration tables', style={
            'fontSize': '12px', 'color': UI['text_secondary'],
        }),
    ])


# ── Tab entry point ────────────────────────────────────────────────────────────

def render_tab(dq_results, frames):
    intro_data = get_asset_intro_data(frames)
    return html.Div([
        _render_intro(intro_data),
        _dq_section_header(),
        render_dimension_scorecard(dq_results),
        render_dimension_grid(dq_results),
        render_dimensions_table(dq_results),
        html.Div(id='dim-drill-down-container', style={'marginTop': '24px'}),
    ])
