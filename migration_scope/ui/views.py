"""
Screens for the Migration Scope module.

  Overview   funnel per House, in-scope headline, change since last snapshot,
             things needing attention, monthly trend
  Records    rule cards, filter chips, one record grid, export
  Drawer     everything about one supplier, and recording a decision
  Decisions  upload steward workbooks (with preview), export, audit log, snapshots
  Rules      every rule and its parameters, with the ruleset version and change log
"""
import json

import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html, dash_table

from migration_scope import config
from migration_scope.core.model import (
    KEEP, FIX, MONITOR, CLOSE, HOLD_NONCOMMERCIAL, HOLD_POLICY, OUT_OF_SCOPE, NOT_IN_EXTRACT, IN_SCOPE, HELD,
    EXCLUDED, AWAITING, DECIDED, OVERRIDDEN, NO_DECISION_NEEDED, DECISIONS, ISSUE_TYPES,
)
from migration_scope.objects import OBJECTS
from migration_scope.ui.theme import (
    INK, MUTED, FAINT, LINE, BG, BRAND, HOUSE, HOUSE_NAME, CLASS_COLOUR, CLASS_BG, CLASS_HELP, STATUS_COLOUR,
    DIM_COLOUR, CARD, icon, pill, class_pill, house_pill, card, section_title, delta, fmt_money, fmt_date,
)

VIEWS = [('overview', 'Overview', 'lucide:filter'), ('records', 'Records', 'lucide:table-2'),
         ('decisions', 'Decisions & uploads', 'lucide:clipboard-check'), ('rules', 'Rules', 'lucide:book-open')]

CHIP_GROUPS = [
    ('cls', 'Classification', [KEEP, FIX, MONITOR, CLOSE, 'Held', OUT_OF_SCOPE]),
    ('issue', 'Issues', ISSUE_TYPES + ['Cross-House']),
    ('status', 'Decision', [AWAITING, DECIDED, OVERRIDDEN, NO_DECISION_NEEDED]),
    ('house', 'House', ['HOC', 'HOL']),
]
CHIP_LABEL = {'HOC': 'HoC', 'HOL': 'HoL', 'Held': 'Held for policy', OUT_OF_SCOPE: 'Closed in Unit4'}


# ═════════════════════════════════════════════════════════════════════════════
# FILTERING (shared by the grid, chip counts and exports)
# ═════════════════════════════════════════════════════════════════════════════

def filter_entities(ent, fired, f, skip=None):
    f = f or {}
    e = ent
    if not f.get('cls') and not f.get('show_closed'):
        e = e[~e['classification'].isin([OUT_OF_SCOPE, NOT_IN_EXTRACT])]
    if f.get('hide_excluded'):
        e = e[~e['classification'].isin(EXCLUDED)]
    if skip != 'cls' and f.get('cls'):
        want = set()
        for c in f['cls']:
            want |= set(HELD) if c == 'Held' else ({OUT_OF_SCOPE, NOT_IN_EXTRACT} if c == OUT_OF_SCOPE else {c})
        e = e[e['classification'].isin(want)]
    if skip != 'issue' and f.get('issue'):
        m = pd.Series(False, index=e.index)
        for t in f['issue']:
            col = {'Duplicate': 'has_duplicate', 'Cross-House': None}.get(t, f'has_{t.lower()}')
            m |= (e['cross_house'] != '') if t == 'Cross-House' else e[col]
        e = e[m]
    if skip != 'status' and f.get('status'):
        e = e[e['decision_status'].isin(f['status'])]
    if skip != 'house' and f.get('house'):
        e = e[e['house'].isin(f['house'])]
    if skip != 'rule' and f.get('rule'):
        e = e[e['entity_key'].isin(fired[fired['rule_id'] == f['rule']]['entity_key'])]
    if f.get('search'):
        q = f['search'].strip().lower()
        hay = (e['apar_name'].astype(str) + ' ' + e['entity_key'] + ' ' + e['vat_reg_no'].astype(str) + ' '
               + e['dup_group'].astype(str)).str.lower()
        e = e[hay.str.contains(q, regex=False)]
    return e


def _chip_match(e, group, value):
    if group == 'cls':
        if value == 'Held':
            return e['classification'].isin(HELD).sum()
        if value == OUT_OF_SCOPE:
            return e['classification'].isin([OUT_OF_SCOPE, NOT_IN_EXTRACT]).sum()
        return (e['classification'] == value).sum()
    if group == 'issue':
        if value == 'Cross-House':
            return (e['cross_house'] != '').sum()
        return e['has_duplicate' if value == 'Duplicate' else f'has_{value.lower()}'].sum()
    if group == 'status':
        return (e['decision_status'] == value).sum()
    return (e['house'] == value).sum()


# ═════════════════════════════════════════════════════════════════════════════
# SHELL
# ═════════════════════════════════════════════════════════════════════════════

def layout(engine, obj='suppliers'):
    r = engine.result(obj)
    objects = []
    for key, spec in OBJECTS.items():
        on = key == obj
        objects.append(html.Div(className='ms-obj' + (' ms-obj-on' if on else '') + ('' if spec['available'] else ' ms-obj-off'),
                                title=spec.get('note', ''), children=[
            icon(spec['icon'], 15, 'white' if on else MUTED), spec['label'],
            None if spec['available'] else html.Span('Planned', className='ms-soon')]))
    return html.Div(className='ms-root', children=[
        dcc.Store(id='ms-view', data='overview'),
        dcc.Store(id='ms-filters', data={}),
        dcc.Store(id='ms-selected'),
        dcc.Store(id='ms-version', data=engine.version),
        dcc.Store(id='ms-upload-preview'),
        dcc.Store(id='ms-upload-content'),
        dcc.Download(id='ms-dl'),

        # Hero
        html.Div(className='ms-hero', children=[
            html.Div([
                html.Div('MIGRATION SCOPE ENGINE', className='ms-eyebrow'),
                html.H1('What are we migrating?', className='ms-title'),
                html.Div('The in-scope list is exactly what we would hand the SI if they asked for the extract '
                         'today. Data quality issues are shown on the records they affect.', className='ms-sub'),
                html.Div(objects, style={'display': 'flex', 'gap': '8px', 'marginTop': '18px'}),
            ]),
            html.Div(className='ms-hero-meta', children=[
                _meta('lucide:database', 'Data', r.source),
                _meta('lucide:calendar', 'As at', fmt_date(r.as_of)),
                _meta('lucide:git-branch', 'Ruleset', f'v{config.RULESET_VERSION}'),
                html.Div(style={'display': 'flex', 'gap': '8px', 'marginTop': '14px'}, children=[
                    html.Button([icon('lucide:camera', 15, 'white'), "Save this month's position"],
                                id='ms-snap-open', n_clicks=0, className='ms-btn ms-btn-primary'),
                ]),
            ]),
        ]),
        html.Div(id='ms-snap-panel', className='ms-snap-panel', style={'display': 'none'}, children=[
            html.Div([
                html.Div("Save this month's position", style={'fontWeight': '700', 'color': INK}),
                html.Div('Keeps a copy of every record\'s classification so next month shows real change. '
                         'Do this once a month, after loading the new extracts and uploading decisions.',
                         style={'fontSize': '12px', 'color': MUTED, 'marginTop': '2px'}),
            ]),
            dcc.Input(id='ms-snap-label', type='text', debounce=False, className='ms-input',
                      value=f"{r.as_of:%b %Y} position", style={'width': '260px'}),
            html.Button('Save', id='ms-snap-save', n_clicks=0, className='ms-btn ms-btn-primary'),
            html.Button('Cancel', id='ms-snap-cancel', n_clicks=0, className='ms-btn'),
            html.Div(id='ms-snap-msg', style={'fontSize': '12px'}),
        ]),

        # View switcher
        html.Div(className='ms-tabs', children=[
            html.Button([icon(ic, 15), label], id={'type': 'ms-tab', 'v': v}, n_clicks=0,
                        className='ms-tab' + (' ms-tab-on' if v == 'overview' else ''))
            for v, label, ic in VIEWS]),

        html.Div(id='ms-view-overview', className='ms-view'),
        html.Div(id='ms-view-records', className='ms-view', style={'display': 'none'},
                 children=records_shell()),
        html.Div(id='ms-view-decisions', className='ms-view', style={'display': 'none'},
                 children=decisions_shell(engine, obj)),
        html.Div(id='ms-view-rules', className='ms-view', style={'display': 'none'},
                 children=rules_shell(engine, obj)),

        # Record drawer
        html.Div(id='ms-backdrop', n_clicks=0, className='ms-backdrop', style={'display': 'none'}),
        html.Div(id='ms-drawer', className='ms-drawer', style={'transform': 'translateX(105%)'}, children=[
            html.Div(id='ms-drawer-body'),
        ]),
    ])


