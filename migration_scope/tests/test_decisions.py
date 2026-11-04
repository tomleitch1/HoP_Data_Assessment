"""Steward decisions: overrides, history, follow-through, workbook round trip and snapshots."""
import io

import pytest
from openpyxl import load_workbook

from migration_scope.core.engine import Engine
from migration_scope.core.model import KEEP, FIX, CLOSE, OVERRIDDEN, DECIDED, NOT_IN_EXTRACT
from migration_scope.core.workbook import export_steward_workbook, preview_upload, apply_upload
from migration_scope.tests.conftest import sup, inv, make_inputs, run, ent, decide


def test_keep_overrides_close_and_shows_both(params, store):
    inputs = make_inputs([sup('1')], hist=[inv('1', 700)])
    decide(store, 'HOC|1', 'KEEP')
    e = ent(run(inputs, params, store), 'HOC|1')
    assert e['classification'] == KEEP and e['recommended'] == CLOSE
    assert e['decision_status'] == OVERRIDDEN and e['decision_by'] == 'Tester'


def test_close_decision(params, store):
    decide(store, 'HOC|1', 'CLOSE')
    e = ent(run(make_inputs([sup('1')], hist=[inv('1', 5)]), params, store), 'HOC|1')
    assert e['classification'] == CLOSE and e['recommended'] == KEEP


def test_accept_as_is_turns_fix_into_keep(params, store):
    inputs = make_inputs([sup('1', terms_id=None)], hist=[inv('1', 5)])
    assert ent(run(inputs, params), 'HOC|1')['classification'] == FIX
    decide(store, 'HOC|1', 'ACCEPT_AS_IS')
    assert ent(run(inputs, params, store), 'HOC|1')['classification'] == KEEP


def test_agree_keeps_classification_and_marks_decided(params, store):
    decide(store, 'HOC|1', 'AGREE')
    e = ent(run(make_inputs([sup('1')], hist=[inv('1', 700)]), params, store), 'HOC|1')
    assert e['classification'] == CLOSE and e['decision_status'] == DECIDED


def test_latest_decision_wins_and_history_is_kept(params, store):
    decide(store, 'HOC|1', 'KEEP')
    decide(store, 'HOC|1', 'CLOSE')
    e = ent(run(make_inputs([sup('1')], hist=[inv('1', 5)]), params, store), 'HOC|1')
    assert e['classification'] == CLOSE
    assert len(store.decisions('suppliers')) == 2   # append-only


def test_decisions_need_a_reason_and_steward(store):
    with pytest.raises(ValueError):
        decide(store, 'HOC|1', 'KEEP', reason=' ')
    with pytest.raises(ValueError):
        decide(store, 'HOC|1', 'KEEP', steward='')


def test_confirm_preferred_switches_the_survivor(params, store):
    inputs = make_inputs([sup('1', vat_reg_no='GB123456789'), sup('2', vat_reg_no='GB123456789')],
                         hist=[inv('1', 5), inv('2', 60)])
    assert ent(run(inputs, params), 'HOC|1')['preferred']
    decide(store, 'HOC|2', 'CONFIRM_PREFERRED')
    r = run(inputs, params, store)
    assert ent(r, 'HOC|2')['preferred'] and ent(r, 'HOC|2')['group_confirmed']
    assert ent(r, 'HOC|1')['classification'] == 'Monitor'


def test_not_duplicate_removes_from_group(params, store):
    inputs = make_inputs([sup('1', vat_reg_no='GB123456789'), sup('2', vat_reg_no='GB123456789')],
                         hist=[inv('1', 5), inv('2', 300)])
    decide(store, 'HOC|2', 'NOT_DUPLICATE')
    r = run(inputs, params, store)
    assert ent(r, 'HOC|2')['dup_group'] == '' and ent(r, 'HOC|2')['classification'] == KEEP


def test_same_supplier_links_a_possible_duplicate(params, store):
    inputs = make_inputs([sup('1', name='Brightwater Catering Services Ltd'),
                          sup('2', name='Brightwater Catering Service Ltd')], hist=[inv('1', 5), inv('2', 300)])
    decide(store, 'HOC|1', 'SAME_SUPPLIER', target_type='pair', related='HOC|2')
    r = run(inputs, params, store)
    assert ent(r, 'HOC|1')['dup_group'] == ent(r, 'HOC|2')['dup_group'] != ''
    assert not ent(r, 'HOC|1')['possible_dup']


