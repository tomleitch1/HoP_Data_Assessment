"""
Parliament Finance Systems Programme
DQ Engine & Data Processing
"""

import pandas as pd
import numpy as np
import os
from datetime import date
from dashboard.core.config import RAG_THRESHOLDS, SupplierConfig
from dashboard.core.rules.ap_rules import get_ap_checks
from dashboard.core.rules.ar_rules import get_ar_checks
from dashboard.core.rules.asset_rules import get_asset_checks
from dashboard.core.rules.gl_rules import get_gl_checks
from dashboard.core.rules.po_rules import get_po_checks
from dashboard.core.rules.atamis_rules import get_atamis_checks
from dashboard.core.rules.budget_rules import get_budget_checks

DATA_DIR = 'data'
CLIENTS = ['HOC', 'HOL']
SCOPE_LABELS = {10: 'Suppliers', 11: 'Customers', 16: 'AP Invoices', 17: 'AR Invoices'}

# Atamis/Unit4-via-Atamis tables are the only ones NOT split into per-house HOC/HOL
# extracts — all four arrive as single combined files spanning both houses (and,
# for atamis_contracts, a third 'Joint' category). House is derived post-load by
# cross-referencing the Unit4 supplier master rather than read from the filename —
# see _derive_atamis_houses(). ATAMIS_HOUSES extends the standard 2-house iteration
# in run_dq_analysis() for these tables only; every other table's checks are
# unaffected since their 'house' column never equals 'Joint' or 'Unknown'.
ATAMIS_TABLES = {'atamis_contracts', 'unit4_commitments', 'unit4_spend', 'atamis_suppliers', 'unit4_contract_refs'}
ATAMIS_HOUSES = ['HOC', 'HOL', 'Joint', 'Unknown']


def _atamis_blank(s: pd.Series) -> pd.Series:
    return s.isna() | (s.astype(str).str.strip().isin(['', 'nan', 'None']))


def _atamis_existence_population(df_table, house, id_col):
    """Shared population for Atamis 'no matching record in the other system'
    checks (ATAMIS_SUPPLIER_NOT_IN_UNIT4, UNIT4_COMMIT_SUPPLIER_ORPHAN,
    UNIT4_SPEND_CONTRACT_ORPHAN), whose failing condition is the row's own
    derived house being 'Unknown'. 'Unknown' isn't a real house to report a
    rate under three times over (HOC/HOL/Joint would each trivially show 0%,
    since an unresolved row can never appear in a resolved house's population) —
    so these checks emit exactly one dq_results row, tagged house='Unknown',
    with the FULL non-blank population as the denominator. Every other house
    iteration is skipped by returning an empty frame."""
    if house != 'Unknown':
        return df_table.iloc[0:0]
    return df_table[~_atamis_blank(df_table[id_col])]


def _atamis_open_contract_refs(frames: dict):
    """Set of u4_contract_id values considered currently open, per
    unit4_open_contracts.csv — its own existence as a row means open, there
    is no separate status column on that extract. Returns None (not an empty
    set) when the file isn't loaded, so callers can tell "no data, don't
    filter" apart from "loaded, but genuinely empty" (which would correctly
    exclude everything)."""
    open_df = frames.get('unit4_open_contracts')
    if open_df is None or 'u4_contract_id' not in open_df.columns:
        return None
    return set(open_df['u4_contract_id'].dropna().astype(str).str.strip())


# Checks restricted to currently-open contracts only (per direct request,
# once unit4_open_contracts.csv became available) — a closed contract's
# commitment/spend records, or a closed Atamis contract with no commitment
# counterpart, are no longer a data quality concern once the contract itself
# isn't live. Every UNIT4_COMMIT_*/UNIT4_SPEND_* check plus the one Atamis
# check that tests the same "does this trace to a real Unit4 record"
# question in the other direction (ATAMIS_CONTRACT_NOT_IN_COMMITMENTS).
_ATAMIS_OPEN_ONLY_CHECKS = {
    'UNIT4_COMMIT_NO_SUPPLIER_ID', 'UNIT4_COMMIT_DATE_INVALID', 'UNIT4_COMMIT_REMAINING_MISMATCH',
    'UNIT4_COMMIT_OVERSPEND', 'UNIT4_COMMIT_DUP_ID', 'UNIT4_COMMIT_SUPPLIER_ORPHAN',
    'UNIT4_COMMIT_NOT_IN_CONTRACTS', 'UNIT4_COMMIT_VS_SPEND_MISMATCH', 'UNIT4_COMMIT_VS_PO_MISMATCH',
    'UNIT4_SPEND_CONTRACT_ORPHAN', 'UNIT4_SPEND_NEGATIVE_POSTED',
    'ATAMIS_CONTRACT_NOT_IN_COMMITMENTS',
}


def _atamis_filter_open_only(h_df, table, frames):
    """Applied after a check's normal population is computed, for check_ids
    in _ATAMIS_OPEN_ONLY_CHECKS. No-ops (returns h_df unchanged) if
    unit4_open_contracts.csv isn't loaded, so this never silently excludes
    everything when the file simply isn't present yet."""
    open_refs = _atamis_open_contract_refs(frames)
    if open_refs is None:
        return h_df
    ref_col = 'contract_ref' if table == 'atamis_contracts' else 'u4_contract_id'
    if ref_col not in h_df.columns:
        return h_df
    return h_df[h_df[ref_col].astype(str).str.strip().isin(open_refs)]


# Standard financial fields always surfaced in the modal for every apodetail
# (PO Line) check, regardless of which field actually triggered it, so the
# reviewer can assess the full amount/receipt/match/invoice picture in one view.
_PO_LINE_STANDARD_FIELDS = ['amount', 'vow_amount', 'vow_val', 'arr_amount', 'arr_val', 'invoiced', 'unit_price']

_PO_UNMATCHED_RECEIPT_CHECKS = ['PO_LINE_UNINVOICED_RECEIPT_OVER3M']

# PO join checks whose evidence relies on their own explicit early-return
# enrichment block further down in this function (join + narrow to the
# identifiers and the specific joined field being compared, e.g. contract_id
# on both sides) — for these, for_export=True must NOT take the generic
# early-return shortcut below, or Excel exports would show the raw source
# table only, with no evidence of the join that actually drove the flag.
# Scoped to PO only; every other domain's early-return blocks (GL, Assets)
# keep the existing for_export shortcut unchanged.
_PO_JOIN_EXPORT_CHECKS = {
    'PO_FINISHED_WITH_BALANCE', 'PO_HDR_LINE_CONTRACT_MISMATCH',
    'PO_LINE_CLOSED_ACCOUNT', 'PO_LINE_ORPHAN_ACCOUNT',
    'PO_INACTIVE_SUPPLIER', 'PO_ORPHANED_SUPPLIER',
}


def _po_unmatched_receipt_population(df_table, house):
    """Shared base population for the three unmatched-open-receipt age-tier
    checks: status not in (F,C,T), genuinely received (vow_amount > 0), and
    unmatched by either invoicing measure. Uses GREATEST(arr_amount,
    invoiced), not invoiced alone — see QUESTIONS_FOR_PARLIAMENT.md #5."""
    vow = pd.to_numeric(df_table['vow_amount'], errors='coerce').fillna(0)
    eff_invoiced = df_table[['arr_amount', 'invoiced']].apply(pd.to_numeric, errors='coerce').fillna(0).max(axis=1)
    return df_table[
        (df_table['house'] == house)
        & (~df_table['status'].isin(['F', 'C', 'T']))
        & (vow > 0.01)
        & (eff_invoiced <= 0.01)
    ]

# Subdirectory for each data domain within DATA_DIR
SUBDIR = {
    'suppliers': ['supplier_master', 'supplier_open_trans', 'supplier_history'],
    'customers': ['customer_master', 'customer_open_trans', 'customer_history'],
    'gl':        ['gl_chart_of_accounts', 'gl_opening_balances', 'gl_dimension_config', 'gl_dimension_values',
                  'gl_transact_dimensions', 'gl_budgets', 'gl_journals',
                  'gl_active_accounts', 'gl_planner_accounts'],
    'assets':    ['asset_master', 'asset_depreciation', 'asset_balances',
                  'asset_trans_flags', 'asset_groups'],
    'po':        ['po_header', 'po_detail'],
    # Base names here are the ACTUAL file stems (no _HOC/_HOL suffix — these
    # four are single combined files, unlike every other domain), not the
    # internal table keys. See single_files in load_data().
    'atamis':    ['contracts_report', 'contract_total_commitments', 'contracts_spend_details', 'supplier_data_report',
                  'unit4_open_contracts', 'hol_unit4_spend'],
    # budgets_report is a single combined HOC+HOL file (Recharge column = HOC/HOL),
    # same pattern as Atamis — house derived post-load, not from filename.
    # Key is 'budgets' (the actual data/ subdirectory) not 'pbf' (the tab name).
    'budgets':   ['budgets_report'],
}
# Reverse lookup: base_name -> subdirectory
_SUBDIR_MAP = {name: sub for sub, names in SUBDIR.items() for name in names}

# Raw Atamis/Unit4 export headers -> clean snake_case column names. These four
# files arrive exactly as exported (human-readable headers with spaces/punctuation),
# unlike every other domain's CSVs which already have clean names baked in by the
# SQL extract's own column aliases.
_ATAMIS_RENAME = {
    'atamis_contracts': {
        # The real export's first column header carries a "Sourcing to
        # Contract: " report-tool prefix ahead of the field name — both keys
        # are mapped so a plain 'ContractTitle' header (e.g. from dummy data)
        # still renames correctly too.
        'Sourcing to Contract: ContractTitle':  'contract_title',
        'ContractTitle':                        'contract_title',
        'Contract Reference':                    'contract_ref',
        'Contract Manager':                      'contract_manager',
        'Organisation':                          'organisation',
        'Supplier':                               'supplier_name',
        'HAIS Product Code(s)':                   'hais_product_codes',
        'EPMO Project Name or SE Project Code':   'epmo_project',
        'Department Name':                        'department_name',
        'PCD Branch':                              'pcd_branch',
        'Start Date':                              'start_date',
        'End Date':                                'end_date',
        'Contract Award Date':                     'award_date',
        'Extendable?':                             'extendable',
        'Extension Options Available':             'extension_options',
        'One-Off Contract':                        'one_off_contract',
        'Total Award Value':                       'total_award_value',
        'Current Value':                           'current_value',
        'Parent Contract / Framework':             'parent_contract',
    },
    # Unit4 view #1 of contract spend — Committed/Posted/Remaining as at extract date.
    'unit4_commitments': {
        'Contract Id':                    'u4_contract_id',
        'Contract Title':                 'contract_title',
        'Contract Date From':             'date_from',
        'Contract Date To':               'date_to',
        'Supplier ID':                    'supplier_id',
        'Supplier Name':                  'supplier_name',
        'Contract Award Amount':          'award_amount',
        'Contract Amount Limit':          'amount_limit',
        'Committed Amount':               'committed_amount',
        'Posted Amount':                  'posted_amount',
        'Total Registered Invoices':      'registered_invoices',
        'Total Open Requisitions Amount': 'open_requisitions',
        'Remaining Amount':               'remaining_amount',
    },
    # Unit4 view #2 of contract spend — a separate Agresso view of the same
    # contracts, joined back to unit4_commitments via u4_contract_id. The two
    # views can disagree (see UNIT4_COMMIT_VS_SPEND_MISMATCH).
    'unit4_spend': {
        'Contract':   'u4_contract_id',
        'Posted':     'posted',
        'Amount (C)': 'amount_c',
    },
    # Atamis's own supplier list. Supplier: ID is a Salesforce record ID and is
    # NOT the join key to Unit4 — Creditor Ref is. See ATAMIS_SUPPLIER_NOT_IN_UNIT4.
    'atamis_suppliers': {
        'Supplier: ID':             'supplier_salesforce_id',
        'Supplier: Supplier Name':  'supplier_name',
        'Creditor Ref':             'creditor_ref',
    },
    # Master list of currently OPEN Unit4 contracts — its own existence as a
    # row means open, there is no separate status column. Used to restrict
    # the Commitments/Spend reconciliation checks to contracts that are still
    # live, so a closed contract's commitment/spend records stop being tested
    # against Atamis at all (see _atamis_open_contract_refs / _ATAMIS_OPEN_ONLY_CHECKS).
    'unit4_open_contracts': {
        'Contract':                                          'u4_contract_id',
        'Contract(T)':                                        'contract_title',
        'Contract Details - Contract Award Date':             'award_date',
        'Related Contract Info - Contract Manager':           'contract_manager',
        'Related Contract Info - Contract Manager´s Email':   'contract_manager_email',
        'Related Contract Info - Contract Manager User':      'contract_manager_user',
        'Contract Details - Contract Owner':                  'contract_owner',
        'Contract Details - Procurement Length Months':       'procurement_length_months',
        'Contract Details - Contract to be re-let':            'to_be_relet',
        'Supplier ID':                                        'supplier_id',
        'Supplier ID(T)':                                     'supplier_name',
        'Supplier Company registration no.':                  'supplier_comp_reg_no',
        'Related Contract Info - Department':                 'department',
        'Related Contract Info - Lead PPCS Category Team':    'ppcs_category_team',
        'Related Contract Info - PPCS Contact':               'ppcs_contact',
        'Contract Details - Contract Start Date':             'start_date',
        'Date to':                                            'end_date',
        'Contract Details - Contract Length (months)':        'contract_length_months',
        'Extension Options - Extension Applied Date':          'extension_applied_date',
        'Compliance - Risk':                                  'risk',
        'Contract Details - Contract Current Value':          'current_value',
        'Contract Details - Contract Award Value':            'award_value',
        'Contract Details - Contract Price Type':             'price_type',
        'Contract Details - Procedures':                      'procedures',
        'Framework Details - Framework Options':              'framework_options',
        'Compliance - GDPR':                                  'gdpr',
        'Supplier Type - SME':                                'sme',
        'Supplier Type - Social Enterprise':                  'social_enterprise',
        'Ppcs Performance Measures - Performance-Authoritative': 'perf_authoritative',
        'Ppcs Performance Measures - Performance-Clear':       'perf_clear',
        'Ppcs Performance Measures - Performance-Engaged':     'perf_engaged',
        'Ppcs Performance Measures - Performance-Making Impact': 'perf_impact',
        'Ppcs Performance Measures - Performance-Proactive':   'perf_proactive',
        'Related Contract Info - Location':                   'location',
    },
    # HOL's own contract-spend report, sent to Atamis from HAIS. Two columns
    # only — no rich commitment data like HOC's Commitments view — but this
    # is HOL's only source of real financial activity against a contract
    # reference, used as a materiality gate on the HOL GL Contract Number
    # dimension signal (see _build_unit4_contract_refs).
    'hol_unit4_spend': {
        'Contract Number': 'u4_contract_id',
        'Amount':          'amount',
    },
}

_ATAMIS_ORG_HOUSE_MAP = {'HOC': 'HOC', 'HOL': 'HOL', 'JOINT': 'Joint'}

# Pre-built Finance report column headers → clean snake_case.
# The Finance report arrives with human-readable headers (spaces, parentheses)
# unlike every SQL-extracted CSV which already has clean names from its own
# column aliases.
_BUDGET_RENAME = {
    'Mipck-l1':    'mipck_l1',
    'Mipck-l1(T)': 'mipck_l1_desc',
    'Mipck-l2':    'mipck_l2',
    'Mipck-l2(T)': 'mipck_l2_desc',
    'Mipck-l3':    'mipck_l3',
    'Account':     'account',
    'Account(T)':  'account_desc',
    'Department':  'department',
    'Directorate': 'directorate',
    'Costc':       'costc',
    'Haiscode':    'haiscode',
    'Haiscode(T)': 'haiscode_desc',
    'Recharge':    'recharge',
    'Year':        'year',
    'Period':      'period',
    'Amount':      'gl_actuals',
    'Amount DA':   'orig_budget',
    'Amount DB':   'curr_budget',
    'Amount DE':   'live_forecast',
    'Amount DF':   'pfst_budget',
    'Amount DG':   'q1_forecast',
    'Amount DH':   'q2_forecast',
    'Amount DI':   'q3_forecast',
    'Unit':        'unit',
}


def _derive_atamis_houses(frames: dict) -> None:
    """Assigns a 'house' column to each Atamis/Unit4-via-Atamis table in place.

    None of these four files are split into HOC/HOL extracts like every other
    domain's tables, so house cannot be read from the filename. atamis_contracts
    carries its own Organisation field (HOC/HOL/Joint); HOC/HOL map directly,
    but 'Joint' is resolved further — see below. The other three have no house
    field at all — house is derived by matching their supplier identifier
    against asuheader.apar_id (checking HOC first, then HOL). A row whose
    identifier matches neither house is tagged 'Unknown' — that mismatch is
    exactly the condition several DQ checks below test for (e.g.
    ATAMIS_SUPPLIER_NOT_IN_UNIT4, UNIT4_COMMIT_SUPPLIER_ORPHAN), not a gap to
    be papered over with a guessed default.
    """
    asu = frames.get('asuheader')
    hoc_ids, hol_ids = set(), set()
    if asu is not None and not asu.empty:
        hoc_ids = set(asu.loc[asu['house'] == 'HOC', 'apar_id'].dropna().astype(str).str.strip())
        hol_ids = set(asu.loc[asu['house'] == 'HOL', 'apar_id'].dropna().astype(str).str.strip())

    def _match_house(id_series: pd.Series) -> pd.Series:
        ids = id_series.astype(str).str.strip()
        house = pd.Series('Unknown', index=ids.index)
        house[ids.isin(hoc_ids)] = 'HOC'
        house[(house == 'Unknown') & ids.isin(hol_ids)] = 'HOL'
        return house

    # unit4_commitments' house is computed first — atamis_contracts' 'Joint'
    # resolution below depends on it.
    if 'unit4_commitments' in frames:
        df = frames['unit4_commitments']
        df['house'] = _match_house(df['supplier_id'])

    if 'atamis_contracts' in frames:
        df = frames['atamis_contracts']
        org = df['organisation'].astype(str).str.strip().str.upper()
        house = org.map(_ATAMIS_ORG_HOUSE_MAP).fillna('Unknown')

        # Any contract not cleanly resolved to HOC/HOL by its own Organisation
        # field — labelled 'Joint', or blank/unexpected (mapped to 'Unknown'
        # above) — gets a second chance via the confirmed Contract Reference
        # == Contract Id join to Unit4 Commitments, using that commitment's
        # own already-resolved house (computed above). Not a name match —
        # tried first, rejected as not robust: real supplier names differ in
        # formatting between Atamis and Unit4, e.g. "LTD" vs "LIMITED", and
        # won't reliably resolve. A commitment always pays one specific
        # supplier, and that supplier belongs to exactly one house — so even
        # though Atamis's own Organisation field doesn't say so (whether it
        # says 'Joint' or is simply blank/wrong), the underlying spend has a
        # real house once traced through to who's actually being paid. This
        # was originally scoped to 'Joint' only, which meant a contract with
        # a blank/invalid Organisation value skipped this lookup entirely
        # even when the exact same resolution would have worked — found
        # directly by the user via a specific contract on real data. Only if
        # no matching commitment exists at all, or that commitment's own
        # supplier doesn't resolve either, does the contract fall to
        # 'Unknown' — same meaning as every other unresolvable reference in
        # this domain, not a gap to guess at. The raw Organisation field
        # itself is untouched and still drives the tab's own "Contracts by
        # Organisation" visualisation, a separate concept from this resolved
        # house.
        needs_resolution = ~house.isin(['HOC', 'HOL'])
        # Baseline every unresolved row to 'Unknown' first (covers 'Joint' and
        # any blank/unexpected Organisation alike), then only rows with a
        # populated contract_ref get a chance to upgrade via the commitments
        # lookup. Blank contract_ref rows are excluded from the lookup itself,
        # not just left as-is afterwards — a pandas merge treats NaN/blank keys
        # as equal to each other, so without this exclusion a contract with no
        # reference at all could spuriously match a commitment that also has a
        # blank/missing u4_contract_id and adopt its house, rather than
        # correctly staying 'Unknown' for lack of anything to look up. Same bug
        # class as the one already fixed in ATAMIS_CONTRACT_VALUE_MISMATCH.
        house.loc[needs_resolution] = 'Unknown'
        lookup_rows = needs_resolution & ~_atamis_blank(df['contract_ref'])
        if lookup_rows.any() and 'unit4_commitments' in frames:
            commit_raw = frames['unit4_commitments']
            commit_house = (
                commit_raw[~_atamis_blank(commit_raw['u4_contract_id'])][['u4_contract_id', 'house']]
                .drop_duplicates(subset=['u4_contract_id'])
                .rename(columns={'u4_contract_id': 'contract_ref', 'house': '_commit_house'})
            )
            merged = df.loc[lookup_rows, ['contract_ref']].merge(commit_house, on='contract_ref', how='left')
            resolved = merged['_commit_house'].where(merged['_commit_house'].isin(['HOC', 'HOL'])).fillna('Unknown')
            house.loc[lookup_rows] = resolved.values

        df['house'] = house

    if 'atamis_suppliers' in frames:
        df = frames['atamis_suppliers']
        df['house'] = _match_house(df['creditor_ref'])

    if 'unit4_spend' in frames:
        df = frames['unit4_spend']
        if 'unit4_commitments' in frames:
            commit_house = (
                frames['unit4_commitments'][['u4_contract_id', 'house']]
                .drop_duplicates(subset=['u4_contract_id'])
            )
            merged = df[['u4_contract_id']].merge(commit_house, on='u4_contract_id', how='left')
            df['house'] = merged['house'].fillna('Unknown').values
        else:
            df['house'] = 'Unknown'


