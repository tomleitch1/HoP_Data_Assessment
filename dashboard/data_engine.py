"""
Parliament Finance Systems Programme
DQ Engine & Data Processing
"""

import pandas as pd
import numpy as np
import os
from datetime import date
from dashboard.core.rules.gl_rules import get_gl_checks
from dashboard.core.rules.ap_rules import get_ap_checks
from dashboard.core.rules.ar_rules import get_ar_checks
from dashboard.core.rules.asset_rules import get_asset_checks   

DATA_DIR = 'data'
CLIENTS = ['HOC', 'HOL']
SCOPE_LABELS = {10: 'Suppliers', 11: 'Customers', 16: 'AP Invoices', 17: 'AR Invoices'}

def load_data():
    """Loads all CSV files from the data directory and combines HOC/HOL."""
    frames = {}
    
    # Mapping of filename to table name (GL files are single combined extracts)
    file_map = {
        'gl_chart_of_accounts.csv': 'aglaccounts',
        'gl_dimension_values.csv': 'agldimvalue',
        'gl_opening_balances.csv': 'aglyearend',
        'gl_transact_dimensions.csv': 'agltransact'
    }

    for filename, table in file_map.items():
        path = os.path.join(DATA_DIR, filename)
        if os.path.exists(path):
            df = pd.read_csv(path, low_memory=False)
            if 'client' in df.columns:
                df['house'] = df['client']
            frames[table] = df

    # Tables where house is determined by the filename suffix (_HOC / _HOL),
    # not by the client column. The client column contains internal Unit4 client
    # codes that are NOT 'HOC'/'HOL'.
    house_from_filename = {
        'supplier_master', 'supplier_open_trans', 'supplier_history',
        'asset_master', 'asset_depreciation', 'asset_balances',
        'asset_trans_flags', 'asset_groups', 'gl_journals',
    }

    # Load split files
    split_files = {
        'supplier_master': 'asuheader',
        'supplier_open_trans': 'asutrans',
        'supplier_history': 'asuhistr',
        'customer_master': 'acuheader',
        'customer_open_trans': 'acutrans',
        'customer_history': 'acuhistr',
        'asset_master': 'asset_master',
        'asset_depreciation': 'asset_depreciation',
        'asset_balances': 'asset_balances',
        'asset_trans_flags': 'asset_trans_flags',
        'asset_groups': 'asset_groups',
        'gl_journals': 'gl_journals',
    }
    for base_name, table in split_files.items():
        dfs = []
        for house in ['HOC', 'HOL']:
            path = os.path.join(DATA_DIR, f"{base_name}_{house}.csv")
            if os.path.exists(path):
                df = pd.read_csv(path, low_memory=False)
                if base_name in house_from_filename:
                    df['house'] = house
                elif 'client' in df.columns:
                    df['house'] = df['client']
                else:
                    df['house'] = house
                dfs.append(df)
        if dfs:
            frames[table] = pd.concat(dfs, ignore_index=True)

    # Process all frames for strings and dates
    for table, df in frames.items():
        # Force ID and registration columns to string to prevent DQ test errors
        string_cols = ['apar_id', 'vat_reg_no', 'comp_reg_no', 'bank_account', 'clearing_code', 'swift', 'iban', 'ext_inv_ref', 'voucher_no', 'account', 'dim_value', 'rel_value']
        for col in string_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).replace(['nan', 'None', ''], np.nan)
        
        # GL specific dimensions should be strings
        for i in range(1, 8):
            col = f'dim_{i}'
            if col in df.columns:
                df[col] = df[col].astype(str).replace(['nan', 'None', ''], np.nan)
        
        # Basic date parsing
        date_cols = ['trans_date', 'due_date', 'voucher_date', 'last_update', 'expired_date', 'period_from', 'period_to']
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        frames[table] = df

    return frames

def get_dq_checks():
    """Returns a list of DQ check definitions based on SQL requirements."""
    checks = []
    checks.extend(get_gl_checks())
    checks.extend(get_ap_checks())
    checks.extend(get_ar_checks())
    checks.extend(get_asset_checks())
    return checks

