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
PERIOD_TO_NORMAL   = to_excel(date(2099, 12, 31))  # 72684 — effectively no expiry
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
# Format not yet confirmed from real data — client codes updated, structure TBD
# ===========================================================================

ATTR_COSTC = 'COSTC'
ATTR_SUBJ  = 'SUBJ'
ATTR_ANAL1 = 'ANL1'
ATTR_ANAL2 = 'ANL2'

def generate_dimension_values(df_accounts: pd.DataFrame) -> pd.DataFrame:
    rows = []

    cc_codes    = [f"CC{i:03d}" for i in range(100, 130)]
    cc_parents  = ['DEPT_A', 'DEPT_B', 'DEPT_C', 'DEPT_D']
    subj_codes  = [f"S{i:03d}" for i in range(100, 125)]
    anal1_codes = [f"A1{i:02d}" for i in range(10, 30)]
    anal2_codes = [f"A2{i:02d}" for i in range(10, 25)]

    dimension_configs = [
        (ATTR_COSTC, cc_codes,    'Cost Centre', cc_parents, 1),
        (ATTR_SUBJ,  subj_codes,  'Subjective',  None,       2),
        (ATTR_ANAL1, anal1_codes, 'Programme',   None,       3),
        (ATTR_ANAL2, anal2_codes, 'Project',     None,       4),
    ]

    # Generate for both houses using confirmed client codes
    all_clients = HOC_CLIENTS + [HOL_CLIENT]
    for client in all_clients:
        house = client_to_house(client)
        for (attr_id, codes, desc_prefix, parents, dim_pos) in dimension_configs:
            for code in codes:
                rel_value = random.choice(parents) if parents else None
                rows.append({
                    '_house':       house,
                    'client':       client,
                    'attribute_id': attr_id,
                    'dim_position': dim_pos,
                    'dim_value':    code,
                    'description':  f"{desc_prefix} {code}",
                    'status':       random.choice(['N', 'N', 'N', 'C']),
                    'period_from':  make_period_from(),
                    'period_to':    PERIOD_TO_NORMAL,
                    'rel_value':    rel_value,
                    'last_update':  last_update_recent(),
                    'wf_state':     random.choice(['T', 'T', 'T', 'W', '']),
                })

    edge_cases = [
        {'_house': 'HOC', 'client': 'CA', 'attribute_id': ATTR_COSTC, 'dim_position': 1,
         'dim_value': 'EC_D001', 'description': None, 'status': 'N',
         'period_from': PERIOD_FROM_NORMAL, 'period_to': PERIOD_TO_NORMAL,
         'rel_value': 'DEPT_A', 'last_update': last_update_recent(), 'wf_state': 'T'},

        {'_house': 'HOC', 'client': 'CA', 'attribute_id': ATTR_COSTC, 'dim_position': 1,
         'dim_value': 'EC_D002', 'description': 'EC No Parent CC', 'status': 'N',
         'period_from': PERIOD_FROM_NORMAL, 'period_to': PERIOD_TO_NORMAL,
         'rel_value': None, 'last_update': last_update_recent(), 'wf_state': 'T'},

        {'_house': 'HOC', 'client': 'CA', 'attribute_id': ATTR_COSTC, 'dim_position': 1,
         'dim_value': 'EC_D003', 'description': 'EC Invalid Period', 'status': 'N',
         'period_from': PERIOD_TO_NORMAL, 'period_to': PERIOD_FROM_NORMAL,
         'rel_value': 'DEPT_A', 'last_update': last_update_recent(), 'wf_state': 'T'},

        {'_house': 'HOC', 'client': 'CA', 'attribute_id': ATTR_COSTC, 'dim_position': 1,
         'dim_value': 'EC_D004', 'description': 'EC Expired Active', 'status': 'N',
         'period_from': PERIOD_FROM_NORMAL, 'period_to': PERIOD_TO_EXPIRED,
         'rel_value': 'DEPT_A', 'last_update': last_update_recent(), 'wf_state': 'T'},

        {'_house': 'HOC', 'client': 'CA', 'attribute_id': ATTR_COSTC, 'dim_position': 1,
         'dim_value': 'EC_D005', 'description': 'EC Stuck Workflow', 'status': 'N',
         'period_from': PERIOD_FROM_NORMAL, 'period_to': PERIOD_TO_NORMAL,
         'rel_value': 'DEPT_A', 'last_update': last_update_recent(), 'wf_state': 'W'},

        {'_house': 'HOC', 'client': 'CA', 'attribute_id': ATTR_COSTC, 'dim_position': 1,
         'dim_value': 'EC_D006', 'description': 'EC Orphaned Parent', 'status': 'N',
         'period_from': PERIOD_FROM_NORMAL, 'period_to': PERIOD_TO_NORMAL,
         'rel_value': 'DEPT_GHOST', 'last_update': last_update_recent(), 'wf_state': 'T'},

        {'_house': 'HOC', 'client': 'CA', 'attribute_id': ATTR_COSTC, 'dim_position': 1,
         'dim_value': 'EC_D009', 'description': 'EC Stale Dimension', 'status': 'N',
         'period_from': PERIOD_FROM_NORMAL, 'period_to': PERIOD_TO_NORMAL,
         'rel_value': 'DEPT_A', 'last_update': LAST_UPDATE_STALE, 'wf_state': 'T'},

        {'_house': 'HOC', 'client': 'CA', 'attribute_id': ATTR_COSTC, 'dim_position': 1,
         'dim_value': 'EC_D010', 'description': 'EC Inactive With Balances', 'status': 'C',
         'period_from': PERIOD_FROM_NORMAL, 'period_to': PERIOD_TO_NORMAL,
         'rel_value': 'DEPT_A', 'last_update': last_update_recent(), 'wf_state': 'T'},
    ]

    return pd.DataFrame(rows + edge_cases)


