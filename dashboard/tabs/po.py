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
from dashboard.shared.dimensions import render_dimension_scorecard, render_dimension_grid

# ── Design tokens ─────────────────────────────────────────────────────────────
_HDR_BG    = '#0d1f2d'   # deep navy
_HDR2_BG   = '#102535'
_ACCENT    = '#0d9488'   # teal
_WARN_C    = '#d97706'   # amber
_CARD_BG   = '#ffffff'
_CARD_BOR  = '#e2e8f0'
_PAGE_BG   = '#f4f7f9'
_BAR_TRACK = '#1e3448'
_BAR_TRACK_LIGHT = '#e8f0f6'
_DIV_COL   = '#1e3650'

# ── Status config (confirmed by Parliament, July 2026) ────────────────────────
# F/C/T carry good/warning/critical meaning (clean automatic close vs manual
# close-with-balance vs error), so they wear status colors, not arbitrary hues.
_STATUS_CFG = {
    'N': {'color': '#2563eb', 'label': 'Not Ordered', 'group': 'active'},
    'O': {'color': '#16a34a', 'label': 'Ordered',      'group': 'active'},
    'A': {'color': '#0891b2', 'label': 'Confirmed',    'group': 'active'},
    'F': {'color': '#059669', 'label': 'Finished',     'group': 'historical'},  # good — clean, automatic
    'C': {'color': '#d97706', 'label': 'Closed',       'group': 'historical'},  # warning — manual, funds left
    'T': {'color': '#dc2626', 'label': 'Terminated',   'group': 'historical'},  # critical — error
}
_STATUS_ORDER = ['N', 'O', 'A', 'F', 'C', 'T']

