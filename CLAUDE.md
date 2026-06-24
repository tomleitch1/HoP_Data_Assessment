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
- Dependencies installed: `pip install dash plotly pandas numpy faker python-dotenv dash-iconify openpyxl`
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
├── gl/          gl_chart_of_accounts_HOC/HOL.csv        ← LOADED (11 GL_ACC_* checks)
│                gl_opening_balances_HOC/HOL.csv         ← LOADED (3 GL_BAL_* checks)
│                gl_dimension_config_HOC/HOL.csv         ← LOADED (2 GL_DIM_ATTR_* checks, treemap)
│                gl_dimension_values_HOC/HOL.csv         ← LOADED (5 GL_DIM_* checks)
│                gl_transact_dimensions_HOC/HOL.csv      ← not yet loaded
│                gl_journals_HOC/HOL.csv                 ← not yet extracted (50k rows)
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

## Customer / AR Domain — Implementation Details

### `voucher_type` codes in acutrans / acuhistr

HOC and HOL use entirely different picklists for AR voucher types. The same code can mean different things in each house.

**HOC AR voucher types — standard invoice/sales types (positive amount expected):**

| Code | Description | Category |
|------|-------------|----------|
| `SI` | Sales Invoices | Invoice |
| `SC` | Catering and Retail | Invoice |
| `BA` | BizTalk Events Perfect Invoices | Invoice |
| `BC` | BizTalk Micros Sales | Invoice |
| `BD` | BizTalk Micros On Account Sales | Invoice |
| `BG` | BizTalk TSO Invoice | Invoice |
| `BH` | BizTalk IndiCater Invoices | Invoice |
| `BP` | BizTalk RMS On Account Sales | Invoice |
| `BS` | BizTalk Tours Ticketing | Invoice |

**HOC AR voucher types — negative amount expected (receipts, matching, reversals, adjustments):**

| Code | Description |
|------|-------------|
| `RV` | Reversing entries |
| `ZX` | Invoice Adjustments |
| `SR` | Cash Receipts |
| `SM` | Matched Receipts |
| `SN` | Manual Matching Customer Transactions |
| `ZR` | Central Allocated Receipts |
| `MM` | Manual Matching |
| `SZ` | AR O/S Invoices from 5.4 (migration) |
| `PM` | O/S AR Transactions from 5.4 (migration) |
| `ZZ` | Transactions post Periodical Triggers |

**HOL AR voucher types — standard invoice/sales types (positive amount expected):**

| Code | Description | Category |
|------|-------------|----------|
| `DR` | Debtors Refreshment Department | Invoice |
| `RI` | Registered Invoices | Invoice |
| `EI` | EPOS Interface Journals | Invoice |
| `MI` | Micros Interface Journals | Invoice |

**HOL AR voucher types — negative amount expected (credit notes, reversals, receipts, write-offs):**

| Code | Description |
|------|-------------|
| `CN` | Purchase Credit Notes |
| `IC` | Incoming Invoices Registration Credit Notes |
| `IN` | Incoming Invoices Posting Credit Notes |
| `RC` | Registration Credit Notes |
| `IR` | Incoming Invoices Payment Reversal |
| `PR` | Payment Reversal |
| `RV` | Reversals |
| `DB` | Debtors - Banking |
| `DP` | Debtors - Post payments against invoices |
| `WO` | Debtors Write-Off |

**`AR_NEG_INV` check logic:** flags negative `amount` only on the house-specific invoice whitelist above. HOC and HOL whitelists are applied per row using the `house` column. Any code not in the whitelist is left unchecked (most AR types can legitimately carry either sign).

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

### Iterative build approach

**The GL tab is built one dataset at a time.** A new dataset and its checks are only added when:
1. The SQL extract has been run against real Parliament data and the output has been reviewed
2. The column names, data types, and value formats are confirmed (not assumed from dummy data or spec)
3. The dummy data generator has been updated to match the real format

Do not add checks speculatively against a schema that has not been seen in real data. The cost of a wrong assumption is a check that always shows 0% or 100% and has to be reworked later.

