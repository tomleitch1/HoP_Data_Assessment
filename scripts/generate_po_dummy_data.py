"""
Parliament Finance Systems Programme
Purchase Orders Dummy Data Generator
=====================================
Generates two CSVs mirroring the shape of the PO SQL extract outputs (HoC only):

  - po_header_HOC.csv  (apoheader)
  - po_detail_HOC.csv  (apodetail)

Status distribution matches real Parliament data proportions:
  F: ~50%  (meaning unconfirmed — likely historical)
  C: ~33%  (closed)
  O: ~11%  (open / active)
  T:  ~3%  (meaning unconfirmed)
  N:  ~2%  (new)
  A:  ~0.5% (approved)

Date range: 2009 (EPOCH) to present, matching real data.
art_gr_description uses placeholder category names until Parliament confirms
the real algarticlegr descriptions.

Run:  python scripts/generate_po_dummy_data.py
Output: data/po/
"""

import os
import random
from datetime import date, timedelta
import pandas as pd
from faker import Faker

fake = Faker('en_GB')
random.seed(42)
Faker.seed(42)

OUTPUT_DIR = os.path.join('data', 'po')
os.makedirs(OUTPUT_DIR, exist_ok=True)

HOC_CLIENTS  = ['CA', 'CM']
TODAY        = date.today()
EPOCH        = date(2009, 4, 1)

STATUS_DIST = [
    ('F', 250),
    ('C', 165),
    ('O',  55),
    ('T',  15),
    ('N',  12),
    ('A',   3),
]

# 20 placeholder categories — real descriptions pulled from algarticlegr on Parliament laptop
ART_GROUPS = [
    ('ICT',       'ICT Infrastructure & Hosting'),
    ('FACIL',     'Facilities Management'),
    ('PROFSVC',   'Professional Services'),
    ('CATERING',  'Catering & Hospitality'),
    ('SECURITY',  'Security Services'),
    ('PRINT',     'Printing & Publications'),
    ('MAINT',     'Maintenance & Repair'),
    ('CONSULT',   'Management Consultancy'),
    ('TRAINING',  'Staff Learning & Development'),
    ('ENERGY',    'Utilities & Energy'),
    ('CLEANING',  'Cleaning & Grounds'),
    ('COMMS',     'Communications & Media'),
    ('LEGAL',     'Legal Services'),
    ('TRANSPORT', 'Transport & Logistics'),
    ('CAPITAL',   'Capital Projects'),
    ('ICTSUPP',   'ICT Support Services'),
    ('MEDICAL',   'Medical & Welfare'),
    ('EVENTS',    'Events & Ceremonies'),
    ('RESEARCH',  'Research & Information'),
    ('RECORDS',   'Archives & Records'),
]
ART_WEIGHTS = [20, 15, 12, 8, 10, 5, 8, 12, 6, 7, 5, 6, 8, 5, 15, 10, 3, 6, 4, 3]

GL_ACCOUNTS  = [str(i) for i in range(3000, 4500, 10)]
COST_CENTRES = ['CC001', 'CC002', 'CC003', 'CC010', 'CC020', 'CC030', 'CC040', 'CC050']
ORDER_TYPES  = ['PO', 'FO', 'BL']
CURRENCIES   = ['GBP'] * 18 + ['EUR', 'USD']
PAY_METHODS  = ['BACS', 'CHAPS', 'INT', 'CHQ']
TERMS        = ['30DAYS', '14DAYS', '60DAYS', 'NET30']


def _rand_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, max(delta, 0)))


def _excel_serial(d) -> int:
    if d is None:
        return None
    return (d - date(1899, 12, 30)).days


def _rand_apar_id():
    return str(random.randint(1000, 9999))


