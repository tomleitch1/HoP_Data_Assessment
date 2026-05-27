"""
Parliament Finance Systems Programme
AP Supplier Dummy Data Generator
=================================
Generates six CSVs mirroring the shape of the three AP SQL extract outputs,
split by house (HOC / HOL):

  - supplier_master_HOC.csv     / supplier_master_HOL.csv     (asuheader)
  - supplier_open_trans_HOC.csv / supplier_open_trans_HOL.csv (asutrans)
  - supplier_history_HOC.csv    / supplier_history_HOL.csv    (asuhistr)

The 'client' column contains internal Unit4 client codes — NOT 'HOC'/'HOL'.
House is determined by which file the record comes from; data_engine.py
assigns the 'house' column from the filename suffix.

Run:  python scripts/generate_ap_dummy_data.py
Output: ./data/ directory
"""

import os
import random
from datetime import datetime, timedelta, date

import pandas as pd
from faker import Faker

fake = Faker('en_GB')
random.seed(42)
Faker.seed(42)

OUTPUT_DIR = os.path.join('data', 'suppliers')
os.makedirs(OUTPUT_DIR, exist_ok=True)

TODAY = date.today()
THREE_YEARS_AGO   = TODAY - timedelta(days=3 * 365)
EIGHTEEN_MONTHS_AGO = TODAY - timedelta(days=548)

# Internal Unit4 client codes — placeholders until Parliament confirms actual values.
# These are NOT 'HOC'/'HOL'; they are system-level client identifiers within Unit4.
HOC_CLIENT_CODE = 'CA'
HOL_CLIENT_CODE = 'LA'

STATUSES      = ['N', 'C', 'P', 'T']
CURRENCIES    = ['GBP', 'USD', 'EUR']
PAY_METHODS   = ['BACS', 'CHAPS', 'INT', 'CHQ']
TERMS         = ['30DAYS', '14DAYS', '60DAYS', 'COD']
SUP_GROUPS    = ['UTIL', 'GEN', 'CONS', 'IT', 'PROF']
VOUCHER_TYPES = ['INVOICE', 'CREDIT', 'PAYMENT']
TAX_CODES     = ['S20', 'EX', 'Z0']


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

def voucher_no(prefix='AP', n=6) -> str:
    return f"{prefix}{random.randint(10**(n-1), 10**n - 1)}"


# ──────────────────────────────────────────────────────────────────────────────
# SUPPLIER MASTER  (asuheader)
# ──────────────────────────────────────────────────────────────────────────────

def make_clean_supplier(client_code: str, apar_id: str) -> dict:
    pay_method = random.choice(PAY_METHODS)
    has_bacs   = pay_method in ('BACS', 'CHAPS')
    has_int    = pay_method == 'INT'

    return {
        'client':       client_code,
        'apar_id':      apar_id,
        'apar_name':    fake.company(),
        'short_name':   fake.company()[:10],
        'apar_gr_id':   random.choice(SUP_GROUPS),
        'status':       'N',
        'apar_once':    'N',
        'vat_reg_no':   fmt_vat(),
        'comp_reg_no':  fmt_comp_reg(),
        'country_code': 'GB',
        'tax_code':     random.choice(TAX_CODES),
        'tax_system':   'UKVAT',
        'terms_id':     random.choice(TERMS),
        'pay_method':   pay_method,
        'currency':     'GBP',
        'pay_delay':    random.choice([0, 0, 0, 5, 10]),
        'clearing_code': fmt_sort_code() if has_bacs else None,
        'bank_account':  fmt_account()   if has_bacs else None,
        'iban':          fmt_iban()       if has_int  else None,
        'swift':         fmt_swift()      if has_int  else None,
        'address':       fake.street_address(),
        'place':         fake.city(),
        'zip_code':      fake.postcode(),
        'province':      fake.county(),
        'expired_date':  None,
        'last_update':   rand_date(date(2021, 1, 1), TODAY).isoformat(),
        'wf_state':      'T',
        '_edge_case':    None,
    }


