# ═══════════════════════════════════════════════════════════════════════════════
# volumetrics.py  —  Pure computation of dataset statistics for the
#                    Volumetrics sections on the Overview and module tab pages.
#
#  Called by:
#    tabs/overview.py   → get_overview_volumetrics(frames)
#    tabs/module_tab.py → get_tab_volumetrics(frames, scope_key)
#
#  No Dash imports. No side effects. Returns plain dicts and DataFrames.
#
#  ADDING A NEW DATASET:
#    Add a branch to get_tab_volumetrics() following the AP/AR pattern.
#    All constants (status codes etc.) come from dashboard.core.config.
# ═══════════════════════════════════════════════════════════════════════════════

import pandas as pd
from dashboard.core.config import (
    CLIENTS,
    SupplierConfig,
    CustomerConfig,
    APConfig,
    ARConfig,
)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _safe_max_date(df: pd.DataFrame, col: str) -> str | None:
    """Return the latest date in a column as a formatted string, or None."""
    if df is None or col not in df.columns:
        return None
    parsed = pd.to_datetime(df[col], errors='coerce')
    if parsed.isna().all():
        return None
    return parsed.max().strftime('%d %b %Y').lstrip('0')


def _filter_house(df: pd.DataFrame, house: str) -> pd.DataFrame:
    """Filter a DataFrame to a single house using the 'house' column."""
    if df is None or df.empty or 'house' not in df.columns:
        return pd.DataFrame()
    return df[df['house'] == house]


def _count_by_status(df: pd.DataFrame, house: str, col: str = 'status') -> dict:
    """Return {status_value: count} for a given house."""
    if df is None or col not in df.columns:
        return {}
    sub = _filter_house(df, house)
    return sub[col].value_counts().to_dict()


def _sum_column(df: pd.DataFrame, house: str, col: str) -> float:
    """Return the sum of a numeric column for a given house, safely."""
    if df is None or col not in df.columns:
        return 0.0
    sub = _filter_house(df, house)
    return pd.to_numeric(sub[col], errors='coerce').sum()


def _record_count(df: pd.DataFrame, house: str) -> int:
    if df is None:
        return 0
    return int(len(_filter_house(df, house)))


# ── Overview volumetrics ──────────────────────────────────────────────────────

