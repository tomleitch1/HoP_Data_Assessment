import copy
import hashlib
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from migration_scope import config  # noqa: E402
from migration_scope.core.store import Store  # noqa: E402
from migration_scope.objects import suppliers  # noqa: E402

AS_OF = pd.Timestamp('2026-11-01')


def days(n):
    return AS_OF - pd.Timedelta(days=n)


def _n(seed, mod):
    # Deterministic, well-spread numbers so default test suppliers never match each other by accident
    return int(hashlib.md5(seed.encode()).hexdigest(), 16) % mod


def sup(apar_id, house='HOC', client=None, name=None, group='TN', status='N', **kw):
    row = {'house': house, 'client': client or ('CA' if house == 'HOC' else 'LA'), 'apar_id': apar_id,
           'apar_name': name or f"{hashlib.md5(apar_id.encode()).hexdigest()[:10].upper()} Trading Ltd",
           'apar_gr_id': group, 'status': status,
           'vat_reg_no': f'GB{_n(apar_id + house, 900000000) + 100000000}',
           'comp_reg_no': f'{_n(apar_id, 90000000) + 10000000}', 'country_code': 'GB',
           'terms_id': '30D', 'pay_method': 'IP', 'currency': 'GBP',
           'clearing_code': f'{_n(apar_id + 's', 90) + 10}-11-22',
           'bank_account': f'{_n(apar_id + 'a', 90000000) + 10000000}', 'iban': None, 'swift': None,
           'address': '1 High Street', 'place': 'London', 'zip_code': f'SW1A {_n(apar_id, 9)}AA',
           'province': 'Greater London', 'last_update': days(30), 'last_trans_date': pd.NaT}
    row.update(kw)
    return row


def inv(apar_id, days_ago, house='HOC', client=None, vtype='PI', rest=0.0, voucher=None):
    return {'house': house, 'client': client or ('CA' if house == 'HOC' else 'LA'), 'apar_id': apar_id,
            'voucher_no': voucher or f'V{apar_id}{days_ago}', 'sequence_no': '1', 'voucher_type': vtype,
            'trans_date': days(days_ago), 'voucher_date': days(days_ago), 'amount': 100.0, 'rest_amount': rest,
            'due_date': days(days_ago - 30), 'ext_inv_ref': 'X1', 'status': 'N' if rest else 'C'}


def make_inputs(sups, hist=(), open_=(), po=()):
    def frame(rows, cols):
        return pd.DataFrame(list(rows)) if rows else pd.DataFrame(columns=cols)
    return {
        'master': pd.DataFrame(sups),
        'history': frame(hist, ['house', 'client', 'apar_id', 'voucher_no', 'voucher_type', 'trans_date']),
        'open_trans': frame(open_, ['house', 'client', 'apar_id', 'voucher_no', 'voucher_type', 'trans_date',
                                    'rest_amount']),
        'po': frame(po, ['house', 'client', 'order_id', 'apar_id', 'status', 'order_date']),
        'source': 'test',
    }


@pytest.fixture
def params():
    return copy.deepcopy(config.SUPPLIER_PARAMS)


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / 'test.db')


def run(inputs, params, store=None):
    dec = store.effective_decisions('suppliers') if store else None
    return suppliers.run(inputs, params, dec, AS_OF)


def ent(result, key):
    return result.entities.set_index('entity_key').loc[key]


def decide(store, key, decision, target_type='record', related='', reason='test reason', steward='Tester'):
    store.add_decisions([{'object': 'suppliers', 'target_type': target_type, 'target_key': key,
                          'related_key': related, 'decision': decision, 'reason': reason, 'steward': steward}],
                        source='test')
