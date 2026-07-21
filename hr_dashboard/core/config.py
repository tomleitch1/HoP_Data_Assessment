"""
Royal Mail HR & Payroll Data Quality Assessment — Configuration
==================================================================
One-off bid-demo build (Veran Performance x Royal Mail). Structured the same
way as the Parliament finance dashboard's config.py — a single source of
truth for scope identifiers, thresholds, and status codes — but trimmed to
this demo's two data objects (Employee Master, Payroll Transactions) and a
single combined dataset (no HOC/HOL-style house split).

All data here is entirely synthetic. Nothing in this file reflects any real
Royal Mail Group system, schema, or process.
"""

import os
from enum import IntEnum


class Scope(IntEnum):
    EMPLOYEE = 1
    PAYROLL  = 2


class EmployeeConfig:
    ACTIVE_STATUSES = ['Active']
    LEAVER_STATUSES = ['Leaver']
    MIN_WORKING_AGE = 16
    MAX_WORKING_AGE = 75


class PayrollConfig:
    CALC_TOLERANCE_GBP = 1.00   # gross - deductions vs net, rounding tolerance
    STALE_PENDING_DAYS = 7


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(_PROJECT_ROOT, 'data', 'hr')

# Single-entity dataset — every dq_results row carries this constant so the
# shared scorecard/grid components (built generic over "house") still work
# unchanged with exactly one bucket.
ENTITY_LABEL = 'Royal Mail Group'

SCOPE_CONFIG = {
    'employee': {
        'label':     'Employee Master',
        'tab_value': 'employee',
        'scope_ids': [Scope.EMPLOYEE],
        'tables':    ['employee_master'],
    },
    'payroll': {
        'label':     'Payroll',
        'tab_value': 'payroll',
        'scope_ids': [Scope.PAYROLL],
        'tables':    ['payroll_transactions'],
    },
}

SCOPE_LABELS = {
    Scope.EMPLOYEE: 'Employee Master',
    Scope.PAYROLL:  'Payroll Transactions',
}

# Per-severity RAG thresholds (error rate %). Green = below first value, Amber = below second, Red = above.
# Same methodology as the Parliament finance dashboard, for a consistent story about the approach.
RAG_THRESHOLDS = {
    'Critical': (1,  5),
    'High':     (3,  10),
    'Medium':   (5,  15),
    'Low':      (10, 25),
}

SEV_ORDER  = ['Critical', 'High', 'Medium', 'Low']
SEV_WEIGHT = {'Critical': 1, 'High': 2, 'Medium': 3, 'Low': 4}
RAG_ORDER  = ['Red', 'Amber', 'Green']