def get_overview_volumetrics(frames: dict) -> dict:
    """
    Return a flat dict of KPI stats for the Overview page Data Snapshot strip.

    Structure:
    {
        'HOC': {
            'suppliers_active':   int,
            'suppliers_inactive': int,
            'suppliers_total':    int,
            'customers_active':   int,
            'customers_inactive': int,
            'customers_total':    int,
            'ap_invoices_open':   int,
            'ap_balance':         float,
            'ar_invoices_open':   int,
            'ar_balance':         float,
            'supplier_extract_date': str | None,
            'ap_extract_date':       str | None,
        },
        'HOL': { ... }
    }
    """
    sup  = frames.get('asuheader')
    cus  = frames.get('acuheader')
    ap   = frames.get('asutrans')
    ar   = frames.get('acutrans')

    result = {}
    for house in CLIENTS:
        # ── Supplier master ───────────────────────────────────────────────────
        sup_all      = _filter_house(sup, house)
        sup_active   = int(sup_all['status'].isin(SupplierConfig.ACTIVE_STATUSES).sum())   if not sup_all.empty else 0
        sup_inactive = int(sup_all['status'].isin(SupplierConfig.INACTIVE_STATUSES).sum()) if not sup_all.empty else 0
        sup_total    = len(sup_all)

        # ── Customer master ───────────────────────────────────────────────────
        cus_all      = _filter_house(cus, house)
        cus_active   = int(cus_all['status'].isin(CustomerConfig.ACTIVE_STATUSES).sum())   if not cus_all.empty else 0
        cus_inactive = int(cus_all['status'].isin(CustomerConfig.INACTIVE_STATUSES).sum()) if not cus_all.empty else 0
        cus_total    = len(cus_all)

        # ── AP transactions ───────────────────────────────────────────────────
        ap_h         = _filter_house(ap, house)
        ap_open_mask = ap_h['status'].isin(APConfig.OPEN_TRANSACTION_STATUSES) if not ap_h.empty else pd.Series(dtype=bool)
        ap_open      = int(ap_open_mask.sum()) if not ap_h.empty else 0
        ap_balance   = float(
            pd.to_numeric(
                ap_h.loc[ap_open_mask, 'rest_amount'],
                errors='coerce'
            ).sum()
        ) if not ap_h.empty and 'rest_amount' in ap_h.columns else 0.0
        if not ap_h.empty and 'due_date' in ap_h.columns:
            ap_due     = pd.to_datetime(ap_h.loc[ap_open_mask, 'due_date'], errors='coerce')
            ap_overdue = int((ap_due < pd.Timestamp.now().normalize()).sum())
        else:
            ap_overdue = 0

        # ── AR transactions ───────────────────────────────────────────────────
        ar_h         = _filter_house(ar, house)
        ar_open_mask = ar_h['status'].isin(ARConfig.OPEN_TRANSACTION_STATUSES) if not ar_h.empty else pd.Series(dtype=bool)
        ar_open      = int(ar_open_mask.sum()) if not ar_h.empty else 0
        ar_balance   = float(
            pd.to_numeric(
                ar_h.loc[ar_open_mask, 'rest_amount'],
                errors='coerce'
            ).sum()
        ) if not ar_h.empty and 'rest_amount' in ar_h.columns else 0.0
        if not ar_h.empty and 'due_date' in ar_h.columns:
            ar_due     = pd.to_datetime(ar_h.loc[ar_open_mask, 'due_date'], errors='coerce')
            ar_overdue = int((ar_due < pd.Timestamp.now().normalize()).sum())
        else:
            ar_overdue = 0

        # ── Extract dates (latest last_update / trans_date as proxy) ──────────
        sup_date = _safe_max_date(sup_all, 'last_update')  if not sup_all.empty else None
        ap_date  = _safe_max_date(ap_h,    'trans_date')   if not ap_h.empty  else None
        ar_date  = _safe_max_date(ar_h,    'trans_date')   if not ar_h.empty  else None
        cus_date = _safe_max_date(cus_all, 'last_update')  if not cus_all.empty else None

        result[house] = {
            'suppliers_active':      sup_active,
            'suppliers_inactive':    sup_inactive,
            'suppliers_total':       sup_total,
            'customers_active':      cus_active,
            'customers_inactive':    cus_inactive,
            'customers_total':       cus_total,
            'ap_invoices_open':      ap_open,
            'ap_balance':            ap_balance,
            'ap_overdue':            ap_overdue,
            'ar_invoices_open':      ar_open,
            'ar_balance':            ar_balance,
            'ar_overdue':            ar_overdue,
            'supplier_extract_date': sup_date,
            'customer_extract_date': cus_date,
            'ap_extract_date':       ap_date,
            'ar_extract_date':       ar_date,
        }

    return result


# ── Tab-level volumetrics ─────────────────────────────────────────────────────

