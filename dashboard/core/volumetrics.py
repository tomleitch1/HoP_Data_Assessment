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
    GLConfig
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


def _count_by_status(df: pd.DataFrame, house: str, col: str = 'status') -> dict:
    """Return {status_value: count} for a given house."""
    if df is None or col not in df.columns:
        return {}
    sub = df[df['client'] == house]
    return sub[col].value_counts().to_dict()


def _sum_column(df: pd.DataFrame, house: str, col: str) -> float:
    """Return the sum of a numeric column for a given house, safely."""
    if df is None or col not in df.columns:
        return 0.0
    sub = df[df['client'] == house]
    return pd.to_numeric(sub[col], errors='coerce').sum()


def _record_count(df: pd.DataFrame, house: str) -> int:
    if df is None:
        return 0
    return int((df['client'] == house).sum())


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
    gl_coa = frames.get('aglaccounts')
    gl_ob  = frames.get('aglyearend')

    result = {}
    for house in CLIENTS:
        # ── Supplier master ───────────────────────────────────────────────────
        sup_all      = sup[sup['client'] == house] if sup is not None else pd.DataFrame()
        sup_active   = int(sup_all['status'].isin(SupplierConfig.ACTIVE_STATUSES).sum())   if not sup_all.empty else 0
        sup_inactive = int(sup_all['status'].isin(SupplierConfig.INACTIVE_STATUSES).sum()) if not sup_all.empty else 0
        sup_total    = len(sup_all)

        # ── Customer master ───────────────────────────────────────────────────
        cus_all      = cus[cus['client'] == house] if cus is not None else pd.DataFrame()
        cus_active   = int(cus_all['status'].isin(CustomerConfig.ACTIVE_STATUSES).sum())   if not cus_all.empty else 0
        cus_inactive = int(cus_all['status'].isin(CustomerConfig.INACTIVE_STATUSES).sum()) if not cus_all.empty else 0
        cus_total    = len(cus_all)

        # ── AP transactions ───────────────────────────────────────────────────
        ap_h         = ap[ap['client'] == house] if ap is not None else pd.DataFrame()
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
        ar_h         = ar[ar['client'] == house] if ar is not None else pd.DataFrame()
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

        # ── GL summary ────────────────────────────────────────────────────────
        coa_h        = gl_coa[gl_coa['client'] == house] if gl_coa is not None else pd.DataFrame()
        gl_coa_total = len(coa_h)
        gl_accounts  = int(coa_h['status'].isin(GLConfig.ACTIVE_STATUSES).sum()) if not coa_h.empty and 'status' in coa_h.columns else 0
        gl_pl        = int((coa_h['res_bal'] == 'R').sum()) if not coa_h.empty and 'res_bal' in coa_h.columns else 0
        gl_bs        = int((coa_h['res_bal'] == 'B').sum()) if not coa_h.empty and 'res_bal' in coa_h.columns else 0
        ob_h         = gl_ob[gl_ob['client'] == house] if gl_ob is not None else pd.DataFrame()
        gl_ob_total  = len(ob_h)
        gl_ob_bal    = float(pd.to_numeric(ob_h.get('amount', pd.Series(dtype=float)), errors='coerce').sum()) if not ob_h.empty else 0.0
        gl_coa_date  = _safe_max_date(coa_h, 'last_update') if not coa_h.empty else None
        # Total across all three scored GL tables (CoA + OB; dim_values counted separately)
        gl_dim_df    = frames.get('agldimvalue')
        gl_dim_h     = gl_dim_df[gl_dim_df['client'] == house] if gl_dim_df is not None else pd.DataFrame()
        gl_total_all = gl_coa_total + gl_ob_total + len(gl_dim_h)

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
            # ── GL ────────────────────────────────────────────────────────────
            'gl_total_records':   gl_total_all,    # CoA + Dim Values + Opening Balances
            'gl_accounts_active': gl_accounts,
            'gl_pl_accounts':     gl_pl,
            'gl_bs_accounts':     gl_bs,
            'gl_ob_rows':         gl_ob_total,
            'gl_ob_balance':      gl_ob_bal,
            'gl_extract_date':    gl_coa_date,
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
    elif scope_key == 'gl':
        master_key    = 'aglaccounts'
        trans_key     = 'aglyearend'
        hist_key      = None
        master_label  = 'Chart of Accounts'
        trans_label   = 'Opening Balances'
        active_stats  = GLConfig.ACTIVE_STATUSES
        inactive_stats= GLConfig.INACTIVE_STATUSES   # C, P, T — same pattern as suppliers/customers
        open_stats    = []   # opening balances have no status filter
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
        m = master_df[master_df['client'] == house].copy() if master_df is not None else pd.DataFrame()

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
        t = trans_df[trans_df['client'] == house].copy() if trans_df is not None else pd.DataFrame()

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
            h_house = hist_df[hist_df['client'] == house] if 'client' in hist_df.columns else pd.DataFrame()
            hist_out[house] = {
                'total':        len(h_house),
                'extract_date': _safe_max_date(h_house, 'trans_date'),
            }

        # ── GL Dimension Values (GL tab only) ─────────────────────────────────
        if scope_key == 'gl':
            dim_df   = frames.get('agldimvalue')
            dim_h    = dim_df[dim_df['client'] == house].copy() if dim_df is not None else pd.DataFrame()
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
        # 1. Supplier Logic
        h_header = header[header['client'] == house] if not header.empty else pd.DataFrame()
        active   = int((h_header['status'] == 'N').sum()) if not h_header.empty and 'status' in h_header.columns else 0
        inactive = int((h_header['status'] == 'C').sum()) if not h_header.empty and 'status' in h_header.columns else 0
        total_m  = len(h_header)
        m_date   = _safe_max_date(h_header, 'last_update')
        
        # Added: Full status breakdown for master data
        m_status_breakdown = h_header['status'].value_counts().to_dict() if not h_header.empty and 'status' in h_header.columns else {}
        
        # 2. Transaction Logic
        h_trans = trans[trans['client'] == house] if not trans.empty else pd.DataFrame()
        t_all_counts = h_trans['status'].value_counts().to_dict() if not h_trans.empty and 'status' in h_trans.columns else {}
        
        t_open = h_trans[h_trans['status'].isin(open_statuses)] if not h_trans.empty and 'status' in h_trans.columns else pd.DataFrame()
        
        open_count = len(t_open)
        balance    = float(pd.to_numeric(t_open['rest_amount'], errors='coerce').sum()) if not t_open.empty and 'rest_amount' in t_open.columns else 0.0
        
        if not t_open.empty and 'due_date' in t_open.columns:
            due = pd.to_datetime(t_open['due_date'], errors='coerce')
            overdue = int((due < today).sum())
        else:
            overdue = 0
            
        if not t_open.empty and 'trans_date' in t_open.columns:
            td = pd.to_datetime(t_open['trans_date'], errors='coerce')
            ages = (today - td).dt.days.dropna()
            avg_age = float(ages.mean()) if len(ages) else 0.0
        else:
            avg_age = 0.0
            
        t_date = _safe_max_date(h_trans, 'trans_date')
        
        # 3. History Logic
        h_hist = hist[hist['client'] == house] if not hist.empty else pd.DataFrame()
        hist_total = len(h_hist)
        
        results[house] = {
            'house': house,
            'master': {
                'total': total_m,
                'active': active,
                'inactive': inactive,
                'status_breakdown': m_status_breakdown,
                'extract_date': m_date
            },
            'transactions': {
                'open_count': open_count,
                'balance': balance,
                'overdue_count': overdue,
                'avg_days_old': avg_age,
                'status_breakdown': t_all_counts,
                'extract_date': t_date
            },
            'history': {
                'total': hist_total
            }
        }
        
    return results

