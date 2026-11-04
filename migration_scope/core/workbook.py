"""
Steward workbooks (export and re-import) and the governance summary.

Export: one workbook per House, one tab per kind of decision, each row showing
the recommendation and why, with Decision (dropdown), Reason and Steward
columns to fill in. The workbook lives in SharePoint; stewards mark it up.

Import: safe to upload the same file twice (a living workbook) or a fresh
monthly one. Rows are compared with the decisions already in force: same =
skipped, different = recorded as a new decision on top of the old one, new =
recorded. Nothing is applied until the preview has been confirmed.
"""
import io
from datetime import datetime

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from migration_scope import config
from migration_scope.core.model import (
    DECISIONS, DECISION_BY_LABEL, CLOSE, FIX, MONITOR, HELD, IN_SCOPE, NOT_IN_EXTRACT,
)

GREEN, INPUT, KEYFILL = '006548', 'FFF8E1', 'F1F5F9'
INPUT_COLS = ['Decision', 'Reason', 'Steward']

SHEETS = {
    # sheet: (key column, decision options, target type)
    'Close - confirm': ('Record key', ['AGREE', 'KEEP'], 'record'),
    'Duplicates': ('Record key', ['CONFIRM_PREFERRED', 'NOT_DUPLICATE', 'AGREE', 'KEEP', 'CLOSE'], 'record'),
    'Possible duplicates': ('Record key', ['SAME_SUPPLIER', 'DIFFERENT_SUPPLIER'], 'pair'),
    'Fix': ('Record key', ['WILL_FIX', 'ACCEPT_AS_IS', 'CLOSE'], 'record'),
    'Stuck items': ('Item key', ['MIGRATE', 'DONT_MIGRATE'], 'item'),
    'Held for policy': ('Record key', ['KEEP', 'CLOSE', 'AGREE'], 'record'),
}


def _fmt_date(d):
    return d.strftime('%d/%m/%Y') if pd.notna(d) else ''


def _label(code):
    return DECISIONS[code][0] if code else ''


def why_text(result, e):
    steps = result.trail(e)
    return steps[-1]['text'] if steps else ''


def _current(dec, target_type, key, family, related=''):
    if dec.empty:
        return ''
    m = dec[(dec['target_type'] == target_type) & (dec['target_key'] == key) & (dec['family'] == family)
            & (dec['related_key'] == related)]
    return '' if m.empty else f"{_label(m.iloc[-1]['decision'])} ({m.iloc[-1]['steward']}, {m.iloc[-1]['recorded_at'][:10]})"