def test_different_supplier_clears_possible_duplicate(params, store):
    inputs = make_inputs([sup('1', name='Brightwater Catering Services Ltd'),
                          sup('2', name='Brightwater Catering Service Ltd')], hist=[inv('1', 5), inv('2', 5)])
    decide(store, 'HOC|2', 'DIFFERENT_SUPPLIER', target_type='pair', related='HOC|1')
    assert not ent(run(inputs, params, store), 'HOC|1')['possible_dup']


def test_dont_migrate_all_items_closes_dormant_supplier(params, store):
    inputs = make_inputs([sup('1')], open_=[inv('1', 900, rest=50.0, voucher='OLD')])
    assert ent(run(inputs, params), 'HOC|1')['classification'] == KEEP
    decide(store, 'HOC|CA|1|OLD', 'DONT_MIGRATE', target_type='item')
    e = ent(run(inputs, params, store), 'HOC|1')
    assert e['classification'] == CLOSE and e['class_rule'] == 'MS-TRN-02' and e['decision_status'] == DECIDED


def test_dont_migrate_does_not_close_active_supplier(params, store):
    decide(store, 'HOC|CA|1|OLD', 'DONT_MIGRATE', target_type='item')
    inputs = make_inputs([sup('1')], hist=[inv('1', 10)], open_=[inv('1', 900, rest=50.0, voucher='OLD')])
    assert ent(run(inputs, params, store), 'HOC|1')['classification'] == KEEP


def test_follow_through_and_survives_reextract(params, store):
    decide(store, 'HOC|1', 'CLOSE')
    decide(store, 'HOC|2', 'CLOSE')
    decide(store, 'HOC|3', 'KEEP')
    # Next month: 1 closed in Unit4, 2 still open, 3 closed against a Keep, 4 decided then deleted
    decide(store, 'HOC|4', 'CLOSE')
    r = run(make_inputs([sup('1', status='C'), sup('2'), sup('3', status='C')], hist=[inv('2', 700)]), params, store)
    assert ent(r, 'HOC|1')['follow_through'] == 'Actioned in Unit4'
    assert ent(r, 'HOC|2')['follow_through'] == 'Not yet actioned in Unit4'
    assert ent(r, 'HOC|3')['follow_through'].startswith('Conflict')
    assert ent(r, 'HOC|4')['classification'] == NOT_IN_EXTRACT


def test_workbook_round_trip_is_idempotent(params, store):
    inputs = make_inputs([sup('1'), sup('2')], hist=[inv('1', 700), inv('2', 800)])
    r = run(inputs, params, store)
    wb = load_workbook(io.BytesIO(export_steward_workbook(r, store.effective_decisions('suppliers'), 'HOC')))
    ws = wb['Close - confirm']
    head = [c.value for c in ws[1]]
    col = {h: i + 1 for i, h in enumerate(head)}
    ws.cell(2, col['Decision'], 'Agree with recommendation')
    ws.cell(2, col['Reason'], 'Dormant')
    ws.cell(2, col['Steward'], 'A Patel')
    ws.cell(3, col['Decision'], 'Keep: include in scope')          # no reason: rejected
    buf = io.BytesIO()
    wb.save(buf)
    prev = preview_upload(buf.getvalue(), 'wb.xlsx', r, store.effective_decisions('suppliers'))
    assert prev['counts'] == {'New decision': 1, 'Rejected': 1}
    assert apply_upload(prev, store, 'suppliers') == 1
    r2 = run(inputs, params, store)
    again = preview_upload(buf.getvalue(), 'wb.xlsx', r2, store.effective_decisions('suppliers'))
    assert again['counts'] == {'Already recorded': 1, 'Rejected': 1}


def test_snapshot_and_change_attribution(params, store, tmp_path):
    from migration_scope.dummy.generate import generate
    eng = Engine(store=store, source='dummy')
    generate()
    r = eng.result()
    eng.save_snapshot('suppliers', 'Test position')
    keep = r.entities[r.entities['classification'] == KEEP].iloc[0]['entity_key']
    decide(store, keep, 'CLOSE')
    eng.refresh()
    snap, changes = eng.changes_since_snapshot('suppliers')
    row = changes.set_index('entity_key').loc[keep]
    assert snap['label'] == 'Test position' and row['before'] == KEEP and row['now'] == CLOSE
    assert row['cause'] == 'Decision recorded'