def run_dq_analysis(frames):
    """Executes all DQ checks and returns a summary DataFrame."""
    results = []
    checks = get_dq_checks()
    
    for check_id, scope_id, obj, dim, sev, desc, intent, rem, table, joined_table, logic, filter_func in checks:
        if table not in frames:
            continue
            
        df_table = frames[table]
        
        for house in CLIENTS:
            # Determine population based on table and check type
            if table in ['asuheader', 'acuheader']:
                if check_id in ['SUP_EXPIRED_ACTIVE', 'SUP_WF_STUCK']:
                    h_df = df_table[df_table['house'] == house]
                else:
                    h_df = df_table[(df_table['house'] == house) & (df_table['status'] == 'N')]
            elif table in ['asutrans', 'acutrans']:
                h_df = df_table[(df_table['house'] == house) & (df_table['status'] != 'C')]
            elif table in ['asuhistr', 'acuhistr']:
                h_df = df_table[df_table['house'] == house]
            elif table == 'aglaccounts':
                if check_id in ['GL_ACC_STALE_N', 'GL_ACC_DUP_CODE']:
                    h_df = df_table[df_table['house'] == house]
                else:
                    h_df = df_table[(df_table['house'] == house) & (df_table['status'] == 'N')]
            elif table == 'agldimvalue':
                if check_id in ['GL_DIM_DUP']:
                    h_df = df_table[df_table['house'] == house]
                else:
                    # Precision: only run stuck/orphan checks on active records
                    h_df = df_table[(df_table['house'] == house) & (df_table['status'] == 'N')]
            elif table in ['asset_master', 'asset_depreciation', 'asset_balances', 'asset_trans_flags']:
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
            rag = 'Green' if error_rate <= 2 else ('Amber' if error_rate <= 10 else 'Red')
            
            results.append({
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
            })
            
    return pd.DataFrame(results)

