"""
Dash callbacks for the Migration Scope module. register(app, frames) is the
only thing the dashboard calls; every component id here starts with 'ms-'.
"""
import base64
import json
from datetime import datetime

import dash
from dash import ALL, Input, Output, State, html, no_update

from migration_scope.core.engine import Engine
from migration_scope.core.model import DECISIONS
from migration_scope.core.workbook import (
    export_steward_workbook, preview_upload, apply_upload, table_bytes, governance_summary,
)
from migration_scope.ui import views
from migration_scope.ui.theme import icon

OBJ = 'suppliers'
_ENGINE = {'engine': None, 'frames': None}


def engine():
    if _ENGINE['engine'] is None:
        _ENGINE['engine'] = Engine(_ENGINE['frames'])
    return _ENGINE['engine']


def render():
    """Called by the dashboard's tab router."""
    try:
        return views.layout(engine(), OBJ)
    except Exception as exc:  # show the problem in the page rather than a blank tab
        import traceback
        traceback.print_exc()
        return html.Div(style={'padding': '40px', 'color': '#B91C1C'}, children=[
            html.H3('Migration Scope could not load'), html.Pre(str(exc))])


def _filtered(f):
    r = engine().result(OBJ)
    e = views.filter_entities(r.entities, r.fired, f)
    if f.get('chase'):
        e = e[(e['follow_through'] == 'Not yet actioned in Unit4') | e['follow_through'].str.startswith('Conflict')
              | (e['alert'] != '')]
    return r, e


def _clicked():
    t = dash.ctx.triggered
    return bool(t) and bool(t[0].get('value'))


