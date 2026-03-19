import pandas as pd
from datetime import date

def get_ap_checks():
    """Returns a list of Supplier and AP DQ check definitions."""
    today = pd.Timestamp(date.today())
    
    checks = [
        # ======================================================================
        # --- SUPPLIER MASTER (asuheader) ---
        # ======================================================================
        
        ('SUP_VAT_MISSING', 10, 'Suppliers', 'Completeness', 'Medium', 
         'Active supplier missing VAT registration number',
         'Verifies presence of VAT numbers for active suppliers to ensure compliance with UK tax regulations.',
         'Verify asuheader.vat_reg_no.', 'asuheader', None,
         'asuheader.vat_reg_no IS NULL WHERE status = "N"',
         lambda df: df['vat_reg_no'].isna()),
         
        ('SUP_COMP_REG_MISSING', 10, 'Suppliers', 'Completeness', 'Low', 
         'Active supplier missing company registration number',
         'Checks for the presence of Companies House registration numbers for corporate entity validation.',
         'Verify asuheader.comp_reg_no.', 'asuheader', None,
         'asuheader.comp_reg_no IS NULL WHERE status = "N"',
         lambda df: df['comp_reg_no'].isna()),

        ('SUP_TERMS_MISSING', 10, 'Suppliers', 'Completeness', 'High', 
         'Active supplier missing payment terms',
         'Ensures all active suppliers have payment terms defined to automate accurate due date calculation.',
         'Assign asuheader.terms_id.', 'asuheader', None,
         'asuheader.terms_id IS NULL',
         lambda df: df['terms_id'].isna()),

        ('SUP_PAY_METHOD_MISSING', 10, 'Suppliers', 'Completeness', 'Critical', 
         'Active supplier missing default payment method',
         'Critical for payment run automation; verifies that a payment method (BACS/INT) is assigned.',
         'Assign asuheader.pay_method (BACS/INT).', 'asuheader', None,
         'asuheader.pay_method IS NULL',
         lambda df: df['pay_method'].isna()),

        ('SUP_CURRENCY_MISSING', 10, 'Suppliers', 'Completeness', 'Critical', 
         'Active supplier missing default currency',
         'Ensures all active suppliers have a default currency (typically GBP) to prevent posting errors.',
         'Assign asuheader.currency (GBP).', 'asuheader', None,
         'asuheader.currency IS NULL',
         lambda df: df['currency'].isna()),

        ('SUP_BANK_MISSING', 10, 'Suppliers', 'Completeness', 'Critical', 
         'Active supplier missing bank account number',
         'Identifies active suppliers missing bank details, which would prevent automated settlement.',
         'Obtain and populate asuheader.bank_account.', 'asuheader', None,
         'asuheader.bank_account IS NULL',
         lambda df: df['bank_account'].isna()),

        ('SUP_SORT_IBAN_MISSING', 10, 'Suppliers', 'Completeness', 'Critical', 
         'Active supplier missing both Sort Code AND IBAN',
         'Verifies that at least one form of electronic routing (Sort Code or IBAN) is available for payments.',
         'Required routing in asuheader.clearing_code or iban.', 'asuheader', None,
         'asuheader.clearing_code IS NULL AND asuheader.iban IS NULL',
         lambda df: df['clearing_code'].isna() & df['iban'].isna()),

        ('SUP_SWIFT_MISSING', 10, 'Suppliers', 'Completeness', 'High', 
         'Supplier has an IBAN but is missing a SWIFT/BIC code',
         'Ensures international suppliers have both IBAN and SWIFT codes for cross-border payment compliance.',
         'Required for international; populate asuheader.swift.', 'asuheader', None,
         'asuheader.iban IS NOT NULL AND asuheader.swift IS NULL',
         lambda df: df['swift'].isna() & df['iban'].notna()),

        ('SUP_VAT_FORMAT', 10, 'Suppliers', 'Validity', 'High', 
         'VAT number format is invalid (Expected GB + 9 digits)',
         'Validates that VAT numbers conform to the HMRC standard format (GB prefix followed by 9 digits).',
         'Correct asuheader.vat_reg_no.', 'asuheader', None,
         'asuheader.vat_reg_no NOT LIKE "GB_________" (9 digits)',
         lambda df: (~df['vat_reg_no'].str.match(r'^GB\d{9}$', na=False)) & df['vat_reg_no'].notna()),

        ('SUP_COMP_REG_FORMAT', 10, 'Suppliers', 'Validity', 'Medium', 
         'Company registration format is invalid (Expected 8 digits)',
         'Validates that Company House numbers are exactly 8 digits long.',
         'Correct asuheader.comp_reg_no.', 'asuheader', None,
         'asuheader.comp_reg_no NOT LIKE "________" (8 digits)',
         lambda df: (~df['comp_reg_no'].str.match(r'^\d{8}$', na=False)) & df['comp_reg_no'].notna()),

        ('SUP_SORT_FORMAT', 10, 'Suppliers', 'Validity', 'High', 
         'Bank sort code format is invalid (Expected XX-XX-XX)',
         'Ensures bank sort codes follow the standard hyphenated 6-digit pattern.',
         'Correct asuheader.clearing_code.', 'asuheader', None,
         'asuheader.clearing_code NOT LIKE "__-__-__"',
         lambda df: (~df['clearing_code'].str.match(r'^\d{2}-\d{2}-\d{2}$', na=False)) & df['clearing_code'].notna()),

        ('SUP_BANK_FORMAT', 10, 'Suppliers', 'Validity', 'Critical', 
         'Bank account format is invalid (Expected 8 digits)',
         'Ensures UK bank account numbers are valid 8-digit numeric strings.',
         'Correct asuheader.bank_account.', 'asuheader', None,
         'asuheader.bank_account NOT LIKE "________" (8 digits)',
         lambda df: (~df['bank_account'].str.match(r'^\d{8}$', na=False)) & df['bank_account'].notna()),

        ('SUP_SWIFT_FORMAT', 10, 'Suppliers', 'Validity', 'High', 
         'SWIFT/BIC format is invalid (Expected 8 or 11 chars)',
         'Validates the alphanumeric SWIFT/BIC code format for international routing.',
         'Correct asuheader.swift.', 'asuheader', None,
         'asuheader.swift length NOT IN (8, 11) or contains invalid chars',
         lambda df: (~df['swift'].str.match(r'^[A-Z0-9]{8,11}$', na=False)) & df['swift'].notna()),

        ('SUP_EXPIRED_ACTIVE', 10, 'Suppliers', 'Consistency', 'Medium', 
         'Supplier is active but has an expired/closed date populated',
         'Identifies data conflicts where a supplier is marked active despite having a past expiration date.',
         'Review status alignment in asuheader.', 'asuheader', None,
         'asuheader.status = "N" AND asuheader.expired_date IS NOT NULL',
         lambda df: df['expired_date'].notna() & (df['status'] == 'N')),

        ('SUP_WF_STUCK', 10, 'Suppliers', 'Consistency', 'Medium', 
         'Supplier is currently stuck in an unapproved workflow state',
         'Ensures all supplier master changes have completed the Unit4 approval cycle.',
         'Complete asuheader.wf_state.', 'asuheader', None,
         'asuheader.wf_state NOT IN ("", "T") AND wf_state IS NOT NULL',
         lambda df: (~df['wf_state'].isin(['', 'T'])) & df['wf_state'].notna()),

        ('SUP_BACS_NO_BANK', 10, 'Suppliers', 'Consistency', 'Critical', 
         'Payment method set to BACS but bank details are missing',
         'Ensures data integrity between the selected payment method and the required banking fields.',
         'Provide bank details in asuheader.', 'asuheader', None,
         'asuheader.pay_method = "BACS" AND (bank_account IS NULL OR clearing_code IS NULL)',
         lambda df: (df['pay_method'] == 'BACS') & (df['bank_account'].isna() | df['clearing_code'].isna())),

        ('SUP_INT_NO_IBAN', 10, 'Suppliers', 'Consistency', 'Critical', 
         'Payment method set to International but IBAN is missing',
         'Ensures data integrity for international suppliers; IBAN is mandatory for "INT" payment method.',
         'Provide asuheader.iban.', 'asuheader', None,
         'asuheader.pay_method = "INT" AND asuheader.iban IS NULL',
         lambda df: (df['pay_method'] == 'INT') & df['iban'].isna()),

        ('SUP_NAME_DUP', 10, 'Suppliers', 'Uniqueness', 'Medium', 
         'Duplicate supplier name exists within the same House',
         'Identifies potential duplicate supplier master records to prevent over-stating the vendor population.',
         'Consolidate records in asuheader.apar_name.', 'asuheader', None,
         'COUNT(*) OVER(PARTITION BY client, apar_name) > 1',
         lambda df: df.duplicated(subset=['house', 'apar_name'], keep=False)),

        ('SUP_VAT_DUP', 10, 'Suppliers', 'Uniqueness', 'High', 
         'Duplicate VAT registration number exists within the same House',
         'Uses VAT numbers as a unique identifier to detect duplicate vendor accounts across the ledger.',
         'Consolidate records in asuheader.vat_reg_no.', 'asuheader', None,
         'COUNT(*) OVER(PARTITION BY client, vat_reg_no) > 1',
         lambda df: df.duplicated(subset=['house', 'vat_reg_no'], keep=False) & df['vat_reg_no'].notna()),

        ('SUP_STALE', 10, 'Suppliers', 'Timeliness', 'Low', 
         'Stale record: Supplier has not been updated in over 3 years',
         'Assists in data cleansing by identifying inactive vendor master records for potential decommissioning.',
         'Review for archival in asuheader.', 'asuheader', None,
         'asuheader.last_update < TODAY - 3 years',
         lambda df: df['last_update'] < (today - pd.Timedelta(days=3*365))),

        ('SUP_SUNDRY', 10, 'Suppliers', 'Validity', 'Low', 
         'Record is a Sundry/One-time supplier',
         'Flags one-time use vendors to ensure they are excluded from the core migration master data.',
         'Verify asuheader.apar_once migration scope.', 'asuheader', None,
         'asuheader.apar_once = "Y"',
         lambda df: df['apar_once'] == 'Y'),


        # ======================================================================
        # --- AP OPEN TRANSACTIONS (asutrans) ---
        # ======================================================================

        ('AP_DUE_DATE_MISSING', 16, 'AP Invoices', 'Completeness', 'High', 
         'Open invoice is missing a due date',
         'Ensures all open liabilities have a due date for accurate cash flow and aging reporting.',
         'Populate asutrans.due_date.', 'asutrans', None,
         'asutrans.due_date IS NULL',
         lambda df: df['due_date'].isna()),

        ('AP_EXT_REF_MISSING', 16, 'AP Invoices', 'Completeness', 'Critical', 
         'Open invoice missing its external (supplier) reference',
         'Ensures every invoice can be reconciled against the physical supplier document via its reference.',
         'Populate asutrans.ext_inv_ref.', 'asutrans', None,
         'asutrans.ext_inv_ref IS NULL',
         lambda df: df['ext_inv_ref'].isna()),

        ('AP_AMOUNT_MISSING', 16, 'AP Invoices', 'Completeness', 'Critical', 
         'Open invoice is missing its original gross amount',
         'Fundamental check to ensure every financial transaction record carries a value.',
         'Populate asutrans.amount.', 'asutrans', None,
         'asutrans.amount IS NULL',
         lambda df: df['amount'].isna()),

        ('AP_PO_CONTRACT_MISSING', 16, 'AP Invoices', 'Completeness', 'Medium', 
         'Open invoice is not linked to either a PO or a Contract',
         'Verifies that invoices are correctly referenced to an upstream procurement object (PO/Contract).',
         'Populate asutrans.order_id or contract_id.', 'asutrans', None,
         'asutrans.order_id IS NULL AND asutrans.contract_id IS NULL',
         lambda df: df['order_id'].isna() & df['contract_id'].isna()),

        ('AP_FX_NO_RATE', 16, 'AP Invoices', 'Completeness', 'High', 
         'Foreign currency invoice missing its exchange rate to GBP',
         'Ensures non-GBP invoices have a conversion rate to maintain accurate base-currency reporting.',
         'Provide rate in asutrans.exch_rate.', 'asutrans', None,
         'asutrans.currency <> "GBP" AND asutrans.exch_rate IS NULL',
         lambda df: (df['currency'] != 'GBP') & df['exch_rate'].isna()),

        ('AP_CN_NO_REF', 16, 'AP Invoices', 'Completeness', 'Medium', 
         'Credit note missing its link to the original invoice',
         'Ensures traceability between credits and their original source invoices.',
         'Populate asutrans.orig_reference.', 'asutrans', None,
         'asutrans.voucher_type LIKE "%CREDIT%" AND asutrans.orig_reference IS NULL',
         lambda df: (df['voucher_type'].str.contains('CREDIT', case=False, na=False)) & df['orig_reference'].isna()),

        ('AP_NEG_INV', 16, 'AP Invoices', 'Validity', 'Medium', 
         'Negative amount found on a standard invoice voucher type',
         'Identifies bookkeeping errors where standard invoices carry negative values instead of being credit notes.',
         'Correct asutrans.voucher_type.', 'asutrans', None,
         'asutrans.amount < 0 AND asutrans.voucher_type NOT LIKE "%CREDIT%"',
         lambda df: (df['amount'] < 0) & (~df['voucher_type'].str.contains('CREDIT', case=False, na=False))),

        ('AP_FX_NO_CUR_AMT', 16, 'AP Invoices', 'Validity', 'High', 
         'Foreign currency invoice missing its transaction currency amount',
         'Ensures that for FX transactions, both the base and transaction currency amounts are populated.',
         'Populate asutrans.cur_amount.', 'asutrans', None,
         'asutrans.currency <> "GBP" AND asutrans.cur_amount IS NULL',
         lambda df: (df['currency'] != 'GBP') & df['cur_amount'].isna()),

        ('AP_REST_ZERO', 16, 'AP Invoices', 'Consistency', 'Medium', 
         'Outstanding balance is zero but the item is still flagged as OPEN',
         'Identifies "ghost" open items that have been fully paid but not technically closed in the source system.',
         'Close item in source system; asutrans.rest_amount = 0.', 'asutrans', None,
         'asutrans.rest_amount = 0',
         lambda df: df['rest_amount'] == 0),

        ('AP_REST_OVER_AMT', 16, 'AP Invoices', 'Consistency', 'High', 
         'Outstanding balance exceeds the original invoice amount',
         'Identifies data corruption where the remaining balance is higher than the original invoice total.',
         'Investigate asutrans.rest_amount vs asutrans.amount.', 'asutrans', None,
         'ABS(asutrans.rest_amount) > ABS(asutrans.amount) + 0.01',
         lambda df: df['rest_amount'].abs() > df['amount'].abs() + 0.01),

        ('AP_OVERDUE', 16, 'AP Invoices', 'Timeliness', 'Medium', 
         'Invoice is past its due date and remains unpaid',
         'Highlights overdue liabilities that require immediate payment attention.',
         'Review asutrans.due_date.', 'asutrans', None,
         'asutrans.due_date < TODAY',
         lambda df: df['due_date'] < today),

        ('AP_WF_STUCK', 16, 'AP Invoices', 'Consistency', 'High', 
         'Open invoice is stuck in an unapproved workflow state',
         'Identifies invoices that are blocked from payment due to incomplete workflow approvals.',
         'Complete asutrans.wf_state.', 'asutrans', None,
         'asutrans.wf_state NOT IN ("", "T") AND asutrans.wf_state IS NOT NULL',
         lambda df: (~df['wf_state'].isin(['', 'T'])) & df['wf_state'].notna()),

        ('AP_EXT_REF_DUP', 16, 'AP Invoices', 'Uniqueness', 'High', 
         'Duplicate external reference found for the same supplier',
         'Prevents duplicate payments by flagging multiple invoices with the same reference for one vendor.',
         'Resolve duplicate asutrans.ext_inv_ref.', 'asutrans', None,
         'COUNT(*) OVER(PARTITION BY asutrans.apar_id, asutrans.ext_inv_ref) > 1',
         lambda df: df.duplicated(subset=['apar_id', 'ext_inv_ref'], keep=False) & df['ext_inv_ref'].notna()),

        ('AP_NET_NEGATIVE_SUP', 16, 'AP Invoices', 'Consistency', 'Medium', 
         'Supplier has a net negative opening balance (unallocated credits)',
         'Flags suppliers where the total of open credits exceeds invoices, indicating unallocated payments.',
         'Review asutrans.rest_amount total by supplier.', 'asutrans', None,
         'SUM(asutrans.rest_amount) GROUP BY apar_id < 0',
         lambda df: df.groupby(['house', 'apar_id'])['rest_amount'].transform('sum') < -0.01),

        ('AP_ORPHANED_CREDITS', 16, 'AP Invoices', 'Consistency', 'Low', 
         'Credit note exists but its referenced original invoice is already closed',
         'Ensures that credit notes remain linked to active, open invoice liabilities.',
         'Review asutrans.orig_reference.', 'asutrans', None,
         'asutrans.voucher_type LIKE "%CREDIT%" AND asutrans.orig_reference NOT IN (SELECT voucher_no FROM asutrans)',
         lambda df: (df['voucher_type'].str.contains('CREDIT', case=False, na=False)) & (~df['orig_reference'].isin(df['voucher_no'])) & df['orig_reference'].notna()),

        ('AP_ORPHANED_TRANS', 16, 'AP Invoices', 'Referential Integrity', 'Critical', 
         'Open transaction references a Supplier ID that does not exist',
         'Critical check to ensure transaction-to-master data integrity for the sub-ledger migration.',
         'Create master record in asuheader.', 'asutrans', 'asuheader',
         'asutrans.apar_id NOT IN (SELECT apar_id FROM asuheader)',
         lambda df, frames: ~df['apar_id'].isin(frames.get('asuheader', pd.DataFrame())['apar_id'])),

        ('AP_TRANS_SUP_CLOSED', 16, 'AP Invoices', 'Referential Integrity', 'Critical', 
         'Open transaction exists against a CLOSED supplier',
         'Identifies liabilities sitting against vendors that have been decommissioned or marked as inactive.',
         'Review status of supplier in asuheader.', 'asutrans', 'asuheader',
         'asutrans.apar_id IN (SELECT apar_id FROM asuheader WHERE status = "C")',
         lambda df, frames: df['apar_id'].isin(frames.get('asuheader', pd.DataFrame())[frames.get('asuheader', pd.DataFrame())['status'] == 'C']['apar_id'])),


        # ======================================================================
        # --- AP HISTORY (asuhistr) ---
        # ======================================================================

        ('HIS_REST_NOT_ZERO', 18, 'AP History', 'Consistency', 'High', 
         'Historical (closed) item still carries a non-zero balance',
         'Verifies that items in the history table are truly closed and have a remaining balance of zero.',
         'Historical items in asuhistr must have rest_amount = 0.', 'asuhistr', None,
         'asuhistr.rest_amount <> 0',
         lambda df: df['rest_amount'] != 0),

        ('HIS_DATE_MISSING', 18, 'AP History', 'Completeness', 'Critical', 
         'Historical record missing its transaction date',
         'Ensures historical records have dates to allow for accurate trend analysis and statutory reporting.',
         'Populate asuhistr.trans_date.', 'asuhistr', None,
         'asuhistr.trans_date IS NULL',
         lambda df: df['trans_date'].isna()),

        ('HIS_CN_NO_REF', 18, 'AP History', 'Completeness', 'Medium', 
         'Historical credit note missing its original invoice reference',
         'Ensures historical data maintains the audit trail between credit notes and source invoices.',
         'Populate asuhistr.orig_reference.', 'asuhistr', None,
         'asuhistr.voucher_type LIKE "%CREDIT%" AND asuhistr.orig_reference IS NULL',
         lambda df: (df['voucher_type'].str.contains('CREDIT', case=False, na=False)) & df['orig_reference'].isna()),

        ('HIS_DUP', 18, 'AP History', 'Uniqueness', 'High', 
         'Duplicate voucher and sequence number found in history',
         'Identifies data corruption in the history table where transaction identifiers are duplicated.',
         'Data integrity error in asuhistr.', 'asuhistr', None,
         'COUNT(*) OVER(PARTITION BY client, voucher_no, sequence_no) > 1',
         lambda df: df.duplicated(subset=['house', 'voucher_no', 'sequence_no'], keep=False)),

        ('HIS_ORPHANED', 18, 'AP History', 'Referential Integrity', 'Medium', 
         'Historical record references a Supplier ID that does not exist',
         'Ensures historical transactions remain linked to a valid supplier master record.',
         'Check asuhistr.apar_id against asuheader.', 'asuhistr', 'asuheader',
         'asuhistr.apar_id NOT IN (SELECT apar_id FROM asuheader)',
         lambda df, frames: ~df['apar_id'].isin(frames.get('asuheader', pd.DataFrame())['apar_id'])),
    ]
    return checks
