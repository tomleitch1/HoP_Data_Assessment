-- ============================================================
-- customer_open_trans.sql
-- Source:  acutrans
-- Filter:  status != 'C' (open items only), both Houses
-- Purpose: All open AR transactions at point of extract covering:
--          Seq 17 - open invoices and credit/debit memos (pay_flag = 0)
--          Seq 18 - unapplied cash and on-account receipts (pay_flag = 1)
--          Python splits by pay_flag for separate migration object handling
-- ============================================================

SELECT
    -- === IDENTITY ===
    t.client,                    // Which House - HoC or HoL
    t.apar_id,                   // Customer ID - links to acuheader.apar_id
    t.voucher_no,                // Unique transaction number
    t.sequence_no,               // Line number within the transaction

    -- === TRANSACTION DETAIL ===
    t.voucher_type,              // Transaction type e.g. invoice, credit note, receipt
    t.voucher_date,              // Date transaction was posted
    t.trans_date,                // Original transaction date
    t.due_date,                  // Payment due date
    t.description,               // Transaction description/narrative

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
    t.pay_flag,                  // 1 = unapplied receipt/payment on account (Seq 18), 0 = invoice (Seq 17)
    t.pay_method,                // Payment method code
    t.payment_date,              // Date payment was made if applicable
    t.period,                    // Accounting period
    t.payperiod,                 // Payment period

    -- === REFERENCES ===
    t.ext_inv_ref,               // External invoice reference - customer's own invoice number
    t.orig_reference,            // Links credit note back to its original invoice voucher_no
    t.order_id,                  // Linked sales order number
    t.contract_id,               // Linked contract reference
    t.tax_code,                  // Tax code applied to this transaction
    t.exch_rate,                 // Exchange rate used if foreign currency

    -- === AR SPECIFIC ===
    t.rem_level,                 // Reminder level - how many payment reminders have been sent
    t.remind_date,               // Date of last reminder sent
    t.collect_status,            // Debt collection status
    t.collect_agency,            // Collection agency if referred to external collection
    t.intrule_id,                // Interest and reminder rule applied to this transaction
    t.int_status,                // Interest status - whether interest has been charged

    -- === AUDIT ===
    t.last_update,               // Last time this record was modified
    t.wf_state                   // Workflow state

FROM acutrans t
WHERE t.client IN ('[HOC_CLIENT]', '[HOL_CLIENT]')
  AND t.status != 'C'           // Exclude closed/paid - open items only
ORDER BY t.client, t.apar_id, t.voucher_no;


## customer_open_trans.sql
## Source: acutrans
## Filter: status != 'C' (open items only), both Houses
## Purpose: All open AR transactions at point of extract.
##          Seq 17 - open invoices and credit/debit memos (pay_flag = 0)
##          Seq 18 - unapplied cash and on-account receipts (pay_flag = 1)
##          Python splits by pay_flag for separate migration object handling

---

## Assumptions

| # | Assumption |
|---|---|
| 1 | No date filter applied - all open items regardless of age are in scope for migration |
| 2 | status != 'C' is the correct filter for open items - C is the only closed status |
| 3 | pay_flag = 1 identifies unapplied receipts (Seq 18) and pay_flag = 0 identifies open invoices (Seq 17) |
| 4 | Parked transactions (P) are included - unapproved invoices are in scope |
| 5 | Confirmed payments (I) are included - payment confirmed but not yet cleared |
| 6 | voucher_type values for invoices vs credit notes are unknown - to be confirmed by Parliament |
| 7 | orig_reference on a credit note points to the voucher_no of the original invoice |
| 8 | rest_amount represents the true outstanding balance at point of extract |
| 9 | Customers in active collection (collect_status populated) are included - scope decision required |
| 10 | Both Houses exist as separate client codes within the same Unit4 instance |
| 11 | [HOC_CLIENT] and [HOL_CLIENT] are placeholders - actual client codes to be confirmed by Parliament |

---

