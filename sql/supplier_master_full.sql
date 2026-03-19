SELECT
    -- === IDENTITY ===
    h.client,                    // Which House - HoC or HoL
    h.apar_id,                   // Supplier ID - primary key
    h.apar_name,                 // Supplier full name
    h.short_name,                // Abbreviated name - 10 char max
    h.apar_gr_id,                // Supplier group code
    h.status,                    // N=Active, C=Closed, P=Parked, T=Terminated
    h.apar_once,                 // Y = sundry/one-off supplier, not a standing record

    -- === REGISTRATION & TAX ===
    h.vat_reg_no,                // VAT registration number - may be blank for non-VAT suppliers
    h.comp_reg_no,               // Companies House registration number
    h.country_code,              // Country of supplier
    h.tax_code,                  // Default tax code applied to invoices
    h.tax_system,                // Tax framework (e.g. UK VAT)

    -- === PAYMENT CONFIGURATION ===
    h.terms_id,                  // Payment terms code e.g. 30 days
    h.pay_method,                // Payment method code e.g. BACS, CHAPS
    h.currency,                  // Default transaction currency
    h.pay_delay,                 // Additional days added on top of payment due date

    -- === BANK DETAILS ===
    // Bank details are held on the supplier record in Unit4 - no separate bank table
    h.clearing_code,             // Sort code
    h.bank_account,              // Bank account number
    h.iban,                      // IBAN - used for international payments
    h.swift,                     // SWIFT/BIC code

    -- === STATUS & DATES ===
    h.expired_date,              // Populated if supplier has been end-dated
    h.last_update,               // Last time this record was modified
    h.wf_state                   // Workflow state - blank=none, T=approved, W=in workflow

FROM asuheader h
WHERE h.client IN ('[HOC_CLIENT]', '[HOL_CLIENT]')
ORDER BY h.client, h.apar_id;


## supplier_master.sql
## Source: asuheader
## Filter: Both Houses, no status filter - full population
## Purpose: Complete supplier master extract. Status filter applied in Python depending 
##          on test - active only for DQ and scoping, full list for backward compatibility checks

---

## Assumptions

| # | Assumption |
|---|---|
| 1 | No status filter applied in SQL - all suppliers extracted regardless of active/inactive |
| 2 | status = 'N' filter applied in Python for all master DQ and migration scoping tests |
| 3 | Full population used in Python for backward compatibility joins to asutrans and asuhistr |
| 4 | Sundry suppliers (apar_once = Y) are included pending a scope decision |
| 5 | Bank details are held exclusively on asuheader - there is no separate bank reference table |
| 6 | Both Houses exist as separate client codes within the same Unit4 instance |
| 7 | [HOC_CLIENT] and [HOL_CLIENT] are placeholders - actual client codes to be confirmed by Parliament |

---

## Data Quality Tests

### Completeness — Active Suppliers Only (status = 'N' in Python)

| Test | Fields |
|---|---|
| Total active supplier count per House | `client`, `status` |
| Missing VAT registration number | `vat_reg_no` |
| Missing company registration number | `comp_reg_no` |
| Missing payment terms | `terms_id` |
| Missing payment method | `pay_method` |
| Missing currency | `currency` |
| Missing sort code AND IBAN - no bank routing detail at all | `clearing_code`, `iban` |
| Missing bank account number | `bank_account` |
| Missing SWIFT where IBAN is present | `swift`, `iban` |

### Validity — Active Suppliers Only (status = 'N' in Python)

| Test | Fields |
|---|---|
| VAT registration number format (GB + 9 digits) | `vat_reg_no` |
| Company registration number format (8 digits) | `comp_reg_no` |
| Sort code format (6 digits numeric) | `clearing_code` |
| Bank account number format (8 digits numeric) | `bank_account` |
| IBAN format and length valid for country code | `iban`, `country_code` |
| SWIFT/BIC format (8 or 11 characters) | `swift` |

### Consistency — Active Suppliers Only (status = 'N' in Python)

| Test | Fields | Notes |
|---|---|---|
| Suppliers with expired_date populated but status still N | `expired_date`, `status` | End-dated but still active |
| Suppliers stuck in workflow | `wf_state` | Should not be migrated until resolved |
| pay_method indicates BACS but sort code and bank account missing | `pay_method`, `clearing_code`, `bank_account` | Would fail payment run in new system |
| pay_method indicates international but IBAN missing | `pay_method`, `iban` | Would fail payment run in new system |

### Duplicates — Active Suppliers Only (status = 'N' in Python)

| Test | Fields | Notes |
|---|---|---|
| Duplicate supplier names within the same House | `client`, `apar_name` | Requires human review to confirm true duplicates |
| Duplicate VAT registration numbers within the same House | `client`, `vat_reg_no` | Stronger duplicate signal than name match |
| Duplicate company registration numbers within the same House | `client`, `comp_reg_no` | Stronger duplicate signal than name match |
| Duplicate supplier names across HoC and HoL | `apar_name` across both clients | Candidates for consolidation - requires human review |
| Duplicate VAT numbers across HoC and HoL | `vat_reg_no` across both clients | Same supplier registered in both Houses |

### Scope — Active Suppliers Only (status = 'N' in Python)

| Test | Fields | Notes |
|---|---|---|
| Volume of sundry suppliers (apar_once = Y) | `apar_once`, `client` | Scope decision required |
| Suppliers with no currency set | `currency` | Cannot process transactions in new system |
| Stale records - last_update older than 3 years | `last_update` | May indicate records never maintained |

### Backward Compatibility — Full Population joined to asutrans in Python

| Test | Fields | Notes |
|---|---|---|
| Open transactions where apar_id does not exist in supplier master at all | `apar_id`, `client` | Genuinely orphaned transaction - no supplier record anywhere |
| Open transactions where apar_id exists but supplier is inactive | `apar_id`, `status` | Transaction open against a closed, parked or terminated supplier - needs investigation |

### Backward Compatibility — Full Population joined to asuhistr in Python

| Test | Fields | Notes |
|---|---|---|
| Historical transactions where apar_id does not exist in supplier master at all | `apar_id`, `client` | Genuinely orphaned historical transaction |
| Historical transactions where apar_id exists but supplier is inactive | `apar_id`, `status` | Expected and normal - supplier deactivated after transaction settled - not an issue |

---

## Outstanding Questions — Parliament Team

| # | Question |
|---|---|
| 1 | What are the client codes for House of Commons and House of Lords in Unit4? |
| 2 | Are there any suppliers Parliament considers active that have a status other than N? |
| 3 | Are sundry suppliers (apar_once = Y) in or out of migration scope? |