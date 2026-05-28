# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

**Parliament Finance Systems Programme – Unit4 Data Quality Assessment Dashboard**

A Dash/Plotly web application that executes data quality (DQ) checks against financial data extracted from Parliament's legacy system (Unit4 predecessor), covering five domains: General Ledger, Suppliers/AP, Customers/AR, Fixed Assets, and PBF. Data arrives as CSV exports from two parliamentary houses (HoC and HoL) and is assessed against ~80+ rules across completeness, validity, referential integrity, and consistency dimensions.

---

## Two-Laptop Workflow

**This project runs across two machines — all code changes must be made here and pushed, then pulled on the Parliament laptop.**

| Machine | Role | Claude Code | Real data |
|---|---|---|---|
| Development laptop (this one) | Code changes, dummy data, git push | Yes | No |
| Parliament laptop (`leitchtb`) | Runs against live data, git pull only | No | Yes |

### Standard workflow
1. Make and test code changes here (against dummy data in `data/`)
2. `git push` from this machine
3. On Parliament laptop: `git pull` then `python run_dashboard.py`

### Parliament laptop setup (already done)
- Server: `mdata837`, databases: `Agresso_HoC` and `agresso_HoL`
- Git installed, repo cloned to `C:\Users\leitchtb\HoP_Data_Assessment`
- Dependencies installed: `pip install dash plotly pandas faker python-dotenv dash-iconify`
- Real CSVs live in `data/` on the Parliament laptop — **never commit the `data/` folder**
- App confirmed working with real supplier data as of May 2026

### Getting the real data CSVs
Run the SQL files in `sql/` against each database in SSMS (server `mdata837`). Each file has a `HOW TO RUN` header with the exact database and output filename. Copy-paste results via Excel to avoid SSMS encoding issues. Place files in the correct subfolder under `data/` (see Data Folder Structure below).

---

## Running the App

```bash
python run_dashboard.py              # all tabs
python run_dashboard.py suppliers    # suppliers + AP only
python run_dashboard.py gl           # GL only
python run_dashboard.py customers    # customers + AR only
python run_dashboard.py assets       # assets only
```

App starts at `http://127.0.0.1:8050`. No build step. Place CSV extracts in `data/` before launching.

**Per-tab mode** — passing a tab name loads only that domain's CSV files and runs only its DQ checks. Use this on the Parliament laptop to reduce startup time when working on one domain. `ap` and `ar` are accepted as aliases for `suppliers` and `customers`. Implemented via `DASHBOARD_TAB` env var read by `app.py`; `load_data(tab=)` and `run_dq_analysis(frames, tab=)` in `data_engine.py` both accept the filter.

There are no automated tests. The scripts in `scripts/` generate dummy data for development on this machine:
```bash
python scripts/generate_ap_dummy_data.py   # Supplier / AP data (HOC + HOL split files)
python scripts/generate_dummy_data.py      # Customer / AR data
python scripts/generate_asset_data.py      # Asset data
python scripts/generate_gl_dummy_data.py   # GL data
```

### Tracker Generator

Generates an Excel tracker for a specific tab and house, listing only checks with at least one failing record:
```bash
python scripts/generate_tracker.py suppliers HOC
python scripts/generate_tracker.py suppliers HOL
python scripts/generate_tracker.py gl HOC
python scripts/generate_tracker.py assets HOL
```
Output saved to `trackers/<tab>_tracker_<HOUSE>.xlsx`. Columns: Test Reference, Description, Dimension, Severity, Failing Records, Total Assessed, Error Rate, RAG, Comments, Source System Cleansing Complete. Run on Parliament laptop against real data for a meaningful tracker.

---

## Architecture

Four strictly separated layers, all initialized once at startup in `app.py`:

```
SQL extracts → data/ CSVs → data_engine.load_data() → frames dict
                                  ↓
                          run_dq_analysis(frames) → dq_results DataFrame
                          build_aging_analysis(frames) → aging_results dict
                                  ↓
                          Dash tab renderers (tabs/*.py)
```

**Config (`dashboard/core/config.py`)** — The single source of truth for schema mapping, status codes, thresholds, and scope registration. When live Unit4 data arrives with different column names or status codes, only this file changes. Key objects:
- `Scope(IntEnum)`: All 11 data scope IDs
- `COLUMN_MAP`: Maps semantic names (e.g. `'name'`) to actual CSV column headers
- `SupplierConfig`, `CustomerConfig`, `GLConfig`: Threshold constants (active statuses, stale days, etc.)
- `SCOPE_CONFIG`: Registers each domain tab with its scope IDs, tables, and aging config
- `RAG_THRESHOLDS`: Per-severity dict of `(green_threshold, amber_threshold)` error-rate % cutoffs:
  ```python
  RAG_THRESHOLDS = {
      'Critical': (1,  5),
      'High':     (3,  10),
      'Medium':   (5,  15),
      'Low':      (10, 25),
  }
  ```
  RAG is computed in `data_engine.py` as: Green if `error_rate <= green_t`, Amber if `<= amber_t`, else Red.

