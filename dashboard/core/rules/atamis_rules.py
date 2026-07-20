import pandas as pd


def _is_blank(s):
    return s.isna() | (s.astype(str).str.strip().isin(['', 'nan', 'None']))


def _unit4_supplier_not_in_atamis(df, frames):
    """Flags active Unit4 suppliers (asuheader) whose apar_id has no matching
    Creditor Ref in the Atamis supplier list. The reverse direction of
    ATAMIS_SUPPLIER_NOT_IN_UNIT4 — a supplier can transact in Unit4 without ever
    being registered in Atamis (e.g. payroll/HMRC-type suppliers that never go
    through procurement), so this is Medium rather than High severity."""
    if df.empty or 'atamis_suppliers' not in frames:
        return pd.Series(False, index=df.index)

    atamis_ids = set(
        frames['atamis_suppliers']['creditor_ref'].dropna().astype(str).str.strip()
    )
    ids = df['apar_id'].astype(str).str.strip()
    return ~ids.isin(atamis_ids)


def _atamis_contract_ref_not_in_po(df, frames):
    """Flags HOC/Joint Atamis contracts whose Contract Reference has no matching
    contract_id anywhere in po_detail_HOC. PO is HoC-only (population is already
    restricted to house in (HOC, Joint) in data_engine.py), so an HOL contract
    is never expected to have a PO match and never reaches this lambda."""
    if df.empty or 'apodetail' not in frames:
        return pd.Series(False, index=df.index)

    po_refs = set(
        frames['apodetail']['contract_id'].dropna().astype(str).str.strip()
    )
    refs = df['contract_ref'].astype(str).str.strip()
    return ~refs.isin(po_refs)


def _atamis_commit_vs_spend_mismatch(df, frames):
    """Flags contracts where the two Unit4 views of the same spend — the
    Commitments view's posted_amount and the Spend Details view's own posted
    figure — disagree by more than a small materiality threshold. The two are
    separate Agresso views of the same underlying ledger and are not guaranteed
    to reconcile; Parliament flagged this as a known area of potential
    discrepancy between the systems."""
    if df.empty or 'atamis_commitments' not in frames:
        return pd.Series(False, index=df.index)

    commit = (
        frames['atamis_commitments'][['u4_contract_id', 'posted_amount']]
        .drop_duplicates(subset=['u4_contract_id'])
        .rename(columns={'posted_amount': '_commit_posted'})
    )
    merged = df[['u4_contract_id', 'posted']].merge(commit, on='u4_contract_id', how='left')
    commit_posted = pd.to_numeric(merged['_commit_posted'], errors='coerce')
    spend_posted = pd.to_numeric(merged['posted'], errors='coerce')
    diff = (commit_posted - spend_posted).abs()
    return (commit_posted.notna() & (diff > 1.00)).values