## Data Quality Tests

### Completeness — Standalone

| Test | Fields |
|---|---|
| Total open transaction count per House | `client`, `apar_id` |
| Total outstanding balance per House | `client`, `rest_amount` |
| Split by pay_flag — Seq 17 vs Seq 18 volume and value | `pay_flag`, `rest_amount`, `client` |
| Split by status (N/P/R/I) — volume and value | `status`, `rest_amount`, `client` |
| Invoices missing due date | `due_date` |
| Invoices missing external invoice reference | `ext_inv_ref` |
| Invoices missing amount | `amount` |
| Credit notes missing orig_reference | `voucher_type`, `orig_reference` |
| Foreign currency invoices with missing exchange rate | `currency`, `exch_rate` |
| Transactions with no linked order or contract | `order_id`, `contract_id` |

### Validity — Standalone

| Test | Fields | Notes |
|---|---|---|
| Invoices where amount is negative but voucher_type is not credit note | `amount`, `voucher_type` | Negative amount should only appear on credit notes |
| Foreign currency invoices where cur_amount is missing | `currency`, `cur_amount` | If currency != GBP then cur_amount should be populated |

### Consistency — Standalone

| Test | Fields | Notes |
|---|---|---|
| Invoices where rest_amount is zero but status is not closed | `rest_amount`, `status` | Fully paid but not closed - should not be in acutrans |
| Invoices where rest_amount exceeds original amount | `rest_amount`, `amount` | Outstanding balance cannot exceed original invoice value |
| Overdue invoices — due_date in the past | `due_date`, `rest_amount` | Volume and value of overdue AR |
| Net negative opening balance per customer | `apar_id`, `client`, `rest_amount` | Sum rest_amount by customer - negative means credits outweigh invoices |
| Credit notes where orig_reference does not match any voucher_no in this extract | `orig_reference`, `voucher_no` | Orphaned credit note - original invoice already closed. Candidates for review not definitive errors - AR team to confirm |
| Transactions in active collection | `collect_status`, `collect_agency` | Volume and value of debt in collection - scope decision required |
| Transactions with high reminder level | `rem_level` | Invoices at high reminder level are overdue and may be irrecoverable |
| Transactions stuck in workflow | `wf_state` | Must be resolved before cutover |
| Duplicate external invoice references per customer | `apar_id`, `ext_inv_ref` | Same customer invoice number appearing twice |

### Completeness — Joined to acuheader in Python

| Test | Fields | Notes |
|---|---|---|
| Open transactions where apar_id does not exist in customer master at all | `apar_id`, `client` | Genuinely orphaned transaction - no customer record anywhere |
| Open transactions where apar_id exists but customer is inactive | `apar_id`, `status` | Transaction open against inactive customer - needs investigation |
| Total open AR liability per customer with customer name | `apar_id`, `rest_amount`, `apar_name` | Allows AR team to review by name not just ID |
| Customers in acuheader with no open transactions | `apar_id`, `client` | Active customers with no current receivable - RECENT_ACTIVITY candidates |
| Open transactions where customer has active collection case | `apar_id`, `collect_flag` | Cross-check transaction collect_status against customer master collect_flag |
| Transaction currency does not match customer default currency | `currency`, `apar_id` | May be valid but worth flagging volume |
| Transaction tax code differs from customer default tax code | `tax_code`, `apar_id` | May be valid override or data entry error |

---

## Outstanding Questions — Parliament Team

| # | Question |
|---|---|
| 1 | What are the exact values Unit4 uses in voucher_type to distinguish invoices from credit notes? Required before credit note checks can be run in Python |
| 2 | Are open credit notes with no matching open invoice always an error, or can they legitimately sit open awaiting offset against a future invoice? AR team to confirm before flagging as issues |
| 3 | Are transactions in active collection (collect_status populated) expected to be migrated or held pending resolution? |
| 4 | What reminder level is considered high risk for migration purposes? AR team to confirm threshold |