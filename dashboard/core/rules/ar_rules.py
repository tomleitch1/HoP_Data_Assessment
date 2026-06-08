import pandas as pd
from datetime import date

# AR credit note / reversal types (Agresso picklist — same codes as AP module)
# Confirm with AR team if any AR-specific codes exist before amending.
_CREDIT_NOTE_TYPES  = ['CN', 'IC', 'IN', 'RC']
_REVERSAL_TYPES     = ['IR', 'PR', 'RV']
_CREDIT_OR_REVERSAL = _CREDIT_NOTE_TYPES + _REVERSAL_TYPES

def get_ar_checks():
    """Returns a list of Customer and AR DQ check definitions."""
    today = pd.Timestamp(date.today())

    checks = [
        # ======================================================================
        # --- CUSTOMER MASTER (acuheader) ---
        # ======================================================================

        # ── Completeness ──────────────────────────────────────────────────────

        ('CUS_TERMS_MISSING', 11, 'Customers', 'Completeness', 'High',
         'Active customer missing payment terms',
         'Payment terms must be assigned to every active customer. The system uses this field to calculate invoice due dates and drive the AR aging report. A customer without terms will cause incorrect aging and cannot generate accurate debtor reports.',
         'Assign acuheader.terms_id.', 'acuheader', None,
         'acuheader.terms_id IS NULL WHERE status != "C"',
         lambda df: df['terms_id'].isna()),

        ('CUS_PAY_METHOD_MISSING', 11, 'Customers', 'Completeness', 'Critical',
         'Active customer missing default payment method',
         'Every active customer must have a default payment method assigned. The collection process relies on this field to determine how receipts will be applied. A customer without a payment method cannot be included in collection runs.',
         'Assign acuheader.pay_method.', 'acuheader', None,
         'acuheader.pay_method IS NULL WHERE status != "C"',
         lambda df: df['pay_method'].isna()),

        ('CUS_CURRENCY_MISSING', 11, 'Customers', 'Completeness', 'Critical',
         'Active customer missing default currency',
         'Every active customer must have a default currency set, typically GBP. The system uses this to denominate invoices correctly. A customer without a currency will cause invoice entry to fail in the new system.',
         'Assign acuheader.currency (GBP).', 'acuheader', None,
         'acuheader.currency IS NULL WHERE status != "C"',
         lambda df: df['currency'].isna()),

        ('CUS_CREDIT_LIMIT_MISSING', 11, 'Customers', 'Completeness', 'Medium',
         'Active customer has no credit limit configured',
         'Every active customer should have a credit limit defined. Without one the system cannot enforce credit controls. A customer with a null credit limit will bypass all credit checking at invoice entry in the new ERP.',
         'Populate acuheader.credit_limit.', 'acuheader', None,
         'acuheader.credit_limit IS NULL WHERE status != "C"',
         lambda df: df['credit_limit'].isna()),

        ('CUS_SWIFT_MISSING', 11, 'Customers', 'Completeness', 'Medium',
         'Customer has an IBAN but is missing a SWIFT/BIC code',
         'Customers with an IBAN must also have a SWIFT/BIC code populated. International payment systems require both fields to route cross-border receipts correctly. An IBAN without a SWIFT code will cause international collection instructions to be rejected.',
         'Populate acuheader.swift.', 'acuheader', None,
         'acuheader.iban IS NOT NULL AND acuheader.swift IS NULL',
         lambda df: df['iban'].notna() & df['swift'].isna()),

        # ── Validity ──────────────────────────────────────────────────────────

        ('CUS_SORT_FORMAT', 11, 'Customers', 'Validity', 'High',
         'Bank sort code format is invalid (Expected XX-XX-XX or XXXXXX)',
         'Bank sort codes must be in either the XX-XX-XX hyphenated format or plain 6-digit format. Sort codes in any other format will be rejected by collection processing systems.',
         'Correct acuheader.clearing_code.', 'acuheader', None,
         'acuheader.clearing_code NOT LIKE "__-__-__" AND NOT LIKE "______" (6 digits)',
         lambda df: (
             df['clearing_code'].notna() &
             ~df['clearing_code'].str.match(r'^(\d{2}-\d{2}-\d{2}|\d{6})$', na=False) &
             ~('0' + df['clearing_code'].fillna('')).str.match(r'^(\d{2}-\d{2}-\d{2}|\d{6})$', na=False)
         )),

        ('CUS_BANK_FORMAT', 11, 'Customers', 'Validity', 'High',
         'Bank account format is invalid (More than 8 digits, or contains non-numeric characters)',
         'Bank account numbers must contain only digits and be no longer than 8 digits. Values exceeding 8 digits or containing non-numeric characters will be rejected during collection processing.',
         'Correct acuheader.bank_account.', 'acuheader', None,
         'acuheader.bank_account containing non-digits OR length > 8',
         lambda df: df['bank_account'].notna() & ~df['bank_account'].str.match(r'^\d{1,8}$', na=False)),

        ('CUS_SWIFT_FORMAT', 11, 'Customers', 'Validity', 'High',
         'SWIFT/BIC format is invalid (Expected 8 or 11 chars)',
         'SWIFT/BIC codes must be either 8 or 11 alphanumeric characters in line with the internationally recognised standard. Codes that do not match this format will be rejected by international payment systems.',
         'Correct acuheader.swift.', 'acuheader', None,
         'acuheader.swift length NOT IN (8, 11) or contains invalid chars',
         lambda df: (~df['swift'].str.match(r'^[A-Z0-9]{8,11}$', na=False)) & df['swift'].notna()),

        # ── Consistency ───────────────────────────────────────────────────────

        ('CUS_BANK_MISSING', 11, 'Customers', 'Consistency', 'Critical',
         'Payment method indicates Direct Debit but bank details are missing',
         'Customers set to Direct Debit must have both a bank account number and a sort code populated. A DD collection cannot be initiated without these details. Any outstanding balance against this customer would need to be collected manually.',
         'Obtain and populate acuheader.bank_account and clearing_code.', 'acuheader', None,
         'acuheader.pay_method = "DD" AND (bank_account IS NULL OR clearing_code IS NULL)',
         lambda df: (df['pay_method'] == 'DD') & (df['bank_account'].isna() | df['clearing_code'].isna())),

        ('CUS_EXPIRED_ACTIVE', 11, 'Customers', 'Consistency', 'Medium',
         'Customer has an expiry date set but is still marked as active',
         'A customer with an expired_date populated but a status of N is in a contradictory state — it has been end-dated but not formally closed. These records must be resolved before migration to avoid creating customers that are active but should not receive new invoices.',
         'Set status to C or clear expired_date in acuheader.', 'acuheader', None,
         'acuheader.expired_date IS NOT NULL AND acuheader.status = "N"',
         lambda df: df['expired_date'].notna() & (df['status'] == 'N')),

        ('CUS_COLLECT_ACTIVE', 11, 'Customers', 'Consistency', 'High',
         'Customer has an active debt collection case',
         'Customers with an active collection flag represent outstanding debts currently with a collection agency or under formal collection proceedings. These must be reviewed before migration to determine whether the debt should be migrated or written off.',
         'Review acuheader.collect_flag and resolve collection case before migration.', 'acuheader', None,
         'acuheader.collect_flag = 1',
         lambda df: df['collect_flag'].notna() & (pd.to_numeric(df['collect_flag'], errors='coerce') == 1)),

        # ── Uniqueness ────────────────────────────────────────────────────────

        ('CUS_NAME_DUP', 11, 'Customers', 'Uniqueness', 'Medium',
         'Duplicate customer name exists within the same House',
         'Each customer name should be unique within a House. Duplicate names indicate the same debtor may have been registered more than once, which can split receivables across multiple records and complicate reconciliation.',
         'Consolidate records in acuheader.apar_name.', 'acuheader', None,
         'COUNT(*) OVER(PARTITION BY house, apar_name) > 1',
         lambda df: df.duplicated(subset=['house', 'apar_name'], keep=False) & (df['apar_name'].str.strip().str.len() > 1)),

        ('CUS_NAME_DUP_ANY', 11, 'Customers', 'Uniqueness', 'Low',
         'Customer name appears more than once within the same House (any address)',
         'Customer names appear more than once within the same House. Records sharing a name may be legitimate separate entities but should be reviewed to confirm each is a distinct legal entity and not an accidental duplicate.',
         'Review acuheader.apar_name for same-name records and confirm each is a distinct legal entity.', 'acuheader', None,
         'COUNT(*) OVER(PARTITION BY house, UPPER(apar_name)) > 1',
         lambda df: df.duplicated(subset=['house', 'apar_name'], keep=False) & (df['apar_name'].str.strip().str.len() > 1)),

        ('CUS_BANK_SORT_DUP', 11, 'Customers', 'Uniqueness', 'High',
         'Duplicate bank account and sort code combination exists within the same House',
         'The combination of bank account number and sort code should identify a unique collection destination within a House. The same bank details on multiple customer records means collections could be applied to the same account under different customer names.',
         'Review acuheader.bank_account and clearing_code and confirm each is a distinct entity.', 'acuheader', None,
         'COUNT(*) OVER(PARTITION BY house, bank_account, clearing_code) > 1',
         lambda df: df.duplicated(subset=['house', 'bank_account', 'clearing_code'], keep=False) & df['bank_account'].notna() & df['clearing_code'].notna() & (df['bank_account'].str.strip().str.len() > 1) & (df['clearing_code'].str.strip().str.len() > 1)),

        ('CUS_CLIENT_APAR_DUP', 11, 'Customers', 'Uniqueness', 'Critical',
         'Duplicate (client, apar_id) combination found in customer master',
         'The combination of client code and customer ID must be unique in the customer master. Any duplicate on this key is a data integrity error in the source system that must be resolved before the record can be safely migrated.',
         'Investigate and remove duplicate rows in acuheader.', 'acuheader', None,
         'COUNT(*) OVER(PARTITION BY client, apar_id) > 1',
         lambda df: df.duplicated(subset=['client', 'apar_id'], keep=False)),

        # ── Timeliness ────────────────────────────────────────────────────────

        ('CUS_DORMANT', 11, 'Customers', 'Timeliness', 'Medium',
         'Active customer with no open transactions and no activity in the last 18 months',
         'Active customers must have had recent activity to be included in migration scope. Customers with no open transactions and no history transactions in the last 18 months are dormant and should be reviewed before cutover to confirm they are still needed in the new system.',
         'Review acuheader and consider closing or excluding from migration scope.', 'acuheader', None,
         'apar_id NOT IN (SELECT apar_id FROM acutrans) AND apar_id NOT IN (SELECT apar_id FROM acuhistr WHERE trans_date >= TODAY - 18 months)',
         lambda df, frames: (
             ~df['apar_id'].isin(
                 frames.get('acutrans', pd.DataFrame(columns=['apar_id', 'house']))
                     .pipe(lambda t: t[t['house'].isin(df['house'].unique())]['apar_id'])
             ) &
             ~df['apar_id'].isin(
                 frames.get('acuhistr', pd.DataFrame(columns=['apar_id', 'house', 'trans_date']))
                     .pipe(lambda h: h[
                         h['house'].isin(df['house'].unique()) &
                         (h['trans_date'] >= today - pd.Timedelta(days=548))
                     ]['apar_id'])
             )
         )),

        # ── Validity (scope) ──────────────────────────────────────────────────

        ('CUS_SUNDRY', 11, 'Customers', 'Validity', 'Low',
         'Record is a Sundry/One-time customer',
         'One-time (sundry) customer records are typically created for single-use billing and are not part of the standing customer master. These records should be reviewed to confirm whether they need to be included in migration scope.',
         'Verify acuheader.apar_once migration scope.', 'acuheader', None,
         'acuheader.apar_once = "1" OR "Y"',
         lambda df: df['apar_once'].isin(['1', 'Y', 1])),


        # ======================================================================
        # --- AR OPEN TRANSACTIONS (acutrans) ---
        # ======================================================================

        # ── Completeness ──────────────────────────────────────────────────────

        ('AR_DUE_DATE_MISSING', 17, 'AR Invoices', 'Completeness', 'High',
         'Open AR invoice is missing a due date',
         'Every open AR invoice must have a due date populated. Without this field the system cannot produce debtor aging reports, chase overdue payments or perform period-end accrual calculations.',
         'Populate acutrans.due_date.', 'acutrans', None,
         'acutrans.due_date IS NULL',
         lambda df: df['due_date'].isna()),

        ('AR_EXT_REF_MISSING', 17, 'AR Invoices', 'Completeness', 'High',
         'Open AR invoice missing external reference',
         'Every open invoice should carry an external reference. Without it the invoice cannot be reconciled against customer remittances or matched to supporting documentation.',
         'Populate acutrans.ext_inv_ref.', 'acutrans', None,
         'acutrans.ext_inv_ref IS NULL',
         lambda df: df['ext_inv_ref'].isna()),

        ('AR_AMOUNT_MISSING', 17, 'AR Invoices', 'Completeness', 'Critical',
         'Open AR invoice is missing its original gross amount',
         'Every open invoice must have a gross amount recorded. A revenue record with no value cannot be reported, reconciled or collected and represents a fundamental completeness failure in the AR ledger.',
         'Populate acutrans.amount.', 'acutrans', None,
         'acutrans.amount IS NULL',
         lambda df: df['amount'].isna()),

        ('AR_ORDER_CONTRACT_MISSING', 17, 'AR Invoices', 'Completeness', 'Medium',
         'Open AR invoice is not linked to either a Sales Order or a Contract',
         'Open invoices should be linked to either a Sales Order or a Contract reference. Invoices with no link suggest they were raised outside the standard billing process and may not have been properly authorised.',
         'Populate acutrans.order_id or contract_id.', 'acutrans', None,
         'acutrans.order_id IS NULL AND acutrans.contract_id IS NULL',
         lambda df: df['order_id'].isna() & df['contract_id'].isna()),

        ('AR_FX_NO_RATE', 17, 'AR Invoices', 'Completeness', 'High',
         'Foreign currency invoice missing its exchange rate to GBP',
         'Foreign currency invoices must have an exchange rate to GBP populated. Without a rate the system cannot convert the invoice value into base currency for financial reporting and the balance will be missing from the sterling ledger.',
         'Provide rate in acutrans.exch_rate.', 'acutrans', None,
         'acutrans.currency <> "GBP" AND acutrans.exch_rate IS NULL',
         lambda df: (df['currency'] != 'GBP') & df['exch_rate'].isna()),

        ('AR_CN_NO_REF', 17, 'AR Invoices', 'Completeness', 'Medium',
         'Credit note missing its link to the original invoice',
         'Credit notes must carry a reference back to the original invoice they are offsetting. Without this link the audit trail between the credit and the original charge is broken and the credit cannot be correctly matched during reconciliation.',
         'Populate acutrans.orig_reference.', 'acutrans', None,
         'acutrans.voucher_type IN ("CN","IC","IN","RC") AND acutrans.orig_reference IS NULL',
         lambda df: df['voucher_type'].isin(_CREDIT_NOTE_TYPES) & df['orig_reference'].isna()),

        # ── Validity ──────────────────────────────────────────────────────────

        ('AR_FX_NO_CUR_AMT', 17, 'AR Invoices', 'Validity', 'High',
         'Foreign currency invoice missing its transaction currency amount',
         'Foreign currency invoices must have both the base currency amount and the original transaction currency amount populated. Without the foreign currency amount the record cannot be revalued or reconciled against customer statements.',
         'Populate acutrans.cur_amount.', 'acutrans', None,
         'acutrans.currency <> "GBP" AND acutrans.cur_amount IS NULL',
         lambda df: (df['currency'] != 'GBP') & df['cur_amount'].isna()),

        ('AR_NEG_INV', 17, 'AR Invoices', 'Validity', 'Medium',
         'Negative amount found on a standard AR invoice voucher type',
         'Standard AR invoices must carry a positive amount. A negative amount on an invoice type indicates the wrong voucher type has been used — the record should be a credit note, not an invoice.',
         'Correct acutrans.voucher_type or repost as a credit note.', 'acutrans', None,
         'acutrans.amount < 0 AND acutrans.voucher_type NOT IN credit/reversal types',
         lambda df: (df['amount'] < 0) & ~df['voucher_type'].isin(_CREDIT_OR_REVERSAL)),

        # ── Consistency ───────────────────────────────────────────────────────

        ('AR_REST_ZERO', 17, 'AR Invoices', 'Consistency', 'Medium',
         'Outstanding balance is zero but the item is still flagged as open',
         'Open AR items must have a non-zero remaining balance. An item showing as open with a zero balance has been fully collected but was never closed off in the source system. These ghost records clutter the open AR ledger.',
         'Close item in source system; acutrans.rest_amount = 0.', 'acutrans', None,
         'acutrans.rest_amount = 0',
         lambda df: df['rest_amount'] == 0),

        ('AR_REST_OVER_AMT', 17, 'AR Invoices', 'Consistency', 'High',
         'Outstanding balance exceeds the original invoice amount',
         'The outstanding balance on an invoice cannot exceed the original invoice amount. A remaining balance larger than the gross amount is mathematically impossible and indicates a data corruption issue.',
         'Investigate acutrans.rest_amount vs acutrans.amount.', 'acutrans', None,
         'ABS(acutrans.rest_amount) > ABS(acutrans.amount) + 0.01',
         lambda df: df['rest_amount'].abs() > df['amount'].abs() + 0.01),

        # ── Timeliness ────────────────────────────────────────────────────────

        ('AR_OVERDUE', 17, 'AR Invoices', 'Timeliness', 'Medium',
         'Invoice is past its due date and remains uncollected',
         'Open invoices past their due date represent outstanding receivables that have not been collected on time. These records need to be reviewed before cutover to confirm whether they should be chased, disputed or written off.',
         'Review acutrans.due_date.', 'acutrans', None,
         'acutrans.due_date < TODAY',
         lambda df: df['due_date'] < today),

        # ── Uniqueness ────────────────────────────────────────────────────────

        ('AR_TRANS_KEY_DUP', 17, 'AR Invoices', 'Uniqueness', 'Critical',
         'Duplicate (client, apar_id, voucher_no, sequence_no) found in open transactions',
         'The combination of client, customer ID, voucher number and sequence number must be unique in the open transactions table. Any duplicate on this key is a data integrity error that must be resolved before the record can be safely migrated.',
         'Investigate and remove duplicate rows in acutrans.', 'acutrans', None,
         'COUNT(*) OVER(PARTITION BY client, apar_id, voucher_no, sequence_no) > 1',
         lambda df: df.duplicated(subset=['client', 'apar_id', 'voucher_no', 'sequence_no'], keep=False)),

        ('AR_EXT_REF_DUP', 17, 'AR Invoices', 'Uniqueness', 'High',
         'Duplicate external reference found for the same customer',
         'The same customer invoice reference should not appear on multiple open invoices for the same customer. Duplicate external references are a strong indicator of duplicate billing risk and must be investigated before cutover.',
         'Resolve duplicate acutrans.ext_inv_ref.', 'acutrans', None,
         'COUNT(*) OVER(PARTITION BY acutrans.apar_id, acutrans.ext_inv_ref) > 1',
         lambda df: df.duplicated(subset=['apar_id', 'ext_inv_ref'], keep=False) & df['ext_inv_ref'].notna()),

        # ── Referential integrity ─────────────────────────────────────────────

        ('AR_ORPHANED_TRANS', 17, 'AR Invoices', 'Referential Integrity', 'Critical',
         'Open transaction references a Customer ID that does not exist',
         'Every open AR invoice must reference a customer ID that exists in the customer master. An invoice with no matching customer record has no valid debtor and cannot be processed or collected in the new system.',
         'Create master record in acuheader.', 'acutrans', 'acuheader',
         'acutrans.apar_id NOT IN (SELECT apar_id FROM acuheader)',
         lambda df, frames: ~df['apar_id'].isin(frames.get('acuheader', pd.DataFrame())['apar_id']) if 'acuheader' in frames else pd.Series([False]*len(df))),

        ('AR_TRANS_CUS_CLOSED', 17, 'AR Invoices', 'Referential Integrity', 'Critical',
         'Open transaction exists against a CLOSED customer',
         'Open AR invoices must not be posted against a customer that has been closed or deactivated. Receivables sitting against closed customer records cannot be processed for collection and must be reassigned or written off before migration.',
         'Review status of customer in acuheader.', 'acutrans', 'acuheader',
         'acutrans.apar_id IN (SELECT apar_id FROM acuheader WHERE status = "C")',
         lambda df, frames: df['apar_id'].isin(frames.get('acuheader', pd.DataFrame())[frames.get('acuheader', pd.DataFrame())['status'] == 'C']['apar_id']) if 'acuheader' in frames else pd.Series([False]*len(df))),


        # ======================================================================
        # --- AR HISTORY (acuhistr) ---
        # ======================================================================

        ('AR_HIS_REST_NOT_ZERO', 12, 'AR History', 'Consistency', 'High',
         'Historical (closed) item still carries a non-zero balance',
         'All items in the AR history table must have a zero remaining balance. A historical item with a non-zero balance was not fully collected before being closed and may represent a receivable that was incorrectly written off.',
         'Historical items in acuhistr must have rest_amount = 0.', 'acuhistr', None,
         'acuhistr.rest_amount <> 0',
         lambda df: df['rest_amount'] != 0),

        ('AR_HIS_DATE_MISSING', 12, 'AR History', 'Completeness', 'Critical',
         'Historical record missing its transaction date',
         'Every historical AR transaction must have a transaction date populated. Dates are required for statutory reporting, audit purposes and trend analysis. Records without a date cannot be correctly placed in a financial period.',
         'Populate acuhistr.trans_date.', 'acuhistr', None,
         'acuhistr.trans_date IS NULL',
         lambda df: df['trans_date'].isna()),

        ('AR_HIS_CN_NO_REF', 12, 'AR History', 'Completeness', 'Medium',
         'Historical credit note missing its original invoice reference',
         'Historical credit notes must carry a reference to the original invoice they were raised against. Without this link the audit trail between the credit and the original charge is incomplete and cannot be verified during the migration review.',
         'Populate acuhistr.orig_reference.', 'acuhistr', None,
         'acuhistr.voucher_type IN ("CN","IC","IN","RC") AND acuhistr.orig_reference IS NULL',
         lambda df: df['voucher_type'].isin(_CREDIT_NOTE_TYPES) & df['orig_reference'].isna()),

        ('AR_HIS_DUP', 12, 'AR History', 'Uniqueness', 'High',
         'Duplicate voucher and sequence number found in AR history',
         'The combination of house, voucher number and sequence number must be unique in the AR history table. Duplicate records in the closed ledger indicate a data integrity issue in the source system that needs investigation.',
         'Data integrity error in acuhistr.', 'acuhistr', None,
         'COUNT(*) OVER(PARTITION BY house, voucher_no, sequence_no) > 1',
         lambda df: df.duplicated(subset=['house', 'voucher_no', 'sequence_no'], keep=False)),

        ('AR_HIS_ORPHANED', 12, 'AR History', 'Referential Integrity', 'Medium',
         'Historical record references a Customer ID that does not exist',
         'Every historical AR transaction must reference a customer ID that exists in the customer master. A historical record with no matching customer cannot be correctly attributed to a debtor and breaks the link between transaction history and master data.',
         'Check acuhistr.apar_id against acuheader.', 'acuhistr', 'acuheader',
         'acuhistr.apar_id NOT IN (SELECT apar_id FROM acuheader)',
         lambda df, frames: ~df['apar_id'].isin(frames.get('acuheader', pd.DataFrame())['apar_id'])),
    ]
    return checks
