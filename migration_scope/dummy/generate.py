"""
Dummy supplier dataset for the Migration Scope Engine, in the same column
layout as the real SQL extracts (sql/supplier_*_run.sql, po_header_HOC_run.sql).

Every planted edge case is labelled in the _edge_case column so it can be
traced in the dashboard. Writes to data/migration_scope/dummy/ and never
touches the dashboard's own data files.

    python -m migration_scope.dummy.generate
"""
import random
from datetime import date, timedelta

import pandas as pd
from faker import Faker

from migration_scope import config

fake = Faker('en_GB')
TODAY = date.today()


def _d(days_ago):
    return TODAY - timedelta(days=int(days_ago))


class _Builder:
    def __init__(self, seed=42):
        random.seed(seed)
        Faker.seed(seed)
        self.master, self.open, self.hist, self.po = [], [], [], []
        self.voucher = 40000000
        self.order = 4500000

    # ── master ───────────────────────────────────────────────────────────────
    def supplier(self, house, client, apar_id, name, group, status='N', edge='', pay='IP', vat=True, comp=True,
                 bank=True, address=True, postcode=None, vat_no=None, comp_no=None, sort=None, acct=None,
                 iban=None, last_trans=None):
        pc = postcode or fake.postcode()
        self.master.append({
            'house': house, 'client': client, 'apar_id': apar_id, 'apar_name': name,
            'short_name': name[:10].upper(), 'apar_gr_id': group, 'status': status, 'apar_once': 'N',
            'vat_reg_no': (vat_no or f'GB{random.randint(100000000, 999999999)}') if vat else '',
            'comp_reg_no': (comp_no or f'{random.randint(1000000, 99999999):08d}') if comp else '',
            'country_code': 'GB' if pay != 'IN' else 'FR', 'tax_code': 'S20', 'tax_system': 'UKVAT',
            'terms_id': '30D', 'pay_method': pay, 'currency': 'GBP' if pay != 'IN' else 'EUR', 'pay_delay': '0',
            'clearing_code': (sort or f'{random.randint(10, 99)}-{random.randint(10, 99)}-{random.randint(10, 99)}')
            if bank and pay != 'IN' else '',
            'bank_account': (acct or f'{random.randint(10000000, 99999999)}') if bank and pay != 'IN' else '',
            'iban': (iban or f'FR76{random.randint(10**20, 10**21 - 1)}') if pay == 'IN' else '',
            'swift': 'BNPAFRPP' if pay == 'IN' else '',
            'address': fake.street_address().replace('\n', ' ') if address else '',
            'place': fake.city() if address else '', 'zip_code': pc if address else '',
            'province': fake.county() if address else '', 'expired_date': '',
            'last_update': str(_d(random.randint(10, 900))), 'wf_state': '',
            'last_trans_date': str(last_trans) if last_trans else '', '_edge_case': edge,
        })
        return self

    # ── transactions ─────────────────────────────────────────────────────────
    def invoice(self, house, client, apar_id, days_ago, amount=None, open_=False, vtype='PI', edge=''):
        self.voucher += 1
        amount = amount if amount is not None else round(random.uniform(150, 25000), 2)
        row = {'house': house, 'client': client, 'apar_id': apar_id, 'voucher_no': str(self.voucher),
               'sequence_no': '1', 'voucher_type': vtype, 'voucher_date': str(_d(days_ago)),
               'trans_date': str(_d(days_ago)), 'amount': amount, 'currency': 'GBP', '_edge_case': edge}
        if open_:
            self.open.append({**row, 'due_date': str(_d(days_ago - 30)), 'description': fake.sentence(nb_words=5),
                              'rest_amount': amount, 'status': 'N', 'pay_method': 'IP',
                              'ext_inv_ref': f'INV-{random.randint(1000, 99999)}', 'order_id': '',
                              'period': _d(days_ago).strftime('%Y%m')})
        elif days_ago <= 548:  # the history extract only holds the last 18 months
            self.hist.append({**row, 'status': 'C', 'rest_amount': 0.0, 'orig_reference': ''})
            self.voucher += 1
            self.hist.append({**row, 'voucher_no': str(self.voucher), 'voucher_type': 'PY',
                              'trans_date': str(_d(max(days_ago - 30, 0))), 'amount': -amount, 'status': 'C',
                              'rest_amount': 0.0, 'orig_reference': ''})
        return self

    def purchase_order(self, apar_id, days_ago, status='O', client='CA'):
        self.order += 1
        self.po.append({'house': 'HOC', 'client': client, 'order_id': str(self.order), 'apar_id': apar_id,
                        'order_type': 'PO', 'status': status, 'order_date': str(_d(days_ago)), 'currency': 'GBP'})
        return self

    def finish_last_trans(self):
        """last_trans_date = latest movement of any type, as the real extract computes it."""
        latest = {}
        for t in self.open + self.hist:
            k = (t['house'], t['client'], t['apar_id'])
            latest[k] = max(latest.get(k, ''), t['trans_date'])
        for m in self.master:
            k = (m['house'], m['client'], m['apar_id'])
            if k in latest and latest[k] > (m['last_trans_date'] or ''):
                m['last_trans_date'] = latest[k]


