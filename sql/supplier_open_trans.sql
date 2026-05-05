-- ============================================================
-- HOW TO RUN
-- Run against Agresso_HoC  → save as supplier_open_trans_HOC.csv
-- Run against agresso_HoL  → save as supplier_open_trans_HOL.csv
-- Server: mdata837
-- ============================================================

SELECT
    -- === IDENTITY ===
    t.client,                    -- Internal Unit4 client/fund code (not the house identifier)
    t.apar_id,                   // Supplier ID - links to asuheader.apar_id
    t.voucher_no,                // Unique transaction/invoice number
    t.sequence_no,               // Line number within the transaction

    -- === INVOICE DETAIL ===
    t.voucher_type,              // Transaction type e.g. invoice, credit note
    t.voucher_date,              // Date transaction was posted
    t.trans_date,                // Original transaction date
    t.due_date,                  // Payment due date
    t.description,               // Invoice description/narrative

    -- === AMOUNTS ===
    t.amount,                    // Amount in local currency (GBP)
    t.cur_amount,                // Amount in transaction currency (if foreign)
    t.currency,                  // Transaction currency code
    t.rest_amount,               // Outstanding balance remaining
    t.rest_curr,                 // Outstanding balance in transaction currency
    t.discount,                  // Discount amount if applicable
    t.dc_flag,                   // Debit/Credit flag

    -- === STATUS & PAYMENT ===
    t.status,                    // N=Open, P=Parked, R=On proposal, I=Confirmed payment
    t.pay_method,                // Payment method code
    t.payment_date,              // Date payment was made if applicable
    t.pay_flag,                  // Y = payment on account
    t.period,                    // Accounting period
    t.payperiod,                 // Payment period

    -- === REFERENCES ===
    t.ext_inv_ref,               // External invoice reference - supplier's own invoice number
    t.orig_reference,            // Links credit note back to its original invoice voucher_no
    t.order_id,                  // Linked purchase order number
    t.contract_id,               // Linked contract reference
    t.tax_code,                  // Tax code applied to this transaction
    t.exch_rate,                 // Exchange rate used if foreign currency

    -- === AUDIT ===
    t.last_update,               // Last time this record was modified
    t.wf_state                   // Workflow state

FROM asutrans t
WHERE t.status != 'C'           -- Exclude closed/paid - open items only
ORDER BY t.apar_id, t.voucher_no;




## supplier_open_trans.sql
## Source: asutrans
## Filter: status != 'C' (open items only), both Houses
## Purpose: All open/unpaid supplier invoices and credit notes at point of extract - 
##          primary input for AP opening balance migration and pre-cutover cleansing

---

## Assumptions

| # | Assumption |
|---|---|
| 1 | No date filter applied - all open items regardless of age are in scope for migration |
| 2 | status != 'C' is the correct filter for open items - C is the only closed/paid status |
| 3 | Parked invoices (P) are included - migration scope explicitly includes unapproved invoices |
| 4 | Confirmed payments (I) are included - payment confirmed but not yet cleared |
| 5 | Payment on account items (pay_flag = Y) are included - unapplied credits in scope |
| 6 | voucher_type values for invoices vs credit notes are unknown - to be confirmed by Parliament |
| 7 | orig_reference on a credit note points to the voucher_no of the original invoice |
| 8 | rest_amount represents the true outstanding balance at point of extract |
| 9 | Both Houses exist as separate client codes within the same Unit4 instance |
| 10 | [HOC_CLIENT] and [HOL_CLIENT] are placeholders - actual client codes to be confirmed by Parliament |

---

## Data Quality Tests

### Completeness — Standalone

| Test | Fields |
|---|---|
| Total open invoice count per House | `client`, `apar_id` |
| Total outstanding balance per House | `client`, `rest_amount` |
| Split by status (N/P/R/I) — volume and value | `status`, `rest_amount`, `client` |
| Invoices missing due date | `due_date` |
| Invoices missing external invoice reference | `ext_inv_ref` |
| Invoices missing amount | `amount` |
| Invoices with no linked PO or contract | `order_id`, `contract_id` |
| Parked invoices — volume and value | `status`, `amount`, `rest_amount` |
| Foreign currency invoices with missing exchange rate | `currency`, `exch_rate` |
| Credit notes missing orig_reference | `voucher_type`, `orig_reference` |

### Validity — Standalone

| Test | Fields | Notes |
|---|---|---|
| Invoices where amount is negative but voucher_type is not credit note | `amount`, `voucher_type` | Negative amount should only appear on credit notes |
| Foreign currency invoices where cur_amount is missing | `currency`, `cur_amount` | If currency != GBP then cur_amount should be populated |

### Consistency — Standalone

| Test | Fields | Notes |
|---|---|---|
| Invoices where rest_amount is zero but status is not closed | `rest_amount`, `status` | Fully paid but not closed - should not be in asutrans |
| Invoices where rest_amount exceeds original amount | `rest_amount`, `amount` | Outstanding balance cannot exceed original invoice value |
| Overdue invoices — due_date in the past | `due_date` | Volume and value of overdue liability |
| Net negative opening balance per supplier | `apar_id`, `client`, `rest_amount` | Sum rest_amount by supplier - negative means credits outweigh invoices |
| Credit notes where orig_reference does not match any voucher_no in this extract | `orig_reference`, `voucher_no` | Orphaned credit note - original invoice already closed/paid. Candidates for review not definitive errors - AP team to confirm |
| Invoices stuck in workflow | `wf_state` | Must be resolved before cutover |
| Duplicate external invoice references per supplier | `apar_id`, `ext_inv_ref` | Same supplier invoice number appearing twice |

### Completeness — Joined to asuheader in Python

| Test | Fields | Notes |
|---|---|---|
| Open transactions where apar_id does not exist in asuheader | `apar_id`, `client` | Orphaned transaction - no parent supplier record |
| Total open liability per supplier with supplier name | `apar_id`, `rest_amount`, `apar_name` | Allows AP team to review by name not just ID |
| Suppliers in asuheader with no open transactions | `apar_id`, `client` | Active suppliers with no current liability - RECENT_ACTIVITY candidates |

### Consistency — Joined to asuheader in Python

| Test | Fields | Notes |
|---|---|---|
| Open transactions against a supplier with status C | `apar_id`, `status` | Transaction open but supplier is closed |
| Open transactions against a supplier with status P | `apar_id`, `status` | Transaction open but supplier is parked |
| Open transactions against an expired supplier | `apar_id`, `expired_date` | Transaction open but supplier has been end-dated |
| Transaction currency does not match supplier default currency | `currency`, `apar_id` | May be valid but worth flagging volume |
| Transaction tax code differs from supplier default tax code | `tax_code`, `apar_id` | May be valid override or data entry error |
| Transaction payment method differs from supplier default payment method | `pay_method`, `apar_id` | May indicate one-off override or error |
| Supplier pay_method indicates BACS but sort code or bank account missing on asuheader | `pay_method`, `clearing_code`, `bank_account` | Would fail payment run in new system |

---

## Outstanding Questions — Parliament Team

| # | Question |
|---|---|
| 1 | What are the exact values Unit4 uses in `voucher_type` to distinguish invoices from credit notes? Required before credit note checks can be run in Python |
| 2 | Are open credit notes with no matching open invoice always an error, or can they legitimately sit open awaiting offset against a future invoice? AP team to confirm before flagging as issues |
| 3 | Are Members' allowances and expenses held in asutrans or a separate table? If in asutrans what apar_type or voucher_type value identifies them? |