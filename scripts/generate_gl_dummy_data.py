import pandas as pd
import random
from datetime import date, timedelta

random.seed(42)

# ---------------------------------------------------------------------------
# EXCEL SERIAL DATE HELPERS
# Excel counts days since 1899-12-30 (accounting for the 1900 leap-year bug)
# Data extracted from SSMS via Excel arrives with date fields as these serials
# ---------------------------------------------------------------------------
EXCEL_EPOCH = date(1899, 12, 30)

def to_excel(d: date) -> int:
    return (d - EXCEL_EPOCH).days

def excel_rand(start: date, end: date) -> int:
    days = (end - start).days
    return to_excel(start + timedelta(days=random.randint(0, days)))

TODAY = date.today()

# Pre-computed serials for common sentinel dates
PERIOD_FROM_NORMAL = to_excel(date(2000, 1, 1))   # 36526 — account created ~Y2K
PERIOD_TO_NORMAL   = to_excel(date(2049, 12, 31))  # 54788 — far future, within engine parse range (max 55000)
PERIOD_TO_EXPIRED  = to_excel(date(2010, 6, 1))    # ~40330 — expired account
LAST_UPDATE_STALE  = to_excel(date(2018, 1, 1))    # ~43101 — > 3 years ago

# ---------------------------------------------------------------------------
# UNIT4 / AGRESSO CONSTANTS (confirmed from real Parliament data)
# ---------------------------------------------------------------------------
HOC_CLIENTS = ['CA', 'CM']
HOL_CLIENT  = 'LA'

HOC_GRPS    = [str(i) for i in range(1, 10)]   # '1' .. '9'
HOL_GRPS    = ['A', 'B', 'C', 'D', 'E', 'F']  # 6 letters — exact meaning TBD

# bflag is a bitmask — powers of 2; 0 = no special flag. Specific bit meanings TBD.
BFLAG_NONE = 0
BFLAG_VALUES = [0, 8, 16, 32, 64, 128]

def last_update_recent() -> int:
    return excel_rand(date(2021, 1, 1), TODAY)

def make_period_from() -> int:
    return excel_rand(date(1995, 1, 1), date(2010, 1, 1))

def client_to_house(client: str) -> str:
    return 'HOL' if client == HOL_CLIENT else 'HOC'


# ===========================================================================
# CHART OF ACCOUNTS — aglaccounts
# HOC: numeric account codes (1000+), client CA or CM, grp 1–9, rule 1–39
# HOL: letter-prefixed codes (A1000, B2000...), client LA, grp A–F, rule 1–89
# Both: bflag in {0,8,16,32,64,128}, period_from/to & last_update as Excel serials
# ===========================================================================