_ACTIVE_STATUSES     = ['O', 'N', 'A']
_HISTORICAL_STATUSES = ['F', 'C', 'T']

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
    # Line-level status is kept (renamed to line_status) rather than discarded, so it can be
    # compared against the header status — the two are not guaranteed to agree.
    hdr_slim = hdr[['client', 'order_id', 'status', 'order_date', 'amend_no', 'contract_id']].drop_duplicates()
    hdr_slim = hdr_slim.rename(columns={'status': 'hdr_status'})
    dtl_for_merge = dtl.rename(columns={'status': 'line_status'}) if 'status' in dtl.columns else dtl.copy()
    merged = dtl_for_merge.merge(hdr_slim, on=['client', 'order_id'], how='left')
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

    # ── Fulfilment pipeline: Ordered -> Received (vow_amount) -> Invoiced (arr_amount) ──
    # Independently-maintained running totals (receiving vs. AP invoice matching), not
    # derived from each other — so "received, not yet invoiced" is not guaranteed >= 0
    # on every line, only reliable as an aggregate.
    active_received = float(active_dtl['vow_amount'].sum())
    active_received_not_invoiced = max(active_received - active_inv, 0.0)
    active_not_received = max(active_val - active_received, 0.0)

    # ── Invoicing signal agreement: does arr_amount agree with invoiced? ──
    # Real PO line inspection showed these disagreeing in both directions — a fully
    # invoiced line reading invoiced=0, a partially invoiced line reading arr_val=0
    # (see QUESTIONS_FOR_PARLIAMENT.md #5). Not simple currency-conversion duplicates
    # of the same fact. Dummy data always agrees (generator sets invoiced=arr_amount),
    # so this is only informative once run against real data.
    _EPS = 0.01
    arr_has = active_dtl['arr_amount'] > _EPS
    inv_has = active_dtl['invoiced'] > _EPS
    _agreement_masks = [
        ('both_nonzero',  'Both agree — invoiced',                        arr_has & inv_has),
        ('both_zero',     'Both agree — not yet invoiced',                ~arr_has & ~inv_has),
        ('arr_only',      'arr_amount says invoiced, invoiced says no',   arr_has & ~inv_has),
        ('invoiced_only', 'invoiced says invoiced, arr_amount says no',   ~arr_has & inv_has),
    ]
    invoicing_agreement = pd.DataFrame([
        {
            'bucket': key, 'label': label,
            'line_count': int(mask.sum()),
            'value': float(active_dtl.loc[mask, 'amount'].sum()),
        }
        for key, label, mask in _agreement_masks
    ])
    disagreement_count = int((arr_has != inv_has).sum())
    disagreement_pct = disagreement_count / len(active_dtl) * 100 if len(active_dtl) else 0.0

    # ── Oldest active PO ──
    if not active_hdr.empty and active_hdr['order_date'].notna().any():
        oldest_active = (today - active_hdr['order_date'].min()).days
    else:
        oldest_active = None

    # ── Resolution mix: how POs leave the active book (F / C / T) ──
    resolution_counts = {
        s: int(status_df.loc[status_df['status'] == s, 'po_count'].sum()) for s in _HISTORICAL_STATUSES
    }
    resolution_total = sum(resolution_counts.values()) or 1
    clean_completion_rate = resolution_counts.get('F', 0) / resolution_total * 100
    error_rate = resolution_counts.get('T', 0) / resolution_total * 100

    # ── Released budget: commitment left unspent on manually-closed (C) POs ──
    released_budget = float(merged.loc[merged['status'] == 'C', 'open_commitment'].sum())
    resolved_count = sum(resolution_counts.values())

    # ── Fulfilment of the resolved book: same pipeline as the live book, but a closed
    # PO ideally should already be near-fully received/invoiced — a gap here is more
    # notable than the same gap on a still-open PO. ──
    resolved_dtl = merged[merged['status'].isin(_HISTORICAL_STATUSES)]
    resolved_val      = float(resolved_dtl['amount'].sum())
    resolved_invoiced = float(resolved_dtl['arr_amount'].sum())
    resolved_received = float(resolved_dtl['vow_amount'].sum())
    resolved_received_not_invoiced = max(resolved_received - resolved_invoiced, 0.0)
    resolved_not_received = max(resolved_val - resolved_received, 0.0)

    # ── Invoicing signal agreement, same check as the live book, scoped to resolved lines ──
    r_arr_has = resolved_dtl['arr_amount'] > _EPS
    r_inv_has = resolved_dtl['invoiced'] > _EPS
    _resolved_agreement_masks = [
        ('both_nonzero',  'Both agree — invoiced',                      r_arr_has & r_inv_has),
        ('both_zero',     'Both agree — not yet invoiced',              ~r_arr_has & ~r_inv_has),
        ('arr_only',      'arr_amount says invoiced, invoiced says no', r_arr_has & ~r_inv_has),
        ('invoiced_only', 'invoiced says invoiced, arr_amount says no', ~r_arr_has & r_inv_has),
    ]
    resolved_agreement = pd.DataFrame([
        {
            'bucket': key, 'label': label,
            'line_count': int(mask.sum()),
            'value': float(resolved_dtl.loc[mask, 'amount'].sum()),
        }
        for key, label, mask in _resolved_agreement_masks
    ])
    resolved_disagreement_count = int((r_arr_has != r_inv_has).sum())
    resolved_disagreement_pct = (
        resolved_disagreement_count / len(resolved_dtl) * 100 if len(resolved_dtl) else 0.0
    )

    # ── Line-level status vs header status ──
    if 'line_status' in merged.columns:
        line_status_counts = (
            merged.groupby('line_status', dropna=False).size().reset_index(name='line_count')
        )
        line_status_counts['line_status'] = line_status_counts['line_status'].astype(str)
        mismatch_mask = merged['line_status'].astype(str) != merged['status'].astype(str)
        mismatch_count = int(mismatch_mask.sum())
        mismatch_pct = mismatch_count / len(merged) * 100 if len(merged) else 0.0
    else:
        line_status_counts = pd.DataFrame(columns=['line_status', 'line_count'])
        mismatch_count = 0
        mismatch_pct = 0.0

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

    # ── Active status composition (O / N / A) ──
    active_status_mix = (
        active_hdr.groupby('status')['order_id'].nunique().reset_index(name='po_count')
        .merge(
            active_dtl.groupby('status')['amount'].sum().reset_index(name='value'),
            on='status', how='outer',
        ).fillna(0)
    )
    active_status_mix['status'] = active_status_mix['status'].astype(str)

    # ── Finished-with-balance: does F really mean "fully used", as Parliament defines it? ──
    # Real PO line inspection shows arr_amount and invoiced disagreeing about invoicing status
    # in both directions (see QUESTIONS_FOR_PARLIAMENT.md #5) — one field is sometimes zero
    # while the other genuinely shows the line as invoiced, for the same line. Taking whichever
    # of the two is larger per line avoids under-counting real invoicing progress purely because
    # of that field ambiguity, rather than trusting either field alone.
    finished_dtl = merged[merged['status'] == 'F'].copy()
    finished_dtl['effective_invoiced'] = finished_dtl[['arr_amount', 'invoiced']].max(axis=1)
    finished_bal = (
        finished_dtl
        .groupby(['client', 'order_id'])
        .agg(po_value=('amount', 'sum'), po_invoiced=('effective_invoiced', 'sum'),
             po_received=('vow_amount', 'sum'))
        .reset_index()
    )
    finished_bal['uninvoiced'] = finished_bal['po_value'] - finished_bal['po_invoiced']
    finished_bal['uninvoiced_pct'] = (
        (finished_bal['uninvoiced'] / finished_bal['po_value'].replace(0, np.nan)) * 100
    ).fillna(0)
    finished_total_count = int(len(finished_bal))
    # Materiality threshold, not a float-noise floor — invoicing is rarely mathematically
    # exact, so ">5% of value still unaccounted for" separates a genuinely incomplete PO from
    # ordinary rounding/timing noise around a "complete" invoice.
    finished_with_balance_count = int((finished_bal['uninvoiced_pct'] > 5).sum())
    finished_with_balance_pct = (
        finished_with_balance_count / finished_total_count * 100 if finished_total_count else 0.0
    )
    finished_value_total = float(finished_bal['po_value'].sum())
    # Secondary, contrasting figure — receipt (vow_amount) alone, kept for context since it
    # was the original basis before the arr_amount/invoiced ambiguity was confirmed.
    finished_received_pct = (
        finished_bal['po_received'].sum() / finished_value_total * 100 if finished_value_total else 0.0
    )

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
        'active_invoiced':             active_inv,
        'active_received':             active_received,
        'active_received_not_invoiced': active_received_not_invoiced,
        'active_not_received':          active_not_received,
        'invoicing_agreement':          invoicing_agreement,
        'disagreement_count':           disagreement_count,
        'disagreement_pct':             disagreement_pct,
        'oldest_active':   oldest_active,
        'resolution_counts':     resolution_counts,
        'resolution_total':      resolution_total,
        'clean_completion_rate': clean_completion_rate,
        'error_rate':            error_rate,
        'released_budget':       released_budget,
        'resolved_count':                resolved_count,
        'resolved_received_not_invoiced': resolved_received_not_invoiced,
        'resolved_not_received':          resolved_not_received,
        'resolved_invoiced':              resolved_invoiced,
        'resolved_agreement':             resolved_agreement,
        'resolved_disagreement_count':    resolved_disagreement_count,
        'resolved_disagreement_pct':      resolved_disagreement_pct,
        'line_status_counts':    line_status_counts,
        'mismatch_count':        mismatch_count,
        'mismatch_pct':          mismatch_pct,
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
        'active_status_mix':           active_status_mix,
        'finished_total_count':        finished_total_count,
        'finished_with_balance_count': finished_with_balance_count,
        'finished_with_balance_pct':   finished_with_balance_pct,
        'finished_received_pct':       finished_received_pct,
    }


