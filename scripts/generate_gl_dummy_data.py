import pandas as pd
import random
from datetime import datetime, timedelta

random.seed(42)

# ============================================================
# CONFIGURATION
# Parliament-specific values would replace these placeholders
# ============================================================

CLIENTS = ['HOC', 'HOL']
FISCAL_YEAR = 2025
YEAR_END_PERIOD = 1200  # Period 12 of FY2025

# Simulated attribute_ids - in real data these come from Step 1 profile query
ATTR_ACCOUNT = 'ACCT'
ATTR_COSTC = 'COSTC'
ATTR_SUBJ = 'SUBJ'
ATTR_ANAL1 = 'ANL1'
ATTR_ANAL2 = 'ANL2'

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def random_client():
    return random.choice(CLIENTS)

def random_date(start_days_ago=730, end_days_ago=0):
    days = random.randint(end_days_ago, start_days_ago)
    return (datetime.now() - timedelta(days=days)).date()

def random_period():
    return random.randint(1, 12) * 100 + FISCAL_YEAR % 100

def random_account():
    return str(random.randint(1000, 9999))

def random_cost_centre():
    return f"CC{str(random.randint(100, 999))}"

def random_subjective():
    return f"S{str(random.randint(100, 999))}"

def random_anal1():
    return f"A1{str(random.randint(10, 99))}"

def random_anal2():
    return f"A2{str(random.randint(10, 99))}"

def random_wf_state():
    return random.choice(['', 'T', 'T', 'T', 'W'])

def random_status():
    return random.choice(['N', 'N', 'N', 'N', 'C', 'T'])

def random_amount(min_val=100, max_val=500000):
    return round(random.uniform(min_val, max_val), 2)


# ============================================================
# CHART OF ACCOUNTS — aglaccounts
# ============================================================