def _meta(ic, label, value):
    return html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '8px', 'fontSize': '12.5px'}, children=[
        icon(ic, 14, '#A7F3D0'), html.Span(label, style={'color': '#A7C4B8', 'width': '52px'}),
        html.Span(value, style={'color': 'white', 'fontWeight': '600'})])


# ═════════════════════════════════════════════════════════════════════════════
# OVERVIEW
# ═════════════════════════════════════════════════════════════════════════════

def overview(engine, obj='suppliers'):
    r = engine.result(obj)
    s = engine.summary(obj)
    snap = engine.store.latest_snapshot(obj)
    prev = json.loads(snap['summary_json']) if snap is not None else None

    def d(house, key):
        if prev is None:
            return None
        return s[house][key] - prev.get(house, {}).get(key, 0)

    e = r.entities
    alerts = e[(e['follow_through'].isin(['Not yet actioned in Unit4']) |
                e['follow_through'].str.startswith('Conflict') | (e['alert'] != ''))]
    kpis = html.Div(className='ms-kpis', children=[
        html.Div(className='ms-kpi ms-kpi-hero', children=[
            html.Div('IN SCOPE TODAY', className='ms-kpi-label', style={'color': '#A7F3D0'}),
            html.Div(f"{s['all']['in_scope']:,}", className='ms-kpi-value', style={'color': 'white'}),
            html.Div(f"suppliers would go to the SI · HoC {s['HOC']['in_scope']:,} · HoL {s['HOL']['in_scope']:,}",
                     style={'color': '#D1FAE5', 'fontSize': '12.5px'}),
            html.Div(delta(d('all', 'in_scope')), style={'marginTop': '6px', 'filter': 'brightness(1.6)'}),
        ]),
        _kpi('Awaiting a decision', s['awaiting'], 'records with something for a steward to decide',
             goto={'status': [AWAITING]}, colour=STATUS_COLOUR[AWAITING], ic='lucide:hourglass'),
        _kpi('Blocking issues', s['blocking'], 'on in-scope suppliers (stops payment or set-up)',
             goto={'cls': [FIX]}, colour=CLASS_COLOUR[FIX], ic='lucide:alert-triangle'),
        _kpi('Duplicate groups resolved', f"{s['dup_groups_resolved']} / {s['dup_groups']}",
             'preferred record confirmed by a steward', goto={'issue': ['Duplicate']},
             colour=CLASS_COLOUR[MONITOR], ic='lucide:copy'),
        _kpi('Needs chasing', len(alerts), 'decisions not actioned in Unit4, conflicts, wrong supplier used',
             goto={'chase': True}, colour='#B91C1C', ic='lucide:bell-ring'),
    ])

    houses = html.Div(className='ms-grid2', children=[_house_funnel(s[h], h, d) for h in ('HOC', 'HOL')])
    return html.Div([kpis, houses, html.Div(className='ms-grid2', children=[
        _changes_card(engine, obj), _attention_card(alerts)]), _trend_card(engine, obj)])


def _goto_id(f):
    return {'type': 'ms-goto', 'f': json.dumps(f, sort_keys=True)}


def _kpi(label, value, sub, goto, colour, ic):
    return html.Button(id=_goto_id(goto), n_clicks=0, className='ms-kpi ms-click', children=[
        html.Div([icon(ic, 15, colour), html.Span(label.upper(), className='ms-kpi-label')],
                 style={'display': 'flex', 'alignItems': 'center', 'gap': '6px'}),
        html.Div(f'{value:,}' if isinstance(value, int) else value, className='ms-kpi-value',
                 style={'color': colour}),
        html.Div(sub, style={'color': MUTED, 'fontSize': '12px', 'lineHeight': '1.35'}),
    ])


def _house_funnel(f, h, d):
    colour = HOUSE[h]
    top = max(f['unit4'], 1)

    def stage(label, n, sub, goto, shade, indent=0):
        return html.Button(id=_goto_id(goto), n_clicks=0, className='ms-stage ms-click', children=[
            html.Div(style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'baseline'}, children=[
                html.Span(label, style={'fontWeight': '600', 'color': INK, 'fontSize': '13px'}),
                html.Span(f'{n:,}', style={'fontWeight': '800', 'color': INK, 'fontSize': '16px'}),
            ]),
            html.Div(className='ms-bar', children=html.Div(style={
                'width': f'{max(n / top * 100, 1.5):.1f}%', 'background': shade, 'marginLeft': f'{indent}%'})),
            html.Div(sub, style={'fontSize': '11.5px', 'color': MUTED}),
        ])

    def drop(label, n, goto):
        return html.Button(id=_goto_id(goto), n_clicks=0, className='ms-drop ms-click', children=[
            icon('lucide:corner-down-right', 13, FAINT), html.Span(label), html.Span(f'{n:,}', className='ms-drop-n')])

    classes = []
    for c in (KEEP, FIX, MONITOR, CLOSE):
        classes.append(html.Button(id=_goto_id({'cls': [c], 'house': [h]}), n_clicks=0, className='ms-class ms-click',
                                   style={'borderTop': f'3px solid {CLASS_COLOUR[c]}'}, children=[
            html.Div(c, style={'fontSize': '12px', 'fontWeight': '700', 'color': CLASS_COLOUR[c]}),
            html.Div(f'{f[c]:,}', style={'fontSize': '22px', 'fontWeight': '800', 'color': INK}),
            html.Div(CLASS_HELP[c], style={'fontSize': '11px', 'color': MUTED}),
            html.Div(delta(d(h, c), good_when_up=c == KEEP), style={'marginTop': '4px'}),
        ]))

    return card(style={'borderTop': f'4px solid {colour}'}, children=[
        section_title(HOUSE_NAME[h], 'From everything in Unit4 to what migrates', right=house_pill(h)),
        stage('In Unit4', f['unit4'], 'every supplier record in the in-scope clients', {'house': [h], 'show_closed': True},
              '#CBD5E1'),
        drop('Closed or terminated in Unit4: never in scope', f['closed_terminated'], {'house': [h], 'cls': [OUT_OF_SCOPE]}),
        drop('Legacy exclusions (89 / 99 IDs, SZSINGLES)', f['legacy'], {'house': [h], 'rule': 'MS-POP-03', 'show_closed': True})
        if f['legacy'] else None,
        stage('Population', f['population'], 'status N (active) or P (parked)', {'house': [h]}, '#94A3B8'),
        drop('Held for policy: non-commercial (Members, staff, witnesses)', f['noncommercial'],
             {'house': [h], 'cls': ['Held']}),
        drop('Held for policy: card accounts', f['policy'], {'house': [h], 'cls': ['Held']}) if f['policy'] else None,
        stage('Classified', f['classified'], 'commercial suppliers run through the rules', {'house': [h]}, '#64748B'),
        drop('Recommended Close (dormant, or inactive duplicate)', f[CLOSE], {'house': [h], 'cls': [CLOSE]}),
        stage('In scope', f['in_scope'], 'Keep + Fix + Monitor: what the SI would receive today',
              {'house': [h], 'cls': [KEEP, FIX, MONITOR]}, colour),
        html.Div(classes, className='ms-classes'),
    ])