# ── Hero banner ───────────────────────────────────────────────────────────────

def _render_hero(m: dict) -> html.Div:
    """Pure orientation — scale only. Status and active-commitment detail live
    entirely in the PO Lifecycle section below; showing them here too was
    duplicating the same numbers in two places."""
    total_val   = m['total_ordered']
    total_pos   = m['total_pos']
    total_lines = m['total_lines']

    date_min = m['date_min']
    date_max = m['date_max']
    yr_min   = date_min.year if pd.notna(date_min) else '?'
    yr_max   = date_max.year if pd.notna(date_max) else '?'
    span_yrs = (date_max - date_min).days // 365 if pd.notna(date_min) and pd.notna(date_max) else '?'

    def _secondary_stat(value, label):
        return html.Div(style={'minWidth': '110px'}, children=[
            html.Div(value, style={
                'fontSize': '22px', 'fontWeight': '800', 'color': 'rgba(255,255,255,0.92)',
                'lineHeight': '1', 'fontFamily': DISPLAY_FONT,
            }),
            html.Div(label, style={
                'fontSize': '10px', 'fontWeight': '700', 'color': 'rgba(255,255,255,0.4)',
                'textTransform': 'uppercase', 'letterSpacing': '0.1em', 'marginTop': '5px',
            }),
        ])

    return html.Div(style={
        'background': (
            f'radial-gradient(ellipse 900px 420px at 12% 8%, rgba(13,148,136,0.18), transparent 60%), '
            f'linear-gradient(155deg, {_HDR_BG}, {_HDR2_BG})'
        ),
        'borderRadius': '14px', 'padding': '34px 40px', 'marginBottom': '24px',
        'boxShadow': '0 8px 32px rgba(0,0,0,0.18)',
    }, children=[
        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'marginBottom': '28px'}, children=[
            _badge('SEQ 15', '#0d3347', '#7dd3fc'),
            _badge('HoC Only', '#1e3a22', '#86efac'),
        ]),
        html.Div(style={'display': 'flex', 'alignItems': 'flex-end', 'gap': '48px', 'flexWrap': 'wrap'}, children=[
            html.Div(children=[
                html.Div('Total ordered value', style={
                    'fontSize': '11px', 'fontWeight': '700', 'color': 'rgba(255,255,255,0.45)',
                    'textTransform': 'uppercase', 'letterSpacing': '0.12em', 'marginBottom': '8px',
                }),
                html.Div(_fmt_val(total_val), style={
                    'fontSize': '52px', 'fontWeight': '800', 'color': '#ffffff',
                    'lineHeight': '1', 'fontFamily': DISPLAY_FONT, 'letterSpacing': '-1.5px',
                }),
                html.Div(style={
                    'width': '48px', 'height': '4px', 'background': _ACCENT,
                    'borderRadius': '2px', 'marginTop': '14px',
                }),
            ]),
            html.Div(style={'display': 'flex', 'gap': '32px', 'paddingBottom': '6px'}, children=[
                _secondary_stat(_fmt_count(total_pos), 'Purchase orders'),
                _secondary_stat(_fmt_count(total_lines), 'Order lines'),
            ]),
        ]),
        html.Div(style={
            'marginTop': '26px', 'paddingTop': '18px',
            'borderTop': '1px solid rgba(255,255,255,0.08)',
            'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'flexWrap': 'wrap', 'gap': '8px',
        }, children=[
            html.Span("Across every status — what's live vs. resolved is below", style={
                'fontSize': '11px', 'color': 'rgba(255,255,255,0.35)',
            }),
            html.Span(f'{yr_min} → {yr_max} · {span_yrs} year span', style={
                'fontSize': '12px', 'fontWeight': '600', 'color': 'rgba(255,255,255,0.65)',
            }),
        ]),
    ])


