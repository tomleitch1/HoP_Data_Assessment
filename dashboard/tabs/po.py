"""
Parliament Finance Systems Programme
Purchase Orders — Volumetrics & Procurement Insight
HoC only (HOL has no PO data).
"""

from dash import html, dcc
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from dashboard.core.theme import UI, DISPLAY_FONT, PLOTLY_HOVER_CONFIG, PLOTLY_STATIC_CONFIG

# ── Design tokens ─────────────────────────────────────────────────────────────
_HDR_BG    = '#0d1f2d'   # deep navy
_HDR2_BG   = '#102535'
_ACCENT    = '#0d9488'   # teal
_ACTIVE_C  = '#16a34a'   # green  — O/N/A statuses
_HIST_C    = '#64748b'   # slate  — F/C statuses
_WARN_C    = '#d97706'   # amber
_CARD_BG   = '#ffffff'
_CARD_BOR  = '#e2e8f0'
_PAGE_BG   = '#f4f7f9'
_BAR_TRACK = '#1e3448'
_BAR_TRACK_LIGHT = '#e8f0f6'
_DIV_COL   = '#1e3650'

# ── Status config (confirmed: C=Closed, O=Open; F/T meanings unconfirmed) ────
_STATUS_CFG = {
    'O': {'color': '#16a34a', 'label': 'Open',      'group': 'active'},
    'N': {'color': '#2563eb', 'label': 'New',        'group': 'active'},
    'A': {'color': '#0891b2', 'label': 'Approved',   'group': 'active'},
    'F': {'color': '#94a3b8', 'label': 'F Status',   'group': 'historical'},
    'C': {'color': '#475569', 'label': 'Closed',     'group': 'historical'},
    'T': {'color': '#dc2626', 'label': 'T Status',   'group': 'unknown'},
}
_STATUS_ORDER = ['O', 'N', 'A', 'F', 'C', 'T']

_ACTIVE_STATUSES     = ['O', 'N', 'A']
_HISTORICAL_STATUSES = ['F', 'C']

_AGE_BANDS = ['< 6 months', '6–12 months', '1–2 years', '2–3 years', '3–5 years', '5+ years']
_AGE_COLORS = ['#16a34a', '#65a30d', '#d97706', '#ea580c', '#dc2626', '#7f1d1d']

_CAT_COLOR = '#0d9488'
_SUP_COLOR = '#0284c7'


# ── Formatters ────────────────────────────────────────────────────────────────