def register(app, frames):
    _ENGINE['frames'] = frames

    # ── View switching ───────────────────────────────────────────────────────
    @app.callback(Output('ms-view', 'data'), Input({'type': 'ms-tab', 'v': ALL}, 'n_clicks'),
                  prevent_initial_call=True)
    def switch_view(_):
        if not _clicked():
            return no_update
        return dash.ctx.triggered_id['v']

    @app.callback([Output(f'ms-view-{v}', 'style') for v, _, _ in views.VIEWS] +
                  [Output({'type': 'ms-tab', 'v': ALL}, 'className')],
                  Input('ms-view', 'data'))
    def show_view(view):
        styles = [{} if v == view else {'display': 'none'} for v, _, _ in views.VIEWS]
        tabs = ['ms-tab' + (' ms-tab-on' if o['id']['v'] == view else '') for o in dash.ctx.outputs_list[-1]]
        return styles + [tabs]

    # ── Overview (re-rendered when decisions or snapshots change) ────────────
    @app.callback(Output('ms-view-overview', 'children'), Input('ms-version', 'data'))
    def render_overview(_v):
        return views.overview(engine(), OBJ)

    @app.callback(Output('ms-filters', 'data', allow_duplicate=True), Output('ms-view', 'data', allow_duplicate=True),
                  Input({'type': 'ms-goto', 'f': ALL}, 'n_clicks'), prevent_initial_call=True)
    def goto(_):
        if not _clicked():
            return no_update, no_update
        return json.loads(dash.ctx.triggered_id['f']), 'records'

    # ── Filters ──────────────────────────────────────────────────────────────
    @app.callback(Output('ms-filters', 'data', allow_duplicate=True),
                  Input({'type': 'ms-chip', 'g': ALL, 'v': ALL}, 'n_clicks'),
                  Input({'type': 'ms-rulecard', 'r': ALL}, 'n_clicks'),
                  Input('ms-search', 'value'), Input('ms-toggles', 'value'), Input('ms-clear', 'n_clicks'),
                  State('ms-filters', 'data'), prevent_initial_call=True)
    def update_filters(_c, _r, search, toggles, _clear, f):
        f = dict(f or {})
        trig = dash.ctx.triggered_id
        if trig == 'ms-clear':
            return {} if _clicked() else no_update
        if trig == 'ms-search':
            f['search'] = search or ''
        elif trig == 'ms-toggles':
            f['hide_excluded'] = 'hide_excluded' in (toggles or [])
            f['show_closed'] = 'show_closed' in (toggles or [])
        elif isinstance(trig, dict):
            if not _clicked():
                return no_update
            if trig['type'] == 'ms-chip':
                vals = list(f.get(trig['g']) or [])
                vals = [x for x in vals if x != trig['v']] if trig['v'] in vals else vals + [trig['v']]
                f[trig['g']] = vals
            else:
                f['rule'] = None if f.get('rule') == trig['r'] else trig['r']
        return f

    @app.callback(Output('ms-search', 'value'), Output('ms-toggles', 'value'), Input('ms-clear', 'n_clicks'),
                  prevent_initial_call=True)
    def clear_inputs(n):
        return ('', []) if n else (no_update, no_update)

    @app.callback(Output('ms-chips', 'children'), Output('ms-rulecards', 'children'), Output('ms-table', 'data'),
                  Output('ms-count', 'children'), Input('ms-filters', 'data'), Input('ms-version', 'data'))
    def render_records(f, _v):
        f = f or {}
        r, e = _filtered(f)
        base = views.filter_entities(r.entities, r.fired, {k: v for k, v in f.items() if k != 'rule'})
        total = len(views.filter_entities(r.entities, r.fired, {}))
        count = [html.Span(f'{len(e):,} records'),
                 html.Span(f' of {total:,} in the population' if len(e) != total else ' (everything in the population)',
                           style={'color': '#94A3B8', 'fontWeight': '500'})]
        return (views.chips(r.entities, r.fired, f), views.rule_cards(r, base, f.get('rule')), views.grid_rows(e),
                count)

    @app.callback(Output('ms-dl', 'data', allow_duplicate=True), Input('ms-export-grid', 'n_clicks'),
                  State('ms-filters', 'data'), prevent_initial_call=True)
    def export_grid(n, f):
        if not n:
            return no_update
        _, e = _filtered(f or {})
        data = table_bytes({'Suppliers': views.export_frame(e)})
        return dash.dcc.send_bytes(data, f'scope_suppliers_{datetime.now():%Y%m%d_%H%M}.xlsx')

    # ── Drawer ───────────────────────────────────────────────────────────────
    @app.callback(Output('ms-selected', 'data'), Output('ms-drawer', 'style'), Output('ms-backdrop', 'style'),
                  Output('ms-table', 'active_cell'), Output('ms-table', 'selected_cells'),
                  Input('ms-table', 'active_cell'), Input({'type': 'ms-open', 'k': ALL}, 'n_clicks'),
                  Input('ms-backdrop', 'n_clicks'), Input('ms-drawer-close', 'n_clicks'),
                  prevent_initial_call=True)
    def open_drawer(cell, _o, _b, _c):
        trig = dash.ctx.triggered_id
        closed = ({'transform': 'translateX(105%)'}, {'display': 'none'})
        opened = ({'transform': 'translateX(0)'}, {'display': 'block'})
        if trig == 'ms-table':
            if not cell or not cell.get('row_id'):
                return no_update, no_update, no_update, no_update, no_update
            return (cell['row_id'], *opened, None, [])
        if isinstance(trig, dict) and trig.get('type') == 'ms-open':
            if not _clicked():
                return no_update, no_update, no_update, no_update, no_update
            return (trig['k'], *opened, no_update, no_update)
        if trig in ('ms-backdrop', 'ms-drawer-close') and _clicked():
            return (None, *closed, no_update, no_update)
        return no_update, no_update, no_update, no_update, no_update

    @app.callback(Output('ms-drawer-body', 'children'), Input('ms-selected', 'data'), Input('ms-version', 'data'))
    def render_drawer(key, _v):
        if not key:
            return html.Div(html.Button(id='ms-drawer-close', n_clicks=0, style={'display': 'none'}))
        return views.drawer(engine(), key, OBJ)

    @app.callback(Output('ms-dec-choice', 'options'), Output('ms-dec-choice', 'value'),
                  Input('ms-dec-target', 'value'), State('ms-selected', 'data'), prevent_initial_call=True)
    def decision_choices(target, key):
        e = engine().result(OBJ).entity(key) if key else None
        return views.decision_options(target, e), None

    @app.callback(Output('ms-dec-msg', 'children'), Output('ms-version', 'data', allow_duplicate=True),
                  Input('ms-dec-save', 'n_clicks'),
                  State('ms-dec-target', 'value'), State('ms-dec-choice', 'value'), State('ms-dec-reason', 'value'),
                  State('ms-dec-steward', 'value'), State('ms-selected', 'data'), prevent_initial_call=True)
    def save_decision(n, target, choice, reason, steward, key):
        if not n:
            return no_update, no_update
        err = lambda t: (html.Span(t, style={'color': '#B91C1C'}), no_update)
        if not choice:
            return err('Choose a decision.')
        if not (reason or '').strip():
            return err('A reason is mandatory.')
        if not (steward or '').strip():
            return err('Give the steward name.')
        eng = engine()
        r = eng.result(OBJ)
        e = r.entity(key)
        ttype, tkey, related = target.split('|')
        if ttype == 'pair':
            tkey, related = min(tkey, related), max(tkey, related)
        rec = 'Needs review' if ttype == 'item' else (e['recommended'] if e is not None else '')
        eng.store.add_decisions([{'object': OBJ, 'target_type': ttype, 'target_key': tkey, 'related_key': related,
                                  'decision': choice, 'reason': reason, 'steward': steward, 'recommendation': rec,
                                  'record_label': e['apar_name'] if e is not None else ''}], source='Dashboard')
        eng.refresh(OBJ)
        return html.Span(f"Recorded: {DECISIONS[choice][0]}", style={'color': '#15803D'}), eng.version

    # ── Exports ──────────────────────────────────────────────────────────────
    @app.callback(Output('ms-dl', 'data', allow_duplicate=True), Input('ms-export-wb', 'n_clicks'),
                  State('ms-wb-house', 'value'), prevent_initial_call=True)
    def export_workbook(n, house):
        if not n:
            return no_update
        eng = engine()
        h = None if house == 'ALL' else house
        data = export_steward_workbook(eng.result(OBJ), eng.store.effective_decisions(OBJ), h)
        return dash.dcc.send_bytes(data, f"Supplier_scope_review_{house}_{datetime.now():%Y%m%d}.xlsx")

    @app.callback(Output('ms-dl', 'data', allow_duplicate=True), Input('ms-export-gov', 'n_clicks'),
                  prevent_initial_call=True)
    def export_gov(n):
        if not n:
            return no_update
        return dash.dcc.send_bytes(governance_summary(engine(), OBJ),
                                   f"Supplier_scope_governance_{datetime.now():%Y%m%d}.xlsx")

    # ── Upload ───────────────────────────────────────────────────────────────
    @app.callback(Output('ms-upload-result', 'children'), Output('ms-upload-preview', 'data'),
                  Output('ms-upload-content', 'data'),
                  Input('ms-upload', 'contents'), State('ms-upload', 'filename'), prevent_initial_call=True)
    def on_upload(contents, filename):
        if not contents:
            return no_update, no_update, no_update
        try:
            raw = base64.b64decode(contents.split(',', 1)[1])
            eng = engine()
            prev = preview_upload(raw, filename, eng.result(OBJ), eng.store.effective_decisions(OBJ))
        except Exception as exc:
            return html.Div(f'Could not read {filename}: {exc}', style={'color': '#B91C1C', 'marginTop': '10px'}), \
                None, None
        if not prev['total']:
            return html.Div('No decisions found in that workbook. Fill in the Decision, Reason and Steward columns.',
                            className='ms-muted', style={'marginTop': '10px'}), None, None
        return views.upload_preview(prev), prev, contents

    @app.callback(Output('ms-upload-result', 'children', allow_duplicate=True),
                  Output('ms-version', 'data', allow_duplicate=True), Output('ms-upload', 'contents'),
                  Input('ms-upload-apply', 'n_clicks'), Input('ms-upload-cancel', 'n_clicks'),
                  State('ms-upload-preview', 'data'), State('ms-upload-content', 'data'), prevent_initial_call=True)
    def apply_or_cancel(apply_n, cancel_n, prev, contents):
        if not _clicked():
            return no_update, no_update, no_update
        if dash.ctx.triggered_id == 'ms-upload-cancel' or not prev:
            return html.Div('Upload cancelled. Nothing was applied.', className='ms-muted',
                            style={'marginTop': '10px'}), no_update, None
        eng = engine()
        raw = base64.b64decode(contents.split(',', 1)[1]) if contents else None
        n = apply_upload(prev, eng.store, OBJ, raw)
        eng.refresh(OBJ)
        return html.Div([icon('lucide:check-circle-2', 16, '#15803D'),
                         html.Span(f" {n} decision(s) recorded from {prev['file']}. A backup was taken first.")],
                        style={'color': '#15803D', 'marginTop': '12px', 'fontWeight': '600'}), eng.version, None

    @app.callback(Output('ms-decisions-log', 'children'), Input('ms-version', 'data'))
    def render_log(_v):
        return views.decisions_log(engine(), OBJ)

    # ── Monthly snapshot ─────────────────────────────────────────────────────
    @app.callback(Output('ms-snap-panel', 'style'), Output('ms-snap-msg', 'children'),
                  Input('ms-snap-open', 'n_clicks'), Input('ms-snap-cancel', 'n_clicks'), prevent_initial_call=True)
    def snap_panel(_o, _c):
        if not _clicked():
            return no_update, no_update
        eng = engine()
        if dash.ctx.triggered_id == 'ms-snap-cancel':
            return {'display': 'none'}, ''
        existing = eng.store.month_snapshot(OBJ, eng.as_of.strftime('%Y-%m'))
        msg = html.Span(f"A position is already saved for this month ({existing['label']}). Saving again replaces it; "
                        'the old one is kept as superseded.', style={'color': '#B45309'}) if existing is not None else ''
        return {}, msg

    @app.callback(Output('ms-snap-msg', 'children', allow_duplicate=True),
                  Output('ms-version', 'data', allow_duplicate=True), Input('ms-snap-save', 'n_clicks'),
                  State('ms-snap-label', 'value'), prevent_initial_call=True)
    def snap_save(n, label):
        if not n:
            return no_update, no_update
        eng = engine()
        eng.save_snapshot(OBJ, (label or '').strip() or f'{eng.as_of:%b %Y} position')
        eng.version += 1
        return html.Span('Saved. Next month the overview will show what changed since this position.',
                         style={'color': '#15803D', 'fontWeight': '600'}), eng.version

    # ── What-if ──────────────────────────────────────────────────────────────
    @app.callback(Output('ms-wi-result', 'children'), Input('ms-wi-run', 'n_clicks'),
                  State({'type': 'ms-wi', 'p': ALL}, 'value'), State({'type': 'ms-wi', 'p': ALL}, 'id'),
                  State('ms-wi-xh', 'value'), prevent_initial_call=True)
    def what_if(n, values, ids, xh):
        if not n:
            return no_update
        eng = engine()
        current = eng.result(OBJ).params
        overrides = {i['p']: v for i, v in zip(ids, values) if v != current[i['p']]}
        if bool(xh) != current['cross_house_as_duplicate']:
            overrides['cross_house_as_duplicate'] = bool(xh)
        if not overrides:
            return html.Div('Every slider is at its current value. Move one to see the impact.', className='ms-empty')
        _, changed = eng.what_if(OBJ, overrides)
        return views.what_if_result(changed, overrides)
