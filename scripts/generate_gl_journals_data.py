"""
Parliament Finance Systems Programme
GL Journals Dummy Data Generator
=================================
Generates two CSVs mirroring the exact shape of the GL Journals SQL extract
(agltransact, Seq 20 — Current Year Journals):

  data/gl_journals_HOC.csv
  data/gl_journals_HOL.csv

Column order matches the SELECT in sql/gl_journals.sql exactly.
house column is added in Python after load (not in SQL output).

Contains 150 baseline rows (HOC) / 75 baseline rows (HOL) of clean data,
followed by hardcoded edge-case rows that each trigger a specific DQ test.
"""

import os
import random
from datetime import timedelta, date

import pandas as pd
from faker import Faker

fake = Faker('en_GB')
random.seed(42)
Faker.seed(42)

OUTPUT_DIR = 'data'
os.makedirs(OUTPUT_DIR, exist_ok=True)

TODAY = date.today()
FISCAL_YEAR = 2026

HOC_CLIENTS = ['CA', 'CF', 'CM']
HOL_CLIENTS = ['LA']

# Realistic GL account codes (4-6 digits)
ACCOUNTS = [
    '1000', '1010', '1100', '1200',
    '2000', '2100', '2200',
    '3000', '3100',
    '4000', '4010', '4100', '4200',
    '5001', '5010', '5100', '5200',
    '6000', '6010', '6100',
    '7000', '7010', '7100',
    '8000', '8010',
]

COST_CENTRES = ['CC100', 'CC101', 'CC110', 'CC120', 'CC121', 'CC200', 'CC201', 'CC210']
SUBJECTIVES  = ['S101', 'S102', 'S103', 'S110', 'S123', 'S200', 'S210', 'S301']
VOUCHER_TYPES = ['BACS', 'JRNL', 'ACCRUAL', 'REVERSAL', 'APINV']
USERS = ['jsmith', 'abrown', 'mjones', 'kpatel', 'swilliams', 'dbaker', 'lthomas']

# Baseline date window: full calendar 2026 up to yesterday (avoids triggering DQ-GJ-V02)
BASELINE_DATE_START = date(2026, 1, 1)
BASELINE_DATE_END   = TODAY - timedelta(days=1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def rand_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, max(delta, 0)))


def to_period(d: date) -> int:
    """Return YYYYPP integer from a date, e.g. 202603 for March 2026."""
    return int(f"{d.year}{d.month:02d}")


def split_amount(total: float, n: int) -> list:
    """Split total into n positive parts that sum exactly to total."""
    if n == 1:
        return [round(total, 2)]
    cuts = sorted(random.uniform(1.0, total - 1.0) for _ in range(n - 1))
    parts = []
    prev = 0.0
    for c in cuts:
        parts.append(round(c - prev, 2))
        prev = c
    parts.append(round(total - prev, 2))
    # Correct any floating-point drift
    drift = round(total - sum(parts), 2)
    parts[-1] = round(parts[-1] + drift, 2)
    return parts


def make_journal_row(
    client, house, voucher_no, sequence_no, account,
    trans_date, voucher_date, voucher_type, amount,
    update_flag, currency='GBP', cur_amount=None,
    apar_id=None, apar_type=None,
    tax_code=None, tax_system=None,
    description=None, ext_inv_ref=None,
    dim_1=None, dim_2=None,
    dim_3=None, dim_4=None, dim_5=None, dim_6=None, dim_7=None,
    user_id=None, last_update=None, status='',
    edge_case=None,
) -> dict:
    """Assemble a single agltransact row dict."""
    return {
        'client':       client,
        'house':        house,
        'voucher_no':   voucher_no,
        'sequence_no':  sequence_no,
        'account':      account,
        'fiscal_year':  FISCAL_YEAR,
        'period':       to_period(trans_date) if trans_date else None,
        'trans_date':   trans_date.isoformat() if trans_date else None,
        'voucher_date': voucher_date.isoformat() if voucher_date else None,
        'voucher_type': voucher_type,
        'amount':       amount,
        'cur_amount':   cur_amount,
        'currency':     currency,
        # dc_flag convention unconfirmed by Parliament — mirroring update_flag for now.
        # Do not use dc_flag in balance logic until confirmed with Rod/Dan.
        'dc_flag':      update_flag,
        'update_flag':  update_flag,
        'status':       status,
        'apar_id':      apar_id,
        'apar_type':    apar_type,
        'tax_code':     tax_code,
        'tax_system':   tax_system,
        'description':  description if description is not None else fake.sentence(nb_words=6),
        'ext_inv_ref':  ext_inv_ref,
        'dim_1':        dim_1 or random.choice(COST_CENTRES),
        'dim_2':        dim_2 or random.choice(SUBJECTIVES),
        'dim_3':        dim_3,
        'dim_4':        dim_4,
        'dim_5':        dim_5,
        'dim_6':        dim_6,
        'dim_7':        dim_7,
        'last_update':  (last_update or rand_date(BASELINE_DATE_START, TODAY)).isoformat(),
        'user_id':      user_id or random.choice(USERS),
        '_edge_case':   edge_case,
    }


