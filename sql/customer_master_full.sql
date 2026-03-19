-- ============================================================
-- customer_master.sql
-- Source:  acuheader
-- Filter:  Both Houses, no status filter - full population
-- Purpose: Complete customer master extract. Status filter applied 
--          in Python depending on test - active only for DQ and 
--          scoping, full list for backward compatibility checks
-- ============================================================

SELECT
    -- === IDENTITY ===
    h.client,                    // Which House - HoC or HoL
    h.apar_id,                   // Customer ID - primary key
    h.apar_name,                 // Customer full name
    h.short_name,                // Abbreviated name - 10 char max
    h.apar_gr_id,                // Customer group code
    h.status,                    // N=Active, C=Closed, P=Parked, T=Terminated
    h.apar_once,                 // 1 = sundry/one-off customer, not a standing record
    h.main_apar_id,              // Head office customer ID - links subsidiary to parent

    -- === REGISTRATION & TAX ===
    h.vat_reg_no,                // VAT registration number
    h.comp_reg_no,               // Companies House registration number
    h.country_code,              // Country of customer
    h.tax_code,                  // Default tax code applied to invoices
    h.tax_system,                // Tax framework (e.g. UK VAT)

    -- === PAYMENT & CREDIT ===
    h.terms_id,                  // Payment terms code e.g. 30 days
    h.pay_method,                // Payment method code
    h.currency,                  // Default transaction currency
    h.pay_delay,                 // Additional days added on top of payment due date
    h.credit_limit,              // Credit limit in local currency - 0 or null may indicate unconfigured
    h.credit_age,                // Maximum days past due date allowed in credit check
    h.intrule_id,                // Interest and reminder rule - drives overdue interest calculations

    -- === BANK DETAILS ===
    // Bank details held on customer record - used for direct debit collections
    h.clearing_code,             // Sort code
    h.bank_account,              // Bank account number
    h.iban,                      // IBAN - used for international payments
    h.swift,                     // SWIFT/BIC code

    -- === COLLECTION & LEGAL ===
    h.collect_flag,              // 1 = active collection case against this customer
    h.invoice_code,              // Invoice rule code

    -- === STATUS & DATES ===
    h.expired_date,              // Populated if customer has been end-dated
    h.last_update,               // Last time this record was modified
    h.wf_state                   // Workflow state - blank=none, T=approved, W=in workflow

FROM acuheader h
WHERE h.client IN ('[HOC_CLIENT]', '[HOL_CLIENT]')
ORDER BY h.client, h.apar_id;


## customer_master.sql
## Source: acuheader
## Filter: Both Houses, no status filter - full population
## Purpose: Complete customer master extract. Status filter applied in Python 
##          depending on test - active only for DQ and scoping, full list for 
##          backward compatibility checks

---

## Assumptions

| # | Assumption |
|---|---|
| 1 | No status filter applied in SQL - all customers extracted regardless of active/inactive |
| 2 | status = 'N' filter applied in Python for all master DQ and migration scoping tests |
| 3 | Full population used in Python for backward compatibility joins to acutrans and acuhistr |
| 4 | Sundry customers (apar_once = 1) are included pending a scope decision |
| 5 | Bank details are held on acuheader - used for direct debit collections |
| 6 | credit_limit of zero and null are treated as distinct - zero may be deliberate, null may indicate never configured |
| 7 | main_apar_id is included but whether Parliament uses parent/subsidiary customer relationships is unknown |
| 8 | collect_flag = 1 indicates an active collection case - these customers require review before migration |
| 9 | Both Houses exist as separate client codes within the same Unit4 instance |
| 10 | [HOC_CLIENT] and [HOL_CLIENT] are placeholders - actual client codes to be confirmed by Parliament |

---

## Data Quality Tests

### Completeness — Active Customers Only (status = 'N' in Python)

