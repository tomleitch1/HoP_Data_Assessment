"""One test (or more) per rule in the supplier ruleset."""
import pandas as pd

from migration_scope.core import standardise as std
from migration_scope.core.model import (
    KEEP, FIX, MONITOR, CLOSE, HOLD_NONCOMMERCIAL, HOLD_POLICY, OUT_OF_SCOPE,
)
from migration_scope.tests.conftest import sup, inv, make_inputs, run, ent, days


# ── Standardised layer ───────────────────────────────────────────────────────

def test_standardise_names_vat_postcode():
    names = pd.Series(['Acme Facilities Limited.', 'ACME FACILITIES LTD', 'The Acme Co'])
    assert std.name(names).tolist()[:2] == ['ACME FACILITIES LTD', 'ACME FACILITIES LTD']
    assert std.vat(pd.Series(['GB 123 4567 89', 'gb123456789'])).tolist() == ['123456789', '123456789']
    assert std.postcode(pd.Series(['sw1a 0aa', 'SW1A0AA'])).tolist() == ['SW1A0AA', 'SW1A0AA']
    assert std.company_no(pd.Series(['1800000'])).tolist() == ['01800000']


# ── Population ───────────────────────────────────────────────────────────────

def test_pop01_only_n_and_p_are_in_population(params):
    r = run(make_inputs([sup('1', status='N'), sup('2', status='P'), sup('3', status='C'), sup('4', status='T')],
                        hist=[inv(i, 10) for i in '1234']), params)
    assert ent(r, 'HOC|1')['in_population'] and ent(r, 'HOC|2')['in_population']
    assert ent(r, 'HOC|3')['classification'] == OUT_OF_SCOPE
    assert ent(r, 'HOC|4')['classification'] == OUT_OF_SCOPE


def test_pop02_out_of_scope_clients_ignored(params):
    r = run(make_inputs([sup('1', client='CF')]), params)
    assert 'HOC|1' not in set(r.entities['entity_key'])


def test_pop03_legacy_exclusions(params):
    r = run(make_inputs([sup('8912'), sup('5', name='SZSINGLES')]), params)
    assert not ent(r, 'HOC|8912')['in_population'] and not ent(r, 'HOC|5')['in_population']


def test_ca_and_cm_roll_up_to_one_supplier(params):
    r = run(make_inputs([sup('7', client='CA'), sup('7', client='CM', status='C')], hist=[inv('7', 20)]), params)
    e = ent(r, 'HOC|7')
    assert e['clients'] == 'CA, CM' and e['in_population'] and e['classification'] == KEEP


def test_ca_cm_disagreement_is_a_consistency_issue(params):
    r = run(make_inputs([sup('7', client='CA', bank_account='11111112'),
                         sup('7', client='CM', bank_account='22222223')], hist=[inv('7', 20)]), params)
    assert 'MS-DQ-CLIENT-DIFF' in set(r.issues[r.issues['entity_key'] == 'HOC|7']['test_id'])


# ── Categorisation ───────────────────────────────────────────────────────────

def test_cat01_noncommercial_groups(params):
    r = run(make_inputs([sup('1', group='ME'), sup('2', group='IR'), sup('50001', house='HOL', group='05')],
                        hist=[inv('1', 5), inv('2', 5), inv('50001', 5, house='HOL')]), params)
    assert ent(r, 'HOC|1')['classification'] == HOLD_NONCOMMERCIAL
    assert ent(r, 'HOC|2')['classification'] == KEEP          # HMRC (IR) is commercial
    assert ent(r, 'HOL|50001')['classification'] == HOLD_NONCOMMERCIAL


def test_cat02_noncommercial_id_ranges(params):
    r = run(make_inputs([sup('10001234'), sup('30001', house='HOL', group='01'), sup('50002', house='HOL', group='01')],
                        hist=[inv('10001234', 5), inv('30001', 5, house='HOL'), inv('50002', 5, house='HOL')]), params)
    assert ent(r, 'HOC|10001234')['category_rule'] == 'MS-CAT-02'
    assert ent(r, 'HOL|30001')['classification'] == HOLD_NONCOMMERCIAL
    assert ent(r, 'HOL|50002')['classification'] == KEEP