def steward_frames(result, decisions, house=None):
    """The rows for each tab, as DataFrames (also used by tests)."""
    e = result.entities
    e = e[e['in_population']]
    if house:
        e = e[e['house'] == house]
    issues = result.issues
    out = {}

    def base(df):
        return pd.DataFrame({
            'Record key': df['entity_key'], 'House': df['house'], 'Supplier ID': df['apar_id'],
            'Clients': df['clients'], 'Name': df['apar_name'], 'Group': df['apar_gr_id'],
            'Recommendation': df['recommended'], 'Why': [why_text(result, r) for _, r in df.iterrows()],
            'Last activity': df['last_activity'].map(_fmt_date), 'Open items': df['open_items'],
            'Open POs': df['open_pos'],
        })

    close = e[(e['recommended'] == CLOSE) & (e['category'] == 'Commercial') & (e['dup_group'] == '')]
    df = base(close)
    df['Current decision'] = [_current(decisions, 'record', k, 'scope') for k in close['entity_key']]
    out['Close - confirm'] = df

    g = e[e['dup_group'] != ''].sort_values(['dup_group', 'preferred_rank'])
    df = base(g)
    df.insert(0, 'Duplicate group', g['dup_group'].values)
    df.insert(5, 'Proposed preferred', g['preferred'].map({True: 'Yes', False: ''}).values)
    df['Why matched'] = g['match_reasons'].values
    df['Blocking issues'] = g['blocking'].values
    df['Completeness (of 8)'] = g['completeness'].values
    df['Current decision'] = [
        '; '.join(x for x in (_current(decisions, 'record', k, 'dup'), _current(decisions, 'record', k, 'scope')) if x)
        for k in g['entity_key']]
    out['Duplicates'] = df

    names = result.entities.set_index('entity_key')['apar_name']
    p = result.possible
    if house:
        p = p[p['a'].str.startswith(house + '|')]
    out['Possible duplicates'] = pd.DataFrame({
        'Record key': p['a'], 'Name': p['a'].map(names), 'Matched record key': p['b'],
        'Matched name': p['b'].map(names), 'Name similarity %': p['score'],
        'Current decision': [_current(decisions, 'pair', a, 'pair', b) for a, b in zip(p['a'], p['b'])]})

    fx = e[e['recommended'] == FIX]
    df = base(fx)
    blk = issues[issues['blocking']].drop_duplicates(['entity_key', 'test_id'])
    txt = (blk['test_id'] + ' (' + blk['description'].astype(str) + ')').groupby(blk['entity_key']).agg('; '.join)
    df['Blocking issues'] = fx['entity_key'].map(txt).fillna('').values
    df['Current decision'] = [_current(decisions, 'record', k, 'scope') for k in fx['entity_key']]
    out['Fix'] = df

    it = result.items[result.items['stuck']]
    it = it[it['entity_key'].isin(e['entity_key'])].sort_values(['entity_key', 'trans_date'])
    out['Stuck items'] = pd.DataFrame({
        'Item key': it['item_key'], 'Record key': it['entity_key'], 'Supplier': it['entity_key'].map(names),
        'Voucher': it['voucher_no'], 'Type': it['voucher_type'], 'Transaction date': it['trans_date'].map(_fmt_date),
        'Financial year': it['fy'], 'Age (days)': it['age_days'], 'Outstanding (£)': it['rest_amount'].round(2),
        'Supplier ref': it['ext_inv_ref'],
        'Current decision': [_current(decisions, 'item', k, 'item') for k in it['item_key']]})

    held = e[e['recommended'].isin(HELD)]
    df = base(held)
    df.insert(6, 'Category', held['category_detail'].values)
    df['Current decision'] = [_current(decisions, 'record', k, 'scope') for k in held['entity_key']]
    out['Held for policy'] = df

    xh = e[e['cross_house'] != '']
    out['Cross-House (info)'] = pd.DataFrame({
        'Record key': xh['entity_key'], 'Name': xh['apar_name'], 'Classification': xh['classification'],
        'Matches': xh['cross_house'], 'Comment': ''})
    return out


def export_steward_workbook(result, decisions, house=None) -> bytes:
    frames = steward_frames(result, decisions, house)
    wb = Workbook()
    readme = wb.active
    readme.title = 'Read me'
    lines = [
        ('Migration scope review: suppliers' + (f' ({house})' if house else ''), True),
        (f"Produced {datetime.now():%d %b %Y %H:%M} · data as at {result.as_of:%d %b %Y} · "
         f"ruleset v{config.RULESET_VERSION}", False),
        ('', False),
        ('How to fill this in', True),
        ('1. Each tab lists records needing one kind of decision. The Recommendation and Why columns explain '
         'what the rules concluded.', False),
        ('2. Choose a Decision from the dropdown, give a Reason (mandatory) and your name in Steward.', False),
        ('3. Leave Decision blank if you are not deciding yet. Existing decisions are shown in Current decision; '
         'enter a new one only to change it.', False),
        ('4. Save the workbook in SharePoint. It will be uploaded to the dashboard; nothing is applied without a '
         'preview first.', False),
        ('', False),
        ('Tabs', True),
        ('Close - confirm: dormant suppliers recommended for closure. Agree, or Keep with a reason.', False),
        ('Duplicates: one block per duplicate group. The proposed preferred record is marked Yes. Confirm it, or '
         'confirm a different one, or mark a record Not a duplicate.', False),
        ('Possible duplicates: similar names. Say whether they are the same supplier.', False),
        ('Fix: suppliers being kept that have blocking data issues (test IDs refer to the DQA dashboard).', False),
        ('Stuck items: open items more than '
         f"{result.params['stuck_item_months']} months old. Migrate or don't migrate.", False),
        ('Held for policy: non-commercial and card-account records.', False),
        ('Cross-House (info): HoC and HoL suppliers that look like the same company. For information only.', False),
    ]
    for i, (t, bold) in enumerate(lines, 1):
        c = readme.cell(row=i, column=1, value=t)
        c.font = Font(bold=bold, size=14 if i == 1 else 11, color=GREEN if bold else '1F2937')
    readme.column_dimensions['A'].width = 130

    for name, df in frames.items():
        ws = wb.create_sheet(name[:31])
        info = SHEETS.get(name)
        cols = list(df.columns) + (INPUT_COLS if info else [])
        ws.append(cols)
        for row in df.itertuples(index=False):
            ws.append([None if (isinstance(v, float) and pd.isna(v)) else v for v in row])
        for j, col in enumerate(cols, 1):
            cell = ws.cell(row=1, column=j)
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor=GREEN if col not in INPUT_COLS else 'B45309')
            cell.alignment = Alignment(wrap_text=True, vertical='top')
            width = {'Why': 60, 'Why matched': 55, 'Blocking issues': 60, 'Name': 34, 'Reason': 40,
                     'Matches': 55, 'Current decision': 34, 'Decision': 30, 'Supplier': 30}.get(col, 16)
            ws.column_dimensions[get_column_letter(j)].width = width
            if col in INPUT_COLS or col in ('Record key', 'Item key'):
                fill = PatternFill('solid', fgColor=INPUT if col in INPUT_COLS else KEYFILL)
                for r in range(2, ws.max_row + 1):
                    ws.cell(row=r, column=j).fill = fill
        if info and ws.max_row > 1:
            options = ','.join(DECISIONS[c][0] for c in info[1])
            dv = DataValidation(type='list', formula1=f'"{options}"', allow_blank=True)
            dv.error, dv.errorTitle = 'Choose a decision from the list', 'Invalid decision'
            ws.add_data_validation(dv)
            col = get_column_letter(cols.index('Decision') + 1)
            dv.add(f'{col}2:{col}{ws.max_row + 500}')
        ws.freeze_panes = 'B2'
        ws.auto_filter.ref = ws.dimensions
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── Import ───────────────────────────────────────────────────────────────────