def generate_chart_of_accounts(n=80):

    # Define realistic account ranges
    # Balance sheet accounts: 1000-4999
    # P&L accounts: 5000-9999
    account_configs = [
        # (account_range_start, count, res_bal, account_type, description_prefix, bflag)
        (1000, 10, 'B', 'GL', 'Cash and Bank',        0),
        (1100, 8,  'B', 'GL', 'Accounts Receivable',  7),   # AR control
        (1200, 6,  'B', 'GL', 'Prepayments',           9),
        (2000, 8,  'B', 'GL', 'Accounts Payable',      7),   # AP control
        (2100, 6,  'B', 'GL', 'Accruals',              0),
        (3000, 6,  'B', 'GL', 'Capital',               0),
        (3100, 6,  'B', 'GL', 'Reserves',              0),
        (5000, 10, 'R', 'GL', 'Staff Costs',           0),
        (5100, 8,  'R', 'GL', 'Premises',              0),
        (5200, 6,  'R', 'GL', 'IT and Technology',     0),
        (5300, 6,  'R', 'GL', 'Professional Services', 0),
        (9000, 10, 'R', 'AR', 'Income',                0),
    ]

    rows = []
    account_pool = {}  # track accounts per client for cross-checks

    for client in CLIENTS:
        account_pool[client] = []
        for (start, count, res_bal, acc_type, desc_prefix, bflag) in account_configs:
            for i in range(count):
                account = str(start + i)
                account_pool[client].append(account)
                rows.append({
                    'client': client,
                    'account': account,
                    'description': f"{desc_prefix} {i+1:02d}",
                    'account_grp': f"GRP{start // 1000}",
                    'account_type': acc_type,
                    'status': 'N',
                    'res_bal': res_bal,
                    'bflag': bflag,
                    'account_rule': random.randint(1, 10),
                    'period_from': 100 + (FISCAL_YEAR % 100),
                    'period_to': 1200 + (FISCAL_YEAR % 100),
                    'last_update': random_date(365, 30),
                    'head_account': None
                })

    # --- Edge cases ---
    edge_cases = [

        # COMPLETENESS: Missing description
        {'client': 'HOC', 'account': 'EC_A001', 'description': None,
         'account_grp': 'GRP5', 'account_type': 'GL', 'status': 'N',
         'res_bal': 'R', 'bflag': 0, 'account_rule': 1,
         'period_from': 125, 'period_to': 1225,
         'last_update': random_date(90, 30), 'head_account': None},

        # COMPLETENESS: Missing account_grp
        {'client': 'HOC', 'account': 'EC_A002', 'description': 'EC Missing Group',
         'account_grp': None, 'account_type': 'GL', 'status': 'N',
         'res_bal': 'R', 'bflag': 0, 'account_rule': 1,
         'period_from': 125, 'period_to': 1225,
         'last_update': random_date(90, 30), 'head_account': None},

        # COMPLETENESS: Missing res_bal
        {'client': 'HOC', 'account': 'EC_A003', 'description': 'EC Missing ResBal',
         'account_grp': 'GRP5', 'account_type': 'GL', 'status': 'N',
         'res_bal': None, 'bflag': 0, 'account_rule': 1,
         'period_from': 125, 'period_to': 1225,
         'last_update': random_date(90, 30), 'head_account': None},

        # VALIDITY: Invalid res_bal value
        {'client': 'HOC', 'account': 'EC_A004', 'description': 'EC Invalid ResBal',
         'account_grp': 'GRP5', 'account_type': 'GL', 'status': 'N',
         'res_bal': 'X', 'bflag': 0, 'account_rule': 1,
         'period_from': 125, 'period_to': 1225,
         'last_update': random_date(90, 30), 'head_account': None},

        # VALIDITY: period_from greater than period_to
        {'client': 'HOC', 'account': 'EC_A005', 'description': 'EC Invalid Period Range',
         'account_grp': 'GRP5', 'account_type': 'GL', 'status': 'N',
         'res_bal': 'R', 'bflag': 0, 'account_rule': 1,
         'period_from': 1225, 'period_to': 125,
         'last_update': random_date(90, 30), 'head_account': None},

        # VALIDITY: Period expired but status still N
        {'client': 'HOC', 'account': 'EC_A006', 'description': 'EC Expired Period Active',
         'account_grp': 'GRP5', 'account_type': 'GL', 'status': 'N',
         'res_bal': 'R', 'bflag': 0, 'account_rule': 1,
         'period_from': 100, 'period_to': 200,
         'last_update': random_date(90, 30), 'head_account': None},

        # CONSISTENCY: P&L account in balance sheet group
        {'client': 'HOC', 'account': 'EC_A007', 'description': 'EC PL in BS Group',
         'account_grp': 'GRP1', 'account_type': 'GL', 'status': 'N',
         'res_bal': 'R', 'bflag': 0, 'account_rule': 1,
         'period_from': 125, 'period_to': 1225,
         'last_update': random_date(90, 30), 'head_account': None},

        # CONSISTENCY: Balance sheet account in P&L group
        {'client': 'HOC', 'account': 'EC_A008', 'description': 'EC BS in PL Group',
         'account_grp': 'GRP5', 'account_type': 'GL', 'status': 'N',
         'res_bal': 'B', 'bflag': 0, 'account_rule': 1,
         'period_from': 125, 'period_to': 1225,
         'last_update': random_date(90, 30), 'head_account': None},

        # CONSISTENCY: Reconciliation bflag but not AP or AR type
        {'client': 'HOC', 'account': 'EC_A009', 'description': 'EC Recon Not Control',
         'account_grp': 'GRP5', 'account_type': 'GL', 'status': 'N',
         'res_bal': 'R', 'bflag': 7, 'account_rule': 1,
         'period_from': 125, 'period_to': 1225,
         'last_update': random_date(90, 30), 'head_account': None},

        # DUPLICATE: Same description different code within HOC
        {'client': 'HOC', 'account': 'EC_A010', 'description': 'Duplicate Account Description',
         'account_grp': 'GRP5', 'account_type': 'GL', 'status': 'N',
         'res_bal': 'R', 'bflag': 0, 'account_rule': 1,
         'period_from': 125, 'period_to': 1225,
         'last_update': random_date(90, 30), 'head_account': None},

        {'client': 'HOC', 'account': 'EC_A011', 'description': 'Duplicate Account Description',
         'account_grp': 'GRP5', 'account_type': 'GL', 'status': 'N',
         'res_bal': 'R', 'bflag': 0, 'account_rule': 1,
         'period_from': 125, 'period_to': 1225,
         'last_update': random_date(90, 30), 'head_account': None},

        # SCOPE: Stale account - last updated 4 years ago
        {'client': 'HOC', 'account': 'EC_A012', 'description': 'EC Stale Account',
         'account_grp': 'GRP5', 'account_type': 'GL', 'status': 'N',
         'res_bal': 'R', 'bflag': 0, 'account_rule': 1,
         'period_from': 125, 'period_to': 1225,
         'last_update': (datetime.now() - timedelta(days=1500)).date(),
         'head_account': None},

        # BACKWARD COMPAT: Closed account - will have balances against it in aglyearend
        {'client': 'HOC', 'account': 'EC_A013', 'description': 'EC Closed With Balance',
         'account_grp': 'GRP1', 'account_type': 'GL', 'status': 'C',
         'res_bal': 'B', 'bflag': 0, 'account_rule': 1,
         'period_from': 125, 'period_to': 1225,
         'last_update': random_date(730, 365), 'head_account': None},
    ]

    return pd.DataFrame(rows + edge_cases), account_pool


