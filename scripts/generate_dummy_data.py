"""
Parliament Finance Systems Programme
AR Customer Dummy Data Generator
=================================
Generates six CSVs mirroring the exact shape of the three AR SQL extract outputs:
  - customer_master_HOC.csv       / customer_master_HOL.csv       (acuheader)
  - customer_open_trans_HOC.csv   / customer_open_trans_HOL.csv   (acutrans)
  - customer_history_HOC.csv      / customer_history_HOL.csv      (acuhistr)

Each file contains a mix of clean records (to pass DQ checks) and deliberate
edge-case rows (to trigger specific DQ tests). Edge cases are labelled with
a comment in the _edge_case column so expected failures are traceable.

Run:  python generate_ar_dummy_data.py
Output: ./data/ directory (created if not present)
"""

import os
import random
from datetime import datetime, timedelta, date

import pandas as pd
from faker import Faker

fake = Faker('en_GB')
random.seed(42)
Faker.seed(42)

OUTPUT_DIR = 'data'
os.makedirs(OUTPUT_DIR, exist_ok=True)

TODAY = date.today()
THREE_YEARS_AGO = TODAY - timedelta(days=3 * 365)
EIGHTEEN_MONTHS_AGO = TODAY - timedelta(days=548)

HOC = 'HOC'
HOL = 'HOL'

VOUCHER_TYPES_INV = ['SINV', 'DINV', 'PINV']   # invoice types
VOUCHER_TYPES_CN  = ['SCRN', 'DCRN']            # credit note types
VOUCHER_TYPES_RCT = ['SRCT', 'DRCT']            # receipt types
STATUSES          = ['N', 'P', 'R', 'I']
CURRENCIES        = ['GBP', 'USD', 'EUR']
PAY_METHODS       = ['BACS', 'CHQ', 'INT', 'DD']
TERMS             = ['30NET', '60NET', '14NET', 'COD']

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def rand_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, max(delta, 0)))

def fmt_sort_code() -> str:
    return f"{random.randint(10,99)}-{random.randint(10,99)}-{random.randint(10,99)}"

def fmt_account() -> str:
    return str(random.randint(10000000, 99999999))

def fmt_vat() -> str:
    return f"GB{random.randint(100000000, 999999999)}"

def fmt_comp_reg() -> str:
    return str(random.randint(10000000, 99999999))

def fmt_iban() -> str:
    return f"GB{random.randint(10,99)}{''.join([str(random.randint(0,9)) for _ in range(18)])}"

def fmt_swift() -> str:
    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    return ''.join(random.choices(letters, k=4)) + 'GB' + ''.join(random.choices(letters + '0123456789', k=2))

def voucher_no(prefix='AR', n=6) -> str:
    return f"{prefix}{random.randint(10**(n-1), 10**n - 1)}"

def _yn(prob_yes=0.5):
    return 'Y' if random.random() < prob_yes else 'N'

def _null(prob_null=0.05):
    """Return None with given probability, else signal to use real value."""
    return random.random() < prob_null

# ──────────────────────────────────────────────────────────────────────────────
# CUSTOMER MASTER  (acuheader)
# ──────────────────────────────────────────────────────────────────────────────

def make_clean_customer(client: str, apar_id: str) -> dict:
    pay_method = random.choice(PAY_METHODS)
    currency   = 'GBP'
    has_dd     = pay_method == 'DD'
    has_int    = pay_method == 'INT'

    return {
        'client':        client,
        'apar_id':       apar_id,
        'apar_name':     fake.company(),
        'short_name':    fake.company()[:10],
        'apar_gr_id':    random.choice(['CORP', 'GOV', 'CHAR', 'SME']),
        'status':        'N',
        'apar_once':     '0',
        'main_apar_id':  None,
        'vat_reg_no':    fmt_vat(),
        'comp_reg_no':   fmt_comp_reg(),
        'country_code':  'GB',
        'tax_code':      random.choice(['S1', 'S2', 'Z0']),
        'tax_system':    'UK_VAT',
        'terms_id':      random.choice(TERMS),
        'pay_method':    pay_method,
        'currency':      currency,
        'pay_delay':     random.choice([0, 0, 0, 5, 10]),
        'credit_limit':  round(random.uniform(5000, 200000), 2),
        'credit_age':    random.choice([30, 60, 90]),
        'intrule_id':    random.choice(['RULE1', 'RULE2', 'STD']),
        'clearing_code': fmt_sort_code() if has_dd else None,
        'bank_account':  fmt_account()   if has_dd else None,
        'iban':          fmt_iban()       if has_int else None,
        'swift':         fmt_swift()      if has_int else None,
        'collect_flag':  0,
        'invoice_code':  random.choice(['STD', 'ELEC', 'PAPER']),
        'expired_date':  None,
        'last_update':   rand_date(date(2021, 1, 1), TODAY).isoformat(),
        'wf_state':      'T',
        '_edge_case':    None,
    }