def _fmt_val(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return '—'
    sign = '−' if v < 0 else ''
    a = abs(v)
    if a >= 1_000_000_000:
        return f'{sign}£{a / 1_000_000_000:.2f}bn'
    if a >= 1_000_000:
        return f'{sign}£{a / 1_000_000:.1f}m'
    if a >= 1_000:
        return f'{sign}£{a / 1_000:.0f}k'
    return f'{sign}£{a:,.0f}'


def _fmt_count(v):
    if v >= 1_000_000:
        return f'{v / 1_000_000:.1f}m'
    if v >= 1_000:
        return f'{v / 1_000:.1f}k'
    return f'{v:,}'


def _badge(text, bg, color='#f4f0fc'):
    return html.Span(text, style={
        'background': bg, 'color': color,
        'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.1em',
        'padding': '3px 9px', 'borderRadius': '4px',
        'textTransform': 'uppercase', 'display': 'inline-block',
    })


def _label(text):
    return html.Div(text, style={
        'fontSize': '10px', 'fontWeight': '700', 'color': 'rgba(255,255,255,0.45)',
        'textTransform': 'uppercase', 'letterSpacing': '0.1em', 'marginBottom': '8px',
    })


def _divider_v():
    return html.Div(style={
        'width': '1px', 'background': _DIV_COL,
        'alignSelf': 'stretch', 'margin': '0 4px',
    })


# ── Metric computation ────────────────────────────────────────────────────────

def _compute_metrics(frames: dict) -> dict:
    hdr = frames.get('apoheader', pd.DataFrame()).copy()
    dtl = frames.get('apodetail', pd.DataFrame()).copy()

    if hdr.empty:
        return {}

    today = pd.Timestamp.today()

    # ── Numerics ──
    for col in ['amount', 'arr_amount', 'vow_amount', 'com_amount', 'invoiced', 'exch_rate']:
        if col in dtl.columns:
            dtl[col] = pd.to_numeric(dtl[col], errors='coerce').fillna(0)
    if 'exch_rate' in dtl.columns:
        dtl['exch_rate'] = dtl['exch_rate'].replace(0, 1)

    hdr['amend_no'] = pd.to_numeric(hdr.get('amend_no', pd.Series(0, index=hdr.index)), errors='coerce').fillna(0)

    # ── Dates ──
    hdr['order_date'] = pd.to_datetime(hdr['order_date'], errors='coerce')

    # ── Merge detail with header status/date ──
    hdr_slim = hdr[['client', 'order_id', 'status', 'order_date', 'amend_no', 'contract_id']].drop_duplicates()
    hdr_slim = hdr_slim.rename(columns={'status': 'hdr_status'})
    dtl_nostat = dtl.drop(columns=['status'], errors='ignore')
    merged = dtl_nostat.merge(hdr_slim, on=['client', 'order_id'], how='left')
    merged = merged.rename(columns={'hdr_status': 'status'})
    merged['open_commitment'] = merged['amount'] - merged['arr_amount']

    # ── Status breakdown ──
    hdr_by_status = hdr.groupby('status', dropna=False)['order_id'].nunique().reset_index(name='po_count')
    val_by_status = merged.groupby('status', dropna=False).agg(
        total_ordered=('amount', 'sum'),
        total_invoiced=('arr_amount', 'sum'),
        total_receipted=('vow_amount', 'sum'),
    ).reset_index()
    status_df = hdr_by_status.merge(val_by_status, on='status', how='outer').fillna(0)
    status_df['open_commitment'] = status_df['total_ordered'] - status_df['total_invoiced']
    status_df['status'] = status_df['status'].astype(str)

    # ── Totals ──
    total_pos      = int(hdr['order_id'].nunique())
    total_lines    = len(dtl)
    total_ordered  = float(dtl['amount'].sum())
    total_invoiced = float(dtl['arr_amount'].sum())

    date_min = hdr['order_date'].min()
    date_max = hdr['order_date'].max()

    # ── Active population ──
    active_hdr   = hdr[hdr['status'].isin(_ACTIVE_STATUSES)]
    active_dtl   = merged[merged['status'].isin(_ACTIVE_STATUSES)]
    active_count = int(active_hdr['order_id'].nunique())
    active_val   = float(active_dtl['amount'].sum())
    active_inv   = float(active_dtl['arr_amount'].sum())
    active_open  = active_val - active_inv

    # ── Oldest active PO ──
    if not active_hdr.empty and active_hdr['order_date'].notna().any():
        oldest_active = (today - active_hdr['order_date'].min()).days
    else:
        oldest_active = None

    # ── Aging of ALL non-T headers ──
    hdr_nont = hdr[hdr['status'] != 'T'].copy()
    hdr_nont['age_days'] = (today - hdr_nont['order_date']).dt.days.fillna(0)
    bins   = [-1, 180, 365, 730, 1095, 1825, float('inf')]
    labels = _AGE_BANDS
    hdr_nont['age_band'] = pd.cut(hdr_nont['age_days'], bins=bins, labels=labels)

    # Merge PO total ordered value for aging
    po_totals = dtl.groupby(['client', 'order_id'])['amount'].sum().reset_index(name='po_value')
    hdr_nont  = hdr_nont.merge(po_totals, on=['client', 'order_id'], how='left')

    aging_stats = hdr_nont.groupby('age_band', observed=True).agg(
        po_count=('order_id', 'nunique'),
        total_value=('po_value', 'sum'),
    ).reset_index()
    aging_stats['age_band'] = aging_stats['age_band'].astype(str)

    # ── Spend by category ──
    cat_stats = (
        merged[merged['art_gr_description'].notna() & (merged['art_gr_description'].astype(str).str.strip() != '')]
        .groupby('art_gr_description')
        .agg(total_ordered=('amount', 'sum'), po_count=('order_id', 'nunique'))
        .reset_index()
        .sort_values('total_ordered', ascending=False)
    )

    # ── Top 15 suppliers by ordered value ──
    supp_dtl = merged.copy()
    asuheader = frames.get('asuheader', pd.DataFrame())
    if not asuheader.empty and 'apar_name' in asuheader.columns:
        name_map = asuheader.drop_duplicates('apar_id')[['apar_id', 'apar_name']]
        supp_dtl = supp_dtl.merge(name_map, on='apar_id', how='left')
        supp_dtl['display_name'] = supp_dtl['apar_name'].fillna(supp_dtl['apar_id'].astype(str))
    else:
        supp_dtl['display_name'] = supp_dtl['apar_id'].fillna('Unknown').astype(str)

    top_suppliers = (
        supp_dtl.groupby('display_name')
        .agg(total_ordered=('amount', 'sum'), po_count=('order_id', 'nunique'))
        .reset_index()
        .sort_values('total_ordered', ascending=False)
        .head(15)
    )

    # ── Amendment profile ──
    amend_copy = hdr.copy()
    amend_copy['amend_band'] = pd.cut(
        amend_copy['amend_no'],
        bins=[-1, 0, 1, 2, 4, float('inf')],
        labels=['0 (none)', '1', '2', '3–4', '5+'],
    )
    amend_profile = (
        amend_copy.groupby('amend_band', observed=True)['order_id']
        .nunique()
        .reset_index(name='po_count')
    )
    amend_profile['amend_band'] = amend_profile['amend_band'].astype(str)
    amended_any  = int((hdr['amend_no'] > 0).sum())
    amended_high = int((hdr['amend_no'] >= 3).sum())

    # ── Policy signals ──
    po_val_df = dtl.groupby(['client', 'order_id'])['amount'].sum().reset_index(name='po_value')
    po_val_df = po_val_df.merge(hdr[['client', 'order_id', 'status']], on=['client', 'order_id'])

    lvhv_df    = po_val_df[po_val_df['po_value'] < 5000]
    lvhv_count = int(len(lvhv_df))
    lvhv_value = float(lvhv_df['po_value'].sum())

    def _is_blank(s):
        return s.isna() | (s.astype(str).str.strip().isin(['', 'nan', 'None']))

    no_contract = int(_is_blank(hdr['contract_id']).sum())
    no_responsible = int(_is_blank(hdr['responsible']).sum())

    lines_no_acct   = dtl[_is_blank(dtl.get('account', pd.Series(dtype=str)))]
    pos_no_acct     = int(lines_no_acct['order_id'].nunique())

    return {
        'status_df':       status_df,
        'total_pos':       total_pos,
        'total_lines':     total_lines,
        'total_ordered':   total_ordered,
        'total_invoiced':  total_invoiced,
        'date_min':        date_min,
        'date_max':        date_max,
        'active_count':    active_count,
        'active_val':      active_val,
        'active_open':     active_open,
        'oldest_active':   oldest_active,
        'aging_stats':     aging_stats,
        'cat_stats':       cat_stats,
        'top_suppliers':   top_suppliers,
        'amend_profile':   amend_profile,
        'amended_any':     amended_any,
        'amended_high':    amended_high,
        'lvhv_count':      lvhv_count,
        'lvhv_value':      lvhv_value,
        'no_contract':     no_contract,
        'no_responsible':  no_responsible,
        'pos_no_acct':     pos_no_acct,
        'total_hdr':       len(hdr),
    }


# ── Hero banner ───────────────────────────────────────────────────────────────

def _render_hero(m: dict) -> html.Div:
    status_df   = m['status_df']
    total_val   = m['total_ordered']
    total_pos   = m['total_pos']

    date_min = m['date_min']
    date_max = m['date_max']
    yr_min   = date_min.year if pd.notna(date_min) else '?'
    yr_max   = date_max.year if pd.notna(date_max) else '?'
    span_yrs = (date_max - date_min).days // 365 if pd.notna(date_min) and pd.notna(date_max) else '?'

    # ── Left: Landscape overview ──────────────────────────────────────────────
    def _big_stat(value, label):
        return html.Div(style={'marginBottom': '18px'}, children=[
            html.Div(value, style={
                'fontSize': '34px', 'fontWeight': '800',
                'color': '#ffffff', 'lineHeight': '1',
                'fontFamily': DISPLAY_FONT, 'letterSpacing': '-0.5px',
            }),
            html.Div(label, style={
                'fontSize': '10px', 'fontWeight': '700',
                'color': 'rgba(255,255,255,0.45)',
                'textTransform': 'uppercase', 'letterSpacing': '0.1em',
                'marginTop': '4px',
            }),
        ])

    left = html.Div(style={'flex': '0 0 260px', 'paddingRight': '32px'}, children=[
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'marginBottom': '24px'}, children=[
            _badge('SEQ 15', '#0d3347', '#7dd3fc'),
            _badge('HoC Only', '#1e3a22', '#86efac'),
        ]),
        _big_stat(_fmt_count(total_pos), 'Purchase orders'),
        _big_stat(_fmt_count(m['total_lines']), 'Order lines'),
        _big_stat(_fmt_val(total_val), 'Total ordered value'),
        html.Div(style={
            'marginTop': '6px', 'padding': '10px 14px',
            'background': 'rgba(255,255,255,0.05)', 'borderRadius': '8px',
            'border': '1px solid rgba(255,255,255,0.08)',
        }, children=[
            html.Div(style={'display': 'flex', 'justifyContent': 'space-between'}, children=[
                html.Span(f'{yr_min} → {yr_max}', style={
                    'fontSize': '13px', 'fontWeight': '700', 'color': 'rgba(255,255,255,0.8)',
                }),
                html.Span(f'{span_yrs} year span', style={
                    'fontSize': '11px', 'color': 'rgba(255,255,255,0.4)',
                }),
            ]),
            html.Div('Data range — all statuses', style={
                'fontSize': '10px', 'color': 'rgba(255,255,255,0.35)', 'marginTop': '3px',
            }),
        ]),
    ])

    # ── Middle: Status breakdown ───────────────────────────────────────────────
    def _status_row(row):
        s    = str(row['status'])
        cfg  = _STATUS_CFG.get(s, {'color': '#94a3b8', 'label': s, 'group': 'unknown'})
        cnt  = int(row['po_count'])
        val  = float(row.get('total_ordered', 0))
        pct  = (cnt / total_pos * 100) if total_pos > 0 else 0
        color = cfg['color']
        return html.Div(style={
            'display': 'flex', 'alignItems': 'center', 'gap': '10px',
            'padding': '6px 0', 'borderBottom': '1px solid rgba(255,255,255,0.04)',
        }, children=[
            html.Span(s, style={
                'background': color + '22', 'color': color,
                'fontSize': '10px', 'fontWeight': '800', 'letterSpacing': '0.06em',
                'padding': '2px 7px', 'borderRadius': '3px',
                'minWidth': '28px', 'textAlign': 'center',
            }),
            html.Span(cfg['label'], style={
                'fontSize': '11px', 'color': 'rgba(255,255,255,0.5)',
                'minWidth': '70px',
            }),
            html.Div(style={
                'flex': '1', 'height': '6px', 'background': _BAR_TRACK,
                'borderRadius': '3px', 'overflow': 'hidden',
            }, children=[
                html.Div(style={
                    'height': '100%',
                    'width': f'{min(pct, 100):.1f}%',
                    'background': color, 'borderRadius': '3px',
                    'minWidth': '3px' if cnt > 0 else '0',
                }),
            ]),
            html.Span(f'{cnt:,}', style={
                'fontSize': '12px', 'fontWeight': '700', 'color': '#ffffff',
                'minWidth': '48px', 'textAlign': 'right',
            }),
            html.Span(_fmt_val(val), style={
                'fontSize': '10px', 'color': 'rgba(255,255,255,0.4)',
                'minWidth': '64px', 'textAlign': 'right',
            }),
        ])

    ordered_statuses = [s for s in _STATUS_ORDER if s in status_df['status'].values]
    remaining = [s for s in status_df['status'].values if s not in ordered_statuses]
    status_rows_data = []
    for s in ordered_statuses + remaining:
        r = status_df[status_df['status'] == s]
        if not r.empty:
            status_rows_data.append(r.iloc[0])

    middle = html.Div(style={'flex': '1', 'paddingRight': '32px'}, children=[
        _label('Status breakdown'),
        html.Div(style={
            'fontSize': '10px', 'color': 'rgba(255,255,255,0.3)',
            'marginBottom': '12px', 'fontStyle': 'italic',
        }, children='Status F and T meanings unconfirmed — Parliament confirmation pending'),
        html.Div([_status_row(r) for r in status_rows_data]),
        html.Div(style={
            'marginTop': '14px', 'display': 'flex', 'gap': '16px',
        }, children=[
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '6px'}, children=[
                html.Div(style={'width': '10px', 'height': '10px', 'background': _ACTIVE_C, 'borderRadius': '2px'}),
                html.Span('Active (O/N/A)', style={'fontSize': '10px', 'color': 'rgba(255,255,255,0.4)'}),
            ]),
            html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '6px'}, children=[
                html.Div(style={'width': '10px', 'height': '10px', 'background': _HIST_C, 'borderRadius': '2px'}),
                html.Span('Historical (F/C)', style={'fontSize': '10px', 'color': 'rgba(255,255,255,0.4)'}),
            ]),
        ]),
    ])

    # ── Right: Active commitment ───────────────────────────────────────────────
    active_count = m['active_count']
    active_val   = m['active_val']
    active_open  = m['active_open']
    oldest       = m['oldest_active']
    oldest_str   = f'{oldest // 365}y {(oldest % 365) // 30}m' if oldest else '—'

    def _active_kpi(value, label, sub=None):
        return html.Div(style={
            'padding': '12px 16px', 'marginBottom': '10px',
            'background': 'rgba(255,255,255,0.06)',
            'borderRadius': '8px',
            'borderLeft': f'3px solid {_ACTIVE_C}',
        }, children=[
            html.Div(value, style={
                'fontSize': '26px', 'fontWeight': '800', 'color': '#ffffff',
                'fontFamily': DISPLAY_FONT, 'lineHeight': '1',
            }),
            html.Div(label, style={
                'fontSize': '10px', 'fontWeight': '700',
                'color': 'rgba(255,255,255,0.45)',
                'textTransform': 'uppercase', 'letterSpacing': '0.1em',
                'marginTop': '4px',
            }),
            html.Div(sub, style={'fontSize': '11px', 'color': 'rgba(255,255,255,0.35)', 'marginTop': '2px'}) if sub else None,
        ])

    right = html.Div(style={'flex': '0 0 220px'}, children=[
        _label('Active commitment (O · N · A)'),
        _active_kpi(_fmt_count(active_count), 'Active POs'),
        _active_kpi(_fmt_val(active_val), 'Ordered value'),
        _active_kpi(_fmt_val(active_open), 'Uninvoiced balance', sub='amount − arr_amount'),
        html.Div(style={
            'padding': '10px 14px',
            'background': 'rgba(255,255,255,0.04)',
            'borderRadius': '8px',
            'border': '1px solid rgba(255,255,255,0.07)',
        }, children=[
            html.Div('Oldest active PO', style={
                'fontSize': '10px', 'color': 'rgba(255,255,255,0.4)',
                'textTransform': 'uppercase', 'letterSpacing': '0.08em',
            }),
            html.Div(oldest_str, style={
                'fontSize': '18px', 'fontWeight': '700', 'color': _WARN_C,
                'fontFamily': DISPLAY_FONT, 'marginTop': '4px',
            }),
        ]),
    ])

    return html.Div(style={
        'background': _HDR_BG,
        'borderRadius': '14px',
        'padding': '32px 36px',
        'marginBottom': '24px',
        'display': 'flex',
        'gap': '0',
        'boxShadow': '0 8px 32px rgba(0,0,0,0.18)',
    }, children=[left, _divider_v(), html.Div(style={'width': '32px'}), middle, _divider_v(), html.Div(style={'width': '32px'}), right])