# ── PO Lifecycle narrative ─────────────────────────────────────────────────────


# O/N/A are all "the live book" — one hue family, shade by weight, rather than three
# unrelated identity colors. O (the dominant status) takes the card's own accent so
# the composition rows read as sub-groups of the stat tiles above, not a separate palette.
_LIVE_COMPOSITION_COLORS = {'O': _ACCENT, 'N': '#5eead4', 'A': '#99f6e4'}


def _render_active_composition(m: dict) -> html.Div:
    """Row breakdown of how the live book splits across O/N/A — same label/bar/count
    pattern as Amendment Depth and Line-Level Status elsewhere on this tab, so identity
    reads from one row at a time rather than cross-referencing a separate legend."""
    mix = m['active_status_mix']
    if mix.empty:
        return html.Div()

    order = [s for s in ['O', 'N', 'A'] if s in mix['status'].values]
    total_val = mix['value'].sum() or 1

    rows = []
    for s in order:
        row = mix[mix['status'] == s].iloc[0]
        color = _LIVE_COMPOSITION_COLORS[s]
        pct = row['value'] / total_val * 100
        rows.append(html.Div(style={
            'display': 'flex', 'alignItems': 'center', 'gap': '10px',
            'padding': '6px 0', 'borderBottom': '1px solid #f1f5f9',
        }, children=[
            html.Span(_STATUS_CFG[s]['label'], style={'fontSize': '12px', 'color': '#475569', 'minWidth': '92px'}),
            html.Div(style={
                'flex': '1', 'height': '8px', 'background': _BAR_TRACK_LIGHT,
                'borderRadius': '4px', 'overflow': 'hidden',
            }, children=[
                html.Div(style={
                    'height': '100%', 'width': f'{min(pct, 100):.1f}%',
                    'background': color, 'borderRadius': '4px',
                    'minWidth': '3px' if pct > 0 else '0',
                }),
            ]),
            html.Span(f"{int(row['po_count']):,}", style={
                'fontSize': '13px', 'fontWeight': '700', 'color': color,
                'minWidth': '34px', 'textAlign': 'right',
            }),
            html.Span(_fmt_val(row['value']), style={
                'fontSize': '11px', 'color': '#94a3b8', 'minWidth': '64px', 'textAlign': 'right',
            }),
        ]))

    return html.Div(style={'marginTop': '18px'}, children=[
        html.Div('Composition of the live book', style={
            'fontSize': '11px', 'fontWeight': '700', 'color': '#94a3b8',
            'textTransform': 'uppercase', 'letterSpacing': '0.06em', 'marginBottom': '10px',
        }),
        html.Div(rows),
    ])


# Invoiced is furthest along (darkest), not-yet-received hasn't started (neutral grey) —
# reads as a fill gradient rather than three competing identities.
# Live book: teal family, darkest = furthest along. Resolved book: slate family —
# a closed PO ideally should already be fully received/invoiced, so this isn't the
# "healthy in-progress" teal, it's a neutral "should be settled by now" tone.
_FULFILMENT_COLORS = {
    'invoiced':              _ACCENT,    # #0d9488
    'received_not_invoiced': '#5eead4',  # teal-300 — reused from the N composition shade
    'not_received':          '#cbd5e1',  # slate-300 — hasn't happened yet, not "teal-lite"
}
_RESOLVED_FULFILMENT_COLORS = {
    'invoiced':              '#475569',  # slate-600
    'received_not_invoiced': '#94a3b8',  # slate-400
    'not_received':          '#cbd5e1',  # slate-300 — same "not yet" neutral as the live book
}