def _changes_card(engine, obj):
    snap, ch = engine.changes_since_snapshot(obj)
    if snap is None:
        body = html.Div(className='ms-empty', children=[
            icon('lucide:camera', 28, FAINT),
            html.Div('No monthly position saved yet', style={'fontWeight': '600', 'color': INK}),
            html.Div("Press \"Save this month's position\" once a month. From then on this card shows every record "
                     'whose classification changed, and why.', style={'fontSize': '12.5px'})])
    elif ch.empty:
        body = html.Div(f"No classification has changed since {snap['label']}.", className='ms-empty')
    else:
        causes = ch['cause'].value_counts()
        rows = [html.Button(id={'type': 'ms-open', 'k': rr['entity_key']}, n_clicks=0, className='ms-row ms-click',
                            children=[house_pill(rr['house']), html.Span(rr['name'] or rr['entity_key'],
                                                                         className='ms-row-name'),
                                      class_pill(rr['before']), icon('lucide:arrow-right', 13, FAINT),
                                      class_pill(rr['now']), html.Span(rr['cause'], className='ms-row-meta')])
                for _, rr in ch.head(12).iterrows()]
        body = html.Div([
            html.Div([pill(f'{c}: {n}', INK, '#F1F5F9') for c, n in causes.items()],
                     style={'display': 'flex', 'gap': '6px', 'flexWrap': 'wrap', 'marginBottom': '10px'}),
            html.Div(rows),
            html.Div(f'+ {len(ch) - 12} more (see the governance summary export)', className='ms-more')
            if len(ch) > 12 else None])
    sub = f"Compared with {snap['label']} ({snap['taken_at'][:10]})" if snap is not None else 'Saved monthly positions'
    return card([section_title('Changed since last month', sub, ic='lucide:history'), body])


def _attention_card(alerts):
    if alerts.empty:
        body = html.Div(className='ms-empty', children=[
            icon('lucide:check-circle-2', 28, '#16A34A'),
            html.Div('Nothing to chase', style={'fontWeight': '600', 'color': INK}),
            html.Div('Closures not yet done in Unit4, conflicts with steward decisions, and duplicates used after '
                     'the preferred record was confirmed will appear here.', style={'fontSize': '12.5px'})])
    else:
        body = html.Div([html.Button(id={'type': 'ms-open', 'k': a['entity_key']}, n_clicks=0,
                                     className='ms-row ms-click', children=[
            house_pill(a['house']), html.Span(a['apar_name'], className='ms-row-name'),
            html.Span(a['alert'] or a['follow_through'], className='ms-row-meta',
                      style={'color': '#B91C1C' if (a['alert'] or 'Conflict' in a['follow_through']) else '#B45309'})])
            for _, a in alerts.head(12).iterrows()])
    return card([section_title('Needs chasing', 'Follow-through of steward decisions in Unit4',
                               ic='lucide:bell-ring'), body])


def _trend_card(engine, obj):
    t = engine.trend(obj)
    if t.empty or t['month'].nunique() < 2:
        saved = '' if t.empty else f" One position saved so far ({t['label'].iloc[0]})."
        content = html.Div(f'The trend line appears once two monthly positions are saved.{saved}', className='ms-empty')
    else:
        fig = go.Figure()
        for h in ('HOC', 'HOL'):
            sub = t[t['house'] == h]
            fig.add_trace(go.Scatter(x=sub['label'], y=sub['in_scope'], name=f"{'HoC' if h == 'HOC' else 'HoL'} in scope",
                                     mode='lines+markers', line=dict(color=HOUSE[h], width=3)))
            fig.add_trace(go.Bar(x=sub['label'], y=sub['Fix'], name=f"{'HoC' if h == 'HOC' else 'HoL'} Fix",
                                 marker_color=CLASS_COLOUR[FIX], opacity=0.35 if h == 'HOL' else 0.7))
        fig.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor='rgba(0,0,0,0)',
                          plot_bgcolor='rgba(0,0,0,0)', font=dict(family='Poppins', size=11, color=MUTED),
                          legend=dict(orientation='h', y=-0.2), barmode='group')
        fig.update_yaxes(gridcolor='#F1F5F9')
        content = dcc.Graph(figure=fig, config={'displayModeBar': False})
    return card([section_title('Monthly trend', 'In-scope suppliers and records still to fix, from saved positions',
                               ic='lucide:trending-up'), content], style={'marginTop': '20px'})


# ═════════════════════════════════════════════════════════════════════════════
# RECORDS
# ═════════════════════════════════════════════════════════════════════════════

GRID_COLS = [
    ('house', 'House'), ('apar_id', 'Supplier ID'), ('apar_name', 'Name'), ('clients', 'Clients'),
    ('classification', 'Classification'), ('recommended', 'Recommended'), ('decision_status', 'Decision'),
    ('last_activity_txt', 'Last activity'), ('open_items', 'Open items'), ('open_balance_txt', 'Open £'),
    ('issues', 'Issues'), ('blocking', 'Blocking'), ('dup_group', 'Duplicate group'), ('xh', 'Cross-House'),
]