# ── KPI strip ─────────────────────────────────────────────────────────────────

def _kpi(value, label, color, sublabel='', warn=False):
    return html.Div(style={
        'background': _CARD_BG, 'border': f'1px solid {_CARD_BOR}',
        'borderRadius': '12px', 'padding': '20px 24px',
        'flex': '1', 'minWidth': '200px',
        'boxShadow': '0 2px 8px rgba(0,0,0,0.05)',
        'borderTop': f'3px solid {color}',
    }, children=[
        html.Div(value, style={
            'fontSize': '32px', 'fontWeight': '800',
            'color': _WARN_C if warn else '#1e293b',
            'lineHeight': '1', 'fontFamily': DISPLAY_FONT,
            'letterSpacing': '-0.5px',
        }),
        html.Div(label, style={
            'fontSize': '10px', 'fontWeight': '700', 'color': '#94a3b8',
            'textTransform': 'uppercase', 'letterSpacing': '1px', 'marginTop': '8px',
        }),
        html.Div(sublabel, style={
            'fontSize': '12px', 'color': '#64748b', 'marginTop': '3px',
        }) if sublabel else None,
    ])


def _render_kpi_strip(m: dict) -> html.Div:
    oldest = m['oldest_active']
    oldest_yrs = f"{oldest / 365:.1f} years" if oldest else '—'

    return html.Div(style={
        'display': 'flex', 'gap': '16px', 'marginBottom': '24px', 'flexWrap': 'wrap',
    }, children=[
        _kpi(_fmt_count(m['active_count']), 'Active POs', _ACTIVE_C,
             sublabel='O, N, and A status'),
        _kpi(_fmt_val(m['active_val']), 'Active ordered value', _ACCENT,
             sublabel='Uninvoiced: ' + _fmt_val(m['active_open'])),
        _kpi(oldest_yrs, 'Oldest active PO', '#dc2626',
             sublabel='Earliest O/N/A order date', warn=oldest and oldest > 730),
    ])