def make_supplier_edge_cases(client_code: str, start_id: int) -> tuple:
    cases = []
    i = start_id

    def ec(overrides: dict, label: str) -> dict:
        nonlocal i
        base = make_clean_supplier(client_code, f"SUP{i:04d}")
        base.update(overrides)
        base['_edge_case'] = label
        i += 1
        return base

    # Completeness
    cases.append(ec({'address': None},                       'SUP_ADDR_MISSING'))
    cases.append(ec({'place': None},                         'SUP_PLACE_MISSING'))
    cases.append(ec({'zip_code': None},                      'SUP_ZIP_MISSING'))
    cases.append(ec({'province': None},                      'SUP_PROVINCE_MISSING'))
    cases.append(ec({'zip_code': 'INVALID99', 'country_code': 'GB'}, 'SUP_ZIP_FORMAT'))
    cases.append(ec({'vat_reg_no': None},                   'SUP_VAT_MISSING'))
    cases.append(ec({'pay_method': None, 'clearing_code': None, 'bank_account': None}, 'SUP_PAY_METHOD_MISSING'))
    cases.append(ec({'clearing_code': None, 'bank_account': None, 'iban': None,
                     'pay_method': 'BACS'},                 'SUP_BANK_MISSING'))
    cases.append(ec({'terms_id': None},                     'SUP_TERMS_MISSING'))
    cases.append(ec({'currency': None},                     'SUP_CURRENCY_MISSING'))

    # Validity
    cases.append(ec({'vat_reg_no': '12345INVALID'},         'SUP_VAT_FORMAT'))
    cases.append(ec({'clearing_code': '123456',
                     'bank_account': fmt_account(),
                     'pay_method': 'BACS'},                 'SUP_SORT_FORMAT'))
    cases.append(ec({'swift': 'TOOSHORT',
                     'iban': fmt_iban(),
                     'pay_method': 'INT'},                  'SUP_SWIFT_FORMAT'))

    # Consistency
    cases.append(ec({'expired_date': rand_date(date(2022,1,1), date(2023,12,31)).isoformat(),
                     'status': 'N'},                        'SUP_EXPIRED_ACTIVE'))
    cases.append(ec({'wf_state': 'W'},                      'SUP_WF_STUCK'))
    cases.append(ec({'apar_once': 'Y'},                     'SUP_SUNDRY'))
    cases.append(ec({'last_update': (TODAY - timedelta(days=4*365)).isoformat()},
                                                            'SUP_STALE'))
    cases.append(ec({'pay_method': 'BACS',
                     'clearing_code': None,
                     'bank_account': None},                 'SUP_BACS_NO_BANK'))

    # Duplicate VAT — wired up after clean list is assembled
    dup_vat = make_clean_supplier(client_code, f"SUP{i:04d}")
    dup_vat['_edge_case'] = 'SUP_VAT_DUP'
    cases.append(dup_vat)
    i += 1

    # Inactive record kept for referential integrity join tests
    inactive = make_clean_supplier(client_code, f"SUP{i:04d}")
    inactive['status']       = 'C'
    inactive['expired_date'] = rand_date(date(2020,1,1), date(2022,12,31)).isoformat()
    inactive['_edge_case']   = 'SUP_INACTIVE_FOR_TRANS_JOIN'
    cases.append(inactive)

    return cases, i


def build_supplier_master(client_code: str, n_clean: int = 60) -> pd.DataFrame:
    clean = [make_clean_supplier(client_code, f"SUP{i:04d}") for i in range(1, n_clean + 1)]
    edge_cases, _ = make_supplier_edge_cases(client_code, n_clean + 1)

    dup_vat = next(r for r in edge_cases if r['_edge_case'] == 'SUP_VAT_DUP')
    dup_vat['vat_reg_no'] = clean[0]['vat_reg_no']

    return pd.DataFrame(clean + edge_cases)