**When adding a new GL dataset, the steps are:**
1. Run the SQL on the Parliament laptop, inspect the first ~20 rows in Excel — note column names, value formats, nulls, and any surprises
2. Update the dummy data generator (`scripts/generate_gl_dummy_data.py`) to match the real format exactly
3. Register the file in `SUBDIR['gl']`, `split_files`, and `house_from_filename` in `data_engine.py`
4. Add the checks to `gl_rules.py` as tuples, import via `get_gl_checks()`
5. Add the population filter branch for the new table to `run_dq_analysis()` and `get_failing_records()`
6. Add `get_check_columns()` entries for each new check

### Currently loaded datasets (active)

| Frame key | Files | Source table | Checks live |
|-----------|-------|--------------|-------------|
| `aglaccounts` | `gl_chart_of_accounts_HOC/HOL.csv` | `aglaccounts` | Yes — 11 GL_ACC_* checks |
| `aglyearend` | `gl_opening_balances_HOC/HOL.csv` | `aglperiodic` | Yes — 3 GL_BAL_* checks |
| `gl_dimconfig` | `gl_dimension_config_HOC/HOL.csv` | `agldimension` ⋈ `agldimvalue` (counts) | Yes — 2 GL_DIM_ATTR_* checks + treemap |
| `agldimvalue` | `gl_dimension_values_HOC/HOL.csv` | `agldimvalue` ⋈ `agldimension` | Yes — 5 GL_DIM_* checks |

### Planned datasets (not yet loaded)

| Frame key | Files | Source table | Status |
|-----------|-------|--------------|--------|
| `agltransact` | `gl_transact_dimensions_HOC/HOL.csv` | `agltransact` | SQL ready, schema not confirmed |
| `gl_journals` | `gl_journals_HOC/HOL.csv` | `agltransact` | SQL ready, 50k rows, schema not confirmed |

To add one of these: review real data first, then follow the iterative build steps above.

### Chart of Accounts (`aglaccounts`) — confirmed schema

Columns extracted: `client, account, description, account_grp, account_type, status, res_bal, bflag, account_rule, period_from, period_to, last_update, head_account`

**Confirmed from real Parliament data:**
- `client`: HOC = `CA` or `CM` (same account codes appear for both); HOL = `LA`
- `account`: HOC = numeric string (e.g. `1000`); HOL = letter-prefix + number (e.g. `A1000`)
- `account_grp`: HOC = numeric `1`–`9`; HOL = single letter `A`–`F` (6 groups — exact meaning TBD)
- `account_type`: `GL`, `AP`, or `AR`
- `status`: `N` (active) or `C` (closed)
- `res_bal`: `R` (P&L) or `B` (Balance Sheet)
- `bflag`: bitmask integer — `0` or powers of 2 (`8`, `16`, `32`, `64`, `128`). Specific bit meanings not yet confirmed. **Do not use `bflag == 7` from old spec** — that was a placeholder.
- `account_rule`: integer; HOC up to 39, HOL up to 89
- `period_from`, `period_to`, `last_update`: **Excel serial date integers** (e.g. `45698`) — parsed to datetime by `_parse_dates()`. Engine parse range is 20000–55000 (~1954–2050); use dates within this range in dummy data.
- `head_account`: blank for both houses

**Population filter in `run_dq_analysis`:** active accounts (`status == 'N'`) for all checks except `GL_ACC_DUP_CODE` which uses full population.

**Deferred check:** `GL_ACC_BFLAG_CON` (reconciliation account not flagged as AP/AR type) is not yet implemented — the specific `bflag` bit that means "reconciliation" has not been confirmed from real data. Implement once Parliament confirms the bitmask definition.

### Opening Balances (`aglyearend` / `aglperiodic`) — confirmed schema

Columns extracted: `client, account, period, dim_1, dim_2, dim_3, dim_4, dim_5, dim_6, dim_7, amount, cur_amount, currency, dc_flag, voucher_type, voucher_no, trans_date, tax_code, apar_id, apar_type, status, description`