# ---------------------------------------------------------------------------
# Baseline voucher generation
# ---------------------------------------------------------------------------

def generate_baseline(house: str, clients: list, target_rows: int) -> list:
    """
    Generate balanced journal vouchers totalling approximately target_rows lines.
    Each voucher has 3-6 lines. Debits must equal credits per voucher.
    update_flag 1 = Debit, 2 = Credit. amount is always positive.
    """
    rows = []
    voucher_counter = 1

    while len(rows) < target_rows:
        client       = random.choice(clients)
        voucher_no   = f"V{house}{voucher_counter:05d}"
        voucher_counter += 1
        voucher_type = random.choice(VOUCHER_TYPES)
        user         = random.choice(USERS)

        # Pick line count — ensure even split is possible
        n_debit  = random.randint(1, 3)
        n_credit = random.randint(1, 3)
        total    = round(random.uniform(500.0, 50000.0), 2)

        debit_amounts  = split_amount(total, n_debit)
        credit_amounts = split_amount(total, n_credit)

        trans_date   = rand_date(BASELINE_DATE_START, BASELINE_DATE_END)
        voucher_date = trans_date + timedelta(days=random.randint(0, 3))

        currency   = random.choices(['GBP', 'EUR', 'USD'], weights=[0.95, 0.025, 0.025])[0]
        dim_3_val  = f"PROJ{random.randint(100, 999)}" if random.random() < 0.15 else None

        seq = 1
        all_lines = [(a, 1) for a in debit_amounts] + [(a, 2) for a in credit_amounts]

        for amt, flag in all_lines:
            # 10% chance of sub-ledger reference
            if random.random() < 0.10:
                apar_type = random.choice(['P', 'R'])
                apar_id   = f"{'SUPP' if apar_type == 'P' else 'CUST'}{random.randint(1000, 9999)}"
                ext_ref   = f"INV{random.randint(10000, 99999)}" if random.random() < 0.5 else None
            else:
                apar_type = apar_id = ext_ref = None

            cur_amount = round(amt * random.uniform(1.10, 1.35), 2) if currency != 'GBP' else None

            rows.append(make_journal_row(
                client=client, house=house,
                voucher_no=voucher_no, sequence_no=seq,
                account=random.choice(ACCOUNTS),
                trans_date=trans_date, voucher_date=voucher_date,
                voucher_type=voucher_type,
                amount=amt, update_flag=flag,
                currency=currency, cur_amount=cur_amount,
                apar_id=apar_id, apar_type=apar_type,
                ext_inv_ref=ext_ref,
                dim_3=dim_3_val,
                user_id=user,
            ))
            seq += 1

    return rows


# ---------------------------------------------------------------------------
# Edge case rows
# ---------------------------------------------------------------------------

def edge_row(base: dict, overrides: dict, edge_case_id: str) -> dict:
    """Clone base row, apply overrides, tag with edge_case ID."""
    row = dict(base)
    row.update(overrides)
    row['_edge_case'] = edge_case_id
    return row