def preview_upload(content: bytes, filename, result, decisions):
    """Read a returned workbook and classify every filled-in row. Applies nothing."""
    wb = load_workbook(io.BytesIO(content), data_only=True)
    entity_keys = set(result.entities['entity_key'])
    labels = result.entities.set_index('entity_key')['apar_name'].to_dict()
    rec = result.entities.set_index('entity_key')['recommended'].to_dict()
    item_keys = set(result.items['item_key'])
    rows = []
    for sheet, (key_col, allowed, ttype) in SHEETS.items():
        if sheet not in wb.sheetnames:
            continue
        ws = wb[sheet]
        data = list(ws.values)
        if not data:
            continue
        head = [str(h).strip() if h is not None else '' for h in data[0]]
        if 'Decision' not in head or key_col not in head:
            continue
        ix = {h: i for i, h in enumerate(head)}
        for n, vals in enumerate(data[1:], start=2):
            get = lambda c: ('' if c not in ix or vals[ix[c]] is None else str(vals[ix[c]]).strip())
            label = get('Decision')
            if not label:
                continue
            key, related = get(key_col), get('Matched record key') if ttype == 'pair' else ''
            row = {'sheet': sheet, 'row': n, 'target_type': ttype, 'target_key': key, 'related_key': related,
                   'decision_label': label, 'reason': get('Reason'), 'steward': get('Steward'),
                   'record_label': labels.get(key, get('Name') or get('Supplier'))}
            code = DECISION_BY_LABEL.get(label)
            problem = ''
            if code not in allowed:
                problem = f'"{label}" is not a valid decision on this tab'
            elif not row['reason']:
                problem = 'No reason given'
            elif not row['steward']:
                problem = 'No steward name given'
            row['decision'] = code or ''
            row['recommendation'] = rec.get(key, 'Needs review' if ttype == 'item' else '')
            family = DECISIONS[code][1] if code else ''
            if not problem:
                rel = related
                tkey = key
                if ttype == 'pair':
                    tkey, rel = min(key, related), max(key, related)
                cur = decisions[(decisions['target_type'] == ttype) & (decisions['target_key'] == tkey)
                                & (decisions['family'] == family) & (decisions['related_key'] == rel)] \
                    if not decisions.empty else decisions
                if not cur.empty and cur.iloc[-1]['decision'] == code:
                    row['status'] = 'Already recorded'
                else:
                    known = (key in item_keys) if ttype == 'item' else (
                        key in entity_keys and (ttype != 'pair' or related in entity_keys))
                    if not known:
                        problem = 'Record not in the latest extract'
                    else:
                        row['status'] = 'Changed decision' if not cur.empty else 'New decision'
            if problem:
                row['status'], row['problem'] = 'Rejected', problem
            rows.append(row)
    df = pd.DataFrame(rows)
    counts = df['status'].value_counts().to_dict() if not df.empty else {}
    return {'file': filename, 'rows': df.to_dict('records'), 'counts': counts, 'total': len(df)}