def get_tab_volumetrics(frames: dict, scope_key: str) -> dict:
    """
    Return per-house chart data for the detailed volumetrics card on a module tab.

    scope_key: 'ap' | 'ar'

    Returns:
    {
        'scope_key':     str,
        'master_label':  str,           e.g. 'Suppliers'
        'trans_label':   str,           e.g. 'AP Invoices'
        'houses':        list[str],
        'master': {
            house: {
                'status_counts':  dict,    {status: count}  — full population
                'active':         int,
                'inactive':       int,
                'other':          int,     parked / other statuses
                'total':          int,
                'extract_date':   str | None,
            }
        },
        'transactions': {
            house: {
                'status_counts':     dict,    {status: count} — all statuses in extract
                'status_value_split': dict,   {status: {count, balance}} — open items only;
                                              replaces the duplicate Info check in ar_invoices.py
                'pay_flag_split':    dict,    {pay_flag: {count, balance}} — open items only;
                                              AR-specific (Seq 17 / Seq 18 split); empty for AP
                'open':              int,     rows matching open-status list
                'total':             int,     all rows in extract
                'outstanding_bal':   float,   sum of rest_amount for open items
                'overdue_count':     int,     due_date < today
                'avg_days_old':      float,   mean (today - trans_date) for open items
                'extract_date':      str | None,
            }
        },
        'history': {                         # AP only — asuhistr if present
            house: {
                'total':          int,
                'extract_date':   str | None,
            }
        } | None,
    }
    """
    today = pd.Timestamp.now().normalize()

    if scope_key == 'ap':
        master_key    = 'asuheader'
        trans_key     = 'asutrans'
        hist_key      = 'asuhistr'
        master_label  = 'Suppliers'
        trans_label   = 'AP Invoices'
        active_stats  = SupplierConfig.ACTIVE_STATUSES
        inactive_stats= SupplierConfig.INACTIVE_STATUSES
        open_stats    = APConfig.OPEN_TRANSACTION_STATUSES
    elif scope_key == 'ar':
        master_key    = 'acuheader'
        trans_key     = 'acutrans'
        hist_key      = None
        master_label  = 'Customers'
        trans_label   = 'AR Invoices'
        active_stats  = CustomerConfig.ACTIVE_STATUSES
        inactive_stats= CustomerConfig.INACTIVE_STATUSES
        open_stats    = ARConfig.OPEN_TRANSACTION_STATUSES
    else:
        return {}

    master_df = frames.get(master_key)
    trans_df  = frames.get(trans_key)
    hist_df   = frames.get(hist_key) if hist_key else None

    master_out = {}
    trans_out  = {}
    hist_out   = {}

    for house in CLIENTS:
        # ── Master data ───────────────────────────────────────────────────────
        m = _filter_house(master_df, house).copy()

        if not m.empty and 'status' in m.columns:
            sc         = m['status'].value_counts().to_dict()
            active     = int(m['status'].isin(active_stats).sum())
            inactive   = int(m['status'].isin(inactive_stats).sum())
            parked     = int((m['status'] == 'P').sum())
            terminated = int((m['status'] == 'T').sum())
            other      = len(m) - active - inactive
        else:
            sc, active, inactive, parked, terminated, other = {}, 0, 0, 0, 0, 0

        master_out[house] = {
            'status_counts': sc,
            'active':        active,
            'inactive':      inactive,
            'parked':        parked,
            'terminated':    terminated,
            'other':         max(other, 0),
            'total':         len(m),
            'extract_date':  _safe_max_date(m, 'last_update'),
        }

        # ── Transactions ──────────────────────────────────────────────────────
        t = _filter_house(trans_df, house).copy()

        if scope_key == 'gl':
            # Opening Balances (aglyearend) have no status, due_date, or rest_amount.
            # Compute GL-appropriate stats: total rows, debit total, credit total.
            if not t.empty:
                debit_total  = float(pd.to_numeric(
                    t.loc[t['dc_flag'] == GLConfig.DC_DEBIT,  'amount'], errors='coerce'
                ).sum()) if 'dc_flag' in t.columns and 'amount' in t.columns else 0.0
                credit_total = float(pd.to_numeric(
                    t.loc[t['dc_flag'] == GLConfig.DC_CREDIT, 'amount'], errors='coerce'
                ).sum()) if 'dc_flag' in t.columns and 'amount' in t.columns else 0.0
                # Build a synthetic status_counts using dc_flag so the stacked bar renders
                dc_counts = t['dc_flag'].value_counts().to_dict() if 'dc_flag' in t.columns else {}
                t_sc = {
                    str(k): int(v) for k, v in dc_counts.items()
                }
            else:
                debit_total = credit_total = 0.0
                t_sc = {}

            trans_out[house] = {
                'status_counts':   t_sc,
                'open':            len(t),      # "open" = total rows for GL
                'total':           len(t),
                'outstanding_bal': 0.0,
                'overdue_count':   0,
                'avg_days_old':    0.0,
                'extract_date':    None,
                # GL-specific
                'debit_total':     debit_total,
                'credit_total':    abs(credit_total),
            }

        else:
            if not t.empty:
                # Status breakdown across ALL rows in extract (not filtered to open)
                t_sc    = t['status'].value_counts().to_dict() if 'status' in t.columns else {}
                t_open  = t[t['status'].isin(open_stats)] if 'status' in t.columns else t

                # Outstanding balance
                bal = float(
                    pd.to_numeric(t_open.get('rest_amount', pd.Series(dtype=float)), errors='coerce').sum()
                ) if 'rest_amount' in t_open.columns else 0.0

                # Overdue count
                if 'due_date' in t_open.columns:
                    due = pd.to_datetime(t_open['due_date'], errors='coerce')
                    overdue = int((due < today).sum())
                else:
                    overdue = 0

                # Average age (days since trans_date)
                if 'trans_date' in t_open.columns:
                    td    = pd.to_datetime(t_open['trans_date'], errors='coerce')
                    ages  = (today - td).dt.days.dropna()
                    avg_age = float(ages.mean()) if len(ages) else 0.0
                else:
                    avg_age = 0.0

                t_date = _safe_max_date(t, 'trans_date')

                # ── Status value split ────────────────────────────────────────
                # Count AND outstanding balance (rest_amount) per status for open
                # items. volumetrics previously had count-only (status_counts).
                # This is consumed by the AR tab status breakdown chart and removes
                # the need to emit a duplicate Info check from ar_invoices.py.
                if 'status' in t_open.columns and 'rest_amount' in t_open.columns:
                    _rest = pd.to_numeric(t_open['rest_amount'], errors='coerce')
                    status_value_split = {
                        str(s): {
                            'count': int((t_open['status'] == s).sum()),
                            'balance': float(_rest[t_open['status'] == s].sum()),
                        }
                        for s in t_open['status'].dropna().unique()
                    }
                else:
                    status_value_split = {}

                # ── Pay-flag split (AR only — Seq 17 vs Seq 18) ──────────────
                # Count AND outstanding balance per pay_flag for open items.
                # Not present anywhere else in volumetrics; used by the AR tab.
                if 'pay_flag' in t_open.columns and 'rest_amount' in t_open.columns:
                    _rest = pd.to_numeric(t_open['rest_amount'], errors='coerce')
                    pay_flag_split = {
                        str(pf): {
                            'count': int((t_open['pay_flag'] == pf).sum()),
                            'balance': float(_rest[t_open['pay_flag'] == pf].sum()),
                        }
                        for pf in sorted(t_open['pay_flag'].dropna().unique())
                    }
                else:
                    pay_flag_split = {}

            else:
                (t_sc, t_open, bal, overdue, avg_age,
                 t_date, status_value_split, pay_flag_split) = (
                    {}, pd.DataFrame(), 0.0, 0, 0.0, None, {}, {}
                )

            trans_out[house] = {
                'status_counts':      t_sc,
                'status_value_split': status_value_split,  # {status: {count, balance}}
                'pay_flag_split':     pay_flag_split,       # {pay_flag: {count, balance}}
                'open':               len(t_open),
                'total':              len(t),
                'outstanding_bal':    bal,
                'overdue_count':      overdue,
                'avg_days_old':       avg_age,
                'extract_date':       t_date,
            }

        # ── Historical transactions (AP only) ─────────────────────────────────
        if hist_df is not None:
            h_house = _filter_house(hist_df, house)
            hist_out[house] = {
                'total':        len(h_house),
                'extract_date': _safe_max_date(h_house, 'trans_date'),
            }

        # ── GL Dimension Values (GL tab only) ─────────────────────────────────
        if scope_key == 'gl':
            dim_df   = frames.get('agldimvalue')
            dim_h    = _filter_house(dim_df, house).copy()
            dim_sc   = dim_h['status'].value_counts().to_dict() if not dim_h.empty and 'status' in dim_h.columns else {}
            dim_act  = int((dim_h['status'] == 'N').sum()) if not dim_h.empty and 'status' in dim_h.columns else 0
            dim_inact= int((dim_h['status'] != 'N').sum()) if not dim_h.empty and 'status' in dim_h.columns else 0
            dim_date = _safe_max_date(dim_h, 'last_update')
            by_type  = dim_h[dim_h['status'] == 'N']['attribute_id'].value_counts().to_dict() if not dim_h.empty and 'attribute_id' in dim_h.columns else {}
            if 'dim_values' not in dir():
                dim_values_out = {}
            dim_values_out[house] = {
                'status_counts': dim_sc,
                'active':        dim_act,
                'inactive':      dim_inact,
                'total':         len(dim_h),
                'by_type':       by_type,
                'extract_date':  dim_date,
            }

    # Initialise dim_values_out for non-GL scopes
    if scope_key != 'gl':
        dim_values_out = None
    elif 'dim_values_out' not in dir():
        dim_values_out = None

    return {
        'scope_key':    scope_key,
        'master_label': master_label,
        'trans_label':  trans_label,
        'houses':       CLIENTS,
        'master':       master_out,
        'transactions': trans_out,
        'history':      hist_out if hist_df is not None else None,
        'dim_values':   dim_values_out,
    }


