"""
Parliament Finance Systems Programme
Atamis / Unit4-via-Atamis Dummy Data Generator
================================================
Generates four CSVs mirroring the shape of the real Atamis and Unit4 contract
extracts. Unlike every other domain, these four files are NOT split into
HOC/HOL extracts — each is a single combined file, exactly as saved on the
Parliament laptop:

  - contracts_report.csv            (Atamis — contracts, Organisation = HOC/HOL/Joint)
  - contract_total_commitments.csv  (Unit4 view #1 of contract spend)
  - contracts_spend_details.csv     (Unit4 view #2 of contract spend)
  - supplier_data_report.csv        (Atamis — supplier list, Creditor Ref is the Unit4 join key)

Deliberately injects realistic cross-system mismatches (rather than perfectly
clean linkage) so the DQ checks in atamis_rules.py show non-zero, meaningful
results:
  - Atamis suppliers with no matching Unit4 Creditor Ref
  - Unit4 suppliers never registered in Atamis (natural — Atamis's supplier
    list only covers a subset of the full HOC+HOL supplier master)
  - Contract References with no matching PO (and vice versa is out of scope —
    PO is HoC-only)
  - Contract commitment records referencing a Supplier ID absent from Unit4
  - Spend Details rows with no matching Commitments record
  - Commitments vs Spend Details Posted-amount disagreement on a few contracts
  - A handful of Atamis "sample/test" supplier records, mirroring the real
    Atamis demo rows Parliament's own extract still carries
  - The Spend Details extract's first row is a grand-total summary (blank
    Contract) — reproduced here so the data_engine.py load-time filter that
    drops it is actually exercised

Run:  python scripts/generate_atamis_dummy_data.py
Output: data/atamis/
"""

import os
import random
import pandas as pd
from datetime import date, timedelta
from faker import Faker

fake = Faker('en_GB')
random.seed(42)
Faker.seed(42)

OUTPUT_DIR = os.path.join('data', 'atamis')
os.makedirs(OUTPUT_DIR, exist_ok=True)

TODAY = date.today()


def _dmy(d: date) -> str:
    return d.strftime('%d/%m/%Y')


def _rand_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, max(delta, 1)))


def _gbp(v: float) -> str:
    return f"GBP{v:,.2f}"


def _amt(v: float) -> str:
    return f"{v:,.2f}"


# ── Pull real supplier IDs / names and real PO contract IDs from the other ──
# ── domains' own dummy data, so Atamis links to genuine records rather than ──
# ── an entirely disjoint ID space (the known gap already documented for the ──
# ── PO <-> Suppliers <-> GL dummy generators). ──────────────────────────────

def _load_unit4_suppliers():
    frames = []
    for house, path in [('HOC', 'data/suppliers/supplier_master_HOC.csv'),
                         ('HOL', 'data/suppliers/supplier_master_HOL.csv')]:
        if os.path.exists(path):
            df = pd.read_csv(path, dtype=str)
            df['house'] = house
            frames.append(df[['apar_id', 'apar_name', 'status', 'house']])
    if not frames:
        return pd.DataFrame(columns=['apar_id', 'apar_name', 'status', 'house'])
    return pd.concat(frames, ignore_index=True)


def _load_po_contract_refs():
    path = 'data/po/po_header_HOC.csv'
    if not os.path.exists(path):
        return []
    df = pd.read_csv(path, dtype=str)
    return sorted(df['contract_id'].dropna().unique().tolist())


UNIT4_SUPPLIERS = _load_unit4_suppliers()
PO_CONTRACT_REFS = _load_po_contract_refs()

DEPARTMENTS = [
    'HOC: Strategic Estates', 'HOC: Strategic Estates>Property and Asset Strategy',
    'HOC: Finance Portfolio and Performance', 'HOC: Parliamentary Security Department',
    'HOL: Facilities', 'HOL: Digital Service', 'Joint: Parliamentary Digital Service',
    'Joint: Restoration and Renewal',
]
PCD_BRANCHES = ['Works', 'S&S', 'Goods', 'Services', 'ICT']
FRAMEWORKS = [
    'FWK1128 - Mechanical Electrical Public Health (MEP), Conservation and Minor Work',
    'RM6165 - Construction Professional Services',
    'FWK1121 Programme, Project & Cost Management',
    'RM6229 - Permanent Recruitment 2',
    'Northern Estate Programme Engineering Services',
    '',
]


