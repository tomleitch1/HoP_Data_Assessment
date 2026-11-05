"""
The engine service: owns the loaded inputs, the decision store and the latest
result for each object, and recomputes when decisions change.
"""
import json

import pandas as pd

from migration_scope import config
from migration_scope.core.model import NOT_IN_EXTRACT, IN_SCOPE
from migration_scope.core.store import Store
from migration_scope.objects import OBJECTS


def settings():
    try:
        return json.loads(config.SETTINGS_PATH.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


class Engine:
    def __init__(self, frames=None, store=None, source=None, as_of=None):
        self.frames = frames or {}
        self.store = store or Store()
        self.source = source or settings().get('source', 'dashboard')
        self.as_of = pd.Timestamp(as_of or pd.Timestamp.today()).normalize()
        self._inputs = {}
        self._results = {}
        self.version = 0

    def inputs(self, obj):
        if obj not in self._inputs:
            self._inputs[obj] = OBJECTS[obj]['module'].load_inputs(self.frames, self.source)
        return self._inputs[obj]

    def result(self, obj='suppliers'):
        if obj not in self._results:
            spec = OBJECTS[obj]
            self._results[obj] = spec['module'].run(self.inputs(obj), spec['params'],
                                                    self.store.effective_decisions(obj), self.as_of)
        return self._results[obj]

    def refresh(self, obj='suppliers'):
        """Recompute after decisions change."""
        self._results.pop(obj, None)
        self.version += 1
        return self.result(obj)

    # ── Snapshots and change since last month ────────────────────────────────
    def summary(self, obj='suppliers'):
        r = self.result(obj)
        mod = OBJECTS[obj]['module']
        out = {'all': mod.funnel(r.entities, r.raw)}
        for h in ('HOC', 'HOL'):
            out[h] = mod.funnel(r.entities, r.raw, h)
        e = r.entities[r.entities['classification'] != NOT_IN_EXTRACT]
        out['open_issues'] = int(e.loc[e['in_scope'], 'issues'].sum())
        out['blocking'] = int(e.loc[e['in_scope'], 'blocking'].sum())
        groups = e[e['dup_group'] != ''].drop_duplicates('dup_group')
        out['dup_groups'] = len(groups)
        out['dup_groups_resolved'] = int(groups['group_confirmed'].sum())
        out['decisions'] = len(self.store.decisions(obj))
        out['awaiting'] = int((e['pending'] != '').sum())
        return out

    def save_snapshot(self, obj, label):
        r = self.result(obj)
        e = r.entities
        recs = e.assign(dup_group=e['dup_group'].fillna(''))[[
            'entity_key', 'house', 'classification', 'recommended', 'decision_status', 'blocking', 'issues',
            'dup_group', 'fingerprint']]
        month = self.as_of.strftime('%Y-%m')
        return self.store.save_snapshot(obj, label, month, str(self.as_of.date()), OBJECTS[obj]['params'],
                                        self.summary(obj), recs)

    def changes_since_snapshot(self, obj='suppliers'):
        """Records whose classification changed since the last saved snapshot,
        each with the most likely cause."""
        snap = self.store.latest_snapshot(obj)
        if snap is None:
            return None, pd.DataFrame()
        before = self.store.snapshot_records(snap['id']).set_index('entity_key')
        now = self.result(obj).entities.set_index('entity_key')
        keys = before.index.union(now.index)
        df = pd.DataFrame(index=keys)
        df['before'] = before['classification'].reindex(keys).fillna('(new)')
        df['now'] = now['classification'].reindex(keys).fillna(NOT_IN_EXTRACT)
        df = df[df['before'] != df['now']].copy()
        if df.empty:
            return snap, df.reset_index()
        dec = self.store.decisions(obj)
        new = dec[dec['recorded_at'] >= snap['taken_at']]
        # Item keys are House|client|ID|voucher: attribute them to their supplier (House|ID)
        recent = set(new['target_key']) | set(new['related_key']) | {
            f"{k.split('|')[0]}|{k.split('|')[2]}" for k in new.loc[new['target_type'] == 'item', 'target_key']}
        fp_before = before['fingerprint'].reindex(df.index)
        fp_now = now['fingerprint'].reindex(df.index)
        pop_now = now['in_population'].reindex(df.index).fillna(False)
        cause = []
        for k in df.index:
            if k in recent:
                cause.append('Decision recorded')
            elif df.at[k, 'before'] == '(new)':
                cause.append('New in extract')
            elif not pop_now.get(k, False):
                cause.append('Unit4 status changed')
            elif fp_before.get(k) != fp_now.get(k):
                cause.append('Data changed')
            elif snap['ruleset_version'] != config.RULESET_VERSION:
                cause.append('Rule change')
            else:
                cause.append('Other')
        df['cause'] = cause
        df['house'] = [k.split('|')[0] for k in df.index]
        df['name'] = now['apar_name'].reindex(df.index).fillna('')
        return snap, df.reset_index().rename(columns={'index': 'entity_key'})

    def trend(self, obj='suppliers'):
        snaps = self.store.snapshots(obj)
        snaps = snaps[snaps['superseded'] == 0]
        rows = []
        for s in snaps.itertuples():
            summ = json.loads(s.summary_json)
            for h in ('HOC', 'HOL'):
                f = summ.get(h, {})
                rows.append({'month': s.month, 'label': s.label, 'house': h, 'in_scope': f.get('in_scope', 0),
                             **{c: f.get(c, 0) for c in IN_SCOPE + ['Close']}})
        return pd.DataFrame(rows)