**Confirmed from real Parliament data (May 2026):**
- Row count: ~3,000 HOC, ~1,600 HOL — very manageable
- `period`: 6-digit YYYYPP integer (e.g. `202601` = FY2025/26 period 1)
- `amount`: **signed** — positive = debit, negative = credit. `dc_flag` is always `0` and is not used for sign.
- `currency`: always `GBP`. `cur_amount` is always blank — `GL_BAL_FX_MISSING` is not applicable.
- `dim_1`: populated with dimension codes. `dim_2` through `dim_7`: always blank.
- `trans_date`: stored as integer `1` in SSMS/Excel (system placeholder, not a real date). Parsed to NaT by the engine. Do not write checks on `trans_date`.
- `status`: mostly blank; a small number of rows have D, N, T, X — meaning unknown, no checks written.
- `apar_id`: always blank — sub-ledger reconciliation checks not possible from this extract.
- `voucher_type`: standard Agresso picklist (BU/BV excluded in SQL extract).

**Population filter in `run_dq_analysis`:** all rows for the house — no status filter (falls through to `else` branch).

**Implemented checks (3):**
- `GL_BAL_AMT_MISSING` — `amount IS NULL` (Completeness, High)
- `GL_BAL_ORPHAN_ACC` — account not in `aglaccounts` for same house (Consistency, High) — joined check
- `GL_BAL_PL_NONZERO` — P&L account (res_bal=R) has non-zero net across all periods (Validity, Medium) — joined check. Will fire legitimately if year-end close journals (periods 13–15) are still pending.

**Skipped checks:**
- `GL_BAL_FX_MISSING` — not applicable, currency always GBP
- `GL_BAL_TOTAL_NET` — aggregate check (SUM across all rows), does not fit the row-level DQ model

### SQL extracts (`sql/`)
All GL extract files exist in two forms:
- `gl_*_run.sql` — **original full spec** with documentation, assumptions, and DQ test descriptions
- `gl_*_HOC_run.sql` / `gl_*_HOL_run.sql` — **clean run-ready versions** for pasting directly into SSMS, filtered to confirmed client codes

Use the `_HOC_run.sql` / `_HOL_run.sql` files when extracting on the Parliament laptop.

### Dimension Configuration (`gl_dimconfig`) — confirmed schema

Summary/reference frame — one row per `(client, attribute_id)`. Not a DQ check frame in the traditional sense; used for the GL tab treemap visualisation and two attribute-level DQ checks.

Columns: `client, attribute_id, description, dim_position, total_values, active, closed`

**`dim_position` key:**
- `1`–`7` → maps to `dim_1` through `dim_7` on GL journal lines — in scope for GL migration
- Letters (`A`, `B`, ...) → header-level or cross-module dimensions — review for relevance
- `X` → not mapped to any GL transaction line — out of scope for GL migration

**Real Parliament data scale (June 2026):** HOC has ~50 GL-mapped attributes (dim_position 0–7) and ~700 total (mostly X). CA and CM share the same attribute definitions; both clients appear per attribute, so CA+CM counts must be **summed** before display (done in `_build_treemap()` in `gl.py`).

**Population filter:** all rows for the house (SQL already filters `agldimension` to `status = 'N'`).

**Implemented checks (2):**
- `GL_DIM_ATTR_GL_EMPTY` — GL-mapped attribute (position 0–7) with zero active values (Completeness, High). Population scoped to GL-mapped rows only so error rate is not diluted by the 650+ X-position attributes.
- `GL_DIM_ATTR_DESC_MISSING` — any attribute with blank description (Completeness, Low). Full population.

**GL tab treemap (`dashboard/tabs/gl.py`):**
- `_build_treemap(df_config, house)` renders a `px.treemap` per house. HOC aggregates CA+CM counts. GL attributes (position 0–7) are individual leaves sized by `active` values. X-position and letter-coded attributes are collapsed into "Out of Scope" blocks, normalised to ~22% of total width (`_OOS_FRACTION = 0.22`) so HOC and HOL are visually comparable. Colour = `closed_pct` (green→amber→red at 0–35–80%).
- House labels ("HoC" / "HoL") live in Dash html elements above the chart — not in the plotly title — so the path bar (breadcrumb when drilling in) cannot overlap them.
- Modebar enabled with reset/home button; irrelevant chart-type buttons removed.

### Dimension Values (`agldimvalue`) — confirmed schema

Columns extracted: `client, attribute_id, dim_position, dim_description, dim_value, description, status, period_from, period_to, rel_value, last_update, wf_state`

