import numpy as np
import pandas as pd


def _is_blank(s):
    return s.isna() | (s.astype(str).str.strip().isin(['', 'nan', 'None']))


def _po_finished_with_balance(df, frames):
    """Flags Finished (F) POs where more than 5% of ordered value is still
    unaccounted for by invoicing. Real PO line data shows arr_amount and
    invoiced disagreeing about invoicing status in both directions (see
    QUESTIONS_FOR_PARLIAMENT.md #5) — one field is sometimes zero while the
    other genuinely shows the line as invoiced. Taking whichever of the two
    is larger per line avoids under-counting real progress because of that
    field ambiguity, rather than trusting either one alone. Same materiality
    threshold as the PO tab's finished_with_balance stat in dashboard/tabs/po.py."""
    if df.empty or 'apodetail' not in frames:
        return pd.Series(False, index=df.index)

    house = df['house'].iloc[0]
    dtl = frames['apodetail']
    dtl = dtl[dtl['house'] == house].copy()
    dtl['effective_invoiced'] = dtl[['arr_amount', 'invoiced']].max(axis=1)
    agg = dtl.groupby(['client', 'order_id']).agg(
        po_value=('amount', 'sum'), po_invoiced=('effective_invoiced', 'sum'),
    ).reset_index()
    agg['uninvoiced_pct'] = (
        (agg['po_value'] - agg['po_invoiced']) / agg['po_value'].replace(0, np.nan)
    ) * 100
    flagged = agg.loc[agg['uninvoiced_pct'] > 5, ['client', 'order_id']].assign(_flag=True)

    merged = df[['client', 'order_id']].merge(flagged, on=['client', 'order_id'], how='left')
    return merged['_flag'].eq(True).values


def _po_line_status_mismatch(df, frames):
    """Flags apodetail lines whose own status differs from their PO header's
    status. The real-data meaning of this divergence is not yet confirmed —
    see CLAUDE.md's PO Domain section — so this check is kept Low severity."""
    if df.empty or 'apoheader' not in frames:
        return pd.Series(False, index=df.index)

    house = df['house'].iloc[0]
    hdr = frames['apoheader']
    hdr = (
        hdr[hdr['house'] == house][['client', 'order_id', 'status']]
        .drop_duplicates(subset=['client', 'order_id'])
        .rename(columns={'status': 'hdr_status'})
    )
    merged = df[['client', 'order_id', 'status']].merge(hdr, on=['client', 'order_id'], how='left')
    return (merged['status'].astype(str) != merged['hdr_status'].astype(str)).values


def _po_orphaned_supplier(df, frames):
    """Flags POs whose apar_id doesn't exist in the supplier master (asuheader)
    for the same (client, apar_id) — asuheader's real unique key, since the same
    apar_id can appear under multiple HOC client codes. Blank apar_id is
    PO_NO_SUPPLIER's concern, not this one."""
    if df.empty or 'asuheader' not in frames:
        return pd.Series(False, index=df.index)

    house = df['house'].iloc[0]
    sup = (
        frames['asuheader'][frames['asuheader']['house'] == house][['client', 'apar_id']]
        .drop_duplicates().assign(_exists=True)
    )
    merged = df[['client', 'apar_id']].merge(sup, on=['client', 'apar_id'], how='left')
    orphaned = merged['_exists'].isna().values
    return orphaned & ~_is_blank(df['apar_id']).values


def _po_inactive_supplier(df, frames):
    """Flags active POs (O/N/A) whose supplier is Closed in the supplier master —
    an active commitment sitting against a supplier that's since been marked
    inactive. Joins on (client, apar_id), the real asuheader key."""
    if df.empty or 'asuheader' not in frames:
        return pd.Series(False, index=df.index)

    house = df['house'].iloc[0]
    sup = (
        frames['asuheader'][frames['asuheader']['house'] == house][['client', 'apar_id', 'status']]
        .drop_duplicates(subset=['client', 'apar_id'])
        .rename(columns={'status': 'supplier_status'})
    )
    merged = df[['client', 'apar_id']].merge(sup, on=['client', 'apar_id'], how='left')
    return (merged['supplier_status'] == 'C').values


