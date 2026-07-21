"""
Read-only diagnostic -- run this on the Parliament laptop against real data to
understand why so few Atamis commitments/suppliers/spend records resolve to
HOL. Prints everything needed to tell apart three possible causes:
  1. Real HOC/HOL supplier IDs genuinely overlap (same numbering used in both)
  2. A formatting mismatch (whitespace, leading zeros, case) is silently
     breaking otherwise-valid matches
  3. The real data itself simply has few Atamis/Commitments records that
     reference a HOL supplier (a fact about the data, not a bug)

Run:  python scripts/diagnose_atamis_house.py
Makes no changes to any file.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from dashboard.data_engine import load_data

frames = load_data()

asu = frames.get('asuheader')
if asu is None or asu.empty:
    print("asuheader not loaded -- run the full dashboard (no tab filter) so this can compare against both houses.")
    raise SystemExit

hoc_ids = set(asu.loc[asu['house'] == 'HOC', 'apar_id'].dropna().astype(str).str.strip())
hol_ids = set(asu.loc[asu['house'] == 'HOL', 'apar_id'].dropna().astype(str).str.strip())

print("=" * 70)
print("SUPPLIER MASTER -- apar_id overlap between houses")
print("=" * 70)
print(f"HOC supplier count: {len(hoc_ids)}")
print(f"HOL supplier count: {len(hol_ids)}")
print(f"IDs that exist in BOTH houses (genuine collision): {len(hoc_ids & hol_ids)}")
print(f"IDs that exist ONLY in HOL: {len(hol_ids - hoc_ids)}")
if hoc_ids & hol_ids:
    sample = sorted(hoc_ids & hol_ids)[:10]
    print(f"Sample colliding IDs: {sample}")
print()

for table, id_col in [
    ('atamis_suppliers', 'creditor_ref'),
    ('unit4_commitments', 'supplier_id'),
]:
    df = frames.get(table)
    if df is None or df.empty:
        print(f"{table}: not loaded")
        continue

    print("=" * 70)
    print(f"{table} ({id_col}) -- resolution breakdown")
    print("=" * 70)
    print("house value_counts:", df['house'].value_counts().to_dict())

    ids = df[id_col].astype(str).str.strip()
    ids = ids[~ids.isin(['', 'nan', 'None'])]
    total = len(ids)
    only_hoc = int((ids.isin(hoc_ids) & ~ids.isin(hol_ids)).sum())
    only_hol = int((ids.isin(hol_ids) & ~ids.isin(hoc_ids)).sum())
    both = int((ids.isin(hoc_ids) & ids.isin(hol_ids)).sum())
    neither = int((~ids.isin(hoc_ids) & ~ids.isin(hol_ids)).sum())
    print(f"Of {total} non-blank IDs: only-HOC={only_hoc}, only-HOL={only_hol}, "
          f"in-BOTH(ambiguous)={both}, in-NEITHER(orphan)={neither}")

    # Show a few IDs that failed to match at all, so formatting issues are visible
    unmatched = ids[~ids.isin(hoc_ids) & ~ids.isin(hol_ids)]
    if not unmatched.empty:
        print(f"Sample unmatched {id_col} values (check formatting against apar_id): "
              f"{unmatched.head(10).tolist()}")

    # Show a few real HOL apar_id values side by side for a manual eyeball check
    if hol_ids:
        print(f"Sample real HOL apar_id values for comparison: {sorted(hol_ids)[:10]}")
    print()

print("=" * 70)
print("If 'in-BOTH(ambiguous)' is large: real HOC/HOL IDs genuinely overlap --")
print("  the same limitation seen in dummy data also applies to real data.")
print("If 'only-HOL' is 0 or near-0 but HOL has real suppliers: check the")
print("  'Sample unmatched' and 'Sample real HOL apar_id' lines above for a")
print("  formatting mismatch (e.g. Atamis stores '8705187' but Unit4 stores")
print("  '08705187', or with trailing whitespace).")
print("=" * 70)

# ── atamis_contracts full resolution chain for every row still 'Unknown' ──
# Shows exactly why each one didn't resolve: no matching commitment at all,
# vs. a matching commitment whose own Supplier ID doesn't resolve either.
contracts = frames.get('atamis_contracts')
commitments = frames.get('unit4_commitments')
if contracts is not None and not contracts.empty:
    unknown_contracts = contracts[contracts['house'] == 'Unknown']
    print()
    print("=" * 70)
    print(f"atamis_contracts -- {len(unknown_contracts)} rows still 'Unknown' -- full resolution chain")
    print("=" * 70)
    if commitments is not None and not commitments.empty:
        commit_lookup = commitments.set_index('u4_contract_id')[['supplier_id', 'house']]
        commit_lookup = commit_lookup[~commit_lookup.index.to_series().duplicated(keep='first')]
    else:
        commit_lookup = None
    for _, row in unknown_contracts.iterrows():
        ref = str(row['contract_ref']).strip()
        print(f"contract_ref={row['contract_ref']!r}  organisation={row['organisation']!r}")
        if commit_lookup is None:
            print("  -> unit4_commitments not loaded, cannot check")
        elif ref in ('nan', 'None', '', 'NaN') or row['contract_ref'] is None:
            print("  -> contract_ref itself is blank -- nothing to look up (see ATAMIS_CONTRACT_NO_REF)")
        elif ref not in commit_lookup.index:
            print(f"  -> no commitment record found with Contract Id == {ref!r} (check for whitespace/case differences)")
        else:
            match = commit_lookup.loc[ref]
            if isinstance(match, pd.DataFrame):
                print(f"  -> WARNING: {len(match)} commitment records share this Contract Id")
                match = match.iloc[0]
            print(f"  -> matched commitment: supplier_id={match['supplier_id']!r}, that commitment's own resolved house={match['house']!r}")
            if match['house'] == 'Unknown':
                print(f"  -> stays Unknown because the MATCHED COMMITMENT's own Supplier ID ({match['supplier_id']!r}) doesn't resolve to a Unit4 supplier either")
    print("=" * 70)