def get_ap_volumetrics(df_dict: dict) -> dict:
    """
    Returns calculated AP volumetrics for both Houses.
    Calculates Active ('N'), Inactive ('C'), and Total counts for Suppliers.
    Calculates Open Count, Balance, Overdue Count, and Avg Days Old for Transactions.
    """
    today = pd.Timestamp.now().normalize()
    open_statuses = ['N', 'R', 'I', 'P']
    
    header = df_dict.get('asuheader', pd.DataFrame())
    trans  = df_dict.get('asutrans', pd.DataFrame())
    hist   = df_dict.get('asuhistr', pd.DataFrame())
    
    results = {}
    
    for house in CLIENTS:
        # 1. Supplier master
        h_header = _filter_house(header, house)
        total_m  = len(h_header)
        m_date   = _safe_max_date(h_header, 'last_update')
        m_status_breakdown = h_header['status'].value_counts().to_dict() if not h_header.empty and 'status' in h_header.columns else {}

        # Active = any status that is not Closed (N, P, T all count)
        active   = int((h_header['status'] != 'C').sum()) if not h_header.empty and 'status' in h_header.columns else 0
        inactive = int((h_header['status'] == 'C').sum()) if not h_header.empty and 'status' in h_header.columns else 0

        # 2. History — identifies which closed suppliers had recent activity
        h_hist = _filter_house(hist, house)
        hist_total = len(h_hist)
        hist_ids   = set(h_hist['apar_id'].dropna().astype(str).unique()) if not h_hist.empty and 'apar_id' in h_hist.columns else set()

        # Closed suppliers who appear in 18-month history = in migration scope
        if not h_header.empty and 'status' in h_header.columns and 'apar_id' in h_header.columns:
            closed = h_header[h_header['status'] == 'C']['apar_id'].astype(str)
            inactive_recent  = int(closed.isin(hist_ids).sum())
            archive          = int((~closed.isin(hist_ids)).sum())
        else:
            inactive_recent = 0
            archive         = inactive

        migration_scope = active + inactive_recent

        # 3. Open transactions
        # Deduplicate by voucher_no before counting/summing — rest_amount is a
        # header-level field repeated on every line of a multi-line invoice.
        # Summing all rows would multiply the balance by the number of lines.
        h_trans      = _filter_house(trans, house)
        t_open = h_trans[h_trans['status'].isin(open_statuses)] if not h_trans.empty and 'status' in h_trans.columns else pd.DataFrame()

        open_count   = len(t_open)
        t_all_counts = t_open['status'].value_counts().to_dict() if not t_open.empty and 'status' in t_open.columns else {}

        balance = float(pd.to_numeric(t_open['rest_amount'], errors='coerce').sum()) if not t_open.empty and 'rest_amount' in t_open.columns else 0.0

        if not t_open.empty and 'due_date' in t_open.columns:
            due     = pd.to_datetime(t_open['due_date'], errors='coerce')
            overdue = int((due < today).sum())
        else:
            overdue = 0

        if not t_open.empty and 'trans_date' in t_open.columns:
            td      = pd.to_datetime(t_open['trans_date'], errors='coerce')
            ages    = (today - td).dt.days.dropna()
            avg_age = float(ages.mean()) if len(ages) else 0.0
        else:
            avg_age = 0.0

        t_date = _safe_max_date(h_trans, 'trans_date')

        # Balance broken down by status
        balance_by_status = {}
        if not t_open.empty and 'status' in t_open.columns and 'rest_amount' in t_open.columns:
            for s in ['N', 'R', 'I', 'P']:
                s_rows = t_open[t_open['status'] == s]
                balance_by_status[s] = float(
                    pd.to_numeric(s_rows['rest_amount'], errors='coerce').sum()
                ) if not s_rows.empty else 0.0

        results[house] = {
            'house': house,
            'master': {
                'total':            total_m,
                'active':           active,
                'inactive':         inactive,
                'inactive_recent':  inactive_recent,
                'archive':          archive,
                'migration_scope':  migration_scope,
                'status_breakdown': m_status_breakdown,
                'extract_date':     m_date,
            },
            'transactions': {
                'open_count':       open_count,
                'balance':          balance,
                'balance_by_status': balance_by_status,
                'overdue_count':    overdue,
                'avg_days_old':     avg_age,
                'status_breakdown': t_all_counts,
                'extract_date':     t_date,
            },
            'history': {
                'total': hist_total,
            },
        }
        
    return results