def generate_chart_of_accounts() -> pd.DataFrame:
    rows = []

    # HOC account structure — each account code appears once for CA and once for CM
    hoc_configs = [
        # (grp, start, count, res_bal, acc_type, desc_prefix, bflag)
        ('1', 1000, 12, 'B', 'GL', 'Cash and Bank',         BFLAG_NONE),
        ('2', 1200,  8, 'B', 'AR', 'Receivables Control',   32),
        ('3', 2000,  8, 'B', 'GL', 'Accounts Payable',      BFLAG_NONE),
        ('3', 2100,  6, 'B', 'GL', 'Accruals',              BFLAG_NONE),
        ('4', 3000,  8, 'B', 'GL', 'Capital',               BFLAG_NONE),
        ('4', 3500,  6, 'B', 'GL', 'Reserves',              BFLAG_NONE),
        ('5', 4000, 18, 'R', 'GL', 'Staff Costs',           BFLAG_NONE),
        ('6', 5000, 12, 'R', 'GL', 'Premises',              BFLAG_NONE),
        ('7', 6000, 10, 'R', 'GL', 'IT and Technology',     BFLAG_NONE),
        ('8', 7000, 10, 'R', 'GL', 'Professional Services', BFLAG_NONE),
        ('9', 9000, 12, 'R', 'AR', 'Income',                BFLAG_NONE),
    ]

    for hoc_client in HOC_CLIENTS:
        for (grp, start, count, res_bal, acc_type, desc_prefix, bflag) in hoc_configs:
            for i in range(count):
                rows.append({
                    '_house': 'HOC',
                    'client':       hoc_client,
                    'account':      str(start + i),
                    'description':  f"{desc_prefix} {i+1:02d}",
                    'account_grp':  grp,
                    'account_type': acc_type,
                    'status':       'N' if random.random() > 0.04 else 'C',
                    'res_bal':      res_bal,
                    'bflag':        bflag,
                    'account_rule': random.randint(1, 39),
                    'period_from':  make_period_from(),
                    'period_to':    PERIOD_TO_NORMAL,
                    'last_update':  last_update_recent(),
                    'head_account': None,
                })

    # HOL account structure — letter-prefixed codes, LA client only
    hol_configs = [
        # (grp, prefix, start_num, count, res_bal, acc_type, desc_prefix)
        ('A', 'A', 1000, 25, 'B', 'GL', 'Balance Sheet Assets'),
        ('B', 'B', 2000, 20, 'B', 'GL', 'Liabilities'),
        ('C', 'C', 3000, 15, 'B', 'GL', 'Capital and Reserves'),
        ('D', 'D', 4000, 35, 'R', 'GL', 'Staff Costs'),
        ('E', 'E', 5000, 30, 'R', 'GL', 'Premises and Overheads'),
        ('F', 'F', 9000, 25, 'R', 'AR', 'Income'),
    ]

    for (grp, prefix, start_num, count, res_bal, acc_type, desc_prefix) in hol_configs:
        for i in range(count):
            rows.append({
                '_house': 'HOL',
                'client':       HOL_CLIENT,
                'account':      f"{prefix}{start_num + i}",
                'description':  f"{desc_prefix} {i+1:02d}",
                'account_grp':  grp,
                'account_type': acc_type,
                'status':       'N' if random.random() > 0.04 else 'C',
                'res_bal':      res_bal,
                'bflag':        BFLAG_NONE,
                'account_rule': random.randint(1, 89),
                'period_from':  make_period_from(),
                'period_to':    PERIOD_TO_NORMAL,
                'last_update':  last_update_recent(),
                'head_account': None,
            })

    # --- Edge cases (HOC, client CA, accounts in 8001–8013 range) ---
    # Each edge case maps to a specific planned DQ check
    edge_cases = [
        # GL_ACC_DESC_MISSING: active account, no description
        {'_house': 'HOC', 'client': 'CA', 'account': '8001', 'description': None,
         'account_grp': '5', 'account_type': 'GL', 'status': 'N', 'res_bal': 'R',
         'bflag': 0, 'account_rule': 5, 'period_from': PERIOD_FROM_NORMAL,
         'period_to': PERIOD_TO_NORMAL, 'last_update': last_update_recent(), 'head_account': None},

        # GL_ACC_GRP_MISSING: active account, no account_grp
        {'_house': 'HOC', 'client': 'CA', 'account': '8002', 'description': 'EC Missing Group',
         'account_grp': None, 'account_type': 'GL', 'status': 'N', 'res_bal': 'R',
         'bflag': 0, 'account_rule': 5, 'period_from': PERIOD_FROM_NORMAL,
         'period_to': PERIOD_TO_NORMAL, 'last_update': last_update_recent(), 'head_account': None},

        # GL_ACC_RESBAL_MISSING: active account, no res_bal
        {'_house': 'HOC', 'client': 'CA', 'account': '8003', 'description': 'EC Missing ResBal',
         'account_grp': '5', 'account_type': 'GL', 'status': 'N', 'res_bal': None,
         'bflag': 0, 'account_rule': 5, 'period_from': PERIOD_FROM_NORMAL,
         'period_to': PERIOD_TO_NORMAL, 'last_update': last_update_recent(), 'head_account': None},

        # GL_ACC_RULE_MISSING: active account, no account_rule
        {'_house': 'HOC', 'client': 'CA', 'account': '8004', 'description': 'EC Missing Rule',
         'account_grp': '5', 'account_type': 'GL', 'status': 'N', 'res_bal': 'R',
         'bflag': 0, 'account_rule': None, 'period_from': PERIOD_FROM_NORMAL,
         'period_to': PERIOD_TO_NORMAL, 'last_update': last_update_recent(), 'head_account': None},

        # GL_ACC_PERIOD_MISSING: active account, no period_from
        {'_house': 'HOC', 'client': 'CA', 'account': '8005', 'description': 'EC Missing Period From',
         'account_grp': '5', 'account_type': 'GL', 'status': 'N', 'res_bal': 'R',
         'bflag': 0, 'account_rule': 5, 'period_from': None,
         'period_to': PERIOD_TO_NORMAL, 'last_update': last_update_recent(), 'head_account': None},

        # GL_ACC_RESBAL_INVALID: res_bal = 'X' (not R or B)
        {'_house': 'HOC', 'client': 'CA', 'account': '8006', 'description': 'EC Invalid ResBal',
         'account_grp': '5', 'account_type': 'GL', 'status': 'N', 'res_bal': 'X',
         'bflag': 0, 'account_rule': 5, 'period_from': PERIOD_FROM_NORMAL,
         'period_to': PERIOD_TO_NORMAL, 'last_update': last_update_recent(), 'head_account': None},

        # GL_ACC_TYPE_INVALID: account_type not in GL/AP/AR
        {'_house': 'HOC', 'client': 'CA', 'account': '8007', 'description': 'EC Invalid Type',
         'account_grp': '5', 'account_type': 'XX', 'status': 'N', 'res_bal': 'R',
         'bflag': 0, 'account_rule': 5, 'period_from': PERIOD_FROM_NORMAL,
         'period_to': PERIOD_TO_NORMAL, 'last_update': last_update_recent(), 'head_account': None},

        # GL_ACC_PERIOD_INV: period_from > period_to (swapped)
        {'_house': 'HOC', 'client': 'CA', 'account': '8008', 'description': 'EC Invalid Period Range',
         'account_grp': '5', 'account_type': 'GL', 'status': 'N', 'res_bal': 'R',
         'bflag': 0, 'account_rule': 5, 'period_from': PERIOD_TO_NORMAL,
         'period_to': PERIOD_FROM_NORMAL, 'last_update': last_update_recent(), 'head_account': None},

        # GL_ACC_STALE_N: period_to in the past but status still N
        {'_house': 'HOC', 'client': 'CA', 'account': '8009', 'description': 'EC Expired Still Active',
         'account_grp': '5', 'account_type': 'GL', 'status': 'N', 'res_bal': 'R',
         'bflag': 0, 'account_rule': 5, 'period_from': PERIOD_FROM_NORMAL,
         'period_to': PERIOD_TO_EXPIRED, 'last_update': last_update_recent(), 'head_account': None},

        # GL_ACC_BFLAG_CON: reconciliation-type bflag but account_type = GL (not AR/AP)
        # bflag = 32 used as placeholder — update once reconciliation bit is confirmed
        {'_house': 'HOC', 'client': 'CA', 'account': '8010', 'description': 'EC Recon Flag Not Control',
         'account_grp': '2', 'account_type': 'GL', 'status': 'N', 'res_bal': 'B',
         'bflag': 32, 'account_rule': 5, 'period_from': PERIOD_FROM_NORMAL,
         'period_to': PERIOD_TO_NORMAL, 'last_update': last_update_recent(), 'head_account': None},

        # GL_ACC_DUP_CODE: same (client, account) appears twice — a true duplicate
        {'_house': 'HOC', 'client': 'CA', 'account': '8011', 'description': 'EC Dup Account A',
         'account_grp': '5', 'account_type': 'GL', 'status': 'N', 'res_bal': 'R',
         'bflag': 0, 'account_rule': 5, 'period_from': PERIOD_FROM_NORMAL,
         'period_to': PERIOD_TO_NORMAL, 'last_update': last_update_recent(), 'head_account': None},
        {'_house': 'HOC', 'client': 'CA', 'account': '8011', 'description': 'EC Dup Account B',
         'account_grp': '5', 'account_type': 'GL', 'status': 'N', 'res_bal': 'R',
         'bflag': 0, 'account_rule': 5, 'period_from': PERIOD_FROM_NORMAL,
         'period_to': PERIOD_TO_NORMAL, 'last_update': last_update_recent(), 'head_account': None},

        # GL_ACC_STALE_MOD: last_update > 3 years ago
        {'_house': 'HOC', 'client': 'CA', 'account': '8012', 'description': 'EC Stale Account',
         'account_grp': '5', 'account_type': 'GL', 'status': 'N', 'res_bal': 'R',
         'bflag': 0, 'account_rule': 5, 'period_from': PERIOD_FROM_NORMAL,
         'period_to': PERIOD_TO_NORMAL, 'last_update': LAST_UPDATE_STALE, 'head_account': None},

        # Closed account — for backward-compat checks (will have transactions against it)
        {'_house': 'HOC', 'client': 'CA', 'account': '8013', 'description': 'EC Closed With Transactions',
         'account_grp': '1', 'account_type': 'GL', 'status': 'C', 'res_bal': 'B',
         'bflag': 0, 'account_rule': 5, 'period_from': PERIOD_FROM_NORMAL,
         'period_to': PERIOD_TO_NORMAL, 'last_update': LAST_UPDATE_STALE, 'head_account': None},
    ]

    return pd.DataFrame(rows + edge_cases)