def _build_unit4_contract_refs(frames: dict) -> None:
    """Builds frames['unit4_contract_refs'] — the population for
    UNIT4_COMMIT_NOT_IN_CONTRACTS — since HOC and HOL master their Unit4-side
    contract reference completely differently and neither source alone covers
    both houses:

      - HOC: contract_total_commitments.csv (unit4_commitments) is the real,
        rich source — one row per commitment, Contract Id plus Supplier,
        Posted/Remaining/Limit amounts, dates, etc. In practice this extract
        is HOC-only (real data: Supplier IDs resolve almost exclusively to
        HOC — see CLAUDE.md), so it contributes no meaningful HOL coverage.
      - HOL: has no equivalent Commitments extract. Per direct confirmation,
        HOL's contract reference instead lives in the GL dimension value list
        (gl_dimension_values_HOL.csv / agldimvalue), specifically the
        dim_position == '5' ('Contract Number') attribute, where dim_value
        IS the contract reference.

    Rather than replacing unit4_commitments (which every other Commitments
    check — REMAINING_MISMATCH, DATE_INVALID, DUP_ID, OVERSPEND,
    SUPPLIER_ORPHAN — still depends on, and which HOL has no equivalent rich
    data for), this builds a separate frame: a full copy of unit4_commitments
    (same columns, so UNIT4_COMMIT_NOT_IN_CONTRACTS's existing lambda and
    modal enrichment work unchanged for HOC) with synthetic HOL rows appended
    that populate only 'house' and 'u4_contract_id' (from dim_value) — every
    other commitment-specific column (contract_title, supplier_name,
    amount_limit, etc.) is blank for these rows since HOL has no equivalent
    data. A '_source' column marks which rows came from which extract, so the
    modal evidence makes the provenance difference visible rather than
    implying HOL has the same rich commitment data HOC does.
    """
    commit = frames.get('unit4_commitments')
    if commit is not None and not commit.empty:
        base = commit.copy()
        base['_source'] = 'unit4_commitments'
    else:
        base = pd.DataFrame(columns=['house', 'u4_contract_id', '_source'])

    dimvals = frames.get('agldimvalue')
    if dimvals is not None and not dimvals.empty:
        hol_mask = (
            (dimvals['house'] == 'HOL') &
            (dimvals['dim_position'].astype(str).str.strip() == '5') &
            (dimvals['dim_description'].astype(str).str.strip().str.lower() == 'contract number')
        )
        hol_refs = dimvals.loc[hol_mask, ['dim_value']].rename(columns={'dim_value': 'u4_contract_id'})
        hol_refs['house'] = 'HOL'
        hol_refs['_source'] = 'gl_dimension_values'

        # Materiality gate (per direct request): a HOL GL Contract Number
        # dimension code only counts as a genuine Unit4-side signal if there
        # is actual recorded spend against it in hol_unit4_spend.csv (HAIS's
        # own contract-spend report for HOL — the only source of real
        # financial activity HOL has, since it has no Commitments extract).
        # A dimension code with no spend is presumed dormant/unused rather
        # than a real link, so it's excluded here — before any downstream
        # check (UNIT4_COMMIT_NOT_IN_CONTRACTS, ATAMIS_CONTRACT_NOT_IN_COMMITMENTS)
        # or the Organisation Field Reliability card (which reads this same
        # frame) ever sees it. If hol_unit4_spend isn't loaded at all, the
        # gate is skipped entirely (every HOL GL reference counts, as before)
        # rather than silently excluding everything.
        hol_spend = frames.get('hol_unit4_spend')
        if hol_spend is not None and not hol_spend.empty and 'u4_contract_id' in hol_spend.columns:
            spend_by_ref = (
                hol_spend[~_atamis_blank(hol_spend['u4_contract_id'])]
                .assign(_ref=lambda d: d['u4_contract_id'].astype(str).str.strip())
                .groupby('_ref')['amount'].sum()
            )
            ref_clean = hol_refs['u4_contract_id'].astype(str).str.strip()
            hol_refs = hol_refs.assign(_hol_spend_amount=ref_clean.map(spend_by_ref).fillna(0.0))
            hol_refs = hol_refs[hol_refs['_hol_spend_amount'] > 0].drop(columns=['_hol_spend_amount'])

        base = pd.concat([base, hol_refs], ignore_index=True)

    frames['unit4_contract_refs'] = base


def _derive_budget_houses(frames: dict) -> None:
    """Assigns a 'house' column to budgets_report in place.

    budgets_report is a single combined HOC+HOL file (same pattern as Atamis).
    The Recharge column contains 'HOC' or 'HOL' directly — unlike Atamis, there
    is no cross-reference needed. Any unrecognised value maps to 'Unknown'.
    """
    df = frames.get('budgets_report')
    if df is None:
        return
    df['house'] = df['recharge'].astype(str).str.strip().map({'HOC': 'HOC', 'HOL': 'HOL'}).fillna('Unknown')


def _data_path(base_name: str, suffix: str = '') -> str:
    """Return the full path for a data file, respecting the subdirectory layout."""
    filename = f"{base_name}{suffix}.csv"
    subdir = _SUBDIR_MAP.get(base_name, '')
    return os.path.join(DATA_DIR, subdir, filename)

_EXCEL_ORIGIN = pd.Timestamp('1899-12-30')
_EXCEL_MIN, _EXCEL_MAX = 20000, 55000  # approx year 1954 – 2050

_CACHE_DIR = os.path.join('data', '.cache')

def _version_suffix() -> str:
    """Cache-key suffix for the active DASHBOARD_VERSION (e.g. 'v2'), empty for the
    standard run. Every cache file below is keyed through this so a versioned run
    (e.g. `python run_dashboard.py suppliers v2`) can never write into — or read
    from — the plain run's cache, and vice versa."""
    v = os.environ.get('DASHBOARD_VERSION', '').strip()
    return f'__{v}' if v else ''

def _cache_path(table: str) -> str:
    return os.path.join(_CACHE_DIR, f'{table}{_version_suffix()}.pkl')

def _cache_fresh(table: str, source_paths: list) -> bool:
    """True if the cached pickle exists and is newer than all source CSVs."""
    cp = _cache_path(table)
    if not os.path.exists(cp):
        return False
    ct = os.path.getmtime(cp)
    return all(not os.path.exists(p) or os.path.getmtime(p) <= ct for p in source_paths)


def _dq_cache_fresh(cache_key: str, frames: dict) -> bool:
    """True if the dq_results cache is newer than all frame caches and all rules files.

    Invalidated by: any source CSV change (via frame pickles), any rules .py
    edit, or any change to data_engine.py itself.  Tab renderer / app.py changes
    do NOT invalidate it — those are pure UI and don't affect DQ results.
    """
    cp = _cache_path(cache_key)
    if not os.path.exists(cp):
        return False
    ct = os.path.getmtime(cp)

    # If any frame pickle is newer → underlying data changed → re-run
    for table in frames:
        fp = _cache_path(table)
        if os.path.exists(fp) and os.path.getmtime(fp) > ct:
            return False

    # If any rules file changed → check definitions changed → re-run
    rules_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'core', 'rules')
    if os.path.isdir(rules_dir):
        for fname in os.listdir(rules_dir):
            if fname.endswith('.py'):
                if os.path.getmtime(os.path.join(rules_dir, fname)) > ct:
                    return False

    # If data_engine.py itself changed → population filters / scoring logic changed → re-run
    if os.path.getmtime(os.path.abspath(__file__)) > ct:
        return False

    return True


# ── Per-check caching ──────────────────────────────────────────────────────────
# Each (check_id, house) result row is cached individually so editing one rule
# only reruns that check — everything else loads from cache instantly.

import hashlib as _hashlib
import inspect as _inspect
import pickle as _pickle
from glob import glob as _glob

_CHK_DIR = os.path.join('data', '.cache', 'checks')


def _chk_sig(check_tuple) -> str:
    """Short content-hash of the full check definition including lambda source.
    Changes whenever the rule logic, severity, dimension, or table mapping changes.
    """
    *meta, filter_func = check_tuple
    try:
        src = _inspect.getsource(filter_func).strip()
    except OSError:
        src = repr(filter_func)
    raw = '|'.join(str(m) for m in meta) + '|' + src
    return _hashlib.md5(raw.encode()).hexdigest()[:12]


def _chk_file(check_id: str, house: str, check_sig: str, engine_sig: str) -> str:
    return os.path.join(_CHK_DIR, f'{check_id}__{house}__{check_sig}__{engine_sig}{_version_suffix()}.pkl')


def _chk_fresh(cache_file: str, relevant_fps: list) -> bool:
    """True if the per-check cache file exists and source data hasn't changed.

    The engine_sig is embedded in the filename — if run_dq_analysis changes,
    the filename changes and the file won't be found.  Editing get_failing_records
    or get_check_columns does NOT change engine_sig so those edits don't
    invalidate the analysis cache.
    """
    if not os.path.exists(cache_file):
        return False
    ct = os.path.getmtime(cache_file)
    for fp in relevant_fps:
        if os.path.exists(fp) and os.path.getmtime(fp) > ct:
            return False
    return True


def _read_chk(cache_file: str) -> dict:
    with open(cache_file, 'rb') as f:
        return _pickle.load(f)


_ENGINE_SIG_CACHE: str | None = None

def _engine_sig() -> str:
    """Hash of run_dq_analysis source, plus _derive_atamis_houses and
    _build_unit4_contract_refs source. Changing get_failing_records,
    get_check_columns, or any other function in this file does NOT change
    this value — only edits to these three do.

    _derive_atamis_houses is included despite living outside run_dq_analysis
    because it determines the 'house' column every Atamis check's population
    and results depend on, but is called from load_data() rather than from
    run_dq_analysis itself — so a change there previously didn't bust the
    per-check cache at all. This was found the hard way: two consecutive
    house-derivation fixes (Joint resolved via commitments, not a name match;
    resolving contract-level ambiguity) changed which contracts land in which
    house without invalidating a single cached check result, so the DQ
    scorecard kept serving stale pre-fix numbers indefinitely while
    get_failing_records (which never caches) correctly showed the current,
    much smaller result — exactly the discrepancy that surfaced this gap.

    _build_unit4_contract_refs is included for the same reason: it determines
    the population UNIT4_COMMIT_NOT_IN_CONTRACTS runs against (HOC from
    unit4_commitments, HOL from agldimvalue's Contract Number dimension), and
    is also called from load_data() rather than run_dq_analysis.

    _atamis_filter_open_only and _atamis_open_contract_refs are included for
    the same class of gap — they're called FROM run_dq_analysis (so their
    call sites are covered), but as separate functions their own bodies
    aren't part of run_dq_analysis's own source text, so an edit to just
    their logic wouldn't otherwise bust the cache either.
    """
    global _ENGINE_SIG_CACHE
    if _ENGINE_SIG_CACHE is None:
        try:
            src = (
                _inspect.getsource(run_dq_analysis)
                + _inspect.getsource(_derive_atamis_houses)
                + _inspect.getsource(_build_unit4_contract_refs)
                + _inspect.getsource(_atamis_filter_open_only)
                + _inspect.getsource(_atamis_open_contract_refs)
            )
        except Exception:
            src = str(os.path.getmtime(os.path.abspath(__file__)))
        _ENGINE_SIG_CACHE = _hashlib.md5(src.encode()).hexdigest()[:8]
    return _ENGINE_SIG_CACHE


def _write_chk(cache_file: str, row: dict) -> None:
    os.makedirs(_CHK_DIR, exist_ok=True)
    # Remove any stale-signature files for this check+house (old check_sig or engine_sig)
    parts = os.path.basename(cache_file).split('__')
    if len(parts) >= 2:
        for old in _glob(os.path.join(_CHK_DIR, f'{parts[0]}__{parts[1]}__*.pkl')):
            if old != cache_file:
                try:
                    os.remove(old)
                except Exception:
                    pass
    with open(cache_file, 'wb') as f:
        _pickle.dump(row, f)


def _parse_dates(series: pd.Series) -> pd.Series:
    """
    Parse a date column that may arrive in three formats:
      1. YYYY-MM-DD          — dummy data from dev scripts
      2. dd/mm/yyyy          — SSMS plain text export
      3. Excel serial float  — e.g. 45626.0 or 45626.614 when Excel
         formats date cells as Text. Floor to integer to discard the
         sub-day time fraction before converting.
    Returns datetime64[us] throughout to avoid pandas dtype mismatches
    between ns and s precision on different Python/pandas versions.
    """
    s = series.astype(str).str.strip().str.split().str[0]
    blank = s.isin(['nan', 'None', 'NaT', ''])
    result = pd.Series(pd.NaT, index=series.index, dtype='datetime64[us]')

    non_blank = s[~blank]
    if non_blank.empty:
        return result

    # Fast path: if ALL non-blank values are numeric, skip straight to Excel
    # serial conversion. On real SSMS/Excel exports every date is an integer
    # serial — this avoids two wasted pd.to_datetime format attempts per column.
    if pd.to_numeric(non_blank, errors='coerce').notna().all():
        numeric = pd.to_numeric(non_blank, errors='coerce')
        in_range = numeric[numeric.between(_EXCEL_MIN, _EXCEL_MAX)]
        if not in_range.empty:
            converted = (_EXCEL_ORIGIN + pd.to_timedelta(in_range.astype(int), unit='D')).dt.as_unit('us')
            result[in_range.index] = converted
        return result

    # 1. ISO YYYY-MM-DD
    iso = pd.to_datetime(s, format='%Y-%m-%d', errors='coerce')
    hit = iso.notna()
    if hit.any():
        result[hit] = iso[hit].dt.as_unit('us')

    # 2. dd/mm/yyyy
    need = result.isna() & ~blank
    if need.any():
        dmy = pd.to_datetime(s[need], format='%d/%m/%Y', errors='coerce')
        hit2 = dmy.notna()
        if hit2.any():
            result[need[need].index[hit2]] = dmy[hit2].dt.as_unit('us')

    # 3. Excel serial — floor removes fractional time component
    need = result.isna() & ~blank
    if need.any():
        numeric = pd.to_numeric(s[need], errors='coerce').dropna()
        in_range = numeric[numeric.between(_EXCEL_MIN, _EXCEL_MAX)]
        if not in_range.empty:
            converted = (_EXCEL_ORIGIN + pd.to_timedelta(in_range.astype(int), unit='D')).dt.as_unit('us')
            result[in_range.index] = converted

    return result


_FORCE_STR_DTYPE = {col: str for col in [
    'apar_id', 'vat_reg_no', 'comp_reg_no', 'bank_account', 'clearing_code',
    'swift', 'iban', 'ext_inv_ref', 'orig_reference', 'voucher_no',
    'account', 'dim_value', 'rel_value',
    # Atamis / Unit4-via-Atamis identifiers — raw CSV headers, applied by column
    # name post-rename, so this also covers the pre-rename originals harmlessly.
    'Contract Reference', 'Contract Id', 'Contract', 'Supplier ID', 'Creditor Ref',
    'Supplier: ID', 'contract_ref', 'u4_contract_id', 'supplier_id', 'creditor_ref',
    'supplier_salesforce_id',
]}


# Maps CLI/SUBDIR domain names to SCOPE_CONFIG keys for check filtering
_SUBDIR_TO_SCOPE = {
    'suppliers': 'ap',
    'customers': 'ar',
    'gl':        'gl',
    'assets':    'assets',
    'po':        'po',
    'atamis':    'atamis',
    'pbf':       'pbf',
}

# User-friendly aliases accepted on the command line
TAB_ALIASES = {
    'suppliers': 'suppliers', 'ap': 'suppliers',
    'customers': 'customers', 'ar': 'customers',
    'gl':        'gl',
    'assets':    'assets',
    'atamis':    'atamis',
}


