# Migration Scope Engine

> **The in-scope list is exactly what we would hand the SI if they asked for the extract today.**

The DQA dashboard asks "what is wrong with the data?", one table per test. This module asks
**"what are we migrating?"**. It takes every record through a scoping pipeline, classifies it, and
shows data quality issues as attributes of the records that will actually migrate. It is also the
foundation for the later migration work (mapping to SI templates, transformation, load workbooks).

First build: **supplier master, both Houses**, with the open items, invoice history and POs
needed to apply the scope rules. Customers are registered but not built yet.

---

## Running it

It is a page in the existing dashboard: `python run_dashboard.py`, then **Menu → Migration → Migration Scope**.

| Machine | Data source | How it is chosen |
|---|---|---|
| Parliament laptop | The dashboard's own loaded extracts (`asuheader`, `asutrans`, `asuhistr`, `apoheader`), read-only | Default |
| Development laptop | The module's dummy dataset | `data/migration_scope/settings.json` containing `{"source": "dummy"}` |

```bash
python -m migration_scope.dummy.generate      # rebuild the dummy dataset (data/migration_scope/dummy/)
python -m pytest migration_scope/tests -q     # run the tests (70)
```

Install `rapidfuzz` on the Parliament laptop (`pip install rapidfuzz`). Without it, possible-duplicate
name matching falls back to Python's `difflib`, which is much slower on the full supplier master.

### Monthly routine

1. Run the SQL extracts and drop them into `data/` as usual.
2. Open **Migration Scope**. The overview shows the position now and what changed since last month.
3. **Decisions & uploads → Export steward workbook** (one per House) and put it in SharePoint.
4. Stewards fill in Decision / Reason / Steward. Download the workbook and **upload** it. You see a
   preview (already recorded / new / changed / rejected) before anything is applied.
5. Press **Save this month's position**. That's the official monthly snapshot used for trends.

---

## How a record is classified

Classification is made per **supplier**: House + supplier ID. In HoC the same supplier ID can sit under
client CA and CM; those rows are one supplier, and any disagreement between them (bank details, VAT,
name, postcode) is raised as a Consistency issue (`MS-DQ-CLIENT-DIFF`). Raw rows stay at
House + client + ID and are all shown in the record drawer.

| Step | Rule | Outcome |
|---|---|---|
| 1 | Status not N or P, or a legacy exclusion | Not in scope (never classified) |
| 2 | Non-commercial group or ID range (Members, Peers, staff, witnesses, advisors) | Held: non-commercial |
| 2 | HoL group 03 card accounts | Held: policy decision |
| 3 | No invoice, credit note or PO in 18 months **and** nothing open | **Close** |
| 4 | Non-preferred member of a duplicate group, no activity in 6 months, nothing open | **Close** |
| 4 | Non-preferred member of a duplicate group, still active or has open items | **Monitor** |
| 5 | A blocking data issue | **Fix** |
| 6 | Otherwise | **Keep** |

In scope = Keep + Fix + Monitor. Each record stores every step it went through, in plain English,
with the rule ID. The drawer shows them as "Why it is classified this way".

**Duplicates.** Confirmed matches (same VAT, company number, bank details, or name + postcode after
standardising) form groups. The preferred record has the fewest blocking issues, then has open items
or POs, then has the most recent activity, then is the most complete. If two records are level on all of
these, the rules don't pick one: they stay Monitor until a steward chooses the preferred record.
Similar names are *possible* duplicates: shown for review, never reclassified on their own.
**Cross-House** matches (HoC ↔ HoL) are tagged, not grouped, until the target design is decided
(`cross_house_as_duplicate`).

**Open items.** An open item more than 2 months past its transaction date is "stuck" and needs a
migrate / don't migrate decision. Until then it counts as in scope. If every open item on a dormant
supplier is marked don't migrate, the supplier closes (`MS-TRN-02`).