# ── Aging chart ───────────────────────────────────────────────────────────────

def _render_aging(m: dict) -> html.Div:
    aging = m['aging_stats']
    if aging.empty:
        return html.Div()

    # Reorder to correct age band sequence
    all_bands = _AGE_BANDS
    aging = aging.copy()
    aging['age_band'] = pd.Categorical(aging['age_band'], categories=all_bands, ordered=True)
    aging = aging.sort_values('age_band')

    bands  = aging['age_band'].astype(str).tolist()
    counts = aging['po_count'].tolist()
    values = aging['total_value'].tolist()
    colors = [_AGE_COLORS[all_bands.index(b)] if b in all_bands else '#94a3b8' for b in bands]

    # Dual-axis figure: bars = count (left), line = value (right)
    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=bands, x=counts,
        orientation='h',
        marker=dict(
            color=colors,
            line=dict(width=0),
        ),
        text=[_fmt_count(c) for c in counts],
        textposition='outside',
        textfont=dict(size=11, color='#475569'),
        hovertemplate='<b>%{y}</b><br>%{x:,} POs<br>' +
                      '<extra></extra>',
        name='PO Count',
        width=0.55,
    ))

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(t=10, b=40, l=10, r=80),
        height=280,
        bargap=0.35,
        xaxis=dict(
            showgrid=True,
            gridcolor='#f1f5f9',
            title=dict(text='Number of POs', font=dict(size=11, color='#94a3b8')),
            tickfont=dict(size=10),
            zeroline=False,
        ),
        yaxis=dict(
            showgrid=False,
            tickfont=dict(size=11, color='#475569'),
            autorange='reversed',
        ),
        showlegend=False,
        font=dict(family="'Inter', sans-serif"),
    )

    fig_dual = go.Figure()
    fig_dual.add_trace(go.Bar(
        y=bands, x=counts,
        orientation='h',
        marker=dict(color=colors, line=dict(width=0)),
        text=[_fmt_count(c) for c in counts],
        textposition='inside',
        insidetextanchor='end',
        textfont=dict(size=11, color='white', family="'Inter', sans-serif"),
        hovertemplate='<b>%{y}</b><br><b>%{x:,} POs</b><extra></extra>',
        name='PO Count',
    ))

    fig_dual.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(t=10, b=30, l=10, r=10),
        height=280,
        bargap=0.3,
        xaxis=dict(
            showgrid=True, gridcolor='#f1f5f9',
            tickfont=dict(size=10, color='#94a3b8'),
            zeroline=False,
        ),
        yaxis=dict(
            showgrid=False,
            tickfont=dict(size=11, color='#475569'),
            autorange='reversed',
        ),
        showlegend=False,
        font=dict(family="'Inter', sans-serif"),
    )

    # Build a table-style value annotation row
    value_rows = []
    for band, cnt, val, color in zip(bands, counts, values, colors):
        value_rows.append(html.Div(style={
            'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between',
            'padding': '5px 10px',
            'background': '#f8fafc',
            'borderRadius': '4px',
            'marginBottom': '3px',
        }, children=[
            html.Span(band, style={
                'fontSize': '11px', 'color': '#475569', 'minWidth': '100px',
            }),
            html.Div(style={
                'flex': '1', 'height': '5px', 'background': '#e2e8f0',
                'borderRadius': '3px', 'overflow': 'hidden', 'margin': '0 12px',
            }, children=[
                html.Div(style={
                    'height': '100%',
                    'width': f'{(cnt / max(counts, default=1)) * 100:.1f}%' if counts else '0%',
                    'background': color, 'borderRadius': '3px',
                }),
            ]),
            html.Span(f'{cnt:,}', style={
                'fontSize': '11px', 'fontWeight': '700', 'color': color,
                'minWidth': '44px', 'textAlign': 'right',
            }),
            html.Span(_fmt_val(val), style={
                'fontSize': '10px', 'color': '#94a3b8',
                'minWidth': '72px', 'textAlign': 'right',
            }),
        ]))

    return html.Div(style={
        'background': _CARD_BG, 'border': f'1px solid {_CARD_BOR}',
        'borderRadius': '12px', 'padding': '20px 24px',
        'flex': '3',
        'boxShadow': '0 2px 8px rgba(0,0,0,0.04)',
    }, children=[
        html.Div('PO Age Profile', style={
            'fontSize': '13px', 'fontWeight': '700', 'color': '#1e293b', 'marginBottom': '4px',
        }),
        html.Div('All statuses except T · age measured from order_date', style={
            'fontSize': '11px', 'color': '#94a3b8', 'marginBottom': '16px',
        }),
        html.Div(value_rows),
    ])