def get_check_columns():
    """Returns a map of check_id to the columns relevant for that check."""
    return {
        # GL Accounts
        'GL_ACC_DESC_MISSING': ['description', 'status'],
        'GL_ACC_GRP_MISSING': ['account_grp', 'status'],
        'GL_ACC_RESBAL_MISSING': ['res_bal'],
        'GL_ACC_RULE_MISSING': ['account_rule'],
        'GL_ACC_PERIOD_MISSING': ['period_from'],
        'GL_ACC_RESBAL_INVALID': ['res_bal'],
        'GL_ACC_TYPE_INVALID': ['account_type'],
        'GL_ACC_PERIOD_INV': ['period_from', 'period_to'],
        'GL_ACC_STALE_N': ['period_to', 'status'],
        'GL_ACC_BFLAG_CON': ['bflag', 'account_type'],
        'GL_ACC_DUP_CODE': ['account', 'client'],
        'GL_ACC_STALE_MOD': ['last_update'],

        # GL Dimensions
        'GL_DIM_DESC_MISSING': ['description', 'status'],
        'GL_DIM_PERIOD_MISSING': ['period_from'],
        'GL_DIM_PERIOD_INV': ['period_from', 'period_to'],
        'GL_DIM_WF_STUCK': ['wf_state'],
        'GL_DIM_ORPHAN_REL': ['rel_value', 'attribute_id', 'status'],
        'GL_DIM_DUP': ['dim_value', 'attribute_id', 'client'],

        # GL Balances
        'GL_BAL_AMT_MISSING': ['amount'],
        'GL_BAL_FX_MISSING': ['currency', 'cur_amount'],
        'GL_BAL_PL_NONZERO': ['amount', 'account', 'res_bal'],
        'GL_BAL_TOTAL_NET': ['amount', 'dc_flag', 'client'],
        'GL_BAL_ORPHAN_ACC': ['account'],

        # GL Transactions
        'GL_TRA_ORPHAN_DIM1': ['dim_1', 'dim_value', 'status'],

        # Suppliers
        'SUP_VAT_MISSING': ['vat_reg_no', 'status'],
        'SUP_COMP_REG_MISSING': ['comp_reg_no', 'status'],
        'SUP_TERMS_MISSING': ['terms_id'],
        'SUP_PAY_METHOD_MISSING': ['pay_method'],
        'SUP_CURRENCY_MISSING': ['currency'],
        'SUP_BANK_MISSING': ['bank_account'],
        'SUP_SORT_IBAN_MISSING': ['clearing_code', 'iban'],
        'SUP_SWIFT_MISSING': ['swift', 'iban'],
        'SUP_VAT_FORMAT': ['vat_reg_no'],
        'SUP_COMP_REG_FORMAT': ['comp_reg_no'],
        'SUP_SORT_FORMAT': ['clearing_code'],
        'SUP_BANK_FORMAT': ['bank_account'],
        'SUP_SWIFT_FORMAT': ['swift'],
        'SUP_EXPIRED_ACTIVE': ['expired_date', 'status'],
        'SUP_WF_STUCK': ['wf_state'],
        'SUP_BACS_NO_BANK': ['pay_method', 'bank_account', 'clearing_code'],
        'SUP_INT_NO_IBAN': ['pay_method', 'iban'],
        'SUP_NAME_DUP': ['apar_name', 'client'],
        'SUP_VAT_DUP': ['vat_reg_no', 'client'],
        'SUP_STALE': ['last_update'],
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
        'AP_REST_ZERO': ['rest_amount'],
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
        'CUS_VAT_MISSING': ['vat_reg_no', 'status'],
        'CUS_COMP_REG_MISSING': ['comp_reg_no', 'status'],
        'CUS_TERMS_MISSING': ['terms_id'],
        'CUS_PAY_METHOD_MISSING': ['pay_method'],
        'CUS_CURRENCY_MISSING': ['currency'],
        'CUS_CREDIT_LIMIT_MISSING': ['credit_limit'],
        'CUS_BANK_MISSING': ['pay_method', 'bank_account', 'iban'],
        'CUS_VAT_FORMAT': ['vat_reg_no'],
        'CUS_COMP_REG_FORMAT': ['comp_reg_no'],
        'CUS_NAME_DUP': ['apar_name', 'client'],
        'CUS_VAT_DUP': ['vat_reg_no', 'client'],

        # AR Invoices
        'AR_DUE_DATE_MISSING': ['due_date'],
        'AR_EXT_REF_MISSING': ['ext_inv_ref'],
        'AR_AMOUNT_MISSING': ['amount'],
        'AR_NEG_INV': ['amount', 'voucher_type'],
        'AR_REST_ZERO': ['rest_amount'],
        'AR_REST_OVER_AMT': ['rest_amount', 'amount'],
        'AR_OVERDUE': ['due_date'],
        'AR_WF_STUCK': ['wf_state'],
        'AR_ORPHANED_TRANS': ['apar_id'],
        'AR_TRANS_CUS_CLOSED': ['apar_id', 'status'],

        # AR History
        'AR_HIS_REST_NOT_ZERO': ['rest_amount'],
        'AR_HIS_DATE_MISSING': ['trans_date'],

        # Asset Register - Master
        'DQ-AM-C01': ['asset_id'],
        'DQ-AM-C02': ['description', 'status'],
        'DQ-AM-C03': ['asset_group', 'status'],
        'DQ-AM-C04': ['date_from', 'status'],
        'DQ-AM-C05': ['org_amount', 'cap_date_from'],
        'DQ-AM-C06': ['cap_date_from', 'cap_flag'],
        'DQ-AM-C07': ['ins_amount'],
        'DQ-AM-V01': ['status'],
        'DQ-AM-V02': ['wf_state'],
        'DQ-AM-V03': ['org_amount'],
        'DQ-AM-V04': ['date_from', 'date_to'],
        'DQ-AM-V05': ['cap_date_from', 'date_from'],
        'DQ-AM-V06': ['org_amt_date', 'cap_date_from'],
        'DQ-AM-T01': ['last_update'],
        'DQ-AM-K01': ['date_to', 'status'],
        'DQ-AM-K02': ['wf_state', 'status'],
        'DQ-AM-K03': ['org_amt_date', 'org_amount'],
        'DQ-AM-K04': ['grant_flag', 'dim_1'],
        'DQ-AM-D01': ['asset_id', 'house'],
        'DQ-AM-D02': ['description', 'asset_group', 'cap_date_from', 'org_amount'],
        'DQ-AM-R01': ['asset_id'],
        'DQ-AM-R02': ['asset_id'],
        'DQ-AM-R03': ['asset_id', 'status'],
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
        'DQ-AD-K04': ['index_id', 'depr_method'],
        'DQ-AD-K05': ['res_value', 'org_amount'],
        'DQ-AD-D01': ['asset_id', 'depr_book_id', 'house'],
        'DQ-AD-X01': ['asset_id'],
        'DQ-AD-X02': ['asset_id', 'status'],
        'DQ-AD-X03': ['cap_date_from'],
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
        'DQ-AB-K01': ['total_amount', 'trans_type'],
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
        'DQ-AG-D02': ['description'],
        'DQ-AG-X01': ['asset_group'],
        'DQ-AG-X03': ['depr_method', 'asset_group'],
        'DQ-AG-X04': ['lifetime', 'asset_group'],

        # GL Journals (agltransact — Seq 20)
        # Completeness
        'DQ-GJ-C01': ['voucher_no', 'client'],
        'DQ-GJ-C02': ['account', 'voucher_no'],
        'DQ-GJ-C03': ['amount', 'voucher_no'],
        'DQ-GJ-C04': ['trans_date', 'voucher_no'],
        'DQ-GJ-C05': ['voucher_date', 'voucher_no'],
        'DQ-GJ-C06': ['voucher_type', 'voucher_no'],
        'DQ-GJ-C07': ['description', 'voucher_type'],
        'DQ-GJ-C08': ['user_id', 'voucher_no'],
        # Validity
        'DQ-GJ-V01': ['update_flag', 'voucher_no'],
        'DQ-GJ-V02': ['trans_date', 'voucher_no'],
        'DQ-GJ-V03': ['voucher_date', 'voucher_no'],
        'DQ-GJ-V04': ['trans_date', 'voucher_date'],
        'DQ-GJ-V05': ['currency', 'voucher_no'],
        'DQ-GJ-V06': ['currency', 'cur_amount'],
        'DQ-GJ-V07': ['period', 'fiscal_year'],
        'DQ-GJ-V08': ['apar_id', 'account'],
        # Consistency
        'DQ-GJ-K01': ['voucher_no', 'amount', 'update_flag'],
        'DQ-GJ-K02': ['trans_date', 'period'],
        'DQ-GJ-K03': ['apar_id', 'apar_type'],
        'DQ-GJ-K04': ['voucher_no', 'period'],
        'DQ-GJ-K05': ['tax_code', 'tax_system'],
        # Duplicates
        'DQ-GJ-D01': ['voucher_no', 'sequence_no', 'client'],
        'DQ-GJ-D02': ['voucher_no', 'account', 'amount', 'trans_date'],
        # Scope / Info
        'DQ-GJ-S02': ['period', 'voucher_no', 'client'],
        'DQ-GJ-S04': ['currency', 'cur_amount'],
        'DQ-GJ-S05': ['apar_id', 'apar_type', 'account'],
        # Cross-extract
        'DQ-GJ-X01': ['account', 'voucher_no'],
        'DQ-GJ-X02': ['account', 'voucher_no'],
        'DQ-GJ-X03': ['dim_1', 'account'],
    }

