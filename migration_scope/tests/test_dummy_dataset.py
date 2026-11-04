"""Every planted edge case in the dummy dataset lands where it should."""
import pytest

from migration_scope.core.engine import Engine
from migration_scope.core.model import KEEP, FIX, MONITOR, CLOSE, HOLD_NONCOMMERCIAL, HOLD_POLICY, OUT_OF_SCOPE

EXPECTED = {
    'HOC|21000': CLOSE,        # dormant 3 years, nothing open
    'HOC|21100': KEEP,         # dormant with old open invoice
    'HOC|22000': KEEP,         # duplicate (VAT), preferred
    'HOC|22001': CLOSE,        # duplicate, non-preferred, inactive
    'HOC|22011': MONITOR,      # duplicate, non-preferred, used 3 months ago
    'HOC|25000': FIX,          # BACS with no bank details
    'HOC|25001': FIX,          # VAT missing
    'HOC|25002': FIX,          # Ltd with no company number
    'HOC|25004': KEEP,         # international with IBAN
    'HOC|26000': CLOSE,        # parked, new, no activity
    'HOC|26001': KEEP,         # parked with recent activity
    'HOC|27000': OUT_OF_SCOPE,  # closed in Unit4
    'HOC|27100': OUT_OF_SCOPE,  # terminated in Unit4
    'HOC|23001': KEEP,         # CA active, CM closed
    'HOL|30000': HOLD_NONCOMMERCIAL,
    'HOL|54000': HOLD_NONCOMMERCIAL,
    'HOL|55000': HOLD_POLICY,
}


@pytest.fixture(scope='module')
def result(tmp_path_factory):
    from migration_scope.core.store import Store
    return Engine(store=Store(tmp_path_factory.mktemp('d') / 'd.db'), source='dummy').result()


@pytest.mark.parametrize('key,expected', EXPECTED.items())
def test_edge_case(result, key, expected):
    assert result.entities.set_index('entity_key').loc[key, 'classification'] == expected


def test_matching_edge_cases(result):
    e = result.entities.set_index('entity_key')
    assert e.loc['HOC|22020', 'dup_group'] == e.loc['HOC|22021', 'dup_group'] != ''       # fuzzy name + postcode
    assert len({e.loc[k, 'dup_group'] for k in ('HOC|22030', 'HOC|22031', 'HOC|22032')}) == 1
    assert e.loc['HOC|22050', 'dup_group'] == ''                                              # placeholder bank
    assert e.loc['HOC|22040', 'possible_dup']
    assert e.loc['HOC|24000', 'cross_house'] and e.loc['HOC|24000', 'dup_group'] == ''
    assert e.loc['HOC|29000', 'individual']
    assert 'MS-DQ-CLIENT-DIFF' in set(result.issues[result.issues['entity_key'] == 'HOC|23000']['test_id'])
    assert result.items[result.items['entity_key'] == 'HOC|21101']['stuck'].any()


def test_no_dqa_test_failed_to_run(result):
    assert result.test_errors == []
