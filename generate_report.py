#!/usr/bin/env python3
"""
Generate a self-contained HTML DQ report for Parliament review.
Run from project root:  python generate_report.py
Output: dq_report_suppliers.html
"""

import os, sys
from datetime import date
from html import escape as H
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dashboard.data_engine import load_data, run_dq_analysis, get_failing_records, get_check_columns

OUTPUT      = 'dq_report_suppliers.html'
TODAY       = date.today().strftime('%d %B %Y')
SCOPE_IDS   = {10, 16, 18}
HOUSES      = ['HOC', 'HOL']
SCOPE_LABELS = {10: 'Supplier Master', 16: 'AP Open Invoices', 18: 'AP History'}
MAX_ROWS     = 1000  # cap per check/house to keep file size reasonable

DIM_COLOR = {
    'Completeness':          ('#EFF6FF', '#1D4ED8'),
    'Validity':              ('#F5F3FF', '#6D28D9'),
    'Consistency':           ('#FFF7ED', '#C2410C'),
    'Uniqueness':            ('#F0FDFA', '#0F766E'),
    'Timeliness':            ('#FDF4FF', '#9333EA'),
    'Referential Integrity': ('#FFF1F2', '#BE123C'),
}
SEV_COLOR = {
    'Critical': ('#FEF2F2', '#DC2626'),
    'High':     ('#FFF7ED', '#EA580C'),
    'Medium':   ('#FEFCE8', '#CA8A04'),
    'Low':      ('#F5F3FF', '#7C3AED'),
}
SEV_ORDER   = {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}
HOUSE_BG    = {'HOC': '#1E3A5F', 'HOL': '#5C1A3A'}
DIM_ORDER   = ['Completeness', 'Validity', 'Consistency', 'Uniqueness',
               'Timeliness', 'Referential Integrity']


def rag(pass_rate):
    if pass_rate >= 98: return '#16A34A', '#F0FDF4'
    if pass_rate >= 90: return '#D97706', '#FFFBEB'
    return '#DC2626', '#FEF2F2'


# ── CSS ───────────────────────────────────────────────────────────────────────
CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
     background:#F1F5F9;color:#1E293B;line-height:1.5;font-size:14px}
a{color:inherit;text-decoration:none}

.topbar{position:sticky;top:0;z-index:100;background:#1e1528;padding:0 28px;
        display:flex;align-items:center;gap:16px;box-shadow:0 2px 10px rgba(0,0,0,.4);
        height:54px;flex-wrap:wrap}