def get_failing_records(check_id, house, frames, base_cols=None):
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
    if table in ['asuheader', 'acuheader']:
        if check_id in ['SUP_EXPIRED_ACTIVE', 'SUP_WF_STUCK']:
            h_df = df_table[df_table['house'] == house]
        else:
            h_df = df_table[(df_table['house'] == house) & (df_table['status'] == 'N')]
    elif table in ['asutrans', 'acutrans']:
        h_df = df_table[(df_table['house'] == house) & (df_table['status'] != 'C')]
    elif table in ['asuhistr', 'acuhistr']:
        h_df = df_table[df_table['house'] == house]
    elif table == 'aglaccounts':
        if check_id in ['GL_ACC_STALE_N', 'GL_ACC_DUP_CODE']:
            h_df = df_table[df_table['house'] == house]
        else:
            h_df = df_table[(df_table['house'] == house) & (df_table['status'] == 'N')]
    elif table == 'agldimvalue':
        if check_id in ['GL_DIM_DUP']:
            h_df = df_table[df_table['house'] == house]
        else:
            h_df = df_table[(df_table['house'] == house) & (df_table['status'] == 'N')]
    elif table in ['asset_master', 'asset_depreciation', 'asset_balances', 'asset_trans_flags']:
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

    # Enrich with context for better inspection
    if table == 'asset_depreciation' and check_id in ['DQ-AG-X03', 'DQ-AG-X04']:
        # 1. Join to Master to get the Bridging Group (Deduplicated)
        if 'asset_master' in frames:
            master_link = frames['asset_master'][['house', 'asset_id', 'asset_group']].copy()
            master_link = master_link.drop_duplicates(subset=['house', 'asset_id'])
            failing = failing.merge(master_link, on=['house', 'asset_id'], how='left')
            
        # 2. Join to Group Config to get the Standard Value (Deduplicated)
        if 'asset_groups' in frames:
            target_field = 'lifetime' if check_id == 'DQ-AG-X04' else 'depr_method'
            grp_link = frames['asset_groups'][['house', 'asset_group', target_field]].copy()
            grp_link.columns = ['house', 'asset_group', f'STANDARD_{target_field}']
            grp_link = grp_link.drop_duplicates(subset=['house', 'asset_group'])
            failing = failing.merge(grp_link, on=['house', 'asset_group'], how='left')
            
        # 3. Final Explicit Mapping for business users
        val_field = 'lifetime' if check_id == 'DQ-AG-X04' else 'depr_method'
        
        # We rename to explicit Source.Field format
        failing = failing.rename(columns={
            'asset_id': 'ASSET_DEPRECIATION.asset_id',
            val_field: f'ASSET_DEPRECIATION.{val_field}',
            'asset_group': 'ASSET_MASTER.asset_group',
            f'STANDARD_{val_field}': f'ASSET_GROUPS.{val_field}'
        })
        
        cols = ['ASSET_DEPRECIATION.asset_id', f'ASSET_DEPRECIATION.{val_field}', 'ASSET_MASTER.asset_group', f'ASSET_GROUPS.{val_field}']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_depreciation' and check_id == 'DQ-AD-K05':
        # Join to Asset Master to get org_amount for comparison
        if 'asset_master' in frames:
            master_link = frames['asset_master'][['house', 'asset_id', 'org_amount']].copy()
            master_link = master_link.drop_duplicates(subset=['house', 'asset_id'])
            failing = failing.merge(master_link, on=['house', 'asset_id'], how='left')
 
        # Rename to explicit Source.Field format for the evidence table
        failing = failing.rename(columns={
            'asset_id':          'ASSET_DEPRECIATION.asset_id',
            'res_value':         'ASSET_DEPRECIATION.res_value',
            'org_amount':        'ASSET_MASTER.org_amount',
        })
 
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.res_value', 'ASSET_MASTER.org_amount']
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
 
    if table == 'asset_balances' and check_id == 'DQ-AM-R03':
        failing = failing.rename(columns={'asset_id': 'ASSET_BALANCES.asset_id'})
        if 'asset_master' in frames:
            master_link = frames['asset_master'][['house', 'asset_id', 'status']].copy()
            master_link = master_link.drop_duplicates(subset=['house', 'asset_id'])
            master_link = master_link.rename(columns={'asset_id': 'ASSET_MASTER.asset_id', 'status': 'ASSET_MASTER.status'})
            failing = failing.merge(master_link, left_on=['house', 'ASSET_BALANCES.asset_id'], right_on=['house', 'ASSET_MASTER.asset_id'], how='left')
        cols = ['ASSET_BALANCES.asset_id', 'ASSET_MASTER.asset_id', 'ASSET_MASTER.status']
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
        failing = failing.rename(columns={'asset_id': 'ASSET_DEPRECIATION.asset_id', 'cap_date_from': 'ASSET_DEPRECIATION.cap_date_from'})
        if 'asset_master' in frames:
            master_link = frames['asset_master'][['house', 'asset_id', 'cap_date_from']].copy()
            master_link = master_link.drop_duplicates(subset=['house', 'asset_id'])
            master_link = master_link.rename(columns={'asset_id': 'ASSET_MASTER.asset_id', 'cap_date_from': 'ASSET_MASTER.cap_date_from'})
            failing = failing.merge(master_link, left_on=['house', 'ASSET_DEPRECIATION.asset_id'], right_on=['house', 'ASSET_MASTER.asset_id'], how='left')
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.cap_date_from', 'ASSET_MASTER.cap_date_from']
        return failing[[c for c in cols if c in failing.columns]]
 
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
        cols = ['ASSET_TRANS_FLAGS.asset_id', 'ASSET_TRANS_FLAGS.trans_type', 'ASSET_MASTER.status']
        return failing[[c for c in cols if c in failing.columns]]
 
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

    if table == 'asset_master' and check_id == 'DQ-AM-C07':
        failing = failing.rename(columns={
            'asset_id':   'ASSET_MASTER.asset_id',
            'ins_amount': 'ASSET_MASTER.ins_amount',
        })
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.ins_amount']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_master' and check_id == 'DQ-AM-V01':
        failing = failing.rename(columns={
            'asset_id': 'ASSET_MASTER.asset_id',
            'status':   'ASSET_MASTER.status',
        })
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.status']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_master' and check_id == 'DQ-AM-V02':
        failing = failing.rename(columns={
            'asset_id': 'ASSET_MASTER.asset_id',
            'wf_state': 'ASSET_MASTER.wf_state',
        })
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.wf_state']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_master' and check_id == 'DQ-AM-V03':
        failing = failing.rename(columns={
            'asset_id':   'ASSET_MASTER.asset_id',
            'org_amount': 'ASSET_MASTER.org_amount',
        })
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.org_amount']
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

    if table == 'asset_master' and check_id == 'DQ-AM-K02':
        failing = failing.rename(columns={
            'asset_id': 'ASSET_MASTER.asset_id',
            'wf_state': 'ASSET_MASTER.wf_state',
            'status':   'ASSET_MASTER.status',
        })
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.wf_state', 'ASSET_MASTER.status']
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
            'asset_id': 'ASSET_MASTER.asset_id',
            'house':    'ASSET_MASTER.house',
        })
        cols = ['ASSET_MASTER.asset_id', 'ASSET_MASTER.house']
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

    if table == 'asset_depreciation' and check_id == 'DQ-AD-K04':
        failing = failing.rename(columns={
            'asset_id':    'ASSET_DEPRECIATION.asset_id',
            'index_id':    'ASSET_DEPRECIATION.index_id',
            'depr_method': 'ASSET_DEPRECIATION.depr_method',
        })
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.index_id', 'ASSET_DEPRECIATION.depr_method']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'asset_depreciation' and check_id == 'DQ-AD-D01':
        failing = failing.rename(columns={
            'asset_id':     'ASSET_DEPRECIATION.asset_id',
            'depr_book_id': 'ASSET_DEPRECIATION.depr_book_id',
            'house':        'ASSET_DEPRECIATION.house',
        })
        cols = ['ASSET_DEPRECIATION.asset_id', 'ASSET_DEPRECIATION.depr_book_id', 'ASSET_DEPRECIATION.house']
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

    if table == 'asset_balances' and check_id == 'DQ-AB-K01':
        failing = failing.rename(columns={
            'asset_id':     'ASSET_BALANCES.asset_id',
            'depr_book_id': 'ASSET_BALANCES.depr_book_id',
            'trans_type':   'ASSET_BALANCES.trans_type',
            'total_amount': 'ASSET_BALANCES.total_amount',
        })
        cols = ['ASSET_BALANCES.asset_id', 'ASSET_BALANCES.depr_book_id', 'ASSET_BALANCES.trans_type', 'ASSET_BALANCES.total_amount']
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
            'house':       'ASSET_GROUPS.house',
        })
        cols = ['ASSET_GROUPS.asset_group', 'ASSET_GROUPS.description', 'ASSET_GROUPS.house']
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
        failing = failing.rename(columns={
            'voucher_no': 'AP_INVOICES.voucher_no',
            'apar_id':    'AP_INVOICES.apar_id',
        })
        if 'asuheader' in frames:
            sup_link = frames['asuheader'][['house', 'apar_id']].copy()
            sup_link = sup_link.drop_duplicates(subset=['house', 'apar_id'])
            sup_link = sup_link.rename(columns={'apar_id': 'SUPPLIER_MASTER.apar_id'})
            failing = failing.merge(sup_link,
                left_on=['house', 'AP_INVOICES.apar_id'],
                right_on=['house', 'SUPPLIER_MASTER.apar_id'],
                how='left')
        cols = ['AP_INVOICES.voucher_no', 'AP_INVOICES.apar_id', 'SUPPLIER_MASTER.apar_id']
        return failing[[c for c in cols if c in failing.columns]]

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

    if table in ['asutrans', 'asuhistr'] and 'asuheader' in frames:
        # Join to master to get supplier name for transaction errors
        master = frames['asuheader'][['house', 'apar_id', 'apar_name', 'status']].copy()
        master.columns = ['house', 'apar_id', 'Master_Supplier_Name', 'Master_Status']
        failing = failing.merge(master, on=['house', 'apar_id'], how='left')
    
    if table in ['acutrans', 'acuhistr'] and 'acuheader' in frames:
        # Join to master to get customer name for transaction errors
        master = frames['acuheader'][['house', 'apar_id', 'apar_name', 'status']].copy()
        master.columns = ['house', 'apar_id', 'Master_Customer_Name', 'Master_Status']
        failing = failing.merge(master, on=['house', 'apar_id'], how='left')

    if table == 'aglyearend' and check_id == 'GL_BAL_ORPHAN_ACC':
        failing = failing.rename(columns={
            'account': 'GL_BALANCES.account',
            'amount':  'GL_BALANCES.amount',
        })
        if 'aglaccounts' in frames:
            acc_link = frames['aglaccounts'][['house', 'account']].copy()
            acc_link = acc_link.drop_duplicates(subset=['house', 'account'])
            acc_link = acc_link.rename(columns={'account': 'GL_ACCOUNTS.account'})
            failing = failing.merge(acc_link,
                left_on=['house', 'GL_BALANCES.account'],
                right_on=['house', 'GL_ACCOUNTS.account'],
                how='left')
        cols = ['GL_BALANCES.account', 'GL_BALANCES.amount', 'GL_ACCOUNTS.account']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'aglyearend' and check_id == 'GL_BAL_PL_NONZERO':
        failing = failing.rename(columns={
            'account': 'GL_BALANCES.account',
            'amount':  'GL_BALANCES.amount',
        })
        if 'aglaccounts' in frames:
            acc_link = frames['aglaccounts'][['house', 'account', 'res_bal']].copy()
            acc_link = acc_link.drop_duplicates(subset=['house', 'account'])
            acc_link = acc_link.rename(columns={
                'account': 'GL_ACCOUNTS.account',
                'res_bal': 'GL_ACCOUNTS.res_bal',
            })
            failing = failing.merge(acc_link,
                left_on=['house', 'GL_BALANCES.account'],
                right_on=['house', 'GL_ACCOUNTS.account'],
                how='left')
        cols = ['GL_BALANCES.account', 'GL_BALANCES.amount', 'GL_ACCOUNTS.account', 'GL_ACCOUNTS.res_bal']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'agltransact' and check_id == 'GL_TRA_ORPHAN_DIM1':
        failing = failing.rename(columns={
            'dim_1': 'GL_TRANSACTIONS.dim_1',
        })
        if 'agldimvalue' in frames:
            dim_link = frames['agldimvalue'][['house', 'dim_value', 'status']].copy()
            dim_link = dim_link.drop_duplicates(subset=['house', 'dim_value'])
            dim_link = dim_link.rename(columns={
                'dim_value': 'GL_DIMENSIONS.dim_value',
                'status':    'GL_DIMENSIONS.status',
            })
            failing = failing.merge(dim_link,
                left_on=['house', 'GL_TRANSACTIONS.dim_1'],
                right_on=['house', 'GL_DIMENSIONS.dim_value'],
                how='left')
        cols = ['GL_TRANSACTIONS.dim_1', 'GL_DIMENSIONS.dim_value', 'GL_DIMENSIONS.status']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'agldimvalue' and check_id == 'GL_DIM_ORPHAN_REL':
        failing = failing.rename(columns={
            'dim_value': 'GL_DIMENSIONS.dim_value',
            'rel_value': 'GL_DIMENSIONS.rel_value',
        })
        if 'agldimvalue' in frames:
            parent_link = frames['agldimvalue'][['house', 'dim_value']].copy()
            parent_link = parent_link.drop_duplicates(subset=['house', 'dim_value'])
            parent_link = parent_link.rename(columns={'dim_value': 'GL_DIMENSIONS (TARGET).dim_value'})
            failing = failing.merge(parent_link,
                left_on=['house', 'GL_DIMENSIONS.rel_value'],
                right_on=['house', 'GL_DIMENSIONS (TARGET).dim_value'],
                how='left')
        cols = ['GL_DIMENSIONS.dim_value', 'GL_DIMENSIONS.rel_value', 'GL_DIMENSIONS (TARGET).dim_value']
        return failing[[c for c in cols if c in failing.columns]]

    if table == 'aglyearend' and 'aglaccounts' in frames:
        acc = frames['aglaccounts'][['house', 'account', 'description', 'res_bal', 'status']].copy()
        acc.columns = ['house', 'account', 'Account_Description', 'Res_Bal', 'Account_Status']
        failing = failing.merge(acc, on=['house', 'account'], how='left')

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