# ===========================================================================
# DIMENSION VALUES — agldimvalue (joined with agldimension for dim_position)
# Confirmed schema from real Parliament data:
#   period_from / period_to: YYYYMM integers (e.g. 201202 = period 2 of 2012)
#                            NOT Excel serial dates
#   last_update: Excel serial integer (e.g. 46090)
#   wf_state:    not used in Parliament's Agresso — always blank
#   rel_value:   hierarchy parent code within the same (attribute_id, client),
#                or blank for root nodes
#   dim_description: attribute type label from agldimension (e.g. 'Cost Centre')
#   All rows active (status = 'N') — SQL extract filters to active only
# ===========================================================================

# YYYYMM integer sentinels for agldimvalue period fields
DIM_PERIOD_FROM = 200101   # Period 1 of 2001 — typical start
DIM_PERIOD_TO   = 209912   # Period 12 of 2099 — open-ended sentinel
DIM_PERIOD_INV  = 209901   # Used as period_from in inverted edge case (> DIM_PERIOD_TO)

# HOC GL attributes: (attribute_id, dim_description, dim_position, n_root, n_child_per_root)
_HOC_DIM_ATTRS = [
    ('COSTC', 'Cost Centre',     '1', 8,  6),   # hierarchical — roots then children
    ('SUBJ',  'Subjective Code', '2', 40, 0),   # flat
    ('ACTV',  'Activity',        '3', 20, 0),   # flat
    ('PROJ',  'Project Code',    '4', 10, 8),   # hierarchical
    ('CTPT',  'Counterpart',     '5', 12, 0),   # flat
    ('FUND',  'Fund',            '6', 6,  0),   # flat
    ('PROG',  'Programme',       '7', 10, 0),   # flat
]