**Rules (`dashboard/core/rules/*.py`)** — Declarative DQ checks as 12-element tuples returned by `get_*_checks()` functions. The lambda at position 11 receives a DataFrame (or `df, frames` for join checks) and returns a boolean mask of **failing** records. Do not put data loading or aggregation logic here.

Tuple format:
```python
('CHECK_ID', Scope.SUPPLIERS, 'Object Name', 'Dimension', 'Severity',
 'Human-readable description', 'Business intent', 'Remediation action',
 'source_table', 'joined_table_or_None',
 'SQL equivalent (documentation only)',
 lambda df: df['column'].isna())
```

**Engine (`dashboard/data_engine.py`)** — Loads CSVs, executes every rule lambda, computes pass rates and RAG status, and produces a flat `dq_results` DataFrame with columns: `check_id, scope_id, object, house, dimension, severity, description, intent, total, failing, passing, error_rate, pass_rate, rag, remediation, table, joined_table`. Also exposes `get_failing_records(check_id, house, frames)` for the modal drill-down.

**UI (`dashboard/tabs/*.py` + `dashboard/app.py`)** — Tab renderers consume `dq_results` filtered to their scope IDs and `frames` for volumetrics. Each tab follows the same pattern: dimension scorecard → dimension grid (charts) → dimensions table → optional aging analysis. `app.py` holds all Dash callbacks.

---

## Data Folder Structure

The `data/` folder is in `.gitignore` — it is **never committed**. Each machine maintains its own copy (dummy data here, real data on Parliament laptop).

```
data/
├── suppliers/   supplier_master_HOC.csv, supplier_master_HOL.csv
│                supplier_open_trans_HOC/HOL.csv
│                supplier_history_HOC/HOL.csv
├── customers/   customer_master_HOC/HOL.csv
│                customer_open_trans_HOC/HOL.csv
│                customer_history_HOC/HOL.csv
├── gl/          gl_chart_of_accounts_HOC/HOL.csv
│                gl_dimension_values_HOC/HOL.csv
│                gl_opening_balances_HOC/HOL.csv
│                gl_transact_dimensions_HOC/HOL.csv
│                gl_journals_HOC/HOL.csv
└── assets/      asset_master_HOC/HOL.csv, asset_depreciation_HOC/HOL.csv
                 asset_balances_HOC/HOL.csv, asset_trans_flags_HOC/HOL.csv
                 asset_groups_HOC/HOL.csv
```

`data_engine.py` uses a `SUBDIR` map and `_data_path()` helper to resolve paths — adding a new file means registering it in `SUBDIR` and `split_files` in `load_data()`. There is no longer a `file_map` for single combined files — all tables use split files.

---

## HOC/HOL Data Split

All tables in every domain use **per-house split files** (`*_HOC.csv` + `*_HOL.csv`). The engine concatenates them and assigns `house` from the filename suffix — **not** from the `client` column. The `client` column contains internal Unit4 fund codes and must not be used for house filtering anywhere.

**Confirmed Unit4 client codes:**
- HoC (`Agresso_HoC`): `CA`, `CM` — these are the only two in scope. `CF` exists in the database but is not extracted.
- HoL (`agresso_HoL`): `LA`

All DQ analysis runs per-house. `dq_results` always has a `house` column. Charts typically show HOC and HOL side by side.

---

## Key Workflows

### Updating for Live Data (Column Names / Status Codes)
Edit only `dashboard/core/config.py`:
- Column name change → update `COLUMN_MAP` right-hand side
- Status code change → update the relevant `*Config` class constant

### Adding a DQ Rule to an Existing Domain
Add a tuple to the list in the relevant `dashboard/core/rules/*_rules.py`. Use existing tuples in the same file as templates. The engine picks it up automatically via `get_dq_checks()`.

**Intent text style (position 6 in the tuple — "Why this matters"):**
- Lead with the specific condition that must be true: "Every active supplier must have X populated."
- Follow with the consequence if it is not: "Without it, Y will fail / Z cannot be processed."
- Use short declarative sentences. No em dashes. No "Finds/Flags/Identifies" opener.
- Example: *"Payment terms must be assigned to every active supplier. The system uses this field to calculate invoice due dates automatically. A supplier without terms will cause payment runs to fail or require manual intervention on every invoice."*

### Adding a Completely New Dataset and Tab
1. Drop CSVs in `data/`, register in `load_data()` (`file_map` or `split_files`)
2. Add `Scope` enum value and `SCOPE_CONFIG` entry in `config.py`
3. Create `dashboard/core/rules/new_rules.py`, define `get_new_checks()`, import and extend in `data_engine.get_dq_checks()`
4. Create `dashboard/tabs/new_tab.py` (use `customers.py` as template), wire into `app.py` routing

### Adding Critical Field Highlights for a New Rule
Update `get_check_columns()` in `data_engine.py` — maps `check_id` → list of column names to highlight in the modal inspector (source columns appear red, join target columns blue, bridge columns gray).

