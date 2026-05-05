# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

**Parliament Finance Systems Programme – Unit4 Data Quality Assessment Dashboard**

A Dash/Plotly web application that executes data quality (DQ) checks against financial data extracted from Parliament's legacy system (Unit4 predecessor), covering five domains: General Ledger, Suppliers/AP, Customers/AR, Fixed Assets, and PBF. Data arrives as CSV exports from two parliamentary houses (HoC and HoL) and is assessed against ~80+ rules across completeness, validity, referential integrity, and consistency dimensions.

---

## Running the App

```bash
python run_dashboard.py
```

App starts at `http://127.0.0.1:8050`. No build step. Place CSV extracts in `data/` before launching.

There are no automated tests. The scripts in `scripts/` generate dummy data for development:
```bash
python scripts/generate_dummy_data.py      # AP/AR data
python scripts/generate_asset_data.py     # Asset data
python scripts/generate_gl_dummy_data.py  # GL data
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

## HOC/HOL Data Split

CSVs come in two variants:
- **Single file** (e.g. `supplier_master.csv`) → registered in `file_map` in `load_data()`
- **Per-house files** (e.g. `asset_master_HOC.csv` + `asset_master_HOL.csv`) → registered in `split_files`; the engine concatenates them and adds a `house` column

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

---

## Current State (as of May 2026)

**Implemented and tested with dummy data:**
- GL (Chart of Accounts, Dimension Values, Opening Balances, Journals)
- Suppliers / AP (master, open transactions, history)
- Customers / AR (master, open transactions, history)
- Fixed Assets (master, depreciation, balances, groups, transactions)
- Executive Summary (cross-domain overview, scope heatmap, severity breakdown)
- Modal drill-down inspector (failing record detail with surgical column highlighting)
- Aging analysis (AP and AR)

**Not yet implemented:**
- PBF tab (`dashboard/tabs/pbf.py` is a placeholder)

**Pending:** Live Unit4 data has not yet been ingested. The app runs entirely on dummy data generated by `scripts/`. When live CSVs arrive, update `COLUMN_MAP` and status code constants in `config.py` before re-running.

**SQL files in `sql/`** are the extraction specs for Parliament's IT team — they define what data to pull and serve as authoritative DQ test documentation. The Python rule lambdas in `rules/` are the executable equivalents of the `DATA QUALITY TESTS` sections in each SQL file.