# HOL GL attributes (independent configuration, LA client)
_HOL_DIM_ATTRS = [
    ('LOSTC', 'Cost Centre',     '1', 6,  5),
    ('LSUBJ', 'Subjective Code', '2', 30, 0),
    ('LACTV', 'Activity',        '3', 15, 0),
    ('LPROJ', 'Project Code',    '4', 8,  6),
    ('LCTPT', 'Counterpart',     '5', 8,  0),
    ('LFUND', 'Fund',            '6', 4,  0),
    ('LPROG', 'Programme',       '7', 8,  0),
]


def _dim_rows(client, house, attr_id, dim_desc, dim_pos, n_root, n_child_per_root):
    """Generate flat + hierarchical dimension value rows for one attribute/client."""
    rows = []
    pfx = attr_id[:2].upper()

    root_codes = [f"{pfx}R{i:03d}" for i in range(1, n_root + 1)]
    for code in root_codes:
        rows.append({
            '_house': house, 'client': client,
            'attribute_id': attr_id, 'dim_position': dim_pos,
            'dim_description': dim_desc,
            'dim_value': code, 'description': f"{dim_desc} {code}",
            'status': 'N',
            'period_from': DIM_PERIOD_FROM, 'period_to': DIM_PERIOD_TO,
            'rel_value': None,
            'last_update': last_update_recent(), 'wf_state': '',
        })

    if n_child_per_root:
        child_num = 1
        for parent in root_codes:
            for _ in range(n_child_per_root):
                code = f"{pfx}C{child_num:04d}"
                child_num += 1
                rows.append({
                    '_house': house, 'client': client,
                    'attribute_id': attr_id, 'dim_position': dim_pos,
                    'dim_description': dim_desc,
                    'dim_value': code, 'description': f"{dim_desc} {code}",
                    'status': 'N',
                    'period_from': DIM_PERIOD_FROM, 'period_to': DIM_PERIOD_TO,
                    'rel_value': parent,
                    'last_update': last_update_recent(), 'wf_state': '',
                })
    return rows