def build():
    b = _Builder()
    trade_hoc = ['TN', 'TC', 'SM', 'SS', 'CA']

    # Bulk clean active suppliers: HoC 1xx via 2xxxx IDs, HoL 5xxxx (normal) and 4xxxx (catering)
    for i in range(140):
        aid = str(20000 + i)
        last = random.choice([20, 45, 90, 200, 400])
        b.supplier('HOC', 'CA', aid, fake.company(), random.choice(trade_hoc), edge='')
        b.invoice('HOC', 'CA', aid, last).invoice('HOC', 'CA', aid, last + 60)
        if i % 4 == 0:
            b.purchase_order(aid, last + 10, status=random.choice(['O', 'F']))
        if i % 9 == 0:
            b.invoice('HOC', 'CA', aid, random.randint(5, 40), open_=True)
    for i in range(30):
        aid = str(30500 + i)
        b.supplier('HOC', 'CM', aid, fake.company(), random.choice(trade_hoc))
        b.invoice('HOC', 'CM', aid, random.choice([30, 120, 300]))
    for i in range(70):
        aid = str(50000 + i)
        grp = random.choice(['01', '01', '02', '07'])
        b.supplier('HOL', 'LA', aid if grp != '07' else str(40000 + i), fake.company(), grp)
        b.invoice('HOL', 'LA', aid if grp != '07' else str(40000 + i), random.choice([25, 80, 250, 500]))

    # Dormant: nothing for 3 years, nothing open -> Close
    for i in range(18):
        aid = str(21000 + i)
        b.supplier('HOC', 'CA', aid, fake.company(), 'TN', edge='Dormant 3 years, nothing open',
                   last_trans=_d(1100 + i * 20))
    for i in range(8):
        aid = str(51000 + i)
        b.supplier('HOL', 'LA', aid, fake.company(), '01', edge='Dormant, nothing open', last_trans=_d(800 + i * 30))

    # Dormant but with an old open invoice -> Keep, item stuck
    b.supplier('HOC', 'CA', '21100', 'Hartley Joinery Ltd', 'TN', edge='Dormant with old open invoice',
               last_trans=_d(900))
    b.invoice('HOC', 'CA', '21100', 900, open_=True, edge='Old open invoice (2+ years)')
    b.supplier('HOL', 'LA', '51100', 'Kestrel Print Services Ltd', '01', edge='Dormant with old open invoice',
               last_trans=_d(700))
    b.invoice('HOL', 'LA', '51100', 700, open_=True)

    # Active supplier with a stuck invoice (5 months old) and a recent one
    b.supplier('HOC', 'CA', '21101', 'Meridian Office Supplies Ltd', 'TN', edge='Active with stuck open invoice')
    b.invoice('HOC', 'CA', '21101', 150, open_=True, edge='Stuck: 5 months').invoice('HOC', 'CA', '21101', 12,
                                                                                         open_=True)

    # Exact duplicate pair (same VAT): preferred has open PO, other inactive 1 year -> Close
    b.supplier('HOC', 'CA', '22000', 'Northgate Security Services Ltd', 'SS', vat_no='GB123456789',
               edge='Duplicate (VAT): preferred')
    b.invoice('HOC', 'CA', '22000', 15).purchase_order('22000', 20)
    b.supplier('HOC', 'CA', '22001', 'Northgate Security Ltd', 'SS', vat_no='GB 123 4567 89',
               edge='Duplicate (VAT): non-preferred, inactive 1 year -> Close')
    b.invoice('HOC', 'CA', '22001', 380)

    # Duplicate where the non-preferred one was used 3 months ago -> Monitor
    b.supplier('HOC', 'CA', '22010', 'Pemberton Facilities Management Ltd', 'TN', sort='40-11-22',
               acct='31926819', edge='Duplicate (bank): preferred')
    b.invoice('HOC', 'CA', '22010', 10, open_=True)
    b.supplier('HOC', 'CA', '22011', 'Pemberton FM', 'TN', sort='40-11-22', acct='31926819',
               edge='Duplicate (bank): non-preferred, used 3 months ago -> Monitor')
    b.invoice('HOC', 'CA', '22011', 95)

    # Fuzzy-name duplicate: same name once standardised + same postcode
    b.supplier('HOC', 'CA', '22020', 'Acme Facilities Ltd', 'TN', postcode='SW1A 0AA',
               edge='Duplicate (name + postcode, fuzzy): preferred')
    b.invoice('HOC', 'CA', '22020', 30)
    b.supplier('HOC', 'CA', '22021', 'ACME FACILITIES LIMITED.', 'TN', postcode='sw1a0aa', bank=False,
               edge='Duplicate (name + postcode, fuzzy): non-preferred')
    b.invoice('HOC', 'CA', '22021', 250)

    # Three-way group via chained keys (VAT on one pair, bank on the other)
    b.supplier('HOC', 'CA', '22030', 'Riverside Cleaning Co', 'TN', vat_no='GB555666777', sort='20-00-00',
               acct='55779911', edge='Three-way duplicate group (chained VAT + bank)')
    b.invoice('HOC', 'CA', '22030', 60)
    b.supplier('HOC', 'CA', '22031', 'Riverside Cleaning Company', 'TN', vat_no='GB555666777',
               edge='Three-way duplicate group (chained VAT + bank)')
    b.invoice('HOC', 'CA', '22031', 400)
    b.supplier('HOC', 'CM', '22032', 'Riverside Contract Cleaning', 'TN', sort='20-00-00', acct='55779911',
               edge='Three-way duplicate group (chained VAT + bank)')
    b.invoice('HOC', 'CM', '22032', 700)

    # Possible duplicate: similar names, different addresses
    b.supplier('HOC', 'CA', '22040', 'Brightwater Catering Services Ltd', 'CA', edge='Possible duplicate (similar name)')
    b.invoice('HOC', 'CA', '22040', 40)
    b.supplier('HOC', 'CA', '22041', 'Brightwater Catering Service Ltd', 'CA', edge='Possible duplicate (similar name)')
    b.invoice('HOC', 'CA', '22041', 70)

    # Placeholder bank accounts must not create a duplicate group
    for aid in ('22050', '22051'):
        b.supplier('HOC', 'CA', aid, fake.company(), 'TN', sort='00-00-00', acct='00000000',
                   edge='Placeholder bank account 00000000 (not a duplicate)')
        b.invoice('HOC', 'CA', aid, 50)

    # Same supplier ID under CA and CM with different bank details
    b.supplier('HOC', 'CA', '23000', 'Whitehall Stationers Ltd', 'TN', vat_no='GB222333444', sort='30-90-12',
               acct='11223344', edge='CA and CM rows disagree (bank details)')
    b.supplier('HOC', 'CM', '23000', 'Whitehall Stationers Ltd', 'TN', vat_no='GB222333444', sort='30-90-12',
               acct='99887766', edge='CA and CM rows disagree (bank details)')
    b.invoice('HOC', 'CA', '23000', 20).invoice('HOC', 'CM', '23000', 600)
    # CA active, CM closed: one supplier, in scope
    b.supplier('HOC', 'CA', '23001', 'Lambeth Electrical Ltd', 'TN', edge='CA active, CM closed')
    b.supplier('HOC', 'CM', '23001', 'Lambeth Electrical Ltd', 'TN', status='C', edge='CA active, CM closed')
    b.invoice('HOC', 'CA', '23001', 45)

    # Cross-House matches (same VAT / same company number in HoC and HoL)
    b.supplier('HOC', 'CA', '24000', 'British Telecommunications PLC', 'TN', vat_no='GB245719348',
               comp_no='01800000', edge='Cross-House match (VAT + company no)')
    b.invoice('HOC', 'CA', '24000', 8)
    b.supplier('HOL', 'LA', '52000', 'BT PLC', '01', vat_no='GB245719348', comp_no='1800000',
               edge='Cross-House match (VAT + company no)')
    b.invoice('HOL', 'LA', '52000', 12)
    b.supplier('HOC', 'CA', '24001', 'Crown Commercial Furniture Ltd', 'TN', comp_no='06543210',
               edge='Cross-House match (company no)')
    b.invoice('HOC', 'CA', '24001', 100)
    b.supplier('HOL', 'LA', '52001', 'Crown Commercial Furniture Limited', '02', comp_no='06543210',
               edge='Cross-House match (company no)')
    b.invoice('HOL', 'LA', '52001', 200)

    # Fix: blocking issues on kept suppliers
    b.supplier('HOC', 'CA', '25000', 'Thameside Plumbing Ltd', 'TN', bank=False, edge='Fix: BACS with no bank details')
    b.invoice('HOC', 'CA', '25000', 25)
    b.supplier('HOC', 'CA', '25001', 'Victoria Audio Visual Ltd', 'TN', vat=False, edge='Fix: VAT number missing')
    b.invoice('HOC', 'CA', '25001', 33)
    b.supplier('HOC', 'CA', '25002', 'Abbey Catering Equipment Ltd', 'CA', comp=False,
               edge='Fix: Ltd with no company number')
    b.invoice('HOC', 'CA', '25002', 70)
    b.supplier('HOC', 'CA', '25003', 'Millbank Removals Ltd', 'TN', address=False, edge='Fix: no address')
    b.invoice('HOC', 'CA', '25003', 15)
    b.supplier('HOC', 'CA', '25004', 'Lyon Archives SARL', 'TN', pay='IN', edge='International with IBAN (OK)')
    b.invoice('HOC', 'CA', '25004', 18)
    b.supplier('HOL', 'LA', '52100', 'Parliament Square Florists Ltd', '01', bank=False,
               edge='Fix: BACS with no bank details')
    b.invoice('HOL', 'LA', '52100', 40)

    # Parked new supplier, nothing yet -> Close (18 months is absolute)
    b.supplier('HOC', 'CA', '26000', 'Greenline Events Ltd', 'TN', status='P', edge='Parked, new, no activity -> Close')
    # Parked supplier with recent activity -> Keep
    b.supplier('HOC', 'CA', '26001', 'Stonegate Masonry Ltd', 'TN', status='P', edge='Parked with recent activity')
    b.invoice('HOC', 'CA', '26001', 60)

    # Closed and terminated: never in scope (one closed record matches an active supplier's VAT)
    for i in range(25):
        b.supplier('HOC', 'CA', str(27000 + i), fake.company(), 'TN', status='C', edge='Closed in Unit4',
                   last_trans=_d(1500 + i))
    for i in range(6):
        b.supplier('HOC', 'CA', str(27100 + i), fake.company(), 'TN', status='T', edge='Terminated in Unit4')
    for i in range(10):
        b.supplier('HOL', 'LA', str(53000 + i), fake.company(), '01', status='C', edge='Closed in Unit4')

    # Legacy exclusions (89 / 99 prefix, SZSINGLES)
    b.supplier('HOC', 'CA', '8900001', 'Sundry Payee Account', 'TN', edge='Legacy exclusion (89 prefix)')
    b.supplier('HOC', 'CA', '99001', 'SZSINGLES', 'TN', edge='Legacy exclusion (SZSINGLES)')

    # Non-commercial: HoC groups and ID ranges
    for grp, label, n in (('EM', 'Employee', 6), ('ME', 'Member', 8), ('SA', 'Select Committee Advisor', 4),
                          ('WI', 'Witness', 5)):
        for i in range(n):
            aid = str(28000 + len(b.master))
            b.supplier('HOC', 'CA', aid, fake.name(), grp, vat=False, comp=False,
                       edge=f'Non-commercial: {label} (group {grp})')
            b.invoice('HOC', 'CA', aid, random.randint(10, 300), vtype='PI')
    for i in range(5):
        aid = f'1000{i:04d}'
        b.supplier('HOC', 'CA', aid, fake.name(), 'TN', vat=False, comp=False, address=False,
                   edge='Non-commercial: iTrent employee (1000 prefix)')
        b.invoice('HOC', 'CA', aid, 30)
    # Individual contractors (commercial, flagged individual)
    for i in range(3):
        aid = str(29000 + i)
        b.supplier('HOC', 'CA', aid, fake.name(), 'TI', vat=False, comp=False, edge='Individual contractor (IR35)')
        b.invoice('HOC', 'CA', aid, 40)

    # Non-commercial: HoL groups and ID ranges
    for i in range(6):
        aid = f'3{i:04d}'
        b.supplier('HOL', 'LA', aid, f'Lord {fake.last_name()}', '05', vat=False, comp=False,
                   edge='Non-commercial: Member (group 05, prefix 3)')
        b.invoice('HOL', 'LA', aid, 60)
    for i in range(5):
        aid = f'1{i:04d}'
        b.supplier('HOL', 'LA', aid, fake.name(), '06', vat=False, comp=False,
                   edge='Non-commercial: Employee (group 06, prefix 1)')
        b.invoice('HOL', 'LA', aid, 90)
    for i in range(3):
        aid = f'2{i:04d}'
        b.supplier('HOL', 'LA', aid, fake.name(), '06', vat=False, comp=False,
                   edge='Non-commercial: Employee weekly payroll (prefix 2)')
        b.invoice('HOL', 'LA', aid, 20)
    b.supplier('HOL', 'LA', '54000', fake.name(), '06', vat=False, comp=False,
               edge='Group 06 Employee but normal-supplier ID range (mismatch)')
    b.invoice('HOL', 'LA', '54000', 50)
    for i in range(4):
        aid = str(55000 + i)
        b.supplier('HOL', 'LA', aid, f'Card account: {fake.name()}', '03', vat=False, comp=False,
                   edge='Card account (group 03): policy decision')
        b.invoice('HOL', 'LA', aid, 35)

    b.finish_last_trans()
    return b


def generate(out_dir=None):
    out = config.DUMMY_DIR if out_dir is None else out_dir
    out.mkdir(parents=True, exist_ok=True)
    b = build()
    files = {'supplier_master': b.master, 'supplier_open_trans': b.open, 'supplier_history': b.hist}
    for stem, rows in files.items():
        df = pd.DataFrame(rows)
        for h in ('HOC', 'HOL'):
            df[df['house'] == h].drop(columns='house').to_csv(out / f'{stem}_{h}.csv', index=False)
    pd.DataFrame(b.po).drop(columns='house').to_csv(out / 'po_header_HOC.csv', index=False)
    return out


if __name__ == '__main__':
    path = generate()
    print(f'Dummy supplier dataset written to {path}')