**Confirmed from real Parliament data (June 2026):**
- Extract scoped to GL-mapped positions only (`dim_position IN ('0','1','2','3','4','5','6','7')`) and active values (`status = 'N'`). Row counts: ~95k HOC, ~38k HOL. This is the real volume — Parliament has a large number of active dimension values across 50+ GL attributes.
- `dim_position`: string (`'1'`–`'7'`); same key as gl_dimconfig
- `dim_description`: the attribute type label from `agldimension` (e.g. `'Cost Centre'`)
- `dim_value`: string code, may have leading zeros (e.g. `0101`) — preserved correctly via Excel import
- `description`: human-readable label for the individual value
- `status`: always `'N'` in the extract (SQL filters active only)
- `period_from` / `period_to`: **YYYYMM integers** (e.g. `201202` = 2012 period 2, `209912` = 2099 period 12 open-ended sentinel). **NOT Excel serial dates.** Engine converts these to numeric with `pd.to_numeric()` — they are explicitly excluded from `_parse_dates()` for `agldimvalue`.
- `last_update`: **Excel serial integer** (e.g. `46090`) — parsed normally by `_parse_dates()`.
- `rel_value`: parent `dim_value` code within the same `(attribute_id, client)` for hierarchy; blank for root nodes. Can be letters, numbers, or alphanumeric (e.g. `RD`, `1101`).
- `wf_state`: **not used** in Parliament's Agresso — always blank. Do not write `GL_DIM_WF_STUCK` checks.

**Population filter in `run_dq_analysis` and `get_failing_records`:** all rows for the house (SQL already active-only; engine adds explicit `agldimvalue` branch for consistency).

**Period handling in `data_engine.py`:** the post-processing loop has a table-specific branch for `agldimvalue` that converts `period_from` and `period_to` to numeric with `pd.to_numeric()` and excludes them from the `_parse_dates()` call. `last_update` is still date-parsed normally.

**Implemented checks (5):**
- `GL_DIM_DESC_MISSING` — active value with blank description (Completeness, Medium)
- `GL_DIM_PERIOD_MISSING` — active value with no `period_from` (Completeness, Low)
- `GL_DIM_PERIOD_INV` — `period_from > period_to` as YYYYMM integers (Validity, Medium)
- `GL_DIM_ORPHAN_REL` — `rel_value` populated but does not exist as an active `dim_value` in the same `(attribute_id, client)` (Consistency, High). Vectorised via composite key string: `attribute_id + '||' + client + '||' + rel_value`. This catches both missing parents and closed parents (since only active values are in the extract).
- `GL_DIM_DUP` — duplicate `(client, attribute_id, dim_value)` (Uniqueness, High)

### GL opening balances (`aglperiodic` — not `aglyearend`) — not yet loaded
`aglyearend` is **not used** in Parliament's Agresso installation — it contains only legacy pre-2008 data. The correct table is `aglperiodic`.

Key facts about `aglperiodic`:
- `period` is a **6-digit YYYYPP integer** (e.g. `202610` = FY2025/26 period 10). There is no separate `fiscal_year` column.
- The table is **transactional** (one row per posting), not a cumulative balance snapshot.
- Budget and virement entries (`voucher_type IN ('BU', 'BV')`) can appear with future-dated periods (e.g. 203407) — excluded in the SQL extract.
- `BA` (Batch Input adj) is a real financial posting and is **not** excluded.
- **Both HOC and HOL use start-year fiscal year convention** — confirmed from agltransact data (June 2026):
  - **HOC** (`Agresso_HoC`): `fiscal_year = 2025` and `period BETWEEN 202501 AND 202515` is FY2025/26
  - **HOL** (`agresso_HoL`): `fiscal_year = 2025` and `period BETWEEN 202501 AND 202512` is FY2025/26
  - HOL historically never uses period 13 or 14 — period 12 is always the final period
  - HOC typically posts year-end journals in period 13; occasionally period 14
  - Previous documentation stated HOL used end-year convention — **this was wrong**. Confirmed by inspecting period 202601 in the HOL agltransact extract: trans_dates were predominantly April 2026, proving fiscal_year=2026 = FY2026/27 for HOL.
