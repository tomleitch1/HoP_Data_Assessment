-- ============================================================
-- gl_opening_balances.sql
-- Source:  aglyearend
-- Filter:  Both Houses, current fiscal year closing balances
-- Purpose: Year end GL balances per account and dimension 
--          combination. Used as opening balance in new ERP.
--          Assumes 1 April go-live - full year end closing 
--          position migrated as opening balance.
--
-- CONTINGENCY: If go-live slips to mid-year, this script must
--          be replaced with an agltransact aggregation approach.
--          See assumptions for detail.
-- ============================================================

SELECT
    -- === IDENTITY ===
    y.client,                    -- Which House - HoC or HoL
    y.account,                   -- Account code - links to aglaccounts
    y.fiscal_year,               -- Financial year this balance relates to
    y.period,                    -- Period within fiscal year - year end period TBC with Parliament

    -- === DIMENSION CODING STRING ===
    y.dim_1,                     -- Dimension 1 value - attribute_id to be confirmed from profile query
    y.dim_2,                     -- Dimension 2 value
    y.dim_3,                     -- Dimension 3 value
    y.dim_4,                     -- Dimension 4 value
    y.dim_5,                     -- Dimension 5 value
    y.dim_6,                     -- Dimension 6 value
    y.dim_7,                     -- Dimension 7 value

    -- === AMOUNTS ===
    y.amount,                    -- Balance in local currency (GBP)
    y.cur_amount,                -- Balance in transaction currency if foreign
    y.currency,                  -- Currency code
    y.dc_flag,                   -- Debit/Credit flag

    -- === CLASSIFICATION ===
    y.voucher_type,              -- Transaction type that generated this balance
    y.tax_code,                  -- Tax code associated with the balance
    y.apar_id,                   -- Customer or supplier ID if sub-ledger control account
    y.apar_type                  -- R=Customer, P=Supplier - populated on control accounts only

FROM aglyearend y
WHERE y.client IN ('[HOC_CLIENT]', '[HOL_CLIENT]')
  AND y.fiscal_year = '[CURRENT_FISCAL_YEAR]'  -- e.g. 2025 for FY2025/26 - confirm format with Parliament
  AND y.period = '[YEAR_END_PERIOD]'            -- Final period of fiscal year - likely period 12 or 15 depending on adjustments
ORDER BY y.client, y.account, y.dim_1;


## gl_opening_balances.sql
## Source: aglyearend
## Filter: Both Houses, current fiscal year closing balances
## Purpose: Year end GL balances per account and dimension combination.
##          Used as opening balance in new ERP at cutover.
##          Primary approach assumes 1 April go-live.

---

## Assumptions

| # | Assumption |
|---|---|
| 1 | aglyearend is the correct source for opening balances - holds pre-aggregated year end positions per coding string |
| 2 | 1 April go-live assumed - year end closing balance is the correct opening position for the new system |
| 3 | fiscal_year filter value is Parliament-specific - format to be confirmed (e.g. 2025 or 202526) |
| 4 | Year end period is the final posted period - likely period 12 but may be period 13, 14, or 15 if Parliament posts year end adjustments. Period to be confirmed with Parliament |
| 5 | dim_1 through dim_7 map to Parliament's configured dimensions - attribute_id mapping to be confirmed from gl_dimension_values.sql profile query |
| 6 | apar_id and apar_type are populated on AP and AR control account balances only - used for sub-ledger reconciliation tests in Python |
| 7 | P&L accounts (res_bal = R in aglaccounts) carry a zero balance at year end after profit and loss transfer - non-zero P&L balances at year end flag a potential issue |
| 8 | Balance sheet accounts (res_bal = B in aglaccounts) carry forward their closing balance as the opening balance for the new year |
| 9 | Both Houses extracted separately - consolidation of balances handled in new ERP not in migration |
| 10 | [HOC_CLIENT], [HOL_CLIENT], [CURRENT_FISCAL_YEAR], and [YEAR_END_PERIOD] are placeholders to be confirmed by Parliament |

---

## CONTINGENCY NOTE — Mid-Year Go-Live

If go-live is confirmed as mid-year rather than 1 April, this script
must be replaced with an agltransact aggregation approach:

- Source changes from aglyearend to agltransact
- Filter changes from fiscal_year + year_end_period to 
  all periods up to and including the cutover period