def _render_fulfilment_rows(title, total, invoiced, received_not_invoiced, not_received, colors):
    """Breaks an Ordered-value total into where it actually stands: amount ->
    vow_amount (received) -> arr_amount (invoiced). Distinguishes 'received,
    paperwork hasn't caught up yet' (low risk) from 'genuinely still awaited from
    the supplier' (the real open commitment) — both are invisible inside one
    Uninvoiced Balance figure. Same row pattern as Composition of the Live Book."""
    if not total:
        return html.Div()

    segments = [
        ('invoiced', 'Invoiced', invoiced),
        ('received_not_invoiced', 'Received, not yet invoiced', received_not_invoiced),
        ('not_received', 'Not yet received', not_received),
    ]

    rows = []
    for key, label, value in segments:
        color = colors[key]
        pct = value / total * 100 if total else 0
        rows.append(html.Div(style={
            'display': 'flex', 'alignItems': 'center', 'gap': '10px',
            'padding': '6px 0', 'borderBottom': '1px solid #f1f5f9',
        }, children=[
            html.Span(label, style={'fontSize': '12px', 'color': '#475569', 'minWidth': '190px'}),
            html.Div(style={
                'flex': '1', 'height': '8px', 'background': _BAR_TRACK_LIGHT,
                'borderRadius': '4px', 'overflow': 'hidden',
            }, children=[
                html.Div(style={
                    'height': '100%', 'width': f'{min(pct, 100):.1f}%',
                    'background': color, 'borderRadius': '4px',
                    'minWidth': '3px' if pct > 0 else '0',
                }),
            ]),
            html.Span(_fmt_val(value), style={
                'fontSize': '13px', 'fontWeight': '700', 'color': color,
                'minWidth': '58px', 'textAlign': 'right',
            }),
            html.Span(f'{pct:.0f}%', style={
                'fontSize': '11px', 'color': '#94a3b8', 'minWidth': '34px', 'textAlign': 'right',
            }),
        ]))

    return html.Div(style={'marginTop': '22px', 'paddingTop': '18px', 'borderTop': '1px solid #f1f5f9'}, children=[
        html.Div(title, style={
            'fontSize': '11px', 'fontWeight': '700', 'color': '#94a3b8',
            'textTransform': 'uppercase', 'letterSpacing': '0.06em', 'marginBottom': '10px',
        }),
        html.Div(rows),
    ])


def _render_active_fulfilment(m: dict) -> html.Div:
    return _render_fulfilment_rows(
        'Fulfilment of the live book', m['active_val'],
        m['active_invoiced'], m['active_received_not_invoiced'], m['active_not_received'],
        _FULFILMENT_COLORS,
    )


def _render_resolved_fulfilment(m: dict) -> html.Div:
    total = m['resolved_invoiced'] + m['resolved_received_not_invoiced'] + m['resolved_not_received']
    return _render_fulfilment_rows(
        'Fulfilment of the resolved book', total,
        m['resolved_invoiced'], m['resolved_received_not_invoiced'], m['resolved_not_received'],
        _RESOLVED_FULFILMENT_COLORS,
    )


# Agreement = the book's own accent/neutral (matches each Fulfilment's "resolved"/
# "not yet" language); disagreement always gets purple regardless of book, since
# it's the same underlying field ambiguity either way — an open question about
# which field to trust, not a health signal like the amber warnings elsewhere.
_AGREEMENT_COLORS = {
    'both_nonzero':  _ACCENT,
    'both_zero':     '#cbd5e1',
    'arr_only':      '#7c3aed',
    'invoiced_only': '#c4b5fd',
}
_RESOLVED_AGREEMENT_COLORS = {
    'both_nonzero':  '#475569',
    'both_zero':     '#cbd5e1',
    'arr_only':      '#7c3aed',
    'invoiced_only': '#c4b5fd',
}