# ── Atamis Contracts (contracts_report.csv) ─────────────────────────────────

def _gen_contracts(n=90):
    rows = []
    used_refs = set()
    hoc_names = UNIT4_SUPPLIERS[UNIT4_SUPPLIERS['house'] == 'HOC']['apar_name'].dropna().tolist()
    hol_names = UNIT4_SUPPLIERS[UNIT4_SUPPLIERS['house'] == 'HOL']['apar_name'].dropna().tolist()

    for i in range(n):
        org = random.choices(['HOC', 'HOL', 'Joint'], weights=[60, 25, 15])[0]

        # ~60% of HOC/Joint contracts reuse a real PO contract_id (genuine link);
        # HOL contracts never do, since PO is HoC-only and this is not the check's
        # concern; the remaining HOC/Joint share is left unmatched on purpose so
        # ATAMIS_CONTRACT_REF_NOT_IN_PO has real failures to show.
        if org in ('HOC', 'Joint') and PO_CONTRACT_REFS and random.random() < 0.6:
            ref = random.choice(PO_CONTRACT_REFS)
        else:
            ref = f"FWK{random.randint(1000,1199)}-{fake.bothify('??##')}{random.randint(1,9999)}"

        # A handful of deliberately blank refs (MOUs) and deliberate duplicates
        if random.random() < 0.04:
            ref = ''
        elif i > 5 and random.random() < 0.03:
            ref = rows[random.randint(0, len(rows) - 1)]['Contract Reference'] or ref

        supplier = ''
        if random.random() > 0.06:
            pool = hoc_names if org == 'HOC' else (hol_names if org == 'HOL' else hoc_names + hol_names)
            supplier = random.choice(pool) if pool else fake.company().upper()

        start = _rand_date(date(2015, 1, 1), date(2027, 6, 30))
        end = start + timedelta(days=random.randint(180, 1800))
        award_date = start - timedelta(days=random.randint(0, 30))

        # A few deliberately invalid date pairs
        if random.random() < 0.03:
            end = start - timedelta(days=random.randint(1, 60))
        # A few missing dates
        start_out, end_out = _dmy(start), _dmy(end)
        if random.random() < 0.04:
            start_out = ''
        if random.random() < 0.04:
            end_out = ''

        award_val = 0.0 if random.random() < 0.1 else round(random.uniform(2000, 2_500_000), 2)
        current_val = award_val if random.random() > 0.25 else round(award_val * random.uniform(0.8, 1.3), 2)

        org_out = org
        if random.random() < 0.02:
            org_out = random.choice(['hoc', 'HOL ', 'Both', ''])  # a couple of bad Organisation values

        rows.append({
            'ContractTitle': fake.catch_phrase()[:60],
            'Contract Reference': ref,
            'Contract Manager': 'UKParliament Admin',
            'Organisation': org_out,
            'Supplier': supplier,
            'HAIS Product Code(s)': str(random.randint(70000000, 90999999)) + random.choice(['N', 'R']),
            'EPMO Project Name or SE Project Code': '',
            'Department Name': random.choice(DEPARTMENTS),
            'PCD Branch': random.choice(PCD_BRANCHES),
            'Start Date': start_out,
            'End Date': end_out,
            'Contract Award Date': _dmy(award_date),
            'Extendable?': random.choice(['TRUE', 'FALSE']),
            'Extension Options Available': '',
            'One-Off Contract': random.choice(['TRUE', 'FALSE', 'FALSE', 'FALSE']),
            'Total Award Value': _gbp(award_val),
            'Current Value': _gbp(current_val),
            'Parent Contract / Framework': random.choice(FRAMEWORKS),
        })

    return pd.DataFrame(rows)


# ── Atamis Suppliers (supplier_data_report.csv) ─────────────────────────────

