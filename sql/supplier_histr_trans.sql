-- ============================================================
-- HOW TO RUN
-- Run against Agresso_HoC  → save as supplier_history_HOC.csv
-- Run against agresso_HoL  → save as supplier_history_HOL.csv
-- Server: mdata837
-- ============================================================

SELECT
    -- === IDENTITY ===
    h.client,                    -- Internal Unit4 client/fund code (not the house identifier)
    h.apar_id,                   // Supplier ID - links to asuheader.apar_id
    h.voucher_no,                // Unique transaction number
    h.sequence_no,               // Line number within the transaction

    -- === TRANSACTION DETAIL ===
    h.voucher_type,              // Transaction type e.g. invoice, credit note, payment
    h.voucher_date,              // Date transaction was posted
    h.trans_date,                // Original transaction date - used for 18 month filter
    h.status,                    // C=Closed/paid, N=was open now historical

    -- === AMOUNTS ===
    h.amount,                    // Original amount in local currency
    h.rest_amount,               // Should be zero for historical - flags issue if not
    h.currency,                  // Transaction currency

    -- === REFERENCES ===
    h.orig_reference             // Links credit note to original invoice voucher_no

FROM asuhistr h
WHERE h.trans_date >= DATEADD(MONTH, -18, GETDATE())  -- 18 month window; SQL Server syntax
ORDER BY h.apar_id, h.trans_date;


## Data Quality Tests — asuhistr (AP Transaction History, 18 Months)

### Standalone Tests

| Test | Type | Fields | Notes |
|---|---|---|---|
| Total historical transaction count per House | Completeness | `client`, `apar_id` | |
| Historical transactions where rest_amount is not zero | Consistency | `rest_amount`, `voucher_no` | Transaction moved to history without being fully settled - should always be zero |
| Missing trans_date | Completeness | `trans_date` | Critical - drives the 18 month scope filter |
| Credit notes missing orig_reference | Completeness | `voucher_type`, `orig_reference` | |
| Duplicate voucher_no and sequence_no combinations | Duplicate | `voucher_no`, `sequence_no`, `client` | Should be unique - duplicates indicate a data integrity issue |
| Transactions with missing amount | Completeness | `amount` | |
| Split by voucher_type — invoices vs credit notes vs payments | Completeness | `voucher_type`, `client` | Understand composition of historical transactions |

### Tests Requiring Join to asuheader in Python

| Test | Type | Fields | Notes |
|---|---|---|---|
| Historical transactions where apar_id does not exist in asuheader | Consistency | `apar_id`, `client` | Orphaned historical transaction - no parent supplier record |
| Historical transactions against a closed or terminated supplier | Consistency | `apar_id`, `status` | May be expected but worth flagging volume |
| Suppliers with history in last 18 months but no open transactions | Completeness | `apar_id`, `client` | RECENT_ACTIVITY only - in migration scope but no current liability |

### Tests Requiring Join to asutrans in Python

| Test | Type | Fields | Notes |
|---|---|---|---|
| Reconciliation check — amount minus historical payments vs rest_amount in asutrans | Consistency | `voucher_no`, `amount`, `rest_amount` | Does the payment history add up to the outstanding balance on the open invoice |
| Credit notes in history where orig_reference matches a still-open invoice in asutrans | Consistency | `orig_reference`, `voucher_no` | Credit note is closed but the invoice it relates to is still open - may indicate partial credit or misapplication |
| Suppliers with OPEN_TRANSACTIONS only and no history in 18 months | Consistency | `apar_id`, `client` | Outstanding invoice but no recent activity - could be a very old parked invoice needing review |

### Tests Requiring Join to Both asuheader and asutrans in Python

| Test | Type | Fields | Notes |
|---|---|---|---|
| Migration scope count vs full active population | Completeness | `apar_id`, `client` | Full population from 10a vs suppliers appearing in asutrans or asuhistr |
| Split by inscope_reason — OPEN_TRANSACTIONS / RECENT_ACTIVITY / BOTH | Completeness | `apar_id`, `client` | Derived by comparing presence across all three extracts |
| Archive candidate list | Completeness | `apar_id`, `client` | In 10a but absent from both asutrans and asuhistr - no open items and no recent activity |
| RECENT_ACTIVITY only suppliers | Completeness | `apar_id`, `inscope_reason` | In asuhistr within 18 months but not in asutrans |
| OPEN_TRANSACTIONS only suppliers | Completeness | `apar_id`, `inscope_reason` | In asutrans but not in asuhistr within 18 months |



