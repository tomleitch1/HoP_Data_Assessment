# Build Spec — Projects Tab (Scope Viewer)

**Status:** BUILT on dummy data (October 2026). Not yet run against the real files on the Parliament laptop. See section 13 for what changed from the draft during the build.
**Migration scope:** Seq 22, Active Projects
**Scope statement (as written):** *Opening cumulative position (spend-to-date, commitments, and remaining budget) as at cutover for all projects active at go-live.*

---

## 1. Purpose

The tab answers three questions, in this order:

1. **What is in scope?** Which projects are active, how many there are, and how they split by house, category and portfolio.
2. **What is the opening position?** For each project: spend to date, open commitments and remaining budget, plus how that position built up year by year.
3. **Can the data be trusted?** Data quality checks on the project list and the financials, in the same scorecard/grid/modal format as every other tab.

The tab also produces the **SI extract**: a workbook the System Integrator can load into the new ERP's projects module (section 7).

Parliament does not use a Unit4 projects module today. Projects are built from GL dimensions (Unit → HAIS code) plus two classification tags (Projcat, Projgrp). This tab is where that structure gets turned into something a projects module can take.

---

## 2. Confirmed facts

| Fact | Source |
|---|---|
| A project is a **Unit** (e.g. `C2185` Increase Desk Capacity). The HAIS codes under it are its cost lines (likely tasks in the new ERP). | Krishna, Oct 2026 |
| **Projgrp** is how the business manages the portfolio. Each group has an allocated director. | Krishna / Ebenezer Oduwole |
| **Projcat** (CAT A / B / C) matters to the EPMO, which focuses mostly on CAT A. | Krishna / Ebenezer Oduwole |
| Every code on Krishna's list is active (it includes status `S`). | Krishna |
| Ben's file covers **all HAIS codes** from April 2020. Earlier history is available on request. | Ben |
| Ben's columns: Q = Committed purchase (amount left on PO), R = Actuals, S = Current Budget. | Ben |
| The new ERP will have a projects module. | Tom |

---

## 3. Open questions

Each question lists who answers it, and how the build handles it until it's answered. None of them blocks the build.

| # | Question | Ask | Interim handling |
|---|---|---|---|
| Q1 | Are **Annual Requirements** Units (`F-ANRP`, e.g. staff and property running costs) projects for migration, or only CAT A / B / Other? | Ebenezer | Build with everything. A **scope filter** at the top of the tab switches between "Projects only" and "Include Annual Requirements", so the volumes for both answers are visible. |
| Q2 | Is "Other Project" (`F-MNSP`) the same as CAT C? | Ebenezer | Label it "Other Project (CAT C?)" until confirmed. |
| Q3 | ~~Is **Committed purchase** a current PO balance that can be summed across periods without double counting?~~ **Answered (Tom, Oct 2026): yes, sum it.** Checked on real data for `A1000100`: amounts never repeat across periods for the same account, so it isn't a carried-forward balance. Each row is the remaining open PO amount for that account and period (consistent with `aaghocbud.po_rest_com_amt`). | — | Sum per HAIS code = current open commitment. |
| Q4 | Budget is £0 on capital lines in the sample. Is project budget held at a different account or level? | Ben | Roll budget up to HAIS code and Unit before comparing with actuals. Never compare line by line. |
| Q5 | Should spend to date include **all account types** (income, recharges, depreciation), or expenditure only? | Ben / Ebenezer | Keep every line. Show Mipck-l1 so lines can be filtered, and add an "Expenditure only" toggle (definition to confirm). |
| Q6 | Do any active projects have spend **before April 2020**? | Ben | Flag projects whose first activity is in the first period of the extract (`PRJ_HISTORY_TRUNCATED`). If there are many, request the earlier data. |
| Q7 | The SI will want a **project manager / owner and start / end dates** per project. These aren't in either file. Where are they held? | Ebenezer | Leave the columns in the SI extract blank and list them as a gap in the README sheet. |
| Q8 | The scope request mentions **archive**. Is this scope for migration into the new ERP, archive, or both? | Tom | Treated as migration scope throughout this spec. |

---

## 4. Data sources

