"""
Parliament Finance Systems Programme
Fixed Asset Master Dummy Data Generator
========================================
Generates two CSVs mirroring the exact shape of the at_asset_master.sql extract:
  - asset_master_HOC.csv
  - asset_master_HOL.csv

Each file contains a mix of clean records (to pass DQ checks) and deliberate
edge-case rows (to trigger specific DQ tests). Edge cases are labelled with
a comment in the _edge_case column so expected failures are traceable.

Run:  python generate_dummy_asset_data.py
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

TODAY        = date.today()
THREE_YRS    = TODAY - timedelta(days=3 * 365)
TEN_YRS_AGO  = TODAY - timedelta(days=10 * 365)
ONE_YR_AGO   = TODAY - timedelta(days=365)

HOC = 'HOC'
HOL = 'HOL'

# ── Domain values ─────────────────────────────────────────────────────────────

ASSET_GROUPS   = ['LAND', 'BLDG', 'FURN', 'IT_HW', 'IT_SW', 'PLANT', 'VEHICLE', 'IFRS16']
AT_ATTR_IDS    = ['HERIT', 'OPER', 'LEASE', 'INFRA', 'OFFICE']
STATUSES       = ['N', 'C', 'P', 'T']      # N=Active, C=Closed, P=Parked, T=Terminated
WF_STATES      = ['T', '']                  # T=Approved, W=In workflow
COST_CENTRES   = ['CC001', 'CC002', 'CC003', 'CC004', 'CC005', 'CC010', 'CC020']
SUBJECTIVES    = ['SUB01', 'SUB02', 'SUB03', 'SUB04']
SUPPLIER_IDS   = [f"SUP{i:04d}" for i in range(1, 21)]   # must overlap with supplier_master

# ── Helpers ───────────────────────────────────────────────────────────────────

def rand_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, max(delta, 0)))

def asset_id(client: str, n: int) -> str:
    return f"AT{client}{n:05d}"

# ── Clean asset record ────────────────────────────────────────────────────────

def make_clean_asset(client: str, aid: str) -> dict:
    date_from    = rand_date(TEN_YRS_AGO, ONE_YR_AGO)
    cap_date     = rand_date(date_from, date_from + timedelta(days=90))
    org_amt      = round(random.uniform(500, 250_000), 2)
    base_amt     = round(org_amt * random.uniform(0.5, 1.0), 2)   # base <= org

    return {
        'client':         client,
        'asset_id':       aid,
        'description':    fake.catch_phrase(),
        'short_info':     fake.bs()[:30],
        'long_info':      fake.sentence(),
        'asset_group':    random.choice(ASSET_GROUPS),
        'status':         'N',
        'date_from':      date_from.isoformat(),
        'date_to':        None,
        'cap_date_from':  cap_date.isoformat(),
        'cap_period_from': int(f"{cap_date.year}{cap_date.month:02d}"),
        'base_amount':    base_amt,
        'org_amount':     org_amt,
        'org_amt_date':   date_from.isoformat(),
        'std_amount':     round(org_amt * random.uniform(0.9, 1.1), 2),
        'std_amt_date':   date_from.isoformat(),
        'ins_amount':     round(org_amt * random.uniform(0.8, 1.2), 2),
        'grant_flag':     0,
        'parent_asset':   None,
        'at_attr_id':     random.choice(AT_ATTR_IDS),
        'dim_1':          random.choice(COST_CENTRES),
        'dim_2':          random.choice(SUBJECTIVES),
        'dim_3':          None,
        'dim_4':          None,
        'dim_5':          None,
        'dim_6':          None,
        'dim_7':          None,
        'apar_id':        random.choice(SUPPLIER_IDS),
        'period_from':    int(f"{date_from.year}{date_from.month:02d}"),
        'period_to':      None,
        'wf_state':       'T',
        'last_update':    rand_date(ONE_YR_AGO, TODAY).isoformat(),
        '_edge_case':     None,
    }

# ── Edge cases ────────────────────────────────────────────────────────────────

def make_asset_edge_cases(client: str, start_n: int, clean_ids: list) -> list:
    cases = []
    n = start_n

    def ec(overrides: dict, label: str) -> dict:
        nonlocal n
        base = make_clean_asset(client, asset_id(client, n))
        base.update(overrides)
        base['_edge_case'] = label
        n += 1
        return base

    # ── Completeness (active assets) ──────────────────────────────────────────
    cases.append(ec({'description': None},    'AT_MISSING_DESCRIPTION'))
    cases.append(ec({'asset_group': None},    'AT_MISSING_ASSET_GROUP'))
    cases.append(ec({'cap_date_from': None},  'AT_MISSING_CAP_DATE'))
    cases.append(ec({'base_amount': None},    'AT_MISSING_BASE_AMOUNT'))
    cases.append(ec({'org_amount': None},     'AT_MISSING_ORG_AMOUNT'))
    cases.append(ec({'dim_1': None},          'AT_MISSING_DIM1'))

    # ── Validity ──────────────────────────────────────────────────────────────
    # date_from after date_to
    bad_dt = make_clean_asset(client, asset_id(client, n))
    bad_dt['date_from']    = date(2023, 6, 1).isoformat()
    bad_dt['date_to']      = date(2022, 1, 1).isoformat()   # end before start
    bad_dt['_edge_case']   = 'AT_DATE_FROM_AFTER_DATE_TO'
    cases.append(bad_dt); n += 1

    # cap_date_from before date_from
    bad_cap = make_clean_asset(client, asset_id(client, n))
    df_val  = date(2020, 6, 1)
    bad_cap['date_from']      = df_val.isoformat()
    bad_cap['cap_date_from']  = (df_val - timedelta(days=30)).isoformat()  # cap before ownership
    bad_cap['_edge_case']     = 'AT_CAP_BEFORE_DATE_FROM'
    cases.append(bad_cap); n += 1

    # base_amount > org_amount
    cases.append(ec({'base_amount': 999_000.00, 'org_amount': 10_000.00},
                    'AT_BASE_EXCEEDS_ORG'))

    # base_amount negative
    cases.append(ec({'base_amount': -5_000.00}, 'AT_NEGATIVE_BASE_AMOUNT'))

    # wf_state stuck in workflow
    cases.append(ec({'wf_state': 'W'}, 'AT_WF_STUCK'))

    # Active but date_to populated
    cases.append(ec({'status': 'N', 'date_to': rand_date(ONE_YR_AGO, TODAY).isoformat()},
                    'AT_ACTIVE_WITH_DATE_TO'))

    # ── Consistency ───────────────────────────────────────────────────────────
    # Orphaned asset_group (value not in known groups list — detected in Python)
    cases.append(ec({'asset_group': 'UNKNOWN_GRP'}, 'AT_ORPHANED_ASSET_GROUP'))

    # parent_asset points to non-existent asset_id
    cases.append(ec({'parent_asset': 'ATXXXXNONE'}, 'AT_PARENT_NOT_FOUND'))

    # parent_asset points to an inactive asset — we'll use a closed record's ID
    # The closed asset is created below; we forward-reference its ID
    inactive_parent_id = asset_id(client, n + 10)   # will be created in scope section
    cases.append(ec({'parent_asset': inactive_parent_id}, 'AT_PARENT_INACTIVE'))

    # apar_id references a non-existent supplier
    cases.append(ec({'apar_id': 'SUP_GHOST_999'}, 'AT_SUPPLIER_NOT_FOUND'))

    # apar_id references a supplier that exists but is inactive
    cases.append(ec({'apar_id': 'SUP_INACTIVE_001'}, 'AT_SUPPLIER_INACTIVE'))

    # dim_1 references an invalid cost centre
    cases.append(ec({'dim_1': 'CC_INVALID'}, 'AT_DIM1_INVALID'))

    # ── Duplicates (full population) ──────────────────────────────────────────
    # Same description + asset_group — possible duplicate asset
    dup_desc  = fake.catch_phrase()
    dup_group = random.choice(ASSET_GROUPS)
    for _ in range(2):
        dup = make_clean_asset(client, asset_id(client, n))
        dup['description']  = dup_desc
        dup['asset_group']  = dup_group
        dup['_edge_case']   = 'AT_DUP_DESC_GROUP'
        cases.append(dup)
        n += 1

    # ── Scope / Timeliness ────────────────────────────────────────────────────
    # Grant-funded asset
    cases.append(ec({'grant_flag': 1}, 'AT_GRANT_FUNDED'))

    # Component asset with parent_asset populated (valid parent from clean list)
    if clean_ids:
        cases.append(ec({'parent_asset': random.choice(clean_ids)}, 'AT_COMPONENT_ASSET'))

    # No capitalisation date (work-in-progress / not yet capitalised)
    cases.append(ec({'cap_date_from': None}, 'AT_NO_CAP_DATE_SCOPE'))

    # Stale asset — last_update older than 3 years
    cases.append(ec({'last_update': rand_date(
        TODAY - timedelta(days=6 * 365),
        TODAY - timedelta(days=3 * 365 + 1)).isoformat()},
        'AT_STALE'))

    # No dim_1 coding
    cases.append(ec({'dim_1': None}, 'AT_NO_DIM1_CODING'))

    # ── Closed / Inactive assets (for consistency join tests) ─────────────────
    # Closed asset that can serve as an inactive parent target
    closed = make_clean_asset(client, inactive_parent_id)
    closed['status']      = 'C'
    closed['date_to']     = rand_date(THREE_YRS, ONE_YR_AGO).isoformat()
    closed['_edge_case']  = 'AT_CLOSED_FOR_JOIN'
    cases.append(closed)

    # Terminated asset
    term = make_clean_asset(client, asset_id(client, n))
    term['status']     = 'T'
    term['date_to']    = rand_date(THREE_YRS, ONE_YR_AGO).isoformat()
    term['_edge_case'] = 'AT_TERMINATED'
    cases.append(term); n += 1

    return cases

# ── Builder ───────────────────────────────────────────────────────────────────

def build_asset_master(client: str, n_clean: int = 80) -> pd.DataFrame:
    clean = []
    for i in range(1, n_clean + 1):
        clean.append(make_clean_asset(client, asset_id(client, i)))

    clean_ids = [r['asset_id'] for r in clean]
    edges = make_asset_edge_cases(client, start_n=n_clean + 1, clean_ids=clean_ids)

    df = pd.DataFrame(clean + edges)
    return df

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Generating Fixed Asset Master dummy data...\n")

    for client in [HOC, HOL]:
        print(f"  [{client}] Building asset master (aatasset)...")
        df = build_asset_master(client, n_clean=80)
        path = os.path.join(OUTPUT_DIR, f"asset_master_{client}.csv")
        df.to_csv(path, index=False)
        ec_count = df['_edge_case'].notna().sum()
        print(f"         -> {len(df)} rows  ({ec_count} edge cases)  {path}")
        print()

    print("Done. Files written to ./data/")
    print()
    print("Edge cases embedded per file:")
    print("  Completeness  — AT_MISSING_DESCRIPTION, AT_MISSING_ASSET_GROUP,")
    print("                   AT_MISSING_CAP_DATE, AT_MISSING_BASE_AMOUNT,")
    print("                   AT_MISSING_ORG_AMOUNT, AT_MISSING_DIM1")
    print("  Validity      — AT_DATE_FROM_AFTER_DATE_TO, AT_CAP_BEFORE_DATE_FROM,")
    print("                   AT_BASE_EXCEEDS_ORG, AT_NEGATIVE_BASE_AMOUNT,")
    print("                   AT_WF_STUCK, AT_ACTIVE_WITH_DATE_TO")
    print("  Consistency   — AT_ORPHANED_ASSET_GROUP, AT_PARENT_NOT_FOUND,")
    print("                   AT_PARENT_INACTIVE, AT_SUPPLIER_NOT_FOUND,")
    print("                   AT_SUPPLIER_INACTIVE, AT_DIM1_INVALID")
    print("  Duplicates    — AT_DUP_DESC_GROUP (2 rows per House)")
    print("  Scope         — AT_GRANT_FUNDED, AT_COMPONENT_ASSET,")
    print("                   AT_NO_CAP_DATE_SCOPE, AT_STALE, AT_NO_DIM1_CODING")
    print("  Reference     — AT_CLOSED_FOR_JOIN, AT_TERMINATED")


if __name__ == '__main__':
    main()