# ──────────────────────────────────────────────────────────────────────────────
# SUPPLIER OPEN TRANSACTIONS  (asutrans)
# ──────────────────────────────────────────────────────────────────────────────

def make_clean_open_trans(client_code: str, apar_id: str, vno: str) -> dict:
    trans_date = rand_date(date(2023, 1, 1), TODAY)
    due_date   = trans_date + timedelta(days=random.choice([30, 60, 90]))
    amount     = round(random.uniform(500, 50000), 2)
    paid       = round(random.uniform(0, amount * 0.8), 2)
    rest       = round(amount - paid, 2)

    return {
        'client':         client_code,
        'apar_id':        apar_id,
        'voucher_no':     vno,
        'sequence_no':    1,
        'voucher_type':   'INVOICE',
        'voucher_date':   trans_date.isoformat(),
        'trans_date':     trans_date.isoformat(),
        'due_date':       due_date.isoformat(),
        'description':    fake.sentence(nb_words=6),
        'amount':         amount,
        'cur_amount':     None,
        'currency':       'GBP',
        'rest_amount':    rest,
        'rest_curr':      None,
        'discount':       None,
        'dc_flag':        'D',
        'status':         'N',
        'pay_method':     random.choice(PAY_METHODS),
        'payment_date':   None,
        'pay_flag':       'N',
        'period':         f"{trans_date.year}{trans_date.month:02d}",
        'payperiod':      None,
        'ext_inv_ref':    f"INV-{random.randint(10000,99999)}",
        'orig_reference': None,
        'order_id':       f"PO{random.randint(1000,9999)}",
        'contract_id':    None,
        'tax_code':       random.choice(TAX_CODES),
        'exch_rate':      None,
        'last_update':    TODAY.isoformat(),
        'wf_state':       'T',
        '_edge_case':     None,
    }


def make_open_trans_edge_cases(client_code: str, supplier_ids: list,
                                inactive_id: str, ghost_id: str,
                                existing_vouchers: list) -> list:
    cases = []
    ref_id = random.choice(supplier_ids)

    def vno():
        return voucher_no('AP')

    def ec(base_id, overrides, label):
        row = make_clean_open_trans(client_code, base_id, vno())
        row.update(overrides)
        row['_edge_case'] = label
        return row

    # Completeness
    cases.append(ec(ref_id, {'due_date': None},                         'AP_DUE_DATE_MISSING'))
    cases.append(ec(ref_id, {'ext_inv_ref': None},                      'AP_EXT_REF_MISSING'))
    cases.append(ec(ref_id, {'amount': None},                           'AP_AMOUNT_MISSING'))
    cases.append(ec(ref_id, {'order_id': None, 'contract_id': None},    'AP_PO_CONTRACT_MISSING'))
    cases.append(ec(ref_id, {'currency': 'USD', 'exch_rate': None,
                              'cur_amount': 1200.0},                     'AP_FX_NO_RATE'))

    # Credit note with no orig_reference
    cn = make_clean_open_trans(client_code, ref_id, vno())
    cn['voucher_type']   = 'CREDIT'
    cn['amount']         = -round(random.uniform(100, 2000), 2)
    cn['rest_amount']    = cn['amount']
    cn['orig_reference'] = None
    cn['_edge_case']     = 'AP_CN_NO_REF'
    cases.append(cn)

    # Validity
    cases.append(ec(ref_id, {'amount': -1500.0, 'voucher_type': 'INVOICE'}, 'AP_NEG_INV'))
    cases.append(ec(ref_id, {'currency': 'EUR', 'cur_amount': None,
                              'exch_rate': 1.17},                           'AP_FX_NO_CUR_AMT'))

    # Consistency
    cases.append(ec(ref_id, {'rest_amount': 0.0},                       'AP_REST_ZERO'))
    cases.append(ec(ref_id, {'amount': 1000.0, 'rest_amount': 1500.0},  'AP_REST_OVER_AMT'))
    cases.append(ec(ref_id, {'wf_state': 'W'},                          'AP_WF_STUCK'))

    overdue = make_clean_open_trans(client_code, ref_id, vno())
    overdue['due_date']    = (TODAY - timedelta(days=random.randint(45, 180))).isoformat()
    overdue['rest_amount'] = round(random.uniform(500, 20000), 2)
    overdue['_edge_case']  = 'AP_OVERDUE'
    cases.append(overdue)

    # Duplicate ext_inv_ref for same supplier
    dup_ref = f"INV-{random.randint(10000,99999)}"
    for _ in range(2):
        row = make_clean_open_trans(client_code, ref_id, vno())
        row['ext_inv_ref'] = dup_ref
        row['_edge_case']  = 'AP_EXT_REF_DUP'
        cases.append(row)

    # Referential integrity
    cases.append(ec(ghost_id,    {}, 'AP_ORPHANED_TRANS'))
    cases.append(ec(inactive_id, {}, 'AP_TRANS_SUP_CLOSED'))

    return cases