def get_atamis_checks():
    return [

        # ---------------------------------------------------------------
        # ATAMIS CONTRACTS — atamis_contracts / contracts_report.csv
        # Spans both houses via the Organisation field (HOC/HOL/Joint) — not
        # split into per-house files like every other domain.
        # ---------------------------------------------------------------

        ('ATAMIS_CONTRACT_NO_REF',
         30, 'Atamis Contract', 'Completeness', 'Medium',
         'Contract has no Contract Reference',
         'Every contract record must carry a Contract Reference. '
         'The new system uses this as the primary handle for the contract and it is also the only field that links a contract back to any matching purchase orders. '
         'A contract with no reference cannot be cross-checked against PO or spend data and cannot be tracked through migration.',
         'Add the correct Contract Reference to the affected contract in Atamis.',
         'atamis_contracts', None,
         "WHERE \"Contract Reference\" IS NULL OR TRIM(\"Contract Reference\") = ''",
         lambda df: _is_blank(df['contract_ref'])),

        ('ATAMIS_CONTRACT_NO_SUPPLIER',
         30, 'Atamis Contract', 'Completeness', 'Low',
         'Contract has no supplier recorded',
         'Most contracts are expected to name a supplier. '
         'Some genuinely have none, such as inter-organisational MOUs, so this is a review signal rather than a hard rule. '
         'A contract with no supplier cannot be linked to that supplier\'s spend or master data.',
         'Confirm whether the affected contract genuinely has no supplier, or add the missing supplier name in Atamis.',
         'atamis_contracts', None,
         "WHERE Supplier IS NULL OR TRIM(Supplier) = ''",
         lambda df: _is_blank(df['supplier_name'])),

        ('ATAMIS_CONTRACT_NO_DATES',
         30, 'Atamis Contract', 'Completeness', 'Medium',
         'Contract is missing a start or end date',
         'Every contract must carry both a Start Date and an End Date. '
         'Contract duration drives renewal planning and expiry reporting in the new system. '
         'A contract with a missing date cannot be placed correctly in that timeline.',
         'Add the missing start or end date to the affected contract in Atamis.',
         'atamis_contracts', None,
         "WHERE \"Start Date\" IS NULL OR \"End Date\" IS NULL",
         lambda df: df['start_date'].isna() | df['end_date'].isna()),

        ('ATAMIS_CONTRACT_ORG_INVALID',
         30, 'Atamis Contract', 'Validity', 'Low',
         'Contract Organisation is not one of the expected values',
         "Every contract's Organisation field must be HOC, HOL, or Joint. "
         'This is the only field that tells the new system which house (or both) a contract belongs to, since Atamis contracts are not otherwise split by house. '
         'A contract with an unexpected value here cannot be assigned to a house at all.',
         'Correct the Organisation value on the affected contract in Atamis.',
         'atamis_contracts', None,
         "WHERE Organisation NOT IN ('HOC', 'HOL', 'Joint')",
         lambda df: ~df['organisation'].astype(str).str.strip().str.upper().isin(['HOC', 'HOL', 'JOINT'])),

        ('ATAMIS_CONTRACT_DATE_INVALID',
         30, 'Atamis Contract', 'Validity', 'Medium',
         'Contract End Date is before its Start Date',
         "A contract's End Date must not fall before its own Start Date. "
         'A contract with dates the wrong way round cannot be placed correctly on a migration timeline and signals a data entry error.',
         'Correct the start or end date on the affected contract in Atamis.',
         'atamis_contracts', None,
         "WHERE \"End Date\" < \"Start Date\"",
         lambda df: df['end_date'] < df['start_date']),

        ('ATAMIS_CONTRACT_DUP_REF',
         30, 'Atamis Contract', 'Uniqueness', 'High',
         'Duplicate Contract Reference across contract records',
         'Every populated Contract Reference must be unique. '
         'A duplicate reference means two contract records are competing for the same identifier, which the new system cannot load as-is and which breaks the link to PO data for both records.',
         'Investigate the duplicate contract records in Atamis and determine which, if either, is the genuine one.',
         'atamis_contracts', None,
         "WHERE \"Contract Reference\" HAVING COUNT(*) > 1",
         lambda df: df['contract_ref'].notna() & df.duplicated(subset=['contract_ref'], keep=False) & ~_is_blank(df['contract_ref'])),

        ('ATAMIS_CONTRACT_REF_NOT_IN_PO',
         30, 'Atamis Contract', 'Consistency', 'Medium',
         'Contract Reference has no matching purchase order',
         "Every HoC or Joint contract's Contract Reference is expected to appear as a contract_id on at least one purchase order line, since PO data is HoC-only. "
         'A contract with no matching PO line may simply predate the PO system, or may be a genuine linking gap between Atamis and Unit4 that is worth reviewing before both systems are relied on together.',
         'Confirm with the business owner whether the affected contract is expected to have purchase orders raised against it, and investigate the missing link if so.',
         'atamis_contracts', 'apodetail',
         "WHERE Organisation IN ('HOC','Joint') AND \"Contract Reference\" NOT IN (SELECT contract_id FROM apodetail)",
         _atamis_contract_ref_not_in_po),

        # ---------------------------------------------------------------
        # ATAMIS SUPPLIERS — atamis_suppliers / supplier_data_report.csv
        # Creditor Ref (not Supplier: ID, a Salesforce record ID) is the join
        # key to the Unit4 supplier master.
        # ---------------------------------------------------------------

        ('ATAMIS_SUPPLIER_NO_CREDITOR_REF',
         33, 'Atamis Supplier', 'Completeness', 'High',
         'Atamis supplier has no Creditor Ref',
         "Every Atamis supplier record must carry a Creditor Ref. "
         "This is the only field that links an Atamis supplier back to its Unit4 supplier master record — Supplier: ID is a Salesforce record identifier and cannot be used for this join. "
         'A supplier with no Creditor Ref cannot be reconciled against Unit4 at all.',
         'Add the correct Creditor Ref to the affected supplier record in Atamis.',
         'atamis_suppliers', None,
         "WHERE \"Creditor Ref\" IS NULL OR TRIM(\"Creditor Ref\") = ''",
         lambda df: _is_blank(df['creditor_ref'])),

        ('ATAMIS_SUPPLIER_DUP_CREDITOR_REF',
         33, 'Atamis Supplier', 'Uniqueness', 'Medium',
         'Duplicate Creditor Ref across Atamis supplier records',
         'Every populated Creditor Ref is expected to identify a single supplier. '
         'A Creditor Ref shared by more than one Atamis supplier record is ambiguous when matching back to Unit4 and needs review before the two systems can be reconciled record-for-record.',
         'Investigate the duplicate Creditor Ref values in Atamis and confirm which supplier record, if any, is correct.',
         'atamis_suppliers', None,
         "WHERE \"Creditor Ref\" HAVING COUNT(*) > 1",
         lambda df: df.duplicated(subset=['creditor_ref'], keep=False) & ~_is_blank(df['creditor_ref'])),

        ('ATAMIS_SUPPLIER_NOT_IN_UNIT4',
         33, 'Atamis Supplier', 'Consistency', 'High',
         'Atamis supplier has no matching Unit4 supplier record',
         "Every Atamis supplier's Creditor Ref is expected to match an apar_id in the Unit4 supplier master, in either house. "
         'A supplier registered in Atamis but absent from Unit4 has never actually transacted, or its Creditor Ref was recorded incorrectly, either of which needs resolving before go-live.',
         'Confirm whether the affected supplier genuinely has no Unit4 record, or correct its Creditor Ref in Atamis.',
         'atamis_suppliers', None,
         "WHERE \"Creditor Ref\" NOT IN (SELECT apar_id FROM asuheader)",
         lambda df: df['house'] == 'Unknown'),

        ('UNIT4_SUPPLIER_NOT_IN_ATAMIS',
         33, 'Unit4 Supplier', 'Consistency', 'Medium',
         'Unit4 supplier has no matching Atamis record',
         'Every active Unit4 supplier is expected to have a corresponding Creditor Ref entry in the Atamis supplier list if it has ever been contracted through procurement. '
         'A supplier that transacts in Unit4 but was never registered in Atamis is not unusual for payroll, tax, or individual-type suppliers, but is still worth reviewing for anything that should have gone through procurement.',
         'Confirm whether the affected supplier is expected to be in Atamis, and register it there if so.',
         'asuheader', 'atamis_suppliers',
         "WHERE apar_id NOT IN (SELECT \"Creditor Ref\" FROM atamis_suppliers)",
         _unit4_supplier_not_in_atamis),

        # ---------------------------------------------------------------
        # CONTRACT COMMITMENTS — atamis_commitments / contract_total_commitments.csv
        # Unit4 view #1 of contract spend. Supplier ID is the join key to
        # asuheader.apar_id.
        # ---------------------------------------------------------------

        ('ATAMIS_COMMIT_NO_SUPPLIER_ID',
         31, 'Contract Commitment', 'Completeness', 'High',
         'Contract commitment record has no Supplier ID',
         'Every contract commitment record must carry a Supplier ID. '
         'This is the only field that links a commitment back to the Unit4 supplier master and determines which house it belongs to. '
         'A record with no Supplier ID cannot be assigned a house and cannot be reconciled against the supplier master.',
         'Add the correct Supplier ID to the affected commitment record in Unit4.',
         'atamis_commitments', None,
         "WHERE \"Supplier ID\" IS NULL OR TRIM(\"Supplier ID\") = ''",
         lambda df: _is_blank(df['supplier_id'])),

        ('ATAMIS_COMMIT_DATE_INVALID',
         31, 'Contract Commitment', 'Validity', 'Medium',
         'Contract commitment Date To is before its Date From',
         "A contract commitment's Date To must not fall before its own Date From. "
         'A record with dates the wrong way round signals a data entry error and cannot be placed correctly on a migration timeline.',
         'Correct the date range on the affected commitment record in Unit4.',
         'atamis_commitments', None,
         "WHERE \"Contract Date To\" < \"Contract Date From\"",
         lambda df: df['date_to'] < df['date_from']),

        ('ATAMIS_COMMIT_REMAINING_MISMATCH',
         31, 'Contract Commitment', 'Validity', 'Medium',
         "Remaining Amount does not equal Amount Limit minus Posted Amount",
         "A contract commitment's Remaining Amount is expected to equal its Contract Amount Limit minus its Posted Amount. "
         'A mismatch here points to raw data corruption or a calculation error in one of the three stored fields, not a process issue.',
         'Investigate which of Amount Limit, Posted Amount, or Remaining Amount is wrong on the affected commitment record in Unit4.',
         'atamis_commitments', None,
         "WHERE ABS(\"Remaining Amount\" - (\"Contract Amount Limit\" - \"Posted Amount\")) > 1.00",
         lambda df: ((pd.to_numeric(df['amount_limit'], errors='coerce').fillna(0)
                      - pd.to_numeric(df['posted_amount'], errors='coerce').fillna(0))
                     - pd.to_numeric(df['remaining_amount'], errors='coerce').fillna(0)).abs() > 1.00),

        ('ATAMIS_COMMIT_OVERSPEND',
         31, 'Contract Commitment', 'Consistency', 'Medium',
         'Contract has been posted beyond its authorised amount limit',
         "A contract's Posted Amount is not expected to exceed its Contract Amount Limit, leaving Remaining Amount negative. "
         'A contract posted beyond its authorised limit represents spend that was never formally approved and should be reviewed before cutover, whether or not the underlying arithmetic in Remaining Amount is otherwise correct.',
         "Confirm with the contract owner whether the affected contract's limit should be increased, or whether the overspend needs investigating.",
         'atamis_commitments', None,
         "WHERE \"Remaining Amount\" < -1.00",
         lambda df: pd.to_numeric(df['remaining_amount'], errors='coerce').fillna(0) < -1.00),

        ('ATAMIS_COMMIT_DUP_ID',
         31, 'Contract Commitment', 'Uniqueness', 'High',
         'Duplicate Contract Id across commitment records',
         'Every Contract Id in the commitments view is expected to be unique. '
         'A duplicate Contract Id means two records are competing for the same contract, which the new system cannot load as-is and which also breaks the join to the Spend Details view.',
         'Investigate the duplicate Contract Id values in Unit4 and confirm which record, if either, is genuine.',
         'atamis_commitments', None,
         "WHERE \"Contract Id\" HAVING COUNT(*) > 1",
         lambda df: df.duplicated(subset=['u4_contract_id'], keep=False) & ~_is_blank(df['u4_contract_id'])),

        ('ATAMIS_COMMIT_SUPPLIER_ORPHAN',
         31, 'Contract Commitment', 'Consistency', 'High',
         'Contract commitment references a supplier that does not exist in Unit4',
         "Every contract commitment's Supplier ID is expected to match an apar_id in the Unit4 supplier master, in either house. "
         'A commitment referencing a supplier that cannot be found has no route back to the supplier master and cannot be reconciled at cutover.',
         'Correct the Supplier ID on the affected commitment record, or add the missing supplier to the Unit4 supplier master if it should exist.',
         'atamis_commitments', None,
         "WHERE \"Supplier ID\" NOT IN (SELECT apar_id FROM asuheader)",
         lambda df: df['house'] == 'Unknown'),

        # ---------------------------------------------------------------
        # CONTRACT SPEND — atamis_spend / contracts_spend_details.csv
        # Unit4 view #2 of the same contracts, joined to atamis_commitments
        # via u4_contract_id (Contract in the source extract).
        # ---------------------------------------------------------------

        ('ATAMIS_SPEND_CONTRACT_ORPHAN',
         32, 'Contract Spend', 'Consistency', 'High',
         'Spend record has no matching contract in the Commitments view',
         'Every record in the Spend Details view is expected to match a Contract Id in the Commitments view. '
         'A spend record with no matching commitment cannot be assigned a house and cannot be reconciled against the rest of the contract data.',
         'Investigate the affected Contract Id in Unit4 and confirm why it appears in Spend Details but not in Commitments.',
         'atamis_spend', 'atamis_commitments',
         "WHERE Contract NOT IN (SELECT \"Contract Id\" FROM atamis_commitments)",
         lambda df: df['house'] == 'Unknown'),

        ('ATAMIS_SPEND_NEGATIVE_POSTED',
         32, 'Contract Spend', 'Validity', 'Low',
         'Spend record has a negative Posted value',
         'A contract\'s Posted value in the Spend Details view is ordinarily expected to be positive. '
         'A negative value may reflect a genuine credit note or reversal, but is worth a second look given no credit-note category is confirmed for this extract.',
         'Confirm whether the affected negative Posted value is a genuine credit or reversal, or a data entry error, in Unit4.',
         'atamis_spend', None,
         "WHERE Posted < 0",
         lambda df: pd.to_numeric(df['posted'], errors='coerce').fillna(0) < 0),

        ('ATAMIS_COMMIT_VS_SPEND_MISMATCH',
         32, 'Contract Spend', 'Consistency', 'Medium',
         "Commitments and Spend Details views disagree on Posted amount",
         "A contract's Posted Amount in the Commitments view is expected to agree with its own Posted figure in the Spend Details view — both are Agresso views of the same underlying ledger. "
         'A material disagreement between the two suggests one of the views is stale or the two are computed on a different basis, and should be reconciled before either is relied on for migration decisions.',
         'Confirm with the Unit4 report owner which view is authoritative for the affected contract, and reconcile the difference.',
         'atamis_spend', 'atamis_commitments',
         "WHERE ABS(atamis_commitments.\"Posted Amount\" - atamis_spend.Posted) > 1.00",
         _atamis_commit_vs_spend_mismatch),
    ]