### Adding a Cross-House Uniqueness Check
Cross-house checks detect when the same identifier (VAT number, bank account, etc.) exists in both HOC and HOL supplier/customer records. Key design constraints:

1. **Lambda signature must be `lambda df, frames:`** — `run_dq_analysis` passes one house at a time as `df`, but the lambda needs the full both-house data from `frames['asuheader']` to compute the cross-house set.
2. **Pattern**: find identifier values appearing in both houses using `frames['asuheader']`, then mask the per-house `df`.
3. **Population filter**: use `status != 'C'` (not-closed), not `status == 'N'` (active only).
4. **`run_dq_analysis` filter**: add the new check IDs to the `elif check_id in [...]` block in the asuheader population filter section so they use `status != 'C'` rather than `status == 'N'`.
5. **`get_check_columns()`**: add the matching identifier column(s) for modal highlighting.
6. **`get_failing_records()`**: the `_XHOUSE_ID_COLS` dict at the top of the cross-house early-return block controls which columns are returned. Add the new check ID there.
7. **Modal rendering**: cross-house checks are identified by `_XHOUSE_CHECKS` set in `app.py`'s `handle_modal_logic`. They skip the single-house filter and render a side-by-side HOC/HOL two-table layout automatically.

---

## Migration Scope

**Target go-live: 1 July 2028 (Period 4, FY 2028/29).** Unit4 remains system of record for FY 2027/28 close (Periods 13–15). The new ERP takes opening balances from the Period 3 close (30 June 2028) and requires Periods 1–3 current-year journals to support Budget vs Actual from Day 1.

The DQ assessment covers the data objects below. Sequence numbers are used throughout the codebase as scope identifiers.

| Seq | Category | Data Object | Key Migration Scope |
|-----|----------|-------------|-------------------|
| 1 | Foundation | Chart of Accounts | Full CoA — all active segments from both houses |
| 2 | Foundation | Exchange Rates | Current FY daily rates + historical covering open balances period |
| 3 | Foundation | Tax Configuration Rules | All active tax codes (VAT 20%, 5%, 0%, COS s41) |
| 4 | Foundation | Fiscal Calendars & Periods | Current FY (2028/29) + next FY (2029/30) period structures |
| 5 | Banking | Banks & Bank Branches | Derived from supplier master (asuheader) — no central bank table in Unit4 |
| 6 | Banking | Bank Accounts (Parliament) | All live Parliament bank accounts (HoC & HoL) |
| 7 | Banking | Outstanding/Unreconciled Bank Items | Uncleared cheques and deposits at 30 June 2028 |
| 8 | Master Data | Finance System Users | Active finance users only — iTrent remains HR system of record |
| 9 | Master Data | Finance Approvers | Active approvers; inactive if approved transactions in current FY |
| 10 | Master Data | Suppliers (Headers & Sites) | Active suppliers with activity in last 18 months or open transactions |
| 11 | Master Data | AR Customers (Headers & Sites) | Active customers transacted in last 18 months or with open transactions |
| 12 | Master Data | Fixed Asset Registry | All active assets — capitalised, non-capitalised, and leased (IFRS16) |
| 13 | Master Data | Asset Depreciation Rules | Active methods, useful lives, residual values by category |
| 14 | Balances | GL Balances | Opening balances at 30 June 2028 — must net to zero across all entities |
| 15 | Open Items | Open Purchase Orders | Approved and open POs with uninvoiced/outstanding balance only |
| 16 | Open Items | Unpaid/Open AP Invoices | All unpaid/partially paid invoices and credit notes at cutover |
| 17 | Open Items | Members' Finance Allowances & Expenses | Unpaid allowance claims and expenses at cutover |
| 18 | Open Items | Open AR Transactions | All open AR invoices and credit/debit memos at cutover |
| 19 | Open Items | Unapplied Cash/Receipts | All open unapplied or on-account receipts at cutover |
| 20 | Balances | Asset Balances | NBV, accumulated depreciation, original cost at 30 June 2028 |
| 21 | Current Year | Current Year Journals | Periods 1–3 (Apr–Jun 2028) journals — required for Budget vs Actual from Day 1 |
| 22 | Current Year | Active Project Transaction History | Full history for projects active at cutover |
| 23 | Budgets | GL Budgets & Forecasts | Current FY (2028/29) budgets and forecasts by period |

**Key dependencies:** CoA (1) → GL Balances (14) → sub-ledgers (16, 18). Banks (5) → Suppliers (10). Asset Rules (13) → Asset Balances (20). GL Balances must reconcile to AP (16), AR (18), and Asset (20) sub-ledger totals before go-live.

**What this dashboard assesses:** Sequences 10 (Suppliers), 11 (Customers), 16 (AP Invoices), 18 (AR Invoices), 20 (Asset Balances), and the GL foundation objects (1, 14). PBF/budgets and Members' expenses are not yet in scope.

---

## Suppliers Tab — Design Details