Both files are single combined files (not split by house), saved on the Parliament laptop under `data/projects/`. This is the same single-file pattern as `budgets_report` and the Atamis files.

### 4.1 Project list (Krishna) → `data/projects/project_list.csv` → frame `project_list`

One row per HAIS code.

| Raw header | Column | Notes |
|---|---|---|
| Department / Department(T) | `department` / `department_desc` | |
| Directorate / Directorate(T) | `directorate` / `directorate_desc` | |
| Cost Centre / Cost Centre(T) | `costc` / `costc_desc` | |
| Projcat / Projcat(T) | `projcat` / `projcat_desc` | `F-MAJP` CAT A, `F-MINP` CAT B, `F-MNSP` Other, `F-ANRP` Annual Requirements |
| Projgrp / Projgrp(T) | `projgrp` / `projgrp_desc` | Portfolio. Two code schemes in use (`F-W` / `F017` both "Staff") |
| Unit / Unit(T) | `unit` / `unit_desc` | **The project** |
| HAIS Code / HAIS Code(T) | `hais_code` / `hais_desc` | The cost line. Join key to Ben's file |
| S | `status` | All `N` in the sample |

### 4.2 Project financials (Ben) → `data/projects/project_financials.csv` → frame `project_financials`

One row per account × HAIS code × house × period. Many thousands of rows.

| Raw header | Column | Notes |
|---|---|---|
| Mipck-l1 / Mipck-l1(T) | `mipck_l1` / `mipck_l1_desc` | Top-level cost type (e.g. `CX01` Capital Expenditure) |
| Mipck-l2 / Mipck-l2(T) / Mipck-l3 | `mipck_l2` / `mipck_l2_desc` / `mipck_l3` | |
| Account / Account(T) | `account` / `account_desc` | |
| Department, Directorate, Costc, Unit | `department`, `directorate`, `costc`, `unit` | Compared with Krishna's list by `PRJ_ATTR_MISMATCH` |
| Haiscode / Haiscode(T) | `hais_code` / `hais_desc` | Join key |
| Recharge | `house` | `HOC` / `HOL`. A shared code appears once per house with the amount already split (e.g. 60/40, 70/30) |
| Year | `fiscal_year` | **Start-year convention:** 2020 = FY2020/21 |
| Period | `period` | YYYYPP integer (202012 = FY2020/21 P12). Parse as numeric, never as a date |
| Committed purchase | `committed` | Column Q. See Q3 |
| Actuals | `actuals` | Column R |
| Current Budget | `budget` | Column S. See Q4 |
| Current Forecast | `forecast` | Loaded, not used in scope figures (blended actuals + forecast) |

Amounts arrive comma-formatted (`1,800.00`). Add the four amount columns to the engine's numeric comma-strip list.

---

## 5. Derived model — `dashboard/core/projects.py`

`build_project_frames(frames)` is called at the end of `load_data()`, the same way as `build_asset_nbv`. It's rebuilt on every load, never pickled, and hashed into `_engine_sig()`. It adds four frames.

| Frame | Grain | Key columns |
|---|---|---|
| `project_codes` | One row per HAIS code on the list | List attributes + `project_type` (CAT A / CAT B / Other / Annual Requirements) + `has_activity`, `first_period`, `last_period`, `houses` (HOC / HOL / Shared) |
| `project_units` | **One row per Unit × house.** This is the opening position. | `unit`, `unit_desc`, `house`, `projcat`, `projgrp`, `costc`, `directorate`, `department`, `hais_count`, `spend_to_date`, `commitments`, `budget_to_date`, `remaining_budget` (= `budget_to_date` − `spend_to_date`), `remaining_after_commitments` (= remaining − commitments), `first_period`, `last_period`, `current_fy_actuals`, `current_fy_budget` |
| `project_history` | One row per Unit × house × financial year | `fiscal_year`, `fy_label` (e.g. "2024/25"), `actuals`, `spend_to_date` (running total), `budget`, `budget_to_date`, `remaining_budget` |
| `project_reconciliation` | One row per HAIS code across both files | `on_list`, `in_financials`, `total_actuals`. Feeds the coverage panel |