def records_shell():
    cond = [{'if': {'filter_query': f'{{classification}} = "{c}"', 'column_id': 'classification'},
             'color': CLASS_COLOUR[c], 'backgroundColor': CLASS_BG[c], 'fontWeight': '600'} for c in CLASS_COLOUR]
    cond += [{'if': {'filter_query': f'{{decision_status}} = "{s}"', 'column_id': 'decision_status'},
              'color': col, 'fontWeight': '600'} for s, col in STATUS_COLOUR.items()]
    cond += [{'if': {'filter_query': '{blocking} > 0', 'column_id': 'blocking'}, 'color': '#C2410C',
              'fontWeight': '700'},
             {'if': {'filter_query': '{recommended} != {classification}', 'column_id': 'recommended'},
              'textDecoration': 'line-through', 'color': FAINT}]
    return html.Div([
        html.Div(id='ms-rulecards', className='ms-rulecards'),
        card(style={'padding': '16px 18px', 'marginTop': '16px'}, children=[
            html.Div(className='ms-filterbar', children=[
                html.Div(className='ms-search', children=[
                    icon('lucide:search', 15, FAINT),
                    dcc.Input(id='ms-search', type='text', placeholder='Search name, supplier ID, VAT or group',
                              debounce=True, className='ms-search-input')]),
                dcc.Checklist(id='ms-toggles', className='ms-toggles', value=[],
                              options=[{'label': ' Hide excluded (Close)', 'value': 'hide_excluded'},
                                       {'label': ' Show closed in Unit4', 'value': 'show_closed'}]),
                html.Button([icon('lucide:x', 13), 'Clear filters'], id='ms-clear', n_clicks=0, className='ms-btn ms-btn-ghost'),
            ]),
            html.Div(id='ms-chips'),
        ]),
        card(style={'padding': '0', 'marginTop': '16px', 'overflow': 'hidden'}, children=[
            html.Div(className='ms-gridhead', children=[
                html.Div(id='ms-count', style={'fontWeight': '700', 'color': INK, 'fontSize': '14px'}),
                html.Div(style={'display': 'flex', 'gap': '8px'}, children=[
                    html.Button([icon('lucide:download', 14), 'Export these records'], id='ms-export-grid',
                                n_clicks=0, className='ms-btn')]),
            ]),
            dash_table.DataTable(
                id='ms-table', columns=[{'name': n, 'id': c} for c, n in GRID_COLS], data=[],
                page_size=25, sort_action='native', page_action='native', cell_selectable=True,
                style_as_list_view=True,
                style_table={'overflowX': 'auto'},
                style_header={'backgroundColor': BG, 'color': MUTED, 'fontWeight': '700', 'fontSize': '11px',
                              'textTransform': 'uppercase', 'letterSpacing': '0.04em',
                              'borderBottom': f'1px solid {LINE}', 'padding': '10px 12px'},
                style_cell={'fontFamily': 'Poppins, sans-serif', 'fontSize': '12.5px', 'color': INK,
                            'padding': '10px 12px', 'textAlign': 'left', 'border': 'none',
                            'borderBottom': '1px solid #F1F5F9', 'cursor': 'pointer', 'whiteSpace': 'nowrap',
                            'maxWidth': '280px', 'overflow': 'hidden', 'textOverflow': 'ellipsis'},
                style_cell_conditional=[{'if': {'column_id': 'apar_name'}, 'fontWeight': '600', 'minWidth': '220px'}],
                style_data_conditional=cond,
            ),
        ]),
    ])


def rule_cards(r, ent_view, active_rule):
    counts = r.fired[r.fired['entity_key'].isin(ent_view['entity_key'])]['rule_id'].value_counts()
    cards = []
    for rule in r.rules:
        n = int(counts.get(rule.id, 0))
        on = active_rule == rule.id
        cards.append(html.Button(id={'type': 'ms-rulecard', 'r': rule.id}, n_clicks=0,
                                 className='ms-rulecard ms-click' + (' ms-rulecard-on' if on else ''), children=[
            html.Div(style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center'}, children=[
                html.Span(rule.id, className='ms-ruleid'),
                html.Span(rule.layer, style={'fontSize': '10px', 'color': FAINT, 'fontWeight': '600'})]),
            html.Div(rule.name, style={'fontWeight': '700', 'color': INK, 'fontSize': '13px', 'marginTop': '6px'}),
            html.Div(rule.text(r.params), className='ms-ruletext'),
            html.Div(style={'display': 'flex', 'alignItems': 'baseline', 'gap': '6px', 'marginTop': 'auto'}, children=[
                html.Span(f'{n:,}', style={'fontSize': '20px', 'fontWeight': '800',
                                           'color': CLASS_COLOUR.get(rule.outcome, BRAND) if n else FAINT}),
                html.Span('records', style={'fontSize': '11px', 'color': MUTED}),
                class_pill(rule.outcome, '10px') if rule.outcome else None]),
        ]))
    return cards


def chips(ent_all, fired, f):
    out = []
    for g, title, values in CHIP_GROUPS:
        base = filter_entities(ent_all, fired, f, skip=g)
        items = []
        for v in values:
            on = v in (f.get(g) or [])
            n = int(_chip_match(base, g, v))
            colour = CLASS_COLOUR.get(v) or STATUS_COLOUR.get(v) or DIM_COLOUR.get(v) or HOUSE.get(v) or \
                (CLASS_COLOUR[HOLD_NONCOMMERCIAL] if v == 'Held' else '#0F766E')
            items.append(html.Button(id={'type': 'ms-chip', 'g': g, 'v': v}, n_clicks=0,
                                     className='ms-chip' + (' ms-chip-on' if on else ''),
                                     style={'--chip': colour}, children=[
                html.Span(className='ms-dot', style={'background': colour}),
                CHIP_LABEL.get(v, v), html.Span(f'{n:,}', className='ms-chip-n')]))
        out.append(html.Div(className='ms-chiprow', children=[html.Span(title, className='ms-chiptitle')] + items))
    if f.get('rule'):
        out.append(html.Div(className='ms-chiprow', children=[
            html.Span('Rule', className='ms-chiptitle'),
            html.Button([f"{f['rule']} ", icon('lucide:x', 12)], id={'type': 'ms-rulecard', 'r': f['rule']},
                        n_clicks=0, className='ms-chip ms-chip-on', style={'--chip': BRAND})]))
    if f.get('chase'):
        out.append(html.Div(className='ms-chiprow', children=[
            html.Span('Showing', className='ms-chiptitle'),
            html.Span('Needs chasing (follow-through and alerts)', className='ms-chip ms-chip-on',
                      style={'--chip': '#B91C1C'})]))
    return out


_ORDER = {FIX: 0, MONITOR: 1, CLOSE: 2, KEEP: 3, HOLD_POLICY: 4, HOLD_NONCOMMERCIAL: 5, OUT_OF_SCOPE: 6,
          NOT_IN_EXTRACT: 7}


def grid_rows(e):
    # Work first: what needs fixing or deciding, then what migrates as is
    df = e.assign(_o=e['classification'].map(_ORDER), _a=(e['decision_status'] != AWAITING))           .sort_values(['_o', '_a', 'house', 'apar_name'])
    df['id'] = df['entity_key']
    df['last_activity_txt'] = df['last_activity'].map(lambda d: d.strftime('%Y-%m-%d') if pd.notna(d) else '')
    df['open_balance_txt'] = df['open_balance'].map(lambda v: f'{v:,.0f}' if v else '')
    df['xh'] = df['cross_house'].map(lambda x: 'Yes' if x else '')
    return df[['id'] + [c for c, _ in GRID_COLS]].fillna('').to_dict('records')