def _gen_headers():
    rows = []
    oid = 100000

    for status, count in STATUS_DIST:
        for _ in range(count):
            if status == 'O':
                order_dt = _rand_date(date(2020, 1, 1), TODAY)
            elif status in ('N', 'A'):
                order_dt = _rand_date(date(2022, 1, 1), TODAY)
            elif status == 'F':
                order_dt = _rand_date(EPOCH, date(2024, 12, 31))
            else:
                order_dt = _rand_date(EPOCH, date(2023, 12, 31))

            amend_no = 0
            if status in ('O', 'F', 'C') and random.random() < 0.30:
                amend_no = random.randint(1, 6)

            currency = random.choice(CURRENCIES)
            exch     = 1.0 if currency == 'GBP' else round(random.uniform(1.1, 1.35), 4)

            rows.append({
                'client':        random.choice(HOC_CLIENTS),
                'order_id':      oid,
                'apar_id':       _rand_apar_id(),
                'order_type':    random.choice(ORDER_TYPES),
                'voucher_no':    random.randint(500000, 999999),
                'voucher_type':  'PO',
                'status':        status,
                'amend_no':      amend_no,
                'order_date':    _excel_serial(order_dt),
                'voucher_date':  _excel_serial(order_dt),
                'deliv_date':    _excel_serial(order_dt + timedelta(days=random.randint(14, 120))) if random.random() > 0.1 else None,
                'confirm_date':  _excel_serial(order_dt + timedelta(days=random.randint(1, 5))) if status not in ('N',) else None,
                'obs_date':      None,
                'period':        int(f"{order_dt.year}{order_dt.month:02d}"),
                'currency':      currency,
                'exch_rate':     exch,
                'pay_method':    random.choice(PAY_METHODS),
                'terms_id':      random.choice(TERMS),
                'att_id_1':      'COSTC',
                'att_id_2':      'DEPTM',
                'att_id_3':      None,
                'att_id_4':      None,
                'att_id_5':      None,
                'att_id_6':      None,
                'att_id_7':      None,
                'dim_value_1':   random.choice(COST_CENTRES) if random.random() > 0.15 else None,
                'dim_value_2':   None,
                'dim_value_3':   None,
                'dim_value_4':   None,
                'dim_value_5':   None,
                'dim_value_6':   None,
                'dim_value_7':   None,
                'contract_id':   f'C{random.randint(10000,99999)}' if random.random() > 0.35 else None,
                'responsible':   fake.last_name() if random.random() > 0.2 else None,
                'responsible2':  None,
                'user_id':       fake.user_name()[:8].upper(),
                'ext_ord_ref':   f'EXT-{random.randint(1000,9999)}' if random.random() > 0.5 else None,
                'ext_inv_ref':   None,
                'client_ref':    None,
                'text1':         fake.bs()[:50] if random.random() > 0.4 else None,
                'text2':         None,
                'header_note':   None,
                'overrun_pct':   round(random.uniform(0, 10), 1) if random.random() > 0.5 else 0,
                'overrun_pct_a': 0,
                'overrun_pct_o': 0,
                'last_update':   _excel_serial(_rand_date(order_dt, min(order_dt + timedelta(days=180), TODAY))),
            })
            oid += 1

    return pd.DataFrame(rows)


