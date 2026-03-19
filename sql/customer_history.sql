-- ============================================================
-- customer_history.sql
-- Source:  acuhistr
-- Filter:  trans_date >= 18 months, both Houses
-- Purpose: Historical closed AR transactions for last 18 months.
--          Used to identify recently active customers for migration 
--          scoping only. Not migrated itself - goes to archive.
-- ============================================================

SELECT
    -- === IDENTITY ===
    h.client,                    // Which House - HoC or HoL
    h.apar_id,                   // Customer ID - links to acuheader.apar_id
    h.voucher_no,                // Unique transaction number
    h.sequence_no,               // Line number within the transaction

    -- === TRANSACTION DETAIL ===
    h.voucher_type,              // Transaction type e.g. invoice, credit note, receipt
    h.voucher_date,              // Date transaction was posted
    h.trans_date,                // Original transaction date - used for 18 month filter
    h.status,                    // C=Closed/paid

    -- === AMOUNTS ===
    h.amount,                    // Original amount in local currency
    h.rest_amount,               // Should be zero for historical - flags issue if not
    h.currency,                  // Transaction currency

    -- === REFERENCES ===
    h.orig_reference             // Links credit note to original invoice voucher_no

FROM acuhistr h
WHERE h.client IN ('[HOC_CLIENT]', '[HOL_CLIENT]')
  AND h.trans_date >= DATE_SUB(NOW(), INTERVAL 18 MONTH)
ORDER BY h.client, h.apar_id, h.trans_date;


## customer_history.sql
## Source: acuhistr
## Filter: trans_date >= 18 months, both Houses
## Purpose: Historical closed AR transactions for last 18 months - used to 
##          identify recently active customers for migration scoping.
##          Not migrated itself - goes to archive.

---

## Assumptions

| # | Assumption |
|---|---|
| 1 | 18 month date filter on trans_date is the correct field to determine recent activity |
| 2 | rest_amount should always be zero in acuhistr - transactions only moved here when fully settled |
| 3 | voucher_type values for invoices vs credit notes are unknown - to be confirmed by Parliament |
| 4 | orig_reference on a credit note points to the voucher_no of the original invoice |
| 5 | A customer appearing in acuhistr within 18 months is considered recently active for scoping regardless of whether they have open transactions |
| 6 | The 18 month window will need adjusting once go-live date is confirmed |
| 7 | Both Houses exist as separate client codes within the same Unit4 instance |
| 8 | [HOC_CLIENT] and [HOL_CLIENT] are placeholders - actual client codes to be confirmed by Parliament |

---

## Data Quality Tests

### Completeness — Standalone

| Test | Fields | Notes |
|---|---|---|
| Total historical transaction count per House | `client`, `apar_id` | |
| Split by voucher_type — invoices vs credit notes vs receipts | `voucher_type`, `client` | Understand composition of historical transactions |
| Transactions with missing amount | `amount` | |
| Missing trans_date | `trans_date` | Critical - drives the 18 month scope filter |
| Credit notes missing orig_reference | `voucher_type`, `orig_reference` | |

### Consistency — Standalone

| Test | Fields | Notes |
|---|---|---|
| Historical transactions where rest_amount is not zero | `rest_amount`, `voucher_no` | Transaction moved to history without being fully settled - should always be zero |
| Duplicate voucher_no and sequence_no combinations | `voucher_no`, `sequence_no`, `client` | Should be unique - duplicates indicate a data integrity issue |

### Completeness — Joined to acuheader in Python

| Test | Fields | Notes |
|---|---|---|
| Customers with history in last 18 months but no open transactions | `apar_id`, `client` | RECENT_ACTIVITY only - in migration scope but no current outstanding balance |

### Consistency — Joined to acutrans in Python

| Test | Fields | Notes |
|---|---|---|
| Credit notes in history where orig_reference matches a still-open invoice in acutrans | `orig_reference`, `voucher_no` | Credit note closed but related invoice still open - may indicate partial credit or misapplication |
| Customers with open transactions but no history in last 18 months | `apar_id`, `client` | Outstanding invoice but no recent activity - could be a very old parked item needing review |

### Completeness — Joined to Both acuheader and acutrans in Python

| Test | Fields | Notes |
|---|---|---|
| Migration scope count vs full active customer population | `apar_id`, `client` | Customers in acuheader vs those appearing in acutrans or acuhistr |
| Archive candidate list | `apar_id`, `client` | In acuheader but absent from both acutrans and acuhistr - no open items and no recent activity |
| Split by inscope_reason — OPEN_TRANSACTIONS / RECENT_ACTIVITY / BOTH | `apar_id`, `client` | Derived by comparing presence across all three extracts |
| RECENT_ACTIVITY only customers | `apar_id`, `client` | In acuhistr within 18 months but not in acutrans |
| OPEN_TRANSACTIONS only customers | `apar_id`, `client` | In acutrans but not in acuhistr within 18 months |

---

## Outstanding Questions — Parliament Team

| # | Question |
|---|---|
| 1 | What are the exact values Unit4 uses in voucher_type to distinguish invoices, credit notes, and receipts? |
| 2 | What is the confirmed go-live date? The 18 month lookback date needs to be set to 18 months prior to cutover, not today's date |