# ── Amendment depth ───────────────────────────────────────────────────────────

def _render_amendment_depth(m: dict) -> html.Div:
    ap = m['amend_profile']
    if ap.empty:
        return html.Div()

    _AMEND_COLORS = {
        '0 (none)': '#16a34a',
        '1':        '#65a30d',
        '2':        '#d97706',
        '3–4':      '#ea580c',
        '5+':       '#dc2626',
    }

    bands  = ap['amend_band'].tolist()
    counts = ap['po_count'].tolist()
    colors = [_AMEND_COLORS.get(b, '#94a3b8') for b in bands]
    total  = sum(counts) or 1

    rows = []
    for band, cnt, color in zip(bands, counts, colors):
        pct = cnt / total * 100
        rows.append(html.Div(style={
            'display': 'flex', 'alignItems': 'center', 'gap': '10px',
            'padding': '5px 0', 'borderBottom': '1px solid #f1f5f9',
        }, children=[
            html.Span(band, style={
                'fontSize': '11px', 'color': '#475569', 'minWidth': '62px',
            }),
            html.Div(style={
                'flex': '1', 'height': '7px', 'background': _BAR_TRACK_LIGHT,
                'borderRadius': '4px', 'overflow': 'hidden',
            }, children=[
                html.Div(style={
                    'height': '100%',
                    'width': f'{min(pct, 100):.1f}%',
                    'background': color, 'borderRadius': '4px',
                }),
            ]),
            html.Span(f'{cnt:,}', style={
                'fontSize': '12px', 'fontWeight': '700', 'color': color,
                'minWidth': '44px', 'textAlign': 'right',
            }),
            html.Span(f'{pct:.0f}%', style={
                'fontSize': '10px', 'color': '#94a3b8', 'minWidth': '34px',
            }),
        ]))

    return html.Div(style={
        'background': _CARD_BG, 'border': f'1px solid {_CARD_BOR}',
        'borderRadius': '12px', 'padding': '20px 24px',
        'flex': '2',
        'boxShadow': '0 2px 8px rgba(0,0,0,0.04)',
    }, children=[
        html.Div('Amendment Depth', style={
            'fontSize': '13px', 'fontWeight': '700', 'color': '#1e293b', 'marginBottom': '4px',
        }),
        html.Div(f'{m["amended_any"]:,} POs amended · {m["amended_high"]:,} with 3 or more amendments', style={
            'fontSize': '11px', 'color': '#94a3b8', 'marginBottom': '16px',
        }),
        html.Div(rows),
    ])