def generate_dimension_values() -> pd.DataFrame:
    rows = []

    for client in HOC_CLIENTS:
        for (attr_id, dim_desc, dim_pos, n_root, n_child) in _HOC_DIM_ATTRS:
            rows.extend(_dim_rows(client, 'HOC', attr_id, dim_desc, dim_pos, n_root, n_child))

    for (attr_id, dim_desc, dim_pos, n_root, n_child) in _HOL_DIM_ATTRS:
        rows.extend(_dim_rows(HOL_CLIENT, 'HOL', attr_id, dim_desc, dim_pos, n_root, n_child))

    # -----------------------------------------------------------------------
    # Edge cases — each triggers one specific DQ check
    # All use COSTC / HOC / CA so they appear in GL_DIM_* check results
    # -----------------------------------------------------------------------
    _ec = lambda code, desc, pf, pt, rel, house='HOC', client='CA', attr='COSTC': {
        '_house': house, 'client': client,
        'attribute_id': attr, 'dim_position': '1',
        'dim_description': 'Cost Centre',
        'dim_value': code, 'description': desc,
        'status': 'N',
        'period_from': pf, 'period_to': pt,
        'rel_value': rel,
        'last_update': last_update_recent(), 'wf_state': '',
    }

    edge_cases = [
        # GL_DIM_DESC_MISSING: active value, no description
        _ec('EC_D001', None, DIM_PERIOD_FROM, DIM_PERIOD_TO, None),

        # GL_DIM_PERIOD_MISSING: active value, no period_from
        _ec('EC_D002', 'EC Missing Period From', None, DIM_PERIOD_TO, None),

        # GL_DIM_PERIOD_INV: period_from (209901) > period_to (209912) — inverted
        _ec('EC_D003', 'EC Inverted Period', DIM_PERIOD_INV, DIM_PERIOD_FROM, None),

        # GL_DIM_ORPHAN_REL: rel_value points to a code that does not exist
        _ec('EC_D004', 'EC Orphaned Parent', DIM_PERIOD_FROM, DIM_PERIOD_TO, 'GHOST_PARENT'),

        # GL_DIM_DUP: same dim_value as EC_D005b — both will be flagged
        _ec('EC_D005', 'EC Duplicate A', DIM_PERIOD_FROM, DIM_PERIOD_TO, None),
        _ec('EC_D005', 'EC Duplicate B', DIM_PERIOD_FROM, DIM_PERIOD_TO, None),
    ]

    return pd.DataFrame(rows + edge_cases)


# ===========================================================================
# DIMENSION CONFIG — agldimension joined to agldimvalue (summary/reference only)
# Mirrors the output of gl_dimension_config_HOC/HOL_run.sql.
# Columns: client, attribute_id, description, dim_position, total_values, active, closed
#
# dim_position key:
#   '1'–'7' → GL journal line dimensions (in scope for migration)
#   letter   → header/cross-module dimensions (review)
#   'X'      → not mapped to GL lines (likely out of scope)
#
# Attribute_ids below are FICTIONAL placeholders — replace once real data is
# confirmed from the Parliament laptop. The structure (positions, rough counts)
# is realistic for a typical Agresso installation.
# ===========================================================================

# HOC attributes — same definitions for CA and CM
_HOC_ATTRS = [
    # (attribute_id, description,          dim_position, total, active, closed)
    # --- GL journal line dimensions (positions 1–7) ---
    ('COSTC', 'Cost Centre',               '1',  350,  185, 165),
    ('SUBJ',  'Subjective Code',           '2',  820,  510, 310),
    ('ACTV',  'Activity',                  '3',   75,   55,  20),
    ('PROJ',  'Project Code',              '4', 3200,  980, 2220),
    ('CTPT',  'Counterpart',               '5',   45,   32,  13),
    ('FUND',  'Fund',                      '6',   18,   12,   6),
    ('PROG',  'Programme',                 '7',   28,   20,   8),
    # --- Letter-position dimensions (not GL journal lines) ---
    ('HRCC',  'HR Cost Centre',            'A',  220,  140,  80),
    ('BUNT',  'Budget Unit',               'B',   65,   40,  25),
    # --- X-position dimensions (not mapped to GL transaction lines) ---
    ('RGRP',  'Reporting Group',           'X',   45,   30,  15),
    ('SCAT',  'Spend Category',            'X',  130,   88,  42),
    ('VOTE',  'Vote Type',                 'X',   12,    8,   4),
    ('DEPT',  'Department',                'X',   95,   60,  35),
    ('TCAT',  'Transaction Category',      'X',   40,   28,  12),
]

