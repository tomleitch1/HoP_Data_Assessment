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
python run_dashboard.py
```

App starts at `http://127.0.0.1:8050`. No build step. Place CSV extracts in `data/` before launching.

There are no automated tests. The scripts in `scripts/` generate dummy data for development on this machine:
```bash
python scripts/generate_ap_dummy_data.py   # Supplier / AP data (HOC + HOL split files)
python scripts/generate_dummy_data.py      # Customer / AR data
python scripts/generate_asset_data.py      # Asset data
python scripts/generate_gl_dummy_data.py   # GL data
```

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
- `RAG_GREEN_THRESHOLD = 90`, `RAG_AMBER_THRESHOLD = 70`

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
├── gl/          gl_chart_of_accounts.csv, gl_dimension_values.csv
│                gl_opening_balances.csv, gl_transact_dimensions.csv
│                gl_journals_HOC/HOL.csv
└── assets/      asset_master_HOC/HOL.csv, asset_depreciation_HOC/HOL.csv
                 asset_balances_HOC/HOL.csv, asset_trans_flags_HOC/HOL.csv
                 asset_groups_HOC/HOL.csv
```

`data_engine.py` uses a `SUBDIR` map and `_data_path()` helper to resolve paths — adding a new file means registering it in `SUBDIR` and either `file_map` or `split_files` in `load_data()`.

---

## HOC/HOL Data Split

All supplier, customer, asset, and GL journal tables use **per-house split files** (`*_HOC.csv` + `*_HOL.csv`). The engine concatenates them and assigns `house` from the filename suffix — **not** from the `client` column. The `client` column contains internal Unit4 fund codes (e.g. `CA`, `CF`, `CM` for HoC; `LA` for HoL) and must not be used for house filtering anywhere.

GL reference tables (`gl_chart_of_accounts.csv`, `gl_dimension_values.csv`, `gl_opening_balances.csv`) are currently single combined files — these will need splitting to split files once live data arrives.

All DQ analysis runs per-house. `dq_results` always has a `house` column. Charts typically show HOC and HOL side by side.

---

## Key Workflows

### Updating for Live Data (Column Names / Status Codes)
Edit only `dashboard/core/config.py`:
- Column name change → update `COLUMN_MAP` right-hand side
- Status code change → update the relevant `*Config` class constant

### Adding a DQ Rule to an Existing Domain
Add a tuple to the list in the relevant `dashboard/core/rules/*_rules.py`. Use existing tuples in the same file as templates. The engine picks it up automatically via `get_dq_checks()`.

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
- **Payment method codes in real Agresso data**: AS, AU, BB, BO, CA, CH, DD, EF, EU, FC, FP, IB, II, IN, IP, LE, RF, TF, UE, VD, VI. The DQ rules `SUP_BACS_NO_BANK` (checks `pay_method == 'BACS'`) and `SUP_INT_NO_IBAN` (checks `pay_method == 'INT'`) currently return 0 results because those codes do not exist. The correct codes for domestic and international payment methods need to be confirmed with Parliament before these rules can work. Do not attempt to guess — ask which codes require a sort code/bank account and which require an IBAN.

---

## Modal Drill-Down Inspector

Triggered by clicking any bar in a dimension chart or any row in a DQ results table. Renders via `handle_modal_logic` callback in `app.py`.

**Layout:**
- Single dark header bar (`#1e1528`) — one dark element, everything else white
- Left sidebar (320px): dimension pill at top, then 2×2 grid of stat cards (failing records / pass rate / records assessed / criticality). Stats at 28px/800 weight, rounded cards (`borderRadius: 12px`). Failing count uses `row['failing']` from `dq_results` (same source as charts) — NOT `len(df)` which can be inflated.
- Right panel: "Why this matters" full width, then rule definition + critical fields side by side. Remediation section removed.
- Table strip: record count header strip
- Failing records table: surgical column highlighting (red=source, blue=target, grey=bridge)

**`status` column**: always shown in the evidence table. For the generic fallback path (most checks), `status` is included via `key_fields` in `app.py`. For specific early-return checks (`AP_ORPHANED_TRANS`, `HIS_ORPHANED`, etc.) it must be included explicitly in the `cols` list in `get_failing_records()`.

**Column display logic** (`app.py` — `handle_modal_logic`):
- Checks whose columns are prefixed with a known table name (e.g. `AP_INVOICES.`, `ASSET_MASTER.`) → `is_prefixed = True` → all returned columns shown
- All other checks → `is_prefixed = False` → column filter runs, keeping only columns whose bare name is in `key_fields` (identifiers + `status`) or in `base_cols` (the check's highlighted fields from `get_check_columns()`)
- **Cross-house checks** (`_XHOUSE_CHECKS` set): bypass the single-house filter and the column filter entirely; render as two separate DataTables side by side (HOC green header / HOL red header), deduplicated by matching identifier so rows align for visual comparison.

Uses `dash-iconify` for Lucide icons (`lucide:alert-circle`, `lucide:check-circle-2`, `lucide:database`, `lucide:table-2`, `lucide:download`, `lucide:x`, `lucide:arrow-right`).

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

**Live data:** The Parliament laptop (`leitchtb`) is running against real Agresso data as of May 2026. Supplier/AP data (asuheader, asutrans) confirmed working including DQ checks, modal drill-down, and AP aging analysis. Remaining domains (customers, GL, assets) still need real CSVs extracted and placed in the correct `data/` subfolders. This machine still uses dummy data. When column names or status codes differ from dummy data, update `COLUMN_MAP` and the relevant `*Config` constants in `config.py` here, push, and pull on the Parliament laptop.

**If the Parliament laptop needs to pull a code update**, run `git pull` — the `data/` folder is ignored so real data files are never touched. If git complains about untracked files in `data/`, run `git rm --cached -r data/` first (this happened once during the initial `.gitignore` setup).

**SQL files in `sql/`** are the extraction specs — each has a `HOW TO RUN` header with the exact SSMS database and output filename. The Python rule lambdas in `rules/` are the executable equivalents of the `DATA QUALITY TESTS` sections in each SQL file.