def make_customer_edge_cases(client: str, start_id: int) -> list:
    """One row per named DQ issue to ensure each test fires at least once."""
    cases = []
    i = start_id

    def ec(overrides: dict, label: str) -> dict:
        nonlocal i
        base = make_clean_customer(client, f"C{client}{i:04d}")
        base.update(overrides)
        base['_edge_case'] = label
        i += 1
        return base

    # Completeness
    cases.append(ec({'vat_reg_no': None},   'CUST_VAT_MISSING'))
    cases.append(ec({'comp_reg_no': None},  'CUST_COMP_REG_MISSING'))
    cases.append(ec({'terms_id': None},     'CUST_TERMS_MISSING'))
    cases.append(ec({'pay_method': None},   'CUST_PAY_METHOD_MISSING'))
    cases.append(ec({'currency': None},     'CUST_CURRENCY_MISSING'))
    cases.append(ec({'credit_limit': None}, 'CUST_CREDIT_LIMIT_NULL'))
    cases.append(ec({'credit_limit': 0},    'CUST_CREDIT_LIMIT_ZERO'))
    cases.append(ec({'intrule_id': None},   'CUST_INTRULE_MISSING'))

    # Validity
    cases.append(ec({'vat_reg_no': '12345INVALID'},         'CUST_VAT_FORMAT'))
    cases.append(ec({'comp_reg_no': 'ABC123'},               'CUST_COMP_REG_FORMAT'))
    cases.append(ec({'clearing_code': '123456',
                     'pay_method': 'DD',
                     'bank_account': fmt_account()},          'CUST_SORT_FORMAT'))
    cases.append(ec({'bank_account': '123X',
                     'pay_method': 'DD',
                     'clearing_code': fmt_sort_code()},       'CUST_BANK_FORMAT'))
    cases.append(ec({'swift': 'TOOSHORT',
                     'iban': fmt_iban(),
                     'pay_method': 'INT'},                    'CUST_SWIFT_FORMAT'))

    # Consistency
    cases.append(ec({'expired_date': rand_date(date(2022,1,1), date(2023,12,31)).isoformat(),
                     'status': 'N'},                         'CUST_EXPIRED_ACTIVE'))
    cases.append(ec({'wf_state': 'W'},                       'CUST_WF_STUCK'))
    cases.append(ec({'collect_flag': 1},                     'CUST_COLLECT_FLAG'))
    cases.append(ec({'pay_method': 'DD',
                     'clearing_code': None,
                     'bank_account': None},                   'CUST_DD_NO_BANK'))
    cases.append(ec({'main_apar_id': f"C{client}0001"},      'CUST_SUBSIDIARY'))

    # Duplicates — same name as first clean record (set after clean records built)
    dup = make_clean_customer(client, f"C{client}{i:04d}")
    dup['_edge_case'] = 'CUST_NAME_DUP'
    # Name will be forced to match by caller after clean list is assembled
    cases.append(dup)
    i += 1

    dup_vat = make_clean_customer(client, f"C{client}{i:04d}")
    dup_vat['_edge_case'] = 'CUST_VAT_DUP'
    cases.append(dup_vat)
    i += 1

    # Scope / timeliness
    cases.append(ec({'apar_once': '1'},                                                'CUST_SUNDRY'))
    cases.append(ec({'last_update': (TODAY - timedelta(days=4*365)).isoformat()},      'CUST_STALE'))

    # Inactive customer (for backward-compat join tests from transactions)
    inactive = make_clean_customer(client, f"C{client}{i:04d}")
    inactive['status']      = 'C'
    inactive['expired_date']= rand_date(date(2020,1,1), date(2022,12,31)).isoformat()
    inactive['_edge_case']  = 'CUST_INACTIVE_FOR_TRANS_JOIN'
    cases.append(inactive)

    return cases, i


