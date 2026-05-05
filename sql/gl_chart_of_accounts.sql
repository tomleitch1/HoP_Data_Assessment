-- ============================================================
-- gl_chart_of_accounts.sql
-- Source:  aglaccounts
-- Filter:  Both Houses, no status filter - full population
-- Purpose: Full chart of accounts extract. Status filter applied
--          in Python depending on test - active only for migration
--          scope, full population for backward compatibility checks
--          against agltransact and aglyearend
-- ============================================================

-- ============================================================
-- HOW TO RUN
-- Run against Agresso_HoC  → save as gl_chart_of_accounts_HOC.csv
-- Run against agresso_HoL  → save as gl_chart_of_accounts_HOL.csv
-- Server: mdata837
-- ============================================================

SELECT
    -- === IDENTITY ===
    a.client,                    -- Internal Unit4 client/fund code (not the house identifier)
    a.account,                   -- Account code - primary key
    a.description,               -- Account description
    a.account_grp,               -- Account group code - links to aglaccgrp
    a.account_type,              -- GL=General Ledger, AP=Accounts Payable, AR=Accounts Receivable
    a.status,                    -- N=Active, C=Closed, P=Parked, T=Terminated

    -- === CLASSIFICATION ===
    a.res_bal,                   -- R=Profit and Loss account, B=Balance Sheet account
    a.bflag,                     -- Account behaviour flag - 4=Asset, 7=Reconciliation, 9=Prepayment etc
    a.account_rule,              -- Account rule ID - controls how transactions are posted

    -- === PERIOD VALIDITY ===
    a.period_from,               -- First period this account is valid from
    a.period_to,                 -- Last period this account is valid to

    -- === AUDIT ===
    a.last_update,               -- Last time this record was modified
    a.head_account               -- Headquarter account - links to consolidated account if used

FROM aglaccounts a
ORDER BY a.account;



## gl_chart_of_accounts.sql
## Source: aglaccounts
## Filter: Both Houses, no status filter - full population
## Purpose: Full chart of accounts extract. Status filter applied in 
##          Python - active only for migration scope, full population 
##          for backward compatibility checks against transactions 
##          and year end balances

---

## Assumptions

| # | Assumption |
|---|---|
| 1 | No status filter applied in SQL - all accounts extracted regardless of active/inactive |
| 2 | status = 'N' filter applied in Python for migration scope and active account DQ tests |
| 3 | Full population retained for backward compatibility - checking whether closed accounts still have live transactions or year end balances against them |
| 4 | account_type distinguishes GL accounts from AP and AR control accounts - both in scope for migration |
| 5 | res_bal = 'R' identifies P&L accounts and res_bal = 'B' identifies balance sheet accounts - critical for opening balance migration logic |
| 6 | period_from and period_to define the valid date range for each account - accounts outside their valid period range should not have live transactions |
| 7 | head_account is included but whether Parliament uses consolidated account mapping is unknown - included for completeness |
| 8 | bflag = 7 identifies reconciliation accounts - these are the AP and AR control accounts that must reconcile to sub-ledger totals |
| 9 | Both Houses exist as separate client codes - accounts may differ between Houses and will require consolidation decisions |
| 10 | [HOC_CLIENT] and [HOL_CLIENT] are placeholders - actual client codes to be confirmed by Parliament |

---

## Data Quality Tests

### Completeness — Active Accounts Only (status = 'N' in Python)

| Test | Fields | Notes |
|---|---|---|
| Total active account count per House | `client`, `status` | Baseline population for migration scope |
| Missing account description | `description`, `account` | Account with no description cannot be meaningfully reviewed by business |
| Missing account group | `account_grp` | All accounts should belong to a group for reporting hierarchy |
| Missing res_bal classification | `res_bal` | Must be R or B - drives opening balance migration logic |
| Missing account_rule | `account_rule` | Controls posting behaviour - blank may cause posting failures in new system |
| Missing period_from | `period_from` | Should always be populated |

### Validity — Active Accounts Only (status = 'N' in Python)

| Test | Fields | Notes |
|---|---|---|
| res_bal value not R or B | `res_bal` | Only valid values are R (P&L) and B (Balance Sheet) |
| account_type value not GL, AP, or AR | `account_type` | Only valid values per data dictionary |
| period_from greater than period_to | `period_from`, `period_to` | Invalid period range - account cannot be active |
| Accounts where period_to is in the past but status still N | `period_to`, `status` | Period expired but account still active |

### Consistency — Active Accounts Only (status = 'N' in Python)

| Test | Fields | Notes |
|---|---|---|
| AP control accounts (account_type = AP) count per House | `account_type`, `client` | Should be a small number - flag for sub-ledger reconciliation |
| AR control accounts (account_type = AR) count per House | `account_type`, `client` | Should be a small number - flag for sub-ledger reconciliation |
| Reconciliation accounts (bflag = 7) that are not AP or AR type | `bflag`, `account_type` | Reconciliation flag should align with AP/AR account type |
| P&L accounts (res_bal = R) assigned to balance sheet account group | `res_bal`, `account_grp` | Classification mismatch - account type contradicts its group |
| Balance sheet accounts (res_bal = B) assigned to P&L account group | `res_bal`, `account_grp` | Classification mismatch - account type contradicts its group |

### Duplicates — Full Population

| Test | Fields | Notes |
|---|---|---|
| Duplicate account codes within the same House | `client`, `account` | Should be prevented by unique index but worth confirming |
| Same account description used for different account codes within same House | `client`, `description` | May indicate duplicate accounts with slightly different codes |
| Account codes that exist in HoC but not HoL and vice versa | `account`, `client` | Candidates for consolidation decisions - not errors but need review |
| Accounts with identical descriptions across both Houses but different codes | `description` across both clients | Strong consolidation candidates |

### Scope — Active Accounts Only (status = 'N' in Python)

| Test | Fields | Notes |
|---|---|---|
| Total accounts in migration scope by res_bal (R vs B) | `res_bal`, `client` | P&L vs balance sheet split - affects opening balance migration approach |
| Total accounts in migration scope by account_type | `account_type`, `client` | GL vs AP vs AR split |
| Stale accounts - last_update older than 3 years | `last_update`, `client` | May indicate accounts never used or maintained |

### Backward Compatibility — Full Population joined to agltransact in Python

| Test | Fields | Notes |
|---|---|---|
| Transactions in agltransact referencing accounts that do not exist in aglaccounts | `account`, `client` | Orphaned transactions - account code used in posting has no master record |
| Transactions against closed or terminated accounts | `account`, `status` | Live transactions posted to inactive accounts |

### Backward Compatibility — Full Population joined to aglyearend in Python

| Test | Fields | Notes |
|---|---|---|
| Year end balances referencing accounts that do not exist in aglaccounts | `account`, `client` | Balance exists for account with no master record |
| Year end balances against closed or terminated accounts | `account`, `status` | Balance carried on inactive account |

---

## Outstanding Questions — Parliament Team

| # | Question |
|---|---|
| 1 | What are the client codes for House of Commons and House of Lords in Unit4? |
| 2 | Does Parliament use head_account for consolidated reporting? If so are parent accounts in migration scope? |
| 3 | What are the specific account codes for the AP and AR control accounts in each House? Required for sub-ledger reconciliation tests |
| 4 | Are there any accounts Parliament considers active that have a status other than N? |
| 5 | Does Parliament operate separate Charts of Accounts for HoC and HoL or is there a shared structure? This determines whether account code differences between Houses are expected or errors |