def export_frame(e):
    cols = {'entity_key': 'Record key', 'house': 'House', 'apar_id': 'Supplier ID', 'apar_name': 'Name',
            'clients': 'Clients', 'apar_gr_id': 'Group', 'client_statuses': 'Unit4 status',
            'category': 'Category', 'category_detail': 'Category detail', 'classification': 'Classification',
            'recommended': 'Recommended', 'recommended_rule': 'Rule', 'decision_status': 'Decision status',
            'decision': 'Decision', 'decision_by': 'Decided by', 'decision_reason': 'Reason', 'pending': 'Outstanding',
            'last_activity': 'Last activity', 'last_invoice_ref': 'Last invoice', 'last_po_ref': 'Last PO',
            'open_items': 'Open items', 'open_balance': 'Open balance', 'open_pos': 'Open POs',
            'stuck_items': 'Stuck items', 'issues': 'Issues', 'blocking': 'Blocking issues',
            'dup_group': 'Duplicate group', 'preferred': 'Preferred', 'match_reasons': 'Why matched',
            'cross_house': 'Cross-House matches', 'follow_through': 'Follow-through', 'alert': 'Alert'}
    out = e[[c for c in cols if c in e]].rename(columns=cols)
    if 'Last activity' in out:
        out['Last activity'] = pd.to_datetime(out['Last activity']).dt.date
    if 'Decision' in out:
        out['Decision'] = out['Decision'].map(lambda c: DECISIONS[c][0] if c in DECISIONS else '')
    return out


# ═════════════════════════════════════════════════════════════════════════════
# DRAWER
# ═════════════════════════════════════════════════════════════════════════════

def drawer(engine, key, obj='suppliers'):
    r = engine.result(obj)
    e = r.entity(key)
    if e is None:
        return html.Div('Record not found.', style={'padding': '24px'})
    trail = r.trail(e) if e['classification'] != NOT_IN_EXTRACT else []
    head = html.Div(className='ms-dhead', children=[
        html.Div([
            html.Div([house_pill(e['house']), html.Span(e['entity_key'], className='ms-key'),
                      html.Span(f"Clients {e['clients']}" if e['clients'] else '', className='ms-key')],
                     style={'display': 'flex', 'gap': '8px', 'alignItems': 'center'}),
            html.H2(e['apar_name'] if isinstance(e['apar_name'], str) else '(no name)', className='ms-dtitle'),
            html.Div(style={'display': 'flex', 'gap': '8px', 'flexWrap': 'wrap', 'alignItems': 'center'}, children=[
                class_pill(e['classification'], '12px'),
                html.Span(['Rules said ', class_pill(e['recommended'], '11px')], style={'fontSize': '11px', 'color': MUTED})
                if e['recommended'] != e['classification'] else None,
                pill(e['decision_status'], STATUS_COLOUR.get(e['decision_status'], MUTED)),
                pill(f"{e['category_detail'] or e['category']}", MUTED, '#F1F5F9') if e['category'] else None,
                pill('Individual', '#0369A1') if e['individual'] else None,
            ]),
        ]),
        html.Button(icon('lucide:x', 18, MUTED), id='ms-drawer-close', n_clicks=0, className='ms-iconbtn'),
    ])
    blocks = [head]
    if e['pending']:
        blocks.append(_callout('lucide:hourglass', 'Waiting on a steward', e['pending'], '#B45309', '#FFFBEB'))
    if e['alert'] or e['follow_through']:
        bad = e['alert'] or 'Conflict' in e['follow_through'] or 'Not yet' in e['follow_through']
        blocks.append(_callout('lucide:bell-ring', 'Follow-through', e['alert'] or e['follow_through'],
                               '#B91C1C' if bad else '#15803D', '#FEF2F2' if bad else '#F0FDF4'))

    # Why
    steps = []
    for st in trail:
        ok = st['result']
        ic, col = {'pass': ('lucide:check-circle-2', '#16A34A'), 'fail': ('lucide:alert-circle', '#C2410C'),
                   'stop': ('lucide:circle-slash', MUTED)}[ok]
        steps.append(html.Div(className='ms-step', children=[
            icon(ic, 17, col), html.Div([html.Div(st['text'], style={'color': INK, 'fontSize': '13px'}),
                                         html.Span(st['rule'], className='ms-ruleid')])]))
    if e['decision']:
        steps.append(html.Div(className='ms-step ms-step-dec', children=[
            icon('lucide:user-check', 17, '#7C3AED'), html.Div([
                html.Div(f"Steward decision: {DECISIONS[e['decision']][0]}. \"{e['decision_reason']}\"",
                         style={'color': INK, 'fontSize': '13px', 'fontWeight': '600'}),
                html.Span(f"{e['decision_by']} · {str(e['decision_at'])[:10]}"
                          + (' · overrides the rules' if e['overridden'] else ''), className='ms-ruleid')])]))
    blocks.append(_section('Why it is classified this way', 'lucide:route', steps or html.Div('—')))

    blocks.append(_activity(r, e))
    blocks.append(_issues_block(r, key))
    blocks.append(_dups_block(r, e))
    blocks.append(_fields_block(r, e))
    blocks.append(_history_block(engine, r, e, obj))
    blocks.append(_decision_form(r, e))
    return html.Div(blocks)


def _callout(ic, title, text, colour, bg):
    return html.Div(className='ms-callout', style={'background': bg, 'borderColor': f'{colour}40'}, children=[
        icon(ic, 16, colour), html.Div([html.Div(title, style={'fontWeight': '700', 'color': colour,
                                                               'fontSize': '12.5px'}),
                                        html.Div(text, style={'fontSize': '12.5px', 'color': INK})])])


def _section(title, ic, body, right=None):
    return html.Div(className='ms-dsec', children=[
        html.Div([icon(ic, 15, BRAND), html.Span(title), html.Span(right, style={'marginLeft': 'auto'})],
                 className='ms-dsec-title'), html.Div(body) if isinstance(body, list) else body])


def _tile(label, value, sub=''):
    return html.Div(className='ms-tile', children=[html.Div(label, className='ms-tile-label'),
                                                   html.Div(value, className='ms-tile-value'),
                                                   html.Div(sub, className='ms-tile-sub')])


def _mini_table(df, cols, highlight=None):
    head = html.Tr([html.Th(n) for _, n in cols])
    rows = []
    for _, rw in df.iterrows():
        cls = 'ms-hl' if highlight and highlight(rw) else ''
        rows.append(html.Tr([html.Td(rw[c] if not callable(c) else c(rw)) for c, _ in cols], className=cls))
    return html.Table([html.Thead(head), html.Tbody(rows)], className='ms-mini')