def build_customer_master(client: str, n_clean: int = 60):
    clean = [make_clean_customer(client, f"C{client}{i:04d}") for i in range(1, n_clean + 1)]
    edge_cases, _ = make_customer_edge_cases(client, n_clean + 1)

    # Wire up duplicate name and VAT to existing clean records
    dup_name = next(r for r in edge_cases if r['_edge_case'] == 'CUST_NAME_DUP')
    dup_vat  = next(r for r in edge_cases if r['_edge_case'] == 'CUST_VAT_DUP')
    dup_name['apar_name'] = clean[0]['apar_name']
    dup_vat['vat_reg_no'] = clean[1]['vat_reg_no']

    all_rows = clean + edge_cases
    return pd.DataFrame(all_rows)


# ──────────────────────────────────────────────────────────────────────────────
# CUSTOMER OPEN TRANSACTIONS  (acutrans)
# ──────────────────────────────────────────────────────────────────────────────

def make_clean_open_trans(client: str, apar_id: str, vno: str) -> dict:
    trans_date = rand_date(date(2023, 1, 1), TODAY)
    due_date   = trans_date + timedelta(days=random.choice([30, 60, 90]))
    amount     = round(random.uniform(500, 50000), 2)
    paid       = round(random.uniform(0, amount * 0.8), 2)
    rest       = round(amount - paid, 2)
    currency   = 'GBP'

    return {
        'client':          client,
        'apar_id':         apar_id,
        'voucher_no':      vno,
        'sequence_no':     1,
        'voucher_type':    random.choice(VOUCHER_TYPES_INV),
        'voucher_date':    trans_date.isoformat(),
        'trans_date':      trans_date.isoformat(),
        'due_date':        due_date.isoformat(),
        'description':     fake.sentence(nb_words=6),
        'amount':          amount,
        'cur_amount':      None,
        'currency':        currency,
        'rest_amount':     rest,
        'rest_curr':       None,
        'discount':        None,
        'dc_flag':         1,
        'status':          'N',
        'pay_flag':        0,
        'pay_method':      random.choice(PAY_METHODS),
        'payment_date':    None,
        'period':          f"{trans_date.year}{trans_date.month:02d}",
        'payperiod':       None,
        'ext_inv_ref':     f"INV{random.randint(10000,99999)}",
        'orig_reference':  None,
        'order_id':        f"PO{random.randint(1000,9999)}",
        'contract_id':     None,
        'tax_code':        'S1',
        'exch_rate':       None,
        'rem_level':       random.choice([0, 0, 0, 1, 2]),
        'remind_date':     None,
        'collect_status':  None,
        'collect_agency':  None,
        'intrule_id':      'RULE1',
        'int_status':      None,
        'last_update':     TODAY.isoformat(),
        'wf_state':        'T',
        '_edge_case':      None,
    }


def make_unapplied_receipt(client: str, apar_id: str, vno: str) -> dict:
    """Seq 18 — unapplied cash on account (pay_flag = 1)."""
    row = make_clean_open_trans(client, apar_id, vno)
    row['pay_flag']     = 1
    row['voucher_type'] = random.choice(VOUCHER_TYPES_RCT)
    row['amount']       = round(random.uniform(200, 10000), 2)
    row['rest_amount']  = row['amount']
    row['due_date']     = None
    row['ext_inv_ref']  = None
    row['_edge_case']   = 'UNAPPLIED_RECEIPT_SEQ18'
    return row