def _po_line_orphan_account(df, frames):
    """Flags PO lines whose account doesn't exist in the chart of accounts
    (aglaccounts) for the same house. Matches on account alone (not client) —
    same convention as GL_BAL_ORPHAN_ACC, since HOC account codes are shared
    across its client codes. Blank account is PO_LINE_NO_ACCOUNT's concern."""
    if df.empty or 'aglaccounts' not in frames:
        return pd.Series(False, index=df.index)

    house = df['house'].iloc[0]
    valid_accounts = frames['aglaccounts'][frames['aglaccounts']['house'] == house]['account']
    orphaned = ~df['account'].isin(valid_accounts)
    return orphaned & ~_is_blank(df['account'])


def _po_line_closed_account(df, frames):
    """Flags PO lines posting to a GL account that exists but is Closed
    (status != 'N') in the chart of accounts. Orphaned accounts (not found at
    all) are PO_LINE_ORPHAN_ACCOUNT's concern, not this one."""
    if df.empty or 'aglaccounts' not in frames:
        return pd.Series(False, index=df.index)

    house = df['house'].iloc[0]
    coa = (
        frames['aglaccounts'][frames['aglaccounts']['house'] == house][['account', 'status']]
        .drop_duplicates(subset=['account'])
        .rename(columns={'status': 'account_status'})
    )
    merged = df[['account']].merge(coa, on='account', how='left')
    return (merged['account_status'].notna() & (merged['account_status'] != 'N')).values


def _po_line_never_matched(df):
    """Flags Finished (F) lines with clear evidence of activity (received
    and/or invoiced) but where the matching-specific fields (arr_amount,
    arr_val) are completely zero. Distinct from PO_FINISHED_WITH_BALANCE,
    which aggregates across a whole PO and only fires above a 5% threshold —
    a single old line like this can wash out of that aggregate if the rest
    of the PO reconciled normally. Population is scoped to status == 'F' in
    data_engine.py, so df here is already Finished lines only."""
    vow = pd.to_numeric(df['vow_amount'], errors='coerce').fillna(0)
    invoiced = pd.to_numeric(df['invoiced'], errors='coerce').fillna(0)
    arr_amount = pd.to_numeric(df['arr_amount'], errors='coerce').fillna(0)
    arr_val = pd.to_numeric(df['arr_val'], errors='coerce').fillna(0)
    has_activity = (vow.abs() > 0.01) | (invoiced.abs() > 0.01)
    never_matched = (arr_amount.abs() <= 0.01) & (arr_val.abs() <= 0.01)
    return has_activity & never_matched


def _po_line_stale_unresolved(df):
    """Flags lines still genuinely open (population excludes T/C/F in
    data_engine.py) whose deliv_date is more than 30 days old — delivered
    but stalled before progressing to invoice or close. Blank deliv_date is
    a separate completeness question, not staleness, so it is not flagged
    here."""
    days = (pd.Timestamp.today() - df['deliv_date']).dt.days
    return (days > 30).fillna(False)


def _po_hdr_line_date_mismatch(df, frames):
    """Flags apodetail lines whose own order_date differs from their PO
    header's order_date — both fields are extracted independently (see
    po_header_HOC_run.sql / po_detail_HOC_run.sql). Same open question as
    PO_HDR_LINE_STATUS_MISMATCH about whether these are expected to always
    match; only flags where both dates are actually present, so a blank line
    date isn't miscounted as a mismatch."""
    if df.empty or 'apoheader' not in frames:
        return pd.Series(False, index=df.index)

    house = df['house'].iloc[0]
    hdr = frames['apoheader']
    hdr = (
        hdr[hdr['house'] == house][['client', 'order_id', 'order_date']]
        .drop_duplicates(subset=['client', 'order_id'])
        .rename(columns={'order_date': 'hdr_order_date'})
    )
    merged = df[['client', 'order_id', 'order_date']].merge(hdr, on=['client', 'order_id'], how='left')
    both_present = merged['order_date'].notna() & merged['hdr_order_date'].notna()
    differs = merged['order_date'] != merged['hdr_order_date']
    return (both_present & differs).values