.topbar-title{color:#fff;font-size:15px;font-weight:800;flex:1;white-space:nowrap}
.topbar-date{color:#a090c0;font-size:12px;white-space:nowrap}
.nav-link{color:#c4b5db;font-size:12px;font-weight:600;padding:5px 14px;
          border-radius:20px;border:1px solid #3d2f5a;white-space:nowrap}
.nav-link:hover{background:#2d2040;color:#fff}

.page{max-width:1380px;margin:0 auto;padding:28px 20px}

.section-hdr{display:flex;align-items:baseline;gap:12px;margin:40px 0 18px;
             padding-bottom:10px;border-bottom:2px solid #E2E8F0}
.section-hdr h2{font-size:21px;font-weight:800;color:#1e1528}
.section-hdr .sub{font-size:13px;color:#94A3B8}

/* KPI row */
.kpi-row{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));
         gap:14px;margin-bottom:28px}
.kpi{background:#fff;border-radius:12px;padding:18px 22px;border:1px solid #E2E8F0}
.kpi .v{font-size:34px;font-weight:800;line-height:1}
.kpi .l{font-size:11px;color:#64748B;margin-top:5px;font-weight:600;
        text-transform:uppercase;letter-spacing:.06em}

/* Dimension scorecard */
.dim-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));
          gap:12px;margin-bottom:32px}
.dim-card{background:#fff;border-radius:10px;padding:16px 18px;border:1px solid #E2E8F0}
.dim-name{font-size:13px;font-weight:700;margin-bottom:12px}
.dim-row{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.house-pill{font-size:11px;font-weight:700;color:#fff;padding:2px 9px;
            border-radius:10px;min-width:40px;text-align:center}
.pbar-wrap{flex:1;background:#F1F5F9;border-radius:4px;height:7px}
.pbar{height:100%;border-radius:4px}
.pbar-pct{font-size:12px;font-weight:700;min-width:46px;text-align:right}

/* Dimension group header inside section */
.dim-group-hdr{margin:22px 0 10px;padding:9px 16px;border-radius:8px;
               display:flex;align-items:center;gap:10px}
.dim-group-hdr span{font-size:13px;font-weight:700}

/* Check card */
.check-card{background:#fff;border-radius:12px;border:1px solid #E2E8F0;
            margin-bottom:14px;overflow:hidden}
.check-top{padding:16px 20px}
.check-badges{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.badge{display:inline-block;padding:3px 11px;border-radius:20px;
       font-size:11px;font-weight:700;letter-spacing:.03em}
.check-id{font-size:11px;color:#94A3B8;font-family:monospace;padding:3px 8px;
          background:#F8FAFC;border-radius:6px;border:1px solid #E2E8F0}
.check-title{font-size:15px;font-weight:700;color:#1e1528;margin-bottom:4px}
.check-intent{font-size:13px;color:#475569;background:#F8FAFC;
              border-left:3px solid #CBD5E1;padding:10px 14px;
              border-radius:0 6px 6px 0;margin:10px 0 0}

.check-body{padding:16px 20px;padding-top:0}
.houses-row{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}
@media(max-width:900px){.houses-row{grid-template-columns:1fr}}

/* House block */
.hblock{border:1px solid #E2E8F0;border-radius:8px;overflow:hidden}
.hblock-hdr{padding:10px 16px;display:flex;align-items:center;
            justify-content:space-between}
.hblock-title{font-size:13px;font-weight:800;color:#fff}
.hblock-pct{font-size:13px;font-weight:800;padding:2px 10px;border-radius:10px}
.stats-strip{display:flex;gap:24px;padding:10px 16px;background:#F8FAFC;
             border-bottom:1px solid #F1F5F9}
.stat .sv{font-size:22px;font-weight:800;line-height:1}
.stat .sl{font-size:10px;color:#94A3B8;font-weight:600;
          text-transform:uppercase;letter-spacing:.06em;margin-top:2px}

/* Records expand */
details summary{padding:10px 16px;font-size:12px;font-weight:600;color:#475569;
                cursor:pointer;background:#FAFAFA;list-style:none;
                display:flex;align-items:center;gap:8px;
                border-top:1px solid #F1F5F9;user-select:none}
details summary::-webkit-details-marker{display:none}
details summary .arrow{font-size:9px;display:inline-block;transition:transform .15s}
details[open] summary .arrow{transform:rotate(90deg)}
details summary:hover{background:#F1F5F9}
.all-pass{padding:12px 16px;font-size:12px;font-weight:600;
          color:#16A34A;background:#F0FDF4;border-top:1px solid #DCFCE7}
.records-wrap{overflow-x:auto;max-height:600px;overflow-y:auto}

/* Table */
table{width:100%;border-collapse:collapse;font-size:12px}
thead{position:sticky;top:0;z-index:1}
thead th{background:#F1F5F9;color:#475569;padding:8px 12px;text-align:left;
         border-bottom:2px solid #E2E8F0;white-space:nowrap;
         font-size:11px;font-weight:700}
thead th.hl{background:#FEF2F2;color:#991B1B}
thead th.key{background:#F0F9FF;color:#1D4ED8}
tbody tr:nth-child(even){background:#FAFAFA}
tbody td{padding:7px 12px;border-bottom:1px solid #F5F7FA;
         color:#334155;vertical-align:top;max-width:280px;
         word-break:break-word}
tbody td.hl{background:#FFF5F5;color:#991B1B;font-weight:600}
tbody td.null{color:#CBD5E1}
tbody td.name{font-weight:600;color:#1e1528}
.capped-row td{color:#94A3B8;font-style:italic;text-align:center;
               padding:12px;background:#FAFAFA}

/* Remediation */
.remediation{margin-top:10px;padding:10px 14px;background:#FFFBEB;
             border-left:3px solid #FCD34D;border-radius:0 6px 6px 0;
             font-size:12px;color:#92400E}
.remediation strong{display:block;margin-bottom:3px;font-size:11px;
                    text-transform:uppercase;letter-spacing:.06em}

/* Print */
@media print{
  .topbar{position:relative}
  details{display:block}
  details summary{display:none}
  .records-wrap{max-height:none;overflow:visible}
}
"""


def render_table(df, highlight_cols):
    if df is None or df.empty:
        return '<div class="all-pass">✓ All records pass this check</div>'

    has_name = 'Master_Supplier_Name' in df.columns or 'Master_Customer_Name' in df.columns
    name_col = 'Master_Supplier_Name' if 'Master_Supplier_Name' in df.columns else 'Master_Customer_Name'

    # Columns to display: strip table prefix, skip internal columns
    skip_bare = {'house', 'Master_Supplier_Name', 'Master_Customer_Name',
                 'Master_Status', 'wf_state', 'last_update'}
    display = []
    for c in df.columns:
        bare = c.split('.')[-1] if '.' in c else c
        if bare not in skip_bare:
            display.append((c, bare))

    total = len(df)
    df_show = df.head(MAX_ROWS)

    rows = ['<div class="records-wrap"><table><thead><tr>']
    if has_name:
        rows.append('<th class="key">Supplier Name</th>')
    for _, bare in display:
        cls = ' class="hl"' if bare in highlight_cols else ''
        rows.append(f'<th{cls}>{H(bare.replace("_"," ").title())}</th>')
    rows.append('</tr></thead><tbody>')

    for _, row in df_show.iterrows():
        rows.append('<tr>')
        if has_name:
            nv = row.get(name_col, '')
            rows.append(f'<td class="name">{H(str(nv)) if pd.notna(nv) and str(nv) not in ("nan","None","—") else "<span class=null>—</span>"}</td>')
        for col, bare in display:
            val = row[col]
            is_hl = bare in highlight_cols
            cls = ' class="hl"' if is_hl else ''
            if pd.isna(val) or str(val) in ('nan', 'None', '—', ''):
                cell = '<span class="null">—</span>'
                cls = ' class="null"'
            else:
                v = str(val)
                # strip trailing .0 from numeric IDs
                if v.endswith('.0') and v[:-2].lstrip('-').isdigit():
                    v = v[:-2]
                cell = H(v)
            rows.append(f'<td{cls}>{cell}</td>')
        rows.append('</tr>')

    if total > MAX_ROWS:
        ncols = len(display) + (1 if has_name else 0)
        rows.append(f'<tr class="capped-row"><td colspan="{ncols}">Showing first {MAX_ROWS:,} of {total:,} records — run the dashboard for full data</td></tr>')

    rows.append('</tbody></table></div>')
    return ''.join(rows)


def render_house_block(check_id, house, row, frames, highlight_cols):
    total   = int(row['total'])
    failing = int(row['failing'])
    passing = int(row['passing'])
    prate   = float(row['pass_rate'])
    rem     = str(row.get('remediation', ''))
    fg, bg  = rag(prate)

    if failing > 0:
        try:
            fail_df = get_failing_records(check_id, house, frames)
        except Exception as e:
            fail_df = pd.DataFrame()
    else:
        fail_df = pd.DataFrame()

    table_html  = render_table(fail_df, set(highlight_cols))
    rec_count   = len(fail_df) if fail_df is not None else 0
    summary_txt = f'<span class="arrow">▶</span> Show {rec_count:,} failing records' if rec_count > 0 else '<span class="arrow">▶</span> 0 failing records'
    details_open = ' open' if 0 < rec_count <= 30 else ''

    rem_html = f'<div class="remediation"><strong>Remediation</strong>{H(rem)}</div>' if rem and rem not in ('nan','None') else ''

    return f'''
<div class="hblock">
  <div class="hblock-hdr" style="background:{HOUSE_BG[house]}">
    <span class="hblock-title">{house}</span>
    <span class="hblock-pct" style="background:{bg};color:{fg}">{prate:.1f}%</span>
  </div>
  <div class="stats-strip">
    <div class="stat"><div class="sv" style="color:{fg}">{failing:,}</div><div class="sl">Failing</div></div>
    <div class="stat"><div class="sv" style="color:#64748B">{total:,}</div><div class="sl">Assessed</div></div>
    <div class="stat"><div class="sv" style="color:#16A34A">{passing:,}</div><div class="sl">Passing</div></div>
  </div>
  <details{details_open}>
    <summary>{summary_txt}</summary>
    {table_html}
  </details>
  {rem_html}
</div>'''


def render_check_card(check_id, check_rows, frames, check_col_map):
    r0 = check_rows.iloc[0]
    dim    = str(r0['dimension'])
    sev    = str(r0['severity'])
    desc   = str(r0['description'])
    intent = str(r0['intent'])

    dim_bg, dim_fg = DIM_COLOR.get(dim, ('#F8FAFC', '#475569'))
    sev_bg, sev_fg = SEV_COLOR.get(sev, ('#F8FAFC', '#475569'))
    highlight_cols = check_col_map.get(check_id, [])

    house_blocks = []
    for house in HOUSES:
        hr = check_rows[check_rows['house'] == house]
        if hr.empty:
            continue
        house_blocks.append(render_house_block(check_id, house, hr.iloc[0], frames, highlight_cols))

    both_pass = all(int(check_rows[check_rows['house']==h].iloc[0]['failing']) == 0
                    for h in HOUSES if not check_rows[check_rows['house']==h].empty)

    card_border = 'border-left:4px solid #16A34A' if both_pass else f'border-left:4px solid {sev_fg}'

    return f'''
<div class="check-card" id="{H(check_id)}" style="{card_border}">
  <div class="check-top">
    <div class="check-badges">
      <span class="badge" style="background:{dim_bg};color:{dim_fg}">{H(dim)}</span>
      <span class="badge" style="background:{sev_bg};color:{sev_fg}">{H(sev)}</span>
      <span class="check-id">{H(check_id)}</span>
    </div>
    <div class="check-title">{H(desc)}</div>
    <div class="check-intent">{H(intent)}</div>
  </div>
  <div class="check-body">
    <div class="houses-row">{"".join(house_blocks)}</div>
  </div>
</div>'''


def render_summary_section(scope_results):
    check_ids = scope_results['check_id'].unique()
    total     = len(check_ids)
    with_fail = int((scope_results.groupby('check_id')['failing'].sum() > 0).sum())
    crit_fail = int((scope_results[scope_results['severity']=='Critical']
                     .groupby('check_id')['failing'].sum() > 0).sum())
    passing   = total - with_fail

    kpis = f'''
<div class="kpi-row">
  <div class="kpi"><div class="v" style="color:#1e1528">{total}</div><div class="l">Total Checks</div></div>
  <div class="kpi"><div class="v" style="color:#DC2626">{with_fail}</div><div class="l">Checks with Failures</div></div>
  <div class="kpi"><div class="v" style="color:#EA580C">{crit_fail}</div><div class="l">Critical Failures</div></div>
  <div class="kpi"><div class="v" style="color:#16A34A">{passing}</div><div class="l">Checks Passing</div></div>
</div>'''

    dims_present = [d for d in DIM_ORDER if d in scope_results['dimension'].values]
    dim_cards = []
    for dim in dims_present:
        dim_bg, dim_fg = DIM_COLOR.get(dim, ('#F8FAFC', '#475569'))
        dr = scope_results[scope_results['dimension'] == dim]
        house_rows = []
        for house in HOUSES:
            hr = dr[dr['house'] == house]
            if hr.empty:
                continue
            prate = (hr['passing'].sum() / hr['total'].sum() * 100) if hr['total'].sum() > 0 else 0
            fg, _ = rag(prate)
            house_rows.append(f'''
<div class="dim-row">
  <span class="house-pill" style="background:{HOUSE_BG[house]}">{house}</span>
  <div class="pbar-wrap"><div class="pbar" style="width:{min(prate,100):.1f}%;background:{fg}"></div></div>
  <span class="pbar-pct" style="color:{fg}">{prate:.1f}%</span>
</div>''')
        dim_cards.append(f'''
<div class="dim-card">
  <div class="dim-name" style="color:{dim_fg}">{H(dim)}</div>
  {"".join(house_rows)}
</div>''')

    return f'''
<div id="summary">
  <div class="section-hdr"><h2>Executive Summary</h2><span class="sub">Suppliers &amp; AP — {TODAY}</span></div>
  {kpis}
  <div class="dim-grid">{"".join(dim_cards)}</div>
</div>'''


def render_scope_section(scope_id, label, dq_results, frames, check_col_map):
    rows = dq_results[dq_results['scope_id'] == scope_id]
    if rows.empty:
        return ''

    dims = [d for d in DIM_ORDER if d in rows['dimension'].values]
    content = []
    for dim in dims:
        dim_bg, dim_fg = DIM_COLOR.get(dim, ('#F8FAFC', '#475569'))
        dr = rows[rows['dimension'] == dim]
        # Sort checks: failing first, then by severity
        check_ids = (dr.groupby('check_id')['failing'].sum()
                       .reset_index()
                       .assign(sev=lambda x: x['check_id'].map(
                           lambda c: SEV_ORDER.get(
                               dr[dr['check_id']==c].iloc[0]['severity'], 9)))
                       .sort_values(['failing','sev'], ascending=[False, True])
                       ['check_id'].tolist())

        cards = []
        for cid in check_ids:
            cr = dr[dr['check_id'] == cid]
            print(f'  {cid}…')
            cards.append(render_check_card(cid, cr, frames, check_col_map))

        content.append(f'''
<div class="dim-group-hdr" style="background:{dim_bg}">
  <span style="color:{dim_fg}">{H(dim)}</span>
  <span style="font-size:12px;color:{dim_fg};opacity:.7">{len(check_ids)} checks</span>
</div>
{"".join(cards)}''')

    anchor = label.lower().replace(' ', '-')
    return f'''
<div id="{anchor}">
  <div class="section-hdr">
    <h2>{H(label)}</h2>
    <span class="sub">{rows["check_id"].nunique()} checks</span>
  </div>
  {"".join(content)}
</div>'''


def build_html(dq_results, frames, check_col_map):
    scope_results = dq_results[dq_results['scope_id'].isin(SCOPE_IDS)]

    nav = ''.join(
        f'<a href="#{lbl.lower().replace(" ","-")}" class="nav-link">{H(lbl)}</a>'
        for lbl in SCOPE_LABELS.values()
    )

    sections = [render_summary_section(scope_results)]
    for sid, slabel in SCOPE_LABELS.items():
        print(f'\n── {slabel} ──')
        sections.append(render_scope_section(sid, slabel, dq_results, frames, check_col_map))

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Parliament Finance — Supplier DQ Report — {TODAY}</title>
<style>{CSS}</style>
</head>
<body>
<div class="topbar">
  <span class="topbar-title">Parliament Finance Systems — Supplier &amp; AP Data Quality Assessment</span>
  <a href="#summary" class="nav-link">Summary</a>
  {nav}
  <span class="topbar-date">Generated {TODAY}</span>
</div>
<div class="page">
  {"".join(sections)}
</div>
</body>
</html>'''


if __name__ == '__main__':
    print('Loading data…')
    frames = load_data()
    print('Running DQ analysis…')
    dq      = run_dq_analysis(frames)
    col_map = get_check_columns()

    print('\nGenerating report…')
    html = build_html(dq, frames, col_map)

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write(html)

    size_kb = os.path.getsize(OUTPUT) / 1024
    print(f'\n✓ Written to {OUTPUT}  ({size_kb:,.0f} KB)')