The suppliers tab has a distinctive layout that other tabs will eventually follow:

**Intro section** (`dashboard/tabs/suppliers.py` — `_render_intro`)
Three scope cards aligned to the migration programme:
- **Seq 10 full-width card** — supplier master breakdown with HOC/HOL columns each showing: migration scope headline number, scope progress bar, Active/Inactive+recent composition tiles, N/P/T status bars with proportional fill, archive candidates. Scoping extract (asuhistr) summary shown as a compact right-aligned note in the dark card header.
- **Seq 16 card** — open AP invoices with per-house status bars (N/R/I/P) and outstanding balance broken down by status with proportional bars.
- **Total Migration banner** — white card with house-coloured pills, Seq 10 + Seq 16 record counts per house with totals.

**Section header** — "Data Quality Checks" with thin top border separates the intro from the DQ analysis below. The old volumetrics cards (duplicates of the scope section) have been removed.

**Volumetrics quirks from real Agresso data:**
- `rest_amount` is already signed (positive = invoice owed, negative = credit note) — sum directly, no dc_flag multiplication
- **asuheader unique key**: `(client, apar_id)` — one row per supplier per client code. HOC has multiple client codes (CA, CF, CM, etc.) so the same supplier apar_id appears multiple times in asuheader with different client values.
- **asutrans unique key**: `(client, apar_id, voucher_no, sequence_no)` — one row per transaction dimension allocation. Each row is a real distinct transaction record.
- `asutrans` structure: the SQL extract already filters `status != 'C'`. Each row is a real transaction record. The same invoice can have multiple rows with different status values (N/P/R/I) representing payment lifecycle stages. **For balance calculations**: sum `rest_amount` directly across all rows.
- **Root cause of phantom row duplication (now fixed)**: `get_failing_records` joins `asutrans` failing rows to `asuheader` to enrich with supplier name. Since asuheader has N rows per `apar_id` (one per client code), joining on `(house, apar_id)` without deduplicating first multiplied every failing row by N. Fix: `drop_duplicates(subset=['client','apar_id'])` before the merge, then join on `(client, apar_id)` — the actual unique key.
- **AP aging analysis** (`build_aging_analysis`) filters to `status.isin(['N','R','I'])` and works correctly. DQ checks use `status != 'C'`. Both `run_dq_analysis` and `get_failing_records` must use the same filter — a mismatch causes the summary count and the modal table to show different numbers.
- `rest_amount` values from SSMS via Excel may arrive as comma-formatted strings (`1,234.56`) — `data_engine.py` strips commas in the numeric column pre-processing step
- Date columns from SSMS arrive as Excel serial numbers (e.g. `45626`) — `_parse_dates()` in `data_engine.py` handles ISO, dd/mm/yyyy, and Excel serial formats. The valid serial range is `20000–55000` (~1954–2050). Pre-2000 dates (e.g. 1993 invoices) exist in the real data — the floor was deliberately set to 20000 to capture them.
- **Payment method codes in real Agresso data**: AS, AU, BB, BO, CA, CH, DD, EF, EU, FC, FP, IB, II, IN, IP, LE, RF, TF, UE, VD, VI. Confirmed codes used in DQ rules:
  - **Domestic electronic** (require sort code + bank account — `SUP_BACS_NO_BANK`): `IP` (BACS), `CP` (CHAPS), `BB` (direct RBS payment)
  - **International** (require IBAN — `SUP_INT_NO_IBAN`): `IN`, `EU`, `TF`, `RT` (Request for Transfer)
- **HOC `apar_gr_id` supplier group codes** (HoC only — these are the group classifications on `asuheader`):

  | Code | Description | VAT reg required? |
  |------|-------------|-------------------|
  | CA | Catering Suppliers | Yes |
  | EM | Employees | No — individuals |
  | IR | PAYE and NI Creditors | No — HMRC tax payments |
  | ME | Members (MPs/Lords) | No — individuals |
  | PY | Payroll Third Parties | No — payroll context |
  | SA | Specialist Advisor | Yes |
  | SC | Schools | No — VAT-exempt educational bodies |
  | SM | SME's | Yes |
  | SS | Security Suppliers | Yes |
  | TC | Trade Suppliers (CIS) | Yes |
  | TI | IR35 Suppliers | No — individual contractors |
  | TN | Trade Suppliers (Non CIS) | Yes |
  | TO | Off Payroll Suppliers (IR35) | No — individual contractors |
  | WI | Witness Expenses | No — individuals |

  Groups exempt from VAT reg checks (`SUP_VAT_MISSING`, `SUP_VAT_FORMAT`) for HOC: `EM`, `IR`, `ME`, `PY`, `SC`, `TI`, `TO`, `WI`. Also exempt: apar_id prefixes `71` and `74`.