# ============================================================
# DIMENSION VALUES — agldimvalue
# ============================================================

def generate_dimension_values(account_pool):

    rows = []

    # Cost centres - realistic Parliament-style codes
    cc_codes = [f"CC{str(i).zfill(3)}" for i in range(100, 130)]
    cc_parents = ['DEPT_A', 'DEPT_B', 'DEPT_C', 'DEPT_D']

    # Subjectives
    subj_codes = [f"S{str(i).zfill(3)}" for i in range(100, 125)]

    # Analysis 1 - programme codes
    anal1_codes = [f"A1{str(i).zfill(2)}" for i in range(10, 30)]

    # Analysis 2 - project codes
    anal2_codes = [f"A2{str(i).zfill(2)}" for i in range(10, 25)]

    dimension_configs = [
        (ATTR_COSTC, cc_codes, 'Cost Centre', cc_parents),
        (ATTR_SUBJ,  subj_codes, 'Subjective', None),
        (ATTR_ANAL1, anal1_codes, 'Programme', None),
        (ATTR_ANAL2, anal2_codes, 'Project', None),
    ]

    for client in CLIENTS:
        for (attr_id, codes, desc_prefix, parents) in dimension_configs:
            for i, code in enumerate(codes):
                rel_value = random.choice(parents) if parents else None
                rows.append({
                    'client': client,
                    'attribute_id': attr_id,
                    'dim_value': code,
                    'description': f"{desc_prefix} {code}",
                    'status': random.choice(['N', 'N', 'N', 'C']),
                    'period_from': 100 + (FISCAL_YEAR % 100),
                    'period_to': 1200 + (FISCAL_YEAR % 100),
                    'rel_value': rel_value,
                    'last_update': random_date(365, 30),
                    'wf_state': random_wf_state()
                })

    # --- Edge cases ---
    edge_cases = [

        # COMPLETENESS: Missing description
        {'client': 'HOC', 'attribute_id': ATTR_COSTC, 'dim_value': 'EC_D001',
         'description': None, 'status': 'N',
         'period_from': 125, 'period_to': 1225,
         'rel_value': 'DEPT_A', 'last_update': random_date(90, 30), 'wf_state': 'T'},

        # COMPLETENESS: Missing rel_value where hierarchy expected (Cost Centre)
        {'client': 'HOC', 'attribute_id': ATTR_COSTC, 'dim_value': 'EC_D002',
         'description': 'EC No Parent CC', 'status': 'N',
         'period_from': 125, 'period_to': 1225,
         'rel_value': None, 'last_update': random_date(90, 30), 'wf_state': 'T'},

        # VALIDITY: period_from greater than period_to
        {'client': 'HOC', 'attribute_id': ATTR_COSTC, 'dim_value': 'EC_D003',
         'description': 'EC Invalid Period Range', 'status': 'N',
         'period_from': 1225, 'period_to': 125,
         'rel_value': 'DEPT_A', 'last_update': random_date(90, 30), 'wf_state': 'T'},

        # VALIDITY: Period expired but status still N
        {'client': 'HOC', 'attribute_id': ATTR_COSTC, 'dim_value': 'EC_D004',
         'description': 'EC Expired Period Active', 'status': 'N',
         'period_from': 100, 'period_to': 200,
         'rel_value': 'DEPT_A', 'last_update': random_date(90, 30), 'wf_state': 'T'},

        # VALIDITY: Stuck in workflow
        {'client': 'HOC', 'attribute_id': ATTR_COSTC, 'dim_value': 'EC_D005',
         'description': 'EC Stuck Workflow', 'status': 'N',
         'period_from': 125, 'period_to': 1225,
         'rel_value': 'DEPT_A', 'last_update': random_date(90, 30), 'wf_state': 'W'},

        # CONSISTENCY: rel_value references non-existent parent
        {'client': 'HOC', 'attribute_id': ATTR_COSTC, 'dim_value': 'EC_D006',
         'description': 'EC Orphaned Parent', 'status': 'N',
         'period_from': 125, 'period_to': 1225,
         'rel_value': 'DEPT_GHOST', 'last_update': random_date(90, 30), 'wf_state': 'T'},

        # CONSISTENCY: Same description different code within HOC COSTC
        {'client': 'HOC', 'attribute_id': ATTR_COSTC, 'dim_value': 'EC_D007',
         'description': 'Duplicate Dimension Description', 'status': 'N',
         'period_from': 125, 'period_to': 1225,
         'rel_value': 'DEPT_A', 'last_update': random_date(90, 30), 'wf_state': 'T'},

        {'client': 'HOC', 'attribute_id': ATTR_COSTC, 'dim_value': 'EC_D008',
         'description': 'Duplicate Dimension Description', 'status': 'N',
         'period_from': 125, 'period_to': 1225,
         'rel_value': 'DEPT_B', 'last_update': random_date(90, 30), 'wf_state': 'T'},

        # DUPLICATE: Same dim_value exists in both Houses - consolidation candidate
        {'client': 'HOC', 'attribute_id': ATTR_COSTC, 'dim_value': 'CC999',
         'description': 'Cross House Cost Centre HOC', 'status': 'N',
         'period_from': 125, 'period_to': 1225,
         'rel_value': 'DEPT_A', 'last_update': random_date(90, 30), 'wf_state': 'T'},

        {'client': 'HOL', 'attribute_id': ATTR_COSTC, 'dim_value': 'CC999',
         'description': 'Cross House Cost Centre HOL', 'status': 'N',
         'period_from': 125, 'period_to': 1225,
         'rel_value': 'DEPT_A', 'last_update': random_date(90, 30), 'wf_state': 'T'},

        # SCOPE: Stale dimension value
        {'client': 'HOC', 'attribute_id': ATTR_COSTC, 'dim_value': 'EC_D009',
         'description': 'EC Stale Dimension', 'status': 'N',
         'period_from': 125, 'period_to': 1225,
         'rel_value': 'DEPT_A',
         'last_update': (datetime.now() - timedelta(days=1500)).date(),
         'wf_state': 'T'},

        # BACKWARD COMPAT: Inactive dimension value
        # will be referenced by transactions in aglyearend
        {'client': 'HOC', 'attribute_id': ATTR_COSTC, 'dim_value': 'EC_D010',
         'description': 'EC Inactive With Balances', 'status': 'C',
         'period_from': 125, 'period_to': 1225,
         'rel_value': 'DEPT_A', 'last_update': random_date(730, 365), 'wf_state': 'T'},
    ]

    return pd.DataFrame(rows + edge_cases)