def make_open_trans_edge_cases(client: str, customer_ids: list,
                                inactive_id: str, ghost_id: str,
                                existing_vouchers: list) -> list:
    cases = []

    def vno():
        return voucher_no('AR')

    def ec(base_id, overrides, label):
        row = make_clean_open_trans(client, base_id, vno())
        row.update(overrides)
        row['_edge_case'] = label
        return row

    ref_id = random.choice(customer_ids)

    # Completeness
    cases.append(ec(ref_id, {'due_date': None},       'AR_DUE_DATE_MISSING'))
    cases.append(ec(ref_id, {'ext_inv_ref': None},    'AR_EXT_REF_MISSING'))
    cases.append(ec(ref_id, {'amount': None},         'AR_AMOUNT_MISSING'))
    cases.append(ec(ref_id, {'order_id': None, 'contract_id': None}, 'AR_PO_CONTRACT_MISSING'))
    cases.append(ec(ref_id, {'currency': 'USD', 'exch_rate': None, 'cur_amount': 1200.0},
                             'AR_FX_NO_RATE'))

    cn_no_ref = make_clean_open_trans(client, ref_id, vno())
    cn_no_ref['voucher_type']   = random.choice(VOUCHER_TYPES_CN)
    cn_no_ref['amount']         = -round(random.uniform(100, 2000), 2)
    cn_no_ref['rest_amount']    = cn_no_ref['amount']
    cn_no_ref['orig_reference'] = None
    cn_no_ref['_edge_case']     = 'AR_CN_NO_REF'
    cases.append(cn_no_ref)

    # Validity
    cases.append(ec(ref_id, {'amount': -1500.0, 'voucher_type': 'SINV'}, 'AR_NEG_INV'))
    cases.append(ec(ref_id, {'currency': 'EUR', 'cur_amount': None, 'exch_rate': 1.17},
                             'AR_FX_NO_CUR_AMT'))

    # Consistency
    cases.append(ec(ref_id, {'rest_amount': 0.0}, 'AR_REST_ZERO'))
    cases.append(ec(ref_id, {'amount': 1000.0, 'rest_amount': 1500.0}, 'AR_REST_OVER_AMT'))

    overdue = make_clean_open_trans(client, ref_id, vno())
    overdue['due_date']    = (TODAY - timedelta(days=random.randint(45, 180))).isoformat()
    overdue['rest_amount'] = round(random.uniform(500, 20000), 2)
    overdue['_edge_case']  = 'AR_OVERDUE'
    cases.append(overdue)

    cases.append(ec(ref_id, {'wf_state': 'W'}, 'AR_WF_STUCK'))

    # Duplicate ext_inv_ref for same customer
    dup_ref = f"INV{random.randint(10000,99999)}"
    for _ in range(2):
        row = make_clean_open_trans(client, ref_id, vno())
        row['ext_inv_ref'] = dup_ref
        row['_edge_case']  = 'AR_EXT_REF_DUP'
        cases.append(row)

    # Net negative balance for one customer (credits outweigh invoices)
    neg_id = random.choice(customer_ids)
    for _ in range(2):
        cn = make_clean_open_trans(client, neg_id, vno())
        cn['voucher_type']   = random.choice(VOUCHER_TYPES_CN)
        cn['amount']         = -round(random.uniform(5000, 15000), 2)
        cn['rest_amount']    = cn['amount']
        cn['orig_reference'] = random.choice(existing_vouchers) if existing_vouchers else None
        cn['_edge_case']     = 'AR_NET_NEGATIVE_CUST'
        cases.append(cn)

    # Orphaned credit note — orig_reference points to a closed (non-existent in extract) invoice
    orphan_cn = make_clean_open_trans(client, ref_id, vno())
    orphan_cn['voucher_type']   = random.choice(VOUCHER_TYPES_CN)
    orphan_cn['amount']         = -round(random.uniform(100, 500), 2)
    orphan_cn['rest_amount']    = orphan_cn['amount']
    orphan_cn['orig_reference'] = 'ARXXXXXXCLOSED'   # will not match any voucher_no in extract
    orphan_cn['_edge_case']     = 'AR_ORPHANED_CREDITS'
    cases.append(orphan_cn)

    # Collection / high reminder
    cases.append(ec(ref_id, {'collect_status': 'REFERRED', 'collect_agency': 'DEBTCO'},
                             'AR_IN_COLLECTION'))
    cases.append(ec(ref_id, {'rem_level': 4}, 'AR_HIGH_REMINDER'))

    # Referential integrity
    cases.append(ec(ghost_id,    {}, 'AR_ORPHANED_TRANS'))           # apar_id not in master at all
    cases.append(ec(inactive_id, {}, 'AR_TRANS_CUST_CLOSED'))        # apar_id exists but status=C

    return cases