# HOL attributes — LA client; similar structure but independent configuration
_HOL_ATTRS = [
    # (attribute_id, description,          dim_position, total, active, closed)
    # --- GL journal line dimensions (positions 1–7) ---
    ('LOSTC', 'Cost Centre',               '1',  180,  110,  70),
    ('LSUBJ', 'Subjective Code',           '2',  640,  420, 220),
    ('LACTV', 'Activity',                  '3',   55,   45,  10),
    ('LPROJ', 'Project Code',              '4', 1800,  620, 1180),
    ('LCTPT', 'Counterpart',               '5',   30,   22,   8),
    ('LFUND', 'Fund',                      '6',   10,    8,   2),
    ('LPROG', 'Programme',                 '7',   20,   15,   5),
    # --- Letter-position dimensions ---
    ('LHRCC', 'HR Cost Centre',            'A',  160,  100,  60),
    # --- X-position dimensions ---
    ('LRGRP', 'Reporting Group',           'X',   35,   24,  11),
    ('LSCAT', 'Spend Category',            'X',   95,   65,  30),
    ('LDEPT', 'Department',                'X',   70,   48,  22),
]


def generate_dimension_config() -> pd.DataFrame:
    """
    Generates the gl_dimension_config summary file — matches the output of
    gl_dimension_config_HOC/HOL_run.sql. One row per (client, attribute_id).
    """
    rows = []

    # HOC: CA and CM share the same attribute definitions with near-identical counts
    for attr_id, desc, dim_pos, total, active, closed in _HOC_ATTRS:
        for client in HOC_CLIENTS:
            rows.append({
                'client':       client,
                'attribute_id': attr_id,
                'description':  desc,
                'dim_position': dim_pos,
                'total_values': total,
                'active':       active,
                'closed':       closed,
            })

    # HOL: LA only
    for attr_id, desc, dim_pos, total, active, closed in _HOL_ATTRS:
        rows.append({
            'client':       HOL_CLIENT,
            'attribute_id': attr_id,
            'description':  desc,
            'dim_position': dim_pos,
            'total_values': total,
            'active':       active,
            'closed':       closed,
        })

    return pd.DataFrame(rows)


# ===========================================================================
# OPENING BALANCES — aglperiodic (frame key: aglyearend for backwards compat)
# Confirmed from real Parliament data (May 2026):
#   - period: YYYYPP integer (202601–202699)
#   - amount: signed — positive = debit, negative = credit; dc_flag always 0
#   - currency: always GBP; cur_amount always blank
#   - dim_1 only populated; dim_2–dim_7 always blank
#   - trans_date: stored as 1 in SSMS/Excel (placeholder, not a real date)
#   - status: mostly blank; occasional D, N, T, X on a small subset
#   - apar_id: blank
# ===========================================================================

FISCAL_PERIODS = [202601, 202604, 202607, 202610, 202612]

def random_amount(min_val=100, max_val=500_000):
    sign = random.choice([-1, -1, 1, 1, 1])   # ~40% credit (negative), ~60% debit
    return round(random.uniform(min_val, max_val) * sign, 2)

_BALANCE_STATUSES = [''] * 10 + ['D', 'N', 'T', 'X']   # mostly blank