def _activity(r, e):
    items = r.items[r.items['entity_key'] == e['entity_key']].sort_values('trans_date')
    pos = r.open_pos[r.open_pos['entity_key'] == e['entity_key']] if not r.open_pos.empty else r.open_pos
    tiles = html.Div(className='ms-tiles', children=[
        _tile('Last invoice / credit', fmt_date(e.get('last_invoice_date')), e.get('last_invoice_ref', '') or ''),
        _tile('Last PO raised', fmt_date(e.get('last_po_date')) if e['house'] == 'HOC' else 'n/a (HoL)',
              f"PO {e['last_po_ref']}" if e.get('last_po_ref') else ''),
        _tile('Last movement of any kind', fmt_date(e.get('last_movement')), 'incl. payments and journals'),
        _tile('Open items', f"{int(e.get('open_items', 0)):,}", fmt_money(e.get('open_balance', 0))),
        _tile('Open POs', f"{int(e.get('open_pos', 0)):,}" if e['house'] == 'HOC' else 'n/a', ''),
    ])
    body = [tiles]
    if not items.empty:
        it = items.assign(date=items['trans_date'].map(fmt_date), amt=items['rest_amount'].map(fmt_money),
                          age=items['age_days'].map(lambda v: f'{int(v)} days' if pd.notna(v) else ''))
        body.append(html.Div('Open items', className='ms-subhead'))
        body.append(_mini_table(it, [('voucher_no', 'Voucher'), ('voucher_type', 'Type'), ('date', 'Date'),
                                     ('fy', 'Year'), ('age', 'Age'), ('amt', 'Outstanding'),
                                     ('item_status', 'Status')], highlight=lambda rw: rw['stuck']))
    if not pos.empty:
        p = pos.assign(date=pd.to_datetime(pos['order_date']).map(fmt_date))
        body.append(html.Div('Open purchase orders', className='ms-subhead'))
        body.append(_mini_table(p, [('order_id', 'PO'), ('client', 'Client'), ('date', 'Raised'), ('status', 'Status')]))
    return _section('Activity and open items', 'lucide:activity', html.Div(body))


def _issues_block(r, key):
    iss = r.issues[r.issues['entity_key'] == key]
    if iss.empty:
        return _section('Data quality issues', 'lucide:shield-check',
                        html.Div('No data quality issues.', className='ms-muted'))
    rows = []
    for _, i in iss.sort_values(['blocking', 'dimension'], ascending=[False, True]).iterrows():
        rows.append(html.Div(className='ms-issue', children=[
            pill(i['dimension'], DIM_COLOUR.get(i['dimension'], MUTED)),
            html.Div([html.Div(i['description'], style={'fontSize': '13px', 'color': INK}),
                      html.Span(f"{i['test_id']} · client {i['client']} · {i['source']}", className='ms-ruleid')],
                     style={'flex': '1'}),
            pill('Blocking', '#C2410C') if i['blocking'] else pill('Advisory', FAINT)]))
    return _section('Data quality issues', 'lucide:shield-alert', html.Div(rows),
                    right=html.Span(f"{len(iss)} issue(s)", className='ms-muted'))


def _dups_block(r, e):
    parts = []
    if e['dup_group']:
        g = r.entities[r.entities['dup_group'] == e['dup_group']].sort_values('preferred_rank')
        g = g.assign(name=g.apply(lambda x: html.Button(x['apar_name'], id={'type': 'ms-open', 'k': x['entity_key']},
                                                        n_clicks=0, className='ms-link'), axis=1),
                     pref=[('★ Preferred' if p else ('Level' if t else '')) for p, t in
                           zip(g['preferred'], g['preferred_tie'])],
                     act=g['last_activity'].map(fmt_date), openx=g['open_items'].astype(str) + ' / ' + g['open_pos'].astype(str))
        if e['group_confirmed']:
            status = 'Preferred record confirmed by a steward'
        elif g['preferred_tie'].any():
            status = 'Records are level on every rule, so a steward needs to choose the preferred record'
        else:
            status = 'Preferred record proposed by the rules: awaiting steward confirmation'
        parts += [html.Div([pill(e['dup_group'], '#9333EA'), html.Span(status, className='ms-muted')],
                           style={'display': 'flex', 'gap': '8px', 'alignItems': 'center', 'marginBottom': '8px'}),
                  _mini_table(g, [('pref', ''), ('entity_key', 'Record'), ('name', 'Name'),
                                  ('classification', 'Classification'), ('blocking', 'Blocking'),
                                  ('openx', 'Open items / POs'), ('act', 'Last activity'),
                                  ('completeness', 'Complete (of 8)')], highlight=lambda rw: rw['preferred']),
                  html.Div(e['match_reasons'], className='ms-muted', style={'marginTop': '6px'})]
    p = r.possible[(r.possible['a'] == e['entity_key']) | (r.possible['b'] == e['entity_key'])]
    if not p.empty:
        names = r.entities.set_index('entity_key')['apar_name']
        parts.append(html.Div('Possible duplicates (similar names)', className='ms-subhead'))
        for _, pr in p.iterrows():
            other = pr['b'] if pr['a'] == e['entity_key'] else pr['a']
            parts.append(html.Div(className='ms-issue', children=[
                pill(f"{pr['score']}% similar", '#9333EA'),
                html.Button(f"{names.get(other, other)} ({other})", id={'type': 'ms-open', 'k': other}, n_clicks=0,
                            className='ms-link')]))
    if e['cross_house']:
        parts.append(html.Div('Cross-House matches (tracked, not treated as duplicates)', className='ms-subhead'))
        for m in e['cross_house'].split('; '):
            other = m.split(' as ')[-1]
            parts.append(html.Div(className='ms-issue', children=[
                pill('Cross-House', '#0F766E'), html.Span(m.rsplit(' as ', 1)[0], style={'fontSize': '13px'}),
                html.Button(other, id={'type': 'ms-open', 'k': other}, n_clicks=0, className='ms-link')]))
    if not parts:
        parts = [html.Div('No duplicates or cross-House matches found.', className='ms-muted')]
    return _section('Duplicates and matches', 'lucide:copy', html.Div(parts))


_FIELD_LABELS = [
    ('apar_name', 'Name', 'name_std'), ('apar_gr_id', 'Supplier group', None), ('status', 'Status', None),
    ('vat_reg_no', 'VAT number', 'vat_std'), ('comp_reg_no', 'Company number', 'compno_std'),
    ('pay_method', 'Payment method', None), ('terms_id', 'Payment terms', None), ('currency', 'Currency', None),
    ('clearing_code', 'Sort code', 'sort_std'), ('bank_account', 'Bank account', 'acct_std'),
    ('iban', 'IBAN', 'iban_std'), ('swift', 'SWIFT', None), ('address', 'Street', None), ('place', 'Town', None),
    ('zip_code', 'Postcode', 'postcode_std'), ('country_code', 'Country', None),
    ('last_update', 'Last updated', None), ('last_trans_date', 'Last movement', None),
]


def _fields_block(r, e):
    rows = r.raw[r.raw['entity_key'] == e['entity_key']].sort_values('client')
    if rows.empty:
        return _section('Fields', 'lucide:list', html.Div('Not in the latest extract.', className='ms-muted'))
    head = html.Tr([html.Th('Field')] + [html.Th(f"Raw · {c}") for c in rows['client']] + [html.Th('Standardised')])

    def show(v):
        if isinstance(v, pd.Timestamp):
            return fmt_date(v)
        return '' if pd.isna(v) else str(v)

    body = []
    for f, label, stdcol in _FIELD_LABELS:
        vals = [show(rw.get(f)) for _, rw in rows.iterrows()]
        differs = len(set(vals)) > 1
        body.append(html.Tr([html.Td(label, className='ms-fl')] + [html.Td(v or '—') for v in vals] +
                            [html.Td(show(rows.iloc[0].get(stdcol)) if stdcol else '', className='ms-std')],
                            className='ms-hl' if differs else ''))
    return _section('Fields: raw and standardised', 'lucide:list',
                    html.Div(html.Table([html.Thead(head), html.Tbody(body)], className='ms-mini ms-fields'),
                             style={'overflowX': 'auto'}))