# ── Spend by category ─────────────────────────────────────────────────────────

def _render_category_chart(m: dict) -> html.Div:
    cats = m['cat_stats']
    if cats.empty:
        return html.Div()

    cats = cats.head(20).sort_values('total_ordered', ascending=True)
    labels = cats['art_gr_description'].tolist()
    values = cats['total_ordered'].tolist()
    counts = cats['po_count'].tolist()
    total  = sum(values) or 1

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=labels, x=values,
        orientation='h',
        marker=dict(
            color=_CAT_COLOR,
            opacity=0.85,
            line=dict(width=0),
        ),
        customdata=list(zip(counts, [v / total * 100 for v in values])),
        hovertemplate=(
            '<b>%{y}</b><br>'
            '£%{x:,.0f} ordered<br>'
            '%{customdata[0]:,} POs · %{customdata[1]:.1f}% of total'
            '<extra></extra>'
        ),
        text=[_fmt_val(v) for v in values],
        textposition='outside',
        textfont=dict(size=10, color='#475569'),
    ))

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(t=10, b=30, l=10, r=80),
        height=max(320, len(labels) * 26),
        bargap=0.25,
        xaxis=dict(
            showgrid=True, gridcolor='#f1f5f9',
            tickfont=dict(size=10, color='#94a3b8'),
            zeroline=False,
        ),
        yaxis=dict(
            showgrid=False,
            tickfont=dict(size=11, color='#475569'),
        ),
        showlegend=False,
        font=dict(family="'Inter', sans-serif"),
    )

    return html.Div(style={
        'background': _CARD_BG, 'border': f'1px solid {_CARD_BOR}',
        'borderRadius': '12px', 'padding': '20px 24px',
        'marginBottom': '24px',
        'boxShadow': '0 2px 8px rgba(0,0,0,0.04)',
    }, children=[
        html.Div(style={'marginBottom': '16px'}, children=[
            html.Div('Ordered Value by Spend Category', style={
                'fontSize': '13px', 'fontWeight': '700', 'color': '#1e293b',
            }),
            html.Div('All statuses · sourced from art_gr_description on order lines · placeholder category names pending Parliament confirmation', style={
                'fontSize': '11px', 'color': '#94a3b8', 'marginTop': '3px',
            }),
        ]),
        dcc.Graph(figure=fig, config=PLOTLY_HOVER_CONFIG, style={'height': f'{max(320, len(labels) * 26)}px'}),
    ])