def load_data(tab=None):
    """Loads CSV files from the data directory and combines HOC/HOL.

    If *tab* is provided (e.g. 'suppliers'), only files for that domain are
    loaded.  Pass None (default) to load everything.
    """
    frames = {}
    _cached = set()  # tables loaded from cache — skip re-processing

    # 'pbf' is the tab name; the actual subdirectory is 'budgets'
    _subdir_key   = 'budgets' if tab == 'pbf' else tab
    names_to_load = set(SUBDIR.get(_subdir_key, [])) if tab else {
        n for names in SUBDIR.values() for n in names
    }
    if tab == 'atamis':
        # Atamis's own checks are inherently cross-domain — house derivation and
        # the cross-system checks (supplier/contract reconciliation) need the
        # Unit4 supplier master and PO data to match against. Without these,
        # `python run_dashboard.py atamis` would load only the four Atamis files
        # and every row would resolve to house='Unknown'. Unlike PO's own
        # tab-scoped mode (documented as a known limitation, left as-is since
        # PO's cross-domain checks are a minority of its suite), Atamis's
        # cross-system checks are the domain's main value, so this is loaded
        # unconditionally in tab-scoped mode rather than left as a gap.
        # gl_dimension_values is needed too — HOL's contract reference isn't
        # in unit4_commitments at all (see _build_unit4_contract_refs), it
        # lives in the GL dimension value list.
        names_to_load |= {'supplier_master', 'po_header', 'po_detail', 'gl_dimension_values'}

    # Tables where house is determined by the filename suffix (_HOC / _HOL),
    # not by the client column. The client column contains internal Unit4 client
    # codes that are NOT 'HOC'/'HOL'.
    house_from_filename = {
        'supplier_master', 'supplier_open_trans', 'supplier_history',
        'customer_master', 'customer_open_trans', 'customer_history',
        'asset_master', 'asset_depreciation', 'asset_balances',
        'asset_trans_flags', 'asset_groups',
        'gl_chart_of_accounts',
        'gl_opening_balances',
        'gl_dimension_config',
        'gl_dimension_values',
        'gl_transact_dimensions',
        'gl_budgets',
        'gl_journals',
        'gl_active_accounts',
        'gl_planner_accounts',
        'po_header',
        'po_detail',
    }

    # Load split files
    split_files = {
        'supplier_master':    'asuheader',
        'supplier_open_trans': 'asutrans',
        'supplier_history':   'asuhistr',
        'customer_master':    'acuheader',
        'customer_open_trans': 'acutrans',
        'customer_history':   'acuhistr',
        'asset_master':        'asset_master',
        'asset_depreciation':  'asset_depreciation',
        'asset_balances':      'asset_balances',
        'asset_trans_flags':   'asset_trans_flags',
        'asset_groups':        'asset_groups',
        'gl_chart_of_accounts':  'aglaccounts',
        'gl_opening_balances':   'aglyearend',
        'gl_dimension_config':   'gl_dimconfig',
        'gl_dimension_values':   'agldimvalue',
        'gl_transact_dimensions': 'gl_transact_dim',
        'gl_budgets':             'gl_budgets',
        'gl_journals':            'gl_journals',
        'gl_active_accounts':     'gl_active_accounts',
        'gl_planner_accounts':    'gl_planner_accounts',
        'po_header':              'apoheader',
        'po_detail':              'apodetail',
    }
    _version = os.environ.get('DASHBOARD_VERSION', '').strip()

    for base_name, table in split_files.items():
        if base_name not in names_to_load:
            continue
        source_paths = [_data_path(base_name, f'_{h}') for h in ['HOC', 'HOL']]
        if not _version and _cache_fresh(table, source_paths):
            frames[table] = pd.read_pickle(_cache_path(table))
            _cached.add(table)
            continue
        dfs = []
        for house in ['HOC', 'HOL']:
            # If a version is specified, prefer the versioned file; fall back to standard.
            if _version:
                versioned = _data_path(base_name, f'_{house}_{_version}')
                path = versioned if os.path.exists(versioned) else _data_path(base_name, f'_{house}')
            else:
                path = _data_path(base_name, f'_{house}')
            if os.path.exists(path):
                df = pd.read_csv(path, low_memory=False, dtype=_FORCE_STR_DTYPE)
                if base_name in house_from_filename:
                    df['house'] = house
                elif 'client' in df.columns:
                    df['house'] = df['client']
                else:
                    df['house'] = house
                dfs.append(df)
        if dfs:
            frames[table] = pd.concat(dfs, ignore_index=True)

    # Load single (non-house-split) Atamis files — one CSV per table, no _HOC/_HOL
    # suffix. House is derived later by _derive_atamis_houses(), not read from the
    # filename, so nothing house-related happens in this loop.
    single_files = {
        'contracts_report':             'atamis_contracts',
        'contract_total_commitments':   'unit4_commitments',
        'contracts_spend_details':      'unit4_spend',
        'supplier_data_report':         'atamis_suppliers',
        'unit4_open_contracts':         'unit4_open_contracts',
        'hol_unit4_spend':              'hol_unit4_spend',
        'budgets_report':               'budgets_report',
    }
    for base_name, table in single_files.items():
        if base_name not in names_to_load:
            continue
        source_path = _data_path(base_name)
        if not _version and _cache_fresh(table, [source_path]):
            frames[table] = pd.read_pickle(_cache_path(table))
            _cached.add(table)
            continue
        if not os.path.exists(source_path):
            continue
        # These are pasted/exported from Atamis, HAIS, and Excel rather than
        # SSMS's own Query Results grid, and have been seen arriving as
        # Windows-1252 (e.g. a curly quote or en-dash in a free-text contract
        # title) rather than UTF-8 — fall back rather than crashing the load.
        try:
            df = pd.read_csv(source_path, low_memory=False, dtype=_FORCE_STR_DTYPE)
        except UnicodeDecodeError:
            df = pd.read_csv(source_path, low_memory=False, dtype=_FORCE_STR_DTYPE, encoding='cp1252')
        _rename_map = _ATAMIS_RENAME.get(table, {}) if table != 'budgets_report' else _BUDGET_RENAME
        df = df.rename(columns=_rename_map)
        # Guard against a real export header not matching any key in the
        # rename map (report-tool prefixes vary, budget report column names may
        # differ slightly between Finance team exports) — fill any expected
        # column that didn't get created with blank rather than letting it
        # KeyError deep in a rule or tab. A genuinely missing field then shows
        # up honestly as a 100% completeness failure instead of crashing the load.
        for expected_col in set(_rename_map.values()):
            if expected_col not in df.columns:
                df[expected_col] = pd.NA
        if table == 'unit4_spend':
            # The extract's first row is a grand-total summary (blank Contract,
            # totals across every contract) — not a real per-contract record.
            df = df[df['u4_contract_id'].notna() & (df['u4_contract_id'].astype(str).str.strip() != '')]
        frames[table] = df.reset_index(drop=True)

    # Process frames that were not loaded from cache
    for table, df in frames.items():
        if table in _cached:
            continue
        # Force ID and registration columns to string to prevent DQ test errors
        string_cols = ['apar_id', 'vat_reg_no', 'comp_reg_no', 'bank_account', 'clearing_code', 'swift', 'iban', 'ext_inv_ref', 'voucher_no', 'account', 'dim_value', 'rel_value',
                       'contract_ref', 'u4_contract_id', 'supplier_id', 'creditor_ref', 'supplier_salesforce_id']
        for col in string_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().replace(['nan', 'None', ''], np.nan)
        
        # GL specific dimensions should be strings
        for i in range(1, 8):
            col = f'dim_{i}'
            if col in df.columns:
                df[col] = df[col].astype(str).replace(['nan', 'None', ''], np.nan)
        
        # Atamis contracts amounts arrive as "GBP45,000.00" — strip the currency
        # prefix before the generic comma-strip/to_numeric pass below handles them
        # like every other numeric column.
        if table == 'atamis_contracts':
            for col in ('total_award_value', 'current_value'):
                if col in df.columns:
                    df[col] = df[col].astype(str).str.replace('GBP', '', regex=False).str.strip()

        # Numeric columns — strip commas from Excel-formatted numbers (e.g. "1,234.56")
        # before any downstream pd.to_numeric calls, otherwise values >= 1000 become NaN
        numeric_cols = ['amount', 'rest_amount', 'cur_amount', 'rest_curr', 'discount',
                        'exch_rate', 'credit_limit', 'pay_delay', 'dc_flag', 'sequence_no',
                        'update_flag', 'total_amount', 'total_cur_amount',
                        # PO-specific numeric columns
                        'arr_amount', 'vow_amount', 'vow_val', 'arr_val', 'invoiced',
                        'cost_amount', 'real_amount', 'forecast', 'com_amount', 'open_flag',
                        'unit_price', 'disc_percent', 'tax_amount', 'tax_percent',
                        'overrun_pct', 'overrun_pct_a', 'overrun_pct_o', 'amend_no',
                        # Atamis / Unit4-via-Atamis numeric columns
                        'total_award_value', 'current_value', 'award_value',
                        'award_amount', 'amount_limit', 'committed_amount', 'posted_amount',
                        'registered_invoices', 'open_requisitions', 'remaining_amount',
                        'posted', 'amount_c',
                        # Budget / PBF numeric columns
                        'gl_actuals', 'orig_budget', 'curr_budget', 'live_forecast',
                        'pfst_budget', 'q1_forecast', 'q2_forecast', 'q3_forecast',
                        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(',', '', regex=False).str.strip(),
                    errors='coerce'
                )

        date_cols = [
            'trans_date', 'due_date', 'voucher_date', 'last_update', 'expired_date', 'last_trans_date',
            'period_from', 'period_to',
            # PO date columns
            'order_date', 'deliv_date', 'confirm_date', 'obs_date', 'rev_del_date',
            # Asset date columns — arrive as Excel serial integers from SSMS/Excel export
            'cap_date_from', 'date_from', 'date_to', 'org_amt_date',
            'at_trans_date', 'max_trans_date', 'min_trans_date',
            'grp_last_update', 'book_last_update',
            # Atamis contracts dates — dd/mm/yyyy, same as every other SSMS export
            'start_date', 'end_date', 'award_date',
        ]
        # agldimvalue: period_from/period_to are YYYYMM integers (e.g. 201202 = period 2 of 2012),
        # not Excel serial dates. Convert to numeric; parse last_update as normal.
        if table == 'agldimvalue':
            for col in ('period_from', 'period_to'):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].astype(str).str.strip(), errors='coerce')
            _date_cols = [c for c in date_cols if c not in ('period_from', 'period_to')]
        elif table == 'gl_journals':
            for col in ('period', 'fiscal_year'):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].astype(str).str.strip(), errors='coerce')
            _date_cols = date_cols
        elif table == 'budgets_report':
            # period (1–15) and year are plain integers, not dates — parse to
            # numeric, explicitly excluded from _parse_dates.
            for col in ('period', 'year'):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].astype(str).str.strip(), errors='coerce')
            _date_cols = [c for c in date_cols if c not in ('period', 'year')]
        elif table in ('asset_master', 'asset_depreciation'):
            # cap_period_from and depr_period are YYYYPP integers, not dates
            _yypp = ('cap_period_from', 'depr_period')
            for col in _yypp:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col].astype(str).str.strip(), errors='coerce')
            _date_cols = [c for c in date_cols if c not in _yypp]
        else:
            _date_cols = date_cols
        for col in _date_cols:
            if col in df.columns:
                df[col] = _parse_dates(df[col])
        frames[table] = df

    # Save newly processed frames to cache for fast reload next run
    os.makedirs(_CACHE_DIR, exist_ok=True)
    for table, df in frames.items():
        if table not in _cached:
            try:
                df.to_pickle(_cache_path(table))
            except Exception:
                pass

    # Always recompute Atamis house assignment fresh, even for cache-hit frames —
    # it depends on asuheader (and, for unit4_spend, unit4_commitments), which
    # may have changed independently of the Atamis files' own cache freshness.
    # Cheap (a few thousand rows), so not worth its own cache entry.
    if any(t in frames for t in ATAMIS_TABLES):
        _derive_atamis_houses(frames)
        _build_unit4_contract_refs(frames)

    # Budget house assignment — much simpler than Atamis: the Recharge column
    # directly contains 'HOC' or 'HOL', so no cross-reference to asuheader is needed.
    # Still recomputed fresh rather than relying on the cached frame, for the same
    # reason as Atamis: a cache hit on budgets_report would have arrived without a
    # 'house' column if it was built before this derivation existed.
    if 'budgets_report' in frames:
        _derive_budget_houses(frames)

    return frames

def get_dq_checks():
    """Returns a list of DQ check definitions based on SQL requirements."""
    checks = []
    checks.extend(get_ap_checks())
    checks.extend(get_ar_checks())
    checks.extend(get_asset_checks())
    checks.extend(get_gl_checks())
    checks.extend(get_po_checks())
    checks.extend(get_atamis_checks())
    checks.extend(get_budget_checks())
    return checks

def run_dq_analysis(frames, tab=None):
    """Executes DQ checks and returns a summary DataFrame.

    If *tab* is provided, only checks for that domain's scope IDs are run.
    Each (check_id, house) result row is cached individually in
    data/.cache/checks/.  Editing one rule re-runs only that check — all other
    checks load from cache instantly.  Cache is invalidated per-check by:
      - a change to data_engine.py (population filters / scoring logic)
      - a change to the frame pickle for the check's source or joined table
      - any change to the check's own definition (lambda source, severity, etc.)
    """
    from dashboard.core.config import SCOPE_CONFIG
    results = []
    checks = get_dq_checks()
    if tab:
        scope_key = _SUBDIR_TO_SCOPE.get(tab)
        if scope_key and scope_key in SCOPE_CONFIG:
            allowed = set(SCOPE_CONFIG[scope_key]['scope_ids'])
            checks = [c for c in checks if c[1] in allowed]

    # Engine sig: hash of run_dq_analysis source only.  Editing get_failing_records
    # or get_check_columns won't change this, so those edits don't bust the cache.
    esig = _engine_sig()
    
    n_hit = n_miss = 0
    for check_tuple in checks:
        check_id, scope_id, obj, dim, sev, desc, intent, rem, table, joined_table, logic, filter_func = check_tuple
        if table not in frames:
            continue

        df_table = frames[table]
        sig       = _chk_sig(check_tuple)
        rel_fps   = [_cache_path(table)]
        if joined_table and joined_table in frames:
            rel_fps.append(_cache_path(joined_table))
        if 'unit4_contract_refs' in (table, joined_table):
            # Synthetic frame, never pickled itself (whether it's this check's
            # own source table or, for ATAMIS_CONTRACT_NOT_IN_COMMITMENTS, the
            # joined_table) — track its two real underlying sources so a
            # change to either one busts this check's per-check cache (mirrors
            # the joined_table pattern above).
            rel_fps.append(_cache_path('unit4_commitments'))
            rel_fps.append(_cache_path('agldimvalue'))

        _dq_version = os.environ.get('DASHBOARD_VERSION', '').strip()
        _houses = ATAMIS_HOUSES if table in ATAMIS_TABLES else CLIENTS
        for house in _houses:
            # Per-check cache — load if fresh, skip the run entirely.
            # Bypass cache entirely when a data version is active so versioned
            # files are always used rather than serving stale cached results.
            cf = _chk_file(check_id, house, sig, esig)
            if not _dq_version and _chk_fresh(cf, rel_fps):
                try:
                    results.append(_read_chk(cf))
                    n_hit += 1
                    continue
                except Exception:
                    pass  # corrupt entry — fall through and recompute

            # Determine population based on table and check type
            if table == 'asuheader':
                if house == 'HOL':
                    mask = (df_table['house'] == house) & (df_table['status'] == 'N')
                    mask &= df_table['client'].isin(SupplierConfig.HOL_CLIENTS)
                else:
                    mask = (df_table['house'] == house) & (df_table['status'] != 'C')
                    mask &= df_table['client'].isin(SupplierConfig.HOC_CLIENTS)
                    mask &= ~df_table['apar_id'].astype(str).str[:2].isin(['89', '99'])
                    mask &= ~(df_table['apar_name'].astype(str).str.strip().str.upper() == 'SZSINGLES')
                h_df = df_table[mask]
            elif table == 'acuheader':
                mask = (df_table['house'] == house) & (df_table['status'] != 'C')
                if house == 'HOC':
                    mask &= df_table['client'].isin(SupplierConfig.HOC_CLIENTS)
                elif house == 'HOL':
                    mask &= df_table['client'].isin(SupplierConfig.HOL_CLIENTS)
                h_df = df_table[mask]
            elif table in ['asutrans', 'acutrans']:
                mask = (df_table['house'] == house) & (df_table['status'] != 'C')
                if house == 'HOC':
                    mask &= df_table['client'].isin(SupplierConfig.HOC_CLIENTS)
                elif house == 'HOL':
                    mask &= df_table['client'].isin(SupplierConfig.HOL_CLIENTS)
                h_df = df_table[mask]
            elif table in ['asuhistr', 'acuhistr']:
                mask = df_table['house'] == house
                if house == 'HOC':
                    mask &= df_table['client'].isin(SupplierConfig.HOC_CLIENTS)
                elif house == 'HOL':
                    mask &= df_table['client'].isin(SupplierConfig.HOL_CLIENTS)
                h_df = df_table[mask]
            elif table == 'aglaccounts':
                # GL_ACC_DUP_CODE checks all accounts; all other CoA checks use active only
                if check_id == 'GL_ACC_DUP_CODE':
                    h_df = df_table[df_table['house'] == house]
                else:
                    h_df = df_table[(df_table['house'] == house) & (df_table['status'] == 'N')]
            elif table == 'gl_dimconfig':
                # GL_DIM_ATTR_GL_EMPTY is scoped to GL-mapped positions so the denominator
                # is GL attributes only — not inflated by the 650+ out-of-scope X attributes.
                if check_id == 'GL_DIM_ATTR_GL_EMPTY':
                    _gl = {'0','1','2','3','4','5','6','7'}
                    h_df = df_table[
                        (df_table['house'] == house) &
                        df_table['dim_position'].astype(str).str.strip().isin(_gl)
                    ]
                else:
                    h_df = df_table[df_table['house'] == house]
            elif table == 'agldimvalue':
                # SQL already filters to status = 'N'; GL_DIM_DUP checks full population
                # for duplicates, all others use the same house-filtered active rows.
                h_df = df_table[df_table['house'] == house]
            elif table == 'gl_transact_dim':
                h_df = df_table[df_table['house'] == house]
            elif table == 'gl_budgets':
                h_df = df_table[df_table['house'] == house]
            elif table == 'gl_journals':
                # SQL already filters to status IS NULL OR status = '' (actual postings only)
                h_df = df_table[df_table['house'] == house]
            elif table in ['asset_master', 'asset_depreciation', 'asset_balances', 'asset_trans_flags']:
                h_df = df_table[df_table['house'] == house]
            elif table == 'apoheader':
                if check_id == 'PO_DUP_HEADER':
                    h_df = df_table[df_table['house'] == house]
                elif check_id == 'PO_STUCK_NOT_ORDERED':
                    h_df = df_table[(df_table['house'] == house) & (df_table['status'] == 'N')]
                elif check_id == 'PO_FINISHED_WITH_BALANCE':
                    h_df = df_table[(df_table['house'] == house) & (df_table['status'] == 'F')]
                elif check_id == 'PO_INACTIVE_SUPPLIER':
                    h_df = df_table[(df_table['house'] == house) & (df_table['status'].isin(['O', 'N', 'A']))]
                else:
                    h_df = df_table[(df_table['house'] == house) & (df_table['status'] != 'T')]
            elif table == 'apodetail':
                if check_id in ('PO_LINE_INVOICED_AHEAD_OF_RECEIPT', 'PO_ARR_EXCEEDS_AMOUNT',
                                 'PO_LINE_NEG_AMOUNT', 'PO_LINE_VOW_CALC_MISMATCH'):
                    h_df = df_table[(df_table['house'] == house) & (df_table['status'].isin(['O', 'N', 'A']))]
                elif check_id == 'PO_LINE_AMENDED_VALUE_MISMATCH':
                    h_df = df_table[(df_table['house'] == house) & (pd.to_numeric(df_table['amend_no'], errors='coerce').fillna(0) > 0)]
                elif check_id in _PO_UNMATCHED_RECEIPT_CHECKS:
                    h_df = _po_unmatched_receipt_population(df_table, house)
                else:
                    h_df = df_table[df_table['house'] == house]
            elif table in ATAMIS_TABLES:
                if check_id == 'ATAMIS_SUPPLIER_NOT_IN_UNIT4':
                    h_df = _atamis_existence_population(df_table, house, 'creditor_ref')
                elif check_id == 'UNIT4_COMMIT_SUPPLIER_ORPHAN':
                    h_df = _atamis_existence_population(df_table, house, 'supplier_id')
                elif check_id == 'UNIT4_SPEND_CONTRACT_ORPHAN':
                    h_df = _atamis_existence_population(df_table, house, 'u4_contract_id')
                elif check_id == 'ATAMIS_CONTRACT_REF_NOT_IN_PO':
                    # PO is HoC-only, so an HOL contract has no PO to match against —
                    # restricting the population to HOC means the HOL iteration of
                    # this check naturally yields zero rows and is skipped entirely.
                    # ('Joint' never appears as a resolved house any more — see
                    # _derive_atamis_houses — so it doesn't need listing here.)
                    h_df = df_table[df_table['house'] == house]
                    h_df = h_df[(h_df['house'] == 'HOC') & ~_atamis_blank(h_df['contract_ref'])]
                elif check_id in ('ATAMIS_CONTRACT_NOT_IN_COMMITMENTS', 'UNIT4_COMMIT_NOT_IN_CONTRACTS'):
                    # Blank contract_ref/u4_contract_id is each table's own
                    # NO_REF-style completeness check's concern — excluding it
                    # here avoids double-counting the same row (a blank ref
                    # trivially "has no matching commitment/contract" but
                    # that's not a meaningful signal on top of already being
                    # flagged as incomplete).
                    ref_col = 'contract_ref' if check_id == 'ATAMIS_CONTRACT_NOT_IN_COMMITMENTS' else 'u4_contract_id'
                    h_df = df_table[df_table['house'] == house]
                    h_df = h_df[~_atamis_blank(h_df[ref_col])]
                else:
                    h_df = df_table[df_table['house'] == house]
                if check_id in _ATAMIS_OPEN_ONLY_CHECKS:
                    h_df = _atamis_filter_open_only(h_df, table, frames)
            elif table == 'budgets_report':
                h_df = df_table[df_table['house'] == house]
            else:
                h_df = df_table[df_table['house'] == house]

            total = len(h_df)
            if total == 0:
                continue

            # Run check
            try:
                import inspect
                sig = inspect.signature(filter_func)
                if 'frames' in sig.parameters:
                    mask = filter_func(h_df, frames)
                else:
                    mask = filter_func(h_df)
                
                failing_df = h_df[mask]
                failing = len(failing_df)
            except Exception as e:
                print(f"Error running check {check_id} for {house}: {e}")
                failing = 0
            
            passing = total - failing
            error_rate = round((failing / total * 100), 1) if total > 0 else 0.0
            pass_rate = round(100.0 - error_rate, 1)
            green_t, amber_t = RAG_THRESHOLDS.get(sev, (5, 15))
            rag = 'Green' if error_rate <= green_t else ('Amber' if error_rate <= amber_t else 'Red')
            
            row = {
                'check_id': check_id,
                'scope_id': scope_id,
                'object': obj,
                'house': house,
                'dimension': dim,
                'severity': sev,
                'description': desc,
                'intent': intent,
                'total': int(total),
                'failing': int(failing),
                'passing': int(passing),
                'error_rate': error_rate,
                'pass_rate': pass_rate,
                'rag': rag,
                'remediation': rem,
                'table': table,
                'joined_table': joined_table,
                'technical_logic': logic
            }
            results.append(row)
            _write_chk(cf, row)
            n_miss += 1


    if n_hit or n_miss:
        print(f"  DQ analysis: {n_hit} cached, {n_miss} recomputed")
    return pd.DataFrame(results)