# ============================================================
# OPENING BALANCES — aglyearend
# ============================================================

def generate_opening_balances(df_accounts, df_dimensions):

    # Get active accounts and dimension values for realistic data
    active_accounts = df_accounts[
        (df_accounts['status'] == 'N') &
        (~df_accounts['account'].str.startswith('EC_'))
    ][['client', 'account', 'res_bal', 'account_type']].values.tolist()

    active_cc = df_dimensions[
        (df_dimensions['attribute_id'] == ATTR_COSTC) &
        (df_dimensions['status'] == 'N') &
        (~df_dimensions['dim_value'].str.startswith('EC_'))
    ]['dim_value'].tolist()

    active_subj = df_dimensions[
        (df_dimensions['attribute_id'] == ATTR_SUBJ) &
        (df_dimensions['status'] == 'N') &
        (~df_dimensions['dim_value'].str.startswith('EC_'))
    ]['dim_value'].tolist()

    rows = []
    balance_sheet_total = {'HOC': 0, 'HOL': 0}

    for i in range(150):
        client, account, res_bal, acc_type = random.choice(active_accounts)
        amount = random_amount()
        dc_flag = random.choice([1, -1])  # 1=debit, -1=credit

        # Track balance sheet totals for reconciliation check
        if res_bal == 'B':
            balance_sheet_total[client] += amount * dc_flag

        rows.append({
            'client': client,
            'account': account,
            'fiscal_year': FISCAL_YEAR,
            'period': YEAR_END_PERIOD,
            'dim_1': random.choice(active_cc),     # Cost Centre
            'dim_2': random.choice(active_subj),   # Subjective
            'dim_3': None,
            'dim_4': None,
            'dim_5': None,
            'dim_6': None,
            'dim_7': None,
            'amount': amount,
            'cur_amount': amount,
            'currency': 'GBP',
            'dc_flag': dc_flag,
            'voucher_type': 'YEBAL',
            'tax_code': random.choice(['S20', 'Z0', None]),
            'apar_id': None,
            'apar_type': None
        })

    # Add AP and AR control account balances with apar_id populated
    # These are the rows used for sub-ledger reconciliation
    for client in CLIENTS:
        # AP control account balance
        rows.append({
            'client': client,
            'account': '2000',          # AP control account
            'fiscal_year': FISCAL_YEAR,
            'period': YEAR_END_PERIOD,
            'dim_1': 'CC100',
            'dim_2': 'S100',
            'dim_3': None, 'dim_4': None, 'dim_5': None, 'dim_6': None, 'dim_7': None,
            'amount': random_amount(50000, 500000),
            'cur_amount': random_amount(50000, 500000),
            'currency': 'GBP',
            'dc_flag': -1,              # Credit - AP is a liability
            'voucher_type': 'YEBAL',
            'tax_code': None,
            'apar_id': 'SUP_CONTROL',
            'apar_type': 'P'
        })

        # AR control account balance
        rows.append({
            'client': client,
            'account': '1100',          # AR control account
            'fiscal_year': FISCAL_YEAR,
            'period': YEAR_END_PERIOD,
            'dim_1': 'CC100',
            'dim_2': 'S100',
            'dim_3': None, 'dim_4': None, 'dim_5': None, 'dim_6': None, 'dim_7': None,
            'amount': random_amount(50000, 500000),
            'cur_amount': random_amount(50000, 500000),
            'currency': 'GBP',
            'dc_flag': 1,               # Debit - AR is an asset
            'voucher_type': 'YEBAL',
            'tax_code': None,
            'apar_id': 'CUST_CONTROL',
            'apar_type': 'R'
        })

    # --- Edge cases ---
    edge_cases = [

        # COMPLETENESS: Missing amount
        {'client': 'HOC', 'account': '5000', 'fiscal_year': FISCAL_YEAR,
         'period': YEAR_END_PERIOD, 'dim_1': 'CC100', 'dim_2': 'S100',
         'dim_3': None, 'dim_4': None, 'dim_5': None, 'dim_6': None, 'dim_7': None,
         'amount': None, 'cur_amount': None, 'currency': 'GBP', 'dc_flag': 1,
         'voucher_type': 'YEBAL', 'tax_code': None, 'apar_id': None, 'apar_type': None},

        # VALIDITY: Duplicate coding string - same account and dimensions
        {'client': 'HOC', 'account': '5001', 'fiscal_year': FISCAL_YEAR,
         'period': YEAR_END_PERIOD, 'dim_1': 'CC_DUP', 'dim_2': 'S_DUP',
         'dim_3': None, 'dim_4': None, 'dim_5': None, 'dim_6': None, 'dim_7': None,
         'amount': 10000, 'cur_amount': 10000, 'currency': 'GBP', 'dc_flag': 1,
         'voucher_type': 'YEBAL', 'tax_code': None, 'apar_id': None, 'apar_type': None},

        {'client': 'HOC', 'account': '5001', 'fiscal_year': FISCAL_YEAR,
         'period': YEAR_END_PERIOD, 'dim_1': 'CC_DUP', 'dim_2': 'S_DUP',
         'dim_3': None, 'dim_4': None, 'dim_5': None, 'dim_6': None, 'dim_7': None,
         'amount': 5000, 'cur_amount': 5000, 'currency': 'GBP', 'dc_flag': 1,
         'voucher_type': 'YEBAL', 'tax_code': None, 'apar_id': None, 'apar_type': None},

        # VALIDITY: P&L account with non-zero balance at year end
        {'client': 'HOC', 'account': '5002', 'fiscal_year': FISCAL_YEAR,
         'period': YEAR_END_PERIOD, 'dim_1': 'CC100', 'dim_2': 'S100',
         'dim_3': None, 'dim_4': None, 'dim_5': None, 'dim_6': None, 'dim_7': None,
         'amount': 25000, 'cur_amount': 25000, 'currency': 'GBP', 'dc_flag': 1,
         'voucher_type': 'YEBAL', 'tax_code': None, 'apar_id': None, 'apar_type': None},

        # VALIDITY: Wrong period - not year end period
        {'client': 'HOC', 'account': '5003', 'fiscal_year': FISCAL_YEAR,
         'period': 600,   # Period 6 not year end
         'dim_1': 'CC100', 'dim_2': 'S100',
         'dim_3': None, 'dim_4': None, 'dim_5': None, 'dim_6': None, 'dim_7': None,
         'amount': 8000, 'cur_amount': 8000, 'currency': 'GBP', 'dc_flag': 1,
         'voucher_type': 'YEBAL', 'tax_code': None, 'apar_id': None, 'apar_type': None},

        # CONSISTENCY: Balance against non-existent account
        {'client': 'HOC', 'account': 'GHOST_ACC', 'fiscal_year': FISCAL_YEAR,
         'period': YEAR_END_PERIOD, 'dim_1': 'CC100', 'dim_2': 'S100',
         'dim_3': None, 'dim_4': None, 'dim_5': None, 'dim_6': None, 'dim_7': None,
         'amount': 15000, 'cur_amount': 15000, 'currency': 'GBP', 'dc_flag': 1,
         'voucher_type': 'YEBAL', 'tax_code': None, 'apar_id': None, 'apar_type': None},

        # CONSISTENCY: Balance against closed account (EC_A013)
        {'client': 'HOC', 'account': 'EC_A013', 'fiscal_year': FISCAL_YEAR,
         'period': YEAR_END_PERIOD, 'dim_1': 'CC100', 'dim_2': 'S100',
         'dim_3': None, 'dim_4': None, 'dim_5': None, 'dim_6': None, 'dim_7': None,
         'amount': 5000, 'cur_amount': 5000, 'currency': 'GBP', 'dc_flag': 1,
         'voucher_type': 'YEBAL', 'tax_code': None, 'apar_id': None, 'apar_type': None},

        # CONSISTENCY: Balance against inactive dimension value (EC_D010)
        {'client': 'HOC', 'account': '5004', 'fiscal_year': FISCAL_YEAR,
         'period': YEAR_END_PERIOD, 'dim_1': 'EC_D010', 'dim_2': 'S100',
         'dim_3': None, 'dim_4': None, 'dim_5': None, 'dim_6': None, 'dim_7': None,
         'amount': 3000, 'cur_amount': 3000, 'currency': 'GBP', 'dc_flag': 1,
         'voucher_type': 'YEBAL', 'tax_code': None, 'apar_id': None, 'apar_type': None},

        # CONSISTENCY: Balance against non-existent dimension value
        {'client': 'HOC', 'account': '5005', 'fiscal_year': FISCAL_YEAR,
         'period': YEAR_END_PERIOD, 'dim_1': 'CC_GHOST', 'dim_2': 'S100',
         'dim_3': None, 'dim_4': None, 'dim_5': None, 'dim_6': None, 'dim_7': None,
         'amount': 7500, 'cur_amount': 7500, 'currency': 'GBP', 'dc_flag': 1,
         'voucher_type': 'YEBAL', 'tax_code': None, 'apar_id': None, 'apar_type': None},

        # RECONCILIATION: AP control account with deliberately mismatched amount
        # Sum of open supplier rest_amounts will not match this value
        {'client': 'HOC', 'account': '2000', 'fiscal_year': FISCAL_YEAR,
         'period': YEAR_END_PERIOD, 'dim_1': 'CC100', 'dim_2': 'S100',
         'dim_3': None, 'dim_4': None, 'dim_5': None, 'dim_6': None, 'dim_7': None,
         'amount': 999999.99,    # Deliberately wrong for reconciliation test
         'cur_amount': 999999.99, 'currency': 'GBP', 'dc_flag': -1,
         'voucher_type': 'YEBAL', 'tax_code': None,
         'apar_id': 'SUP_RECON_EC', 'apar_type': 'P'},
    ]

    return pd.DataFrame(rows + edge_cases)