- Aggregation logic groups by account + dim_1 through dim_7 
  and sums amount to derive balance at cutover date
- Volume will be significantly larger - every individual 
  posting line rather than pre-aggregated year end rows
- Period 13/14/15 adjustment postings must be included
- Partial year P&L balances must be carried rather than zeroed

This contingency script should be developed as soon as a 
mid-year go-live date is confirmed.

---

## Data Quality Tests

### Completeness — Standalone

| Test | Fields | Notes |
|---|---|---|
| Total balance rows per House | `client` | Baseline volume check |
| Total debit and credit balance per House | `client`, `dc_flag`, `amount` | High level sanity check on scale |
| Accounts with no year end balance | `account`, `client` | Active accounts in aglaccounts with no row in aglyearend - may be valid if never used |
| Missing amount | `amount`, `account` | Should always be populated |
| Missing fiscal_year or period | `fiscal_year`, `period` | Should always be populated |
| Foreign currency balances with missing cur_amount | `currency`, `cur_amount` | If currency != GBP then cur_amount should be populated |

### Validity — Standalone

| Test | Fields | Notes |
|---|---|---|
| Duplicate rows per account and full dimension coding string | `client`, `account`, `dim_1` through `dim_7`, `fiscal_year`, `period` | Should be unique per coding string - duplicates indicate a posting integrity issue |
| P&L accounts with non-zero closing balance | `account`, `amount`, `res_bal` | Joined to aglaccounts in Python - P&L should be zero at year end after profit transfer |
| Balances in unexpected periods | `period` | All balances should be in the confirmed year end period - rows in other periods may indicate incomplete year end processing |

### Consistency — Standalone

| Test | Fields | Notes |
|---|---|---|
| Total GL debits equal total GL credits | `amount`, `dc_flag`, `client` | Fundamental balance check - GL must net to zero. Any difference must be explained before cutover |
| Balance sheet net position per House | `amount`, `dc_flag`, `client` | Assets minus liabilities plus equity should net to zero |
| Foreign currency balances with no exchange rate context | `currency`, `amount`, `cur_amount` | Where currency != GBP, amount and cur_amount should be consistent |

### Consistency — Joined to aglaccounts in Python

| Test | Fields | Notes |
|---|---|---|
| Balances referencing accounts that do not exist in aglaccounts | `account`, `client` | Orphaned balance - account code in aglyearend has no master record |
| Balances against closed or terminated accounts | `account`, `status` | Year end balance carried on inactive account |
| P&L account balances not zeroed at year end | `account`, `res_bal`, `amount` | Joined on account - non-zero P&L balance indicates year end close not completed |
| AP control account balance | `account`, `account_type`, `amount` | Joined on account where account_type = AP - used for sub-ledger reconciliation |
| AR control account balance | `account`, `account_type`, `amount` | Joined on account where account_type = AR - used for sub-ledger reconciliation |

### Consistency — Joined to agldimvalue in Python

| Test | Fields | Notes |
|---|---|---|
| Balances referencing dim values that do not exist in agldimvalue | `dim_1` through `dim_7`, `client` | Orphaned dimension value on a balance - coding string cannot be loaded into new system |
| Balances referencing inactive dimension values | `dim_value`, `status` | Balance coded to closed or terminated segment |

### Reconciliation — Joined to AP and AR extracts in Python

| Test | Fields | Notes |
|---|---|---|
| AP control account balance agrees to sum of open supplier rest_amount in asutrans | `amount` vs `rest_amount` | Critical reconciliation - difference must be zero or explained before cutover |
| AR control account balance agrees to sum of open customer rest_amount in acutrans | `amount` vs `rest_amount` | Critical reconciliation - difference must be zero or explained before cutover |

---

## Outstanding Questions — Parliament Team

| # | Question |
|---|---|
| 1 | What is the fiscal_year value format used in Unit4 - e.g. 2025 or 202526? |
| 2 | What is the final posted period at year end - period 12, 13, 14, or 15? Does Parliament post period 13/14/15 adjustment journals? |
| 3 | What are the AP and AR control account codes in each House? Required for sub-ledger reconciliation tests |
| 4 | Has the year end close process been completed for the current fiscal year? If not, aglyearend may not yet reflect the final position |
| 5 | Is go-live confirmed as 1 April? If not, contingency agltransact approach needs to be developed |