| Test | Fields |
|---|---|
| Total active customer count per House | `client`, `status` |
| Missing VAT registration number | `vat_reg_no` |
| Missing company registration number | `comp_reg_no` |
| Missing payment terms | `terms_id` |
| Missing payment method | `pay_method` |
| Missing currency | `currency` |
| Missing credit limit (null) | `credit_limit` |
| Credit limit set to zero | `credit_limit` |
| Missing interest and reminder rule | `intrule_id` |

### Validity — Active Customers Only (status = 'N' in Python)

| Test | Fields | Notes |
|---|---|---|
| VAT registration number format (GB + 9 digits) | `vat_reg_no` | |
| Company registration number format (8 digits) | `comp_reg_no` | |
| Sort code format (6 digits numeric) | `clearing_code` | Only where pay_method indicates direct debit |
| Bank account number format (8 digits numeric) | `bank_account` | Only where pay_method indicates direct debit |
| IBAN format and length valid for country code | `iban`, `country_code` | |
| SWIFT/BIC format (8 or 11 characters) | `swift` | |

### Consistency — Active Customers Only (status = 'N' in Python)

| Test | Fields | Notes |
|---|---|---|
| Customers with expired_date populated but status still N | `expired_date`, `status` | End-dated but still active |
| Customers stuck in workflow | `wf_state` | Should not be migrated until resolved |
| Customers with active collection case | `collect_flag` | collect_flag = 1 - needs review before migration |
| Customers with main_apar_id set — parent/subsidiary relationships | `main_apar_id`, `apar_id` | Flag volume - confirm whether parent record also in scope |
| pay_method indicates direct debit but no bank details | `pay_method`, `clearing_code`, `bank_account`, `iban` | Would fail collection run in new system |

### Duplicates — Active Customers Only (status = 'N' in Python)

| Test | Fields | Notes |
|---|---|---|
| Duplicate customer names within the same House | `client`, `apar_name` | Requires human review to confirm true duplicates |
| Duplicate VAT registration numbers within the same House | `client`, `vat_reg_no` | Stronger duplicate signal than name match |
| Duplicate company registration numbers within the same House | `client`, `comp_reg_no` | Stronger duplicate signal than name match |
| Duplicate customer names across HoC and HoL | `apar_name` across both clients | Candidates for consolidation - requires human review |
| Duplicate VAT numbers across HoC and HoL | `vat_reg_no` across both clients | Same customer registered in both Houses |

### Scope — Active Customers Only (status = 'N' in Python)

| Test | Fields | Notes |
|---|---|---|
| Volume of sundry customers (apar_once = 1) | `apar_once`, `client` | Scope decision required |
| Customers with no currency set | `currency` | Cannot process transactions in new system |
| Stale records - last_update older than 3 years | `last_update` | May indicate records never maintained |

### Backward Compatibility — Full Population joined to acutrans in Python

| Test | Fields | Notes |
|---|---|---|
| Open transactions where apar_id does not exist in customer master at all | `apar_id`, `client` | Genuinely orphaned transaction - no customer record anywhere |
| Open transactions where apar_id exists but customer is inactive | `apar_id`, `status` | Transaction open against closed, parked or terminated customer |

### Backward Compatibility — Full Population joined to acuhistr in Python

| Test | Fields | Notes |
|---|---|---|
| Historical transactions where apar_id does not exist in customer master at all | `apar_id`, `client` | Genuinely orphaned historical transaction |
| Historical transactions where apar_id exists but customer is inactive | `apar_id`, `status` | Expected and normal - customer deactivated after transaction settled |

---

## Outstanding Questions — Parliament Team

| # | Question |
|---|---|
| 1 | What are the client codes for House of Commons and House of Lords in Unit4? |
| 2 | Are there any customers Parliament considers active that have a status other than N? |
| 3 | Are sundry customers (apar_once = 1) in or out of migration scope? |
| 4 | Does Parliament use parent/subsidiary customer relationships via main_apar_id? If so, are parent records in migration scope? |
| 5 | Are customers with an active collection case (collect_flag = 1) expected to be migrated or held pending resolution? |