# ============================================================
# GENERATE ALL THREE
# ============================================================

df_accounts, account_pool = generate_chart_of_accounts()
df_dimensions = generate_dimension_values(account_pool)
df_balances = generate_opening_balances(df_accounts, df_dimensions)

# ============================================================
# SAVE TO CSV
# ============================================================

df_accounts.to_csv('gl_chart_of_accounts.csv', index=False)
df_dimensions.to_csv('gl_dimension_values.csv', index=False)
df_balances.to_csv('gl_opening_balances.csv', index=False)

print(f"Chart of accounts:  {len(df_accounts)} rows -> gl_chart_of_accounts.csv")
print(f"Dimension values:   {len(df_dimensions)} rows -> gl_dimension_values.csv")
print(f"Opening balances:   {len(df_balances)} rows -> gl_opening_balances.csv")

print("\n--- Account Type Split ---")
print(df_accounts[df_accounts['status'] == 'N']['account_type'].value_counts())

print("\n--- Dimension Value Split by attribute_id ---")
print(df_dimensions[df_dimensions['status'] == 'N']['attribute_id'].value_counts())

print("\n--- Balance Split by res_bal (joined) ---")
merged = df_balances.merge(
    df_accounts[['client', 'account', 'res_bal']],
    on=['client', 'account'],
    how='left'
)
print(merged['res_bal'].value_counts())

print("\n--- Edge Cases in Accounts ---")
print(df_accounts[df_accounts['account'].str.startswith('EC_')][
    ['account', 'description', 'status', 'res_bal']
])

print("\n--- Edge Cases in Dimensions ---")
print(df_dimensions[df_dimensions['dim_value'].str.startswith('EC_')][
    ['attribute_id', 'dim_value', 'description', 'status']
])

print("\n--- Edge Cases in Balances ---")
ec_balances = df_balances[
    df_balances['account'].str.startswith('EC_') |
    df_balances['account'].str.startswith('GHOST') |
    df_balances['dim_1'].str.startswith('EC_') |
    df_balances['dim_1'].str.startswith('CC_') |
    (df_balances['amount'] == 999999.99)
][['client', 'account', 'dim_1', 'amount', 'dc_flag']]
print(ec_balances)