def _render_agreement_rows(agreement, disagreement_pct, disagreement_count, population_label, colors):
    """Does arr_amount agree with invoiced about whether a line's been invoiced?
    Real data shows these disagreeing in both directions (QUESTIONS_FOR_PARLIAMENT.md
    #5) — this makes the size of that ambiguity visible rather than just asserting it
    in a comment. Dummy data always agrees (generator sets invoiced = arr_amount), so
    this only becomes informative once run against real Parliament data."""
    if agreement.empty:
        return html.Div()

    total = agreement['line_count'].sum() or 1
    rows = []
    for _, r in agreement.iterrows():
        color = colors[r['bucket']]
        pct = r['line_count'] / total * 100
        rows.append(html.Div(style={
            'display': 'flex', 'alignItems': 'center', 'gap': '10px',
            'padding': '6px 0', 'borderBottom': '1px solid #f1f5f9',
        }, children=[
            html.Span(r['label'], style={'fontSize': '12px', 'color': '#475569', 'flex': '1'}),
            html.Div(style={
                'flex': '1', 'height': '8px', 'background': _BAR_TRACK_LIGHT,
                'borderRadius': '4px', 'overflow': 'hidden',
            }, children=[
                html.Div(style={
                    'height': '100%', 'width': f'{min(pct, 100):.1f}%',
                    'background': color, 'borderRadius': '4px',
                    'minWidth': '3px' if pct > 0 else '0',
                }),
            ]),
            html.Span(f"{int(r['line_count']):,}", style={
                'fontSize': '13px', 'fontWeight': '700', 'color': color,
                'minWidth': '34px', 'textAlign': 'right',
            }),
            html.Span(_fmt_val(r['value']), style={
                'fontSize': '11px', 'color': '#94a3b8', 'minWidth': '64px', 'textAlign': 'right',
            }),
        ]))

    return html.Div(style={
        'marginTop': '22px', 'paddingTop': '18px', 'borderTop': '1px solid #f1f5f9',
        'display': 'flex', 'gap': '24px', 'flexWrap': 'wrap',
    }, children=[
        html.Div(style={'flex': '1', 'minWidth': '280px'}, children=[
            html.Div('Invoicing signal agreement — arr_amount vs. invoiced', style={
                'fontSize': '11px', 'fontWeight': '700', 'color': '#94a3b8',
                'textTransform': 'uppercase', 'letterSpacing': '0.06em', 'marginBottom': '10px',
            }),
            html.Div(rows),
        ]),
        html.Div(style={
            'flex': '0 0 200px', 'padding': '16px 18px',
            'background': '#faf5ff', 'border': '1px solid #e9d5ff', 'borderRadius': '10px',
            'display': 'flex', 'flexDirection': 'column', 'justifyContent': 'center',
        }, children=[
            html.Div(f"{disagreement_pct:.1f}%", style={
                'fontSize': '28px', 'fontWeight': '800', 'color': '#7c3aed',
                'fontFamily': DISPLAY_FONT, 'lineHeight': '1',
            }),
            html.Div(f'of {population_label} lines disagree on invoicing status', style={
                'fontSize': '11px', 'color': '#64748b', 'marginTop': '8px',
            }),
            html.Div(f"{disagreement_count:,} lines", style={
                'fontSize': '11px', 'color': '#94a3b8', 'marginTop': '6px',
            }),
        ]),
    ])


def _render_invoicing_agreement(m: dict) -> html.Div:
    return _render_agreement_rows(
        m['invoicing_agreement'], m['disagreement_pct'], m['disagreement_count'],
        'active', _AGREEMENT_COLORS,
    )


def _render_resolved_agreement(m: dict) -> html.Div:
    return _render_agreement_rows(
        m['resolved_agreement'], m['resolved_disagreement_pct'], m['resolved_disagreement_count'],
        'resolved', _RESOLVED_AGREEMENT_COLORS,
    )


def _render_finished_balance_callout(m: dict) -> html.Div:
    """Validates Parliament's own definition of F ('used up completely') against
    invoicing — using whichever of arr_amount/invoiced is larger per line, since
    real data shows the two disagreeing about invoicing status in both directions
    (QUESTIONS_FOR_PARLIAMENT.md #5). Trusting either field alone would either
    under- or over-count genuine invoicing progress."""
    return html.Div(style={
        'marginTop': '18px', 'padding': '14px 16px',
        'background': '#f0fdfa', 'border': '1px solid #99f6e4', 'borderRadius': '8px',
        'display': 'flex', 'gap': '20px', 'flexWrap': 'wrap',
    }, children=[
        html.Div(style={'flex': '1', 'minWidth': '220px'}, children=[
            html.Span(f"{m['finished_with_balance_count']:,} of {m['finished_total_count']:,} Finished POs "
                      f"({m['finished_with_balance_pct']:.0f}%)",
                      style={'fontWeight': '700', 'color': '#0f766e', 'fontSize': '12px'}),
            html.Span(' still have more than 5% of their value unaccounted for by invoicing '
                      '(checking both arr_amount and invoiced), despite the system marking '
                      'them "used completely".', style={'color': '#134e4a', 'fontSize': '12px'}),
        ]),
        html.Div(style={'flex': '1', 'minWidth': '220px'}, children=[
            html.Span(f"{m['finished_received_pct']:.0f}% receipted", style={
                'fontWeight': '700', 'color': '#0f766e', 'fontSize': '12px',
            }),
            html.Span(" of Finished POs' total value by vow_amount alone — shown for contrast, "
                      "since receipt and invoicing can tell a different story on the same PO.",
                      style={'color': '#134e4a', 'fontSize': '12px'}),
        ]),
    ])