def get_check_columns():
    """Returns a map of check_id to the columns relevant for that check."""
    return {

        # Purchase Orders (apoheader / apodetail)
        'PO_NO_SUPPLIER':             ['order_id', 'apar_id', 'status'],
        'PO_INVALID_ORDER_DATE':      ['order_id', 'order_date', 'status'],
        'PO_BAD_EXCH_RATE':           ['order_id', 'currency', 'exch_rate', 'status'],
        'PO_STUCK_NOT_ORDERED':       ['order_id', 'apar_id', 'status', 'order_date'],
        'PO_FINISHED_WITH_BALANCE':   ['order_id', 'apar_id', 'status', 'SUM(amount)', 'SUM(arr_amount)', 'SUM(invoiced)', 'uninvoiced_pct'],
        'PO_LINE_NEG_AMOUNT':         ['order_id', 'line_no', 'amount', 'status'],
        'PO_DUP_LINE':                ['client', 'order_id', 'line_no', 'sequence_no', 'status'],
        'PO_HDR_LINE_CONTRACT_MISMATCH': ['order_id', 'line_no', 'contract_id'],
        'PO_ORPHANED_SUPPLIER':        ['order_id', 'apar_id', 'status', 'client'],
        'PO_INACTIVE_SUPPLIER':        ['order_id', 'apar_id', 'status'],
        'PO_LINE_ORPHAN_ACCOUNT':      ['order_id', 'line_no', 'account'],
        'PO_LINE_CLOSED_ACCOUNT':      ['order_id', 'line_no', 'account', 'status'],
        'PO_DUP_HEADER':               ['client', 'order_id', 'status'],
        'PO_FUTURE_ORDER_DATE':        ['order_id', 'order_date', 'status'],
        'PO_ARR_EXCEEDS_AMOUNT':       ['order_id', 'line_no', 'status', 'amount', 'invoiced'],
        'PO_LINE_NO_CATEGORY':         ['order_id', 'line_no', 'art_gr_id', 'art_gr_description'],
        'PO_LINE_INVOICED_AHEAD_OF_RECEIPT': ['order_id', 'line_no', 'status', 'vow_amount', 'invoiced'],
        'PO_LINE_AMENDED_VALUE_MISMATCH': ['order_id', 'line_no', 'amend_no', 'com_amount', 'amount'],
        'PO_LINE_VOW_CALC_MISMATCH':  ['order_id', 'line_no', 'status', 'vow_amount', 'vow_val', 'unit_price'],
        'PO_LINE_UNINVOICED_RECEIPT_OVER3M':   ['order_id', 'line_no', 'status', 'deliv_date', 'days_since_delivery', 'vow_amount', 'invoiced'],

        # GL Dimension Values (agldimvalue)
        'GL_DIM_DESC_MISSING':   ['dim_value', 'description', 'attribute_id', 'dim_position'],
        'GL_DIM_STALE_DESC':     ['dim_value', 'description', 'attribute_id', 'dim_position'],
        'GL_DIM_PERIOD_MISSING': ['dim_value', 'description', 'period_from', 'period_to', 'attribute_id'],
        'GL_DIM_PERIOD_INV':     ['dim_value', 'description', 'period_from', 'period_to', 'attribute_id'],
        'GL_DIM_ORPHAN_REL':     ['dim_value', 'description', 'rel_value', 'attribute_id', 'dim_position'],
        'GL_DIM_SELF_REF':       ['dim_value', 'description', 'rel_value', 'attribute_id', 'dim_position'],
        'GL_DIM_DUP':            ['client', 'attribute_id', 'dim_value', 'description'],
        'GL_DIM_DEEP_HIERARCHY': ['dim_value', 'description', 'rel_value', 'attribute_id', 'dim_position'],
        'GL_DIM_POST_SUMMARY':   ['client', 'dim_position', 'dim_value'],

        # GL Dimension Attributes (gl_dimconfig)
        'GL_DIM_ATTR_GL_EMPTY':      ['attribute_id', 'description', 'dim_position', 'active', 'closed', 'total_values'],
        'GL_DIM_ATTR_DESC_MISSING':  ['attribute_id', 'description', 'dim_position'],

        # GL Journals (gl_journals / agltransact)
        'GL_JNL_VOUCHER_MISSING': ['client', 'sequence_no', 'account', 'period', 'voucher_type', 'amount'],
        'GL_JNL_ACCT_MISSING':   ['client', 'voucher_no', 'sequence_no', 'period', 'voucher_type', 'amount'],
        'GL_JNL_AMT_MISSING':    ['client', 'voucher_no', 'sequence_no', 'account', 'period', 'voucher_type'],
        'GL_JNL_USER_MISSING':   ['user_id', 'voucher_no', 'account', 'period', 'voucher_type'],
        'GL_JNL_DATE_FUTURE':    ['trans_date', 'voucher_no', 'account', 'period', 'voucher_type', 'amount'],
        'GL_JNL_APAR_MISMATCH':  ['apar_id', 'apar_type', 'voucher_no', 'account', 'period', 'voucher_type'],
        'GL_JNL_DUP_KEY':        ['client', 'voucher_no', 'sequence_no', 'account', 'period', 'amount'],
        'GL_JNL_ACCT_ORPHAN':    ['account', 'voucher_no', 'sequence_no', 'period', 'voucher_type', 'amount'],
        'GL_JNL_ACCT_CLOSED':    ['account', 'voucher_no', 'sequence_no', 'period', 'voucher_type', 'amount'],

        # GL Opening Balances
        'GL_BAL_AMT_MISSING':     ['client', 'account', 'period', 'dim_1', 'voucher_type', 'voucher_no'],
        'GL_BAL_ORPHAN_ACC':      ['client', 'account', 'period', 'dim_1', 'amount'],
        'GL_BAL_ORPHAN_DIM':      ['client', 'account', 'period', 'dim_1', 'amount'],
        'GL_BUD_AMT_MISSING':     ['client', 'account', 'period', 'dim_1', 'voucher_type', 'voucher_no'],
        'GL_BUD_ORPHAN_ACC':      ['client', 'account', 'period', 'dim_1', 'amount'],
        'GL_BUD_ORPHAN_DIM':      ['client', 'account', 'period', 'dim_1', 'amount'],

        # GL Chart of Accounts
        'GL_ACC_DESC_MISSING':    ['account', 'description', 'account_type', 'status'],
        'GL_ACC_GRP_MISSING':     ['account', 'account_grp', 'account_type', 'status'],
        'GL_ACC_RESBAL_MISSING':  ['account', 'res_bal', 'account_type', 'status'],
        'GL_ACC_RULE_MISSING':    ['account', 'account_rule', 'account_type', 'status'],
        'GL_ACC_RESBAL_INVALID':  ['account', 'res_bal', 'account_type'],
        'GL_ACC_TYPE_INVALID':    ['account', 'account_type', 'res_bal'],
        'GL_ACC_PERIOD_INV':      ['account', 'period_from', 'period_to'],
        'GL_ACC_STALE_N':         ['account', 'period_from', 'period_to', 'status'],
        'GL_ACC_DUP_CODE':        ['client', 'account', 'description', 'status'],
        'GL_ACC_DUP_DESC':        ['client', 'account', 'account_grp', 'description', 'period_from', 'period_to', 'account_type', 'status'],
        'GL_DIM_DUP_DESC':        ['client', 'attribute_id', 'dim_value', 'description', 'account_grp'],
        'GL_ACC_NO_ACTIVITY':     ['account', 'description', 'account_grp', 'res_bal', 'account_type'],

        # Suppliers
        'SUP_VAT_MISSING': ['vat_reg_no', 'apar_gr_id', 'status'],
        'SUP_SA_VAT_MISSING': ['vat_reg_no', 'apar_gr_id', 'status'],
        'SUP_COMP_REG_MISSING': ['comp_reg_no', 'apar_gr_id', 'status'],
        'SUP_SA_COMP_REG_MISSING': ['comp_reg_no', 'apar_gr_id', 'status'],
        'SUP_TERMS_MISSING': ['terms_id'],
        'SUP_PAY_METHOD_MISSING': ['pay_method'],
        'SUP_CURRENCY_MISSING': ['currency'],
        'SUP_BANK_MISSING': ['bank_account'],
        'SUP_SORT_IBAN_MISSING': ['clearing_code', 'iban', 'pay_method'],
        'SUP_SWIFT_MISSING': ['swift', 'iban'],
        'SUP_ADDR_MISSING': ['address'],
        'SUP_PLACE_MISSING': ['place'],
        'SUP_ZIP_MISSING': ['zip_code'],
        'SUP_ZIP_FORMAT': ['zip_code', 'country_code'],
        'SUP_VAT_FORMAT': ['vat_reg_no', 'apar_gr_id'],
        'SUP_COMP_REG_FORMAT': ['comp_reg_no'],
        'SUP_SORT_FORMAT': ['clearing_code'],
        'SUP_BANK_FORMAT': ['bank_account'],
        'SUP_SWIFT_FORMAT': ['swift'],
        'SUP_WF_STUCK': ['wf_state'],
        'SUP_BACS_NO_BANK': ['pay_method', 'bank_account', 'clearing_code'],
        'SUP_INT_NO_IBAN': ['pay_method', 'iban'],
        'SUP_CLIENT_APAR_DUP': ['client', 'apar_id'],
        'SUP_NAME_DUP':      ['apar_name', 'address', 'zip_code', 'client'],
        'SUP_NAME_DUP_ANY':  ['apar_name', 'address', 'zip_code', 'client'],
        'SUP_VAT_DUP':       ['vat_reg_no', 'client'],
        'SUP_BANK_SORT_DUP': ['bank_account', 'clearing_code', 'client'],
        'SUP_BANK_DUP': ['bank_account', 'clearing_code', 'vat_reg_no', 'client'],
'SUP_STALE': ['last_update'],
        'SUP_DORMANT': ['last_update', 'status'],
        'SUP_SUNDRY': ['apar_once'],
        
        # AP Invoices
        'AP_DUE_DATE_MISSING': ['due_date'],
        'AP_EXT_REF_MISSING': ['ext_inv_ref'],
        'AP_AMOUNT_MISSING': ['amount'],
        'AP_PO_CONTRACT_MISSING': ['order_id', 'contract_id'],
        'AP_FX_NO_RATE': ['currency', 'exch_rate'],
        'AP_CN_NO_REF': ['voucher_type', 'orig_reference'],
        'AP_NEG_INV': ['amount', 'voucher_type'],
        'AP_FX_NO_CUR_AMT': ['currency', 'cur_amount'],
        'AP_TRANS_KEY_DUP': ['client', 'apar_id', 'voucher_no', 'sequence_no'],
        'AP_REST_ZERO': ['rest_amount', 'status'],
        'AP_REST_OVER_AMT': ['rest_amount', 'amount'],
        'AP_OVERDUE': ['due_date'],
        'AP_WF_STUCK': ['wf_state'],
        'AP_EXT_REF_DUP': ['ext_inv_ref', 'apar_id'],
        'AP_NET_NEGATIVE_SUP': ['rest_amount', 'apar_id'],
        'AP_ORPHANED_CREDITS': ['voucher_type', 'orig_reference', 'voucher_no'],
        'AP_ORPHANED_TRANS': ['apar_id'],
        'AP_TRANS_SUP_CLOSED': ['apar_id', 'status'],
        
        # AP History
        'HIS_REST_NOT_ZERO': ['rest_amount'],
        'HIS_DATE_MISSING': ['trans_date'],
        'HIS_CN_NO_REF': ['voucher_type', 'orig_reference'],
        'HIS_DUP': ['voucher_no', 'sequence_no', 'client'],
        'HIS_ORPHANED': ['apar_id'],

        # Customers
        'CUS_VAT_MISSING':          ['vat_reg_no', 'status'],
        'CUS_COMP_REG_MISSING':     ['comp_reg_no', 'status'],
        'CUS_TERMS_MISSING':        ['terms_id'],
        'CUS_PAY_METHOD_MISSING':   ['pay_method'],
        'CUS_CURRENCY_MISSING':     ['currency'],
        'CUS_CREDIT_LIMIT_MISSING': ['credit_limit'],
        'CUS_VAT_FORMAT':           ['vat_reg_no'],
        'CUS_COMP_REG_FORMAT':      ['comp_reg_no'],
        'CUS_CREDIT_NONZERO':       ['credit_limit'],
        'CUS_PARENT_ORPHAN':        ['apar_id', 'main_apar_id'],
        'CUS_EXPIRED_ACTIVE':       ['expired_date', 'status'],
        'CUS_COLLECT_ACTIVE':       ['collect_flag'],
        'CUS_NAME_DUP':             ['apar_name', 'client'],
        'CUS_CLIENT_APAR_DUP':      ['client', 'apar_id'],
        'CUS_DORMANT':              ['last_update', 'status'],

        # AR Invoices
        'AR_DUE_DATE_MISSING':          ['due_date'],
        'AR_EXT_REF_MISSING':           ['ext_inv_ref'],
        'AR_AMOUNT_MISSING':            ['amount'],
        'AR_ORDER_CONTRACT_MISSING':    ['order_id', 'contract_id'],
        'AR_FX_NO_RATE':                ['currency', 'exch_rate'],
        'AR_CN_NO_REF':                 ['voucher_type', 'orig_reference'],
        'AR_FX_NO_CUR_AMT':             ['currency', 'cur_amount'],
        'AR_NEG_INV':                   ['amount', 'voucher_type'],
        'CUS_INTRULE_MISSING':          ['intrule_id'],
        'AR_HIGH_REMINDER':             ['rem_level', 'due_date', 'rest_amount'],
        'AR_NET_NEG_BAL':               ['apar_id', 'rest_amount'],
        'AR_REST_ZERO':                 ['rest_amount', 'status'],
        'AR_REST_OVER_AMT':             ['rest_amount', 'amount'],
        'AR_OVERDUE':                   ['due_date'],
        'AR_TRANS_KEY_DUP':             ['client', 'apar_id', 'voucher_no', 'sequence_no'],
        'AR_EXT_REF_DUP':               ['ext_inv_ref', 'apar_id'],
        'AR_ORPHANED_TRANS':            ['apar_id'],
        'AR_TRANS_CUS_CLOSED':          ['apar_id', 'status'],

        # AR History
        'AR_HIS_REST_NOT_ZERO': ['rest_amount'],
        'AR_HIS_DATE_MISSING':  ['trans_date'],
        'AR_HIS_CN_NO_REF':     ['voucher_type', 'orig_reference'],
        'AR_HIS_DUP':           ['voucher_no', 'sequence_no', 'client'],
        'AR_HIS_ORPHANED':      ['apar_id'],

        # Asset Register - Master
        'DQ-AM-C01': ['asset_id'],
        'DQ-AM-C02': ['description', 'status'],
        'DQ-AM-C03': ['asset_group', 'status'],
        'DQ-AM-C04': ['date_from', 'status'],
        'DQ-AM-C05': ['org_amount', 'cap_date_from'],
        'DQ-AM-C06': ['cap_date_from', 'cap_flag'],
        'DQ-AM-V01': ['status'],
        'DQ-AM-V03': ['base_amount'],
        'DQ-AM-V04': ['date_from', 'date_to'],
        'DQ-AM-V05': ['cap_date_from', 'date_from'],
        'DQ-AM-V06': ['org_amt_date', 'cap_date_from'],
        'DQ-AM-T01': ['last_update'],
        'DQ-AM-K01': ['date_to', 'status'],
        'DQ-AM-K03': ['org_amt_date', 'org_amount'],
        'DQ-AM-K04': ['grant_flag', 'dim_1'],
        'DQ-AM-D01': ['asset_id', 'description', 'asset_group', 'status'],
        'DQ-AM-D02': ['description', 'asset_group', 'cap_date_from', 'org_amount'],
        'DQ-AM-R01': ['asset_id'],
        'DQ-AM-R02': ['asset_id'],
        'DQ-AM-R04': ['parent_asset', 'asset_id'],
        'DQ-AM-R05': ['apar_id'],

        # Asset Register - Depreciation
        'DQ-AD-C01': ['asset_id'],
        'DQ-AD-C02': ['depr_book_id'],
        'DQ-AD-C03': ['depr_method'],
        'DQ-AD-C04': ['lifetime', 'depr_method'],
        'DQ-AD-C05': ['depr_percent', 'depr_method'],
        'DQ-AD-C06': ['cap_date_from', 'cap_flag'],
        'DQ-AD-C07': ['depr_period'],
        'DQ-AD-V01': ['depr_method'],
        'DQ-AD-V02': ['status'],
        'DQ-AD-V03': ['depr_percent'],
        'DQ-AD-V04': ['lifetime', 'depr_method'],
        'DQ-AD-V05': ['date_from', 'date_to'],
        'DQ-AD-V06': ['cap_date_from', 'date_from'],
        'DQ-AD-V07': ['depr_percent'],
        'DQ-AD-T01': ['last_update'],
        'DQ-AD-K01': ['date_to', 'status'],
        'DQ-AD-K02': ['depr_period'],
        'DQ-AD-K03': ['switch', 'depr_method'],
        'DQ-AD-K05': ['res_value', 'base_amount'],
        'DQ-AD-D01': ['client', 'asset_id', 'depr_book_id', 'status', 'depr_method', 'lifetime'],
        'DQ-AD-X01': ['asset_id'],
        'DQ-AD-X02': ['asset_id', 'status'],
        'DQ-AD-X03': ['depr_book_id', 'cap_date_from', 'status'],
        'DQ-AD-X04': ['res_value', 'org_amount'],
        'DQ-AD-X05': ['asset_id', 'depr_book_id'],

        # Asset Register - Balances
        'DQ-AB-C01': ['asset_id'],
        'DQ-AB-C02': ['depr_book_id'],
        'DQ-AB-C03': ['trans_type'],
        'DQ-AB-C04': ['total_amount'],
        'DQ-AB-V01': ['trans_type'],
        'DQ-AB-V02': ['total_amount', 'trans_type'],
        'DQ-AB-V03': ['max_trans_date'],
        'DQ-AB-K02': ['trans_type'],
        'DQ-AB-K03': ['trans_type'],
        'DQ-AB-X01': ['asset_id'],
        'DQ-AB-X02': ['asset_id', 'depr_book_id'],
        'DQ-AB-X03': ['asset_id', 'status'],

        # Asset Register - Flags
        'DQ-AF-X01': ['trans_type', 'status'],
        'DQ-AF-X02': ['trans_type', 'trans_date', 'date_to'],
        'DQ-AF-X03': ['trans_type', 'amount'],
        'DQ-AF-X04': ['trans_date'],
        'DQ-AF-X05': ['trans_type', 'asset_id'],

        # Asset Groups & Configuration
        'DQ-AG-C01': ['asset_group'],
        'DQ-AG-C02': ['description', 'grp_status'],
        'DQ-AG-C03': ['depr_book_id'],
        'DQ-AG-C04': ['depr_method', 'grp_status', 'book_status'],
        'DQ-AG-C05': ['lifetime', 'depr_method'],
        'DQ-AG-C06': ['depr_percent', 'depr_method'],
        'DQ-AG-V01': ['depr_method'],
        'DQ-AG-V02': ['grp_status'],
        'DQ-AG-V03': ['book_status'],
        'DQ-AG-V04': ['depr_percent'],
        'DQ-AG-V05': ['lifetime', 'depr_method'],
        'DQ-AG-K01': ['book_status', 'grp_status'],
        'DQ-AG-D02': ['asset_group', 'description', 'grp_status', 'depr_method', 'lifetime'],
        'DQ-AG-X01': ['asset_group'],
        'DQ-AG-X03': ['depr_method', 'asset_group'],
        'DQ-AG-X04': ['lifetime', 'asset_group'],

        # Atamis Contracts (atamis_contracts / contracts_report)
        'ATAMIS_CONTRACT_NO_REF':        ['contract_ref', 'contract_title', 'organisation'],
        'ATAMIS_CONTRACT_NO_SUPPLIER':   ['contract_ref', 'supplier_name', 'organisation'],
        'ATAMIS_CONTRACT_NO_DATES':      ['contract_ref', 'start_date', 'end_date'],
        'ATAMIS_CONTRACT_ORG_INVALID':   ['contract_ref', 'organisation'],
        'ATAMIS_CONTRACT_DATE_INVALID':  ['contract_ref', 'start_date', 'end_date'],
        'ATAMIS_CONTRACT_DUP_REF':       ['contract_ref', 'contract_title', 'organisation', 'supplier_name'],
        'ATAMIS_CONTRACT_REF_NOT_IN_PO': ['contract_ref', 'contract_title', 'organisation'],
        'ATAMIS_CONTRACT_NOT_IN_COMMITMENTS': ['contract_ref', 'contract_title', 'organisation'],
        'ATAMIS_CONTRACT_VALUE_MISMATCH':     ['contract_ref', 'contract_title', 'total_award_value', 'award_amount'],
        'ATAMIS_CONTRACT_DATE_MISMATCH':      ['contract_ref', 'contract_title', 'start_date', 'end_date', 'date_from', 'date_to'],

        # Atamis Suppliers (atamis_suppliers / supplier_data_report)
        'ATAMIS_SUPPLIER_NO_CREDITOR_REF':   ['supplier_name', 'creditor_ref', 'supplier_salesforce_id'],
        'ATAMIS_SUPPLIER_DUP_CREDITOR_REF':  ['creditor_ref', 'supplier_name'],
        'ATAMIS_SUPPLIER_NOT_IN_UNIT4':      ['creditor_ref', 'supplier_name'],

        # Contract Commitments (unit4_commitments / contract_total_commitments — Unit4)
        'UNIT4_COMMIT_NO_SUPPLIER_ID':      ['u4_contract_id', 'contract_title', 'supplier_name'],
        'UNIT4_COMMIT_DATE_INVALID':        ['u4_contract_id', 'date_from', 'date_to'],
        'UNIT4_COMMIT_REMAINING_MISMATCH':  ['u4_contract_id', 'amount_limit', 'remaining_amount'],
        'UNIT4_COMMIT_DUP_ID':              ['u4_contract_id', 'contract_title', 'supplier_id'],
        'UNIT4_COMMIT_SUPPLIER_ORPHAN':     ['u4_contract_id', 'supplier_id', 'supplier_name'],
        'UNIT4_COMMIT_OVERSPEND':           ['u4_contract_id', 'amount_limit', 'posted_amount', 'remaining_amount'],
        'UNIT4_COMMIT_NOT_IN_CONTRACTS':    ['u4_contract_id', 'contract_title', 'supplier_name', 'house'],
        'UNIT4_COMMIT_VS_PO_MISMATCH':      ['u4_contract_id', 'contract_title', 'posted_amount', 'invoiced'],

        # Contract Spend (unit4_spend / contracts_spend_details — Unit4)
        'UNIT4_SPEND_CONTRACT_ORPHAN':      ['u4_contract_id', 'posted', 'amount_c'],
        'UNIT4_SPEND_NEGATIVE_POSTED':      ['u4_contract_id', 'posted', 'amount_c'],
        'UNIT4_COMMIT_VS_SPEND_MISMATCH':   ['u4_contract_id', 'posted_amount', 'posted', 'supplier_name'],

        # Budget / PBF (budgets_report)
        'BUD_ACCOUNT_MISSING':       ['account', 'account_desc', 'mipck_l1_desc', 'costc', 'period'],
        'BUD_MIPCK_MISSING':         ['account', 'account_desc', 'mipck_l1', 'costc', 'period'],
        'BUD_HAISCODE_MISSING':      ['account', 'account_desc', 'haiscode', 'costc', 'period'],
        'BUD_COSTC_MISSING':         ['account', 'account_desc', 'costc', 'haiscode', 'period'],
        'BUD_CURR_BUDGET_MISSING':   ['account', 'account_desc', 'haiscode', 'costc', 'period', 'orig_budget', 'curr_budget'],
        'BUD_ORIG_BUDGET_MISSING':   ['account', 'account_desc', 'haiscode', 'costc', 'period', 'orig_budget', 'curr_budget'],
        'BUD_PERIOD_INVALID':        ['account', 'account_desc', 'period', 'year', 'haiscode'],
        'BUD_ACCOUNT_ORPHAN':        ['account', 'account_desc', 'mipck_l1_desc', 'haiscode', 'costc'],
        'BUD_ACCOUNT_CLOSED':        ['account', 'account_desc', 'mipck_l1_desc', 'haiscode', 'costc'],
        'BUD_ACTUALS_NO_CURR_BUDGET': ['account', 'account_desc', 'haiscode', 'costc', 'period', 'gl_actuals', 'curr_budget'],

    }