def test_hol_group_and_id_range_disagree(params):
    r = run(make_inputs([sup('54000', house='HOL', group='06')], hist=[inv('54000', 5, house='HOL')]), params)
    assert ent(r, 'HOL|54000')['classification'] == HOLD_NONCOMMERCIAL
    assert 'MS-DQ-GROUP-ID' in set(r.issues['test_id'])


def test_cat03_card_accounts_held_separately(params):
    r = run(make_inputs([sup('55000', house='HOL', group='03')], hist=[inv('55000', 5, house='HOL')]), params)
    assert ent(r, 'HOL|55000')['classification'] == HOLD_POLICY


def test_cat04_individual_contractor_flag(params):
    r = run(make_inputs([sup('9', group='TI')], hist=[inv('9', 5)]), params)
    assert ent(r, 'HOC|9')['individual'] and ent(r, 'HOC|9')['classification'] != HOLD_NONCOMMERCIAL


# ── Activity and classification ──────────────────────────────────────────────

def test_cls01_dormant_is_close(params):
    r = run(make_inputs([sup('1')], hist=[inv('1', 600)]), params)
    assert ent(r, 'HOC|1')['classification'] == CLOSE and ent(r, 'HOC|1')['class_rule'] == 'MS-CLS-01'


def test_cls01_parked_with_no_activity_is_close(params):
    r = run(make_inputs([sup('1', status='P')]), params)
    assert ent(r, 'HOC|1')['classification'] == CLOSE


def test_payments_alone_are_not_activity(params):
    r = run(make_inputs([sup('1')], hist=[inv('1', 20, vtype='PY')]), params)
    assert ent(r, 'HOC|1')['classification'] == CLOSE


def test_open_item_keeps_dormant_supplier(params):
    r = run(make_inputs([sup('1')], open_=[inv('1', 900, rest=50.0)]), params)
    assert ent(r, 'HOC|1')['classification'] == KEEP


def test_open_po_keeps_dormant_supplier(params):
    po = [{'house': 'HOC', 'client': 'CA', 'order_id': '45001', 'apar_id': '1', 'status': 'O',
           'order_date': days(800)}]
    r = run(make_inputs([sup('1')], po=po), params)
    assert ent(r, 'HOC|1')['open_pos'] == 1 and ent(r, 'HOC|1')['classification'] == KEEP


def test_dormancy_threshold_is_a_parameter(params):
    inputs = make_inputs([sup('1')], hist=[inv('1', 400)])
    assert ent(run(inputs, params), 'HOC|1')['classification'] == KEEP
    params['dormancy_months'] = 12
    assert ent(run(inputs, params), 'HOC|1')['classification'] == CLOSE


def test_cls04_blocking_issue_is_fix(params):
    r = run(make_inputs([sup('1', bank_account=None, clearing_code=None)], hist=[inv('1', 10)]), params)
    assert ent(r, 'HOC|1')['classification'] == FIX
    assert {'SUP_BACS_NO_BANK'} <= set(r.issues[r.issues['blocking']]['test_id'])


def test_advisory_issue_stays_keep(params):
    r = run(make_inputs([sup('1', province=None)], hist=[inv('1', 10)]), params)
    assert ent(r, 'HOC|1')['classification'] == KEEP


def test_ltd_without_company_number_is_fix(params):
    r = run(make_inputs([sup('1', name='Widget Makers Ltd', comp_reg_no=None)], hist=[inv('1', 10)]), params)
    assert 'MS-DQ-LTD-COMPNO' in set(r.issues['test_id']) and ent(r, 'HOC|1')['classification'] == FIX


def test_company_number_formats():
    from dashboard.core.rules.formats import company_no_valid
    valid = ['01234567', 'SC123456', 'sc 123456', 'OC301234', 'NI012345', 'LP012345', 'RS12345C', 'R0000123']
    invalid = ['ABC123', 'XX123456', 'SC12345', 'SC1234567', '12345', None]
    assert company_no_valid(pd.Series(valid)).all()
    assert not company_no_valid(pd.Series(invalid)).any()