def _stat_box(value, label, color=None, sub=None):
    """A boxed stat card — used for the Currently Live headline row. Color is only
    given to figures that are money (teal accent); plain counts/facts stay neutral,
    so the accent means one thing across the row rather than decorating every box."""
    accent = color or '#e2e8f0'
    return html.Div(style={
        'flex': '1', 'minWidth': '150px',
        'background': _CARD_BG, 'border': f'1px solid {_CARD_BOR}',
        'borderTop': f'3px solid {accent}',
        'borderRadius': '10px', 'padding': '16px 18px',
        'boxShadow': '0 2px 6px rgba(0,0,0,0.03)',
    }, children=[
        html.Div(value, style={
            'fontSize': '24px', 'fontWeight': '800', 'color': color or '#1e293b',
            'fontFamily': DISPLAY_FONT, 'lineHeight': '1',
        }),
        html.Div(label, style={
            'fontSize': '10px', 'fontWeight': '700', 'color': '#94a3b8',
            'textTransform': 'uppercase', 'letterSpacing': '0.07em', 'marginTop': '8px',
        }),
        html.Div(sub, style={'fontSize': '11px', 'color': '#64748b', 'marginTop': '3px'}) if sub else None,
    ])


def _render_lifecycle(m: dict) -> html.Div:
    """Two-act narrative built on the confirmed status codes: the open book (O/N/A)
    and how it resolves (F/C/T). Deliberately not a literal flow/Sankey diagram —
    the data is a status snapshot, not a tracked per-PO transition log."""
    oldest = m['oldest_active']
    oldest_str = f'{oldest / 365:.1f}y' if oldest else '—'

    card_live = html.Div(style={
        'background': _CARD_BG, 'border': f'1px solid {_CARD_BOR}',
        'borderRadius': '12px', 'padding': '24px 28px',
        'boxShadow': '0 2px 8px rgba(0,0,0,0.04)',
    }, children=[
        html.Div('Currently Live', style={'fontSize': '15px', 'fontWeight': '700', 'color': '#1e293b'}),
        html.Div('The open book — O, N, and A status', style={
            'fontSize': '11px', 'color': '#94a3b8', 'marginBottom': '18px',
        }),
        html.Div(style={'display': 'flex', 'gap': '14px', 'flexWrap': 'wrap'}, children=[
            _stat_box(_fmt_count(m['active_count']), 'Active POs'),
            _stat_box(_fmt_val(m['active_val']), 'Ordered value', _ACCENT),
            _stat_box(_fmt_val(m['active_open']), 'Uninvoiced balance', _ACCENT, sub='amount − arr_amount'),
            _stat_box(oldest_str, 'Oldest Live Commitment', sub='Still on the books' if oldest else 'No active POs'),
        ]),
        _render_active_composition(m),
        _render_active_fulfilment(m),
        _render_invoicing_agreement(m),
    ])

    connector = html.Div(style={
        'display': 'flex', 'alignItems': 'center', 'gap': '10px', 'padding': '10px 0',
    }, children=[
        html.Div(style={'flex': '1', 'height': '1px', 'background': '#e2e8f0'}),
        html.Div('once resolved ↓', style={
            'fontSize': '10px', 'color': '#94a3b8', 'textTransform': 'uppercase',
            'letterSpacing': '0.08em', 'whiteSpace': 'nowrap',
        }),
        html.Div(style={'flex': '1', 'height': '1px', 'background': '#e2e8f0'}),
    ])

    counts = m['resolution_counts']
    labels = [_STATUS_CFG[s]['label'] for s in _HISTORICAL_STATUSES]
    values = [counts.get(s, 0) for s in _HISTORICAL_STATUSES]
    colors = [_STATUS_CFG[s]['color'] for s in _HISTORICAL_STATUSES]

    donut = go.Figure(data=[go.Pie(
        labels=labels, values=values, hole=0.62,
        marker=dict(colors=colors, line=dict(color='#ffffff', width=2)),
        textinfo='label+percent', textfont=dict(size=11, color='#334155'),
        hovertemplate='<b>%{label}</b><br>%{value:,} POs (%{percent})<extra></extra>',
        sort=False,
    )])
    donut.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(t=10, b=10, l=10, r=10), height=220, showlegend=False,
        font=dict(family="'Inter', sans-serif"),
        annotations=[dict(
            text=_fmt_count(m['resolution_total']), showarrow=False,
            font=dict(size=18, color='#1e293b', family=DISPLAY_FONT),
        )],
    )

    card_resolved = html.Div(style={
        'background': _CARD_BG, 'border': f'1px solid {_CARD_BOR}',
        'borderRadius': '12px', 'padding': '24px 28px',
        'boxShadow': '0 2px 8px rgba(0,0,0,0.04)',
    }, children=[
        html.Div('How POs Get Resolved', style={'fontSize': '15px', 'fontWeight': '700', 'color': '#1e293b'}),
        html.Div('F, C, and T status — the closed book', style={
            'fontSize': '11px', 'color': '#94a3b8', 'marginBottom': '10px',
        }),
        html.Div(style={'display': 'flex', 'gap': '20px', 'alignItems': 'center', 'flexWrap': 'wrap'}, children=[
            html.Div(
                dcc.Graph(figure=donut, config=PLOTLY_HOVER_CONFIG, style={'height': '220px', 'width': '220px'}),
                style={'flex': '0 0 220px'},
            ),
            html.Div(style={
                'flex': '1', 'minWidth': '280px', 'display': 'flex', 'gap': '14px', 'flexWrap': 'wrap',
            }, children=[
                _stat_box(_fmt_count(m['resolved_count']), 'Resolved POs'),
                _stat_box(_fmt_val(m['released_budget']), 'Released, not spent', _WARN_C,
                          sub='Left on Closed (C) POs'),
                _stat_box(f"{m['clean_completion_rate']:.0f}%", 'Clean completion', _STATUS_CFG['F']['color'],
                          sub='Finished automatically'),
                _stat_box(f"{m['error_rate']:.1f}%", 'Raised in error', _STATUS_CFG['T']['color'],
                          sub='Terminated, share of resolved'),
            ]),
        ]),
        _render_resolved_fulfilment(m),
        _render_resolved_agreement(m),
        _render_finished_balance_callout(m),
    ])

    return html.Div(style={'marginBottom': '24px'}, children=[card_live, connector, card_resolved])