def generate_opening_balances(df_accounts: pd.DataFrame, df_dims: pd.DataFrame = None) -> pd.DataFrame:
    active = df_accounts[
        (df_accounts['status'] == 'N') &
        (~df_accounts['account'].astype(str).str.startswith('8'))  # exclude edge cases
    ][['_house', 'client', 'account', 'res_bal', 'account_type']].values.tolist()

    # Use actual leaf dim codes from agldimvalue position 1 so GL_BAL_ORPHAN_DIM has valid references.
    # Fall back to placeholder codes only when df_dims is not provided.
    if df_dims is not None:
        pos1 = df_dims[df_dims['dim_position'] == '1'][['_house', 'client', 'dim_value']].drop_duplicates()
    else:
        pos1 = None

    rows = []
    for i in range(200):
        house, client, account, res_bal, acc_type = random.choice(active)
        if pos1 is not None:
            valid_codes = pos1[pos1['client'] == client]['dim_value'].tolist()
            dim_1_val = random.choice(valid_codes) if valid_codes else None
        else:
            dim_1_val = f"CC{random.randint(100, 129):03d}"
        rows.append({
            '_house':       house,
            'client':       client,
            'account':      account,
            'period':       random.choice(FISCAL_PERIODS),
            'dim_1':        dim_1_val,
            'dim_2': None, 'dim_3': None, 'dim_4': None,
            'dim_5': None, 'dim_6': None, 'dim_7': None,
            'amount':       random_amount(),
            'cur_amount':   None,
            'currency':     'GBP',
            'dc_flag':      0,
            'voucher_type': random.choice(['JO', 'AC', 'PI', 'PY', 'YE', 'JL']),
            'voucher_no':   f"OB{i:04d}",
            'trans_date':   1,          # confirmed placeholder value in real data
            'tax_code':     None,
            'apar_id':      None,
            'apar_type':    None,
            'status':       random.choice(_BALANCE_STATUSES),
            'description':  f"Balance posting {i+1:03d}",
        })

    # Edge cases
    _ec = lambda account, amount, voucher, desc, house='HOC', client='CA': {
        '_house': house, 'client': client, 'account': account,
        'period': 202612, 'dim_1': 'CC100',
        'dim_2': None, 'dim_3': None, 'dim_4': None, 'dim_5': None, 'dim_6': None, 'dim_7': None,
        'amount': amount, 'cur_amount': None, 'currency': 'GBP', 'dc_flag': 0,
        'voucher_type': 'JO', 'voucher_no': voucher, 'trans_date': 1,
        'tax_code': None, 'apar_id': None, 'apar_type': None, 'status': '', 'description': desc,
    }

    edge_cases = [
        # GL_BAL_AMT_MISSING: balance record with no amount
        _ec('4000', None, 'OB9001', 'EC Missing Amount'),

        # GL_BAL_ORPHAN_ACC: account 9999 does not exist in the CoA (range is 9000–9011)
        _ec('9999', 15000.00, 'OB9002', 'EC Ghost Account'),

        # GL_BAL_PL_NONZERO: two positive postings to a P&L account — net is clearly non-zero
        _ec('4000', 25000.00, 'OB9003', 'EC PL Nonzero A'),
        _ec('4000', 18500.00, 'OB9004', 'EC PL Nonzero B'),
    ]

    return pd.DataFrame(rows + edge_cases)


# ===========================================================================
# GENERATE AND SAVE
# ===========================================================================

import os
os.makedirs('data/gl', exist_ok=True)

def generate_transact_dimensions(df_dims: pd.DataFrame) -> pd.DataFrame:
    """
    Generates gl_transact_dimensions — distinct (client, dim_position, dim_value)
    combinations posted to in the current fiscal year.

    Format matches the gl_transact_dimensions_HOC/HOL_run.sql output: unpivoted,
    one row per distinct (client, dim_position, dim_value) used on a GL posting.

    Mostly samples leaf nodes (should pass GL_DIM_POST_SUMMARY) with a handful of
    summary/root nodes as edge cases (should trigger GL_DIM_POST_SUMMARY).
    """
    rows = []
    # Build parent set: (client, dim_position, dim_value) that appear as rel_value
    # of another node — these are summary/parent nodes.
    has_rel = df_dims[df_dims['rel_value'].notna() & (df_dims['rel_value'].astype(str).str.strip() != '')]
    summary_keys = set(
        zip(has_rel['client'], has_rel['dim_position'], has_rel['rel_value'].astype(str))
    )

    for house in ['HOC', 'HOL']:
        h_dims = df_dims[df_dims['_house'] == house]
        for (client, dim_pos), grp in h_dims.groupby(['client', 'dim_position']):
            # Leaf nodes: not in the parent/summary set
            leaf = grp[~grp.apply(
                lambda r: (r['client'], r['dim_position'], str(r['dim_value'])) in summary_keys,
                axis=1
            )]
            # Sample up to 12 leaf nodes as "posted to" (normal passing records)
            for _, r in leaf.sample(min(12, len(leaf)), random_state=42).iterrows():
                rows.append({'_house': house, 'client': client,
                             'dim_position': dim_pos, 'dim_value': r['dim_value']})

            # Edge case: pick one summary/root node and include it as a posting
            # to trigger GL_DIM_POST_SUMMARY for dim_position '1' (COSTC/LOSTC only)
            if dim_pos == '1':
                summary = grp[grp.apply(
                    lambda r: (r['client'], r['dim_position'], str(r['dim_value'])) in summary_keys,
                    axis=1
                )]
                if not summary.empty:
                    ec_row = summary.iloc[0]
                    rows.append({'_house': house, 'client': client,
                                 'dim_position': dim_pos, 'dim_value': ec_row['dim_value']})

    df = pd.DataFrame(rows).drop_duplicates(subset=['_house', 'client', 'dim_position', 'dim_value'])
    return df