def build_edge_cases(house: str, client: str, baseline_rows: list) -> list:
    """Return a list of edge-case rows, one per DQ test ID."""
    edges = []

    # Use the first baseline row as a convenient base template
    base = dict(baseline_rows[0])
    base['house'] = house

    def next_voucher(suffix):
        return f"V{house}_EC_{suffix}"

    def row(suffix, overrides, dq_id):
        r = dict(base)
        r['client']      = client
        r['voucher_no']  = next_voucher(suffix)
        r['sequence_no'] = 1
        r['update_flag'] = 1
        r['dc_flag']     = 1
        r['amount']      = 1000.00
        r['currency']    = 'GBP'
        r['cur_amount']  = None
        r['apar_id']     = None
        r['apar_type']   = None
        r['tax_code']    = None
        r['tax_system']  = None
        r['description'] = 'Edge case row'
        r['ext_inv_ref'] = None
        r['_edge_case']  = dq_id
        r.update(overrides)
        return r

    # ------------------------------------------------------------------
    # COMPLETENESS
    # ------------------------------------------------------------------

    # DQ-GJ-C01: voucher_no is null
    edges.append(row('C01', {'voucher_no': None}, 'DQ-GJ-C01'))

    # DQ-GJ-C02: account is null
    edges.append(row('C02', {'account': None}, 'DQ-GJ-C02'))

    # DQ-GJ-C03: amount is null
    edges.append(row('C03', {'amount': None}, 'DQ-GJ-C03'))

    # DQ-GJ-C04: trans_date is null (period must also be set manually)
    r = row('C04', {
        'trans_date': None,
        'period': 202601,
        'voucher_date': date(2026, 1, 15).isoformat(),
    }, 'DQ-GJ-C04')
    edges.append(r)

    # DQ-GJ-C05: voucher_date is null
    edges.append(row('C05', {
        'trans_date': date(2026, 2, 10).isoformat(),
        'period': 202602,
        'voucher_date': None,
    }, 'DQ-GJ-C05'))

    # DQ-GJ-C07: description is null, voucher_type = JRNL
    edges.append(row('C07', {
        'trans_date': date(2026, 1, 20).isoformat(),
        'period': 202601,
        'voucher_date': date(2026, 1, 21).isoformat(),
        'voucher_type': 'JRNL',
        'description': None,
    }, 'DQ-GJ-C07'))

    # ------------------------------------------------------------------
    # VALIDITY
    # ------------------------------------------------------------------

    # DQ-GJ-V01: update_flag = 9 (invalid — not 1 or 2)
    edges.append(row('V01', {
        'trans_date': date(2026, 1, 15).isoformat(),
        'period': 202601,
        'voucher_date': date(2026, 1, 15).isoformat(),
        'update_flag': 9,
        'dc_flag': 9,
    }, 'DQ-GJ-V01'))

    # DQ-GJ-V02: trans_date is in the future
    future_date = TODAY + timedelta(days=30)
    edges.append(row('V02', {
        'trans_date': future_date.isoformat(),
        'voucher_date': future_date.isoformat(),
        'period': to_period(future_date),
    }, 'DQ-GJ-V02'))

    # DQ-GJ-V04: voucher_date differs from trans_date by more than 60 days
    td = date(2026, 1, 10)
    vd = td + timedelta(days=75)
    edges.append(row('V04', {
        'trans_date': td.isoformat(),
        'period': to_period(td),
        'voucher_date': vd.isoformat(),
    }, 'DQ-GJ-V04'))

    # DQ-GJ-V06: currency = EUR, cur_amount is null
    edges.append(row('V06', {
        'trans_date': date(2026, 2, 5).isoformat(),
        'period': 202602,
        'voucher_date': date(2026, 2, 5).isoformat(),
        'currency': 'EUR',
        'cur_amount': None,
    }, 'DQ-GJ-V06'))

    # ------------------------------------------------------------------
    # CONSISTENCY
    # ------------------------------------------------------------------

    # DQ-GJ-K01: unbalanced voucher — net difference ~500.00
    # Unique voucher_no so the balance check can isolate it.
    # Two debit lines totalling 1500.00, one credit line of 1000.00 → net +500.00
    k01_voucher = f"V{house}_UNBAL01"
    td_k01 = date(2026, 2, 20)
    for seq, amt, flag in [(1, 750.00, 1), (2, 750.00, 1), (3, 1000.00, 2)]:
        edges.append({
            'client':       client,
            'house':        house,
            'voucher_no':   k01_voucher,
            'sequence_no':  seq,
            'account':      random.choice(ACCOUNTS),
            'fiscal_year':  FISCAL_YEAR,
            'period':       to_period(td_k01),
            'trans_date':   td_k01.isoformat(),
            'voucher_date': td_k01.isoformat(),
            'voucher_type': 'JRNL',
            'amount':       amt,
            'cur_amount':   None,
            'currency':     'GBP',
            'dc_flag':      flag,
            'update_flag':  flag,
            'status':       '',
            'apar_id':      None,
            'apar_type':    None,
            'tax_code':     None,
            'tax_system':   None,
            'description':  'Unbalanced voucher edge case',
            'ext_inv_ref':  None,
            'dim_1':        'CC100',
            'dim_2':        'S101',
            'dim_3':        None,
            'dim_4':        None,
            'dim_5':        None,
            'dim_6':        None,
            'dim_7':        None,
            'last_update':  td_k01.isoformat(),
            'user_id':      'jsmith',
            '_edge_case':   'DQ-GJ-K01',
        })

    # DQ-GJ-K02: trans_date falls in period 202603 but period field = 202605
    td_k02 = date(2026, 3, 15)   # → natural period 202603
    edges.append(row('K02', {
        'trans_date': td_k02.isoformat(),
        'voucher_date': td_k02.isoformat(),
        'period': 202605,          # deliberately wrong period
    }, 'DQ-GJ-K02'))

    # DQ-GJ-K03: apar_id populated but apar_type is null
    edges.append(row('K03', {
        'trans_date': date(2026, 1, 25).isoformat(),
        'period': 202601,
        'voucher_date': date(2026, 1, 25).isoformat(),
        'apar_id': 'SUPP9999',
        'apar_type': None,
    }, 'DQ-GJ-K03'))

    # ------------------------------------------------------------------
    # DUPLICATES
    # ------------------------------------------------------------------

    # DQ-GJ-D01: duplicate (client, voucher_no, sequence_no) — repeat first baseline row exactly
    dup = dict(baseline_rows[0])
    dup['_edge_case'] = 'DQ-GJ-D01'
    edges.append(dup)

    # ------------------------------------------------------------------
    # SCOPE
    # ------------------------------------------------------------------

    # DQ-GJ-S02: two journal lines in period 202613 (year-end adjustment period)
    for seq in (1, 2):
        edges.append({
            'client':       client,
            'house':        house,
            'voucher_no':   f"V{house}_YE13",
            'sequence_no':  seq,
            'account':      random.choice(ACCOUNTS),
            'fiscal_year':  FISCAL_YEAR,
            'period':       202613,
            'trans_date':   date(2026, 3, 31).isoformat(),
            'voucher_date': date(2026, 3, 31).isoformat(),
            'voucher_type': 'ACCRUAL',
            'amount':       round(random.uniform(1000.0, 5000.0), 2),
            'cur_amount':   None,
            'currency':     'GBP',
            'dc_flag':      seq,          # line 1 debit, line 2 credit
            'update_flag':  seq,
            'status':       '',
            'apar_id':      None,
            'apar_type':    None,
            'tax_code':     None,
            'tax_system':   None,
            'description':  'Year-end adjustment period 13',
            'ext_inv_ref':  None,
            'dim_1':        'CC100',
            'dim_2':        'S101',
            'dim_3':        None,
            'dim_4':        None,
            'dim_5':        None,
            'dim_6':        None,
            'dim_7':        None,
            'last_update':  date(2026, 3, 31).isoformat(),
            'user_id':      'jsmith',
            '_edge_case':   'DQ-GJ-S02',
        })

    return edges


