import pandas as pd
from datetime import date

def get_ar_checks():
    """Returns a list of Customer and AR DQ check definitions."""
    today = pd.Timestamp(date.today())
    
    checks = [
        # ======================================================================
        # --- CUSTOMER MASTER (acuheader) ---
        # ======================================================================
        
        ('CUS_VAT_MISSING', 11, 'Customers', 'Completeness', 'Medium', 
         'Active customer missing VAT registration number',
         'Verifies presence of VAT numbers for active customers.',
         'Verify acuheader.vat_reg_no.', 'acuheader', None,
         'acuheader.vat_reg_no IS NULL WHERE status = "N"',
         lambda df: df['vat_reg_no'].isna()),
         
        ('CUS_COMP_REG_MISSING', 11, 'Customers', 'Completeness', 'Low', 
         'Active customer missing company registration number',
         'Checks for the presence of Companies House registration numbers.',
         'Verify acuheader.comp_reg_no.', 'acuheader', None,
         'acuheader.comp_reg_no IS NULL WHERE status = "N"',
         lambda df: df['comp_reg_no'].isna()),

        ('CUS_TERMS_MISSING', 11, 'Customers', 'Completeness', 'High', 
         'Active customer missing payment terms',
         'Ensures all active customers have payment terms defined.',
         'Assign acuheader.terms_id.', 'acuheader', None,
         'acuheader.terms_id IS NULL',
         lambda df: df['terms_id'].isna()),

        ('CUS_PAY_METHOD_MISSING', 11, 'Customers', 'Completeness', 'Critical', 
         'Active customer missing default payment method',
         'Verifies that a payment method is assigned.',
         'Assign acuheader.pay_method.', 'acuheader', None,
         'acuheader.pay_method IS NULL',
         lambda df: df['pay_method'].isna()),

        ('CUS_CURRENCY_MISSING', 11, 'Customers', 'Completeness', 'Critical', 
         'Active customer missing default currency',
         'Ensures all active customers have a default currency.',
         'Assign acuheader.currency.', 'acuheader', None,
         'acuheader.currency IS NULL',
         lambda df: df['currency'].isna()),

        ('CUS_CREDIT_LIMIT_MISSING', 11, 'Customers', 'Completeness', 'Medium',
         'Active customer missing credit limit',
         'Checks if a credit limit is defined for active customers.',
         'Populate acuheader.credit_limit.', 'acuheader', None,
         'acuheader.credit_limit IS NULL',
         lambda df: df['credit_limit'].isna()),

        ('CUS_BANK_MISSING', 11, 'Customers', 'Consistency', 'Critical', 
         'Payment method indicates Direct Debit but bank details missing',
         'Direct Debit requires bank details.',
         'Obtain and populate acuheader.bank_account, clearing_code, or iban.', 'acuheader', None,
         'acuheader.pay_method = "DD" AND bank_account IS NULL AND iban IS NULL',
         lambda df: (df['pay_method'] == 'DD') & df['bank_account'].isna() & df['iban'].isna()),

        ('CUS_VAT_FORMAT', 11, 'Customers', 'Validity', 'High', 
         'VAT number format is invalid',
         'Validates VAT numbers.',
         'Correct acuheader.vat_reg_no.', 'acuheader', None,
         'acuheader.vat_reg_no NOT LIKE "GB_________" (9 digits)',
         lambda df: (~df['vat_reg_no'].str.match(r'^GB\d{9}$', na=False)) & df['vat_reg_no'].notna()),

        ('CUS_COMP_REG_FORMAT', 11, 'Customers', 'Validity', 'Medium', 
         'Company registration format is invalid',
         'Validates that Company House numbers are exactly 8 digits long.',
         'Correct acuheader.comp_reg_no.', 'acuheader', None,
         'acuheader.comp_reg_no NOT LIKE "________" (8 digits)',
         lambda df: (~df['comp_reg_no'].str.match(r'^\d{8}$', na=False)) & df['comp_reg_no'].notna()),

        ('CUS_NAME_DUP', 11, 'Customers', 'Uniqueness', 'Medium', 
         'Duplicate customer name exists within the same House',
         'Identifies potential duplicate customer master records.',
         'Consolidate records in acuheader.apar_name.', 'acuheader', None,
         'COUNT(*) OVER(PARTITION BY client, apar_name) > 1',
         lambda df: df.duplicated(subset=['house', 'apar_name'], keep=False)),

        ('CUS_VAT_DUP', 11, 'Customers', 'Uniqueness', 'High', 
         'Duplicate VAT registration number exists within the same House',
         'Uses VAT numbers as a unique identifier to detect duplicate customer accounts.',
         'Consolidate records in acuheader.vat_reg_no.', 'acuheader', None,
         'COUNT(*) OVER(PARTITION BY client, vat_reg_no) > 1',
         lambda df: df.duplicated(subset=['house', 'vat_reg_no'], keep=False) & df['vat_reg_no'].notna()),

        # ======================================================================
        # --- AR OPEN TRANSACTIONS (acutrans) ---
        # ======================================================================

        ('AR_DUE_DATE_MISSING', 17, 'AR Invoices', 'Completeness', 'High', 
         'Open AR invoice is missing a due date',
         'Ensures all open receivables have a due date for accurate aging reporting.',
         'Populate acutrans.due_date.', 'acutrans', None,
         'acutrans.due_date IS NULL',
         lambda df: df['due_date'].isna()),

        ('AR_EXT_REF_MISSING', 17, 'AR Invoices', 'Completeness', 'Critical', 
         'Open AR invoice missing external reference',
         'Ensures every invoice has a reference.',
         'Populate acutrans.ext_inv_ref.', 'acutrans', None,
         'acutrans.ext_inv_ref IS NULL',
         lambda df: df['ext_inv_ref'].isna()),

        ('AR_AMOUNT_MISSING', 17, 'AR Invoices', 'Completeness', 'Critical', 
         'Open AR invoice is missing its original gross amount',
         'Fundamental check to ensure every financial transaction record carries a value.',
         'Populate acutrans.amount.', 'acutrans', None,
         'acutrans.amount IS NULL',
         lambda df: df['amount'].isna()),

        ('AR_NEG_INV', 17, 'AR Invoices', 'Validity', 'Medium', 
         'Negative amount found on a standard AR invoice voucher type',
         'Identifies bookkeeping errors where standard invoices carry negative values instead of being credit notes.',
         'Correct acutrans.voucher_type.', 'acutrans', None,
         'acutrans.amount < 0 AND acutrans.voucher_type NOT LIKE "%CREDIT%"',
         lambda df: (df['amount'] < 0) & (~df['voucher_type'].str.contains('CREDIT', case=False, na=False))),

        ('AR_REST_ZERO', 17, 'AR Invoices', 'Consistency', 'Medium', 
         'Outstanding balance is zero but the item is still flagged as OPEN',
         'Identifies "ghost" open items that have been fully paid but not technically closed.',
         'Close item in source system; acutrans.rest_amount = 0.', 'acutrans', None,
         'acutrans.rest_amount = 0',
         lambda df: df['rest_amount'] == 0),

        ('AR_REST_OVER_AMT', 17, 'AR Invoices', 'Consistency', 'High', 
         'Outstanding balance exceeds the original invoice amount',
         'Identifies data corruption where the remaining balance is higher than the original invoice total.',
         'Investigate acutrans.rest_amount vs acutrans.amount.', 'acutrans', None,
         'ABS(acutrans.rest_amount) > ABS(acutrans.amount) + 0.01',
         lambda df: df['rest_amount'].abs() > df['amount'].abs() + 0.01),

        ('AR_OVERDUE', 17, 'AR Invoices', 'Timeliness', 'Medium', 
         'Invoice is past its due date and remains unpaid',
         'Highlights overdue receivables.',
         'Review acutrans.due_date.', 'acutrans', None,
         'acutrans.due_date < TODAY',
         lambda df: df['due_date'] < pd.Timestamp(date.today())),

        ('AR_WF_STUCK', 17, 'AR Invoices', 'Consistency', 'High', 
         'Open invoice is stuck in an unapproved workflow state',
         'Identifies invoices that are blocked from processing due to incomplete workflow approvals.',
         'Complete acutrans.wf_state.', 'acutrans', None,
         'acutrans.wf_state NOT IN ("", "T") AND acutrans.wf_state IS NOT NULL',
         lambda df: (~df['wf_state'].isin(['', 'T'])) & df['wf_state'].notna()),

        ('AR_ORPHANED_TRANS', 17, 'AR Invoices', 'Referential Integrity', 'Critical', 
         'Open transaction references a Customer ID that does not exist',
         'Critical check to ensure transaction-to-master data integrity.',
         'Create master record in acuheader.', 'acutrans', 'acuheader',
         'acutrans.apar_id NOT IN (SELECT apar_id FROM acuheader)',
         lambda df, frames: ~df['apar_id'].isin(frames.get('acuheader', pd.DataFrame())['apar_id']) if 'acuheader' in frames else pd.Series([False]*len(df))),

        ('AR_TRANS_CUS_CLOSED', 17, 'AR Invoices', 'Referential Integrity', 'Critical', 
         'Open transaction exists against a CLOSED customer',
         'Identifies receivables sitting against customers that have been decommissioned.',
         'Review status of customer in acuheader.', 'acutrans', 'acuheader',
         'acutrans.apar_id IN (SELECT apar_id FROM acuheader WHERE status = "C")',
         lambda df, frames: df['apar_id'].isin(frames.get('acuheader', pd.DataFrame())[frames.get('acuheader', pd.DataFrame())['status'] == 'C']['apar_id']) if 'acuheader' in frames else pd.Series([False]*len(df))),

        # ======================================================================
        # --- AR HISTORY (acuhistr) ---
        # ======================================================================

        ('AR_HIS_REST_NOT_ZERO', 19, 'AR History', 'Consistency', 'High', 
         'Historical (closed) item still carries a non-zero balance',
         'Verifies that items in the history table are truly closed.',
         'Historical items in acuhistr must have rest_amount = 0.', 'acuhistr', None,
         'acuhistr.rest_amount <> 0',
         lambda df: df['rest_amount'] != 0),

        ('AR_HIS_DATE_MISSING', 19, 'AR History', 'Completeness', 'Critical', 
         'Historical record missing its transaction date',
         'Ensures historical records have dates to allow for accurate trend analysis.',
         'Populate acuhistr.trans_date.', 'acuhistr', None,
         'acuhistr.trans_date IS NULL',
         lambda df: df['trans_date'].isna()),
    ]
    return checks