- SQL run files corrected: HOL opening balances now uses `period BETWEEN 202501 AND 202512`; HOL journals uses `fiscal_year = 2025`. Update at cutover to FY2028/29 (both houses: fiscal_year=2028).
- Frame key in the engine is `aglyearend` (for backwards compatibility) — CSV filename unchanged.

### GL Journals / Current Year Transactions (`agltransact`) — confirmed schema and loaded

Columns extracted: `client, voucher_no, sequence_no, account, fiscal_year, period, trans_date, voucher_date, voucher_type, amount, cur_amount, currency, dc_flag, update_flag, status, apar_id, apar_type, tax_code, tax_system, description, ext_inv_ref, dim_1..dim_7, last_update, user_id`

**Confirmed from real Parliament data (June 2026):**
- Both HOC and HOL use **start-year** convention: `fiscal_year = 2025` covers FY2025/26 for both houses
- HOC extract: ~650k rows, periods 202500–202513 (period 00 = opening b/f, 01–13 = full year + year-end)
- HOL extract: ~18k rows, periods 202501–202512 (HOL never uses period 13; HOL must be re-run with `fiscal_year = 2025` after the end-year convention correction)
- `amount` is **signed** — positive = debit, negative = credit. `dc_flag` mirrors the sign (+1 or -1). Both agree.
- `period` is a YYYYPP integer — parsed as numeric in the engine (same as agldimvalue, not parsed as a date)
- `fiscal_year` is a plain integer — parsed as numeric in the engine

**Period 00 (e.g. 202500):** opening brought-forward entries — one-sided by design. The counterpart lived in the prior year close. Do not include period 00 in any balance or net calculations.

**Voucher balance integrity:** `agltransact` with the status filter does NOT contain all sides of every journal. Sub-ledger credits (AP control, payroll creditor) may be in separate tables (asutrans, acutrans) or have a different status code excluded by the filter. Single-line vouchers (e.g. a PE expense posting) are completely normal. Do NOT write a cross-voucher balance check on this extract — it will produce thousands of false positives.

**Frame key:** `gl_journals` — loaded from `gl_journals_HOC.csv` + `gl_journals_HOL.csv`

**Fiscal year convention correction (June 2026):** HOL SQL was originally written assuming end-year convention (`fiscal_year = 2026` for FY2025/26). Confirmed wrong by inspecting period 202601 — trans_dates were predominantly April 2026, proving `fiscal_year = 2026` = FY2026/27. Both SQL run files now use `fiscal_year = 2025`.

**Volumetrics card (GL tab intro):** shows per-house transaction lines, unique vouchers, accounts used, posting users, period range, and proportional voucher type bars. Replaces the old Opening Balances card. The `aglyearend` frame is still loaded for its 3 DQ checks but has no dedicated intro card.

---

## Fixed Assets Domain — Implementation Details

### Iterative approach

**The same principle applies as for the GL tab**: do not finalise DQ checks or balance calculations against assumptions that have not been verified against real Parliament data. The asset extracts are loaded and checks are live, but several critical assumptions about `aattrans` content remain unconfirmed. See QUESTIONS_FOR_PARLIAMENT.md Q3.

### SQL extract files (`sql/`)

| File | Database | Output |
|------|----------|--------|
| `asset_master_HOC_run.sql` | `Agresso_HoC` | `asset_master_HOC.csv` |
| `asset_master_HOL_run.sql` | `agresso_HoL` | `asset_master_HOL.csv` |
| `asset_depreciation_HOC_run.sql` | `Agresso_HoC` | `asset_depreciation_HOC.csv` |
| `asset_depreciation_HOL_run.sql` | `agresso_HoL` | `asset_depreciation_HOL.csv` |
| `asset_balances_HOC_run.sql` | `Agresso_HoC` | `asset_balances_HOC.csv` — joins `aatasset` to exclude closed assets (`status != 'C'`) |
| `asset_balances_HOL_run.sql` | `agresso_HoL` | `asset_balances_HOL.csv` — same join added but blocked by permissions on `aatasset` in HOL db (database refresh June 2026 reset permissions — needs re-granting before this can be run) |
| `asset_groups_HOC_run.sql` | `Agresso_HoC` | `asset_groups_HOC.csv` |
| `asset_groups_HOL_run.sql` | `agresso_HoL` | `asset_groups_HOL.csv` |
| `asset_trans_flags_HOC_run.sql` | `Agresso_HoC` | `asset_trans_flags_HOC.csv` |
| `asset_trans_flags_HOL_run.sql` | `agresso_HoL` | `asset_trans_flags_HOL.csv` |