# ===========================================================================
# OPENING BALANCES — aglperiodic (frame key: aglyearend for backwards compat)
# period is YYYYPP integer (e.g. 202612 = FY2025/26 period 12)
# ===========================================================================

FISCAL_YEAR       = 2026
YEAR_END_PERIOD   = 202612   # Period 12 of FY2025/26

def random_amount(min_val=100, max_val=500_000):
    return round(random.uniform(min_val, max_val), 2)

def generate_opening_balances(df_accounts: pd.DataFrame) -> pd.DataFrame:
    active = df_accounts[
        (df_accounts['status'] == 'N') &
        (~df_accounts['account'].astype(str).str.startswith('8'))  # exclude edge cases
    ][['_house', 'client', 'account', 'res_bal', 'account_type']].values.tolist()

    cc_codes   = [f"CC{i:03d}" for i in range(100, 130)]
    subj_codes = [f"S{i:03d}" for i in range(100, 125)]

    rows = []
    for i in range(200):
        house, client, account, res_bal, acc_type = random.choice(active)
        amount = random_amount()
        dc_flag = random.choice(['D', 'C'])
        rows.append({
            '_house':       house,
            'client':       client,
            'account':      account,
            'period':       YEAR_END_PERIOD,
            'dim_1':        random.choice(cc_codes),
            'dim_2':        random.choice(subj_codes),
            'dim_3': None, 'dim_4': None, 'dim_5': None, 'dim_6': None, 'dim_7': None,
            'amount':       amount,
            'cur_amount':   amount,
            'currency':     'GBP',
            'dc_flag':      dc_flag,
            'voucher_type': 'JO',
            'voucher_no':   f"OB{i:04d}",
            'trans_date':   to_excel(date(2026, 4, 1)),
            'tax_code':     None,
            'apar_id':      None,
            'apar_type':    None,
            'status':       '',
            'description':  'Opening balance',
        })

    # Edge cases — completeness and referential integrity
    edge_cases = [
        # GL_BAL_AMT_MISSING: balance record with no amount
        {'_house': 'HOC', 'client': 'CA', 'account': '4000', 'period': YEAR_END_PERIOD,
         'dim_1': 'CC100', 'dim_2': 'S100', 'dim_3': None, 'dim_4': None, 'dim_5': None,
         'dim_6': None, 'dim_7': None, 'amount': None, 'cur_amount': None, 'currency': 'GBP',
         'dc_flag': 'D', 'voucher_type': 'JO', 'voucher_no': 'OB9001',
         'trans_date': to_excel(date(2026, 4, 1)), 'tax_code': None,
         'apar_id': None, 'apar_type': None, 'status': '', 'description': 'EC Missing Amount'},

        # GL_BAL_ORPHAN_ACC: balance against account that doesn't exist in CoA
        {'_house': 'HOC', 'client': 'CA', 'account': '9999', 'period': YEAR_END_PERIOD,
         'dim_1': 'CC100', 'dim_2': 'S100', 'dim_3': None, 'dim_4': None, 'dim_5': None,
         'dim_6': None, 'dim_7': None, 'amount': 15000, 'cur_amount': 15000, 'currency': 'GBP',
         'dc_flag': 'D', 'voucher_type': 'JO', 'voucher_no': 'OB9002',
         'trans_date': to_excel(date(2026, 4, 1)), 'tax_code': None,
         'apar_id': None, 'apar_type': None, 'status': '', 'description': 'EC Ghost Account'},

        # GL_BAL_PL_NONZERO: P&L account with non-zero balance at year end
        {'_house': 'HOC', 'client': 'CA', 'account': '4000', 'period': YEAR_END_PERIOD,
         'dim_1': 'CC100', 'dim_2': 'S100', 'dim_3': None, 'dim_4': None, 'dim_5': None,
         'dim_6': None, 'dim_7': None, 'amount': 25000, 'cur_amount': 25000, 'currency': 'GBP',
         'dc_flag': 'D', 'voucher_type': 'JO', 'voucher_no': 'OB9003',
         'trans_date': to_excel(date(2026, 4, 1)), 'tax_code': None,
         'apar_id': None, 'apar_type': None, 'status': '', 'description': 'EC PL Nonzero'},
    ]

    return pd.DataFrame(rows + edge_cases)


# ===========================================================================
# GENERATE AND SAVE
# ===========================================================================

import os
os.makedirs('data/gl', exist_ok=True)

df_coa  = generate_chart_of_accounts()
df_dims = generate_dimension_values(df_coa)
df_bal  = generate_opening_balances(df_coa)

for house in ['HOC', 'HOL']:
    coa_out  = df_coa [df_coa ['_house'] == house].drop(columns=['_house'])
    dims_out = df_dims[df_dims['_house'] == house].drop(columns=['_house'])
    bal_out  = df_bal [df_bal ['_house'] == house].drop(columns=['_house'])

    coa_out .to_csv(f'data/gl/gl_chart_of_accounts_{house}.csv',  index=False)
    dims_out.to_csv(f'data/gl/gl_dimension_values_{house}.csv',   index=False)
    bal_out .to_csv(f'data/gl/gl_opening_balances_{house}.csv',   index=False)

    # gl_transact_dimensions: distinct dim combinations from opening balances
    dim_cols = ['client', 'dim_1', 'dim_2', 'dim_3', 'dim_4', 'dim_5', 'dim_6', 'dim_7']
    bal_out[dim_cols].drop_duplicates().to_csv(
        f'data/gl/gl_transact_dimensions_{house}.csv', index=False
    )

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