- **`voucher_type` codes in asutrans / asuhistr** — full reference:

  | Code | Description | Category |
  |------|-------------|----------|
  | AB | Absence, transfer to payroll | Payroll |
  | AC | Accrual journals | Journal |
  | BA | Batch Input adj for CRS BQT debts | Batch |
  | BF | Bank Funding | Banking |
  | BI | Batch Input | Batch |
  | BU | Budget Transactions | Budget |
  | BV | Budget Virements | Budget |
  | **CN** | **Purchase Credit Notes** | **Credit note** |
  | CP | Contract Invoice Posting | Invoice |
  | DB | Debtors - Banking | Debtors |
  | DJ | Drawn Down | Journal |
  | DM | Debtors - Manual matching | Debtors |
  | DP | Debtors - Post payments against invoices | Debtors |
  | DR | Debtors Refreshment Department | Debtors |
  | EI | EPOS Interface Journals | Journal |
  | FZ | Fixed Assets | Assets |
  | **IC** | **Incoming Invoices Registration Credit Notes** | **Credit note** |
  | ID | Incoming Invoices Purchase CRS | Invoice |
  | IF | Incoming Invoices Bank Funding | Invoice |
  | **II** | **Incoming Invoices Registration** | **Invoice** |
  | **IN** | **Incoming Invoices Posting Credit Notes** | **Credit note** |
  | **IR** | **Incoming Invoices Payment Reversal** | **Reversal** |
  | **IU** | **Incoming Invoices Purchase Invoices** | **Invoice** |
  | JL | Adjustment journals | Journal |
  | JO | Opening Balances | Journal |
  | MI | Micros Interface Journals | Journal |
  | MM | Manual Matching | Matching |
  | **OP** | **Purchase Order Based Invoice Posting** | **Invoice** |
  | PA | Absence Entry | Payroll |
  | PC | Payroll Manual Cheque | Payroll |
  | PE | Posting Expenses | Expenses |
  | **PI** | **Purchase Invoices** | **Invoice** |
  | PJ | Prepayment journals | Journal |
  | PP | Posting payroll transactions | Payroll |
  | **PR** | **Payment Reversal** | **Reversal** |
  | PV | Variable payroll transactions | Payroll |
  | PY | Payments | Payment |
  | **RC** | **Registration Credit Notes** | **Credit note** |
  | RD | Purchasing Refreshment Department | Invoice |
  | RE | Registering Expenses | Expenses |
  | **RI** | **Registered Invoices** | **Invoice** |
  | RJ | Recurring journals | Journal |
  | RP | Reshared Staff posting adj for inv | Adjustment |
  | RS | Registering Staff Expenses | Expenses |
  | **RV** | **Reversals** | **Reversal** |
  | SI | Stock Purchasing CRS | Invoice |
  | SR | Speedy Registration of Supplier Invoices | Invoice |
  | TC | Members Travel card | Expenses |
  | TD | Expenses Templates | Expenses |
  | WO | Debtors Write-Off | Debtors |
  | YE | Year end transfer | Journal |

  **Credit / reversal types** (negative `amount` and `rest_amount` are expected and normal):
  - **Credit notes**: `CN`, `IC`, `IN`, `RC`
  - **Reversals**: `IR`, `PR`, `RV`

  **Standard invoice types** (positive `amount` expected — a negative value here indicates wrong voucher type):
  `CP`, `ID`, `IF`, `II`, `IU`, `OP`, `PI`, `RC`*\*, `RD`, `RI`, `SI`, `SR`

  DQ rules that test credit note types (`AP_CN_NO_REF`, `AP_ORPHANED_CREDITS`, `HIS_CN_NO_REF`, `AP_NEG_INV`) must use the full credit note set `['CN', 'IC', 'IN', 'RC']`, not just `'CN'`. Reversal types `['IR', 'PR', 'RV']` should also be excluded from `AP_NEG_INV` as negative amounts are expected there too.

---

## Modal Drill-Down Inspector

Triggered by clicking any bar in a dimension chart or any row in a DQ results table. Renders via `handle_modal_logic` callback in `app.py`.

**Layout:**
- Single dark header bar (`#1e1528`) — one dark element, everything else white
- **Left sidebar (380px):** Three stacked elements, all `gap: 12px`:
  1. Dimension label row — `lucide:layers` icon + dimension name (uppercase, `#a090c0`, no pill/badge) + gradient divider + "severity" label + severity pill (RAG-coloured)
  2. Records assessed card (`#faf9fd` background, `1px solid #ede9f8` border, `12px` radius) — header row with assessed count + RAG pill, then a filled progress bar (RAG colour, `overflow: hidden`), then below the bar: "X flagged" left-aligned in RAG colour and "X%" right-aligned in muted grey
  3. RAG thresholds card (same style) — three rows (Green / Amber / Red) each with a coloured pill badge and threshold text reading e.g. "< 1% flagged", "1–5% flagged", "> 5% flagged". Thresholds pulled from `RAG_THRESHOLDS` for the check's severity.
