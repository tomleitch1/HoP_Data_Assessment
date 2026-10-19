"""DQ checks for the Projects tab (Seq 22).

Three tables, all built by dashboard/core/projects.py:
  project_codes        one row per HAIS code on the project list (house 'Parliament')
  project_units        one row per project (Unit) x house: the opening position
  project_commitments  one row per open commitment (HAIS code x account x house x period)

The aggregation is done in projects.py; these lambdas only read its columns.
Populations live in projects.project_population().
"""
from dashboard.core.config import Scope
from dashboard.core.projects import (
    OVERSPEND_ABS, OVERSPEND_PCT, RESIDUAL_COMMITMENT_MAX, SPLIT_DRIFT_PP, STALE_COMMITMENT_MONTHS, TOLERANCE,
)


def _blank(s):
    return s.isna() | (s.astype(str).str.strip() == '')


def get_project_checks():
    S = Scope.PROJECTS
    return [
        # ── The project list (Krishna's list) ────────────────────────────────
        ('PRJ_LIST_DUP_HAIS', S, 'Project List', 'Uniqueness', 'High',
         'HAIS code listed more than once',
         'Each cost line must appear once on the project list. A HAIS code listed twice can be loaded as two tasks '
         'in the new projects module, splitting or doubling its spend and budget.',
         'Remove the duplicate row from the project list, keeping the correct classification.',
         'project_codes', None,
         'COUNT(*) OVER (PARTITION BY hais_code) > 1',
         lambda df: df['dup_count'] > 1),

        ('PRJ_LIST_MISSING_CLASS', S, 'Project List', 'Completeness', 'High',
         'Cost line with no Projcat or Projgrp',
         'Every project must have a category (Projcat) and a portfolio (Projgrp). The EPMO uses the category to '
         'prioritise CAT A projects, and each portfolio has an allocated director. Without both, the project '
         'cannot be classified or owned in the new projects module.',
         'Assign the correct Projcat and Projgrp to the cost line in Unit4.',
         'project_codes', None,
         "projcat IS NULL OR projgrp IS NULL",
         lambda df: _blank(df['projcat']) | _blank(df['projgrp'])),

        ('PRJ_LIST_HAIS_UNIT_PREFIX', S, 'Project List', 'Consistency', 'Medium',
         'HAIS code not under its Unit code',
         'A HAIS code is built from its Unit code plus a suffix (C0046100 sits under C0046). A code that does not '
         'start with its Unit is attached to the wrong project, so its spend would migrate against the wrong '
         'project.',
         'Confirm which project the cost line belongs to and correct the Unit relation in Unit4.',
         'project_codes', None,
         "hais_code NOT LIKE unit + '%'",
         lambda df: ~df['prefix_ok']),

        ('PRJ_LIST_DO_NOT_USE_ACTIVE', S, 'Project List', 'Validity', 'Medium',
         "Cost line marked 'DO NOT USE' but still active",
         "A cost line or project described as 'DO NOT USE' should be closed. While its status is active it will "
         'migrate as a live task and can still be posted to.',
         "Close the code in Unit4, or remove 'DO NOT USE' from its description if it is genuinely in use.",
         'project_codes', None,
         "status = 'N' AND (hais_desc LIKE '%DO NOT USE%' OR unit_desc LIKE '%DO NOT USE%')",
         lambda df: df['do_not_use']),

        ('PRJ_LIST_DUP_DESC', S, 'Project List', 'Uniqueness', 'Low',
         'Active cost line with the same description as one under another project',
         'Two active cost lines under different projects should not share a description. It usually means a project '
         'was re-created under a new Unit without the old codes being closed, so spend is split across both.',
         'Confirm which code is current, move any open balance across and close the other.',
         'project_codes', None,
         'Same hais_desc (ignoring a DO NOT USE prefix) on an active code under another Unit',
         lambda df: df['desc_dup_units'] != ''),

        ('PRJ_LIST_PROJGRP_DUP_DESC', S, 'Project List', 'Consistency', 'Low',
         'Portfolio name shared by more than one Projgrp code',
         'Each portfolio should have one code. Two codes with the same name (e.g. F-W and F017, both "Staff") mean '
         'two coding schemes are in use, and the new projects module needs one.',
         'Agree the surviving Projgrp code for each portfolio and map the other to it.',
         'project_codes', None,
         'COUNT(DISTINCT projgrp) OVER (PARTITION BY projgrp_desc) > 1',
         lambda df: df['projgrp_desc_codes'] != ''),

        ('PRJ_UNIT_MULTI_CLASS', S, 'Project List', 'Consistency', 'High',
         "Project's cost lines disagree on category, portfolio, cost centre or directorate",
         'A project (Unit) needs one category, one portfolio, one cost centre and one directorate. When its cost '
         'lines disagree, the project cannot be created with a single classification in the new projects module.',
         'Agree the correct classification for the project and align every cost line to it.',
         'project_codes', None,
         'COUNT(DISTINCT projcat | projgrp | costc | directorate) OVER (PARTITION BY unit) > 1',
         lambda df: df['unit_class_variants'] != ''),

        ('PRJ_NO_ACTIVITY', S, 'Project List', 'Completeness', 'Medium',
         'Active cost line with no spend, budget or commitments since April 2020',
         'A cost line in scope should have financial activity. One with no actuals, budget or open commitments '
         'since April 2020 is probably dormant and is a candidate to leave out of the migration.',
         'Confirm with the project owner whether the code is still needed, and close it if not.',
         'project_codes', 'project_financials',
         'hais_code NOT IN (SELECT hais_code FROM project_financials WHERE any amount <> 0)',
         lambda df: ~df['has_activity']),

        ('PRJ_ATTR_MISMATCH', S, 'Project List', 'Consistency', 'Medium',
         'Project list and financials disagree on Unit, cost centre, directorate or department',
         'The project list and the financial data must agree on where a cost line sits. If they disagree, the '
         'opening position will be reported against a different project or cost centre from the one on the list.',
         'Check the HAIS code relations in Unit4 and correct whichever source is wrong.',
         'project_codes', 'project_financials',
         'list.costc <> financials.costc (also unit, directorate, department)',
         lambda df: df['attr_mismatch'] != ''),

        ('PRJ_SPLIT_INCONSISTENT', S, 'Project List', 'Consistency', 'Low',
         'Shared cost line whose HoC / HoL split changes between years',
         f'A shared cost line should be split between the houses on a stable basis (for example 60/40 or 70/30). '
         f'A split that moves by more than {SPLIT_DRIFT_PP:.0f} percentage points between years may be a recharge '
         'error, and it changes how much of the opening position each house carries.',
         'Confirm the agreed split for the cost line and correct any years recharged on a different basis.',
         'project_codes', 'project_financials',
         f'MAX(hoc_share) - MIN(hoc_share) across years > {SPLIT_DRIFT_PP:.0f}pp',
         lambda df: df['split_range_pp'] > SPLIT_DRIFT_PP),

        # ── The opening position (one row per project and house) ─────────────
        ('PRJ_NO_BUDGET', S, 'Project Position', 'Completeness', 'Medium',
         'Project with spend this year but no budget this year',
         'A project spending in the current year must have a current year budget. Without one, remaining budget is '
         'negative from Day 1 in the new system and Budget vs Actual reporting shows an unbudgeted overspend.',
         'Load the approved current year budget against the project, or confirm the spend is coded correctly.',
         'project_units', None,
         'current_fy_actuals <> 0 AND current_fy_budget = 0',
         lambda df: df['current_fy_budget'].abs() < TOLERANCE),

        ('PRJ_OVERSPEND', S, 'Project Position', 'Consistency', 'Medium',
         f'Spend to date exceeds budget to date by more than {OVERSPEND_PCT:.0%} and £{OVERSPEND_ABS:,.0f}',
         'Spend to date should be within the budget approved to date. A material overspend carries a negative '
         'remaining budget into the new projects module and needs an approved explanation before cutover.',
         'Confirm whether additional budget was approved and not loaded, or the spend is miscoded.',
         'project_units', None,
         f'spend_to_date > budget_to_date * {1 + OVERSPEND_PCT} AND spend_to_date - budget_to_date > {OVERSPEND_ABS:.0f}',
         lambda df: (df['spend_to_date'] > df['budget_to_date'] * (1 + OVERSPEND_PCT))
                    & ((df['spend_to_date'] - df['budget_to_date']) > OVERSPEND_ABS)),

        ('PRJ_NEG_SPEND_TO_DATE', S, 'Project Position', 'Validity', 'Medium',
         'Project with negative spend to date',
         'Spend to date on a project should not be negative. A negative balance means more credits (income, '
         'recharges or reversals) than costs have been posted, and it would migrate as a credit opening position.',
         'Review the credits on the project and correct any posted to the wrong project or account.',
         'project_units', None,
         f'spend_to_date < -{TOLERANCE:.0f}',
         lambda df: df['spend_to_date'] < -TOLERANCE),

        ('PRJ_HISTORY_TRUNCATED', S, 'Project Position', 'Completeness', 'Low',
         'Project active from the start of the extract, so earlier spend may be missing',
         'Spend to date must include every year since the project started. The financials start in April 2020, so a '
         'project already spending then probably has earlier spend that is not in the opening position.',
         'Request financials before April 2020 for these projects (Ben has offered them).',
         'project_units', None,
         f'first activity within {3} months of the extract start',
         lambda df: df['truncated']),

        # ── Open commitments ─────────────────────────────────────────────────
        ('PRJ_STALE_COMMITMENT', S, 'Project Commitments', 'Consistency', 'Medium',
         f'Open commitment more than {STALE_COMMITMENT_MONTHS} months old',
         f'An open commitment should relate to a purchase order that is still expected to be invoiced. One posted '
         f'more than {STALE_COMMITMENT_MONTHS} months ago is probably a PO that was never closed, and it would '
         'migrate as a live commitment against the project.',
         'Ask the budget holder whether the PO is still needed, and close it in Unit4 if not.',
         'project_commitments', None,
         f'months between period and latest period > {STALE_COMMITMENT_MONTHS}',
         lambda df: df['age_months'] > STALE_COMMITMENT_MONTHS),

        ('PRJ_NEG_COMMITMENT', S, 'Project Commitments', 'Validity', 'Low',
         'Negative open commitment',
         'Open commitments are the amount left on purchase orders, so they should not be negative. A negative '
         'balance usually means an invoice was matched for more than the PO line, and it would reduce the '
         "project's migrated commitments.",
         'Review the PO line and correct the over-matched invoice.',
         'project_commitments', None,
         f'committed < -{TOLERANCE:.0f}',
         lambda df: df['committed'] < -TOLERANCE),

        ('PRJ_RESIDUAL_COMMITMENT', S, 'Project Commitments', 'Validity', 'Low',
         f'Open commitment under £{RESIDUAL_COMMITMENT_MAX:.0f}',
         'A very small open commitment is usually a residual left on a purchase order that is effectively finished. '
         'It would migrate as an open commitment for no reason.',
         'Close the PO line in Unit4 so the residual is released.',
         'project_commitments', None,
         f'0 < committed < {RESIDUAL_COMMITMENT_MAX:.0f}',
         lambda df: (df['committed'] > 0) & (df['committed'] < RESIDUAL_COMMITMENT_MAX)),
    ]