def get_ar_volumetrics(df_dict: dict) -> dict:
    """
    Returns calculated AR volumetrics for both Houses.
    Mirrors get_ap_volumetrics() structure so the customers tab can use the same
    intro layout as the suppliers tab.
    """
    today = pd.Timestamp.now().normalize()
    open_statuses = ['N', 'R', 'I', 'P']

    header = df_dict.get('acuheader', pd.DataFrame())
    trans  = df_dict.get('acutrans',  pd.DataFrame())
    hist   = df_dict.get('acuhistr',  pd.DataFrame())

    results = {}

    for house in CLIENTS:
        # ── Customer master ───────────────────────────────────────────────────
        h_header = _filter_house(header, house)
        total_m  = len(h_header)
        m_date   = _safe_max_date(h_header, 'last_update')
        m_status_breakdown = h_header['status'].value_counts().to_dict() if not h_header.empty and 'status' in h_header.columns else {}

        # Active = any status that is not Closed (N, P, T all count — mirrors supplier logic)
        active   = int((h_header['status'] != 'C').sum()) if not h_header.empty and 'status' in h_header.columns else 0
        inactive = int((h_header['status'] == 'C').sum()) if not h_header.empty and 'status' in h_header.columns else 0

        # ── History — identifies which closed customers had recent activity ───
        h_hist     = _filter_house(hist, house)
        hist_total = len(h_hist)
        hist_ids   = set(h_hist['apar_id'].dropna().astype(str).unique()) if not h_hist.empty and 'apar_id' in h_hist.columns else set()

        if not h_header.empty and 'status' in h_header.columns and 'apar_id' in h_header.columns:
            closed          = h_header[h_header['status'] == 'C']['apar_id'].astype(str)
            inactive_recent = int(closed.isin(hist_ids).sum())
            archive         = int((~closed.isin(hist_ids)).sum())
        else:
            inactive_recent = 0
            archive         = inactive

        migration_scope = active + inactive_recent

        # ── Open transactions ─────────────────────────────────────────────────
        h_trans = _filter_house(trans, house)
        t_open  = h_trans[h_trans['status'].isin(open_statuses)] if not h_trans.empty and 'status' in h_trans.columns else pd.DataFrame()

        open_count    = len(t_open)
        t_all_counts  = t_open['status'].value_counts().to_dict() if not t_open.empty and 'status' in t_open.columns else {}

        balance = float(pd.to_numeric(t_open['rest_amount'], errors='coerce').sum()) if not t_open.empty and 'rest_amount' in t_open.columns else 0.0

        if not t_open.empty and 'due_date' in t_open.columns:
            due     = pd.to_datetime(t_open['due_date'], errors='coerce')
            overdue = int((due < today).sum())
        else:
            overdue = 0

        if not t_open.empty and 'trans_date' in t_open.columns:
            td      = pd.to_datetime(t_open['trans_date'], errors='coerce')
            ages    = (today - td).dt.days.dropna()
            avg_age = float(ages.mean()) if len(ages) else 0.0
        else:
            avg_age = 0.0

        t_date = _safe_max_date(h_trans, 'trans_date')

        # Balance broken down by status (mirrors AP pattern)
        balance_by_status = {}
        if not t_open.empty and 'status' in t_open.columns and 'rest_amount' in t_open.columns:
            for s in ['N', 'R', 'I', 'P']:
                s_rows = t_open[t_open['status'] == s]
                balance_by_status[s] = float(
                    pd.to_numeric(s_rows['rest_amount'], errors='coerce').sum()
                ) if not s_rows.empty else 0.0

        results[house] = {
            'house': house,
            'master': {
                'total':            total_m,
                'active':           active,
                'inactive':         inactive,
                'inactive_recent':  inactive_recent,
                'archive':          archive,
                'migration_scope':  migration_scope,
                'status_breakdown': m_status_breakdown,
                'extract_date':     m_date,
            },
            'transactions': {
                'open_count':        open_count,
                'balance':           balance,
                'balance_by_status': balance_by_status,
                'overdue_count':     overdue,
                'avg_days_old':      avg_age,
                'status_breakdown':  t_all_counts,
                'extract_date':      t_date,
            },
            'history': {
                'total': hist_total,
            },
        }

    return results