**Data quality.** The existing DQA supplier tests (`dashboard/core/rules/ap_rules.py`) are run
unchanged on every in-population supplier and tagged by their original test ID, alongside a few of
the engine's own (`MS-DQ-*`). Only the tests listed in `blocking_tests` make a supplier Fix; the rest
are advisory.

---

## Decisions

- Recorded against the supplier (`HOC|20977`), an open item (`HOC|CA|20977|40012345`) or a pair
  (possible duplicates). Every decision has a steward, a reason, when, who entered it, the source
  (workbook name or Dashboard), the ruleset version and the recommendation at the time.
- **Append-only.** A new decision supersedes an older one; nothing is edited or deleted. The store is
  backed up to `data/migration_scope/backups/` before every upload, and uploaded workbooks are archived
  in `data/migration_scope/uploads/`. The signed-off workbooks in SharePoint are the record of truth.
- Decisions survive re-extracts and override the rules; the record shows both ("Rules said Close").
- **Follow-through.** Next month's extract is checked against each decision: *Actioned in Unit4*
  (now status C/T), *Not yet actioned*, *Not in latest extract*, or *Conflict* (closed against a Keep).
  A non-preferred duplicate used after its group was confirmed raises an alert.

Everything under `data/migration_scope/` is real Parliament data on the Parliament laptop and is
gitignored with the rest of `data/`.

---

## Changing a rule or a threshold

Everything is in **`migration_scope/config.py`**. Change it **only on the development laptop**, then
push and pull on the Parliament laptop, as with code.

1. Edit the parameter (e.g. `'stuck_item_months': 3`).
2. Bump `RULESET_VERSION` and add a `CHANGELOG` line saying what changed and who agreed it.

To change wording or add a rule, edit `RULES` in `objects/suppliers.py`. A `Rule` has an ID, name,
plain-English description (with `{parameter}` placeholders), layer, parameters, version, active flag
and the classification it produces. Add the logic in `evaluate()`, record when it fires in `run()`
(the `fired` list drives the rule cards), and add a test in `tests/test_rules.py`.

## Adding an object (customers, bank accounts, assets, POs ...)

1. Write `objects/<object>.py` with the same shape as `suppliers.py`: `RULES`, `load_inputs(frames, source)`,
   `run(inputs, params, decisions, as_of)` returning a `Result` whose `entities` has the standard columns
   (`entity_key`, `house`, `classification`, `recommended`, `decision_status`, `in_scope`, ...), and `funnel()`.
2. Add its parameters to `config.py` and register it in `objects/__init__.py`.
3. Reuse `core/`: standardisation, duplicate matching, the decision store, snapshots and workbooks are
   object-agnostic.

Customers are already registered as "Planned". Open questions before building them: how to tell
individuals from organisations (customer group codes?), duplicate matching off by default for
individuals (Appendix H), and there are no contact fields in the extract.

## Target layer (not built)

The `entities` frame for in-scope records is the input the mapping layer will consume: one row per
supplier, with the preferred record's standardised fields, its client rows, and its decisions. SI
template mapping and transformation rules will sit in `migration_scope/target/` and read from there.

---

## Layout

```
migration_scope/
  config.py            parameters, ruleset version, changelog, storage paths
  core/
    model.py           layers, classifications, decision types, Rule
    standardise.py     standardised layer (names, postcodes, VAT, company no, bank)
    duplicates.py      confirmed groups (union-find) and possible duplicates
    store.py           SQLite: append-only decisions, monthly snapshots, backups
    engine.py          loads data, runs objects, snapshot comparison
    workbook.py        steward workbook export / upload preview / apply, governance summary
  objects/
    suppliers.py       supplier rules, loader and pipeline
  ui/                  Dash screens (overview, records, drawer, decisions, rules) and callbacks
  dummy/generate.py    dummy dataset with every edge case labelled
  tests/               pytest: every rule, decision overrides, workbook round trip, snapshots
```

The only changes outside this folder are one navigation entry and three lines in `dashboard/app.py`,
and the stylesheet `dashboard/assets/migration_scope.css` (every selector scoped to `.ms-root`).
