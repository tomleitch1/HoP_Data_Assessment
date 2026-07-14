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

DATA_DIR = 'data'
CLIENTS = ['HOC', 'HOL']
SCOPE_LABELS = {10: 'Suppliers', 11: 'Customers', 16: 'AP Invoices', 17: 'AR Invoices'}

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
}
# Reverse lookup: base_name -> subdirectory
_SUBDIR_MAP = {name: sub for sub, names in SUBDIR.items() for name in names}

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
    """Hash of run_dq_analysis source only.  Changing get_failing_records,
    get_check_columns, or any other function in this file does NOT change
    this value — only edits to run_dq_analysis itself do.
    """
    global _ENGINE_SIG_CACHE
    if _ENGINE_SIG_CACHE is None:
        try:
            src = _inspect.getsource(run_dq_analysis)
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
]}


# Maps CLI/SUBDIR domain names to SCOPE_CONFIG keys for check filtering
_SUBDIR_TO_SCOPE = {
    'suppliers': 'ap',
    'customers': 'ar',
    'gl':        'gl',
    'assets':    'assets',
    'po':        'po',
}

# User-friendly aliases accepted on the command line
TAB_ALIASES = {
    'suppliers': 'suppliers', 'ap': 'suppliers',
    'customers': 'customers', 'ar': 'customers',
    'gl':        'gl',
    'assets':    'assets',
}


def load_data(tab=None):
    """Loads CSV files from the data directory and combines HOC/HOL.

    If *tab* is provided (e.g. 'suppliers'), only files for that domain are
    loaded.  Pass None (default) to load everything.
    """
    frames = {}
    _cached = set()  # tables loaded from cache — skip re-processing

    names_to_load = set(SUBDIR.get(tab, [])) if tab else {
        n for names in SUBDIR.values() for n in names
    }

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

    # Process frames that were not loaded from cache
    for table, df in frames.items():
        if table in _cached:
            continue
        # Force ID and registration columns to string to prevent DQ test errors
        string_cols = ['apar_id', 'vat_reg_no', 'comp_reg_no', 'bank_account', 'clearing_code', 'swift', 'iban', 'ext_inv_ref', 'voucher_no', 'account', 'dim_value', 'rel_value']
        for col in string_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().replace(['nan', 'None', ''], np.nan)
        
        # GL specific dimensions should be strings
        for i in range(1, 8):
            col = f'dim_{i}'
            if col in df.columns:
                df[col] = df[col].astype(str).replace(['nan', 'None', ''], np.nan)
        
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

    return frames

def get_dq_checks():
    """Returns a list of DQ check definitions based on SQL requirements."""
    checks = []
    checks.extend(get_ap_checks())
    checks.extend(get_ar_checks())
    checks.extend(get_asset_checks())
    checks.extend(get_gl_checks())
    checks.extend(get_po_checks())
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

        _dq_version = os.environ.get('DASHBOARD_VERSION', '').strip()
        for house in CLIENTS:
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
                if check_id == 'PO_STUCK_NOT_ORDERED':
                    h_df = df_table[(df_table['house'] == house) & (df_table['status'] == 'N')]
                elif check_id == 'PO_FINISHED_WITH_BALANCE':
                    h_df = df_table[(df_table['house'] == house) & (df_table['status'] == 'F')]
                else:
                    h_df = df_table[(df_table['house'] == house) & (df_table['status'] != 'T')]
            elif table == 'apodetail':
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
        'PO_LINE_NO_ACCOUNT':         ['order_id', 'line_no', 'account', 'status'],
        'PO_DUP_LINE':                ['client', 'order_id', 'line_no', 'sequence_no', 'status'],
        'PO_HDR_LINE_STATUS_MISMATCH': ['order_id', 'line_no', 'status'],

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
        if check_id == 'PO_STUCK_NOT_ORDERED':
            h_df = df_table[(df_table['house'] == house) & (df_table['status'] == 'N')]
        elif check_id == 'PO_FINISHED_WITH_BALANCE':
            h_df = df_table[(df_table['house'] == house) & (df_table['status'] == 'F')]
        else:
            h_df = df_table[(df_table['house'] == house) & (df_table['status'] != 'T')]
    elif table == 'apodetail':
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
    if for_export:
        return failing

    # Enrich with context for better inspection
    if check_id == 'GL_DIM_DUP_DESC' and 'aglaccounts' in frames:
        coa = frames['aglaccounts'][frames['aglaccounts']['house'] == house][['client', 'account', 'account_grp']].drop_duplicates(subset=['client', 'account'])
        failing = failing.merge(coa.rename(columns={'account': 'dim_value'}), on=['client', 'dim_value'], how='left')

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

    if check_id == 'PO_HDR_LINE_STATUS_MISMATCH' and 'apoheader' in frames:
        # Explicit join on (client, order_id) — the real apoheader/apodetail key.
        # The generic referential-integrity join below would instead resolve to
        # (house, apar_id, voucher_no), since client/order_id aren't in its
        # candidate key list — that's a different, unverified relationship, not
        # the actual PO composite key, so this check bypasses it entirely.
        hdr = frames['apoheader'][frames['apoheader']['house'] == house][['client', 'order_id', 'status']]
        hdr = hdr.drop_duplicates(subset=['client', 'order_id']).rename(columns={'status': 'apoheader.status'})
        failing = failing.merge(hdr, on=['client', 'order_id'], how='left')
        failing = failing.rename(columns={
            'order_id': 'apodetail.order_id',
            'line_no':  'apodetail.line_no',
            'status':   'apodetail.status',
        })
        cols = ['apodetail.order_id', 'apodetail.line_no', 'apodetail.status', 'apoheader.status']
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
