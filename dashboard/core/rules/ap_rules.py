import pandas as pd
from datetime import date

# Voucher types where a negative amount/balance is expected and correct
_CREDIT_NOTE_TYPES = ['CN', 'IC', 'IN', 'RC']
_REVERSAL_TYPES    = ['IR', 'PR', 'RV']
_CREDIT_OR_REVERSAL = _CREDIT_NOTE_TYPES + _REVERSAL_TYPES

# Invoice registration/posting types where a negative amount is definitively wrong.
# Expenses, payments, journals, and departmental purchases are excluded because
# their sign depends on context and cannot be asserted.
_INVOICE_TYPES = ['PI', 'OP', 'CP', 'II', 'IU', 'ID', 'IF', 'SR', 'RI', 'SI']

def get_ap_checks():
    """Returns a list of Supplier and AP DQ check definitions."""
    today = pd.Timestamp(date.today())
    
    checks = [
        # ======================================================================
        # --- SUPPLIER MASTER (asuheader) ---
        # ======================================================================
        
        ('SUP_VAT_MISSING', 10, 'Suppliers', 'Completeness', 'Medium',
         'Active supplier missing VAT registration number',
         'Every active supplier must have a VAT registration number populated. Without it, invoices posted against this supplier cannot be correctly reported to HMRC and the record will fail tax compliance checks at go-live. Specialist Adviser (SA) suppliers are excluded and assessed separately.',
         'Verify asuheader.vat_reg_no.', 'asuheader', None,
         'asuheader.vat_reg_no IS NULL WHERE status = "N"',
         lambda df: df['vat_reg_no'].isna() & ~(df['pay_method'] == 'FC') & ~(
             (df['house'] == 'HOC') & (
                 df['apar_id'].astype(str).str[:2].isin(['71', '74']) |
                 df['apar_gr_id'].isin(['ME', 'WI', 'EM', 'IR', 'PY', 'TI', 'TO', 'SC', 'SA'])
             )
         ) & ~(
             (df['house'] == 'HOL') &
             df['apar_id'].astype(str).str[:1].isin(['1', '2', '3'])
         )),

        ('SUP_SA_VAT_MISSING', 10, 'Suppliers', 'Completeness', 'Low',
         'Specialist Adviser supplier missing VAT registration number',
         'Specialist Adviser (SA) suppliers include both individual consultants and limited companies. Individuals may not be VAT-registered, but companies providing services above the VAT threshold must be. Each record in this group should be reviewed to confirm whether a VAT number is expected and populated where appropriate.',
         'Review each SA supplier and populate asuheader.vat_reg_no where the supplier is VAT-registered.', 'asuheader', None,
         'apar_gr_id = "SA" AND vat_reg_no IS NULL',
         lambda df: (df['apar_gr_id'] == 'SA') & df['vat_reg_no'].isna()),

        ('SUP_COMP_REG_MISSING', 10, 'Suppliers', 'Completeness', 'Low',
         'Active supplier missing company registration number',
         'Active suppliers should have a Companies House registration number on record. Without it, Parliament cannot verify the legal entity status of the supplier before migrating the record. Specialist Adviser (SA) suppliers are excluded and assessed separately.',
         'Verify asuheader.comp_reg_no.', 'asuheader', None,
         'asuheader.comp_reg_no IS NULL WHERE status = "N"',
         lambda df: df['comp_reg_no'].isna() & ~(
             (df['house'] == 'HOC') & (
                 df['apar_gr_id'].isin(['EM', 'ME', 'WI', 'IR', 'PY', 'SC', 'SA']) |
                 df['apar_id'].astype(str).str[:2].isin(['71', '74', '89'])
             )
         ) & ~(
             (df['house'] == 'HOL') &
             df['apar_id'].astype(str).str[:1].isin(['1', '2', '3'])
         )),

        ('SUP_SA_COMP_REG_MISSING', 10, 'Suppliers', 'Completeness', 'Low',
         'Specialist Adviser supplier missing company registration number',
         'Specialist Adviser (SA) suppliers include both individual consultants and limited companies. Individuals do not require a Companies House number, but limited companies must have one on record. Each record in this group should be reviewed to confirm whether it represents an individual or a company, and registration numbers populated where appropriate.',
         'Review each SA supplier and populate asuheader.comp_reg_no where the supplier is a limited company.', 'asuheader', None,
         'apar_gr_id = "SA" AND comp_reg_no IS NULL',
         lambda df: (df['apar_gr_id'] == 'SA') & df['comp_reg_no'].isna()),

        ('SUP_TERMS_MISSING', 10, 'Suppliers', 'Completeness', 'High',
         'Active supplier missing payment terms',
         'Payment terms must be assigned to every active supplier. The system uses this field to calculate invoice due dates automatically. A supplier without terms will cause payment runs to fail or require manual intervention on every invoice.',
         'Assign asuheader.terms_id.', 'asuheader', None,
         'asuheader.terms_id IS NULL',
         lambda df: df['terms_id'].isna()),

        ('SUP_PAY_METHOD_MISSING', 10, 'Suppliers', 'Completeness', 'Critical',
         'Active supplier missing default payment method',
         'Every active supplier must have a default payment method assigned. The automated payment run relies on this field to determine how to settle invoices. A supplier without a payment method cannot be included in any payment batch.',
         'Assign asuheader.pay_method (DD/IN).', 'asuheader', None,
         'asuheader.pay_method IS NULL',
         lambda df: df['pay_method'].isna()),

        ('SUP_CURRENCY_MISSING', 10, 'Suppliers', 'Completeness', 'Critical',
         'Active supplier missing default currency',
         'Every active supplier must have a default currency set, typically GBP. The system uses this to assign the correct base currency when posting invoices. A supplier without a currency will cause invoice entry to fail.',
         'Assign asuheader.currency (GBP).', 'asuheader', None,
         'asuheader.currency IS NULL',
         lambda df: df['currency'].isna()),

        ('SUP_BANK_MISSING', 10, 'Suppliers', 'Completeness', 'Critical',
         'Active supplier missing bank account number',
         'A bank account number must be present on every active supplier record. Electronic payments cannot be processed without this field populated. Any open invoice against this supplier would need to be settled manually or held at cutover.',
         'Obtain and populate asuheader.bank_account.', 'asuheader', None,
         'asuheader.bank_account IS NULL',
         lambda df: df['bank_account'].isna()),

        ('SUP_SORT_IBAN_MISSING', 10, 'Suppliers', 'Completeness', 'Critical',
         'Active supplier missing both Sort Code AND IBAN',
         'Every active supplier set to an electronic payment method must have either a sort code or an IBAN populated as a payment routing identifier. Without at least one of these fields, the system has no destination to send electronic payments. Cheque suppliers (pay method CH) are excluded as they do not require electronic routing details.',
         'Required routing in asuheader.clearing_code or iban.', 'asuheader', None,
         'asuheader.clearing_code IS NULL AND asuheader.iban IS NULL AND pay_method != "CH"',
         lambda df: df['clearing_code'].isna() & df['iban'].isna() & ~(df['pay_method'] == 'CH') & ~(
             (df['house'] == 'HOC') &
             df['apar_id'].astype(str).str.strip().str.startswith(('1000', '741'))
         )),

        ('SUP_SWIFT_MISSING', 10, 'Suppliers', 'Completeness', 'High',
         'Supplier has an IBAN but is missing a SWIFT/BIC code',
         'Suppliers with an IBAN must also have a SWIFT/BIC code populated. International payment systems require both fields to route cross-border payments correctly. An IBAN without a SWIFT code will cause international payment instructions to be rejected.',
         'Required for international; populate asuheader.swift.', 'asuheader', None,
         'asuheader.iban IS NOT NULL AND asuheader.swift IS NULL',
         lambda df: df['swift'].isna() & df['iban'].notna()),

        ('SUP_ADDR_MISSING', 10, 'Suppliers', 'Completeness', 'Low',
         'Active supplier has no address line populated',
         'Every supplier should have an address line on record. Address data is required for correspondence, contract administration and to support Know Your Supplier checks before migration.',
         'Populate agladdress.address for this supplier.', 'asuheader', None,
         'agladdress.address IS NULL OR empty',
         lambda df: (df['address'].isna() | (df['address'].str.strip().str.len() == 0)) & ~(
             (df['house'] == 'HOC') & (df['apar_id'].astype(str).str[:4].isin(['1000']) | df['apar_id'].astype(str).str[:2].isin(['74']))
         )),

        ('SUP_PLACE_MISSING', 10, 'Suppliers', 'Completeness', 'Low',
         'Active supplier has no town or city populated',
         'Every supplier should have a town or city recorded. Address data supports supplier verification and correspondence before migration.',
         'Populate agladdress.place for this supplier.', 'asuheader', None,
         'agladdress.place IS NULL OR empty',
         lambda df: (df['place'].isna() | (df['place'].str.strip().str.len() == 0)) & ~(
             (df['house'] == 'HOC') & (df['apar_id'].astype(str).str[:4].isin(['1000']) | df['apar_id'].astype(str).str[:2].isin(['74']))
         )),

        ('SUP_ZIP_MISSING', 10, 'Suppliers', 'Completeness', 'Low',
         'Active supplier has no postcode or zip code populated',
         'Every supplier should have a postcode or zip code recorded. This is required for postal correspondence and automated address verification.',
         'Populate agladdress.zip_code for this supplier.', 'asuheader', None,
         'agladdress.zip_code IS NULL OR empty',
         lambda df: (df['zip_code'].isna() | (df['zip_code'].str.strip().str.len() == 0)) & ~(
             (df['house'] == 'HOC') & df['apar_id'].astype(str).str.strip().str.startswith(('1000', '74'))
         ) & ~(df['pay_method'] == 'FC')),

        ('SUP_VAT_FORMAT', 10, 'Suppliers', 'Validity', 'High',
         'VAT number format is invalid (Expected GB + 9 digits)',
         'VAT registration numbers must follow the HMRC format of GB followed by exactly 9 digits. Numbers that do not match this pattern will fail validation with HMRC systems and cannot be used for tax reporting.',
         'Correct asuheader.vat_reg_no.', 'asuheader', None,
         'asuheader.vat_reg_no NOT LIKE "GB_________" (9 digits)',
         lambda df: (
             (~df['vat_reg_no'].str.replace(' ', '', regex=False).str.match(r'^(GB)?\d{9}$', na=False)) &
             df['vat_reg_no'].notna() &
             ~(df['pay_method'] == 'FC') &
             ~(
                 (df['house'] == 'HOC') & (
                     df['apar_id'].astype(str).str[:2].isin(['71', '74']) |
                     df['apar_gr_id'].isin(['ME', 'WI', 'EM', 'IR', 'PY', 'TI', 'TO', 'SC'])
                 )
             )
         )),

        ('SUP_COMP_REG_FORMAT', 10, 'Suppliers', 'Validity', 'Medium',
         'Company registration format is invalid (Expected 8 digits)',
         'Companies House registration numbers must be exactly 8 digits. Records that do not match this standard format cannot be verified against the Companies House register and may indicate data entry errors.',
         'Correct asuheader.comp_reg_no.', 'asuheader', None,
         'asuheader.comp_reg_no NOT LIKE "________" (8 digits)',
         lambda df: (
             (~df['comp_reg_no'].str.match(r'^\d{8}$', na=False)) &
             df['comp_reg_no'].notna() &
             ~(
                 (df['house'] == 'HOC') &
                 df['apar_id'].astype(str).str[:2].isin(['71', '74', '89'])
             )
         )),

        ('SUP_SORT_FORMAT', 10, 'Suppliers', 'Validity', 'High',
         'Bank sort code format is invalid (Expected XX-XX-XX or XXXXXX)',
         'Bank sort codes must be in either the XX-XX-XX hyphenated format or plain 6-digit format. Sort codes in any other format will be rejected by payment processing systems and must be corrected before go-live.',
         'Correct asuheader.clearing_code.', 'asuheader', None,
         'asuheader.clearing_code NOT LIKE "__-__-__" AND NOT LIKE "______" (6 digits)',
         lambda df: (
             df['clearing_code'].notna() &
             ~df['clearing_code'].str.match(r'^(\d{2}-\d{2}-\d{2}|\d{6})$', na=False) &
             ~('0' + df['clearing_code'].fillna('')).str.match(r'^(\d{2}-\d{2}-\d{2}|\d{6})$', na=False)
         )),

        ('SUP_BANK_FORMAT', 10, 'Suppliers', 'Validity', 'Critical',
         'Bank account format is invalid (More than 8 digits, or contains non-numeric characters)',
         'Bank account numbers must contain only digits and be no longer than 8 digits. Values exceeding 8 digits or containing non-numeric characters will be rejected during payment processing. Accounts with fewer than 8 digits are not flagged as leading zeros may have been stripped during data extraction.',
         'Correct asuheader.bank_account.', 'asuheader', None,
         'asuheader.bank_account containing non-digits OR length > 8',
         lambda df: df['bank_account'].notna() & ~df['bank_account'].str.match(r'^\d{1,8}$', na=False)),

        ('SUP_SWIFT_FORMAT', 10, 'Suppliers', 'Validity', 'High',
         'SWIFT/BIC format is invalid (Expected 8 or 11 chars)',
         'SWIFT/BIC codes must be either 8 or 11 alphanumeric characters in line with the internationally recognised standard. Codes that do not match this format will be rejected by international payment systems.',
         'Correct asuheader.swift.', 'asuheader', None,
         'asuheader.swift length NOT IN (8, 11) or contains invalid chars',
         lambda df: (~df['swift'].str.match(r'^[A-Z0-9]{8,11}$', na=False)) & df['swift'].notna()),

        ('SUP_ZIP_FORMAT', 10, 'Suppliers', 'Validity', 'Medium',
         'Postcode or zip code format is invalid for the supplier country',
         'Postcodes must match the expected format for the supplier country. An invalid postcode indicates a data entry error and will prevent address verification and postal correspondence.',
         'Correct agladdress.zip_code to match the expected format for the country.', 'asuheader', None,
         'zip_code does not match expected format for country_code (GB/US/EU)',
         lambda df: (
             df['zip_code'].notna() &
             (df['zip_code'].str.strip().str.len() > 0) &
             df['country_code'].isin(['GB','US','DE','FR','IT','ES','NL','BE','AT','CH','PT','SE','NO','DK','FI','PL','LU','HU','CZ','SK','SI','HR','RO','BG','IE']) &
             ~(
                 ((df['country_code'] == 'GB') & df['zip_code'].str.strip().str.upper().str.match(r'^[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}$', na=False)) |
                 ((df['country_code'] == 'US') & df['zip_code'].str.strip().str.match(r'^\d{5}(-\d{4})?$', na=False)) |
                 (df['country_code'].isin(['DE','FR','IT','ES','BE','AT','CH','PT','SE','NO','DK','FI','PL','LU','HU','CZ','SK','SI','HR','RO','BG']) & df['zip_code'].str.strip().str.match(r'^\d{4,5}$', na=False)) |
                 ((df['country_code'] == 'NL') & df['zip_code'].str.strip().str.upper().str.match(r'^\d{4}\s?[A-Z]{2}$', na=False)) |
                 ((df['country_code'] == 'IE') & df['zip_code'].str.strip().str.upper().str.match(r'^[A-Z\d]{3}\s?[A-Z\d]{4}$', na=False))
             )
         )),

        ('SUP_BACS_NO_BANK', 10, 'Suppliers', 'Consistency', 'Critical',
         'Payment method is domestic electronic but bank details are missing',
         'Suppliers set to a domestic electronic payment method must have both a bank account number and a sort code populated. The payment run will fail to process settlements for any supplier missing these details.',
         'Provide bank details in asuheader.', 'asuheader', None,
         'asuheader.pay_method IN ("IP","CP","BB") AND (bank_account IS NULL OR clearing_code IS NULL)',
         lambda df: (df['pay_method'].isin(['IP', 'CP', 'BB'])) & (df['bank_account'].isna() | df['clearing_code'].isna()) & ~(
             (df['house'] == 'HOC') &
             df['apar_id'].astype(str).str.strip().str.startswith(('1000', '741'))
         )),

        ('SUP_INT_NO_IBAN', 10, 'Suppliers', 'Consistency', 'Critical',
         'Payment method is international but IBAN is missing',
         'Suppliers set to an international payment method must have an IBAN populated. Cross-border electronic payments cannot be routed without this field. Any open international invoice will fail at the point of payment.',
         'Provide asuheader.iban.', 'asuheader', None,
         'asuheader.pay_method IN ("IN","EU","TF","RT") AND asuheader.iban IS NULL',
         lambda df: (df['pay_method'].isin(['IN', 'EU', 'TF', 'RT'])) & df['iban'].isna()),

        ('SUP_NAME_DUP', 10, 'Suppliers', 'Uniqueness', 'Medium',
         'Duplicate supplier name with matching address and postcode exists within the same House',
         'Each supplier name should be unique within a House. Duplicate names with the same address and postcode indicate the same payee has been registered more than once, which can result in payments being split across multiple records and complicate reconciliation. Records with the same name but a different address or postcode are not flagged.',
         'Consolidate records in asuheader.apar_name.', 'asuheader', None,
         'COUNT(*) OVER(PARTITION BY house, apar_name, address, zip_code) > 1',
         lambda df: df.duplicated(subset=['house', 'apar_name', 'address', 'zip_code'], keep=False) & (df['apar_name'].str.strip().str.len() > 1)),

        ('SUP_NAME_DUP_ANY', 10, 'Suppliers', 'Uniqueness', 'Low',
         'Duplicate supplier name exists within the same House (any address)',
         'Supplier names appear more than once within the same House. Unlike SUP_NAME_DUP, this check does not require address or postcode to match. Records sharing a name at different addresses may be legitimate separate entities, but should be reviewed to confirm they are not accidental duplicates.',
         'Review asuheader.apar_name for any same-name records and confirm each is a distinct legal entity.', 'asuheader', None,
         'COUNT(*) OVER(PARTITION BY house, apar_name) > 1',
         lambda df: df.duplicated(subset=['house', 'apar_name'], keep=False) & (df['apar_name'].str.strip().str.len() > 1)),

        ('SUP_VAT_DUP', 10, 'Suppliers', 'Uniqueness', 'High',
         'Duplicate VAT registration number exists within the same House',
         'A VAT registration number should identify a unique legal entity within a House. The same VAT number on multiple supplier records indicates the same company has been registered more than once, creating duplicate payment risk and potential HMRC reporting errors.',
         'Review asuheader.vat_reg_no and consolidate duplicate supplier records.', 'asuheader', None,
         'COUNT(*) OVER(PARTITION BY house, vat_reg_no) > 1',
         lambda df: df.duplicated(subset=['house', 'vat_reg_no'], keep=False) & df['vat_reg_no'].notna() & (df['vat_reg_no'].str.strip().str.len() > 1)),

        ('SUP_BANK_SORT_DUP', 10, 'Suppliers', 'Uniqueness', 'High',
         'Duplicate bank account and sort code combination exists within the same House',
         'The combination of bank account number and sort code should identify a unique payment destination within a House. The same bank details on multiple supplier records means payments could be made to the same account under different supplier names, which is a significant duplicate payment risk.',
         'Review asuheader.bank_account and clearing_code and confirm each is a distinct payee.', 'asuheader', None,
         'COUNT(*) OVER(PARTITION BY house, bank_account, clearing_code) > 1',
         lambda df: df.duplicated(subset=['house', 'bank_account', 'clearing_code'], keep=False) & df['bank_account'].notna() & df['clearing_code'].notna() & (df['bank_account'].str.strip().str.len() > 1) & (df['clearing_code'].str.strip().str.len() > 1)),

        ('SUP_BANK_DUP', 10, 'Suppliers', 'Uniqueness', 'High',
         'Duplicate bank account, sort code and VAT registration combination within the same House',
         'The combination of bank account, sort code and VAT registration number should be unique within a House. The same combination appearing on multiple supplier records is a strong indicator of duplicate registrations and must be investigated before migration to avoid misdirected payments.',
         'Review and consolidate records in asuheader.', 'asuheader', None,
         'COUNT(*) OVER(PARTITION BY house, bank_account, clearing_code, vat_reg_no) > 1',
         lambda df: df.duplicated(subset=['house', 'bank_account', 'clearing_code', 'vat_reg_no'], keep=False) & df['bank_account'].notna() & df['clearing_code'].notna() & df['vat_reg_no'].notna() & (df['bank_account'].str.strip().str.len() > 1) & (df['clearing_code'].str.strip().str.len() > 1) & (df['vat_reg_no'].str.strip().str.len() > 1)),

        ('SUP_CLIENT_APAR_DUP', 10, 'Suppliers', 'Uniqueness', 'Critical',
         'Duplicate (client, apar_id) combination found in supplier master',
         'The combination of client code and supplier ID must be unique in the supplier master. Any duplicate on this key is a data integrity error in the source system that must be resolved before the record can be safely migrated.',
         'Investigate and remove duplicate rows in asuheader.', 'asuheader', None,
         'COUNT(*) OVER(PARTITION BY client, apar_id) > 1',
         lambda df: df.duplicated(subset=['client', 'apar_id'], keep=False)),

        # ======================================================================
        # --- CROSS-HOUSE UNIQUENESS (asuheader) ---
        # ======================================================================

('SUP_DORMANT', 10, 'Suppliers', 'Timeliness', 'Medium',
         'Active supplier with no open transactions and no activity in the last 18 months',
         'Active suppliers must have had recent activity to be included in migration scope. Suppliers with no open transactions and no history transactions in the last 18 months are dormant and should be reviewed before cutover to confirm they are still needed in the new system.',
         'Review asuheader and consider closing or excluding from migration scope.', 'asuheader', None,
         'apar_id NOT IN (SELECT apar_id FROM asutrans) AND apar_id NOT IN (SELECT apar_id FROM asuhistr WHERE trans_date >= TODAY - 18 months)',
         lambda df, frames: (
             ~df['apar_id'].isin(
                 frames.get('asutrans', pd.DataFrame(columns=['apar_id', 'house']))
                     .pipe(lambda t: t[t['house'].isin(df['house'].unique())]['apar_id'])
             ) &
             ~df['apar_id'].isin(
                 frames.get('asuhistr', pd.DataFrame(columns=['apar_id', 'house', 'trans_date']))
                     .pipe(lambda h: h[
                         h['house'].isin(df['house'].unique()) &
                         (h['trans_date'] >= today - pd.Timedelta(days=548))
                     ]['apar_id'])
             ) &
             ~df['apar_id'].astype(str).str[:4].isin(['1000']) &
             ~((df['house'] == 'HOC') & df['apar_id'].astype(str).str.strip().str.startswith('71')) &
             ~((df['house'] == 'HOC') & df['apar_name'].str.contains(r'school|academy|college|sixth\s*form', case=False, na=False))
         )),

        ('SUP_SUNDRY', 10, 'Suppliers', 'Validity', 'Low',
         'Record is a Sundry/One-time supplier',
         'One-time (sundry) supplier records are typically created for single-use payments and are not part of a standing supplier master. These records should be reviewed to confirm whether they need to be included in the migration scope.',
         'Verify asuheader.apar_once migration scope.', 'asuheader', None,
         'asuheader.apar_once = "Y"',
         lambda df: df['apar_once'] == 'Y'),


        # ======================================================================
        # --- AP OPEN TRANSACTIONS (asutrans) ---
        # ======================================================================

        ('AP_DUE_DATE_MISSING', 16, 'AP Invoices', 'Completeness', 'High',
         'Open invoice is missing a due date',
         'Every open invoice must have a due date populated. Without this field, the system cannot calculate aging, produce liability reports or flag overdue payments. Missing due dates will also prevent correct period-end accrual calculations.',
         'Populate asutrans.due_date.', 'asutrans', None,
         'asutrans.due_date IS NULL',
         lambda df: df['due_date'].isna()),

        ('AP_EXT_REF_MISSING', 16, 'AP Invoices', 'Completeness', 'Critical',
         'Open invoice missing its external (supplier) reference',
         'Every open invoice must carry the supplier invoice reference in the external reference field. Without it, the invoice cannot be matched back to the physical document and the supplier cannot be paid against a specific remittance.',
         'Populate asutrans.ext_inv_ref.', 'asutrans', None,
         'asutrans.ext_inv_ref IS NULL',
         lambda df: df['ext_inv_ref'].isna() & ~(
             (df['house'] == 'HOC') & (df['voucher_no'].astype(str).str.strip() == '10048531')
         )),

        ('AP_AMOUNT_MISSING', 16, 'AP Invoices', 'Completeness', 'Critical',
         'Open invoice is missing its original gross amount',
         'Every open invoice must have a gross amount recorded. A financial record with no value cannot be reported, reconciled or settled and represents a fundamental completeness failure in the AP ledger.',
         'Populate asutrans.amount.', 'asutrans', None,
         'asutrans.amount IS NULL',
         lambda df: df['amount'].isna()),

        ('AP_PO_CONTRACT_MISSING', 16, 'AP Invoices', 'Completeness', 'Medium',
         'Open invoice is not linked to either a PO or a Contract',
         'Open invoices should be linked to either a Purchase Order or a Contract reference. Invoices with no procurement link suggest they arrived outside the standard purchasing process and have not been properly authorised.',
         'Populate asutrans.order_id or contract_id.', 'asutrans', None,
         'asutrans.order_id IS NULL AND asutrans.contract_id IS NULL',
         lambda df: df['order_id'].isna() & df['contract_id'].isna()),

        ('AP_FX_NO_RATE', 16, 'AP Invoices', 'Completeness', 'High',
         'Foreign currency invoice missing its exchange rate to GBP',
         'Foreign currency invoices must have an exchange rate to GBP populated. Without a rate, the system cannot convert the invoice value into base currency for financial reporting and the balance will be missing from the sterling ledger.',
         'Provide rate in asutrans.exch_rate.', 'asutrans', None,
         'asutrans.currency <> "GBP" AND asutrans.exch_rate IS NULL',
         lambda df: (df['currency'] != 'GBP') & df['exch_rate'].isna()),

        ('AP_CN_NO_REF', 16, 'AP Invoices', 'Completeness', 'Medium',
         'Credit note missing its link to the original invoice',
         'Credit notes must carry a reference back to the original invoice they are offsetting. Without this link, the audit trail between the credit and the original charge is broken and the credit cannot be correctly matched during reconciliation.',
         'Populate asutrans.orig_reference.', 'asutrans', None,
         'asutrans.voucher_type IN ("CN","IC","IN","RC") AND asutrans.orig_reference IS NULL',
         lambda df: df['voucher_type'].isin(_CREDIT_NOTE_TYPES) & df['orig_reference'].isna()),

('AP_FX_NO_CUR_AMT', 16, 'AP Invoices', 'Validity', 'High',
         'Foreign currency invoice missing its transaction currency amount',
         'Foreign currency invoices must have both the base currency amount and the original transaction currency amount populated. Without the foreign currency amount, the record cannot be revalued or reconciled against supplier statements.',
         'Populate asutrans.cur_amount.', 'asutrans', None,
         'asutrans.currency <> "GBP" AND asutrans.cur_amount IS NULL',
         lambda df: (df['currency'] != 'GBP') & df['cur_amount'].isna()),

        ('AP_REST_ZERO', 16, 'AP Invoices', 'Consistency', 'Medium',
         'Outstanding balance is zero but the item is still flagged as OPEN',
         'Open items must have a non-zero remaining balance. An item showing as open with a zero balance has been fully settled but was never closed off in the source system. These ghost records clutter the open AP ledger and may trigger unnecessary payment processing or supplier remittance queries in the new system.',
         'Close item in source system; asutrans.rest_amount = 0.', 'asutrans', None,
         'asutrans.rest_amount = 0',
         lambda df: df['rest_amount'] == 0),

        ('AP_REST_OVER_AMT', 16, 'AP Invoices', 'Consistency', 'High',
         'Outstanding balance exceeds the original invoice amount',
         'The outstanding balance on an invoice cannot exceed the original invoice amount. A remaining balance larger than the gross amount is mathematically impossible and indicates a data corruption issue that must be investigated before migration.',
         'Investigate asutrans.rest_amount vs asutrans.amount.', 'asutrans', None,
         'ABS(asutrans.rest_amount) > ABS(asutrans.amount) + 0.01',
         lambda df: df['rest_amount'].abs() > df['amount'].abs() + 0.01),

('AP_TRANS_KEY_DUP', 16, 'AP Invoices', 'Uniqueness', 'Critical',
         'Duplicate (client, apar_id, voucher_no, sequence_no) found in open transactions',
         'The combination of client, supplier ID, voucher number and sequence number must be unique in the open transactions table. Any duplicate on this key is a data integrity error that must be resolved before the record can be safely migrated.',
         'Investigate and remove duplicate rows in asutrans.', 'asutrans', None,
         'COUNT(*) OVER(PARTITION BY client, apar_id, voucher_no, sequence_no) > 1',
         lambda df: df.duplicated(subset=['client', 'apar_id', 'voucher_no', 'sequence_no'], keep=False)),

        ('AP_EXT_REF_DUP', 16, 'AP Invoices', 'Uniqueness', 'High',
         'Duplicate external reference found for the same supplier',
         'The same supplier invoice reference should not appear on multiple open invoices for the same supplier. Duplicate external references are a strong indicator of duplicate payment risk and must be investigated before cutover.',
         'Resolve duplicate asutrans.ext_inv_ref.', 'asutrans', None,
         'COUNT(*) OVER(PARTITION BY asutrans.apar_id, asutrans.ext_inv_ref) > 1',
         lambda df: df.duplicated(subset=['apar_id', 'ext_inv_ref'], keep=False) & df['ext_inv_ref'].notna()),

('AP_ORPHANED_TRANS', 16, 'AP Invoices', 'Referential Integrity', 'Critical',
         'Open transaction references a Supplier ID that does not exist',
         'Every open invoice must reference a supplier ID that exists in the supplier master. An invoice with no matching supplier record has no valid payee and cannot be processed or settled in the new system.',
         'Create master record in asuheader.', 'asutrans', 'asuheader',
         'asutrans.apar_id NOT IN (SELECT apar_id FROM asuheader)',
         lambda df, frames: ~df['apar_id'].isin(frames.get('asuheader', pd.DataFrame())['apar_id'])),

        ('AP_TRANS_SUP_CLOSED', 16, 'AP Invoices', 'Referential Integrity', 'Critical',
         'Open transaction exists against a CLOSED supplier',
         'Open invoices must not be posted against a supplier that has been closed or deactivated. Liabilities sitting against closed vendor records cannot be processed for payment and must be reassigned to an active supplier or written off before migration.',
         'Review status of supplier in asuheader.', 'asutrans', 'asuheader',
         'asutrans.apar_id IN (SELECT apar_id FROM asuheader WHERE status = "C")',
         lambda df, frames: df['apar_id'].isin(frames.get('asuheader', pd.DataFrame())[frames.get('asuheader', pd.DataFrame())['status'] == 'C']['apar_id'])),


        # ======================================================================
        # --- AP HISTORY (asuhistr) ---
        # ======================================================================

        ('HIS_REST_NOT_ZERO', 18, 'AP History', 'Consistency', 'High',
         'Historical (closed) item still carries a non-zero balance',
         'All items in the AP history table must have a zero remaining balance. A historical item with a non-zero balance was not fully settled before being closed and may represent a liability that was incorrectly written off.',
         'Historical items in asuhistr must have rest_amount = 0.', 'asuhistr', None,
         'asuhistr.rest_amount <> 0',
         lambda df: df['rest_amount'] != 0),

        ('HIS_DATE_MISSING', 18, 'AP History', 'Completeness', 'Critical',
         'Historical record missing its transaction date',
         'Every historical AP transaction must have a transaction date populated. Dates are required for statutory reporting, audit purposes and trend analysis. Records without a date cannot be correctly placed in a financial period.',
         'Populate asuhistr.trans_date.', 'asuhistr', None,
         'asuhistr.trans_date IS NULL',
         lambda df: df['trans_date'].isna()),

        ('HIS_CN_NO_REF', 18, 'AP History', 'Completeness', 'Medium',
         'Historical credit note missing its original invoice reference',
         'Historical credit notes must carry a reference to the original invoice they were raised against. Without this link, the audit trail between the credit and the original charge is incomplete and cannot be verified during the migration review.',
         'Populate asuhistr.orig_reference.', 'asuhistr', None,
         'asuhistr.voucher_type IN ("CN","IC","IN","RC") AND asuhistr.orig_reference IS NULL',
         lambda df: df['voucher_type'].isin(_CREDIT_NOTE_TYPES) & df['orig_reference'].isna()),

        ('HIS_DUP', 18, 'AP History', 'Uniqueness', 'High',
         'Duplicate voucher and sequence number found in history',
         'The combination of client, voucher number and sequence number must be unique in the AP history table. Duplicate records in the closed ledger indicate a data integrity issue in the source system that needs investigation before the history is included in migration.',
         'Data integrity error in asuhistr.', 'asuhistr', None,
         'COUNT(*) OVER(PARTITION BY client, voucher_no, sequence_no) > 1',
         lambda df: df.duplicated(subset=['house', 'voucher_no', 'sequence_no'], keep=False)),

        ('HIS_ORPHANED', 18, 'AP History', 'Referential Integrity', 'Medium',
         'Historical record references a Supplier ID that does not exist',
         'Every historical AP transaction must reference a supplier ID that exists in the supplier master. A historical record with no matching supplier cannot be correctly attributed to a vendor and breaks the link between transaction history and master data.',
         'Check asuhistr.apar_id against asuheader.', 'asuhistr', 'asuheader',
         'asuhistr.apar_id NOT IN (SELECT apar_id FROM asuheader)',
         lambda df, frames: ~df['apar_id'].isin(frames.get('asuheader', pd.DataFrame())['apar_id'])),
    ]
    return checks