### `aatassetgrbook` — depreciation book IDs confirmed from real data (June 2026)

Parliament uses exactly **two depreciation book IDs** across both houses:
- `CURR` — current / active depreciation book (financial reporting)
- `HIST` — historical depreciation book

Multi-book assets therefore have one CURR row and one HIST row in `asset_depreciation`. The `depr_book_id` column in `asset_groups` and `asset_depreciation` will always be one of these two values. Do not expect other book names.

### `aattrans` — dc_flag mechanism (confirmed from real HoC data, June 2026)

`aattrans` stores every real transaction with `dc_flag = 1`, **and** mirrors each one with an equal-and-opposite year-end reset entry at `dc_flag = -1`. The reset entries are an internal AT module housekeeping mechanism — they are not real financial movements. Without `AND dc_flag = 1` in the WHERE clause, `SUM(amount)` nets to zero for every asset and every trans_type. **All run SQL files include `dc_flag = 1`.** The spec file `asset_balances.sql` documents this in assumptions but omitted it from the WHERE clause — the run files are correct.

### `aattrans` — trans_type codes confirmed from real data (June 2026)

The following were verified by running `SELECT trans_type, dc_flag, COUNT(*), SUM(amount) FROM aattrans GROUP BY trans_type, dc_flag` on the real Parliament databases:

**Confirmed and understood:**

| Code | Meaning | HOC rows (dc=1) | HOL rows (dc=1) |
|------|---------|----------------|----------------|
| CA | Capitalisation (original cost) | 62,737 | 10,131 |
| PC | Post-capitalisation addition / betterment | 263 | 1,340 |
| ND | Normal (periodic) depreciation | 2,594,255 | 382,061 |
| ED | Extraordinary depreciation | 366 | 34 |
| FD | Final depreciation at disposal | 12 | 2,354 |
| SA | Disposal | 98,109 | 25,829 |
| VN | Revaluation movement | 487 | 327 |
| CI | Calculatory Interest — **excluded from extract** (internal mgmt charge, does not affect NBV or GL) | 6 | 36 |

**Confirmed absent from real data (were in spec as assumed):**
- `ZU` (grant credit) — does not appear in either house. Grant-funded assets may be handled differently or not used.
- `RV` (reversal) — does not appear. Reversals may be handled via negative amounts on the original type.

**Unknown trans_types found in real data — awaiting Parliament confirmation (see QUESTIONS_FOR_PARLIAMENT.md Q3):**

| Code | HOC rows (dc=1) | HOC total amount | HOL rows (dc=1) | HOL total amount | Pattern |
|------|----------------|-----------------|----------------|-----------------|---------|
| NF | 3,874 | £13.0m | 9,857 | £1.97m | Paired with NT (identical counts + amounts) |
| NT | 3,874 | £13.0m | 9,857 | £1.97m | Paired with NF |
| RF | 68 | £0 | 31 | £15.3m | Paired with RT — zero at HOC |
| RT | 68 | £0 | 31 | £15.3m | Paired with RF |
| TF | 51 | £15.0m | 50 | £178.9m | Paired with TT — largest unknown |
| TT | 51 | £10.9m | 50 | £44.6m | Paired with TF |
| OS | 51,297 | £0 | 21,799 | £0 | **No dc_flag=-1 counterpart at all** — anomalous. Zero amounts. |
| WU | — | — | 179 | £12.7m | HOL only |
| TC | 8 | £31k | 10 | £0 | Small/zero |

The NF/NT, RF/RT, and TF/TT pairs are almost certainly **internal asset transfer types** — when an asset moves between cost centres or entities, one side is debited and the other credited. TF/TT is significant: £178m at HOL. The NBV formula cannot be finalised until Parliament confirms whether these should be included and on which side.