def test_prefixed_company_number_is_not_a_format_issue(params):
    r = run(make_inputs([sup('1', name='Highland Widgets Ltd', comp_reg_no='SC123456'),
                         sup('2', name='Bad Number Ltd', comp_reg_no='ABC123')],
                        hist=[inv('1', 10), inv('2', 10)]), params)
    fmt = r.issues[r.issues['test_id'] == 'SUP_COMP_REG_FORMAT']
    assert set(fmt['entity_key']) == {'HOC|2'}
    assert ent(r, 'HOC|1')['classification'] == KEEP and ent(r, 'HOC|2')['classification'] == FIX
    assert fmt.iloc[0]['evidence'] == 'comp_reg_no: ABC123'


def test_issue_evidence_shows_blanks(params):
    r = run(make_inputs([sup('1', address=None)], hist=[inv('1', 10)]), params)
    ev = r.issues[r.issues['test_id'] == 'SUP_ADDR_MISSING']['evidence']
    assert ev.tolist() == ['address: (blank)']


def test_cls05_keep(params):
    r = run(make_inputs([sup('1')], hist=[inv('1', 10)]), params)
    assert ent(r, 'HOC|1')['classification'] == KEEP and ent(r, 'HOC|1')['class_rule'] == 'MS-CLS-05'


# ── Duplicates ───────────────────────────────────────────────────────────────

def test_dup01_vat_match_after_standardising(params):
    r = run(make_inputs([sup('1', vat_reg_no='GB123456789'), sup('2', vat_reg_no='GB 123 4567 89')],
                        hist=[inv('1', 10), inv('2', 10)]), params)
    assert ent(r, 'HOC|1')['dup_group'] == ent(r, 'HOC|2')['dup_group'] != ''


def test_dup01_fuzzy_name_and_postcode(params):
    r = run(make_inputs([sup('1', name='Acme Facilities Ltd', zip_code='SW1A 0AA'),
                         sup('2', name='ACME FACILITIES LIMITED.', zip_code='sw1a0aa')],
                        hist=[inv('1', 10), inv('2', 10)]), params)
    assert ent(r, 'HOC|1')['dup_group'] != ''


def test_placeholder_bank_accounts_do_not_match(params):
    r = run(make_inputs([sup('1', clearing_code='00-00-00', bank_account='00000000'),
                         sup('2', clearing_code='00-00-00', bank_account='00000000')],
                        hist=[inv('1', 10), inv('2', 10)]), params)
    assert ent(r, 'HOC|1')['dup_group'] == ''


def test_chained_matches_form_one_group(params):
    r = run(make_inputs([sup('1', vat_reg_no='GB555666777'), sup('2', vat_reg_no='GB555666777'),
                         sup('3', clearing_code='20-00-00', bank_account='55779911'),
                         ], hist=[inv('1', 10), inv('2', 10), inv('3', 10)]), params)
    r2 = run(make_inputs([sup('1', vat_reg_no='GB555666777', clearing_code='20-00-00', bank_account='55779911'),
                          sup('2', vat_reg_no='GB555666777'),
                          sup('3', clearing_code='20-00-00', bank_account='55779911')],
                         hist=[inv('1', 10), inv('2', 10), inv('3', 10)]), params)
    assert ent(r, 'HOC|3')['dup_group'] == ''
    assert len({ent(r2, f'HOC|{i}')['dup_group'] for i in '123'}) == 1


def test_dup03_preferred_has_open_items_over_completeness(params):
    r = run(make_inputs([sup('1', vat_reg_no='GB123456789'), sup('2', vat_reg_no='GB123456789', province=None)],
                        hist=[inv('1', 5)], open_=[inv('2', 10, rest=10.0)]), params)
    assert ent(r, 'HOC|2')['preferred'] and not ent(r, 'HOC|1')['preferred']


def test_dup03_fewest_blocking_issues_wins(params):
    r = run(make_inputs([sup('1', vat_reg_no='GB123456789', terms_id=None),
                         sup('2', vat_reg_no='GB123456789')], hist=[inv('1', 5), inv('2', 300)]), params)
    assert ent(r, 'HOC|2')['preferred']


