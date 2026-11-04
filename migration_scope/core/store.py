"""
Storage for steward decisions and monthly snapshots (SQLite, one local file).

Decisions are append-only: a new decision on the same record never edits or
deletes an earlier row, it supersedes it. The full history is always kept.
"""
import getpass
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from migration_scope import config
from migration_scope.core.model import DECISIONS

_SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    object          TEXT NOT NULL,
    target_type     TEXT NOT NULL,          -- record | item | pair
    target_key      TEXT NOT NULL,          -- e.g. HOC|20977 or HOC|CA|20977|40012345
    related_key     TEXT NOT NULL DEFAULT '',
    decision        TEXT NOT NULL,
    reason          TEXT NOT NULL,
    steward         TEXT NOT NULL,
    recorded_by     TEXT NOT NULL,
    recorded_at     TEXT NOT NULL,
    source          TEXT NOT NULL,          -- 'Dashboard' or the uploaded workbook name
    ruleset_version TEXT NOT NULL,
    recommendation  TEXT NOT NULL DEFAULT '',
    record_label    TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_decisions_target ON decisions(object, target_key);

CREATE TABLE IF NOT EXISTS snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    object          TEXT NOT NULL,
    label           TEXT NOT NULL,
    month           TEXT NOT NULL,          -- YYYY-MM
    taken_at        TEXT NOT NULL,
    taken_by        TEXT NOT NULL,
    as_of           TEXT NOT NULL,
    ruleset_version TEXT NOT NULL,
    params_json     TEXT NOT NULL,
    summary_json    TEXT NOT NULL,
    superseded      INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS snapshot_records (
    snapshot_id     INTEGER NOT NULL,
    entity_key      TEXT NOT NULL,
    house           TEXT NOT NULL,
    classification  TEXT NOT NULL,
    recommended     TEXT NOT NULL,
    decision_status TEXT NOT NULL,
    blocking        INTEGER NOT NULL,
    issues          INTEGER NOT NULL,
    dup_group       TEXT NOT NULL,
    fingerprint     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_snaprec ON snapshot_records(snapshot_id);
"""

DECISION_COLS = ['id', 'object', 'target_type', 'target_key', 'related_key', 'decision', 'reason', 'steward',
                 'recorded_by', 'recorded_at', 'source', 'ruleset_version', 'recommendation', 'record_label']


def current_user():
    try:
        return getpass.getuser()
    except Exception:
        return 'unknown'


class Store:
    def __init__(self, db_path=None):
        self.path = Path(db_path or config.DB_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(_SCHEMA)

    def _conn(self):
        return sqlite3.connect(self.path)

    # ── Decisions ────────────────────────────────────────────────────────────
    def add_decisions(self, rows, source, recorded_by=None, when=None):
        """rows: dicts with object, target_type, target_key, decision, reason,
        steward and optionally related_key, recommendation, record_label."""
        when = when or datetime.now().isoformat(timespec='seconds')
        recorded_by = recorded_by or current_user()
        with self._conn() as c:
            for r in rows:
                if r['decision'] not in DECISIONS:
                    raise ValueError(f"Unknown decision {r['decision']}")
                if not str(r.get('reason', '')).strip():
                    raise ValueError('A reason is mandatory for every decision')
                if not str(r.get('steward', '')).strip():
                    raise ValueError('The steward name is mandatory for every decision')
                c.execute(
                    'INSERT INTO decisions (object, target_type, target_key, related_key, decision, reason, steward,'
                    ' recorded_by, recorded_at, source, ruleset_version, recommendation, record_label)'
                    ' VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (r['object'], r['target_type'], r['target_key'], r.get('related_key', '') or '',
                     r['decision'], str(r['reason']).strip(), str(r['steward']).strip(), recorded_by, when,
                     source, config.RULESET_VERSION, r.get('recommendation', '') or '', r.get('record_label', '') or ''))
        return len(rows)

    def decisions(self, obj=None) -> pd.DataFrame:
        q = 'SELECT * FROM decisions' + (' WHERE object = ?' if obj else '') + ' ORDER BY id'
        with self._conn() as c:
            return pd.read_sql_query(q, c, params=(obj,) if obj else ())

    def effective_decisions(self, obj) -> pd.DataFrame:
        """Latest decision per (target, family, related record): the one in force."""
        d = self.decisions(obj)
        if d.empty:
            return d.assign(family=pd.Series(dtype=str))
        d['family'] = d['decision'].map(lambda x: DECISIONS[x][1])
        # A pair decision is about (a, b) regardless of which side it was recorded on
        swap = d['target_type'] == 'pair'
        a = d['target_key'].where(~swap | (d['target_key'] < d['related_key']), d['related_key'])
        b = d['related_key'].where(~swap | (d['target_key'] < d['related_key']), d['target_key'])
        d.loc[swap, 'target_key'], d.loc[swap, 'related_key'] = a[swap], b[swap]
        return d.sort_values('id').groupby(['target_type', 'target_key', 'family', 'related_key'], as_index=False).tail(1)

    def backup(self, tag='backup'):
        """Copy the database before anything is written to it, so an upload can be undone."""
        if not self.path.exists():
            return None
        config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        dest = config.BACKUP_DIR / f"scope_{datetime.now():%Y%m%d_%H%M%S}_{tag}.db"
        shutil.copy2(self.path, dest)
        return dest

    # ── Snapshots ────────────────────────────────────────────────────────────
    def snapshots(self, obj) -> pd.DataFrame:
        with self._conn() as c:
            return pd.read_sql_query('SELECT * FROM snapshots WHERE object = ? ORDER BY id', c, params=(obj,))

    def month_snapshot(self, obj, month):
        s = self.snapshots(obj)
        s = s[(s['month'] == month) & (s['superseded'] == 0)]
        return None if s.empty else s.iloc[-1]

    def save_snapshot(self, obj, label, month, as_of, params, summary, records: pd.DataFrame):
        """Save this month's position. An earlier snapshot for the same month is
        kept but marked superseded, never deleted."""
        with self._conn() as c:
            c.execute('UPDATE snapshots SET superseded = 1 WHERE object = ? AND month = ?', (obj, month))
            cur = c.execute(
                'INSERT INTO snapshots (object, label, month, taken_at, taken_by, as_of, ruleset_version,'
                ' params_json, summary_json) VALUES (?,?,?,?,?,?,?,?,?)',
                (obj, label, month, datetime.now().isoformat(timespec='seconds'), current_user(), as_of,
                 config.RULESET_VERSION, json.dumps(params, default=str), json.dumps(summary, default=str)))
            sid = cur.lastrowid
            recs = records.assign(snapshot_id=sid)[
                ['snapshot_id', 'entity_key', 'house', 'classification', 'recommended', 'decision_status',
                 'blocking', 'issues', 'dup_group', 'fingerprint']]
            c.executemany('INSERT INTO snapshot_records VALUES (?,?,?,?,?,?,?,?,?,?)',
                          recs.itertuples(index=False, name=None))
        return sid

    def latest_snapshot(self, obj):
        s = self.snapshots(obj)
        s = s[s['superseded'] == 0]
        return None if s.empty else s.iloc[-1]

    def snapshot_records(self, snapshot_id) -> pd.DataFrame:
        with self._conn() as c:
            return pd.read_sql_query('SELECT * FROM snapshot_records WHERE snapshot_id = ?', c,
                                     params=(int(snapshot_id),))