def build_customer_open_trans(client: str, master_df: pd.DataFrame, n_clean: int = 100):
    active_ids   = master_df[master_df['status'] == 'N']['apar_id'].tolist()
    inactive_row = master_df[master_df['_edge_case'] == 'CUST_INACTIVE_FOR_TRANS_JOIN']
    inactive_id  = inactive_row['apar_id'].iloc[0] if not inactive_row.empty else active_ids[0]
    ghost_id     = 'CGHOST9999'  # never appears in master

    clean = []
    for _ in range(n_clean):
        cust = random.choice(active_ids)
        clean.append(make_clean_open_trans(client, cust, voucher_no('AR')))

    # Add a handful of Seq 18 unapplied receipts
    for _ in range(8):
        cust = random.choice(active_ids)
        clean.append(make_unapplied_receipt(client, cust, voucher_no('AR')))

    existing_vouchers = [r['voucher_no'] for r in clean]
    edges = make_open_trans_edge_cases(client, active_ids, inactive_id, ghost_id, existing_vouchers)

    return pd.DataFrame(clean + edges)


# ──────────────────────────────────────────────────────────────────────────────
# CUSTOMER HISTORY  (acuhistr)
# ──────────────────────────────────────────────────────────────────────────────

def make_clean_history(client: str, apar_id: str, vno: str) -> dict:
    trans_date = rand_date(EIGHTEEN_MONTHS_AGO, TODAY - timedelta(days=30))
    amount     = round(random.uniform(200, 30000), 2)

    return {
        'client':         client,
        'apar_id':        apar_id,
        'voucher_no':     vno,
        'sequence_no':    1,
        'voucher_type':   random.choice(VOUCHER_TYPES_INV),
        'voucher_date':   trans_date.isoformat(),
        'trans_date':     trans_date.isoformat(),
        'status':         'C',
        'amount':         amount,
        'rest_amount':    0.0,
        'currency':       'GBP',
        'orig_reference': None,
        '_edge_case':     None,
    }


def make_history_edge_cases(client: str, customer_ids: list, ghost_id: str) -> list:
    cases = []
    ref_id = random.choice(customer_ids)

    def vno():
        return voucher_no('ARH')

    # Consistency — non-zero rest_amount on a closed transaction
    row = make_clean_history(client, ref_id, vno())
    row['rest_amount'] = round(random.uniform(0.01, 500), 2)
    row['_edge_case']  = 'HIS_REST_NOT_ZERO'
    cases.append(row)

    # Completeness — missing trans_date
    row2 = make_clean_history(client, ref_id, vno())
    row2['trans_date'] = None
    row2['_edge_case'] = 'HIS_DATE_MISSING'
    cases.append(row2)

    # Completeness — credit note missing orig_reference
    cn = make_clean_history(client, ref_id, vno())
    cn['voucher_type']   = random.choice(VOUCHER_TYPES_CN)
    cn['amount']         = -round(random.uniform(100, 1000), 2)
    cn['rest_amount']    = 0.0
    cn['orig_reference'] = None
    cn['_edge_case']     = 'HIS_CN_NO_REF'
    cases.append(cn)

    # Uniqueness — duplicate voucher_no + sequence_no
    dup_vno = vno()
    for _ in range(2):
        row = make_clean_history(client, ref_id, dup_vno)
        row['sequence_no'] = 1
        row['_edge_case']  = 'HIS_DUP'
        cases.append(row)

    # Referential integrity — apar_id not in master
    ghost = make_clean_history(client, ghost_id, vno())
    ghost['_edge_case'] = 'HIS_ORPHANED'
    cases.append(ghost)

    return cases