**Rules:**
- Join Ben → Krishna on `hais_code` (stripped strings on both sides; never join blank to blank).
- Ben's own `unit` decides which Unit a line rolls up to only if the HAIS code isn't on the list. Otherwise use Krishna's Unit. Disagreements are reported by `PRJ_ATTR_MISMATCH`.
- A Unit's classification (Projcat, Projgrp, etc.) is taken from its HAIS codes. If they disagree, `PRJ_UNIT_MULTI_CLASS` flags it and the most common value is used.
- "Shared" means the same HAIS code has rows under both houses. The position is always held per house, because the SI loads each house's entity separately.
- **Reconciliation invariant:** total `spend_to_date` across `project_units` = total `actuals` in `project_financials` for on-list HAIS codes. This is asserted in testing and shown on the tab.

---

## 6. Tab layout — `dashboard/tabs/projects.py`

Same structure as the other tabs: story first, then DQ. Sections from top to bottom:

| # | Section | Answers | Content |
|---|---|---|---|
| 1 | **Hero** | What is this? | Title, scope statement, data sources with row counts, "data as at" (latest period in Ben's file), history start (FY2020/21) |
| 2 | **Scope filter** | — | Segmented control: *Projects only* / *Include Annual Requirements*; *All costs* / *Expenditure only*; *HoC / HoL / Both*. Drives every section below except DQ. |
| 3 | **Scope headline** | How big is it? | KPI strip: projects (Units), cost lines (HAIS codes), spend to date, open commitments, remaining budget. Split by HoC / HoL / Shared. |
| 4 | **By category and portfolio** | Where is the money? | Spend to date by Projcat (CAT A emphasised) and by Projgrp (portfolio). Bars clickable → modal of Units. |
| 5 | **Opening position table** | What does each project carry over? | One row per Unit (HoC / HoL / total columns). Sortable, filterable, paged. Clicking a row opens the **project modal**: year-by-year history chart and table, plus the HAIS code lines under it. |
| 6 | **Spend history** | How did it build up? | Actuals by financial year, stacked by Projcat, with cumulative line. |
| 7 | **Coverage and reconciliation** | Do the two files agree? | On list with financials / on list with no activity / spend on HAIS codes not on the list. The invariant check (section 5) shown as a pass / fail tick. |
| 8 | **Data quality** | Can we trust it? | `render_dimension_scorecard()` + `render_dimension_grid()`, standard modal drill-down. |
| 9 | **Export** | What goes to the SI? | Button to download the SI extract (same content as the script in section 7). |

### 6.1 Data Profile section (built first, answers Q3–Q6)

A collapsible section at the bottom of the tab, titled "Data Profile: how the source data behaves". It answers the open questions about Ben's file directly from the data, so nobody needs to build pivot tables. Every panel states the question, shows the evidence, and gives a plain-English reading (e.g. "Budget only exists in 2 of 7 years").

| Panel | Question it answers | Shows |
|---|---|---|
| **Budget by year** | Q4: is budget held for past years, or only the current one? | Actuals vs Current Budget per financial year (bars), and the number of years with any budget at all |
| **Budget by cost type** | Q4: does capital spend have a budget? | Actuals vs Current Budget by Mipck-l1 (Capital Expenditure, Salaries, Income…), flagging any type with spend but no budget |
| **Budget placement** | Q4: is budget held on different lines from spend? | Count of HAIS codes / accounts that have actuals only, budget only, or both; and the same rolled up to Unit. If many lines are "budget only" or "actuals only" but Units have both, budget is held at a different level. |
| **Commitment repeat test** | Q3: confirms commitments don't repeat across periods | Number of account × HAIS code combinations where the same commitment amount appears in consecutive periods (expected 0) |
| **Commitment age** | Q3: how old are open commitments? | Open commitment £ by financial year of the period it's posted to, plus the count of residual balances under £5 |
| **Cost types** | Q5: what does "all account types" include? | Actuals by Mipck-l1 with income / recharge types highlighted, so the "Expenditure only" definition can be agreed |
| **History start** | Q6: is spend before April 2020 missing? | Number of Units whose first activity is in the extract's first period, and their spend to date |

The panels use the full project financials (not the scope filter), because they describe the source file rather than the scope.

All modals use the shared `modal-overlay` and set `modal-export-context` (type `projects_unit` / `projects_segment`), so the Export button works on them.

---

## 7. SI extract — `scripts/generate_projects_export.py`

Output: `trackers/projects/projects_scope.xlsx` (gitignored, like every other export). Includes every listed code and all cost types unless flags are passed (`--projects-only`, `--expenditure-only`). The tab's download button builds the same workbook using the Scope and Cost type filters currently selected.

| Sheet | Grain | Columns |
|---|---|---|
| `README` | — | Scope statement, as-at period, filters applied, definitions (spend to date, remaining budget), known gaps (Q7: owner, dates), open questions |
| `Project_Header` | Unit | Unit, description, Projcat, Projgrp, cost centre, directorate, department, houses, status, first / last period, number of cost lines, *project manager (blank)*, *start / end date (blank)* |
| `Project_Tasks` | HAIS code | HAIS code, description, Unit, houses, status, first / last period |
| `Opening_Position` | Unit × house | Spend to date, commitments, budget to date, remaining budget, remaining after commitments |
| `Annual_History` | Unit × house × FY | Actuals, spend to date, budget, budget to date |
| `Task_Position` | HAIS code × house | Same figures as `Opening_Position`, one level down, in case the SI loads at task level |
| `Reconciliation` | — | Totals by file, invariant result, coverage counts |

DQ findings go through the existing tracker: `python scripts/generate_tracker.py projects HOC` / `HOL` / `Parliament` (the list checks).

---

## 8. Data quality checks — `dashboard/core/rules/project_rules.py`

Scope ID `Scope.PROJECTS = 34`. Scope 22 is already used by `GL_BALANCES` in the enum, so it can't match the Seq 22 number. Populations are defined in one helper shared by `run_dq_analysis()` and `get_failing_records()`, the same pattern as `nbv_population()`.

### 8.1 On the project list (`project_codes`, one row per HAIS code)

| ID | Dimension / Severity | Fails when |
|---|---|---|
| `PRJ_LIST_DUP_HAIS` | Uniqueness / High | HAIS code appears more than once on the list |
| `PRJ_LIST_MISSING_CLASS` | Completeness / High | Projcat or Projgrp is blank |
| `PRJ_LIST_HAIS_UNIT_PREFIX` | Consistency / Medium | HAIS code doesn't start with its Unit code (`C0046100` must sit under `C0046`) |
| `PRJ_LIST_DO_NOT_USE_ACTIVE` | Validity / Medium | HAIS or Unit description contains "DO NOT USE" but status is `N` |
| `PRJ_LIST_DUP_DESC` | Uniqueness / Low | Two active HAIS codes under different Units share a description (cloned codes, e.g. `C2418100` / `C7780100`) |
| `PRJ_LIST_PROJGRP_DUP_DESC` | Consistency / Low | A Projgrp code shares its description with another code (`F-W` / `F017` "Staff") |

| `PRJ_UNIT_MULTI_CLASS` | Consistency / High | The Unit's HAIS codes carry more than one Projcat, Projgrp, cost centre or directorate. A project needs one of each. Every cost line of the Unit is flagged. |
| `PRJ_NO_ACTIVITY` | Completeness / Medium | Listed cost line with no actuals, budget or commitments since April 2020. Candidate to exclude from migration. |

### 8.2 On the project (`project_units`, one row per Unit × house)

| ID | Dimension / Severity | Fails when |
|---|---|---|
| `PRJ_NO_BUDGET` | Completeness / Medium | Actuals in the current FY but no current FY budget (after rolling budget up to the Unit, per Q4) |
| `PRJ_OVERSPEND` | Consistency / Medium | Spend to date exceeds budget to date by more than 5% and £1,000 |
| `PRJ_NEG_SPEND_TO_DATE` | Validity / Medium | Spend to date below −£1 (more credits than costs) |
| `PRJ_HISTORY_TRUNCATED` | Completeness / Low | First activity within the first 3 months of the extract (FY2020/21 P1 to P3). Spend before April 2020 is probably missing (Q6). |

### 8.2b On open commitments (`project_commitments`, one row per HAIS code × account × house × period)

| ID | Dimension / Severity | Fails when |
|---|---|---|
| `PRJ_NEG_COMMITMENT` | Validity / Low | An open commitment line below −£1 (over-matched PO line) |
| `PRJ_STALE_COMMITMENT` | Consistency / Medium | Open commitment posted to a period more than 12 months before the extract's latest period. These are old POs still showing money outstanding (seen on real data back to FY2022/23). |
| `PRJ_RESIDUAL_COMMITMENT` | Validity / Low | Open commitment between £0 and £5. These are leftovers on POs that are effectively finished (e.g. £0.03, £3.00 seen on real data). |

### 8.3 Between the two files

| ID | Dimension / Severity | Table | Fails when |
|---|---|---|---|
| `PRJ_ATTR_MISMATCH` | Consistency / Medium | `project_codes` | Ben's Unit, cost centre, directorate or department for a HAIS code disagrees with Krishna's list |
| `PRJ_SPLIT_INCONSISTENT` | Consistency / Low | `project_codes` | A shared HAIS code's HoC / HoL split ratio changes between years by more than 5 percentage points |

Spend on HAIS codes **not on the list** is shown in the coverage panel (section 6.7), not scored. Most of it is ordinary running cost, so it isn't a defect.

### 8.4 Later, not in this build

Cross-domain links, built only once confirmed on real data (the GL rule: no speculative checks):
- **PO:** which `apodetail.dim_n` holds the HAIS code. Then: open PO balance per HAIS code vs Ben's committed figure.
- **Atamis:** `contracts_report` has `HAIS Product Code(s)` and `EPMO Project Name or SE Project Code`. Contracts could be linked to projects.
- **Assets:** CAT A / B capital projects may feed assets under construction.

---

## 9. Dummy data — `scripts/generate_projects_dummy_data.py`

Writes both files to `data/projects/` with the **exact real headers** (including `(T)` columns, comma-formatted amounts, start-year `Year`, YYYYPP `Period`).

- About 60 Units and 250 HAIS codes across all four Projcats and both Projgrp code schemes
- Financials for FY2020/21 to FY2026/27, monthly periods, several accounts per HAIS code
- Shared codes split 60/40 and 70/30, the rest HoC-only or HoL-only
- Budgets posted to a different account from actuals on some Units (so the roll-up rule in Q4 is exercised)
- Some HAIS codes in the financials that aren't on the list (ordinary running cost)
- **One planted case per DQ check**, tagged in an `_edge_case` column, so every check is proven to fire

---

## 10. Engine wiring

Following the existing "Adding a Completely New Dataset and Tab" steps in `CLAUDE.md`:

1. `SUBDIR['projects'] = ['project_list', 'project_financials']`; add both to `single_files` and a `_PROJECT_RENAME` map.
2. Add `committed`, `actuals`, `budget`, `forecast` to the numeric comma-strip list; keep `period` / `fiscal_year` numeric; add `hais_code` / `unit` to the string clean-up.
3. `Scope.PROJECTS = 34` and a `SCOPE_CONFIG` entry in `config.py`.
4. `build_project_frames()` at the end of `load_data()`, hashed into `_engine_sig()`.
5. `get_project_checks()` imported in `get_dq_checks()`; population helper in both `run_dq_analysis()` and `get_failing_records()`.
6. `get_check_columns()` entries for every `PRJ_*` check.
7. Tab wired into `app.py` as `Projects`, plus `python run_dashboard.py projects` tab-scoped mode.
8. `projects` support in `generate_tracker.py`.

---

## 11. Build phases

Each phase ends with a commit. "Done when" is the acceptance test.

| Phase | Work | Done when |
|---|---|---|
| 1 | Dummy data generator + loading + tab shell with hero and **Data Profile** (section 6.1) | Both frames load with clean column names and numeric amounts; every Data Profile panel renders on dummy data. **Then pause:** run on the Parliament laptop, answer Q3–Q6 from the panels, and update this spec before phase 2. |
| 2 | Derived model (`projects.py`) | Reconciliation invariant holds on dummy data; a hand-checked Unit's position matches its raw rows |
| 3 | Tab sections 1–7 + project modal | Tab renders with no callback errors (verified by raw `_dash-update-component` round trips, as for other tabs); filters change every figure |
| 4 | DQ checks + drill-downs | Every planted case is caught; modal row counts equal `dq_results.failing` for every check |
| 5 | SI extract script + tab export button | Workbook opens; Opening_Position totals equal the tab headline |
| 6 | Run on the Parliament laptop | Real files load; review the numbers and answers to Q1–Q8, then adjust |

---

## 12. Decisions log

| Date | Decision |
|---|---|
| Oct 2026 | Project = Unit; HAIS code = cost line (Krishna) |
| Oct 2026 | Positions held per house; shared codes split using Ben's Recharge rows |
| Oct 2026 | Scope not yet decided between all codes and projects only: build both, toggle on the tab |
| Oct 2026 | Committed purchase is summed per HAIS code (Q3, checked on real data). Stale and residual commitment checks added. |
| Oct 2026 | Open questions about the source data are answered on the dashboard (Data Profile section), not with Excel pivots. Built first, in phase 1. |

---

## 13. Built (October 2026): what changed from the draft

Files: `dashboard/core/projects.py` (calculation, views, drill-downs, DQ populations and evidence), `dashboard/core/projects_export.py` (SI workbook), `dashboard/core/rules/project_rules.py` (17 checks), `dashboard/tabs/projects.py` (tab and modal content), `dashboard/assets/projects.css` (filter styling), `scripts/generate_projects_dummy_data.py`, `scripts/generate_projects_export.py`. Wiring in `data_engine.py`, `config.py` and `app.py`.

- **Navigation.** The horizontal tab bar ran out of room with a ninth tab, so it was replaced by a menu button (top left of the header) that opens a drawer listing every section grouped by migration area. The current section shows next to the title. The selected section is held in a `dcc.Store` still called `master-tabs`.
- **Three DQ buckets.** List checks run once on the whole list under house `Parliament` (purple), because Krishna's list isn't split by house. Position and commitment checks run per house (HOC / HOL).
- **Checks moved to the right grain.** `PRJ_UNIT_MULTI_CLASS` and `PRJ_NO_ACTIVITY` run on cost lines (`project_codes`), not Unit × house: a Unit with no activity has no house to sit under. `PRJ_NEG_COMMITMENT` runs on commitment lines: at project level a single over-matched PO line was netted away by the project's other commitments.
- **`PRJ_HISTORY_TRUNCATED`** uses the first 3 months of the extract, not only the first period, because a running-cost line may not post in P1 itself.
- **Activity signal** added: Live (activity in the last 12 months of the data), Dormant (older), No activity. It's shown on the headline, the opening table and the SI extract, as evidence for "active at go-live".
- **Drill-down chain:** every bar, tile and reading opens the records behind it; any list of projects (on the tab or in the modal) opens the project view; the project view shows its position per house, the year-by-year chart, its DQ flags, its cost lines and its account breakdown. Every modal exports to CSV.
- **Reconciliation invariant** is shown on the tab and in the SI extract, and holds on dummy data.
- **Performance fix (after the first real-data run got stuck on "Updating"):** the 440k-row financials made every render and click recompute from raw lines (40s to open the tab). Views now run off a pre-summarised `project_summary`, project classifications are computed once, and views are cached per filter combination. Tested at 428k rows: 0.2s to open, under 0.3s per click.
- **Fixed in passing:** the GL tab filtered `dq_results` with `scope_id >= 20`, which also pulled in Atamis (30–33) and Projects (34) checks. It now uses scopes 20–23 only.

Verified on dummy data: every planted case is caught, all 32 raw `_dash-update-component` round trips pass (every tab still renders, navigation, filters, every drill kind, project view, both exports, DQ inspector), the SI extract and trackers generate. Visual layout checked with a headless screenshot; the opening position table did not draw in headless Chrome (the app's own hidden placeholder table didn't either), so confirm it on the Parliament laptop.