def get_ar_volumetrics(df_dict: dict) -> dict:
    """
    Returns calculated AR volumetrics for both Houses.
    Calculates Active ('N'), Inactive ('C'), and Total counts for Customers.
    Calculates Open Count, Balance, Overdue Count, and Avg Days Old for Transactions.
    """
    import pandas as pd
    today = pd.Timestamp.now().normalize()
    open_statuses = ['N', 'R', 'I', 'P']
    CLIENTS = ['HOC', 'HOL']
    
    header = df_dict.get('acuheader', pd.DataFrame())
    trans  = df_dict.get('acutrans', pd.DataFrame())
    hist   = df_dict.get('acuhistr', pd.DataFrame())
    
    # We need _safe_max_date
    def _safe_max_date(df, col):
        if df.empty or col not in df.columns:
            return None
        valid = pd.to_datetime(df[col], errors='coerce').dropna()
        return valid.max() if not valid.empty else None

    results = {}
    
    for house in CLIENTS:
        # 1. Customer Logic
        h_header = header[header['client'] == house] if not header.empty and 'client' in header.columns else (header[header['house'] == house] if not header.empty and 'house' in header.columns else pd.DataFrame())
        active   = int((h_header['status'] == 'N').sum()) if not h_header.empty and 'status' in h_header.columns else 0
        inactive = int((h_header['status'] == 'C').sum()) if not h_header.empty and 'status' in h_header.columns else 0
        total_m  = len(h_header)
        m_date   = _safe_max_date(h_header, 'last_update')
        
        m_status_breakdown = h_header['status'].value_counts().to_dict() if not h_header.empty and 'status' in h_header.columns else {}
        
        # 2. Transaction Logic
        h_trans = trans[trans['client'] == house] if not trans.empty and 'client' in trans.columns else (trans[trans['house'] == house] if not trans.empty and 'house' in trans.columns else pd.DataFrame())
        t_all_counts = h_trans['status'].value_counts().to_dict() if not h_trans.empty and 'status' in h_trans.columns else {}
        
        t_open = h_trans[h_trans['status'].isin(open_statuses)] if not h_trans.empty and 'status' in h_trans.columns else pd.DataFrame()
        
        open_count = len(t_open)
        balance    = float(pd.to_numeric(t_open['rest_amount'], errors='coerce').sum()) if not t_open.empty and 'rest_amount' in t_open.columns else 0.0
        
        if not t_open.empty and 'due_date' in t_open.columns:
            due = pd.to_datetime(t_open['due_date'], errors='coerce')
            overdue = int((due < today).sum())
        else:
            overdue = 0
            
        if not t_open.empty and 'trans_date' in t_open.columns:
            td = pd.to_datetime(t_open['trans_date'], errors='coerce')
            ages = (today - td).dt.days.dropna()
            avg_age = float(ages.mean()) if len(ages) else 0.0
        else:
            avg_age = 0.0
            
        t_date = _safe_max_date(h_trans, 'trans_date')
        
        # 3. History Logic
        h_hist = hist[hist['client'] == house] if not hist.empty and 'client' in hist.columns else (hist[hist['house'] == house] if not hist.empty and 'house' in hist.columns else pd.DataFrame())
        hist_total = len(h_hist)
        
        results[house] = {
            'house': house,
            'master': {
                'total': total_m,
                'active': active,
                'inactive': inactive,
                'status_breakdown': m_status_breakdown,
                'extract_date': m_date
            },
            'transactions': {
                'open_count': open_count,
                'balance': balance,
                'overdue_count': overdue,
                'avg_days_old': avg_age,
                'status_breakdown': t_all_counts,
                'extract_date': t_date
            },
            'history': {
                'total': hist_total
            }
        }
        
    return results