# ── ADDITION TO volumetrics.py for assets ────────────────────────────────────────────────


def get_asset_volumetrics(df_dict: dict) -> dict:
    """
    Returns calculated Asset Register volumetrics for both Houses.
    Calculates Active/Inactive/Total counts, asset group breakdown,
    grant-funded count, stale count, and WIP (no cap date) count.
    """
    import pandas as pd
    from datetime import date, timedelta
    CLIENTS = ['HOC', 'HOL']
    STALE_CUTOFF = pd.Timestamp(date.today() - timedelta(days=3 * 365))

    assets = df_dict.get('asset_register', pd.DataFrame())

    def _safe_max_date(df, col):
        if df.empty or col not in df.columns:
            return None
        valid = pd.to_datetime(df[col], errors='coerce').dropna()
        return valid.max().strftime('%d %b %Y').lstrip('0') if not valid.empty else None

    results = {}
    for house in CLIENTS:
        h = _filter_house(assets, house)

        total    = len(h)
        active   = int((h['status'] == 'N').sum())   if not h.empty and 'status' in h.columns else 0
        inactive = int((h['status'] != 'N').sum())   if not h.empty and 'status' in h.columns else 0

        group_breakdown = h['asset_group'].value_counts().to_dict() \
            if not h.empty and 'asset_group' in h.columns else {}

        h_active = h[h['status'] == 'N'] if not h.empty and 'status' in h.columns else pd.DataFrame()

        grant_count = int((h_active['grant_flag'] == 1).sum()) \
            if not h_active.empty and 'grant_flag' in h_active.columns else 0

        stale_count = int(
            (pd.to_datetime(h_active['last_update'], errors='coerce') < STALE_CUTOFF).sum()
        ) if not h_active.empty and 'last_update' in h_active.columns else 0

        wip_count = int(h_active['cap_date_from'].isna().sum()) \
            if not h_active.empty and 'cap_date_from' in h_active.columns else 0

        extract_date = _safe_max_date(h, 'last_update')

        results[house] = {
            'house': house,
            'register': {
                'total':           total,
                'active':          active,
                'inactive':        inactive,
                'group_breakdown': group_breakdown,
                'grant_count':     grant_count,
                'stale_count':     stale_count,
                'wip_count':       wip_count,
                'extract_date':    extract_date,
            }
        }
    return results