def test_cls02_and_cls03_non_preferred(params):
    r = run(make_inputs([sup('1', vat_reg_no='GB123456789'), sup('2', vat_reg_no='GB123456789'),
                         sup('3', vat_reg_no='GB987654321'), sup('4', vat_reg_no='GB987654321')],
                        hist=[inv('1', 5), inv('2', 300), inv('3', 5), inv('4', 60)]), params)
    assert ent(r, 'HOC|2')['classification'] == CLOSE and ent(r, 'HOC|2')['class_rule'] == 'MS-CLS-02'
    assert ent(r, 'HOC|4')['classification'] == MONITOR


def test_dormant_duplicate_is_close_not_monitor(params):
    r = run(make_inputs([sup('1', vat_reg_no='GB123456789'), sup('2', vat_reg_no='GB123456789')],
                        hist=[inv('1', 5), inv('2', 700)]), params)
    assert ent(r, 'HOC|2')['classification'] == CLOSE


def test_dup02_possible_duplicate_does_not_change_classification(params):
    r = run(make_inputs([sup('1', name='Brightwater Catering Services Ltd'),
                         sup('2', name='Brightwater Catering Service Ltd')], hist=[inv('1', 5), inv('2', 5)]), params)
    assert ent(r, 'HOC|1')['possible_dup'] and ent(r, 'HOC|1')['classification'] == KEEP


def test_xh01_cross_house_tagged_not_grouped(params):
    inputs = make_inputs([sup('1', vat_reg_no='GB245719348'), sup('52000', house='HOL', group='01',
                                                                  vat_reg_no='GB245719348')],
                         hist=[inv('1', 5), inv('52000', 5, house='HOL')])
    r = run(inputs, params)
    assert ent(r, 'HOC|1')['cross_house'] != '' and ent(r, 'HOC|1')['dup_group'] == ''
    params['cross_house_as_duplicate'] = True
    r = run(inputs, params)
    assert ent(r, 'HOC|1')['dup_group'] != ''


# ── Open items ───────────────────────────────────────────────────────────────

def test_trn01_stuck_items_by_age(params):
    r = run(make_inputs([sup('1')], hist=[inv('1', 5)],
                        open_=[inv('1', 30, rest=10.0, voucher='A'), inv('1', 100, rest=10.0, voucher='B')]), params)
    it = r.items.set_index('voucher_no')
    assert not it.loc['A', 'stuck'] and it.loc['B', 'stuck']
    assert ent(r, 'HOC|1')['stuck_undecided'] == 1
    assert it.loc['B', 'fy'] == 'FY2026/27' or it.loc['B', 'fy'].startswith('FY')


def test_dup03_level_records_go_to_a_steward(params):
    # Same everything except ID: the rules must not pick one (no lowest-ID tie-break)
    inputs = make_inputs([sup('1', vat_reg_no='GB123456789'), sup('2', vat_reg_no='GB123456789')],
                         hist=[inv('1', 10), inv('2', 10)])
    r = run(inputs, params)
    for k in ('HOC|1', 'HOC|2'):
        assert not ent(r, k)['preferred'] and ent(r, k)['preferred_tie']
        assert ent(r, k)['classification'] == MONITOR and ent(r, k)['class_rule'] == 'MS-DUP-03'


def test_dup03_steward_resolves_a_tie(params, store):
    from migration_scope.tests.conftest import decide
    inputs = make_inputs([sup('1', vat_reg_no='GB123456789'), sup('2', vat_reg_no='GB123456789')],
                         hist=[inv('1', 10), inv('2', 10)])
    decide(store, 'HOC|2', 'CONFIRM_PREFERRED')
    r = run(inputs, params, store)
    assert ent(r, 'HOC|2')['preferred'] and ent(r, 'HOC|2')['classification'] == KEEP
    assert not ent(r, 'HOC|1')['preferred_tie'] and ent(r, 'HOC|1')['classification'] == MONITOR