def get_gl_volumetrics(df_dict: dict) -> dict:
    """
    Returns calculated GL volumetrics for both Houses.
    Calculates Chart of Accounts, Opening Balances, and Dimension Values stats.
    """
    import pandas as pd
    CLIENTS = ['HOC', 'HOL']
    
    coa = df_dict.get('aglaccounts', pd.DataFrame())
    ob = df_dict.get('aglyearend', pd.DataFrame())
    dim = df_dict.get('agldimvalue', pd.DataFrame())
    
    def _safe_max_date(df, col):
        if df.empty or col not in df.columns:
            return None
        valid = pd.to_datetime(df[col], errors='coerce').dropna()
        return valid.max().strftime('%d %b %Y').lstrip('0') if not valid.empty else None

    results = {}
    for house in CLIENTS:
        # COA
        h_coa = coa[coa['client'] == house] if not coa.empty and 'client' in coa.columns else (coa[coa['house'] == house] if not coa.empty and 'house' in coa.columns else pd.DataFrame())
        coa_active = int((h_coa['status'] == 'N').sum()) if not h_coa.empty and 'status' in h_coa.columns else 0
        coa_inactive = int((h_coa['status'] == 'C').sum()) if not h_coa.empty and 'status' in h_coa.columns else 0
        coa_types = h_coa['account_type'].value_counts().to_dict() if not h_coa.empty and 'account_type' in h_coa.columns else {}
        
        # OB
        h_ob = ob[ob['client'] == house] if not ob.empty and 'client' in ob.columns else (ob[ob['house'] == house] if not ob.empty and 'house' in ob.columns else pd.DataFrame())
        if not h_ob.empty and 'amount' in h_ob.columns and 'dc_flag' in h_ob.columns:
            debits = float(pd.to_numeric(h_ob.loc[h_ob['dc_flag'] == 1, 'amount'], errors='coerce').sum())
            credits = float(pd.to_numeric(h_ob.loc[h_ob['dc_flag'] == -1, 'amount'], errors='coerce').sum())
        else:
            debits = 0.0
            credits = 0.0
            
        # Dim
        h_dim = dim[dim['client'] == house] if not dim.empty and 'client' in dim.columns else (dim[dim['house'] == house] if not dim.empty and 'house' in dim.columns else pd.DataFrame())
        dim_active = int((h_dim['status'] == 'N').sum()) if not h_dim.empty and 'status' in h_dim.columns else 0
        dim_inactive = int((h_dim['status'] != 'N').sum()) if not h_dim.empty and 'status' in h_dim.columns else 0
        dim_types = h_dim['attribute_id'].value_counts().to_dict() if not h_dim.empty and 'attribute_id' in h_dim.columns else {}

        results[house] = {
            'house': house,
            'coa': {
                'total': len(h_coa),
                'active': coa_active,
                'inactive': coa_inactive,
                'type_breakdown': coa_types,
                'extract_date': _safe_max_date(h_coa, 'last_update')
            },
            'ob': {
                'total_rows': len(h_ob),
                'debits': debits,
                'credits': credits,
                'net_balance': abs(debits - credits),
                'extract_date': _safe_max_date(h_ob, 'trans_date')
            },
            'dim': {
                'total': len(h_dim),
                'active': dim_active,
                'inactive': dim_inactive,
                'type_breakdown': dim_types,
                'extract_date': _safe_max_date(h_dim, 'last_update')
            }
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
        h = assets[assets['client'] == house] if not assets.empty and 'client' in assets.columns else \
            (assets[assets['house'] == house] if not assets.empty and 'house' in assets.columns else pd.DataFrame())

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