def build_customer_history(client: str, master_df: pd.DataFrame, n_clean: int = 120):
    active_ids = master_df[master_df['status'] == 'N']['apar_id'].tolist()
    ghost_id   = 'CGHOST9999'

    clean = []
    for _ in range(n_clean):
        cust = random.choice(active_ids)
        clean.append(make_clean_history(client, cust, voucher_no('ARH')))

    edges = make_history_edge_cases(client, active_ids, ghost_id)
    return pd.DataFrame(clean + edges)


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    print("Generating AR dummy data...\n")

    for client in [HOC, HOL]:
        print(f"  [{client}] Building customer master (acuheader)...")
        master = build_customer_master(client, n_clean=60)
        path = os.path.join(OUTPUT_DIR, f"customer_master_{client}.csv")
        master.to_csv(path, index=False)
        print(f"         -> {len(master)} rows  ({master['_edge_case'].notna().sum()} edge cases)  {path}")

        print(f"  [{client}] Building open transactions (acutrans)...")
        open_trans = build_customer_open_trans(client, master, n_clean=100)
        path = os.path.join(OUTPUT_DIR, f"customer_open_trans_{client}.csv")
        open_trans.to_csv(path, index=False)
        print(f"         -> {len(open_trans)} rows  ({open_trans['_edge_case'].notna().sum()} edge cases)  {path}")

        print(f"  [{client}] Building history (acuhistr)...")
        history = build_customer_history(client, master, n_clean=120)
        path = os.path.join(OUTPUT_DIR, f"customer_history_{client}.csv")
        history.to_csv(path, index=False)
        print(f"         -> {len(history)} rows  ({history['_edge_case'].notna().sum()} edge cases)  {path}")

        print()

    print("Done. Files written to ./data/")
    print()
    print("Edge cases embedded per file:")
    print("  customer_master      — CUST_VAT_MISSING, CUST_COMP_REG_MISSING, CUST_TERMS_MISSING,")
    print("                         CUST_PAY_METHOD_MISSING, CUST_CURRENCY_MISSING,")
    print("                         CUST_CREDIT_LIMIT_NULL, CUST_CREDIT_LIMIT_ZERO,")
    print("                         CUST_INTRULE_MISSING, CUST_VAT_FORMAT, CUST_COMP_REG_FORMAT,")
    print("                         CUST_SORT_FORMAT, CUST_BANK_FORMAT, CUST_SWIFT_FORMAT,")
    print("                         CUST_EXPIRED_ACTIVE, CUST_WF_STUCK, CUST_COLLECT_FLAG,")
    print("                         CUST_DD_NO_BANK, CUST_SUBSIDIARY, CUST_NAME_DUP,")
    print("                         CUST_VAT_DUP, CUST_SUNDRY, CUST_STALE,")
    print("                         CUST_INACTIVE_FOR_TRANS_JOIN")
    print()
    print("  customer_open_trans  — AR_DUE_DATE_MISSING, AR_EXT_REF_MISSING, AR_AMOUNT_MISSING,")
    print("                         AR_PO_CONTRACT_MISSING, AR_FX_NO_RATE, AR_CN_NO_REF,")
    print("                         AR_NEG_INV, AR_FX_NO_CUR_AMT, AR_REST_ZERO,")
    print("                         AR_REST_OVER_AMT, AR_OVERDUE, AR_WF_STUCK,")
    print("                         AR_EXT_REF_DUP, AR_NET_NEGATIVE_CUST,")
    print("                         AR_ORPHANED_CREDITS, AR_IN_COLLECTION, AR_HIGH_REMINDER,")
    print("                         AR_ORPHANED_TRANS, AR_TRANS_CUST_CLOSED,")
    print("                         UNAPPLIED_RECEIPT_SEQ18")
    print()
    print("  customer_history     — HIS_REST_NOT_ZERO, HIS_DATE_MISSING, HIS_CN_NO_REF,")
    print("                         HIS_DUP, HIS_ORPHANED")


if __name__ == '__main__':
    main()