- **Right panel:** `paddingTop: 56px` so "Why this matters" aligns horizontally with the Records assessed card. Three cards, all `#faf9fd` / `1px solid #ede9f8` / `12px` radius / `gap: 12px`:
  1. Why this matters — `lucide:alert-circle` header, intent text in `#4a3d6b` weight 400
  2. Rule definition — `lucide:code` header, code block in `#ede8f5` / `#d8d0ee` border (deeper shade nested inside outer card)
  3. Critical fields — `lucide:tag` header, tag chips in `#ede8f5` container. Both rule definition and critical fields cards use `width: fit-content` and `alignItems: stretch` so inner boxes match height.
- Failing records table below — no table strip banner
- Failing count uses `row['failing']` from `dq_results` (same source as charts) — NOT `len(df)` which can be inflated

**`status` column**: always shown in the evidence table. For the generic fallback path (most checks), `status` is included via `key_fields` in `app.py`. For specific early-return checks (`AP_ORPHANED_TRANS`, `HIS_ORPHANED`, etc.) it must be included explicitly in the `cols` list in `get_failing_records()`.

**Column display logic** (`app.py` — `handle_modal_logic`):
- Checks whose columns are prefixed with a known table name (e.g. `AP_INVOICES.`, `ASSET_MASTER.`) → `is_prefixed = True` → all returned columns shown
- All other checks → `is_prefixed = False` → column filter runs, keeping only columns whose bare name is in `key_fields` (identifiers + `status`) or in `base_cols` (the check's highlighted fields from `get_check_columns()`)
- **Cross-house checks** (`_XHOUSE_CHECKS` set): bypass the single-house filter and the column filter entirely; render as two separate DataTables side by side (HOC green header / HOL red header), deduplicated by matching identifier so rows align for visual comparison.

Uses `dash-iconify` for Lucide icons (`lucide:alert-circle`, `lucide:code`, `lucide:tag`, `lucide:layers`, `lucide:bar-chart-2`, `lucide:sliders`, `lucide:check-circle-2`, `lucide:database`, `lucide:table-2`, `lucide:download`, `lucide:x`, `lucide:arrow-right`).

---

## Dimension Scorecard KPIs

`render_dimension_scorecard()` in `dashboard/shared/dimensions.py` renders the KPI strip at the top of each domain tab. It splits `dq_results` by house and shows **two side-by-side groups** (HOC green header / HOL red header), each with:

| Card | Definition |
|------|------------|
| **Overall DQ Score** | % of scored checks (severity ≠ Info) with Green RAG for that house |
| **Total Checks** | Count of all scored checks for that house |
| **Checks With Failures** | Count of checks where `failing > 0` (at least one record fails — binary, not a threshold) |
| **Checks Passing** | Count of checks with Green RAG |

The overall score is **check-level** (% checks green), not record-weighted. This keeps it consistent with the three count cards alongside it and avoids the misleading inflation caused by large clean datasets dominating a record-weighted average.

Each dimension widget header also shows per-house HOC/HOL score chips (`_house_score()` in `dimensions.py`). Each chip is a neutral grey badge (`#F1F5F9` background) with a house-coloured border and the error rate rendered in the RAG colour for that score. A gradient vertical divider separates the two chips. Only "avg error" label appears once between/after the chips.

---

## Supplier Domain — Implementation Details

### SQL extract files (`sql/`)
All supplier extract files exist as HOC/HOL split run files. Use the `_HOC_run.sql` / `_HOL_run.sql` files when extracting on the Parliament laptop:

| File | Database | Client filter | Output filename |
|------|----------|---------------|-----------------|
| `supplier_master_HOC_run.sql` | `Agresso_HoC` | `CA`, `CM` | `supplier_master_HOC.csv` |
| `supplier_master_HOL_run.sql` | `agresso_HoL` | `LA` | `supplier_master_HOL.csv` |
| `supplier_trans_HOC_run.sql` | `Agresso_HoC` | `CA`, `CM` | `supplier_open_trans_HOC.csv` |
| `supplier_trans_HOL_run.sql` | `agresso_HoL` | `LA` | `supplier_open_trans_HOL.csv` |
| `supplier_hist_HOC_run.sql` | `Agresso_HoC` | `CA`, `CM` | `supplier_history_HOC.csv` |
| `supplier_hist_HOL_run.sql` | `agresso_HoL` | `LA` | `supplier_history_HOL.csv` |

### Supplier address (`agladdress`)
Supplier addresses are not stored on `asuheader` — they live in the shared `agladdress` table. The join to get the primary address:

```sql
LEFT JOIN (
    SELECT client, dim_value, address, place, zip_code, province,
           ROW_NUMBER() OVER (PARTITION BY client, dim_value ORDER BY sequence_no) AS rn
    FROM agladdress
    WHERE attribute_id = 'A5'
      AND address_type = '1'
) a ON  a.client    = h.client
    AND a.dim_value = h.apar_id
    AND a.rn        = 1
```

Key facts:
- `agladdress` is shared across all entity types (suppliers, customers, cost centres) — `attribute_id` discriminates supplier records
- **HoC confirmed `attribute_id = 'A5'`** for suppliers — verify for HoL before relying on it (run: `SELECT DISTINCT attribute_id FROM agladdress WHERE client = 'LA' AND address_type = '1'`)
- `address_type = '1'` is the primary address — other types exist (delivery, remittance, etc.)
- 183 HoC suppliers have multiple rows at `address_type = '1'` — `ROW_NUMBER() ORDER BY sequence_no` picks the primary one
- Columns extracted: `address` (street), `place` (town/city), `zip_code` (postcode), `province` (county)
- `00000000` bank account values are Unit4 placeholders (not valid bank accounts) — the `SUP_BACS_NO_BANK` check should eventually be updated to treat these as missing

### Address DQ checks added
Five checks on `asuheader` (all Low/Medium severity, active suppliers only):
- `SUP_ADDR_MISSING` — `address` blank/null (Completeness, Low)
- `SUP_PLACE_MISSING` — `place` blank/null (Completeness, Low)
- `SUP_ZIP_MISSING` — `zip_code` blank/null (Completeness, Low)
- `SUP_PROVINCE_MISSING` — `province` blank/null (Completeness, Low)
- `SUP_ZIP_FORMAT` — zip populated + known country + format wrong (Validity, Medium). Validates GB postcodes, US zips, most EU 4-5 digit formats, NL, IE Eircodes. Unknown country codes are not flagged.

**HOC address exemptions**: `apar_id` values starting with `1000` (iTrent employees — address not held in Unit4) or `74` are excluded from all four address completeness checks. HOL is unaffected.

### Supplier Uniqueness checks (full set)
Within-house checks on `asuheader` (Uniqueness dimension):
- `SUP_NAME_DUP` — duplicate name + address + zip_code within same house (Medium). Same name at different address/postcode is not flagged.
- `SUP_NAME_DUP_ANY` — duplicate name within same house regardless of address (Low). Flags any same-name record for review.
- `SUP_VAT_DUP` — duplicate VAT registration number within same house (High).
- `SUP_BANK_SORT_DUP` — duplicate bank account + sort code combination within same house (High).
- `SUP_BANK_DUP` — duplicate bank account + sort code + VAT registration (all three) within same house (High).
- `SUP_CLIENT_APAR_DUP` — duplicate `(client, apar_id)` primary key (Critical).

Cross-house checks (lambda signature `df, frames`) — see Adding a Cross-House Uniqueness Check above:
- `SUP_XHOUSE_VAT_DUP`, `SUP_XHOUSE_COMP_REG_DUP`, `SUP_XHOUSE_IBAN_DUP`, `SUP_XHOUSE_BANK_DUP`, `SUP_XHOUSE_NAME_DUP`

### SUP_DORMANT exemption
`apar_id` values starting with `1000` are exempt from the dormant check for **both houses**.

### AP_ORPHANED_TRANS modal evidence
The `get_failing_records` early-return for `AP_ORPHANED_TRANS` returns a summary grouped by `apar_id` with a transaction count — one row per orphaned supplier ID rather than one row per transaction. Columns returned: `AP_INVOICES.apar_id`, `AP_INVOICES.transaction_count`.

---

## SSMS Extraction Quirks

Known issues when extracting data on the Parliament laptop and saving via Excel:

**SSMS save location** — SSMS runs under the `adminleitchtb` admin profile. Files saved via "Save Results As" go to `C:\Users\adminleitchtb\Documents\`, not the regular user's Documents. Navigate manually to `C:\Users\leitchtb\HoP_Data_Assessment\data\<subfolder>\` in the Save As dialog and SSMS remembers it next time.

**Headers missing in CSV** — Enable via Tools → Options → Query Results → SQL Server → Results to Grid → tick "Include column headers when copying or saving results". Must close and reopen the query tab for the setting to take effect.

**Leading zeros stripped (sort codes, bank accounts)** — Do not open CSVs by double-clicking in Explorer. Import via Excel: Data → Get Data → From Text/CSV → set affected columns to Text type in Power Query before loading. This preserves leading zeros.

**Large numbers converted to scientific notation / dates** — Click "Don't Convert" when Excel prompts during CSV open. The dashboard handles all type parsing in `data_engine.py`.

**Comma-formatted numbers** — `rest_amount` and similar numeric fields may arrive from SSMS as `1,234.56` — `data_engine.py` strips commas in pre-processing.

---

## GL Domain — Implementation Details

### SQL extracts (`sql/`)
All GL extract files exist in two forms:
- `gl_*_run.sql` — **original full spec** with documentation, assumptions, and DQ test descriptions
- `gl_*_HOC_run.sql` / `gl_*_HOL_run.sql` — **clean run-ready versions** for pasting directly into SSMS, filtered to confirmed client codes

Use the `_HOC_run.sql` / `_HOL_run.sql` files when extracting on the Parliament laptop.

### Dimension values (`agldimvalue` / `gl_dimension_values`)
Unit4 stores GL dimension values (cost centres, subjectives, analysis codes, etc.) in `agldimvalue`. Each row has an `attribute_id` which identifies the dimension type — but these codes are opaque short strings (e.g. `C1`, `ZZ`) not human-readable names.

The mapping between dim positions (dim_1 through dim_7 on journal lines) and attribute_ids is held in the `agldimension` table:

| Column | Description |
|--------|-------------|
| `client` | Fund/entity code |
| `dim_position` | Which dim column this attribute maps to (e.g. `1` = dim_1) |
| `attribute_id` | The attribute code used in agldimvalue |
| `description` | Human-readable name e.g. "Cost Centre", "Subjective" |
| `status` | N=Active — filter to N only |

A single dim_position can have multiple active `attribute_id` codes (e.g. dim_2 may hold both "Cost Centre" and "Seconded Staff Customer" depending on context).

The `gl_dimension_values_HOC/HOL_run.sql` Step 2 query joins `agldimvalue` to `agldimension` automatically — no manual attribute_id codes need to be entered. The output includes `dim_position` and `dim_description` columns.

### GL opening balances (`aglperiodic` — not `aglyearend`)
`aglyearend` is **not used** in Parliament's Agresso installation — it contains only legacy pre-2008 data. The correct table is `aglperiodic`.

Key facts about `aglperiodic`:
- `period` is a **6-digit YYYYPP integer** (e.g. `202610` = FY2025/26 period 10). There is no separate `fiscal_year` column.
- The table is **transactional** (one row per posting), not a cumulative balance snapshot. Rules that assume one row per account (e.g. `GL_BAL_PL_NONZERO`) will need reworking once run against real data.
- Budget and virement entries (`voucher_type IN ('BU', 'BV')`) are stored in the same table and can appear with **future-dated periods** (e.g. 203407 = FY2034 period 7) — these are planning entries, not real postings, and are excluded in the SQL extract.
- `BA` (Batch Input adj) is a real financial posting and is **not** excluded.
- The SQL extract filters to `period BETWEEN 202601 AND 202699` for FY2025/26 (current year). Update this range at cutover.
- The frame key in the engine remains `aglyearend` for backwards compatibility — the CSV filename (`gl_opening_balances_HOC/HOL.csv`) is unchanged.

### GL journals fiscal year convention
`agltransact` (journals) uses an **end-year** convention: `fiscal_year = 2026` means FY2025/26. Filter confirmed as `AND fiscal_year = 2026` in the HOC/HOL run files.

### File loading
All five GL tables load as split files. `house` is assigned from the filename suffix (not the `client` column):

| Frame key | Files | Source table |
|-----------|-------|--------------|
| `aglaccounts` | `gl_chart_of_accounts_HOC/HOL.csv` | `aglaccounts` |
| `agldimvalue` | `gl_dimension_values_HOC/HOL.csv` | `agldimvalue` |
| `aglyearend` | `gl_opening_balances_HOC/HOL.csv` | `aglperiodic` (not `aglyearend`) |
| `agltransact` | `gl_transact_dimensions_HOC/HOL.csv` | `agltransact` |
| `gl_journals` | `gl_journals_HOC/HOL.csv` | `agltransact` |

---

## Current State (as of May 2026)

**Implemented and tested with dummy data:**
- GL (Chart of Accounts, Dimension Values, Opening Balances, Journals)
- Suppliers / AP (master, open transactions, history)
- Customers / AR (master, open transactions, history)
- Fixed Assets (master, depreciation, balances, groups, transactions)
- Executive Summary (cross-domain overview, scope heatmap, severity breakdown)
- Modal drill-down inspector (redesigned — dark header, sidebar metrics, flat content panels)
- Aging analysis (AP and AR) with HOC/HOL/Both toggle
- Cross-house uniqueness checks for suppliers (VAT, company reg, IBAN, bank account+sort code, name) with side-by-side modal evidence tables

**Not yet implemented:**
- PBF tab (`dashboard/tabs/pbf.py` is a placeholder)

**Live data:** The Parliament laptop (`leitchtb`) is running against real Agresso data as of May 2026. Supplier data refreshed May 2026 — master, open transactions, and history CSVs re-extracted with address fields (`address`, `place`, `zip_code`, `province`) added via `agladdress` join. GL customers, and assets still need real CSVs placed in `data/` subfolders on the Parliament laptop. This machine uses dummy data. All five GL extract SQL files have HOC/HOL split run files ready to execute. GL chart of accounts and dimension values have been extracted. GL journals SQL fixed (fiscal_year placeholder replaced with 2026). GL opening balances SQL rewritten to use `aglperiodic` (aglyearend had no current data).

**If the Parliament laptop needs to pull a code update**, run `git pull` — the `data/` folder is ignored so real data files are never touched. If git complains about untracked files in `data/`, run `git rm --cached -r data/` first (this happened once during the initial `.gitignore` setup).

**SQL files in `sql/`** are the extraction specs — each has a `HOW TO RUN` header with the exact SSMS database and output filename. The Python rule lambdas in `rules/` are the executable equivalents of the `DATA QUALITY TESTS` sections in each SQL file.