def get_po_checks():
    return [

        # ---------------------------------------------------------------
        # PO HEADER — apoheader
        # HoC only. Status codes confirmed July 2026: N/O/A active, F/C/T resolved.
        # Population for general completeness/validity checks excludes T
        # (Terminated = raised in error, per Parliament's own definition).
        # ---------------------------------------------------------------

        ('PO_DUP_HEADER',
         15, 'PO Header', 'Uniqueness', 'High',
         'Duplicate purchase order — same client and order number',
         'Every purchase order must be unique on (client, order_id), its primary key in Agresso. '
         'A duplicate key means two header rows are competing for the same logical PO, which the new system cannot load as-is. '
         'Duplicate keys must be resolved before the PO-level migration mapping can be trusted.',
         'Investigate the duplicate header rows in the legacy system and determine which, if any, is the genuine record.',
         'apoheader', None,
         "WHERE (client, order_id) HAVING COUNT(*) > 1",
         lambda df: df.duplicated(subset=['client', 'order_id'], keep=False)),

        ('PO_NO_SUPPLIER',
         15, 'PO Header', 'Completeness', 'High',
         'Purchase order has no supplier reference',
         'Every purchase order must reference a valid supplier via apar_id. '
         'The new system requires this reference to route the order and match it against invoices. '
         'A PO with no supplier reference cannot be migrated or matched to an incoming invoice.',
         'Add the correct supplier reference to the affected purchase order in the legacy system before migration.',
         'apoheader', None,
         "WHERE apar_id IS NULL OR TRIM(apar_id) = ''",
         lambda df: _is_blank(df['apar_id'])),

        ('PO_INVALID_ORDER_DATE',
         15, 'PO Header', 'Validity', 'Medium',
         'Purchase order has no order date',
         'Every purchase order must carry a valid order_date. '
         'Age profiling, aging analysis, and migration cutover reporting all depend on this field. '
         'A PO with no order date cannot be placed in the lifecycle analysis and will appear as an unexplained gap.',
         'Correct or backfill the order date for the affected purchase order in the legacy system.',
         'apoheader', None,
         "WHERE order_date IS NULL",
         lambda df: df['order_date'].isna()),

        ('PO_FUTURE_ORDER_DATE',
         15, 'PO Header', 'Validity', 'Medium',
         'Purchase order has a future order date',
         "A purchase order's order_date must not be later than today's date — a PO cannot be raised in the future. "
         'A future-dated order suggests a data entry error or a placeholder date that was never corrected.',
         'Correct the order date on the affected purchase order in the legacy system.',
         'apoheader', None,
         "WHERE order_date > CURRENT_DATE",
         lambda df: df['order_date'] > pd.Timestamp.today()),

        ('PO_BAD_EXCH_RATE',
         15, 'PO Header', 'Validity', 'Low',
         'Purchase order has an invalid exchange rate',
         'Every purchase order must carry a positive exch_rate. '
         'The order-currency amounts (cur_amount, vow_val, arr_val) are only meaningful when the rate used to derive them is valid. '
         'A zero or negative exchange rate produces a nonsensical currency conversion.',
         'Correct the exchange rate on the affected purchase order in the legacy system.',
         'apoheader', None,
         "WHERE exch_rate <= 0",
         lambda df: pd.to_numeric(df['exch_rate'], errors='coerce').fillna(0) <= 0),

        ('PO_STUCK_NOT_ORDERED',
         15, 'PO Header', 'Consistency', 'Medium',
         'PO has been sitting in Not Ordered status for more than a day',
         'A purchase order in Not Ordered (N) status is raised and approved but the PO document has not yet been created. '
         'Document creation is automated and should complete within 15 minutes. '
         'A PO stuck in N for more than a day indicates a stalled automation job, not a normal processing delay.',
         'Investigate the automated PO document creation job for the affected purchase order.',
         'apoheader', None,
         "WHERE status = 'N' AND order_date < CURRENT_DATE - 1",
         lambda df: (pd.Timestamp.today() - df['order_date']).dt.days > 1),

        ('PO_FINISHED_WITH_BALANCE',
         15, 'PO Header', 'Consistency', 'Medium',
         'Finished PO still has a material amount unaccounted for by invoicing',
         'A purchase order marked Finished (F) is set automatically only once the system determines it has been used completely. '
         'Its ordered value should therefore already be reflected in either arr_amount or invoiced, whichever field is populated for that line. '
         "A Finished PO with more than 5% of its value unaccounted for by both measures contradicts the system's own completion signal.",
         "Review the affected purchase order's invoicing history (both arr_amount and invoiced) and confirm whether it is genuinely complete.",
         'apoheader', 'apodetail',
         "WHERE status = 'F' AND (amount - GREATEST(COALESCE(arr_amount,0), COALESCE(invoiced,0))) / NULLIF(amount, 0) > 0.05",
         _po_finished_with_balance),

        # ---------------------------------------------------------------
        # PO HEADER — cross-domain (Suppliers)
        # ---------------------------------------------------------------

        ('PO_ORPHANED_SUPPLIER',
         15, 'PO Header', 'Consistency', 'High',
         'Purchase order references a supplier that does not exist',
         "Every purchase order's apar_id must match a real supplier record in the supplier master (asuheader). "
         'A PO referencing a supplier that cannot be found has no route to payment and no matching AP invoice path. '
         'This PO cannot be migrated correctly until its supplier reference is corrected.',
         'Correct the apar_id on the affected purchase order to reference a valid, existing supplier.',
         'apoheader', 'asuheader',
         "WHERE apar_id NOT IN (SELECT apar_id FROM asuheader WHERE client = apoheader.client)",
         _po_orphaned_supplier),

        ('PO_INACTIVE_SUPPLIER',
         15, 'PO Header', 'Consistency', 'Medium',
         'Active PO references a supplier that has been closed',
         'An active purchase order (O, N, or A status) should reference a supplier that is still active in the supplier master. '
         'A PO still open against a supplier marked Closed suggests either the PO or the supplier record needs review before cutover.',
         'Confirm whether the affected purchase order should still be open, or whether the supplier record needs reactivating.',
         'apoheader', 'asuheader',
         "WHERE apoheader.status IN ('O','N','A') AND asuheader.status = 'C'",
         _po_inactive_supplier),

        # ---------------------------------------------------------------
        # PO DETAIL — apodetail
        # HoC only. All statuses included.
        # ---------------------------------------------------------------

        ('PO_LINE_NEG_AMOUNT',
         15, 'PO Line', 'Validity', 'Medium',
         'PO line has a negative ordered amount',
         'Every PO line represents a positive ordered value. '
         'Unlike AP/AR invoices, there is no confirmed credit-note or reversal voucher type for PO lines. '
         'A negative amount on a PO line is therefore unexplained and should be checked before migration.',
         'Confirm whether the affected line is a genuine adjustment or a data entry error, and correct it in the legacy system.',
         'apodetail', None,
         "WHERE amount < 0",
         lambda df: pd.to_numeric(df['amount'], errors='coerce').fillna(0) < 0),

        ('PO_TERMINATED_WITH_INVOICING',
         15, 'PO Line', 'Consistency', 'Medium',
         'Terminated PO line still shows real invoicing activity',
         "A line under a Terminated (T) purchase order is expected to carry no material invoicing activity — "
         "Parliament's own guidance is that T is reserved for POs raised in error. "
         'A line with a genuinely non-zero arr_amount or invoiced value means real activity was processed against a PO that was later terminated, '
         'which is worth reviewing even though the termination itself may be legitimate.',
         'Confirm whether the invoicing activity on the affected line was reversed, reassigned, or should be investigated '
         'further before this PO is treated as a clean error.',
         'apodetail', None,
         "WHERE status = 'T' AND GREATEST(COALESCE(arr_amount,0), COALESCE(invoiced,0)) <> 0",
         lambda df: df[['arr_amount', 'invoiced']].max(axis=1).abs() > 0.01),

        ('PO_ARR_EXCEEDS_AMOUNT',
         15, 'PO Line', 'Validity', 'Medium',
         'PO line has been invoiced for more than its ordered value',
         "A PO line's invoiced value (whichever of arr_amount or invoiced is larger) should not exceed its ordered amount. "
         'A line invoiced beyond what was ordered suggests over-billing, a data entry error, or an amendment that was not correctly reflected.',
         'Investigate the affected PO line to confirm whether the over-invoicing is legitimate (e.g. a price adjustment) or an error.',
         'apodetail', None,
         "WHERE GREATEST(COALESCE(arr_amount,0), COALESCE(invoiced,0)) > amount",
         lambda df: (df[['arr_amount', 'invoiced']].max(axis=1) - df['amount']) > 0.01),

        ('PO_LINE_NO_CATEGORY',
         15, 'PO Line', 'Completeness', 'Low',
         'PO line has no spend category',
         'Every PO line should carry a spend category (art_gr_id) so spend can be classified and reported consistently. '
         'A line with no category cannot be included in category-level spend analysis after migration.',
         'Add the correct spend category to the affected PO line in the legacy system.',
         'apodetail', None,
         "WHERE art_gr_id IS NULL OR TRIM(art_gr_id) = ''",
         lambda df: _is_blank(df['art_gr_id'])),

        ('PO_LINE_NO_ACCOUNT',
         15, 'PO Line', 'Completeness', 'High',
         'PO line has no GL account code',
         'Every PO line must carry a GL account code. '
         'The new system uses this code to post the committed spend to the correct ledger account. '
         'A PO line with no account code cannot be coded correctly and will block a clean migration of that commitment.',
         'Add the correct GL account code to the affected PO line in the legacy system before migration.',
         'apodetail', None,
         "WHERE account IS NULL OR TRIM(account) = ''",
         lambda df: _is_blank(df['account'])),

        ('PO_DUP_LINE',
         15, 'PO Line', 'Uniqueness', 'High',
         'Duplicate PO line — same order, line, and sequence number',
         'Every PO line must be unique on (client, order_id, line_no, sequence_no), its primary key in Agresso. '
         'A duplicate key means two rows are competing for the same logical line, which the new system cannot load as-is. '
         'Duplicate keys must be resolved before the line-level migration mapping can be trusted.',
         'Investigate the duplicate rows in the legacy system and determine which, if any, is the genuine record.',
         'apodetail', None,
         "WHERE (client, order_id, line_no, sequence_no) HAVING COUNT(*) > 1",
         lambda df: df.duplicated(subset=['client', 'order_id', 'line_no', 'sequence_no'], keep=False)),

        ('PO_HDR_LINE_STATUS_MISMATCH',
         15, 'PO Line', 'Consistency', 'Low',
         'PO line status differs from its header status',
         "A PO line's own status is expected to track its purchase order header's overall status. "
         'The real-data meaning of a line diverging from its header has not yet been confirmed with Parliament. '
         'A high or growing mismatch rate is worth investigating even though it is not yet a confirmed data error.',
         'Confirm with Parliament whether PO line status is expected to diverge from header status, and under what circumstances.',
         'apodetail', 'apoheader',
         "WHERE apodetail.status <> apoheader.status",
         _po_line_status_mismatch),

        ('PO_HDR_LINE_DATE_MISMATCH',
         15, 'PO Line', 'Consistency', 'Low',
         'PO line order date differs from its header order date',
         "A PO line's own order_date is extracted independently of its header's order_date. "
         'The real-data meaning of a line diverging from its header has not yet been confirmed with Parliament, '
         'same open question as the equivalent status check. A high or growing mismatch rate is worth investigating.',
         'Confirm with Parliament whether PO line order_date is expected to diverge from header order_date, and under what circumstances.',
         'apodetail', 'apoheader',
         "WHERE apodetail.order_date <> apoheader.order_date",
         _po_hdr_line_date_mismatch),

        # ---------------------------------------------------------------
        # PO DETAIL — cross-domain (GL)
        # ---------------------------------------------------------------

        ('PO_LINE_ORPHAN_ACCOUNT',
         15, 'PO Line', 'Consistency', 'High',
         'PO line references a GL account that does not exist',
         "Every PO line's account must match a real account code in the chart of accounts (aglaccounts). "
         'A line referencing an account that cannot be found cannot be posted or migrated correctly.',
         'Correct the account code on the affected PO line, or add the missing account to the chart of accounts if it should exist.',
         'apodetail', 'aglaccounts',
         "WHERE account NOT IN (SELECT account FROM aglaccounts WHERE house = apodetail.house)",
         _po_line_orphan_account),

        ('PO_LINE_CLOSED_ACCOUNT',
         15, 'PO Line', 'Consistency', 'Medium',
         'PO line posts to a GL account that has been closed',
         "A PO line's account should still be active (status = N) in the chart of accounts. "
         'A line coded to an account that has since been closed cannot be posted against that account going forward '
         'and needs review before the commitment is migrated.',
         'Recode the affected PO line to an active account, or confirm the account closure was made in error.',
         'apodetail', 'aglaccounts',
         "WHERE account IN (SELECT account FROM aglaccounts WHERE status != 'N')",
         _po_line_closed_account),

        # ---------------------------------------------------------------
        # PO DETAIL — added from direct Excel exploration of real PO lines
        # (July 2026). Population overrides for these five live in
        # data_engine.py's run_dq_analysis()/get_failing_records() apodetail
        # branch, same dual-location pattern as every other PO population
        # override.
        # ---------------------------------------------------------------

        ('PO_LINE_NEVER_MATCHED',
         15, 'PO Line', 'Consistency', 'High',
         'Finished line shows real activity but was never matched',
         'A PO line marked Finished should have gone through invoice matching by the time it reaches that status. '
         'A Finished line with a received or invoiced value but a completely zero arr_amount and arr_val means the matching step '
         'itself never ran against this line, even though other fields show it was actioned. '
         'This is a distinct root cause from a partially-reconciled Finished PO — the matching process was bypassed entirely, not just incomplete.',
         'Investigate why matching never ran against the affected line, and whether it was closed manually without going through the normal process.',
         'apodetail', None,
         "WHERE status = 'F' AND (vow_amount <> 0 OR invoiced <> 0) AND arr_amount = 0 AND arr_val = 0",
         _po_line_never_matched),

        ('PO_LINE_MATCH_EXCEEDS_RECEIPT',
         15, 'PO Line', 'Validity', 'Medium',
         'PO line has been matched for more than was received',
         'A PO line’s matched value (arr_val) should never exceed its received value (vow_val) — a line cannot be matched '
         'against goods or services that were never receipted. '
         'A line where arr_val exceeds vow_val suggests either the receipt was under-recorded or the matching module has attributed value to the wrong line.',
         'Review the affected PO line’s receipt and matching history to confirm which figure is wrong.',
         'apodetail', None,
         "WHERE arr_val > vow_val",
         lambda df: (pd.to_numeric(df['arr_val'], errors='coerce').fillna(0)
                     - pd.to_numeric(df['vow_val'], errors='coerce').fillna(0)) > 0.01),

        ('PO_LINE_INVOICED_AHEAD_OF_RECEIPT',
         15, 'PO Line', 'Consistency', 'Low',
         'PO line has been invoiced for more than was received',
         'A PO line is expected to be invoiced no more than it has been received (vow_amount), since invoicing normally follows receipt. '
         'A line invoiced ahead of its recorded receipt may simply reflect a timing difference between the invoice and goods-receipt processes rather than an error, '
         'so this is worth reviewing rather than treated as a confirmed defect until Parliament confirms the expected sequencing.',
         'Confirm with Parliament whether invoicing ahead of receipt is an expected in-flight state for this PO process, or a control gap.',
         'apodetail', None,
         "WHERE status <> 'T' AND invoiced > vow_amount",
         lambda df: (pd.to_numeric(df['invoiced'], errors='coerce').fillna(0)
                     - pd.to_numeric(df['vow_amount'], errors='coerce').fillna(0)) > 0.01),

        ('PO_LINE_AMENDED_VALUE_MISMATCH',
         15, 'PO Line', 'Validity', 'Low',
         'Amended PO line has no actual change in committed value',
         'An amended PO line (amend_no > 0) is expected to carry a different amount from its pre-amendment committed value (com_amount) — '
         'that divergence is the point of an amendment. '
         'Checking amend_no > 0 AND amount <> com_amount was tried first and always fires, since a genuine amendment is defined by changing the value — '
         'on 340 real amended dummy lines the minimum divergence was £4.07 and none were zero, confirming this. '
         'The actual anomaly is the opposite: an amendment number was incremented but the committed value never moved at all — a no-op amendment.',
         'Confirm with the legacy system owner whether the affected amendment was applied correctly, or whether amend_no was incremented without an intended value change.',
         'apodetail', None,
         "WHERE amend_no > 0 AND ABS(amount - com_amount) <= 0.01",
         lambda df: (pd.to_numeric(df['amount'], errors='coerce')
                     - pd.to_numeric(df['com_amount'], errors='coerce')).abs() <= 0.01),

        ('PO_LINE_STALE_UNRESOLVED',
         15, 'PO Line', 'Consistency', 'Medium',
         'Line delivered over 30 days ago but still open',
         'A PO line that has been delivered is expected to progress to invoicing and closure within a reasonable time. '
         'A line still open (not Terminated, Closed, or Finished) more than 30 days after its delivery date has stalled somewhere between receipt and closure. '
         'Population excludes Terminated, Closed, and Finished lines, so this only counts lines genuinely still in progress.',
         'Investigate why the affected line has not progressed to invoicing or closure since delivery.',
         'apodetail', None,
         "WHERE status NOT IN ('T','C','F') AND deliv_date < CURRENT_DATE - 30",
         _po_line_stale_unresolved),
    ]