def build_supplier_open_trans(client_code: str, master_df: pd.DataFrame, n_clean: int = 100) -> pd.DataFrame:
    active_ids   = master_df[master_df['status'] == 'N']['apar_id'].tolist()
    inactive_row = master_df[master_df['_edge_case'] == 'SUP_INACTIVE_FOR_TRANS_JOIN']
    inactive_id  = inactive_row['apar_id'].iloc[0] if not inactive_row.empty else active_ids[0]
    ghost_id     = 'SUPGHOST9999'

    clean = [make_clean_open_trans(client_code, random.choice(active_ids), voucher_no('AP'))
             for _ in range(n_clean)]

    existing_vouchers = [r['voucher_no'] for r in clean]
    edges = make_open_trans_edge_cases(client_code, active_ids, inactive_id, ghost_id, existing_vouchers)

    return pd.DataFrame(clean + edges)


# ──────────────────────────────────────────────────────────────────────────────
# SUPPLIER HISTORY  (asuhistr)
# ──────────────────────────────────────────────────────────────────────────────

def make_clean_history(client_code: str, apar_id: str, vno: str) -> dict:
    trans_date = rand_date(EIGHTEEN_MONTHS_AGO, TODAY - timedelta(days=30))
    amount     = round(random.uniform(200, 30000), 2)

    return {
        'client':         client_code,
        'apar_id':        apar_id,
        'voucher_no':     vno,
        'sequence_no':    1,
        'voucher_type':   'INVOICE',
        'voucher_date':   trans_date.isoformat(),
        'trans_date':     trans_date.isoformat(),
        'status':         'C',
        'amount':         amount,
        'rest_amount':    0.0,
        'currency':       'GBP',
        'orig_reference': None,
        '_edge_case':     None,
    }


def make_history_edge_cases(client_code: str, supplier_ids: list, ghost_id: str) -> list:
    cases = []
    ref_id = random.choice(supplier_ids)

    def vno():
        return voucher_no('APH')

    # Non-zero rest on a closed transaction
    row = make_clean_history(client_code, ref_id, vno())
    row['rest_amount'] = round(random.uniform(0.01, 500), 2)
    row['_edge_case']  = 'HIS_REST_NOT_ZERO'
    cases.append(row)

    # Missing trans_date
    row2 = make_clean_history(client_code, ref_id, vno())
    row2['trans_date'] = None
    row2['_edge_case'] = 'HIS_DATE_MISSING'
    cases.append(row2)

    # Credit note missing orig_reference
    cn = make_clean_history(client_code, ref_id, vno())
    cn['voucher_type']   = 'CREDIT'
    cn['amount']         = -round(random.uniform(100, 1000), 2)
    cn['rest_amount']    = 0.0
    cn['orig_reference'] = None
    cn['_edge_case']     = 'HIS_CN_NO_REF'
    cases.append(cn)

    # Duplicate voucher_no + sequence_no
    dup_vno = vno()
    for _ in range(2):
        row = make_clean_history(client_code, ref_id, dup_vno)
        row['sequence_no'] = 1
        row['_edge_case']  = 'HIS_DUP'
        cases.append(row)

    # Orphaned — apar_id not in master
    ghost = make_clean_history(client_code, ghost_id, vno())
    ghost['_edge_case'] = 'HIS_ORPHANED'
    cases.append(ghost)

    return cases