## supplier_history.sql
## Source: asuhistr
## Filter: trans_date >= 18 months, both Houses
## Purpose: Historical closed transactions for the last 18 months - used to identify 
##          recently active suppliers for migration scoping. 

---

## Assumptions

| # | Assumption |
|---|---|
| 1 | 18 month date filter on trans_date is the correct field to determine recent activity |
| 2 | rest_amount should always be zero in asuhistr - transactions are only moved here when fully settled |
| 3 | voucher_type values for invoices vs credit notes are unknown - to be confirmed by Parliament |
| 4 | orig_reference on a credit note points to the voucher_no of the original invoice |
| 5 | A supplier appearing in asuhistr within 18 months is considered recently active for scoping purposes regardless of whether they have open transactions |
| 6 | The 18 month window will need adjusting once go-live date is confirmed |
| 7 | Both Houses exist as separate client codes within the same Unit4 instance |
| 8 | [HOC_CLIENT] and [HOL_CLIENT] are placeholders - actual client codes to be confirmed by Parliament |

---

## Data Quality Tests

### Completeness — Standalone

| Test | Fields | Notes |
|---|---|---|
| Total historical transaction count per House | `client`, `apar_id` | |
| Split by voucher_type — invoices vs credit notes vs payments | `voucher_type`, `client` | Understand composition of historical transactions |
| Transactions with missing amount | `amount` | |
| Missing trans_date | `trans_date` | Critical - drives the 18 month scope filter |
| Credit notes missing orig_reference | `voucher_type`, `orig_reference` | |

### Consistency — Standalone

| Test | Fields | Notes |
|---|---|---|
| Historical transactions where rest_amount is not zero | `rest_amount`, `voucher_no` | Transaction moved to history without being fully settled - should always be zero |
| Duplicate voucher_no and sequence_no combinations | `voucher_no`, `sequence_no`, `client` | Should be unique - duplicates indicate a data integrity issue |

### Consistency — Joined to asuheader in Python

| Test | Fields | Notes |
|---|---|---|
| Historical transactions where apar_id is not present in active supplier master | `apar_id`, `client` | Either orphaned transaction or transaction against an inactive supplier - either needs investigation |

### Completeness — Joined to asuheader in Python

| Test | Fields | Notes |
|---|---|---|
| Suppliers with history in last 18 months but no open transactions | `apar_id`, `client` | RECENT_ACTIVITY only - in migration scope but no current liability |

### Consistency — Joined to asutrans in Python

| Test | Fields | Notes |
|---|---|---|
| Credit notes in history where orig_reference matches a still-open invoice in asutrans | `orig_reference`, `voucher_no` | Credit note is closed but related invoice is still open - may indicate partial credit or misapplication |
| Suppliers with open transactions but no history in last 18 months | `apar_id`, `client` | Outstanding invoice but no recent activity - could be a very old parked invoice needing review before cutover |

### Completeness — Joined to Both asuheader and asutrans in Python

| Test | Fields | Notes |
|---|---|---|
| Migration scope count vs full active population | `apar_id`, `client` | Suppliers in asuheader vs those appearing in asutrans or asuhistr |
| Archive candidate list | `apar_id`, `client` | In asuheader but absent from both asutrans and asuhistr - no open items and no recent activity |
| Split by inscope_reason — OPEN_TRANSACTIONS / RECENT_ACTIVITY / BOTH | `apar_id`, `client` | Derived by comparing presence across all three extracts |
| RECENT_ACTIVITY only suppliers | `apar_id`, `client` | In asuhistr within 18 months but not in asutrans |
| OPEN_TRANSACTIONS only suppliers | `apar_id`, `client` | In asutrans but not in asuhistr within 18 months |

---

## Outstanding Questions — Parliament Team

| # | Question |
|---|---|
| 1 | What are the exact values Unit4 uses in `voucher_type` to distinguish invoices from credit notes? Required before credit note checks can be run |
| 2 | What is the confirmed go-live date? The 18 month lookback date in the WHERE clause needs to be set to 18 months prior to cutover date, not today's date |