# Real sample/demo rows carried in Parliament's own Atamis extract, reproduced
# verbatim so the completeness/uniqueness checks see genuine test-data noise.
_SAMPLE_ROWS = [
    ('a29WS000000JF8D', 'Sample Child Supplier 2', 'Sample Child Supplier 2'),
    ('a29WS000000JF8E', 'Sample Parent Supplier', 'Sample Supplier'),
    ('a29WS000000JF8F', 'Sample Child Supplier 1', 'Sample Child Supplier'),
    ('a29WS000000JF8G', '4th Party Supplier 1', 'Sample Child Supplier 3'),
    ('a29WS000000MV8P', 'Atamis Test supplier', 'BricBrac'),
    ('a29WS000000NcXd', 'UKTest 1', 'UKTest1'),
]


def _gen_suppliers():
    rows = []
    for sid, name, cref in _SAMPLE_ROWS:
        rows.append({'Supplier: ID': sid, 'Supplier: Supplier Name': name, 'Creditor Ref': cref})

    real = UNIT4_SUPPLIERS.dropna(subset=['apar_id']).drop_duplicates(subset=['apar_id'])
    # Cover roughly half of the combined HOC+HOL supplier master with a genuine
    # Atamis registration — leaves the rest for UNIT4_SUPPLIER_NOT_IN_ATAMIS to
    # find, which is expected (payroll/tax/individual suppliers are commonly
    # never registered in procurement).
    covered = real.sample(frac=0.5, random_state=42) if len(real) else real
    for _, r in covered.iterrows():
        rows.append({
            'Supplier: ID': f"a29WS{fake.bothify('??????????').upper()}",
            'Supplier: Supplier Name': r['apar_name'],
            'Creditor Ref': r['apar_id'],
        })

    # Orphan Creditor Refs — registered in Atamis but never in Unit4
    for _ in range(8):
        rows.append({
            'Supplier: ID': f"a29WS{fake.bothify('??????????').upper()}",
            'Supplier: Supplier Name': fake.company().upper(),
            'Creditor Ref': str(random.randint(9000000, 9099999)),
        })

    # Blank Creditor Ref
    for _ in range(4):
        rows.append({
            'Supplier: ID': f"a29WS{fake.bothify('??????????').upper()}",
            'Supplier: Supplier Name': fake.company().upper(),
            'Creditor Ref': '',
        })

    # A couple of duplicate Creditor Refs
    if len(rows) > 10:
        dup = dict(rows[10])
        dup['Supplier: ID'] = f"a29WS{fake.bothify('??????????').upper()}"
        rows.append(dup)

    df = pd.DataFrame(rows)
    return df.sample(frac=1, random_state=42).reset_index(drop=True)


# ── Contract Total Commitments (contract_total_commitments.csv, Unit4) ─────

_CONTRACT_PREFIXES = ['ARC', 'PM', 'COM', 'GSV', 'CON']


def _gen_commitments(n=70):
    rows = []
    real_ids = UNIT4_SUPPLIERS.dropna(subset=['apar_id'])['apar_id'].unique().tolist()
    used_ids = set()

    for i in range(n):
        prefix = random.choice(_CONTRACT_PREFIXES)
        cid = f"{prefix}{1000 + i}"

        supplier_id = random.choice(real_ids) if real_ids and random.random() > 0.08 else ''
        if supplier_id and random.random() < 0.1:
            supplier_id = str(random.randint(9100000, 9199999))  # orphan, not in Unit4

        sup_row = UNIT4_SUPPLIERS[UNIT4_SUPPLIERS['apar_id'] == supplier_id]
        supplier_name = sup_row['apar_name'].iloc[0] if not sup_row.empty else (fake.company().upper() if supplier_id else '')

        date_from = _rand_date(date(2008, 1, 1), date(2022, 1, 1))
        date_to = date_from + timedelta(days=random.randint(365, 3000))
        if random.random() < 0.04:
            date_to = date_from - timedelta(days=random.randint(1, 90))  # invalid pair

        award = round(random.uniform(0, 2_000_000), 2)
        amount_limit = round(award * random.uniform(0.9, 1.4), 2) if award else round(random.uniform(1000, 500000), 2)
        posted = round(amount_limit * random.uniform(0.2, 1.15), 2)
        committed = round(posted * random.uniform(0.95, 1.05), 2)
        remaining = round(amount_limit - posted, 2)

        # A few deliberately wrong Remaining Amount figures
        if random.random() < 0.08:
            remaining = round(remaining + random.uniform(500, 5000) * random.choice([-1, 1]), 2)

        rows.append({
            'Contract Id': cid,
            'Contract Title': fake.bs().title()[:60],
            'Contract Date From': _dmy(date_from),
            'Contract Date To': _dmy(date_to),
            'Supplier ID': supplier_id,
            'Supplier Name': supplier_name,
            'Contract Award Amount': _amt(award),
            'Contract Amount Limit': _amt(amount_limit),
            'Committed Amount': _amt(committed),
            'Posted Amount': _amt(posted),
            'Total Registered Invoices': _amt(round(random.uniform(-1, 1), 2)),
            'Total Open Requisitions Amount': _amt(0.0),
            'Remaining Amount': _amt(remaining),
        })
        used_ids.add(cid)

    # A couple of duplicate Contract Ids
    if len(rows) > 5:
        dup = dict(rows[3])
        rows.append(dup)

    return pd.DataFrame(rows), used_ids