OS is the most anomalous: 51k rows at HOC, 21k at HOL, all zero amount, no year-end reversal entry. Likely a marker or flag transaction rather than a financial posting.

**VN count anomaly (HOC):** `dc_flag=1` has 487 VN rows but `dc_flag=-1` has only 477 — 10 revaluation transactions without a year-end reset mirror. These are likely recent postings not yet through a year-end close. No action required, but confirms the `dc_flag=1` filter is essential.

### Amount sign convention — NOT YET CONFIRMED

The NBV formula in the Python dashboard currently applies signs based on trans_type category (positive for CA/PC/VN, negative for ND/ED/FD/SA). Whether amounts in `aattrans` for these types are stored as absolute positives (formula applies the sign) or as signed values (ND already negative) has not been explicitly confirmed from real data. Run:

```sql
SELECT trans_type, MIN(amount), MAX(amount), AVG(amount)
FROM aattrans WHERE dc_flag = 1 AND trans_type != 'CI'
GROUP BY trans_type ORDER BY trans_type;
```

If ND always has negative MIN and MAX → amounts are signed (formula must not double-negate). If ND always has positive MIN and MAX → amounts are absolute (formula is correct as written).

### Balance formula status

Current formula in `assets.py` / `get_asset_volumetrics`:
```
NBV = (CA + PC + VN + ZU) − (ND + ED + FD + SA)
```

Limitations as of June 2026:
- ZU excluded from real data — has no effect
- NF, NT, RF, RT, TF, TT, WU, OS, TC all excluded — **TF/TT alone is £178m at HOL**
- Amount sign convention unconfirmed — formula may double-negate depreciation
- **Do not rely on balance totals from the dashboard until Parliament confirms the unknown trans_types and sign convention**

### Depreciation method codes — confirmed June 2026

Parliament uses four depreciation method codes across both houses:

| Code | Meaning | Requires `lifetime` | Requires `depr_percent` | HOC | HOL |
|------|---------|--------------------|-----------------------|-----|-----|
| `LNA` | Net book value ÷ lifetime | Yes (`lifetime > 0`) | No | ✓ | ✓ |
| `LNB` | Capitalised amount × fixed percentage | No | Yes (`depr_percent > 0`) | ✓ | No |
| `MAN` | Manual (manually calculated) | Unknown | Unknown | ✓ | ✓ |
| `NOD` | Not depreciated | No | No | ✓ | ✓ |

**`LNB` is HOC-only** — any HOL record with `depr_method = 'LNB'` is invalid data.

**MAN (manual):** whether `lifetime` or `depr_percent` is required for MAN is not yet confirmed. No checks on MAN-specific field requirements have been written until this is clarified.

DQ checks updated to reflect confirmed codes (June 2026):
- `DQ-AD-V04` — tightened to flag `LNA` with `lifetime <= 0` only
- `DQ-AD-C05` — rewritten: flags `LNB` with `depr_percent <= 0`
- `DQ-AG-V05` — rewritten: flags `LNA` with `lifetime <= 0` at group level
- `DQ-AG-C03` — new: flags `LNB` with `depr_percent <= 0` at group level

Removed as no longer applicable: `DQ-AD-V01`, `DQ-AG-V01` (valid method list was wrong), `DQ-AD-C04` (duplicate of DQ-AD-V04), `DQ-AD-K03` (switch flag referenced BAL which does not exist).

### Checks requiring verification before results are reliable

| Check | Dependency |
|-------|-----------|
| All balance-derived checks (DQ-AB-K01, K02, K04, K05) | Unknown trans_types and sign convention |
| Any check referencing `ZU` | ZU does not exist in real data |
| DQ-AD-C05, DQ-AG-C03, DQ-AD-V04, DQ-AG-V05 | Live but unvalidated — depreciation method meanings confirmed, but no real data run yet to verify results are sensible |
| DQ-MAN-* (any future MAN checks) | lifetime/depr_percent requirements for MAN not yet confirmed |

**Note:** `DQ-AB-V01` (unexpected trans_type) was removed. `DQ-AB-K02` and `DQ-AB-K03` now treat `OS` (historical capitalisation from prior system) as equivalent to `CA` — assets with only an `OS` capitalisation record are no longer flagged.