# ── Top suppliers ─────────────────────────────────────────────────────────────

def _render_top_suppliers(m: dict) -> html.Div:
    ts = m['top_suppliers']
    if ts.empty:
        return html.Div()

    ts = ts.sort_values('total_ordered', ascending=True)
    labels = ts['display_name'].astype(str).tolist()
    values = ts['total_ordered'].tolist()
    counts = ts['po_count'].tolist()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=labels, x=values,
        orientation='h',
        marker=dict(color=_SUP_COLOR, opacity=0.85, line=dict(width=0)),
        customdata=counts,
        hovertemplate='<b>%{y}</b><br>£%{x:,.0f} ordered<br>%{customdata:,} POs<extra></extra>',
        text=[_fmt_val(v) for v in values],
        textposition='outside',
        textfont=dict(size=10, color='#475569'),
    ))

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(t=10, b=30, l=10, r=80),
        height=360,
        bargap=0.25,
        xaxis=dict(showgrid=True, gridcolor='#f1f5f9', tickfont=dict(size=10, color='#94a3b8'), zeroline=False),
        yaxis=dict(showgrid=False, tickfont=dict(size=11, color='#475569')),
        showlegend=False,
        font=dict(family="'Inter', sans-serif"),
    )

    return html.Div(style={
        'background': _CARD_BG, 'border': f'1px solid {_CARD_BOR}',
        'borderRadius': '12px', 'padding': '20px 24px',
        'flex': '1',
        'boxShadow': '0 2px 8px rgba(0,0,0,0.04)',
    }, children=[
        html.Div('Top 15 Suppliers by Ordered Value', style={
            'fontSize': '13px', 'fontWeight': '700', 'color': '#1e293b', 'marginBottom': '4px',
        }),
        html.Div('All statuses · supplier name from master data where available', style={
            'fontSize': '11px', 'color': '#94a3b8', 'marginBottom': '16px',
        }),
        dcc.Graph(figure=fig, config=PLOTLY_HOVER_CONFIG, style={'height': '360px'}),
    ])


# ── Policy signals ────────────────────────────────────────────────────────────