def _history_block(engine, r, e, obj):
    d = engine.store.decisions(obj)
    keys = {e['entity_key']} | set(r.items[r.items['entity_key'] == e['entity_key']]['item_key'])
    if e['dup_group']:  # confirming the preferred record is recorded on another member of the group
        group = set(r.entities[r.entities['dup_group'] == e['dup_group']]['entity_key'])
        d = d[d['target_key'].isin(keys) | d['related_key'].isin(keys) |
              (d['target_key'].isin(group) & d['decision'].isin(['CONFIRM_PREFERRED', 'NOT_DUPLICATE']))]
    else:
        d = d[d['target_key'].isin(keys) | d['related_key'].isin(keys)]
    d = d.sort_values('id', ascending=False)
    if d.empty:
        body = html.Div('No decisions recorded yet.', className='ms-muted')
    else:
        body = html.Div([html.Div(className='ms-hist', children=[
            html.Div(className='ms-hist-dot'),
            html.Div([
                html.Div([html.B(DECISIONS[x['decision']][0]),
                          html.Span(f"  on {x['target_key']}" + (f" + {x['related_key']}" if x['related_key'] else ''),
                                    className='ms-muted')]),
                html.Div(f"\"{x['reason']}\"", style={'fontSize': '12.5px', 'color': INK}),
                html.Div(f"{x['steward']} · recorded {x['recorded_at'].replace('T', ' ')} by {x['recorded_by']} · "
                         f"{x['source']} · rules v{x['ruleset_version']} · recommendation then: {x['recommendation'] or '—'}",
                         className='ms-ruleid')])]) for _, x in d.iterrows()])
    return _section('Decision history', 'lucide:history', body,
                    right=html.Span('append-only: nothing is overwritten', className='ms-muted'))


def decision_targets(r, e):
    opts = [{'label': f"This supplier ({e['entity_key']})", 'value': f"record|{e['entity_key']}|"}]
    for _, it in r.items[(r.items['entity_key'] == e['entity_key']) & r.items['stuck']].iterrows():
        opts.append({'label': f"Open item {it['voucher_no']} ({fmt_date(it['trans_date'])}, {fmt_money(it['rest_amount'])})",
                     'value': f"item|{it['item_key']}|"})
    p = r.possible[(r.possible['a'] == e['entity_key']) | (r.possible['b'] == e['entity_key'])]
    for _, pr in p.iterrows():
        other = pr['b'] if pr['a'] == e['entity_key'] else pr['a']
        opts.append({'label': f'Possible duplicate with {other}', 'value': f"pair|{e['entity_key']}|{other}"})
    return opts


def decision_options(target_value, e=None):
    ttype = (target_value or 'record||').split('|')[0]
    codes = {'record': ['AGREE', 'KEEP', 'CLOSE', 'WILL_FIX', 'ACCEPT_AS_IS', 'CONFIRM_PREFERRED', 'NOT_DUPLICATE'],
             'item': ['MIGRATE', 'DONT_MIGRATE'], 'pair': ['SAME_SUPPLIER', 'DIFFERENT_SUPPLIER']}[ttype]
    if e is not None and ttype == 'record':
        if not e['dup_group']:
            codes = [c for c in codes if c not in ('CONFIRM_PREFERRED', 'NOT_DUPLICATE')]
        if e['recommended'] != FIX and e['classification'] != FIX:
            codes = [c for c in codes if c not in ('WILL_FIX', 'ACCEPT_AS_IS')]
    return [{'label': DECISIONS[c][0], 'value': c} for c in codes]


def _decision_form(r, e):
    if e['classification'] == NOT_IN_EXTRACT:
        return None
    targets = decision_targets(r, e)
    return html.Div(className='ms-dsec ms-form', children=[
        html.Div([icon('lucide:pen-line', 15, BRAND), html.Span('Record a decision')], className='ms-dsec-title'),
        html.Div('Usually decisions come back in the steward workbook. Use this for a quick one-off. A reason is '
                 'mandatory; the decision is added to the history and overrides the rules.',
                 className='ms-muted', style={'marginBottom': '10px'}),
        html.Label('Applies to', className='ms-lbl'),
        dcc.Dropdown(id='ms-dec-target', options=targets, value=targets[0]['value'], clearable=False),
        html.Label('Decision', className='ms-lbl'),
        dcc.Dropdown(id='ms-dec-choice', options=decision_options(targets[0]['value'], e), placeholder='Choose…'),
        html.Label('Reason (mandatory)', className='ms-lbl'),
        dcc.Textarea(id='ms-dec-reason', className='ms-input', style={'width': '100%', 'height': '70px'}),
        html.Label('Steward', className='ms-lbl'),
        dcc.Input(id='ms-dec-steward', type='text', className='ms-input', style={'width': '100%'},
                  placeholder='Name of the steward who made the decision'),
        html.Div(style={'display': 'flex', 'gap': '10px', 'alignItems': 'center', 'marginTop': '12px'}, children=[
            html.Button([icon('lucide:check', 15, 'white'), 'Record decision'], id='ms-dec-save', n_clicks=0,
                        className='ms-btn ms-btn-primary'),
            html.Div(id='ms-dec-msg', style={'fontSize': '12.5px'})]),
    ])


# ═════════════════════════════════════════════════════════════════════════════
# DECISIONS & UPLOADS
# ═════════════════════════════════════════════════════════════════════════════

def decisions_shell(engine, obj):
    return html.Div([
        html.Div(className='ms-grid2', children=[
            card([
                section_title('1 · Send to stewards', 'One workbook per House. Each tab is one kind of decision, '
                              'with the recommendation and why.', ic='lucide:file-down'),
                html.Div(style={'display': 'flex', 'gap': '10px', 'alignItems': 'center', 'marginTop': '6px'}, children=[
                    dcc.Dropdown(id='ms-wb-house', options=[{'label': 'House of Commons', 'value': 'HOC'},
                                                            {'label': 'House of Lords', 'value': 'HOL'},
                                                            {'label': 'Both Houses', 'value': 'ALL'}],
                                 value='HOC', clearable=False, style={'width': '200px'}),
                    html.Button([icon('lucide:download', 15, 'white'), 'Export steward workbook'], id='ms-export-wb',
                                n_clicks=0, className='ms-btn ms-btn-primary'),
                ]),
                html.Div('Tabs: Close - confirm · Duplicates · Possible duplicates · Fix · Stuck items · Held for '
                         'policy · Cross-House (info)', className='ms-muted', style={'marginTop': '10px'}),
                html.Hr(style={'border': 'none', 'borderTop': f'1px solid {LINE}', 'margin': '16px 0'}),
                section_title('Governance summary', 'Funnel, issues, decisions, follow-through and change since last '
                              'month, for the board.', ic='lucide:presentation'),
                html.Button([icon('lucide:download', 15), 'Export governance summary'], id='ms-export-gov',
                            n_clicks=0, className='ms-btn', style={'marginTop': '6px'}),
            ]),
            card([
                section_title('2 · Upload marked-up workbook', 'Download it from SharePoint and drop it here. You '
                              'will see exactly what changes before anything is applied.', ic='lucide:file-up'),
                dcc.Upload(id='ms-upload', multiple=False, className='ms-drop-zone', children=html.Div([
                    icon('lucide:upload-cloud', 30, BRAND),
                    html.Div('Drop the steward workbook here, or click to choose', style={'fontWeight': '600'}),
                    html.Div('.xlsx exported from this page. Safe to upload the same file again.',
                             className='ms-muted')])),
                html.Div(id='ms-upload-result'),
            ]),
        ]),
        card(style={'marginTop': '20px'}, children=[html.Div(id='ms-decisions-log')]),
    ])