# ── Contract Spend Details (contracts_spend_details.csv, Unit4) ────────────

def _gen_spend(commitments_df: pd.DataFrame):
    rows = []

    # The extract's first row is always a grand-total summary — blank Contract,
    # totals across every contract. data_engine.py's loader filters this out.
    total_posted = pd.to_numeric(commitments_df['Posted Amount'].str.replace(',', ''), errors='coerce').sum()
    rows.append({'Contract': '', 'Posted': _amt(total_posted), 'Amount (C)': _amt(total_posted * 0.83)})

    for _, c in commitments_df.iterrows():
        cid = c['Contract Id']
        posted = float(str(c['Posted Amount']).replace(',', '') or 0)

        # Most contracts agree closely with the Commitments view; a subset
        # deliberately disagree by a material amount.
        if random.random() < 0.12:
            spend_posted = round(posted + random.uniform(200, 8000) * random.choice([-1, 1]), 2)
        else:
            spend_posted = round(posted + random.uniform(-0.5, 0.5), 2)

        if random.random() < 0.03:
            spend_posted = -abs(spend_posted)

        rows.append({
            'Contract': cid,
            'Posted': _amt(spend_posted),
            'Amount (C)': _amt(round(spend_posted * 0.83, 2)),
        })

    # A few Spend Details rows with no matching Commitments record
    for _ in range(5):
        rows.append({
            'Contract': f"OLD{random.randint(100,999)}",
            'Posted': _amt(round(random.uniform(500, 50000), 2)),
            'Amount (C)': _amt(round(random.uniform(500, 50000), 2)),
        })

    return pd.DataFrame(rows)


if __name__ == '__main__':
    print('Generating Atamis contracts...')
    contracts = _gen_contracts()
    contracts.to_csv(os.path.join(OUTPUT_DIR, 'contracts_report.csv'), index=False)
    print(f'  {len(contracts):,} contracts -> data/atamis/contracts_report.csv')

    print('Generating Atamis suppliers...')
    suppliers = _gen_suppliers()
    suppliers.to_csv(os.path.join(OUTPUT_DIR, 'supplier_data_report.csv'), index=False)
    print(f'  {len(suppliers):,} suppliers -> data/atamis/supplier_data_report.csv')

    print('Generating Unit4 contract commitments...')
    commitments, _ = _gen_commitments()
    commitments.to_csv(os.path.join(OUTPUT_DIR, 'contract_total_commitments.csv'), index=False)
    print(f'  {len(commitments):,} commitments -> data/atamis/contract_total_commitments.csv')

    print('Generating Unit4 contract spend details...')
    spend = _gen_spend(commitments)
    spend.to_csv(os.path.join(OUTPUT_DIR, 'contracts_spend_details.csv'), index=False)
    print(f'  {len(spend):,} spend rows -> data/atamis/contracts_spend_details.csv')

    print('Done.')