---

## Current State (as of June 2026)

**Implemented and running against real data on Parliament laptop:**
- Suppliers / AP (master, open transactions, history) — full check suite live
- Customers / AR (master, open transactions, history) — full check suite live
- Fixed Assets (master, depreciation, balances, groups, transactions) — checks live. Depreciation method codes confirmed (LNA/LNB/MAN/NOD) and checks updated accordingly. Balance-derived checks still unvalidated pending Parliament confirmation of unknown `aattrans` trans_type codes (TF/TT/NF/NT/RF/RT/WU/OS) and amount sign convention. See Fixed Assets Domain section above and QUESTIONS_FOR_PARLIAMENT.md Q3. `asset_balances_HOC.csv` re-extracted to exclude closed assets (join to `aatasset WHERE status != 'C'`); HOL re-extract blocked by SELECT permission on `aatasset` in `agresso_HoL` — permission likely reset by database refresh (June 2026).
- Executive Summary (cross-domain overview, scope heatmap, severity breakdown)
- Modal drill-down inspector (dark header, sidebar metrics, flat content panels)
- Aging analysis (AP and AR) with HOC/HOL/Both toggle
- Cross-house uniqueness checks for suppliers (VAT, company reg, IBAN, bank account+sort code, name)

**GL tab — iterative build in progress (21 checks total):**
- Chart of Accounts (`aglaccounts`) loaded — 11 checks live (GL_ACC_*)
- Opening Balances (`aglyearend` / `aglperiodic`) loaded — 3 checks live (GL_BAL_*): AMT_MISSING, ORPHAN_ACC, PL_NONZERO
- Dimension Configuration (`gl_dimconfig`) loaded — 2 checks live (GL_DIM_ATTR_*) + treemap visualisation
- Dimension Values (`agldimvalue`) loaded — 5 checks live (GL_DIM_*): DESC_MISSING, PERIOD_MISSING, PERIOD_INV, ORPHAN_REL, DUP
- **GL Journals (`gl_journals` / `agltransact`) loaded — volumetrics only, no DQ checks yet.** HOC: ~650k rows FY2025/26. HOL: re-extract required with `fiscal_year = 2025` (was incorrectly using 2026). Intro card shows lines, vouchers, accounts, users, period range, voucher type bars.
- GL tab layout: intro cards (CoA · Journals · Dimension Structure) → dimension scorecard → DQ checks section → treemap
- Deferred: `GL_ACC_BFLAG_CON` — bflag reconciliation bit not yet confirmed from real data
- Skipped: `GL_BAL_FX_MISSING` (currency always GBP), `GL_BAL_TOTAL_NET` (aggregate, does not fit row-level model), `GL_DIM_WF_STUCK` (wf_state not used at Parliament), voucher balance integrity check (status filter makes it unreliable — see GL Journals section above)
- Next: DQ checks on `gl_journals` — completeness (missing account, description, dim_1), validity (future trans_date), orphan account cross-reference

**Not yet implemented:**
- PBF tab (`dashboard/tabs/pbf.py` is a placeholder)

**Dummy data generator** (`scripts/generate_gl_dummy_data.py`) updated to match all confirmed real formats:
- Chart of accounts: Excel serial dates, CA/CM/LA clients, bflag powers of 2
- Opening balances: signed amounts, dc_flag=0, trans_date=1, dim_1 only, YYYYPP periods
- Dimension config: summary counts per (client, attribute_id), dim_position 0–7 / letter / X
- Dimension values: YYYYMM period_from/period_to integers, Excel serial last_update, blank wf_state, rel_value references actual dim_value codes, all status='N'

**If the Parliament laptop needs to pull a code update**, run `git pull` — the `data/` folder is ignored so real data files are never touched. If git complains about untracked files in `data/`, run `git rm --cached -r data/` first (this happened once during the initial `.gitignore` setup).

**SQL files in `sql/`** are the extraction specs — each has a `HOW TO RUN` header with the exact SSMS database and output filename. The Python rule lambdas in `rules/` are the executable equivalents of the `DATA QUALITY TESTS` sections in each SQL file.