def upload_preview(prev):
    c = prev['counts']
    stat = lambda label, n, col: html.Div(className='ms-tile', children=[
        html.Div(label, className='ms-tile-label'), html.Div(f'{n:,}', className='ms-tile-value', style={'color': col})])
    rows = pd.DataFrame(prev['rows'])
    show = rows[rows['status'] != 'Already recorded'] if not rows.empty else rows
    table = None
    if not show.empty:
        show = show.assign(problem=show.get('problem', pd.Series('', index=show.index)).fillna(''))
        table = dash_table.DataTable(
            data=show[['sheet', 'row', 'target_key', 'related_key', 'decision_label', 'reason', 'steward', 'status',
                       'problem']].to_dict('records'),
            columns=[{'name': n, 'id': c} for c, n in [('sheet', 'Tab'), ('row', 'Row'), ('target_key', 'Record'),
                                                       ('related_key', 'With'), ('decision_label', 'Decision'),
                                                       ('reason', 'Reason'), ('steward', 'Steward'),
                                                       ('status', 'Result'), ('problem', 'Problem')]],
            page_size=10, style_as_list_view=True,
            style_cell={'fontFamily': 'Poppins', 'fontSize': '12px', 'textAlign': 'left', 'padding': '6px 8px',
                        'whiteSpace': 'normal', 'height': 'auto'},
            style_header={'fontWeight': '700', 'backgroundColor': BG},
            style_data_conditional=[{'if': {'filter_query': '{status} = "Rejected"'}, 'color': '#B91C1C'},
                                    {'if': {'filter_query': '{status} = "Changed decision"'}, 'color': '#7C3AED'}])
    can_apply = c.get('New decision', 0) + c.get('Changed decision', 0)
    return html.Div(className='ms-preview', children=[
        html.Div([icon('lucide:file-spreadsheet', 16, BRAND), html.B(prev['file']),
                  html.Span(f"{prev['total']} filled-in rows", className='ms-muted')],
                 style={'display': 'flex', 'gap': '8px', 'alignItems': 'center'}),
        html.Div(className='ms-tiles', style={'marginTop': '10px'}, children=[
            stat('Already recorded', c.get('Already recorded', 0), FAINT),
            stat('New decisions', c.get('New decision', 0), '#15803D'),
            stat('Changed decisions', c.get('Changed decision', 0), '#7C3AED'),
            stat('Rejected', c.get('Rejected', 0), '#B91C1C')]),
        table,
        html.Div(style={'display': 'flex', 'gap': '8px', 'marginTop': '12px', 'alignItems': 'center'}, children=[
            html.Button([icon('lucide:check', 15, 'white'), f'Apply {can_apply} decision(s)'], id='ms-upload-apply',
                        n_clicks=0, className='ms-btn ms-btn-primary', disabled=not can_apply),
            html.Button('Cancel', id='ms-upload-cancel', n_clicks=0, className='ms-btn'),
            html.Span('Rejected rows are not applied. Fix them in the workbook and upload again.', className='ms-muted')
            if c.get('Rejected') else None]),
    ])


def decisions_log(engine, obj):
    d = engine.store.decisions(obj)
    snaps = engine.store.snapshots(obj)
    if d.empty:
        log = html.Div('No decisions recorded yet. Export a steward workbook to start.', className='ms-empty')
    else:
        d = d.sort_values('id', ascending=False).assign(
            decision_label=d['decision'].map(lambda c: DECISIONS[c][0]),
            when=d['recorded_at'].str.replace('T', ' '))
        log = dash_table.DataTable(
            data=d[['when', 'target_key', 'related_key', 'record_label', 'decision_label', 'reason', 'steward',
                    'recorded_by', 'source', 'ruleset_version', 'recommendation']].to_dict('records'),
            columns=[{'name': n, 'id': c} for c, n in [
                ('when', 'Recorded'), ('target_key', 'Record'), ('related_key', 'With'), ('record_label', 'Name'),
                ('decision_label', 'Decision'), ('reason', 'Reason'), ('steward', 'Steward'),
                ('recorded_by', 'Entered by'), ('source', 'Source'), ('ruleset_version', 'Rules'),
                ('recommendation', 'Recommendation then')]],
            page_size=15, sort_action='native', filter_action='native', style_as_list_view=True,
            style_table={'overflowX': 'auto'},
            style_cell={'fontFamily': 'Poppins', 'fontSize': '12px', 'textAlign': 'left', 'padding': '8px',
                        'maxWidth': '260px', 'overflow': 'hidden', 'textOverflow': 'ellipsis'},
            style_header={'fontWeight': '700', 'backgroundColor': BG, 'color': MUTED})
    snap_rows = [html.Div(className='ms-row', children=[
        icon('lucide:camera', 14, BRAND), html.Span(s['label'], className='ms-row-name'),
        html.Span(f"saved {s['taken_at'].replace('T', ' ')} by {s['taken_by']} · rules v{s['ruleset_version']}"
                  + (' · superseded' if s['superseded'] else ''), className='ms-row-meta')])
        for _, s in snaps.sort_values('id', ascending=False).iterrows()] or [
        html.Div('No monthly positions saved yet.', className='ms-muted')]
    return html.Div([
        section_title('Decision log', f'{len(d):,} decisions · append-only audit trail', ic='lucide:scroll-text'),
        log,
        html.Div(style={'marginTop': '22px'}, children=[
            section_title('Saved monthly positions', 'Snapshots used for trends and change since last month',
                          ic='lucide:camera'), html.Div(snap_rows)]),
    ])


# ═════════════════════════════════════════════════════════════════════════════
# RULES & WHAT-IF
# ═════════════════════════════════════════════════════════════════════════════

def rules_shell(engine, obj):
    spec = OBJECTS[obj]
    r = engine.result(obj)
    params = spec['params']
    counts = r.fired['rule_id'].value_counts()
    rows = [html.Tr([html.Td(html.B(rule.name)), html.Td(rule.layer),
                     html.Td(rule.text(params), style={'whiteSpace': 'normal'}),
                     html.Td(class_pill(rule.outcome) if rule.outcome else ''),
                     html.Td(f"{int(counts.get(rule.id, 0)):,}")]) for rule in r.rules if rule.active]
    return card([
        section_title('Rules', f'Ruleset v{config.RULESET_VERSION}. Every rule and threshold is set in '
                      'migration_scope/config.py. Records is how many suppliers each rule applies to.',
                      ic='lucide:book-open'),
        html.Table([html.Thead(html.Tr([html.Th(h) for h in ('Rule', 'Category', 'What it does', 'Produces',
                                                             'Records')])),
                    html.Tbody(rows)], className='ms-mini ms-rulestable'),
        html.Div('Change log', className='ms-subhead'),
        html.Div([html.Div(f'v{v} · {d} · {t}', className='ms-muted') for v, d, t in config.CHANGELOG]),
    ])