def get_failing_records(check_id, house, frames, base_cols=None, for_export=False):
    """Retrieves the actual failing records for a specific check and house with enriched context."""
    checks = get_dq_checks()
    check = next((c for c in checks if c[0] == check_id), None)
    if not check:
        return pd.DataFrame()
    
    # Extract based on new Format: (id, scope, object, dimension, severity, desc, intent, remediation, table, joined_table, logic_desc, filter_func)
    _, _, _, _, _, _, _, _, table, joined_table, _, filter_func = check
    if table not in frames:
        return pd.DataFrame()
        
    df_table = frames[table].copy()

    # Apply standard population filters
    if table == 'asuheader':
        if house == 'HOL':
            mask = (df_table['house'] == house) & (df_table['status'] == 'N')
            mask &= df_table['client'].isin(SupplierConfig.HOL_CLIENTS)
        else:
            mask = (df_table['house'] == house) & (df_table['status'] != 'C')
            mask &= df_table['client'].isin(SupplierConfig.HOC_CLIENTS)
            mask &= ~df_table['apar_id'].astype(str).str[:2].isin(['89', '99'])
            mask &= ~(df_table['apar_name'].astype(str).str.strip().str.upper() == 'SZSINGLES')
        h_df = df_table[mask]
    elif table == 'acuheader':
        mask = (df_table['house'] == house) & (df_table['status'] != 'C')
        if house == 'HOC':
            mask &= df_table['client'].isin(SupplierConfig.HOC_CLIENTS)
        elif house == 'HOL':
            mask &= df_table['client'].isin(SupplierConfig.HOL_CLIENTS)
        h_df = df_table[mask]
    elif table in ['asutrans', 'acutrans']:
        mask = (df_table['house'] == house) & (df_table['status'] != 'C')
        if house == 'HOC':
            mask &= df_table['client'].isin(SupplierConfig.HOC_CLIENTS)
        elif house == 'HOL':
            mask &= df_table['client'].isin(SupplierConfig.HOL_CLIENTS)
        h_df = df_table[mask]
    elif table in ['asuhistr', 'acuhistr']:
        mask = df_table['house'] == house
        if house == 'HOC':
            mask &= df_table['client'].isin(SupplierConfig.HOC_CLIENTS)
        elif house == 'HOL':
            mask &= df_table['client'].isin(SupplierConfig.HOL_CLIENTS)
        h_df = df_table[mask]
    elif table == 'aglaccounts':
        if check_id in ['GL_ACC_STALE_N', 'GL_ACC_DUP_CODE']:
            h_df = df_table[df_table['house'] == house]
        else:
            h_df = df_table[(df_table['house'] == house) & (df_table['status'] == 'N')]
    elif table == 'gl_dimconfig':
        if check_id == 'GL_DIM_ATTR_GL_EMPTY':
            _gl = {'0','1','2','3','4','5','6','7'}
            h_df = df_table[
                (df_table['house'] == house) &
                df_table['dim_position'].astype(str).str.strip().isin(_gl)
            ]
        else:
            h_df = df_table[df_table['house'] == house]
    elif table == 'agldimvalue':
        if check_id in ['GL_DIM_DUP', 'GL_DIM_DUP_DESC']:
            h_df = df_table[df_table['house'] == house]
        else:
            h_df = df_table[(df_table['house'] == house) & (df_table['status'] == 'N')]
    elif table == 'gl_journals':
        h_df = df_table[df_table['house'] == house]
    elif table in ['asset_master', 'asset_depreciation', 'asset_balances', 'asset_trans_flags']:
        h_df = df_table[df_table['house'] == house]
    elif table == 'apoheader':
        if check_id == 'PO_DUP_HEADER':
            h_df = df_table[df_table['house'] == house]
        elif check_id == 'PO_STUCK_NOT_ORDERED':
            h_df = df_table[(df_table['house'] == house) & (df_table['status'] == 'N')]
        elif check_id == 'PO_FINISHED_WITH_BALANCE':
            h_df = df_table[(df_table['house'] == house) & (df_table['status'] == 'F')]
        elif check_id == 'PO_INACTIVE_SUPPLIER':
            h_df = df_table[(df_table['house'] == house) & (df_table['status'].isin(['O', 'N', 'A']))]
        else:
            h_df = df_table[(df_table['house'] == house) & (df_table['status'] != 'T')]
    elif table == 'apodetail':
        if check_id in ('PO_LINE_INVOICED_AHEAD_OF_RECEIPT', 'PO_ARR_EXCEEDS_AMOUNT',
                         'PO_LINE_NEG_AMOUNT', 'PO_LINE_VOW_CALC_MISMATCH'):
            h_df = df_table[(df_table['house'] == house) & (df_table['status'].isin(['O', 'N', 'A']))]
        elif check_id == 'PO_LINE_AMENDED_VALUE_MISMATCH':
            h_df = df_table[(df_table['house'] == house) & (pd.to_numeric(df_table['amend_no'], errors='coerce').fillna(0) > 0)]
        elif check_id in _PO_UNMATCHED_RECEIPT_CHECKS:
            h_df = _po_unmatched_receipt_population(df_table, house)
        else:
            h_df = df_table[df_table['house'] == house]
    elif table in ATAMIS_TABLES:
        if check_id == 'ATAMIS_SUPPLIER_NOT_IN_UNIT4':
            h_df = _atamis_existence_population(df_table, house, 'creditor_ref')
        elif check_id == 'UNIT4_COMMIT_SUPPLIER_ORPHAN':
            h_df = _atamis_existence_population(df_table, house, 'supplier_id')
        elif check_id == 'UNIT4_SPEND_CONTRACT_ORPHAN':
            h_df = _atamis_existence_population(df_table, house, 'u4_contract_id')
        elif check_id == 'ATAMIS_CONTRACT_REF_NOT_IN_PO':
            h_df = df_table[df_table['house'] == house]
            h_df = h_df[(h_df['house'] == 'HOC') & ~_atamis_blank(h_df['contract_ref'])]
        elif check_id in ('ATAMIS_CONTRACT_NOT_IN_COMMITMENTS', 'UNIT4_COMMIT_NOT_IN_CONTRACTS'):
            ref_col = 'contract_ref' if check_id == 'ATAMIS_CONTRACT_NOT_IN_COMMITMENTS' else 'u4_contract_id'
            h_df = df_table[df_table['house'] == house]
            h_df = h_df[~_atamis_blank(h_df[ref_col])]
        else:
            h_df = df_table[df_table['house'] == house]
        if check_id in _ATAMIS_OPEN_ONLY_CHECKS:
            h_df = _atamis_filter_open_only(h_df, table, frames)
    elif table == 'budgets_report':
        h_df = df_table[df_table['house'] == house]
    else:
        h_df = df_table[df_table['house'] == house]

    # Run filter
    import inspect
    sig = inspect.signature(filter_func)
    if 'frames' in sig.parameters:
        mask = filter_func(h_df, frames)
    else:
        mask = filter_func(h_df)
        
    failing = h_df[mask].copy()
    if failing.empty:
        return failing
    if for_export and check_id not in _PO_JOIN_EXPORT_CHECKS:
        return failing

    # Enrich with context for better inspection
    if check_id in _PO_UNMATCHED_RECEIPT_CHECKS:
        # Computed column, not an early return — the full apodetail row still
        # flows through the generic tail below (source-column prefixing,
        # datetime formatting), this just adds one extra field to it.
        failing['days_since_delivery'] = (pd.Timestamp.today() - failing['deliv_date']).dt.days

    if check_id == 'GL_DIM_DUP_DESC' and 'aglaccounts' in frames:
        coa = frames['aglaccounts'][frames['aglaccounts']['house'] == house][['client', 'account', 'account_grp']].drop_duplicates(subset=['client', 'account'])
        failing = failing.merge(coa.rename(columns={'account': 'dim_value'}), on=['client', 'dim_value'], how='left')

    if check_id == 'UNIT4_COMMIT_VS_SPEND_MISMATCH':
        # Explicit named join, not the generic referential-integrity auto-join
        # below — that one only has 'house' in common between unit4_spend and
        # unit4_commitments, which would dedupe the joined table down to one
        # arbitrary row per house and attach it to every failing row. This
        # early return bypasses it, same convention as every other PO/GL/Asset
        # cross-domain check in this function.
        failing = failing.rename(columns={
            'u4_contract_id': 'UNIT4_SPEND.u4_contract_id',
            'posted':         'UNIT4_SPEND.posted',
            'amount_c':       'UNIT4_SPEND.amount_c',
        })
        if 'unit4_commitments' in frames:
            commit_link = (
                frames['unit4_commitments'][['u4_contract_id', 'posted_amount', 'supplier_name']]
                .drop_duplicates(subset=['u4_contract_id'])
                .rename(columns={'u4_contract_id': 'UNIT4_SPEND.u4_contract_id',
                                  'posted_amount':  'UNIT4_COMMITMENTS.posted_amount',
                                  'supplier_name':  'UNIT4_COMMITMENTS.supplier_name'})
            )
            failing = failing.merge(commit_link, on='UNIT4_SPEND.u4_contract_id', how='left')
        cols = ['UNIT4_SPEND.u4_contract_id', 'UNIT4_COMMITMENTS.supplier_name',
                'UNIT4_COMMITMENTS.posted_amount', 'UNIT4_SPEND.posted', 'UNIT4_SPEND.amount_c']
        return failing[[c for c in cols if c in failing.columns]]

    if check_id == 'UNIT4_COMMIT_VS_PO_MISMATCH':
        # Explicit named join — the generic auto-join below has no shared
        # candidate key between unit4_commitments and apodetail at all (PO
        # has no 'house' column), so it would never fire; this enriches with
        # the same per-contract PO invoiced total the lambda itself computes,
        # so the disagreement is directly visible alongside Commitments'
        # own Posted Amount.
        failing = failing.rename(columns={
            'u4_contract_id':  'UNIT4_COMMITMENTS.u4_contract_id',
            'contract_title':  'UNIT4_COMMITMENTS.contract_title',
            'posted_amount':   'UNIT4_COMMITMENTS.posted_amount',
        })
        if 'apodetail' in frames:
            dtl = frames['apodetail']
            po_ref = dtl['contract_id'].astype(str).str.strip()
            po_ref = po_ref.where(~_atamis_blank(dtl['contract_id']))
            po_invoiced = (
                pd.to_numeric(dtl['invoiced'], errors='coerce').fillna(0)
                .groupby(po_ref).sum()
                .rename('PO.invoiced_total').reset_index().rename(columns={'index': 'UNIT4_COMMITMENTS.u4_contract_id', po_ref.name: 'UNIT4_COMMITMENTS.u4_contract_id'})
            )
            failing = failing.merge(po_invoiced, on='UNIT4_COMMITMENTS.u4_contract_id', how='left')
        cols = ['UNIT4_COMMITMENTS.u4_contract_id', 'UNIT4_COMMITMENTS.contract_title',
                'UNIT4_COMMITMENTS.posted_amount', 'PO.invoiced_total']
        return failing[[c for c in cols if c in failing.columns]]

    if check_id == 'UNIT4_COMMIT_REMAINING_MISMATCH':
        # Explicit named join — 'Committed Amount' for this check is the
        # Spend Details view's Amount (C), not the Commitments view's own
        # committed_amount column (per direct request), so the evidence
        # needs to show the matched unit4_spend figure the lambda actually
        # used rather than implying it came from unit4_commitments itself.
        failing = failing.rename(columns={
            'u4_contract_id':  'UNIT4_COMMITMENTS.u4_contract_id',
            'contract_title':  'UNIT4_COMMITMENTS.contract_title',
            'amount_limit':    'UNIT4_COMMITMENTS.amount_limit',
            'remaining_amount': 'UNIT4_COMMITMENTS.remaining_amount',
        })
        if 'unit4_spend' in frames:
            spend = frames['unit4_spend']
            spend_ref = spend['u4_contract_id'].astype(str).str.strip()
            spend_ref = spend_ref.where(~_atamis_blank(spend['u4_contract_id']))
            committed = (
                pd.to_numeric(spend['amount_c'], errors='coerce').fillna(0)
                .groupby(spend_ref).sum()
                .rename('UNIT4_SPEND.amount_c').reset_index().rename(columns={spend_ref.name: 'UNIT4_COMMITMENTS.u4_contract_id'})
            )
            failing = failing.merge(committed, on='UNIT4_COMMITMENTS.u4_contract_id', how='left')
        cols = ['UNIT4_COMMITMENTS.u4_contract_id', 'UNIT4_COMMITMENTS.contract_title',
                'UNIT4_COMMITMENTS.amount_limit', 'UNIT4_SPEND.amount_c', 'UNIT4_COMMITMENTS.remaining_amount']
        return failing[[c for c in cols if c in failing.columns]]

    if check_id == 'ATAMIS_CONTRACT_REF_NOT_IN_PO':
        # Explicit named join on contract_ref -> apodetail.contract_id — bypasses
        # the generic auto-join below, which has no shared candidate key between
        # atamis_contracts and apodetail other than 'house'.
        failing = failing.rename(columns={
            'contract_ref':  'ATAMIS_CONTRACTS.contract_ref',
            'contract_title': 'ATAMIS_CONTRACTS.contract_title',
            'organisation':  'ATAMIS_CONTRACTS.organisation',
        })
        cols = ['ATAMIS_CONTRACTS.contract_ref', 'ATAMIS_CONTRACTS.contract_title', 'ATAMIS_CONTRACTS.organisation']
        return failing[[c for c in cols if c in failing.columns]]

    if check_id == 'ATAMIS_CONTRACT_NOT_IN_COMMITMENTS':
        # Explicit named join on contract_ref -> unit4_commitments.u4_contract_id —
        # bypasses the generic auto-join below, which has no shared candidate
        # key between these two tables other than 'house'.
        failing = failing.rename(columns={
            'contract_ref':   'ATAMIS_CONTRACTS.contract_ref',
            'contract_title': 'ATAMIS_CONTRACTS.contract_title',
            'organisation':   'ATAMIS_CONTRACTS.organisation',
        })
        cols = ['ATAMIS_CONTRACTS.contract_ref', 'ATAMIS_CONTRACTS.contract_title', 'ATAMIS_CONTRACTS.organisation']
        return failing[[c for c in cols if c in failing.columns]]

    if check_id == 'UNIT4_COMMIT_NOT_IN_CONTRACTS':
        # HOC rows come from unit4_commitments (rich data — contract_title,
        # supplier_name, etc. are real); HOL rows come from agldimvalue's
        # Contract Number dimension (see _build_unit4_contract_refs) and have
        # nothing but house/u4_contract_id populated. '_source' makes that
        # provenance difference visible in the evidence rather than implying
        # HOL has the same rich commitment data HOC does.
        failing = failing.rename(columns={
            'u4_contract_id': 'UNIT4_COMMITMENTS.u4_contract_id',
            'contract_title': 'UNIT4_COMMITMENTS.contract_title',
            'supplier_name':  'UNIT4_COMMITMENTS.supplier_name',
            '_source':        'UNIT4_COMMITMENTS.source',
        })
        cols = ['house', 'UNIT4_COMMITMENTS.u4_contract_id', 'UNIT4_COMMITMENTS.contract_title',
                'UNIT4_COMMITMENTS.supplier_name', 'UNIT4_COMMITMENTS.source']
        return failing[[c for c in cols if c in failing.columns]]

    if check_id == 'ATAMIS_CONTRACT_VALUE_MISMATCH':
        # Explicit named join, enriching with the matched commitment's own
        # Contract Award Amount so the two systems' disagreement is directly
        # visible alongside Atamis's Total Award Value. Blank contract_ref is
        # excluded from BOTH sides before merging — otherwise a contract with
        # no reference at all can spuriously 'match' an unrelated commitment
        # that also has a blank/missing Contract Id (blank == blank in a
        # merge), showing a fake comparison against an unrelated amount.
        failing = failing.rename(columns={
            'contract_ref':      'ATAMIS_CONTRACTS.contract_ref',
            'contract_title':    'ATAMIS_CONTRACTS.contract_title',
            'total_award_value': 'ATAMIS_CONTRACTS.total_award_value',
        })
        blank_ref = _atamis_blank(failing['ATAMIS_CONTRACTS.contract_ref'])
        failing.loc[blank_ref, 'ATAMIS_CONTRACTS.contract_ref'] = None
        if 'unit4_commitments' in frames:
            commit_raw = frames['unit4_commitments']
            commit_link = (
                commit_raw[~_atamis_blank(commit_raw['u4_contract_id'])][['u4_contract_id', 'award_amount']]
                .drop_duplicates(subset=['u4_contract_id'])
                .rename(columns={'u4_contract_id': 'ATAMIS_CONTRACTS.contract_ref',
                                  'award_amount': 'UNIT4_COMMITMENTS.award_amount'})
            )
            failing = failing.merge(commit_link, on='ATAMIS_CONTRACTS.contract_ref', how='left')
        cols = ['ATAMIS_CONTRACTS.contract_ref', 'ATAMIS_CONTRACTS.contract_title',
                'ATAMIS_CONTRACTS.total_award_value', 'UNIT4_COMMITMENTS.award_amount']
        return failing[[c for c in cols if c in failing.columns]]

    if check_id == 'ATAMIS_CONTRACT_DATE_MISMATCH':
        # Explicit named join, enriching with the matched commitment's own
        # Contract Date From / Contract Date To so the two systems'
        # disagreement is directly visible alongside Atamis's own Start/End
        # Date. Same blank-contract_ref exclusion as ATAMIS_CONTRACT_VALUE_MISMATCH,
        # for the same reason (avoid a spurious blank == blank merge match).
        failing = failing.rename(columns={
            'contract_ref':   'ATAMIS_CONTRACTS.contract_ref',
            'contract_title': 'ATAMIS_CONTRACTS.contract_title',
            'start_date':     'ATAMIS_CONTRACTS.start_date',
            'end_date':       'ATAMIS_CONTRACTS.end_date',
        })
        blank_ref = _atamis_blank(failing['ATAMIS_CONTRACTS.contract_ref'])
        failing.loc[blank_ref, 'ATAMIS_CONTRACTS.contract_ref'] = None
        if 'unit4_commitments' in frames:
            commit_raw = frames['unit4_commitments']
            commit_link = (
                commit_raw[~_atamis_blank(commit_raw['u4_contract_id'])][['u4_contract_id', 'date_from', 'date_to']]
                .drop_duplicates(subset=['u4_contract_id'])
                .rename(columns={'u4_contract_id': 'ATAMIS_CONTRACTS.contract_ref',
                                  'date_from': 'UNIT4_COMMITMENTS.date_from',
                                  'date_to': 'UNIT4_COMMITMENTS.date_to'})
            )
            failing = failing.merge(commit_link, on='ATAMIS_CONTRACTS.contract_ref', how='left')
        cols = ['ATAMIS_CONTRACTS.contract_ref', 'ATAMIS_CONTRACTS.contract_title',
                'ATAMIS_CONTRACTS.start_date', 'ATAMIS_CONTRACTS.end_date',
                'UNIT4_COMMITMENTS.date_from', 'UNIT4_COMMITMENTS.date_to']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_depreciation' and check_id in ['DQ-AG-X03', 'DQ-AG-X04']:
        # 1. Join to Master to get asset_group (join on client to avoid cross-client matches)
        if 'asset_master' in frames:
            master_link = frames['asset_master'][['house', 'client', 'asset_id', 'asset_group']].copy()
            master_link = master_link.drop_duplicates(subset=['house', 'client', 'asset_id'])
            failing = failing.merge(master_link, on=['house', 'client', 'asset_id'], how='left')

        # 2. Join to Group Config — match on depr_book_id so each book compares
        #    against the correct group book default (not the group master summary)
        if 'asset_groups' in frames:
            if check_id == 'DQ-AG-X04':
                grp_link = frames['asset_groups'][['house', 'client', 'asset_group', 'depr_book_id', 'book_lifetime']].copy()
                grp_link = grp_link.rename(columns={'book_lifetime': 'STANDARD_lifetime'})
                failing = failing.merge(grp_link, on=['house', 'client', 'asset_group', 'depr_book_id'], how='left')
                failing = failing.rename(columns={
                    'asset_id':         'ASSET_DEPRECIATION.asset_id',
                    'depr_book_id':     'ASSET_DEPRECIATION.depr_book_id',
                    'lifetime':         'ASSET_DEPRECIATION.lifetime',
                    'asset_group':      'ASSET_MASTER.asset_group',
                    'STANDARD_lifetime':'ASSET_GROUPS.book_lifetime',
                })
                cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.depr_book_id', 'ASSET_DEPRECIATION.lifetime', 'ASSET_MASTER.asset_group', 'ASSET_GROUPS.book_lifetime']
            else:  # DQ-AG-X03
                grp_link = frames['asset_groups'][['house', 'client', 'asset_group', 'depr_book_id', 'book_depr_method']].copy()
                grp_link = grp_link.rename(columns={'book_depr_method': 'STANDARD_depr_method'})
                failing = failing.merge(grp_link, on=['house', 'client', 'asset_group', 'depr_book_id'], how='left')
                failing = failing.rename(columns={
                    'asset_id':               'ASSET_DEPRECIATION.asset_id',
                    'depr_book_id':           'ASSET_DEPRECIATION.depr_book_id',
                    'depr_method':            'ASSET_DEPRECIATION.depr_method',
                    'asset_group':            'ASSET_MASTER.asset_group',
                    'STANDARD_depr_method':   'ASSET_GROUPS.book_depr_method',
                })
                cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.depr_book_id', 'ASSET_DEPRECIATION.depr_method', 'ASSET_MASTER.asset_group', 'ASSET_GROUPS.book_depr_method']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_depreciation' and check_id == 'DQ-AD-K05':
        if 'asset_master' in frames:
            master_link = frames['asset_master'][['house', 'asset_id', 'base_amount']].copy()
            master_link = master_link.drop_duplicates(subset=['house', 'asset_id'])
            failing = failing.merge(master_link, on=['house', 'asset_id'], how='left')
        failing = failing.rename(columns={
            'asset_id':    'ASSET_DEPRECIATION.asset_id',
            'res_value':   'ASSET_DEPRECIATION.res_value',
            'base_amount': 'ASSET_MASTER.base_amount',
        })
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.res_value', 'ASSET_MASTER.base_amount']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_master' and check_id == 'DQ-AG-X01':
        failing = failing.rename(columns={
            'asset_id':    'ASSET_MASTER.asset_id',
            'asset_group': 'ASSET_MASTER.asset_group',
        })
        if 'asset_groups' in frames:
            grp_link = frames['asset_groups'][['house', 'asset_group']].copy()
            grp_link = grp_link.drop_duplicates(subset=['house', 'asset_group'])
            grp_link = grp_link.rename(columns={'asset_group': 'ASSET_GROUPS.asset_group'})
            failing = failing.merge(grp_link, left_on=['house', 'ASSET_MASTER.asset_group'], right_on=['house', 'ASSET_GROUPS.asset_group'], how='left')
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.asset_group', 'ASSET_GROUPS.asset_group']
        return failing[[c for c in cols if c in failing.columns]]
 
    if table == 'asset_balances' and check_id == 'DQ-AM-R01':
        failing = failing.rename(columns={'asset_id': 'ASSET_BALANCES.asset_id'})
        if 'asset_master' in frames:
            master_link = frames['asset_master'][['house', 'asset_id']].copy()
            master_link = master_link.drop_duplicates(subset=['house', 'asset_id'])
            master_link = master_link.rename(columns={'asset_id': 'ASSET_MASTER.asset_id'})
            failing = failing.merge(master_link, left_on=['house', 'ASSET_BALANCES.asset_id'], right_on=['house', 'ASSET_MASTER.asset_id'], how='left')
        cols = ['ASSET_BALANCES.asset_id', 'ASSET_MASTER.asset_id']
        return failing[[c for c in cols if c in failing.columns]]
 
    if table == 'asset_depreciation' and check_id in ['DQ-AM-R02', 'DQ-AD-X01']:
        failing = failing.rename(columns={'asset_id': 'ASSET_DEPRECIATION.asset_id'})
        if 'asset_master' in frames:
            master_link = frames['asset_master'][['house', 'asset_id']].copy()
            master_link = master_link.drop_duplicates(subset=['house', 'asset_id'])
            master_link = master_link.rename(columns={'asset_id': 'ASSET_MASTER.asset_id'})
            failing = failing.merge(master_link, left_on=['house', 'ASSET_DEPRECIATION.asset_id'], right_on=['house', 'ASSET_MASTER.asset_id'], how='left')
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_MASTER.asset_id']
        return failing[[c for c in cols if c in failing.columns]]
 
    if table == 'asset_master' and check_id == 'DQ-AM-R05':
        failing = failing.rename(columns={'asset_id': 'ASSET_MASTER.asset_id', 'apar_id': 'ASSET_MASTER.apar_id'})
        if 'asuheader' in frames:
            sup_link = frames['asuheader'][['house', 'apar_id']].copy()
            sup_link = sup_link.drop_duplicates(subset=['house', 'apar_id'])
            sup_link = sup_link.rename(columns={'apar_id': 'SUPPLIER_MASTER.apar_id'})
            failing = failing.merge(sup_link, left_on=['house', 'ASSET_MASTER.apar_id'], right_on=['house', 'SUPPLIER_MASTER.apar_id'], how='left')
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.apar_id', 'SUPPLIER_MASTER.apar_id']
        return failing[[c for c in cols if c in failing.columns]]
 
    if table == 'asset_master' and check_id == 'DQ-AD-X02':
        failing = failing.rename(columns={'asset_id': 'ASSET_MASTER.asset_id', 'status': 'ASSET_MASTER.status'})
        if 'asset_depreciation' in frames:
            depr_link = frames['asset_depreciation'][['house', 'asset_id']].copy()
            depr_link = depr_link.drop_duplicates(subset=['house', 'asset_id'])
            depr_link = depr_link.rename(columns={'asset_id': 'ASSET_DEPRECIATION.asset_id'})
            failing = failing.merge(depr_link, left_on=['house', 'ASSET_MASTER.asset_id'], right_on=['house', 'ASSET_DEPRECIATION.asset_id'], how='left')
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.status', 'ASSET_DEPRECIATION.asset_id']
        return failing[[c for c in cols if c in failing.columns]]
 
    if table == 'asset_depreciation' and check_id == 'DQ-AD-X03':
        failing = failing.rename(columns={
            'asset_id':     'ASSET_DEPRECIATION.asset_id',
            'depr_book_id': 'ASSET_DEPRECIATION.depr_book_id',
            'cap_date_from': 'ASSET_DEPRECIATION.cap_date_from',
            'status':       'ASSET_DEPRECIATION.status',
        })
        if 'asset_master' in frames:
            master_link = frames['asset_master'][['house', 'asset_id', 'cap_date_from', 'status']].copy()
            master_link = master_link.drop_duplicates(subset=['house', 'asset_id'])
            master_link = master_link.rename(columns={'asset_id': 'ASSET_MASTER.asset_id', 'cap_date_from': 'ASSET_MASTER.cap_date_from', 'status': 'ASSET_MASTER.status'})
            failing = failing.merge(master_link, left_on=['house', 'ASSET_DEPRECIATION.asset_id'], right_on=['house', 'ASSET_MASTER.asset_id'], how='left')
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.depr_book_id', 'ASSET_DEPRECIATION.status', 'ASSET_DEPRECIATION.cap_date_from', 'ASSET_MASTER.status', 'ASSET_MASTER.cap_date_from']
        return failing[[c for c in cols if c in failing.columns]].drop_duplicates(
            subset=['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.depr_book_id']
        )
 
    if table == 'asset_depreciation' and check_id == 'DQ-AD-X05':
        failing = failing.rename(columns={'asset_id': 'ASSET_DEPRECIATION.asset_id', 'depr_book_id': 'ASSET_DEPRECIATION.depr_book_id'})
        if 'asset_balances' in frames:
            bal_link = frames['asset_balances'][['house', 'asset_id', 'depr_book_id']].copy()
            bal_link = bal_link.drop_duplicates(subset=['house', 'asset_id', 'depr_book_id'])
            bal_link = bal_link.rename(columns={'asset_id': 'ASSET_BALANCES.asset_id', 'depr_book_id': 'ASSET_BALANCES.depr_book_id'})
            failing = failing.merge(bal_link,
                left_on=['house', 'ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.depr_book_id'],
                right_on=['house', 'ASSET_BALANCES.asset_id', 'ASSET_BALANCES.depr_book_id'],
                how='left')
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.depr_book_id', 'ASSET_BALANCES.asset_id', 'ASSET_BALANCES.depr_book_id']
        return failing[[c for c in cols if c in failing.columns]]
 
    if table == 'asset_balances' and check_id == 'DQ-AB-X01':
        failing = failing.rename(columns={'asset_id': 'ASSET_BALANCES.asset_id'})
        if 'asset_master' in frames:
            master_link = frames['asset_master'][['house', 'asset_id']].copy()
            master_link = master_link.drop_duplicates(subset=['house', 'asset_id'])
            master_link = master_link.rename(columns={'asset_id': 'ASSET_MASTER.asset_id'})
            failing = failing.merge(master_link, left_on=['house', 'ASSET_BALANCES.asset_id'], right_on=['house', 'ASSET_MASTER.asset_id'], how='left')
        cols = ['ASSET_BALANCES.asset_id', 'ASSET_MASTER.asset_id']
        return failing[[c for c in cols if c in failing.columns]]
 
    if table == 'asset_balances' and check_id == 'DQ-AB-X02':
        failing = failing.rename(columns={'asset_id': 'ASSET_BALANCES.asset_id', 'depr_book_id': 'ASSET_BALANCES.depr_book_id'})
        if 'asset_depreciation' in frames:
            depr_link = frames['asset_depreciation'][['house', 'asset_id', 'depr_book_id']].copy()
            depr_link = depr_link.drop_duplicates(subset=['house', 'asset_id', 'depr_book_id'])
            depr_link = depr_link.rename(columns={'asset_id': 'ASSET_DEPRECIATION.asset_id', 'depr_book_id': 'ASSET_DEPRECIATION.depr_book_id'})
            failing = failing.merge(depr_link,
                left_on=['house', 'ASSET_BALANCES.asset_id', 'ASSET_BALANCES.depr_book_id'],
                right_on=['house', 'ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.depr_book_id'],
                how='left')
        cols = ['ASSET_BALANCES.asset_id', 'ASSET_BALANCES.depr_book_id', 'ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.depr_book_id']
        return failing[[c for c in cols if c in failing.columns]]
 
    if table == 'asset_master' and check_id == 'DQ-AB-X03':
        failing = failing.rename(columns={'asset_id': 'ASSET_MASTER.asset_id', 'status': 'ASSET_MASTER.status'})
        if 'asset_balances' in frames:
            bal_link = frames['asset_balances'][['house', 'asset_id']].copy()
            bal_link = bal_link.drop_duplicates(subset=['house', 'asset_id'])
            bal_link = bal_link.rename(columns={'asset_id': 'ASSET_BALANCES.asset_id'})
            failing = failing.merge(bal_link, left_on=['house', 'ASSET_MASTER.asset_id'], right_on=['house', 'ASSET_BALANCES.asset_id'], how='left')
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.status', 'ASSET_BALANCES.asset_id']
        return failing[[c for c in cols if c in failing.columns]]
 
    if table == 'asset_trans_flags' and check_id == 'DQ-AF-X01':
        failing = failing.rename(columns={'asset_id': 'ASSET_TRANS_FLAGS.asset_id', 'trans_type': 'ASSET_TRANS_FLAGS.trans_type'})
        if 'asset_master' in frames:
            master_link = frames['asset_master'][['house', 'asset_id', 'status']].copy()
            master_link = master_link.drop_duplicates(subset=['house', 'asset_id'])
            master_link = master_link.rename(columns={'asset_id': 'ASSET_MASTER.asset_id', 'status': 'ASSET_MASTER.status'})
            failing = failing.merge(master_link, left_on=['house', 'ASSET_TRANS_FLAGS.asset_id'], right_on=['house', 'ASSET_MASTER.asset_id'], how='left')
        cols = ['ASSET_TRANS_FLAGS.asset_id', 'ASSET_MASTER.status']
        return failing[[c for c in cols if c in failing.columns]].drop_duplicates(subset=['ASSET_TRANS_FLAGS.asset_id'])
 
    if table == 'asset_trans_flags' and check_id == 'DQ-AF-X02':
        failing = failing.rename(columns={'asset_id': 'ASSET_TRANS_FLAGS.asset_id', 'trans_type': 'ASSET_TRANS_FLAGS.trans_type', 'trans_date': 'ASSET_TRANS_FLAGS.trans_date'})
        if 'asset_master' in frames:
            master_link = frames['asset_master'][['house', 'asset_id', 'date_to']].copy()
            master_link = master_link.drop_duplicates(subset=['house', 'asset_id'])
            master_link = master_link.rename(columns={'asset_id': 'ASSET_MASTER.asset_id', 'date_to': 'ASSET_MASTER.date_to'})
            failing = failing.merge(master_link, left_on=['house', 'ASSET_TRANS_FLAGS.asset_id'], right_on=['house', 'ASSET_MASTER.asset_id'], how='left')
        cols = ['ASSET_TRANS_FLAGS.asset_id', 'ASSET_TRANS_FLAGS.trans_type', 'ASSET_TRANS_FLAGS.trans_date', 'ASSET_MASTER.date_to']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_master' and check_id == 'DQ-AM-C06':
        failing = failing.rename(columns={
            'asset_id':      'ASSET_MASTER.asset_id',
            'cap_date_from': 'ASSET_MASTER.cap_date_from',
        })
        if 'asset_depreciation' in frames:
            depr_link = frames['asset_depreciation'][['house', 'asset_id', 'cap_flag']].copy()
            depr_link = depr_link.drop_duplicates(subset=['house', 'asset_id'])
            depr_link = depr_link.rename(columns={
                'asset_id': 'ASSET_DEPRECIATION.asset_id',
                'cap_flag': 'ASSET_DEPRECIATION.cap_flag',
            })
            failing = failing.merge(depr_link, left_on=['house', 'ASSET_MASTER.asset_id'], right_on=['house', 'ASSET_DEPRECIATION.asset_id'], how='left')
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.cap_date_from', 'ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.cap_flag']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_master' and check_id == 'DQ-AM-C01':
        failing = failing.rename(columns={'asset_id': 'ASSET_MASTER.asset_id'})
        cols = ['ASSET_MASTER.asset_id']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_master' and check_id == 'DQ-AM-C02':
        failing = failing.rename(columns={
            'asset_id':    'ASSET_MASTER.asset_id',
            'description': 'ASSET_MASTER.description',
        })
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.description']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_master' and check_id == 'DQ-AM-C03':
        failing = failing.rename(columns={
            'asset_id':    'ASSET_MASTER.asset_id',
            'asset_group': 'ASSET_MASTER.asset_group',
        })
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.asset_group']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_master' and check_id == 'DQ-AM-C04':
        failing = failing.rename(columns={
            'asset_id':  'ASSET_MASTER.asset_id',
            'date_from': 'ASSET_MASTER.date_from',
        })
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.date_from']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_master' and check_id == 'DQ-AM-C05':
        failing = failing.rename(columns={
            'asset_id':      'ASSET_MASTER.asset_id',
            'org_amount':    'ASSET_MASTER.org_amount',
            'cap_date_from': 'ASSET_MASTER.cap_date_from',
        })
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.org_amount', 'ASSET_MASTER.cap_date_from']
        return failing[[c for c in cols if c in failing.columns]]


    if table == 'asset_master' and check_id == 'DQ-AM-V01':
        failing = failing.rename(columns={
            'asset_id': 'ASSET_MASTER.asset_id',
            'status':   'ASSET_MASTER.status',
        })
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.status']
        return failing[[c for c in cols if c in failing.columns]]


    if table == 'asset_master' and check_id == 'DQ-AM-V03':
        failing = failing.rename(columns={
            'asset_id':    'ASSET_MASTER.asset_id',
            'base_amount': 'ASSET_MASTER.base_amount',
        })
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.base_amount']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_master' and check_id == 'DQ-AM-V04':
        failing = failing.rename(columns={
            'asset_id':  'ASSET_MASTER.asset_id',
            'date_from': 'ASSET_MASTER.date_from',
            'date_to':   'ASSET_MASTER.date_to',
        })
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.date_from', 'ASSET_MASTER.date_to']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_master' and check_id == 'DQ-AM-V05':
        failing = failing.rename(columns={
            'asset_id':      'ASSET_MASTER.asset_id',
            'cap_date_from': 'ASSET_MASTER.cap_date_from',
            'date_from':     'ASSET_MASTER.date_from',
        })
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.cap_date_from', 'ASSET_MASTER.date_from']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_master' and check_id == 'DQ-AM-V06':
        failing = failing.rename(columns={
            'asset_id':      'ASSET_MASTER.asset_id',
            'org_amt_date':  'ASSET_MASTER.org_amt_date',
            'cap_date_from': 'ASSET_MASTER.cap_date_from',
        })
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.org_amt_date', 'ASSET_MASTER.cap_date_from']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_master' and check_id == 'DQ-AM-T01':
        failing = failing.rename(columns={
            'asset_id':    'ASSET_MASTER.asset_id',
            'last_update': 'ASSET_MASTER.last_update',
        })
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.last_update']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_master' and check_id == 'DQ-AM-K01':
        failing = failing.rename(columns={
            'asset_id': 'ASSET_MASTER.asset_id',
            'date_to':  'ASSET_MASTER.date_to',
            'status':   'ASSET_MASTER.status',
        })
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.date_to', 'ASSET_MASTER.status']
        return failing[[c for c in cols if c in failing.columns]]


    if table == 'asset_master' and check_id == 'DQ-AM-K03':
        failing = failing.rename(columns={
            'asset_id':     'ASSET_MASTER.asset_id',
            'org_amt_date': 'ASSET_MASTER.org_amt_date',
            'org_amount':   'ASSET_MASTER.org_amount',
        })
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.org_amt_date', 'ASSET_MASTER.org_amount']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_master' and check_id == 'DQ-AM-K04':
        failing = failing.rename(columns={
            'asset_id':   'ASSET_MASTER.asset_id',
            'grant_flag': 'ASSET_MASTER.grant_flag',
            'dim_1':      'ASSET_MASTER.dim_1',
        })
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.grant_flag', 'ASSET_MASTER.dim_1']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_master' and check_id == 'DQ-AM-D01':
        failing = failing.rename(columns={
            'asset_id':    'ASSET_MASTER.asset_id',
            'description': 'ASSET_MASTER.description',
            'asset_group': 'ASSET_MASTER.asset_group',
            'status':      'ASSET_MASTER.status',
        })
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.description', 'ASSET_MASTER.asset_group', 'ASSET_MASTER.status']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_master' and check_id == 'DQ-AM-D02':
        failing = failing.rename(columns={
            'asset_id':      'ASSET_MASTER.asset_id',
            'description':   'ASSET_MASTER.description',
            'asset_group':   'ASSET_MASTER.asset_group',
            'cap_date_from': 'ASSET_MASTER.cap_date_from',
            'org_amount':    'ASSET_MASTER.org_amount',
        })
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.description', 'ASSET_MASTER.asset_group', 'ASSET_MASTER.cap_date_from', 'ASSET_MASTER.org_amount']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_master' and check_id == 'DQ-AM-R04':
        failing = failing.rename(columns={
            'asset_id':     'ASSET_MASTER.asset_id',
            'parent_asset': 'ASSET_MASTER.parent_asset',
        })
        if 'asset_master' in frames:
            parent_link = frames['asset_master'][['house', 'asset_id']].copy()
            parent_link = parent_link.drop_duplicates(subset=['house', 'asset_id'])
            parent_link = parent_link.rename(columns={'asset_id': 'ASSET_MASTER (TARGET).asset_id'})
            failing = failing.merge(parent_link,
                left_on=['house', 'ASSET_MASTER.parent_asset'],
                right_on=['house', 'ASSET_MASTER (TARGET).asset_id'],
                how='left')
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.parent_asset', 'ASSET_MASTER (TARGET).asset_id']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_depreciation' and check_id == 'DQ-AD-C01':
        failing = failing.rename(columns={
            'asset_id': 'ASSET_DEPRECIATION.asset_id',
        })
        cols = ['ASSET_DEPRECIATION.asset_id']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_depreciation' and check_id == 'DQ-AD-C02':
        failing = failing.rename(columns={
            'asset_id':     'ASSET_DEPRECIATION.asset_id',
            'depr_book_id': 'ASSET_DEPRECIATION.depr_book_id',
        })
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.depr_book_id']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_depreciation' and check_id == 'DQ-AD-C03':
        failing = failing.rename(columns={
            'asset_id':     'ASSET_DEPRECIATION.asset_id',
            'depr_method':  'ASSET_DEPRECIATION.depr_method',
        })
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.depr_method']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_depreciation' and check_id == 'DQ-AD-C04':
        failing = failing.rename(columns={
            'asset_id':    'ASSET_DEPRECIATION.asset_id',
            'depr_method': 'ASSET_DEPRECIATION.depr_method',
            'lifetime':    'ASSET_DEPRECIATION.lifetime',
        })
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.depr_method', 'ASSET_DEPRECIATION.lifetime']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_depreciation' and check_id == 'DQ-AD-C05':
        failing = failing.rename(columns={
            'asset_id':     'ASSET_DEPRECIATION.asset_id',
            'depr_method':  'ASSET_DEPRECIATION.depr_method',
            'depr_percent': 'ASSET_DEPRECIATION.depr_percent',
        })
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.depr_method', 'ASSET_DEPRECIATION.depr_percent']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_depreciation' and check_id == 'DQ-AD-C06':
        failing = failing.rename(columns={
            'asset_id':      'ASSET_DEPRECIATION.asset_id',
            'cap_date_from': 'ASSET_DEPRECIATION.cap_date_from',
            'cap_flag':      'ASSET_DEPRECIATION.cap_flag',
        })
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.cap_date_from', 'ASSET_DEPRECIATION.cap_flag']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_depreciation' and check_id == 'DQ-AD-C07':
        failing = failing.rename(columns={
            'asset_id':    'ASSET_DEPRECIATION.asset_id',
            'depr_period': 'ASSET_DEPRECIATION.depr_period',
        })
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.depr_period']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_depreciation' and check_id == 'DQ-AD-V01':
        failing = failing.rename(columns={
            'asset_id':    'ASSET_DEPRECIATION.asset_id',
            'depr_method': 'ASSET_DEPRECIATION.depr_method',
        })
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.depr_method']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_depreciation' and check_id == 'DQ-AD-V02':
        failing = failing.rename(columns={
            'asset_id': 'ASSET_DEPRECIATION.asset_id',
            'status':   'ASSET_DEPRECIATION.status',
        })
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.status']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_depreciation' and check_id == 'DQ-AD-V03':
        failing = failing.rename(columns={
            'asset_id':     'ASSET_DEPRECIATION.asset_id',
            'depr_percent': 'ASSET_DEPRECIATION.depr_percent',
        })
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.depr_percent']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_depreciation' and check_id == 'DQ-AD-V04':
        failing = failing.rename(columns={
            'asset_id':    'ASSET_DEPRECIATION.asset_id',
            'depr_method': 'ASSET_DEPRECIATION.depr_method',
            'lifetime':    'ASSET_DEPRECIATION.lifetime',
        })
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.depr_method', 'ASSET_DEPRECIATION.lifetime']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_depreciation' and check_id == 'DQ-AD-V05':
        failing = failing.rename(columns={
            'asset_id':  'ASSET_DEPRECIATION.asset_id',
            'date_from': 'ASSET_DEPRECIATION.date_from',
            'date_to':   'ASSET_DEPRECIATION.date_to',
        })
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.date_from', 'ASSET_DEPRECIATION.date_to']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_depreciation' and check_id == 'DQ-AD-V06':
        failing = failing.rename(columns={
            'asset_id':      'ASSET_DEPRECIATION.asset_id',
            'cap_date_from': 'ASSET_DEPRECIATION.cap_date_from',
            'date_from':     'ASSET_DEPRECIATION.date_from',
        })
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.cap_date_from', 'ASSET_DEPRECIATION.date_from']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_depreciation' and check_id == 'DQ-AD-V07':
        failing = failing.rename(columns={
            'asset_id':     'ASSET_DEPRECIATION.asset_id',
            'depr_percent': 'ASSET_DEPRECIATION.depr_percent',
        })
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.depr_percent']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_depreciation' and check_id == 'DQ-AD-T01':
        failing = failing.rename(columns={
            'asset_id':    'ASSET_DEPRECIATION.asset_id',
            'last_update': 'ASSET_DEPRECIATION.last_update',
        })
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.last_update']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_depreciation' and check_id == 'DQ-AD-K01':
        failing = failing.rename(columns={
            'asset_id': 'ASSET_DEPRECIATION.asset_id',
            'date_to':  'ASSET_DEPRECIATION.date_to',
            'status':   'ASSET_DEPRECIATION.status',
        })
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.date_to', 'ASSET_DEPRECIATION.status']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_depreciation' and check_id == 'DQ-AD-K02':
        failing = failing.rename(columns={
            'asset_id':    'ASSET_DEPRECIATION.asset_id',
            'depr_period': 'ASSET_DEPRECIATION.depr_period',
        })
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.depr_period']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_depreciation' and check_id == 'DQ-AD-K03':
        failing = failing.rename(columns={
            'asset_id':    'ASSET_DEPRECIATION.asset_id',
            'switch':      'ASSET_DEPRECIATION.switch',
            'depr_method': 'ASSET_DEPRECIATION.depr_method',
        })
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.switch', 'ASSET_DEPRECIATION.depr_method']
        return failing[[c for c in cols if c in failing.columns]]


    if table == 'asset_depreciation' and check_id == 'DQ-AD-D01':
        failing = failing.rename(columns={
            'client':       'ASSET_DEPRECIATION.client',
            'asset_id':     'ASSET_DEPRECIATION.asset_id',
            'depr_book_id': 'ASSET_DEPRECIATION.depr_book_id',
            'status':       'ASSET_DEPRECIATION.status',
            'depr_method':  'ASSET_DEPRECIATION.depr_method',
            'lifetime':     'ASSET_DEPRECIATION.lifetime',
        })
        cols = ['ASSET_DEPRECIATION.client', 'ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.depr_book_id', 'ASSET_DEPRECIATION.status', 'ASSET_DEPRECIATION.depr_method', 'ASSET_DEPRECIATION.lifetime']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_balances' and check_id == 'DQ-AB-C01':
        failing = failing.rename(columns={
            'asset_id': 'ASSET_BALANCES.asset_id',
        })
        cols = ['ASSET_BALANCES.asset_id']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_balances' and check_id == 'DQ-AB-C02':
        failing = failing.rename(columns={
            'asset_id':     'ASSET_BALANCES.asset_id',
            'depr_book_id': 'ASSET_BALANCES.depr_book_id',
        })
        cols = ['ASSET_BALANCES.asset_id', 'ASSET_BALANCES.depr_book_id']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_balances' and check_id == 'DQ-AB-C03':
        failing = failing.rename(columns={
            'asset_id':   'ASSET_BALANCES.asset_id',
            'trans_type': 'ASSET_BALANCES.trans_type',
        })
        cols = ['ASSET_BALANCES.asset_id', 'ASSET_BALANCES.trans_type']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_balances' and check_id == 'DQ-AB-C04':
        failing = failing.rename(columns={
            'asset_id':     'ASSET_BALANCES.asset_id',
            'total_amount': 'ASSET_BALANCES.total_amount',
        })
        cols = ['ASSET_BALANCES.asset_id', 'ASSET_BALANCES.total_amount']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_balances' and check_id == 'DQ-AB-V01':
        failing = failing.rename(columns={
            'asset_id':   'ASSET_BALANCES.asset_id',
            'trans_type': 'ASSET_BALANCES.trans_type',
        })
        cols = ['ASSET_BALANCES.asset_id', 'ASSET_BALANCES.trans_type']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_balances' and check_id == 'DQ-AB-V02':
        failing = failing.rename(columns={
            'asset_id':     'ASSET_BALANCES.asset_id',
            'trans_type':   'ASSET_BALANCES.trans_type',
            'total_amount': 'ASSET_BALANCES.total_amount',
        })
        cols = ['ASSET_BALANCES.asset_id', 'ASSET_BALANCES.trans_type', 'ASSET_BALANCES.total_amount']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_balances' and check_id == 'DQ-AB-V03':
        failing = failing.rename(columns={
            'asset_id':       'ASSET_BALANCES.asset_id',
            'max_trans_date': 'ASSET_BALANCES.max_trans_date',
        })
        cols = ['ASSET_BALANCES.asset_id', 'ASSET_BALANCES.max_trans_date']
        return failing[[c for c in cols if c in failing.columns]]


    if table == 'asset_balances' and check_id == 'DQ-AB-K02':
        failing = failing.rename(columns={
            'asset_id':     'ASSET_BALANCES.asset_id',
            'depr_book_id': 'ASSET_BALANCES.depr_book_id',
            'trans_type':   'ASSET_BALANCES.trans_type',
        })
        cols = ['ASSET_BALANCES.asset_id', 'ASSET_BALANCES.depr_book_id', 'ASSET_BALANCES.trans_type']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_balances' and check_id == 'DQ-AB-K03':
        failing = failing.rename(columns={
            'asset_id':     'ASSET_BALANCES.asset_id',
            'depr_book_id': 'ASSET_BALANCES.depr_book_id',
            'trans_type':   'ASSET_BALANCES.trans_type',
        })
        cols = ['ASSET_BALANCES.asset_id', 'ASSET_BALANCES.depr_book_id', 'ASSET_BALANCES.trans_type']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_groups' and check_id == 'DQ-AG-C01':
        failing = failing.rename(columns={
            'asset_group': 'ASSET_GROUPS.asset_group',
        })
        cols = ['ASSET_GROUPS.asset_group']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_groups' and check_id == 'DQ-AG-C02':
        failing = failing.rename(columns={
            'asset_group': 'ASSET_GROUPS.asset_group',
            'description': 'ASSET_GROUPS.description',
            'grp_status':  'ASSET_GROUPS.grp_status',
        })
        cols = ['ASSET_GROUPS.asset_group', 'ASSET_GROUPS.description', 'ASSET_GROUPS.grp_status']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_groups' and check_id == 'DQ-AG-V01':
        failing = failing.rename(columns={
            'asset_group': 'ASSET_GROUPS.asset_group',
            'depr_method': 'ASSET_GROUPS.depr_method',
        })
        cols = ['ASSET_GROUPS.asset_group', 'ASSET_GROUPS.depr_method']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_groups' and check_id == 'DQ-AG-V04':
        failing = failing.rename(columns={
            'asset_group':  'ASSET_GROUPS.asset_group',
            'depr_percent': 'ASSET_GROUPS.depr_percent',
        })
        cols = ['ASSET_GROUPS.asset_group', 'ASSET_GROUPS.depr_percent']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_groups' and check_id == 'DQ-AG-V05':
        failing = failing.rename(columns={
            'asset_group': 'ASSET_GROUPS.asset_group',
            'depr_method': 'ASSET_GROUPS.depr_method',
            'lifetime':    'ASSET_GROUPS.lifetime',
        })
        cols = ['ASSET_GROUPS.asset_group', 'ASSET_GROUPS.depr_method', 'ASSET_GROUPS.lifetime']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_groups' and check_id == 'DQ-AG-K01':
        failing = failing.rename(columns={
            'asset_group': 'ASSET_GROUPS.asset_group',
            'grp_status':  'ASSET_GROUPS.grp_status',
            'book_status': 'ASSET_GROUPS.book_status',
        })
        cols = ['ASSET_GROUPS.asset_group', 'ASSET_GROUPS.grp_status', 'ASSET_GROUPS.book_status']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_groups' and check_id == 'DQ-AG-D02':
        failing = failing.rename(columns={
            'asset_group': 'ASSET_GROUPS.asset_group',
            'description': 'ASSET_GROUPS.description',
            'grp_status':  'ASSET_GROUPS.grp_status',
            'depr_method': 'ASSET_GROUPS.depr_method',
            'lifetime':    'ASSET_GROUPS.lifetime',
        })
        cols = ['ASSET_GROUPS.asset_group', 'ASSET_GROUPS.description', 'ASSET_GROUPS.grp_status', 'ASSET_GROUPS.depr_method', 'ASSET_GROUPS.lifetime']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_trans_flags' and check_id == 'DQ-AF-X03':
        failing = failing.rename(columns={
            'asset_id':   'ASSET_TRANS_FLAGS.asset_id',
            'trans_type': 'ASSET_TRANS_FLAGS.trans_type',
            'amount':     'ASSET_TRANS_FLAGS.amount',
        })
        cols = ['ASSET_TRANS_FLAGS.asset_id', 'ASSET_TRANS_FLAGS.trans_type', 'ASSET_TRANS_FLAGS.amount']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_trans_flags' and check_id == 'DQ-AF-X04':
        failing = failing.rename(columns={
            'asset_id':   'ASSET_TRANS_FLAGS.asset_id',
            'trans_date': 'ASSET_TRANS_FLAGS.trans_date',
        })
        cols = ['ASSET_TRANS_FLAGS.asset_id', 'ASSET_TRANS_FLAGS.trans_date']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_trans_flags' and check_id == 'DQ-AF-X05':
        failing = failing.rename(columns={
            'asset_id':     'ASSET_TRANS_FLAGS.asset_id',
            'depr_book_id': 'ASSET_TRANS_FLAGS.depr_book_id',
            'trans_type':   'ASSET_TRANS_FLAGS.trans_type',
        })
        cols = ['ASSET_TRANS_FLAGS.asset_id', 'ASSET_TRANS_FLAGS.depr_book_id', 'ASSET_TRANS_FLAGS.trans_type']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'acutrans' and check_id == 'AR_ORPHANED_TRANS':
        failing = failing.rename(columns={
            'voucher_no': 'AR_INVOICES.voucher_no',
            'apar_id':    'AR_INVOICES.apar_id',
        })
        if 'acuheader' in frames:
            cus_link = frames['acuheader'][['house', 'apar_id']].copy()
            cus_link = cus_link.drop_duplicates(subset=['house', 'apar_id'])
            cus_link = cus_link.rename(columns={'apar_id': 'CUSTOMER_MASTER.apar_id'})
            failing = failing.merge(cus_link,
                left_on=['house', 'AR_INVOICES.apar_id'],
                right_on=['house', 'CUSTOMER_MASTER.apar_id'],
                how='left')
        cols = ['AR_INVOICES.voucher_no', 'AR_INVOICES.apar_id', 'CUSTOMER_MASTER.apar_id']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'acutrans' and check_id == 'AR_TRANS_CUS_CLOSED':
        failing = failing.rename(columns={
            'voucher_no': 'AR_INVOICES.voucher_no',
            'apar_id':    'AR_INVOICES.apar_id',
        })
        if 'acuheader' in frames:
            cus_link = frames['acuheader'][['house', 'apar_id', 'status']].copy()
            cus_link = cus_link.drop_duplicates(subset=['house', 'apar_id'])
            cus_link = cus_link.rename(columns={
                'apar_id': 'CUSTOMER_MASTER.apar_id',
                'status':  'CUSTOMER_MASTER.status',
            })
            failing = failing.merge(cus_link,
                left_on=['house', 'AR_INVOICES.apar_id'],
                right_on=['house', 'CUSTOMER_MASTER.apar_id'],
                how='left')
        cols = ['AR_INVOICES.voucher_no', 'AR_INVOICES.apar_id', 'CUSTOMER_MASTER.apar_id', 'CUSTOMER_MASTER.status']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asutrans' and check_id == 'AP_ORPHANED_TRANS':
        summary = (
            failing.groupby('apar_id')
            .size()
            .reset_index(name='AP_INVOICES.transaction_count')
            .rename(columns={'apar_id': 'AP_INVOICES.apar_id'})
            .sort_values('AP_INVOICES.transaction_count', ascending=False)
        )
        return summary

    if table == 'asutrans' and check_id == 'AP_TRANS_SUP_CLOSED':
        failing = failing.rename(columns={
            'voucher_no': 'AP_INVOICES.voucher_no',
            'apar_id':    'AP_INVOICES.apar_id',
        })
        if 'asuheader' in frames:
            sup_link = frames['asuheader'][['house', 'apar_id', 'status']].copy()
            sup_link = sup_link.drop_duplicates(subset=['house', 'apar_id'])
            sup_link = sup_link.rename(columns={
                'apar_id': 'SUPPLIER_MASTER.apar_id',
                'status':  'SUPPLIER_MASTER.status',
            })
            failing = failing.merge(sup_link,
                left_on=['house', 'AP_INVOICES.apar_id'],
                right_on=['house', 'SUPPLIER_MASTER.apar_id'],
                how='left')
        cols = ['AP_INVOICES.voucher_no', 'AP_INVOICES.apar_id', 'SUPPLIER_MASTER.apar_id', 'SUPPLIER_MASTER.status']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asuhistr' and check_id == 'HIS_ORPHANED':
        failing = failing.rename(columns={
            'voucher_no': 'AP_HISTORY.voucher_no',
            'apar_id':    'AP_HISTORY.apar_id',
        })
        if 'asuheader' in frames:
            sup_link = frames['asuheader'][['house', 'apar_id']].copy()
            sup_link = sup_link.drop_duplicates(subset=['house', 'apar_id'])
            sup_link = sup_link.rename(columns={'apar_id': 'SUPPLIER_MASTER.apar_id'})
            failing = failing.merge(sup_link,
                left_on=['house', 'AP_HISTORY.apar_id'],
                right_on=['house', 'SUPPLIER_MASTER.apar_id'],
                how='left')
        cols = ['AP_HISTORY.voucher_no', 'AP_HISTORY.apar_id', 'SUPPLIER_MASTER.apar_id']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'acuhistr' and check_id == 'AR_HIS_ORPHANED':
        failing = failing.rename(columns={
            'voucher_no': 'AR_HISTORY.voucher_no',
            'apar_id':    'AR_HISTORY.apar_id',
        })
        if 'acuheader' in frames:
            cus_link = frames['acuheader'][['house', 'apar_id']].copy()
            cus_link = cus_link.drop_duplicates(subset=['house', 'apar_id'])
            cus_link = cus_link.rename(columns={'apar_id': 'CUSTOMER_MASTER.apar_id'})
            failing = failing.merge(cus_link,
                left_on=['house', 'AR_HISTORY.apar_id'],
                right_on=['house', 'CUSTOMER_MASTER.apar_id'],
                how='left')
        cols = ['AR_HISTORY.voucher_no', 'AR_HISTORY.apar_id', 'CUSTOMER_MASTER.apar_id']
        return failing[[c for c in cols if c in failing.columns]]

    if table in ['asutrans', 'asuhistr'] and 'asuheader' in frames:
        # asuheader unique key is (client, apar_id) — one row per supplier per
        # client code. Join on (client, apar_id) to get the exact supplier name
        # for each transaction row's client allocation.
        join_cols = ['client', 'apar_id'] if 'client' in failing.columns else ['house', 'apar_id']
        master = frames['asuheader'][join_cols + ['apar_name', 'status']].copy()
        master = master.drop_duplicates(subset=join_cols)
        master.columns = join_cols + ['Master_Supplier_Name', 'Master_Status']
        failing = failing.merge(master, on=join_cols, how='left')

    if table in ['acutrans', 'acuhistr'] and 'acuheader' in frames:
        join_cols = ['client', 'apar_id'] if 'client' in failing.columns else ['house', 'apar_id']
        master = frames['acuheader'][join_cols + ['apar_name', 'status']].copy()
        master = master.drop_duplicates(subset=join_cols)
        master.columns = join_cols + ['Master_Customer_Name', 'Master_Status']
        failing = failing.merge(master, on=join_cols, how='left')

    if check_id == 'PO_HDR_LINE_CONTRACT_MISMATCH' and 'apoheader' in frames:
        # Explicit join on (client, order_id) — the real apoheader/apodetail key.
        # The generic referential-integrity join below would instead resolve to
        # (house, apar_id, voucher_no), since client/order_id aren't in its
        # candidate key list — that's a different, unverified relationship, not
        # the actual PO composite key, so this check bypasses it entirely.
        hdr = frames['apoheader'][frames['apoheader']['house'] == house][['client', 'order_id', 'contract_id']]
        hdr = hdr.drop_duplicates(subset=['client', 'order_id']).rename(columns={'contract_id': 'apoheader.contract_id'})
        failing = failing.merge(hdr, on=['client', 'order_id'], how='left')
        failing = failing.rename(columns={
            'order_id': 'apodetail.order_id',
            'line_no':  'apodetail.line_no',
            'contract_id': 'apodetail.contract_id',
            **{c: f'apodetail.{c}' for c in _PO_LINE_STANDARD_FIELDS},
        })
        cols = ['apodetail.order_id', 'apodetail.line_no', 'apodetail.contract_id', 'apoheader.contract_id'] + \
               [f'apodetail.{c}' for c in _PO_LINE_STANDARD_FIELDS]
        return failing[[c for c in cols if c in failing.columns]]

    if check_id == 'PO_FINISHED_WITH_BALANCE' and 'apodetail' in frames:
        # Explicit join on (client, order_id), same reasoning as above. Shows both
        # arr_amount and invoiced (not just the coalesced result), since real data
        # shows the two disagreeing about invoicing status in both directions
        # (QUESTIONS_FOR_PARLIAMENT.md #5) — the reviewer needs to see why the
        # GREATEST-of-the-two logic decided what it did, not just trust the outcome.
        dtl = frames['apodetail'][frames['apodetail']['house'] == house].copy()
        dtl['effective_invoiced'] = dtl[['arr_amount', 'invoiced']].max(axis=1)
        agg = dtl.groupby(['client', 'order_id']).agg(
            po_value=('amount', 'sum'), po_arr=('arr_amount', 'sum'),
            po_invoiced_field=('invoiced', 'sum'), po_effective=('effective_invoiced', 'sum'),
        ).reset_index()
        agg['uninvoiced_pct'] = (
            (agg['po_value'] - agg['po_effective']) / agg['po_value'].replace(0, np.nan) * 100
        ).round(2)
        agg[['po_value', 'po_arr', 'po_invoiced_field']] = agg[['po_value', 'po_arr', 'po_invoiced_field']].round(2)
        agg = agg.rename(columns={
            'po_value':          'apodetail.SUM(amount)',
            'po_arr':            'apodetail.SUM(arr_amount)',
            'po_invoiced_field': 'apodetail.SUM(invoiced)',
        })
        agg = agg.drop(columns=['po_effective'])
        failing = failing.merge(agg, on=['client', 'order_id'], how='left')
        failing = failing.rename(columns={
            'order_id': 'apoheader.order_id',
            'apar_id':  'apoheader.apar_id',
            'status':   'apoheader.status',
        })
        cols = ['apoheader.order_id', 'apoheader.apar_id', 'apoheader.status',
                'apodetail.SUM(amount)', 'apodetail.SUM(arr_amount)', 'apodetail.SUM(invoiced)',
                'uninvoiced_pct']
        return failing[[c for c in cols if c in failing.columns]]

    if check_id == 'PO_ORPHANED_SUPPLIER':
        # No enrichment needed — the evidence here is the absence of a match, which
        # showing the raw apar_id already proves. Bypasses the generic join below,
        # which would join on (house, apar_id) only, not the real (client, apar_id)
        # asuheader key, and could show a misleading match from the wrong client.
        failing = failing.rename(columns={
            'client':   'apoheader.client',
            'order_id': 'apoheader.order_id',
            'apar_id':  'apoheader.apar_id',
            'status':   'apoheader.status',
        })
        cols = ['apoheader.client', 'apoheader.order_id', 'apoheader.apar_id', 'apoheader.status']
        return failing[[c for c in cols if c in failing.columns]]

    if check_id == 'PO_INACTIVE_SUPPLIER' and 'asuheader' in frames:
        # Explicit join on (client, apar_id) — asuheader's real unique key — so the
        # supplier's own status is shown next to the PO's, proving the claim.
        sup = frames['asuheader'][frames['asuheader']['house'] == house][['client', 'apar_id', 'status']]
        sup = sup.drop_duplicates(subset=['client', 'apar_id']).rename(columns={'status': 'asuheader.status'})
        failing = failing.merge(sup, on=['client', 'apar_id'], how='left')
        failing = failing.rename(columns={
            'order_id': 'apoheader.order_id',
            'apar_id':  'apoheader.apar_id',
            'status':   'apoheader.status',
        })
        cols = ['apoheader.order_id', 'apoheader.apar_id', 'apoheader.status', 'asuheader.status']
        return failing[[c for c in cols if c in failing.columns]]

    if check_id == 'PO_LINE_ORPHAN_ACCOUNT':
        # No enrichment needed, same reasoning as PO_ORPHANED_SUPPLIER — the
        # account's absence from the chart of accounts is the evidence.
        failing = failing.rename(columns={
            'order_id': 'apodetail.order_id',
            'line_no':  'apodetail.line_no',
            'account':  'apodetail.account',
            **{c: f'apodetail.{c}' for c in _PO_LINE_STANDARD_FIELDS},
        })
        cols = ['apodetail.order_id', 'apodetail.line_no', 'apodetail.account'] + \
               [f'apodetail.{c}' for c in _PO_LINE_STANDARD_FIELDS]
        return failing[[c for c in cols if c in failing.columns]]

    if check_id == 'PO_LINE_CLOSED_ACCOUNT' and 'aglaccounts' in frames:
        # Explicit join on account (house-scoped, matching GL_BAL_ORPHAN_ACC's own
        # convention) so the account's own status is shown next to the PO line.
        coa = frames['aglaccounts'][frames['aglaccounts']['house'] == house][['account', 'status']]
        coa = coa.drop_duplicates(subset=['account']).rename(columns={'status': 'aglaccounts.status'})
        failing = failing.merge(coa, on='account', how='left')
        failing = failing.rename(columns={
            'order_id': 'apodetail.order_id',
            'line_no':  'apodetail.line_no',
            'account':  'apodetail.account',
            **{c: f'apodetail.{c}' for c in _PO_LINE_STANDARD_FIELDS},
        })
        cols = ['apodetail.order_id', 'apodetail.line_no', 'apodetail.account', 'aglaccounts.status'] + \
               [f'apodetail.{c}' for c in _PO_LINE_STANDARD_FIELDS]
        return failing[[c for c in cols if c in failing.columns]]

    # Generic Join Logic for Referential Integrity
    if joined_table and joined_table in frames:
        jt_df = frames[joined_table].copy()
        
        # Identify join keys with support for aliased keys
        join_pairs = [] # List of (failing_key, joined_key)
        
        if 'house' in failing.columns and 'house' in jt_df.columns:
            join_pairs.append(('house', 'house'))
        
        # Common key candidates
        key_candidates = [
            ('asset_id', 'asset_id'),
            ('apar_id', 'apar_id'),
            ('account', 'account'),
            ('dim_value', 'dim_value'),
            ('voucher_no', 'voucher_no'),
            ('dim_1', 'dim_value'),     # GL Transactions -> Dims
            ('parent_asset', 'asset_id'),# Asset Master -> Parent Asset
            ('rel_value', 'dim_value')   # Dim Hierarchies
        ]
        
        for f_key, j_key in key_candidates:
            if f_key in failing.columns and j_key in jt_df.columns:
                # If we already have a primary key (non-house), don't add more unless relevant
                join_pairs.append((f_key, j_key))
        
        if join_pairs:
            f_keys = [p[0] for p in join_pairs]
            j_keys = [p[1] for p in join_pairs]
            
            # Drop duplicates on join keys to avoid cartesian products
            jt_df = jt_df.drop_duplicates(subset=j_keys)
            
            # Select useful columns from joined table
            jt_cols = [c for c in jt_df.columns if c in j_keys or c in (base_cols or []) or c == 'status']
            jt_subset = jt_df[jt_cols].copy()
            
            # Prefix joined columns to distinguish them
            prefix = "STANDARD_" if joined_table == "asset_groups" else f"Ref_{joined_table}_"
            rename_map = {c: f"{prefix}{c}" for c in jt_subset.columns if c not in j_keys}
            jt_subset = jt_subset.rename(columns=rename_map)
            
            # Perform merge with potentially different key names
            failing = failing.merge(jt_subset, left_on=f_keys, right_on=j_keys, how='left')
            
            # If keys had different names, remove the redundant joined keys
            for f_k, j_k in join_pairs:
                if f_k != j_k and j_k in failing.columns:
                    failing = failing.drop(columns=[j_k])

    # Reorder so all source table columns come first, then joined/Ref_ columns
    source_cols = [c for c in failing.columns if c in df_table.columns]
    other_cols = [c for c in failing.columns if c not in df_table.columns]
    failing = failing[source_cols + other_cols]

    # Add source indicator to columns for clarity in joins
    cols = []
    for c in failing.columns:
        if c in df_table.columns:
            cols.append(f"{table}.{c}")
        else:
            cols.append(c)
    failing.columns = cols

    # Convert datetime64 columns to YYYY-MM-DD strings so the DataTable renders
    # them correctly. Without this, NaT values (e.g. period_from = 0 in source
    # data, below the Excel serial parse range) show as "—" even though the raw
    # CSV has a value.
    for col in failing.columns:
        if pd.api.types.is_datetime64_any_dtype(failing[col]):
            failing[col] = failing[col].dt.strftime('%Y-%m-%d').where(
                failing[col].notna(), other=''
            )

    return failing

def build_aging_analysis(frames):
    """Builds AP/AR aging summaries."""
    today = pd.Timestamp(date.today())
    results = {}

    for module, table, label in [('ap', 'asutrans', 'AP'), ('ar', 'acutrans', 'AR')]:
        if table not in frames:
            continue
        df = frames[table].copy()
        # Open items only
        df = df[df['status'].isin(['N','R','I']) & df['due_date'].notna()].copy()
        df['days_overdue'] = (today - df['due_date']).dt.days
        df['aging_bucket'] = pd.cut(
            df['days_overdue'],
            bins=[-9999, 0, 30, 60, 90, 180, 999999],
            labels=['Not Yet Due', '0-30 Days', '31-60 Days', '61-90 Days', '91-180 Days', '180+ Days']
        )
        df['rest_amount'] = pd.to_numeric(df['rest_amount'], errors='coerce').fillna(0).abs()
        
        agg = df.groupby(['house', 'aging_bucket'], observed=True).agg(
            count=('voucher_no', 'count'),
            balance=('rest_amount', 'sum')
        ).reset_index()
        results[label] = agg
        results[f'{label}_raw'] = df # Store raw for drill-down
        
    return results
