"""
Migration Scope Engine: rule parameters and ruleset version.

This file is the single source of truth for every threshold and code list the
engine uses. It is tracked in git and is only ever changed on the development
laptop, then pulled on the Parliament laptop. Every change bumps
RULESET_VERSION and adds a CHANGELOG line, so each steward decision can be
traced to the exact rules in force when it was made.
"""
from pathlib import Path

RULESET_VERSION = '1.0'

CHANGELOG = [
    ('1.0', '2026-11-04', 'First ruleset for suppliers, agreed in design session with Tom Leitch.'),
]

# ── Storage ───────────────────────────────────────────────────────────────────
# Decisions, snapshots and backups are real Parliament data, so they live under
# data/ (gitignored) and never travel through git.
REPO_ROOT = Path(__file__).resolve().parent.parent
STORAGE_DIR = REPO_ROOT / 'data' / 'migration_scope'
DB_PATH = STORAGE_DIR / 'scope.db'
BACKUP_DIR = STORAGE_DIR / 'backups'
UPLOAD_ARCHIVE_DIR = STORAGE_DIR / 'uploads'
DUMMY_DIR = STORAGE_DIR / 'dummy'
# Local, per-machine settings (e.g. {"source": "dummy"} on the dev laptop).
SETTINGS_PATH = STORAGE_DIR / 'settings.json'

# ── Supplier parameters ───────────────────────────────────────────────────────
SUPPLIER_PARAMS = {
    # Population
    'in_scope_statuses': ['N', 'P'],          # N active, P parked. C closed and T terminated are never in scope.
    'clients': {'HOC': ['CA', 'CM'], 'HOL': ['LA']},
    'legacy_excluded_id_prefixes': {'HOC': ['89', '99'], 'HOL': []},   # same exclusions as the DQA suppliers tab
    'legacy_excluded_names': ['SZSINGLES'],

    # Categorisation (non-commercial records are held for a policy decision)
    'noncommercial_groups': {
        'HOC': {'EM': 'Employee', 'ME': 'Member', 'SA': 'Select Committee Advisor', 'WI': 'Witness'},
        'HOL': {'05': 'Member (Peer)', '06': 'Employee'},
    },
    'noncommercial_id_prefixes': {
        'HOC': {'1000': 'Employee (iTrent)', '74': 'Non-standard payee'},
        'HOL': {'1': 'Employee', '2': 'Employee (weekly payroll)', '3': 'Member (Peer)'},
    },
    'policy_groups': {'HOL': {'03': 'Card account'}},
    'individual_groups': {'HOC': ['TI', 'TO'], 'HOL': []},
    'group_id_check_houses': ['HOL'],        # houses where supplier group and ID range must agree

    # Activity
    'dormancy_months': 18,                   # no activity in this many months and nothing open = Close
    'activity_voucher_types': [              # invoices and credit notes count as activity; payments, journals, reversals don't
        'CP', 'ID', 'IF', 'II', 'IU', 'OP', 'PI', 'RD', 'RI', 'SI', 'SR',
        'CN', 'IC', 'IN', 'RC',
    ],
    'open_po_statuses': ['O', 'N', 'A'],     # HoC only; HoL doesn't use POs

    # Open items
    'stuck_item_months': 2,                  # open item older than this (by transaction date) needs review

    # Duplicates
    'duplicate_keys': ['vat', 'company_no', 'bank', 'name_postcode'],
    'possible_duplicate_similarity': 90,     # 0-100 name similarity for "possible duplicate"
    'monitor_months': 6,                     # non-preferred duplicate with no activity in this many months = Close
    'cross_house_as_duplicate': False,       # target design not decided: cross-House matches are tagged, not grouped
    'placeholder_bank_accounts': ['00000000', '0', '11111111', '99999999'],

    # Data quality tests that make a kept supplier "Fix" (all others are advisory)
    'blocking_tests': [
        'SUP_TERMS_MISSING', 'SUP_PAY_METHOD_MISSING', 'SUP_CURRENCY_MISSING',
        'SUP_SORT_IBAN_MISSING', 'SUP_SORT_FORMAT', 'SUP_BANK_FORMAT',
        'SUP_BACS_NO_BANK', 'SUP_INT_NO_IBAN',
        'SUP_VAT_MISSING', 'SUP_VAT_FORMAT', 'SUP_COMP_REG_FORMAT',
        'SUP_ADDR_MISSING', 'SUP_ZIP_MISSING',
        'MS-DQ-NAME', 'MS-DQ-LTD-COMPNO',
    ],
    # SUP_BANK_MISSING is advisory only: it flags cheque and IBAN payers too.
    # Existing DQA tests not applied here: duplicates are handled by the engine's
    # own matching, and dormancy by the classification rules.
    'ignored_tests': [
        'SUP_NAME_DUP', 'SUP_NAME_DUP_ANY', 'SUP_VAT_DUP', 'SUP_BANK_SORT_DUP', 'SUP_BANK_DUP',
        'SUP_CLIENT_APAR_DUP', 'SUP_DORMANT',
    ],
}

# Parameters shown in the What-if panel (key, label, min, max, step).
WHATIF_PARAMS = [
    ('dormancy_months', 'Dormant after (months)', 6, 36, 1),
    ('monitor_months', 'Non-preferred duplicate closes after (months)', 1, 18, 1),
    ('stuck_item_months', 'Open item needs review after (months)', 1, 24, 1),
    ('possible_duplicate_similarity', 'Possible duplicate name similarity (%)', 70, 99, 1),
]
