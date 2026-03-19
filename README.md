# Parliament Data Quality Assessment Dashboard
## Developer & Maintainer Guide

This document outlines the architecture of the dashboard, explains how to maintain its configuration when live data arrives, and provides step-by-step workflows for extending the application.

---

## 1. Project Structure

The project has been refactored into a modular, clean architecture:

```text
C:\Users\CatherineKilleen\Documents\Python\Houses of Parliament\HoP_Data_Assessment\
├── dashboard/                 # Core application directory
│   ├── core/                  # Engine logic, settings, and business rules
│   │   ├── config.py          # Central configuration (mappings, thresholds, settings)
│   │   ├── theme.py           # UI presentation strings, colors, styles
│   │   ├── charts.py          # Plotly visualization logic
│   │   ├── volumetrics.py     # Data aggregation for summary cards
│   │   └── rules/             # Domain-specific Data Quality (DQ) rules
│   │       ├── ap_rules.py    # Supplier and AP checks
│   │       ├── ar_rules.py    # Customer and AR checks
│   │       ├── asset_rules.py # Fixed Asset checks
│   │       └── gl_rules.py    # General Ledger checks
│   ├── shared/                # Shared UI components
│   │   ├── ui.py              # Reusable UI component helpers
│   │   └── dimensions.py      # Dimension/attribute rendering components
│   ├── tabs/                  # Individual UI pages
│   │   ├── aging.py           # AR/AP aging analysis tab
│   │   ├── assets.py          # Fixed Assets tab
│   │   ├── customers.py       # Customers (AR) tab
│   │   ├── exec_summary.py    # Executive summary tab
│   │   ├── explorer.py        # Data explorer tab
│   │   ├── findings.py        # DQ findings tab
│   │   ├── gl.py              # General Ledger tab
│   │   ├── pbf.py             # PBF tab
│   │   └── suppliers.py       # Suppliers (AP) tab
│   ├── app.py                 # Dash application routing and layout
│   └── data_engine.py         # Data loader and execution engine for DQ checks
├── data/                      # Raw CSV extracts go here
├── scripts/                   # Utility scripts (e.g., dummy data generators)
├── sql/                       # SQL queries used to profile and extract data
└── run_dashboard.py           # The single entry point to launch the application
```

---

## 2. Core Architecture

The dashboard operates on a clear separation of concerns:
*   **The Engine (`data_engine.py`):** Loads the CSVs, executes the rule functions against the dataframes, calculates the RAG status, and builds aggregation tables.
*   **The Rules (`dashboard/core/rules/`):** A collection of `lambda` functions. Each file represents a business domain and defines exactly what constitutes a "failing" record.
*   **The Config (`dashboard/core/config.py`):** The "brain" of the app. It holds all the specific threshold values, allowed system codes, and CSV column mappings. It decouples hardcoded business logic from the engine.
*   **The UI (`dashboard/tabs/`):** Reacts to the output of the engine to render charts and tables.

---

## 3. Workflow: Updating Configuration (When Live Data Arrives)

When Parliament provides live Unit4 data, the system codes or column names may differ from the dummy data. **You do not need to rewrite the engine or rules.** You only need to update `config.py`.

### Scenario A: CSV Column Names Change
If `apar_name` becomes `Supplier_Legal_Name`:
1. Open `dashboard/core/config.py`.
2. Locate the `COLUMN_MAP` dictionary.
3. Update the right-hand side of the mapping:
   ```python
   'name': 'Supplier_Legal_Name',
   ```

### Scenario B: Status Codes or Thresholds Change
If the client confirms that 'A' is active instead of 'N', or a supplier is stale after 3 years instead of 2:
1. Open `dashboard/core/config.py`.
2. Locate the relevant namespace class (e.g., `SupplierConfig`).
3. Update the variable:
   ```python
   class SupplierConfig:
       ACTIVE_STATUSES = ['A']  # Was ['N']
       STALE_SUPPLIER_DAYS = 1095  # Was 730
   ```

---

## 4. Workflow: Adding or Modifying a Data Quality Rule

To add a new check for an existing dataset (e.g., a new AP rule):

1. **Locate the Rules File:** Open `dashboard/core/rules/ap_rules.py`.
2. **Add the Tuple:** Add a new tuple to the list returned by the function.
   The format is: `(Rule_ID, Scope_Enum, Object_Name, Dimension, Severity, Description, Intent, Remediation, Source_Table, Joined_Table, SQL_Equivalent, Lambda_Function)`.
3. **Example:**
   ```python
   ('AP_NEW_RULE', Scope.SUPPLIERS, 'Supplier Master', 'Completeness', 'High',
    'Supplier is missing an email address',
    'Ensures communication can occur.',
    'Populate the email field.', 'asuheader', None,
    'email IS NULL',
    lambda df: df['email'].isna()),
   ```

---

## 5. Workflow: Adding a Completely New Dataset and Tab

If you receive a new dataset (e.g., "Fixed Assets"), follow this 4-step process to integrate it end-to-end:

### Step 1: Tell the Engine to Load the Data
1. Place your CSV file(s) in the `data/` folder.
2. Open `dashboard/data_engine.py` and locate `load_data()`. Add your dataset to the appropriate loader:
   Single file (e.g. one CSV covering all entities) → add to `file_map`:
      'fixed_assets.csv': 'assets_table'
   Per-house files (e.g. separate HOC/HOL CSVs) → add to `split_files` instead:
      'asset_master': 'asset_register'
      
      The engine will automatically look for asset_master_HOC.csv and asset_master_HOL.csv, concatenate them, and load the result as asset_register.


### Step 2: Register the Scope and Configuration
1. Open `dashboard/core/config.py`.
2. Add a new ID to the `Scope(IntEnum)`:
   ```python
   ASSETS = 30
   ```
3. Add the configuration to `SCOPE_CONFIG`:
   ```python
   'assets': {
       'label': 'Fixed Assets',
       'tab_value': 'assets',
       'scope_ids': [Scope.ASSETS],
       'tables': ['assets_table'],
       'aging': None,
   },
   ```

### Step 3: Write the DQ Rules
1. Create a new file: `dashboard/core/rules/asset_rules.py`.
2. Define a function `get_asset_checks()` that returns a list of rule tuples (as shown in Workflow 4).
3. Open `dashboard/data_engine.py`, import `get_asset_checks`, and append it inside `get_dq_checks()`:
   ```python
   from dashboard.core.rules.asset_rules import get_asset_checks
   
   def get_dq_checks():
       checks = []
       checks.extend(get_gl_checks())
       # ...
       checks.extend(get_asset_checks())
       return checks
   ```

### Step 4: Build the UI Tab
1. Create a new file: `dashboard/tabs/assets.py`. (You can duplicate an existing tab like `customers.py` as a template).
2. Open `dashboard/app.py`.
3. Import your layout rendering function from the new tab:
   ```python
   from dashboard.tabs.assets import render_assets_layout
   ```
4. Add it to the routing logic in `update_tab_content`:
   ```python
   elif active_tab == 'assets':
       return render_assets_layout(house, frames, dq_results)
   ```