# ---------------------------------------------------------------------------
# Column ordering — matches SELECT in gl_journals.sql exactly, plus house
# ---------------------------------------------------------------------------

COLS = [
    'client', 'house', 'voucher_no', 'sequence_no', 'account',
    'fiscal_year', 'period', 'trans_date', 'voucher_date', 'voucher_type',
    'amount', 'cur_amount', 'currency', 'dc_flag', 'update_flag', 'status',
    'apar_id', 'apar_type', 'tax_code', 'tax_system', 'description',
    'ext_inv_ref', 'dim_1', 'dim_2', 'dim_3', 'dim_4', 'dim_5', 'dim_6',
    'dim_7', 'last_update', 'user_id', '_edge_case',
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate_house(house: str, clients: list, n_baseline: int):
    print(f"[{house}] Generating {n_baseline} baseline rows...")
    baseline = generate_baseline(house, clients, n_baseline)
    edges    = build_edge_cases(house, clients[0], baseline)
    all_rows = baseline + edges

    df = pd.DataFrame(all_rows)[COLS]
    out_path = os.path.join(OUTPUT_DIR, f"gl_journals_{house}.csv")
    df.to_csv(out_path, index=False)

    edge_count = sum(1 for r in all_rows if r.get('_edge_case'))
    print(f"  -> {len(baseline):4d} baseline rows")
    print(f"  -> {edge_count:4d} edge-case rows")
    print(f"  -> {len(df):4d} total rows written to {out_path}")
    return df


def main():
    print("=" * 60)
    print("GL Journals Dummy Data Generator")
    print("=" * 60)

    df_hoc = generate_house('HOC', HOC_CLIENTS, 150)
    df_hol = generate_house('HOL', HOL_CLIENTS, 75)

    total_rows = len(df_hoc) + len(df_hol)
    print()
    print(f"Done. {total_rows} total rows written to ./{OUTPUT_DIR}/")
    print("=" * 60)


if __name__ == '__main__':
    main()