def _render_policy_signals(m: dict) -> html.Div:
    total = m['total_hdr'] or 1

    def _signal_card(value, label, sublabel, color, icon_char):
        pct = None
        if isinstance(value, (int, float)) and total:
            pct = value / total * 100
        return html.Div(style={
            'background': _CARD_BG, 'border': f'1px solid {_CARD_BOR}',
            'borderRadius': '12px', 'padding': '20px 24px', 'flex': '1', 'minWidth': '180px',
            'borderTop': f'3px solid {color}',
            'boxShadow': '0 2px 8px rgba(0,0,0,0.04)',
        }, children=[
            html.Div(icon_char, style={
                'fontSize': '22px', 'marginBottom': '10px',
            }),
            html.Div(_fmt_count(value) if isinstance(value, (int, float)) else value, style={
                'fontSize': '28px', 'fontWeight': '800', 'color': color,
                'fontFamily': DISPLAY_FONT, 'lineHeight': '1',
            }),
            html.Div(f'{pct:.0f}% of all POs' if pct is not None else '', style={
                'fontSize': '11px', 'color': '#94a3b8', 'marginTop': '3px',
            }),
            html.Div(label, style={
                'fontSize': '12px', 'fontWeight': '600', 'color': '#1e293b', 'marginTop': '8px',
            }),
            html.Div(sublabel, style={
                'fontSize': '11px', 'color': '#64748b', 'marginTop': '3px',
            }),
        ])

    return html.Div(style={'marginBottom': '24px'}, children=[
        html.Div(style={
            'display': 'flex', 'alignItems': 'center', 'gap': '10px',
            'borderTop': '1px solid #e2e8f0', 'paddingTop': '20px', 'marginBottom': '16px',
        }, children=[
            html.Div('Policy Signals', style={
                'fontSize': '15px', 'fontWeight': '700', 'color': '#1e293b',
            }),
            html.Span('Indicators of procurement policy adherence', style={
                'fontSize': '11px', 'color': '#94a3b8',
            }),
        ]),
        html.Div(style={'display': 'flex', 'gap': '16px', 'flexWrap': 'wrap'}, children=[
            _signal_card(
                m['lvhv_count'],
                'Low-value POs (< £5k)',
                f'Total value: {_fmt_val(m["lvhv_value"])}',
                '#d97706', '📦',
            ),
            _signal_card(
                m['amended_high'],
                'Highly amended (≥ 3)',
                'Signals poor initial specification',
                '#dc2626', '✏️',
            ),
            _signal_card(
                m['no_contract'],
                'No contract reference',
                'header_note or contract_id blank',
                '#7c3aed', '📋',
            ),
            _signal_card(
                m['no_responsible'],
                'No responsible owner',
                'responsible field blank',
                '#0891b2', '👤',
            ),
            _signal_card(
                m['pos_no_acct'],
                'Lines missing GL account',
                'No account code on at least one line',
                '#e11d48', '🔴',
            ),
        ]),
    ])


# ── Section divider ───────────────────────────────────────────────────────────

def _section_div(title, subtitle=''):
    return html.Div(style={
        'borderTop': '1px solid #e2e8f0',
        'margin': '4px 0 20px',
        'paddingTop': '20px',
        'display': 'flex', 'alignItems': 'center', 'gap': '12px',
    }, children=[
        html.Div(title, style={
            'fontSize': '15px', 'fontWeight': '700', 'color': '#1e293b',
        }),
        html.Span(subtitle, style={
            'fontSize': '11px', 'color': '#94a3b8',
        }) if subtitle else None,
    ])


# ── Main renderer ─────────────────────────────────────────────────────────────

def render_tab(frames: dict, dq_results=None) -> html.Div:
    hdr = frames.get('apoheader', pd.DataFrame())
    if hdr.empty:
        return html.Div('No PO data loaded. Run po_header_HOC_run.sql and po_detail_HOC_run.sql then restart.', style={
            'padding': '48px', 'textAlign': 'center', 'color': '#94a3b8', 'fontSize': '14px',
        })

    m = _compute_metrics(frames)

    aging_card = _render_aging(m)
    cat_chart  = _render_category_chart(m)
    supp_chart = _render_top_suppliers(m)

    return html.Div(children=[

        # ── Hero ──
        _render_hero(m),

        # ── KPI strip ──
        _render_kpi_strip(m),

        # ── Age profile ──
        _section_div('PO Age Profile',
                     'All statuses except T · age measured from order_date'),
        html.Div(style={'marginBottom': '24px'}, children=[aging_card]),

        # ── Spend by category ──
        _section_div('Spend by Category',
                     'Total ordered value grouped by article category across all PO lines'),
        cat_chart,

        # ── Top suppliers ──
        _section_div('Supplier Concentration',
                     'Top 15 suppliers by total ordered value across all statuses'),
        html.Div(style={'marginBottom': '24px'}, children=[supp_chart]),

    ])
