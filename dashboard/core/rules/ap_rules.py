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
         'Finds active suppliers with no VAT registration number — required for UK tax compliance and HMRC reporting.',
         'Verify asuheader.vat_reg_no.', 'asuheader', None,
         'asuheader.vat_reg_no IS NULL WHERE status = "N"',
         lambda df: df['vat_reg_no'].isna()),
         
        ('SUP_COMP_REG_MISSING', 10, 'Suppliers', 'Completeness', 'Low',
         'Active supplier missing company registration number',
         'Flags active suppliers with no Companies House number — needed to verify the supplier legal entity status.',
         'Verify asuheader.comp_reg_no.', 'asuheader', None,
         'asuheader.comp_reg_no IS NULL WHERE status = "N"',
         lambda df: df['comp_reg_no'].isna()),

        ('SUP_TERMS_MISSING', 10, 'Suppliers', 'Completeness', 'High',
         'Active supplier missing payment terms',
         'Identifies suppliers with no payment terms, which means the system cannot automatically calculate invoice due dates.',
         'Assign asuheader.terms_id.', 'asuheader', None,
         'asuheader.terms_id IS NULL',
         lambda df: df['terms_id'].isna()),

        ('SUP_PAY_METHOD_MISSING', 10, 'Suppliers', 'Completeness', 'Critical',
         'Active supplier missing default payment method',
         'Flags suppliers with no payment method assigned — without DD or IN, the automated payment run cannot process settlements for this supplier.',
         'Assign asuheader.pay_method (DD/IN).', 'asuheader', None,
         'asuheader.pay_method IS NULL',
         lambda df: df['pay_method'].isna()),

        ('SUP_CURRENCY_MISSING', 10, 'Suppliers', 'Completeness', 'Critical',
         'Active supplier missing default currency',
         'Finds suppliers with no default currency — required for the system to assign the correct base currency when posting invoices.',
         'Assign asuheader.currency (GBP).', 'asuheader', None,
         'asuheader.currency IS NULL',
         lambda df: df['currency'].isna()),

        ('SUP_BANK_MISSING', 10, 'Suppliers', 'Completeness', 'Critical',
         'Active supplier missing bank account number',
         'Identifies active suppliers with no bank account number — payment cannot be made electronically without this.',
         'Obtain and populate asuheader.bank_account.', 'asuheader', None,
         'asuheader.bank_account IS NULL',
         lambda df: df['bank_account'].isna()),

        ('SUP_SORT_IBAN_MISSING', 10, 'Suppliers', 'Completeness', 'Critical',
         'Active supplier missing both Sort Code AND IBAN',
         'Flags suppliers that have neither a Sort Code nor an IBAN — at least one routing identifier is needed to make an electronic payment.',
         'Required routing in asuheader.clearing_code or iban.', 'asuheader', None,
         'asuheader.clearing_code IS NULL AND asuheader.iban IS NULL',
         lambda df: df['clearing_code'].isna() & df['iban'].isna()),

        ('SUP_SWIFT_MISSING', 10, 'Suppliers', 'Completeness', 'High',
         'Supplier has an IBAN but is missing a SWIFT/BIC code',
         'Finds suppliers with an IBAN but no SWIFT/BIC code — for international payments, both are required for cross-border routing.',
         'Required for international; populate asuheader.swift.', 'asuheader', None,
         'asuheader.iban IS NOT NULL AND asuheader.swift IS NULL',
         lambda df: df['swift'].isna() & df['iban'].notna()),

        ('SUP_VAT_FORMAT', 10, 'Suppliers', 'Validity', 'High',
         'VAT number format is invalid (Expected GB + 9 digits)',
         'Validates that VAT numbers match the HMRC format of GB followed by exactly 9 digits — incorrectly formatted numbers will fail tax authority validation.',
         'Correct asuheader.vat_reg_no.', 'asuheader', None,
         'asuheader.vat_reg_no NOT LIKE "GB_________" (9 digits)',
         lambda df: (~df['vat_reg_no'].str.match(r'^GB\d{9}$', na=False)) & df['vat_reg_no'].notna()),

        ('SUP_COMP_REG_FORMAT', 10, 'Suppliers', 'Validity', 'Medium',
         'Company registration format is invalid (Expected 8 digits)',
         'Checks that Companies House numbers are exactly 8 digits — the standard format for UK company registration numbers.',
         'Correct asuheader.comp_reg_no.', 'asuheader', None,
         'asuheader.comp_reg_no NOT LIKE "________" (8 digits)',
         lambda df: (~df['comp_reg_no'].str.match(r'^\d{8}$', na=False)) & df['comp_reg_no'].notna()),

        ('SUP_SORT_FORMAT', 10, 'Suppliers', 'Validity', 'High',
         'Bank sort code format is invalid (Expected XX-XX-XX or XXXXXX)',
         'Validates sort codes are in the standard XX-XX-XX hyphenated format or plain 6-digit format — other formats will be rejected by payment systems.',
         'Correct asuheader.clearing_code.', 'asuheader', None,
         'asuheader.clearing_code NOT LIKE "__-__-__" AND NOT LIKE "______" (6 digits)',
         lambda df: (~df['clearing_code'].str.match(r'^(\d{2}-\d{2}-\d{2}|\d{6})$', na=False)) & df['clearing_code'].notna()),

        ('SUP_BANK_FORMAT', 10, 'Suppliers', 'Validity', 'Critical',
         'Bank account format is invalid (Expected 8 digits)',
         'Checks that bank account numbers are exactly 8 digits — non-standard formats will be rejected during payment processing.',
         'Correct asuheader.bank_account.', 'asuheader', None,
         'asuheader.bank_account NOT LIKE "________" (8 digits)',
         lambda df: (~df['bank_account'].str.match(r'^\d{8}$', na=False)) & df['bank_account'].notna()),

        ('SUP_SWIFT_FORMAT', 10, 'Suppliers', 'Validity', 'High',
         'SWIFT/BIC format is invalid (Expected 8 or 11 chars)',
         'Validates SWIFT/BIC codes are 8 or 11 alphanumeric characters — the internationally recognised format for bank routing.',
         'Correct asuheader.swift.', 'asuheader', None,
         'asuheader.swift length NOT IN (8, 11) or contains invalid chars',
         lambda df: (~df['swift'].str.match(r'^[A-Z0-9]{8,11}$', na=False)) & df['swift'].notna()),

        ('SUP_EXPIRED_ACTIVE', 10, 'Suppliers', 'Consistency', 'Medium',
         'Supplier is active but has an expired/closed date populated',
         'Flags suppliers marked as active (status N) that also have an expiry date populated — these two fields are contradictory.',
         'Review status alignment in asuheader.', 'asuheader', None,
         'asuheader.status = "N" AND asuheader.expired_date IS NOT NULL',
         lambda df: df['expired_date'].notna() & (df['status'] == 'N')),

        ('SUP_WF_STUCK', 10, 'Suppliers', 'Consistency', 'Medium',
         'Supplier is currently stuck in an unapproved workflow state',
         'Identifies suppliers stuck in an incomplete approval workflow, meaning their master data changes have not been signed off.',
         'Complete asuheader.wf_state.', 'asuheader', None,
         'asuheader.wf_state NOT IN ("", "T") AND wf_state IS NOT NULL',
         lambda df: (~df['wf_state'].isin(['', 'T'])) & df['wf_state'].notna()),

        ('SUP_BACS_NO_BANK', 10, 'Suppliers', 'Consistency', 'Critical',
         'Payment method is domestic electronic but bank details are missing',
         'Finds suppliers set to a domestic payment method (DD/CH/FP/BB) but missing their bank account or sort code — the payment run will fail without these details.',
         'Provide bank details in asuheader.', 'asuheader', None,
         'asuheader.pay_method IN ("DD","CH","FP","BB") AND (bank_account IS NULL OR clearing_code IS NULL)',
         lambda df: (df['pay_method'].isin(['DD', 'CH', 'FP', 'BB'])) & (df['bank_account'].isna() | df['clearing_code'].isna())),

        ('SUP_INT_NO_IBAN', 10, 'Suppliers', 'Consistency', 'Critical',
         'Payment method is international but IBAN is missing',
         'Flags suppliers set to an international payment method (IN/EU/TF) with no IBAN — required for cross-border electronic payments.',
         'Provide asuheader.iban.', 'asuheader', None,
         'asuheader.pay_method IN ("IN","EU","TF") AND asuheader.iban IS NULL',
         lambda df: (df['pay_method'].isin(['IN', 'EU', 'TF'])) & df['iban'].isna()),

        ('SUP_NAME_DUP', 10, 'Suppliers', 'Uniqueness', 'Medium',
         'Duplicate supplier name exists within the same House',
         'Detects suppliers sharing the same name within a House — likely duplicates that could result in payments being split across multiple records.',
         'Consolidate records in asuheader.apar_name.', 'asuheader', None,
         'COUNT(*) OVER(PARTITION BY client, apar_name) > 1',
         lambda df: df.duplicated(subset=['house', 'apar_name'], keep=False)),

        ('SUP_VAT_DUP', 10, 'Suppliers', 'Uniqueness', 'High',
         'Duplicate VAT registration number exists within the same House',
         'Finds suppliers sharing the same VAT number within a House — since VAT numbers are unique to a legal entity, this indicates duplicate supplier accounts.',
         'Consolidate records in asuheader.vat_reg_no.', 'asuheader', None,
         'COUNT(*) OVER(PARTITION BY client, vat_reg_no) > 1',
         lambda df: df.duplicated(subset=['house', 'vat_reg_no'], keep=False) & df['vat_reg_no'].notna()),

        ('SUP_CLIENT_APAR_DUP', 10, 'Suppliers', 'Uniqueness', 'Critical',
         'Duplicate (client, apar_id) combination found in supplier master',
         'Flags rows where the same client and apar_id appear more than once in asuheader — since (client, apar_id) is the unique key, any duplicate indicates a data integrity error that must be resolved before migration.',
         'Investigate and remove duplicate rows in asuheader.', 'asuheader', None,
         'COUNT(*) OVER(PARTITION BY client, apar_id) > 1',
         lambda df: df.duplicated(subset=['client', 'apar_id'], keep=False)),

        # ======================================================================
        # --- CROSS-HOUSE UNIQUENESS (asuheader) ---
        # ======================================================================

        ('SUP_XHOUSE_VAT_DUP', 10, 'Suppliers', 'Uniqueness', 'High',
         'VAT registration number exists in both Houses',
         'Finds non-closed suppliers sharing a VAT registration number across both Houses — since a VAT number is unique to a legal entity, this indicates the same supplier is registered in both systems and may create duplicate records in the new ERP.',
         'Review asuheader.vat_reg_no across both Houses and consolidate or map to a single record.', 'asuheader', None,
         'vat_reg_no IN (SELECT vat_reg_no FROM asuheader GROUP BY vat_reg_no HAVING COUNT(DISTINCT house) > 1)',
         lambda df, frames: df['vat_reg_no'].isin(
             (lambda f:
                 f[f['vat_reg_no'].notna() & (f['status'] != 'C')]
                 .groupby('vat_reg_no')['house'].nunique()
                 .pipe(lambda s: s[s > 1].index)
             )(frames.get('asuheader', pd.DataFrame()))
         ) & df['vat_reg_no'].notna()),

        ('SUP_XHOUSE_COMP_REG_DUP', 10, 'Suppliers', 'Uniqueness', 'Medium',
         'Company registration number exists in both Houses',
         'Finds non-closed suppliers sharing a Companies House number across both Houses — a company registration number uniquely identifies a legal entity, so the same number in both Houses indicates the same supplier is held twice.',
         'Review asuheader.comp_reg_no across both Houses and consolidate or map to a single record.', 'asuheader', None,
         'comp_reg_no IN (SELECT comp_reg_no FROM asuheader GROUP BY comp_reg_no HAVING COUNT(DISTINCT house) > 1)',
         lambda df, frames: df['comp_reg_no'].isin(
             (lambda f:
                 f[f['comp_reg_no'].notna() & (f['status'] != 'C')]
                 .groupby('comp_reg_no')['house'].nunique()
                 .pipe(lambda s: s[s > 1].index)
             )(frames.get('asuheader', pd.DataFrame()))
         ) & df['comp_reg_no'].notna()),

        ('SUP_XHOUSE_IBAN_DUP', 10, 'Suppliers', 'Uniqueness', 'High',
         'IBAN exists in both Houses',
         'Finds non-closed suppliers sharing an IBAN across both Houses — an IBAN uniquely identifies a bank account, so the same IBAN appearing in both Houses strongly indicates the same payee is registered twice.',
         'Review asuheader.iban across both Houses and confirm whether a single master record is needed.', 'asuheader', None,
         'iban IN (SELECT iban FROM asuheader GROUP BY iban HAVING COUNT(DISTINCT house) > 1)',
         lambda df, frames: df['iban'].isin(
             (lambda f:
                 f[f['iban'].notna() & (f['status'] != 'C')]
                 .groupby('iban')['house'].nunique()
                 .pipe(lambda s: s[s > 1].index)
             )(frames.get('asuheader', pd.DataFrame()))
         ) & df['iban'].notna()),

        ('SUP_XHOUSE_BANK_DUP', 10, 'Suppliers', 'Uniqueness', 'Medium',
         'Bank account and sort code combination exists in both Houses',
         'Finds non-closed suppliers sharing the same bank account number and sort code across both Houses — the same payment destination appearing in both systems may indicate a duplicate supplier registration.',
         'Review asuheader.bank_account and clearing_code across both Houses.', 'asuheader', None,
         'bank_account||clearing_code IN (SELECT bank_account||clearing_code FROM asuheader GROUP BY bank_account, clearing_code HAVING COUNT(DISTINCT house) > 1)',
         lambda df, frames: (
             df['bank_account'].notna() & df['clearing_code'].notna() &
             (df['bank_account'] + '|' + df['clearing_code']).isin(
                 (lambda f:
                     (lambda fa:
                         fa.assign(_k=fa['bank_account'] + '|' + fa['clearing_code'])
                         .groupby('_k')['house'].nunique()
                         .pipe(lambda s: s[s > 1].index)
                     )(f[f['bank_account'].notna() & f['clearing_code'].notna() & (f['status'] != 'C')])
                 )(frames.get('asuheader', pd.DataFrame()))
             )
         )),

        ('SUP_XHOUSE_NAME_DUP', 10, 'Suppliers', 'Uniqueness', 'Low',
         'Supplier name (case-insensitive) exists in both Houses',
         'Finds non-closed suppliers sharing the same name across both Houses — an identical name in both systems may indicate a duplicate registration, though common payees (e.g. HMRC) will appear legitimately in both.',
         'Review asuheader.apar_name matches across Houses and confirm whether records relate to the same legal entity.', 'asuheader', None,
         'UPPER(apar_name) IN (SELECT UPPER(apar_name) FROM asuheader GROUP BY UPPER(apar_name) HAVING COUNT(DISTINCT house) > 1)',
         lambda df, frames: df['apar_name'].notna() & df['apar_name'].str.strip().str.upper().isin(
             (lambda f:
                 (lambda fa:
                     fa.assign(_n=fa['apar_name'].str.strip().str.upper())
                     .groupby('_n')['house'].nunique()
                     .pipe(lambda s: s[s > 1].index)
                 )(f[f['apar_name'].notna() & (f['status'] != 'C')])
             )(frames.get('asuheader', pd.DataFrame()))
         )),

        ('SUP_STALE', 10, 'Suppliers', 'Timeliness', 'Low',
         'Stale record: Supplier has not been updated in over 3 years',
         'Surfaces supplier records that have not been updated in over 3 years — candidates for review and potential decommissioning.',
         'Review for archival in asuheader.', 'asuheader', None,
         'asuheader.last_update < TODAY - 3 years',
         lambda df: df['last_update'] < (today - pd.Timedelta(days=3*365))),

        ('SUP_SUNDRY', 10, 'Suppliers', 'Validity', 'Low',
         'Record is a Sundry/One-time supplier',
         'Flags one-time (sundry) supplier records — these are typically excluded from a core master data migration.',
         'Verify asuheader.apar_once migration scope.', 'asuheader', None,
         'asuheader.apar_once = "Y"',
         lambda df: df['apar_once'] == 'Y'),


        # ======================================================================
        # --- AP OPEN TRANSACTIONS (asutrans) ---
        # ======================================================================

        ('AP_DUE_DATE_MISSING', 16, 'AP Invoices', 'Completeness', 'High',
         'Open invoice is missing a due date',
         'Finds open invoices with no due date — without this, the system cannot produce aging reports or flag overdue liabilities.',
         'Populate asutrans.due_date.', 'asutrans', None,
         'asutrans.due_date IS NULL',
         lambda df: df['due_date'].isna()),

        ('AP_EXT_REF_MISSING', 16, 'AP Invoices', 'Completeness', 'Critical',
         'Open invoice missing its external (supplier) reference',
         'Flags invoices with no external supplier reference — without this, the invoice cannot be matched back to the physical document.',
         'Populate asutrans.ext_inv_ref.', 'asutrans', None,
         'asutrans.ext_inv_ref IS NULL',
         lambda df: df['ext_inv_ref'].isna()),

        ('AP_AMOUNT_MISSING', 16, 'AP Invoices', 'Completeness', 'Critical',
         'Open invoice is missing its original gross amount',
         'Identifies invoices with no gross amount — a financial record with no value is meaningless and will cause processing failures.',
         'Populate asutrans.amount.', 'asutrans', None,
         'asutrans.amount IS NULL',
         lambda df: df['amount'].isna()),

        ('AP_PO_CONTRACT_MISSING', 16, 'AP Invoices', 'Completeness', 'Medium',
         'Open invoice is not linked to either a PO or a Contract',
         'Finds invoices not linked to a Purchase Order or Contract — suggests the invoice arrived outside the procurement process.',
         'Populate asutrans.order_id or contract_id.', 'asutrans', None,
         'asutrans.order_id IS NULL AND asutrans.contract_id IS NULL',
         lambda df: df['order_id'].isna() & df['contract_id'].isna()),

        ('AP_FX_NO_RATE', 16, 'AP Invoices', 'Completeness', 'High',
         'Foreign currency invoice missing its exchange rate to GBP',
         'Flags foreign currency invoices with no exchange rate to GBP — the system cannot convert the value for base currency reporting.',
         'Provide rate in asutrans.exch_rate.', 'asutrans', None,
         'asutrans.currency <> "GBP" AND asutrans.exch_rate IS NULL',
         lambda df: (df['currency'] != 'GBP') & df['exch_rate'].isna()),

        ('AP_CN_NO_REF', 16, 'AP Invoices', 'Completeness', 'Medium',
         'Credit note missing its link to the original invoice',
         'Finds credit notes with no reference back to the original invoice — breaks the audit trail between the credit and the charge it is offsetting.',
         'Populate asutrans.orig_reference.', 'asutrans', None,
         'asutrans.voucher_type LIKE "%CREDIT%" AND asutrans.orig_reference IS NULL',
         lambda df: (df['voucher_type'] == 'CN') & df['orig_reference'].isna()),

        ('AP_NEG_INV', 16, 'AP Invoices', 'Validity', 'Medium',
         'Negative amount found on a standard invoice voucher type',
         'Identifies standard invoice vouchers with a negative amount — negative values should be credit notes, not invoices.',
         'Correct asutrans.voucher_type.', 'asutrans', None,
         'asutrans.amount < 0 AND asutrans.voucher_type NOT LIKE "%CREDIT%"',
         lambda df: (df['amount'] < 0) & (df['voucher_type'] != 'CN')),

        ('AP_FX_NO_CUR_AMT', 16, 'AP Invoices', 'Validity', 'High',
         'Foreign currency invoice missing its transaction currency amount',
         'Flags FX invoices missing the original transaction currency amount — both the base and foreign currency amounts are needed for revaluation.',
         'Populate asutrans.cur_amount.', 'asutrans', None,
         'asutrans.currency <> "GBP" AND asutrans.cur_amount IS NULL',
         lambda df: (df['currency'] != 'GBP') & df['cur_amount'].isna()),

        ('AP_REST_ZERO', 16, 'AP Invoices', 'Consistency', 'Medium',
         'Outstanding balance is zero but the item is still flagged as OPEN',
         'Finds open items with a zero remaining balance — these have effectively been paid and should be closed in the source system.',
         'Close item in source system; asutrans.rest_amount = 0.', 'asutrans', None,
         'asutrans.rest_amount = 0',
         lambda df: df['rest_amount'] == 0),

        ('AP_REST_OVER_AMT', 16, 'AP Invoices', 'Consistency', 'High',
         'Outstanding balance exceeds the original invoice amount',
         'Flags invoices where the outstanding balance exceeds the original amount — mathematically impossible and indicates data corruption.',
         'Investigate asutrans.rest_amount vs asutrans.amount.', 'asutrans', None,
         'ABS(asutrans.rest_amount) > ABS(asutrans.amount) + 0.01',
         lambda df: df['rest_amount'].abs() > df['amount'].abs() + 0.01),

        ('AP_OVERDUE', 16, 'AP Invoices', 'Timeliness', 'Medium',
         'Invoice is past its due date and remains unpaid',
         'Identifies invoices that have passed their due date without being paid — highlights immediate cash flow priorities.',
         'Review asutrans.due_date.', 'asutrans', None,
         'asutrans.due_date < TODAY',
         lambda df: df['due_date'] < today),

        ('AP_WF_STUCK', 16, 'AP Invoices', 'Consistency', 'High',
         'Open invoice is stuck in an unapproved workflow state',
         'Finds invoices blocked in an incomplete approval workflow — these cannot be paid until the workflow is resolved.',
         'Complete asutrans.wf_state.', 'asutrans', None,
         'asutrans.wf_state NOT IN ("", "T") AND asutrans.wf_state IS NOT NULL',
         lambda df: (~df['wf_state'].isin(['', 'T'])) & df['wf_state'].notna()),

        ('AP_TRANS_KEY_DUP', 16, 'AP Invoices', 'Uniqueness', 'Critical',
         'Duplicate (client, apar_id, voucher_no, sequence_no) found in open transactions',
         'Flags rows where the confirmed unique key appears more than once in asutrans — any duplicate indicates a data integrity error that must be resolved before migration.',
         'Investigate and remove duplicate rows in asutrans.', 'asutrans', None,
         'COUNT(*) OVER(PARTITION BY client, apar_id, voucher_no, sequence_no) > 1',
         lambda df: df.duplicated(subset=['client', 'apar_id', 'voucher_no', 'sequence_no'], keep=False)),

        ('AP_EXT_REF_DUP', 16, 'AP Invoices', 'Uniqueness', 'High',
         'Duplicate external reference found for the same supplier',
         'Detects the same supplier reference number appearing on multiple invoices — a strong indicator of a duplicate payment risk.',
         'Resolve duplicate asutrans.ext_inv_ref.', 'asutrans', None,
         'COUNT(*) OVER(PARTITION BY asutrans.apar_id, asutrans.ext_inv_ref) > 1',
         lambda df: df.duplicated(subset=['apar_id', 'ext_inv_ref'], keep=False) & df['ext_inv_ref'].notna()),

        ('AP_NET_NEGATIVE_SUP', 16, 'AP Invoices', 'Consistency', 'Medium',
         'Supplier has a net negative opening balance (unallocated credits)',
         'Flags suppliers whose total open balance is negative, meaning credits exceed invoices — suggests unallocated payments or credits.',
         'Review asutrans.rest_amount total by supplier.', 'asutrans', None,
         'SUM(asutrans.rest_amount) GROUP BY apar_id < 0',
         lambda df: df.groupby(['house', 'apar_id'])['rest_amount'].transform('sum') < -0.01),

        ('AP_ORPHANED_CREDITS', 16, 'AP Invoices', 'Consistency', 'Low',
         'Credit note exists but its referenced original invoice is already closed',
         'Finds credit notes linked to an invoice reference that no longer exists as an open item — the credit is floating with nothing to offset.',
         'Review asutrans.orig_reference.', 'asutrans', None,
         'asutrans.voucher_type LIKE "%CREDIT%" AND asutrans.orig_reference NOT IN (SELECT voucher_no FROM asutrans)',
         lambda df: (df['voucher_type'] == 'CN') & (~df['orig_reference'].isin(df['voucher_no'])) & df['orig_reference'].notna()),

        ('AP_ORPHANED_TRANS', 16, 'AP Invoices', 'Referential Integrity', 'Critical',
         'Open transaction references a Supplier ID that does not exist',
         'Identifies open invoices referencing a supplier ID that does not exist in the supplier master — these transactions have no valid payee.',
         'Create master record in asuheader.', 'asutrans', 'asuheader',
         'asutrans.apar_id NOT IN (SELECT apar_id FROM asuheader)',
         lambda df, frames: ~df['apar_id'].isin(frames.get('asuheader', pd.DataFrame())['apar_id'])),

        ('AP_TRANS_SUP_CLOSED', 16, 'AP Invoices', 'Referential Integrity', 'Critical',
         'Open transaction exists against a CLOSED supplier',
         'Finds open invoices sitting against a supplier that has been deactivated — liabilities cannot be processed against a closed vendor.',
         'Review status of supplier in asuheader.', 'asutrans', 'asuheader',
         'asutrans.apar_id IN (SELECT apar_id FROM asuheader WHERE status = "C")',
         lambda df, frames: df['apar_id'].isin(frames.get('asuheader', pd.DataFrame())[frames.get('asuheader', pd.DataFrame())['status'] == 'C']['apar_id'])),


        # ======================================================================
        # --- AP HISTORY (asuhistr) ---
        # ======================================================================

        ('HIS_REST_NOT_ZERO', 18, 'AP History', 'Consistency', 'High',
         'Historical (closed) item still carries a non-zero balance',
         'Checks that all historical (closed) items have a zero remaining balance — a non-zero amount means the item was not fully settled before being closed.',
         'Historical items in asuhistr must have rest_amount = 0.', 'asuhistr', None,
         'asuhistr.rest_amount <> 0',
         lambda df: df['rest_amount'] != 0),

        ('HIS_DATE_MISSING', 18, 'AP History', 'Completeness', 'Critical',
         'Historical record missing its transaction date',
         'Finds historical transactions with no date — dates are essential for statutory reporting and trend analysis.',
         'Populate asuhistr.trans_date.', 'asuhistr', None,
         'asuhistr.trans_date IS NULL',
         lambda df: df['trans_date'].isna()),

        ('HIS_CN_NO_REF', 18, 'AP History', 'Completeness', 'Medium',
         'Historical credit note missing its original invoice reference',
         'Flags historical credit notes with no link to the original invoice — without this, the audit trail between the credit and the original charge is broken.',
         'Populate asuhistr.orig_reference.', 'asuhistr', None,
         'asuhistr.voucher_type LIKE "%CREDIT%" AND asuhistr.orig_reference IS NULL',
         lambda df: (df['voucher_type'] == 'CN') & df['orig_reference'].isna()),

        ('HIS_DUP', 18, 'AP History', 'Uniqueness', 'High',
         'Duplicate voucher and sequence number found in history',
         'Detects duplicate voucher and sequence number combinations in the history table — indicates data integrity issues in the closed ledger.',
         'Data integrity error in asuhistr.', 'asuhistr', None,
         'COUNT(*) OVER(PARTITION BY client, voucher_no, sequence_no) > 1',
         lambda df: df.duplicated(subset=['house', 'voucher_no', 'sequence_no'], keep=False)),

        ('HIS_ORPHANED', 18, 'AP History', 'Referential Integrity', 'Medium',
         'Historical record references a Supplier ID that does not exist',
         'Finds historical transactions referencing a supplier that no longer exists in the master — breaks the link between historical activity and the vendor record.',
         'Check asuhistr.apar_id against asuheader.', 'asuhistr', 'asuheader',
         'asuhistr.apar_id NOT IN (SELECT apar_id FROM asuheader)',
         lambda df, frames: ~df['apar_id'].isin(frames.get('asuheader', pd.DataFrame())['apar_id'])),
    ]
    return checks
