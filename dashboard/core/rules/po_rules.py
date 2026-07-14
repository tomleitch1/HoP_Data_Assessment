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


def get_po_checks():
    return [

        # ---------------------------------------------------------------
        # PO HEADER — apoheader
        # HoC only. Status codes confirmed July 2026: N/O/A active, F/C/T resolved.
        # Population for general completeness/validity checks excludes T
        # (Terminated = raised in error, per Parliament's own definition).
        # ---------------------------------------------------------------

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
    ]