def build_supplier_history(client_code: str, master_df: pd.DataFrame, n_clean: int = 120) -> pd.DataFrame:
    active_ids = master_df[master_df['status'] == 'N']['apar_id'].tolist()
    ghost_id   = 'SUPGHOST9999'

    clean = [make_clean_history(client_code, random.choice(active_ids), voucher_no('APH'))
             for _ in range(n_clean)]

    edges = make_history_edge_cases(client_code, active_ids, ghost_id)
    return pd.DataFrame(clean + edges)


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    print("Generating AP supplier dummy data...\n")
    print(f"  HOC client code: {HOC_CLIENT_CODE}")
    print(f"  HOL client code: {HOL_CLIENT_CODE}")
    print(f"  (House is assigned by data_engine from filename suffix, not this field)\n")

    for house, client_code in [('HOC', HOC_CLIENT_CODE), ('HOL', HOL_CLIENT_CODE)]:
        print(f"  [{house}] Building supplier master (asuheader)...")
        master = build_supplier_master(client_code, n_clean=60)
        path = os.path.join(OUTPUT_DIR, f"supplier_master_{house}.csv")
        master.to_csv(path, index=False)
        print(f"         -> {len(master)} rows  ({master['_edge_case'].notna().sum()} edge cases)  {path}")

        print(f"  [{house}] Building open transactions (asutrans)...")
        open_trans = build_supplier_open_trans(client_code, master, n_clean=100)
        path = os.path.join(OUTPUT_DIR, f"supplier_open_trans_{house}.csv")
        open_trans.to_csv(path, index=False)
        print(f"         -> {len(open_trans)} rows  ({open_trans['_edge_case'].notna().sum()} edge cases)  {path}")

        print(f"  [{house}] Building history (asuhistr)...")
        history = build_supplier_history(client_code, master, n_clean=120)
        path = os.path.join(OUTPUT_DIR, f"supplier_history_{house}.csv")
        history.to_csv(path, index=False)
        print(f"         -> {len(history)} rows  ({history['_edge_case'].notna().sum()} edge cases)  {path}")

        print()

    print("Done. Files written to ./data/")
    print()
    print("Edge cases per file:")
    print("  supplier_master   — SUP_VAT_MISSING, SUP_PAY_METHOD_MISSING, SUP_BANK_MISSING,")
    print("                      SUP_TERMS_MISSING, SUP_CURRENCY_MISSING, SUP_VAT_FORMAT,")
    print("                      SUP_SORT_FORMAT, SUP_SWIFT_FORMAT, SUP_EXPIRED_ACTIVE,")
    print("                      SUP_WF_STUCK, SUP_SUNDRY, SUP_STALE, SUP_BACS_NO_BANK,")
    print("                      SUP_VAT_DUP, SUP_INACTIVE_FOR_TRANS_JOIN")
    print()
    print("  supplier_open_trans — AP_DUE_DATE_MISSING, AP_EXT_REF_MISSING, AP_AMOUNT_MISSING,")
    print("                        AP_PO_CONTRACT_MISSING, AP_FX_NO_RATE, AP_CN_NO_REF,")
    print("                        AP_NEG_INV, AP_FX_NO_CUR_AMT, AP_REST_ZERO,")
    print("                        AP_REST_OVER_AMT, AP_WF_STUCK, AP_OVERDUE,")
    print("                        AP_EXT_REF_DUP, AP_ORPHANED_TRANS, AP_TRANS_SUP_CLOSED")
    print()
    print("  supplier_history  — HIS_REST_NOT_ZERO, HIS_DATE_MISSING, HIS_CN_NO_REF,")
    print("                      HIS_DUP, HIS_ORPHANED")


if __name__ == '__main__':
    main()