# ── Header vs line-level status ────────────────────────────────────────────────

def _render_line_status(m: dict) -> html.Div:
    lsc = m['line_status_counts']
    if lsc.empty:
        return html.Div()

    total = lsc['line_count'].sum() or 1
    rows = []
    for _, r in lsc.sort_values('line_count', ascending=False).iterrows():
        s = r['line_status']
        cfg = _STATUS_CFG.get(s, {'color': '#94a3b8', 'label': s})
        cnt = int(r['line_count'])
        pct = cnt / total * 100
        rows.append(html.Div(style={
            'display': 'flex', 'alignItems': 'center', 'gap': '10px',
            'padding': '5px 0', 'borderBottom': '1px solid #f1f5f9',
        }, children=[
            html.Span(cfg['label'], style={'fontSize': '11px', 'color': '#475569', 'minWidth': '90px'}),
            html.Div(style={
                'flex': '1', 'height': '7px', 'background': _BAR_TRACK_LIGHT,
                'borderRadius': '4px', 'overflow': 'hidden',
            }, children=[
                html.Div(style={
                    'height': '100%', 'width': f'{min(pct, 100):.1f}%',
                    'background': cfg['color'], 'borderRadius': '4px',
                }),
            ]),
            html.Span(f'{cnt:,}', style={
                'fontSize': '12px', 'fontWeight': '700', 'color': cfg['color'],
                'minWidth': '54px', 'textAlign': 'right',
            }),
            html.Span(f'{pct:.0f}%', style={'fontSize': '10px', 'color': '#94a3b8', 'minWidth': '34px'}),
        ]))

    return html.Div(style={
        'background': _CARD_BG, 'border': f'1px solid {_CARD_BOR}',
        'borderRadius': '12px', 'padding': '20px 24px', 'marginBottom': '24px',
        'boxShadow': '0 2px 8px rgba(0,0,0,0.04)',
        'display': 'flex', 'gap': '28px', 'flexWrap': 'wrap',
    }, children=[
        html.Div(style={'flex': '1', 'minWidth': '260px'}, children=[
            html.Div('Line-Level Status', style={'fontSize': '13px', 'fontWeight': '700', 'color': '#1e293b', 'marginBottom': '4px'}),
            html.Div('apodetail.status — independent of the PO header', style={'fontSize': '11px', 'color': '#94a3b8', 'marginBottom': '14px'}),
            html.Div(rows),
        ]),
        html.Div(style={
            'flex': '0 0 220px', 'padding': '16px 18px',
            'background': '#faf9fd', 'border': '1px solid #ede9f8', 'borderRadius': '10px',
            'display': 'flex', 'flexDirection': 'column', 'justifyContent': 'center',
        }, children=[
            html.Div(f'{m["mismatch_pct"]:.1f}%', style={
                'fontSize': '30px', 'fontWeight': '800', 'color': '#7c3aed',
                'fontFamily': DISPLAY_FONT, 'lineHeight': '1',
            }),
            html.Div('of lines carry a different status to their PO header', style={
                'fontSize': '11px', 'color': '#64748b', 'marginTop': '8px',
            }),
            html.Div(f'{m["mismatch_count"]:,} lines', style={
                'fontSize': '11px', 'color': '#94a3b8', 'marginTop': '6px',
            }),
        ]),
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

def render_tab(dq_results, frames: dict) -> html.Div:
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

        # ── PO Lifecycle ──
        _section_div('PO Lifecycle',
                     'What the status codes tell us — a snapshot, not a tracked transition log'),
        _render_lifecycle(m),

        # ── Header vs line-level status ──
        _render_line_status(m),

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

        # ── Data Quality Checks ──
        _section_div('Data Quality Checks',
                     'DQ rules applied against the extracted population'),
        render_dimension_scorecard(dq_results),
        render_dimension_grid(dq_results),

    ])