df_coa    = generate_chart_of_accounts()
df_dims   = generate_dimension_values()
df_bal    = generate_opening_balances(df_coa, df_dims)
df_dimcfg = generate_dimension_config()
df_tdim   = generate_transact_dimensions(df_dims)

for house in ['HOC', 'HOL']:
    coa_out  = df_coa [df_coa ['_house'] == house].drop(columns=['_house'])
    dims_out = df_dims[df_dims['_house'] == house].drop(columns=['_house'])
    bal_out  = df_bal [df_bal ['_house'] == house].drop(columns=['_house'])
    tdim_out = df_tdim[df_tdim['_house'] == house].drop(columns=['_house'])

    coa_out .to_csv(f'data/gl/gl_chart_of_accounts_{house}.csv',  index=False)
    dims_out.to_csv(f'data/gl/gl_dimension_values_{house}.csv',   index=False)
    bal_out .to_csv(f'data/gl/gl_opening_balances_{house}.csv',   index=False)
    tdim_out.to_csv(f'data/gl/gl_transact_dimensions_{house}.csv', index=False)

    # Dimension config: summary matching gl_dimension_config_*_run.sql output
    clients = ['CA', 'CM'] if house == 'HOC' else ['LA']
    cfg_out = df_dimcfg[df_dimcfg['client'].isin(clients)]
    cfg_out.to_csv(f'data/gl/gl_dimension_config_{house}.csv', index=False)

print(f"Dimension config:   {len(df_dimcfg)} rows  (data/gl/gl_dimension_config_HOC/HOL.csv)")
print(f"  HOC (CA+CM): {len(df_dimcfg[df_dimcfg['client'].isin(['CA','CM'])])} rows  "
      f"| dim 1-7: {len(df_dimcfg[(df_dimcfg['client']=='CA') & df_dimcfg['dim_position'].isin(['1','2','3','4','5','6','7'])])} attributes  "
      f"| letter: {len(df_dimcfg[(df_dimcfg['client']=='CA') & ~df_dimcfg['dim_position'].isin(['1','2','3','4','5','6','7','X'])])}  "
      f"| X: {len(df_dimcfg[(df_dimcfg['client']=='CA') & (df_dimcfg['dim_position']=='X')])}")
print(f"  HOL (LA):    {len(df_dimcfg[df_dimcfg['client']=='LA'])} rows  "
      f"| dim 1-7: {len(df_dimcfg[(df_dimcfg['client']=='LA') & df_dimcfg['dim_position'].isin(['1','2','3','4','5','6','7'])])} attributes  "
      f"| letter: {len(df_dimcfg[(df_dimcfg['client']=='LA') & ~df_dimcfg['dim_position'].isin(['1','2','3','4','5','6','7','X'])])}  "
      f"| X: {len(df_dimcfg[(df_dimcfg['client']=='LA') & (df_dimcfg['dim_position']=='X')])}")
print(f"Chart of accounts:  {len(df_coa)} rows total")
print(f"  HOC ({', '.join(HOC_CLIENTS)}): {len(df_coa[df_coa['_house']=='HOC'])} rows")
print(f"  HOL ({HOL_CLIENT}):         {len(df_coa[df_coa['_house']=='HOL'])} rows")
print(f"Dimension values:   {len(df_dims)} rows total")
print(f"Opening balances:   {len(df_bal)} rows total")

print("\n--- HOC account_type split (active only) ---")
hoc_active = df_coa[(df_coa['_house'] == 'HOC') & (df_coa['status'] == 'N')]
print(hoc_active['account_type'].value_counts().to_dict())

print("\n--- HOC client split ---")
print(df_coa[df_coa['_house'] == 'HOC']['client'].value_counts().to_dict())

print("\n--- HOL account prefix sample ---")
print(df_coa[df_coa['_house'] == 'HOL']['account'].head(10).tolist())

print("\n--- bflag distribution (HOC active) ---")
print(hoc_active['bflag'].value_counts().to_dict())

print("\n--- period_from/to format (HOC sample) ---")
sample = df_coa[df_coa['_house'] == 'HOC'][['account', 'period_from', 'period_to', 'last_update']].head(3)
print(sample.to_string(index=False))

print("\n--- Edge cases ---")
ec = df_coa[df_coa['account'].astype(str).str.startswith('8')]
print(ec[['client', 'account', 'description', 'status', 'res_bal', 'bflag', 'period_to', 'last_update']].to_string(index=False))