def apply_upload(preview, store, obj, content=None):
    """Write the new and changed decisions from a confirmed preview."""
    todo = [r for r in preview['rows'] if r.get('status') in ('New decision', 'Changed decision')]
    if not todo:
        return 0
    store.backup('before_upload')
    if content is not None:
        config.UPLOAD_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        (config.UPLOAD_ARCHIVE_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{preview['file']}").write_bytes(content)
    rows = [{**r, 'object': obj} for r in todo]
    return store.add_decisions(rows, source=preview['file'])


# ── Other exports ────────────────────────────────────────────────────────────

def table_bytes(sheets: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name[:31], index=False)
            ws = xw.sheets[name[:31]]
            for j, col in enumerate(df.columns, 1):
                ws.cell(row=1, column=j).font = Font(bold=True, color='FFFFFF')
                ws.cell(row=1, column=j).fill = PatternFill('solid', fgColor=GREEN)
                ws.column_dimensions[get_column_letter(j)].width = min(max(len(str(col)) + 4, 14), 60)
            ws.freeze_panes = 'A2'
            ws.auto_filter.ref = ws.dimensions
    return buf.getvalue()


def governance_summary(engine, obj='suppliers') -> bytes:
    r = engine.result(obj)
    s = engine.summary(obj)
    e = r.entities[r.entities['classification'] != NOT_IN_EXTRACT]
    stages = [('In Unit4', 'unit4'), ('Closed or terminated (never in scope)', 'closed_terminated'),
              ('Legacy exclusions', 'legacy'), ('Population (N and P)', 'population'),
              ('Held: non-commercial', 'noncommercial'), ('Held: policy decision', 'policy'),
              ('Classified (commercial)', 'classified'), ('Keep', 'Keep'), ('Fix', 'Fix'), ('Monitor', 'Monitor'),
              ('Close', 'Close'), ('IN SCOPE (would go to the SI today)', 'in_scope')]
    funnel = pd.DataFrame([{'Stage': lab, 'HoC': s['HOC'][k], 'HoL': s['HOL'][k], 'Total': s['all'][k]}
                           for lab, k in stages])
    ins = e[e['in_scope']]
    iss = r.issues[r.issues['entity_key'].isin(ins['entity_key'])].drop_duplicates(['entity_key', 'test_id'])
    issues = iss.groupby(['test_id', 'dimension', 'blocking', 'description']).size().reset_index(name='Suppliers') \
        .sort_values('Suppliers', ascending=False)
    dec = engine.store.decisions(obj)
    dec_sum = dec.groupby(['decision', 'steward']).size().reset_index(name='Count') if not dec.empty else \
        pd.DataFrame(columns=['decision', 'steward', 'Count'])
    if not dec_sum.empty:
        dec_sum['decision'] = dec_sum['decision'].map(_label)
    follow = e[e['follow_through'] != ''][['entity_key', 'apar_name', 'decision', 'decision_by', 'follow_through']]
    snap, changes = engine.changes_since_snapshot(obj)
    head = pd.DataFrame([
        {'Item': 'Data as at', 'Value': f'{r.as_of:%d %b %Y}'},
        {'Item': 'Data source', 'Value': r.source},
        {'Item': 'Ruleset version', 'Value': config.RULESET_VERSION},
        {'Item': 'Duplicate groups (resolved / total)', 'Value': f"{s['dup_groups_resolved']} / {s['dup_groups']}"},
        {'Item': 'Records awaiting a steward decision', 'Value': s['awaiting']},
        {'Item': 'Decisions recorded', 'Value': s['decisions']},
        {'Item': 'Compared with snapshot', 'Value': snap['label'] if snap is not None else 'No snapshot saved yet'},
    ])
    return table_bytes({'Summary': head, 'Scope funnel': funnel, 'Issues in scope': issues,
                        'Decisions': dec_sum, 'Follow-through': follow,
                        'Changes since snapshot': changes if not changes.empty else pd.DataFrame(
                            columns=['entity_key', 'before', 'now', 'cause'])})