def _gen_lines(headers: pd.DataFrame):
    rows = []

    for _, h in headers.iterrows():
        status = h['status']

        n_lines = (
            random.randint(1, 6) if status in ('O', 'N', 'A') else
            random.randint(1, 4) if status == 'F' else
            random.randint(1, 3)
        )

        if status == 'O':
            base = random.uniform(8000, 350000)
        elif status in ('N', 'A'):
            base = random.uniform(2000, 120000)
        elif status == 'F':
            base = random.uniform(500, 60000)
        elif status == 'C':
            base = random.uniform(500, 80000)
        else:
            base = random.uniform(500, 25000)

        for line in range(1, n_lines + 1):
            art_gr_id, art_gr_desc = random.choices(ART_GROUPS, weights=ART_WEIGHTS)[0]
            amount = round(base / n_lines * random.uniform(0.8, 1.2), 2)

            if status == 'F':
                arr_pct = random.uniform(0.0, 0.02)   # matches real near-zero pattern
                vow_pct = random.uniform(0.9, 1.0)
            elif status == 'C':
                arr_pct = random.uniform(0.0, 0.02)
                vow_pct = random.uniform(0.0, 1.0)
            elif status == 'O':
                arr_pct = random.uniform(0.0, 0.05)
                vow_pct = random.uniform(0.0, 0.5)
            else:
                arr_pct = 0.0
                vow_pct = 0.0

            arr_amount = round(amount * arr_pct, 2)
            vow_amount = round(amount * vow_pct, 2)
            exch       = float(h['exch_rate']) if h['exch_rate'] else 1.0

            rows.append({
                'client':             h['client'],
                'order_id':           h['order_id'],
                'line_no':            line,
                'sequence_no':        1,
                'apar_id':            h['apar_id'],
                'voucher_no':         h['voucher_no'],
                'voucher_type':       'PO',
                'status':             status,
                'amend_no':           h['amend_no'],
                'rev_status':         None,
                'amount':             amount,
                'cur_amount':         round(amount * exch, 2),
                'com_amount':         round(amount * random.uniform(0.9, 1.0), 2),
                'vow_amount':         vow_amount,
                'vow_val':            round(vow_amount * exch, 2),
                'arr_amount':         arr_amount,
                'arr_val':            round(arr_amount * exch, 2),
                'invoiced':           arr_amount,
                'cost_amount':        amount,
                'real_amount':        vow_amount,
                'forecast':           amount,
                'open_flag':          round(amount - arr_amount, 2),
                'unit_price':         round(amount / random.randint(1, 50), 2),
                'unit_code':          random.choice(['EA', 'HR', 'DAY', 'MTH']),
                'disc_percent':       0,
                'discount':           0,
                'tax_amount':         round(amount * 0.2, 2),
                'tax_percent':        20.0,
                'tax_code':           'S20',
                'tax_system':         'UK',
                'account':            random.choice(GL_ACCOUNTS) if random.random() > 0.08 else None,
                'att_1_id':           'COSTC',
                'att_2_id':           'DEPTM',
                'att_3_id':           None,
                'att_4_id':           None,
                'att_5_id':           None,
                'att_6_id':           None,
                'att_7_id':           None,
                'dim_1':              h['dim_value_1'],
                'dim_2':              None,
                'dim_3':              None,
                'dim_4':              None,
                'dim_5':              None,
                'dim_6':              None,
                'dim_7':              None,
                'article':            f'ART{random.randint(1000,9999)}' if random.random() > 0.5 else None,
                'art_gr_id':          art_gr_id,
                'art_gr_description': art_gr_desc,
                'art_descr':          fake.catch_phrase()[:40] if random.random() > 0.3 else None,
                'sup_article':        None,
                'deliv_date':         h['deliv_date'],
                'rev_del_date':       None,
                'order_date':         h['order_date'],
                'period':             h['period'],
                'currency':           h['currency'],
                'exch_rate':          h['exch_rate'],
                'contract_id':        h['contract_id'],
                'user_id':            h['user_id'],
                'last_update':        h['last_update'],
            })

    return pd.DataFrame(rows)


if __name__ == '__main__':
    print('Generating PO headers...')
    headers = _gen_headers()
    headers.to_csv(os.path.join(OUTPUT_DIR, 'po_header_HOC.csv'), index=False)
    print(f'  {len(headers):,} headers -> data/po/po_header_HOC.csv')

    print('Generating PO detail lines...')
    lines = _gen_lines(headers)
    lines.to_csv(os.path.join(OUTPUT_DIR, 'po_detail_HOC.csv'), index=False)
    print(f'  {len(lines):,} lines -> data/po/po_detail_HOC.csv')
    print('Done.')