def get_gl_volumetrics(frames: dict) -> dict:
    """
    GL tab volumetrics — per-house stats for all loaded GL datasets.
    Returns stats for aglaccounts, aglyearend (aglperiodic), agldimvalue, gl_dimconfig.
    """
    _GL_POS = {'0', '1', '2', '3', '4', '5', '6', '7'}

    accounts  = frames.get('aglaccounts',  pd.DataFrame())
    balances  = frames.get('aglyearend',   pd.DataFrame())
    dimvalue  = frames.get('agldimvalue',  pd.DataFrame())
    dimconfig = frames.get('gl_dimconfig', pd.DataFrame())
    journals  = frames.get('gl_journals',  pd.DataFrame())

    result = {}

    for house in CLIENTS:
        h_acc = _filter_house(accounts, house)
        h_bal = _filter_house(balances, house)
        h_dv  = _filter_house(dimvalue, house)

        # ── aglaccounts ───────────────────────────────────────────────────────
        acc_total  = len(h_acc)
        acc_active = int((h_acc['status'] == 'N').sum()) if not h_acc.empty and 'status' in h_acc.columns else 0
        acc_closed = int((h_acc['status'] == 'C').sum()) if not h_acc.empty and 'status' in h_acc.columns else 0

        acc_type_bd = {}
        acc_res_bd  = {}
        if not h_acc.empty:
            active_h = h_acc[h_acc['status'] == 'N'] if 'status' in h_acc.columns else h_acc
            if 'account_type' in h_acc.columns:
                acc_type_bd = active_h['account_type'].value_counts().to_dict()
            if 'res_bal' in h_acc.columns:
                acc_res_bd = active_h['res_bal'].value_counts().to_dict()

        # ── aglyearend (aglperiodic) ──────────────────────────────────────────
        bal_total = len(h_bal)
        bal_net   = 0.0
        bal_pmin  = None
        bal_pmax  = None
        bal_accs  = 0
        if not h_bal.empty:
            if 'amount' in h_bal.columns:
                bal_net = float(pd.to_numeric(h_bal['amount'], errors='coerce').sum())
            if 'period' in h_bal.columns:
                pp = pd.to_numeric(h_bal['period'], errors='coerce').dropna()
                if len(pp):
                    bal_pmin = int(pp.min())
                    bal_pmax = int(pp.max())
            if 'account' in h_bal.columns:
                bal_accs = int(h_bal['account'].nunique())

        # ── agldimvalue ───────────────────────────────────────────────────────
        dv_total = len(h_dv)
        dv_attrs = int(h_dv['attribute_id'].nunique()) if not h_dv.empty and 'attribute_id' in h_dv.columns else 0

        # ── gl_journals (agltransact) ─────────────────────────────────────────
        h_jnl = _filter_house(journals, house)
        jnl_lines    = len(h_jnl)
        jnl_vouchers = int(h_jnl['voucher_no'].nunique()) if not h_jnl.empty and 'voucher_no' in h_jnl.columns else 0
        jnl_accounts = int(h_jnl['account'].nunique())    if not h_jnl.empty and 'account'    in h_jnl.columns else 0
        jnl_users    = int(h_jnl['user_id'].nunique())    if not h_jnl.empty and 'user_id'    in h_jnl.columns else 0
        jnl_by_type  = h_jnl['voucher_type'].value_counts().to_dict() if not h_jnl.empty and 'voucher_type' in h_jnl.columns else {}
        jnl_net = float(pd.to_numeric(h_jnl['amount'], errors='coerce').sum()) if not h_jnl.empty and 'amount' in h_jnl.columns else 0.0
        jnl_pmin = jnl_pmax = None
        if not h_jnl.empty and 'period' in h_jnl.columns:
            pp = pd.to_numeric(h_jnl['period'], errors='coerce').dropna()
            if len(pp):
                jnl_pmin = int(pp.min())
                jnl_pmax = int(pp.max())

        # ── gl_dimconfig — HOC aggregates CA+CM ───────────────────────────────
        dc_clients = ['CA', 'CM'] if house == 'HOC' else ['LA']
        h_dc = dimconfig[dimconfig['client'].isin(dc_clients)].copy() if not dimconfig.empty and 'client' in dimconfig.columns else pd.DataFrame()

        dc_gl_count = dc_oos_count = dc_gl_active = 0
        if not h_dc.empty and 'dim_position' in h_dc.columns:
            h_dc['dim_position'] = h_dc['dim_position'].astype(str).str.strip()
            h_dc_agg = (
                h_dc.groupby(['attribute_id', 'dim_position'], as_index=False)
                .agg(active=('active', 'sum'), closed=('closed', 'sum'))
            )
            gl_rows  = h_dc_agg[h_dc_agg['dim_position'].isin(_GL_POS)]
            oos_rows = h_dc_agg[~h_dc_agg['dim_position'].isin(_GL_POS)]
            dc_gl_count  = len(gl_rows)
            dc_oos_count = len(oos_rows)
            dc_gl_active = int(pd.to_numeric(gl_rows['active'], errors='coerce').sum()) if not gl_rows.empty and 'active' in gl_rows.columns else 0

        result[house] = {
            'accounts': {
                'total':      acc_total,
                'active':     acc_active,
                'closed':     acc_closed,
                'by_type':    acc_type_bd,
                'by_res_bal': acc_res_bd,
            },
            'balances': {
                'total':         bal_total,
                'net_amount':    bal_net,
                'period_min':    bal_pmin,
                'period_max':    bal_pmax,
                'account_count': bal_accs,
            },
            'dimvalue': {
                'total':      dv_total,
                'attr_count': dv_attrs,
            },
            'dimconfig': {
                'gl_count':  dc_gl_count,
                'oos_count': dc_oos_count,
                'gl_active': dc_gl_active,
            },
            'journals': {
                'lines':      jnl_lines,
                'vouchers':   jnl_vouchers,
                'accounts':   jnl_accounts,
                'users':      jnl_users,
                'by_type':    jnl_by_type,
                'net_amount': jnl_net,
                'period_min': jnl_pmin,
                'period_max': jnl_pmax,
            },
        }

    return result