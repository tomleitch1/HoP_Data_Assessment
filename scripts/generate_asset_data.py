"""
Parliament Finance Systems Programme
Fixed Asset Dummy Data Generator
=================================
Generates eight CSVs mirroring the exact shape of the four Asset SQL extracts:
  - asset_master_HOC.csv       / asset_master_HOL.csv
  - asset_depreciation_HOC.csv / asset_depreciation_HOL.csv
  - asset_balances_HOC.csv     / asset_balances_HOL.csv
  - asset_trans_flags_HOC.csv  / asset_trans_flags_HOL.csv

Contains baseline clean records and hardcoded edge cases for DQ tests.
"""

import os
import random
from datetime import timedelta, date

import pandas as pd
from faker import Faker

fake = Faker('en_GB')
random.seed(42)
Faker.seed(42)

OUTPUT_DIR = os.path.join('data', 'assets')
os.makedirs(OUTPUT_DIR, exist_ok=True)

TODAY = date.today()

HOC_CLIENTS = ['CA', 'CF', 'CM']
HOL_CLIENTS = ['LA']

ASSET_GROUPS = {
    'BUILD': {'life': 50, 'method': 'LIN'},
    'EQUIP': {'life': 10, 'method': 'LIN'},
    'IT':    {'life': 5,  'method': 'LIN'},
    'VEH':   {'life': 7,  'method': 'BAL'},
    'FURN':  {'life': 10, 'method': 'LIN'},
    'ART':   {'life': 99, 'method': 'LIN'},
    'INT':   {'life': 3,  'method': 'LIN'},
    'LEASE': {'life': 15, 'method': 'LIN'}
}

def rand_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, max(delta, 0)))

def to_period(d: date) -> str:
    return f"{d.year}{d.month:02d}"

def make_clean_asset(client: str, asset_id: str) -> dict:
    status = random.choices(['N', 'C', 'T'], weights=[0.8, 0.1, 0.1])[0]
    wf_state = random.choices(['', 'N', 'T'], weights=[0.5, 0.3, 0.2])[0]
    is_capitalised = random.random() < 0.9
    
    start_date = rand_date(TODAY - timedelta(days=3650), TODAY - timedelta(days=30))
    cap_date = start_date + timedelta(days=random.randint(0, 30)) if is_capitalised else None
    
    if status in ('C', 'T'):
        date_to = rand_date(start_date + timedelta(days=30), TODAY).isoformat()
    else:
        date_to = None
        
    org_amount = round(random.uniform(1000, 500000), 2) if is_capitalised else (round(random.uniform(100, 1000), 2) if random.random() < 0.5 else None)
    
    return {
        'client': client,
        'asset_id': asset_id,
        'asset_group': random.choice(['IT_EQ', 'FURN', 'VEH', 'BLDG', 'SOFT']),
        'description': fake.catch_phrase(),
        'short_info': fake.word()[:20],
        'status': status,
        'wf_state': wf_state,
        'cap_date_from': cap_date.isoformat() if cap_date else None,
        'cap_period_from': to_period(cap_date) if cap_date else None,
        'date_from': start_date.isoformat(),
        'date_to': date_to,
        'apar_id': f"SUPP{random.randint(1000, 9999)}" if random.random() < 0.5 else None,
        'parent_asset': None,
        'grant_flag': 1 if random.random() < 0.05 else 0,
        'org_amount': org_amount,
        'org_amt_date': cap_date.isoformat() if cap_date else (start_date.isoformat() if org_amount else None),
        'base_amount': org_amount,
        'std_amount': org_amount,
        'ins_amount': round(org_amount * 1.1, 2) if org_amount else None,
        'dim_1': f"CC{random.randint(100,999)}",
        'dim_2': f"DEPT{random.randint(10,99)}",
        'dim_3': f"PROJ{random.randint(1000,9999)}",
        'dim_4': None,
        'dim_5': None,
        'dim_6': None,
        'dim_7': None,
        'last_update': rand_date(TODAY - timedelta(days=100), TODAY).isoformat(),
        'user_id': fake.user_name(),
        '_edge_case': None
    }

def make_clean_depr(client: str, asset_id: str, master_row: dict, book_id: str) -> dict:
    depr_method = random.choice(['LIN', 'BAL', 'EXP', 'SYD'])
    if depr_method in ('LIN', 'SYD'):
        lifetime = random.randint(3, 50)
        depr_percent = None
    elif depr_method == 'BAL':
        lifetime = None
        depr_percent = round(random.uniform(5, 33), 2)
    else: # EXP
        lifetime = None
        depr_percent = None
        
    cap_date = master_row['cap_date_from']
    return {
        'client': client,
        'asset_id': asset_id,
        'depr_book_id': book_id,
        'status': master_row['status'],
        'depr_method': depr_method,
        'depr_percent': depr_percent,
        'lifetime': lifetime,
        'res_value': 0.0,
        'res_val_flag': '0',
        'salvage_amount': 0.0,
        'cap_date_from': cap_date,
        'cap_period_from': master_row['cap_period_from'],
        'cap_flag': 1 if cap_date else 0,
        'date_from': master_row['date_from'],
        'date_to': master_row['date_to'],
        'depr_period': to_period(TODAY - timedelta(days=random.randint(0, 60))),
        'depr_limit': 0.0,
        'depr_max_perc': None,
        'nbv_rounding': random.choice(['true', 'false']),
        'switch': 'true' if depr_method == 'BAL' and random.random() < 0.1 else 'false',
        'period_exact': 'true',
        'frequency': 'M',
        'index_id': 'IDX1' if random.random() < 0.05 and depr_method != 'EXP' else None,
        'index_code': 'C1' if random.random() < 0.05 and depr_method != 'EXP' else None,
        'repl_amount': None,
        'dim_1': master_row['dim_1'],
        'dim_2': master_row['dim_2'],
        'dim_3': master_row['dim_3'],
        'dim_4': None, 'dim_5': None, 'dim_6': None, 'dim_7': None,
        'last_update': master_row['last_update'],
        'user_id': master_row['user_id'],
        '_edge_case': None
    }

def make_clean_balances(client: str, asset_id: str, book_id: str, master_row: dict) -> list:
    rows = []
    start_date = date.fromisoformat(master_row['cap_date_from']) if master_row['cap_date_from'] else date.fromisoformat(master_row['date_from'])
    org_amount = master_row['org_amount'] or 0.0
    
    if org_amount > 0:
        # CA row
        rows.append({
            'client': client, 'asset_id': asset_id, 'depr_book_id': book_id,
            'trans_type': 'CA',
            'total_amount': org_amount,
            'total_cur_amount': org_amount,
            'max_trans_date': start_date.isoformat(),
            'min_trans_date': start_date.isoformat(),
            'transaction_count': random.randint(1, 5),
            '_edge_case': None
        })
        
        # ND row
        accum_depr = round(org_amount * random.uniform(0.1, 0.9), 2)
        nd_start = start_date + timedelta(days=30)
        nd_end = TODAY - timedelta(days=15)
        if nd_end < nd_start: nd_end = nd_start
        rows.append({
            'client': client, 'asset_id': asset_id, 'depr_book_id': book_id,
            'trans_type': 'ND',
            'total_amount': -accum_depr,
            'total_cur_amount': -accum_depr,
            'max_trans_date': nd_end.isoformat(),
            'min_trans_date': nd_start.isoformat(),
            'transaction_count': random.randint(1, 120),
            '_edge_case': None
        })
        
        # SA row if disposed
        if master_row['status'] in ('C', 'T'):
            disp_date = date.fromisoformat(master_row['date_to']) if master_row['date_to'] else TODAY
            rows.append({
                'client': client, 'asset_id': asset_id, 'depr_book_id': book_id,
                'trans_type': 'SA',
                'total_amount': round(org_amount - accum_depr, 2),
                'total_cur_amount': round(org_amount - accum_depr, 2),
                'max_trans_date': disp_date.isoformat(),
                'min_trans_date': disp_date.isoformat(),
                'transaction_count': 1,
                '_edge_case': None
            })
            
    return rows

def make_clean_trans_flags(client: str, asset_id: str, book_id: str, master_row: dict) -> list:
    rows = []
    start_date = date.fromisoformat(master_row['cap_date_from']) if master_row['cap_date_from'] else date.fromisoformat(master_row['date_from'])
    org_amount = master_row['org_amount'] or 0.0

    if org_amount > 0:
        # CA — individual row (row_type=INDIVIDUAL mirrors the real SQL extract)
        rows.append({
            'client': client, 'asset_id': asset_id, 'depr_book_id': book_id,
            'trans_type': 'CA',
            'trans_date': start_date.isoformat(),
            'at_trans_date': start_date.isoformat(),
            'fiscal_year': start_date.year,
            'amount': org_amount,
            'dc_flag': 1,
            'row_type': 'INDIVIDUAL',
            '_edge_case': None
        })

        # ND — one aggregated LATEST_DEPR row (MAX trans_date across all ND postings).
        # Real SQL does GROUP BY to avoid millions of monthly-depreciation rows.
        nd_dates = []
        for i in range(3):
            nd_date = start_date + timedelta(days=30*(i+1))
            if nd_date > TODAY:
                break
            if master_row['date_to'] and nd_date > date.fromisoformat(master_row['date_to']):
                break
            nd_dates.append(nd_date)
        if nd_dates:
            rows.append({
                'client': client, 'asset_id': asset_id, 'depr_book_id': book_id,
                'trans_type': 'ND',
                'trans_date': max(nd_dates).isoformat(),
                'at_trans_date': None,
                'fiscal_year': None,
                'amount': None,
                'dc_flag': None,
                'row_type': 'LATEST_DEPR',
                '_edge_case': None
            })

        # SA — individual row for disposed/transferred assets
        if master_row['status'] in ('C', 'T'):
            disp_date = date.fromisoformat(master_row['date_to']) if master_row['date_to'] else TODAY
            rows.append({
                'client': client, 'asset_id': asset_id, 'depr_book_id': book_id,
                'trans_type': 'SA',
                'trans_date': disp_date.isoformat(),
                'at_trans_date': disp_date.isoformat(),
                'fiscal_year': disp_date.year,
                'amount': org_amount * 0.5,
                'dc_flag': -1,
                'row_type': 'INDIVIDUAL',
                '_edge_case': None
            })

    return rows

def generate_house_data(house: str, clients: list, n_baseline: int):
    master_rows = []
    depr_rows = []
    bal_rows = []
    trans_rows = []
    
    idx = 1
    def next_id():
        nonlocal idx
        val = idx
        idx += 1
        return f"A{house}{val:04d}"

    # --- BASELINE ROWS ---
    for _ in range(n_baseline):
        client = random.choice(clients)
        aid = next_id()
        m = make_clean_asset(client, aid)
        d = make_clean_depr(client, aid, m, 'FINBOOK')
        
        b = make_clean_balances(client, aid, d['depr_book_id'], m)
        t = make_clean_trans_flags(client, aid, d['depr_book_id'], m)
        
        if random.random() < 0.2:
            d2 = make_clean_depr(client, aid, m, 'TAXBOOK')
            b2 = make_clean_balances(client, aid, d2['depr_book_id'], m)
            t2 = make_clean_trans_flags(client, aid, d2['depr_book_id'], m)
            depr_rows.append(d2)
            bal_rows.extend(b2)
            trans_rows.extend(t2)
            
        master_rows.append(m)
        depr_rows.append(d)
        bal_rows.extend(b)
        trans_rows.extend(t)
        
    # --- EDGE CASES ---
    def add_case(label, table, modifier, client=clients[0]):
        aid = next_id()
        m = make_clean_asset(client, aid)
        m['status'] = 'N'
        m['cap_date_from'] = rand_date(TODAY - timedelta(days=1000), TODAY - timedelta(days=30)).isoformat()
        m['org_amount'] = 10000.0
        
        d = make_clean_depr(client, aid, m, 'FINBOOK')
        b_list = make_clean_balances(client, aid, d['depr_book_id'], m)
        t_list = make_clean_trans_flags(client, aid, d['depr_book_id'], m)
        
        if table == 'master':
            m.update(modifier)
            m['_edge_case'] = label
        elif table == 'depr':
            d.update(modifier)
            d['_edge_case'] = label
        elif table == 'balances':
            if callable(modifier):
                b_list = modifier(b_list)
            else:
                if b_list:
                    b_list[0].update(modifier)
                    b_list[0]['_edge_case'] = label
        elif table == 'trans_flags':
            if callable(modifier):
                t_list = modifier(t_list)
            else:
                if t_list:
                    t_list[0].update(modifier)
                    t_list[0]['_edge_case'] = label
                
        # Cross-table side-effects for consistency
        if label == 'DQ-AF-X02':
            m['date_to'] = TODAY.isoformat()
            
        master_rows.append(m)
        depr_rows.append(d)
        bal_rows.extend(b_list)
        trans_rows.extend(t_list)

    # Master Edge Cases
    add_case('DQ-AM-C01', 'master', {'asset_id': None})
    add_case('DQ-AM-C02', 'master', {'description': None})
    add_case('DQ-AM-C03', 'master', {'asset_group': None})
    add_case('DQ-AM-C04', 'master', {'date_from': None})
    add_case('DQ-AM-C05', 'master', {'org_amount': 0.0})
    add_case('DQ-AM-C06', 'master', {'cap_date_from': None}) 
    add_case('DQ-AM-C07', 'master', {'ins_amount': None})
    
    add_case('DQ-AM-V01', 'master', {'status': 'X'})
    add_case('DQ-AM-V02', 'master', {'wf_state': 'Y'})
    add_case('DQ-AM-V03', 'master', {'org_amount': -500.0})
    add_case('DQ-AM-V04', 'master', {'date_from': '2024-01-01', 'date_to': '2023-01-01'})
    add_case('DQ-AM-V05', 'master', {'date_from': '2023-01-01', 'cap_date_from': '2022-01-01'})
    add_case('DQ-AM-V06', 'master', {'cap_date_from': '2020-01-01', 'org_amt_date': '2022-01-01'})
    add_case('DQ-AM-V07', 'master', {'last_update': '2099-01-01'})
    
    add_case('DQ-AM-K01', 'master', {'date_to': '2023-01-01'})
    add_case('DQ-AM-K02', 'master', {'wf_state': 'W'})
    add_case('DQ-AM-K03', 'master', {'org_amt_date': None, 'org_amount': 5000.0})
    add_case('DQ-AM-K04', 'master', {'grant_flag': 1, 'dim_1': None, 'dim_2': None, 'dim_3': None})
    
    add_case('DQ-AM-D01', 'master', {'asset_id': f"A{house}0001"}) 
    add_case('DQ-AM-D02', 'master', {'description': 'Dup Desc', 'asset_group': 'IT_EQ', 'org_amount': 500.0})
    add_case('DQ-AM-D02', 'master', {'description': 'Dup Desc', 'asset_group': 'IT_EQ', 'org_amount': 500.0}) 
    add_case('DQ-AM-R04', 'master', {'parent_asset': 'ORPHAN_PARENT'})
    add_case('DQ-AM-R05', 'master', {'apar_id': 'NON_EXISTENT_SUPPLIER'})
    
    # Depreciation Edge Cases
    add_case('DQ-AD-C01', 'depr', {'asset_id': None})
    add_case('DQ-AD-C02', 'depr', {'depr_book_id': None})
    add_case('DQ-AD-C03', 'depr', {'depr_method': None})
    add_case('DQ-AD-C04', 'depr', {'depr_method': 'LIN', 'lifetime': None})
    add_case('DQ-AD-C05', 'depr', {'depr_method': 'BAL', 'depr_percent': None})
    add_case('DQ-AD-C06', 'depr', {'cap_date_from': None, 'cap_flag': 1})
    add_case('DQ-AD-C07', 'depr', {'depr_period': None})
    
    add_case('DQ-AD-V01', 'depr', {'depr_method': 'INVALID'})
    add_case('DQ-AD-V02', 'depr', {'status': 'X'})
    add_case('DQ-AD-V03', 'depr', {'depr_percent': 150.0, 'depr_method': 'BAL'})
    add_case('DQ-AD-V04', 'depr', {'lifetime': 0, 'depr_method': 'LIN'})
    add_case('DQ-AD-V05', 'depr', {'date_from': '2024-01-01', 'date_to': '2023-01-01'})
    add_case('DQ-AD-V06', 'depr', {'date_from': '2023-01-01', 'cap_date_from': '2022-01-01'})
    add_case('DQ-AD-V07', 'depr', {'depr_percent': -10.0, 'depr_method': 'BAL'})
    add_case('DQ-AD-V08', 'depr', {'last_update': '2099-01-01'})
    
    add_case('DQ-AD-K01', 'depr', {'date_to': '2023-01-01'})
    add_case('DQ-AD-K02', 'depr', {'depr_period': '201901'})
    add_case('DQ-AD-K03', 'depr', {'switch': 'true', 'depr_method': 'LIN'})
    add_case('DQ-AD-K04', 'depr', {'index_id': 'IDX', 'depr_method': 'EXP'})
    add_case('DQ-AD-K05', 'depr', {'res_value': 9999999.0}) 
    add_case('DQ-AD-X03', 'depr', {'cap_date_from': '2015-01-01'}) 
    
    # Balances Edge Cases
    add_case('DQ-AB-C01', 'balances', {'asset_id': None})
    add_case('DQ-AB-C02', 'balances', {'depr_book_id': None})
    add_case('DQ-AB-C03', 'balances', {'trans_type': None})
    add_case('DQ-AB-C04', 'balances', {'total_amount': None})
    add_case('DQ-AB-V01', 'balances', {'trans_type': 'XX'})
    add_case('DQ-AB-V02', 'balances', {'trans_type': 'CA', 'total_amount': 0.0})
    add_case('DQ-AB-V03', 'balances', {'max_trans_date': '2099-01-01'})
    
    def mod_ab_k01(blist):
        for b in blist:
            if b['trans_type'] == 'CA': b['total_amount'] = 1000.0
            if b['trans_type'] == 'ND': b['total_amount'] = -2000.0
        blist[0]['_edge_case'] = 'DQ-AB-K01'
        return blist
    add_case('DQ-AB-K01', 'balances', mod_ab_k01)
    
    def mod_ab_k02(blist):
        new_list = [b for b in blist if b['trans_type'] != 'CA']
        new_list.append({
            'client': new_list[0]['client'], 'asset_id': new_list[0]['asset_id'],
            'depr_book_id': new_list[0]['depr_book_id'], 'trans_type': 'SA',
            'total_amount': 500, 'total_cur_amount': 500,
            'max_trans_date': TODAY.isoformat(), 'min_trans_date': TODAY.isoformat(),
            'transaction_count': 1, '_edge_case': 'DQ-AB-K02'
        })
        return new_list
    add_case('DQ-AB-K02', 'balances', mod_ab_k02)
    
    def mod_ab_k03(blist):
        new_list = [b for b in blist if b['trans_type'] != 'CA']
        new_list[0]['_edge_case'] = 'DQ-AB-K03'
        return new_list
    add_case('DQ-AB-K03', 'balances', mod_ab_k03)
    
    # Trans Flags Edge Cases
    add_case('DQ-AF-X01', 'trans_flags', lambda tlist: tlist + [{
        'client': tlist[0]['client'], 'asset_id': tlist[0]['asset_id'],
        'depr_book_id': tlist[0]['depr_book_id'], 'trans_type': 'SA',
        'trans_date': TODAY.isoformat(), 'at_trans_date': TODAY.isoformat(),
        'fiscal_year': TODAY.year, 'amount': 1000, 'dc_flag': -1,
        'row_type': 'INDIVIDUAL', '_edge_case': 'DQ-AF-X01'
    }])
    
    def mod_af_x02(tlist):
        for t in tlist:
            if t['trans_type'] == 'ND':
                t['trans_date'] = (TODAY + timedelta(days=30)).isoformat()
                t['_edge_case'] = 'DQ-AF-X02'
        return tlist
    add_case('DQ-AF-X02', 'trans_flags', mod_af_x02)
    
    add_case('DQ-AF-X03', 'trans_flags', {'trans_type': 'CA', 'amount': 0.0})
    add_case('DQ-AF-X04', 'trans_flags', {'trans_date': '2099-01-01'})
    
    def mod_af_x05(tlist):
        ca_rows = [t for t in tlist if t['trans_type'] == 'CA']
        if ca_rows:
            ca_row = ca_rows[0]
            ca2 = dict(ca_row)
            ca2['trans_date'] = (date.fromisoformat(ca_row['trans_date']) + timedelta(days=1)).isoformat()
            ca2['_edge_case'] = 'DQ-AF-X05'
            tlist.append(ca2)
        return tlist
    add_case('DQ-AF-X05', 'trans_flags', mod_af_x05)

    # Orphans (Cross-extract integrity edge cases)
    c = clients[0]
    od = make_clean_depr(c, 'ORPHAN_DEPR', make_clean_asset(c, 'ORPHAN_DEPR'), 'FINBOOK')
    od['_edge_case'] = 'DQ-AD-X01'
    depr_rows.append(od)
    
    bal_rows.append({
        'client': c, 'asset_id': 'ORPHAN_BAL', 'depr_book_id': 'FINBOOK',
        'trans_type': 'CA', 'total_amount': 1000.0, 'total_cur_amount': 1000.0,
        'max_trans_date': TODAY.isoformat(), 'min_trans_date': TODAY.isoformat(),
        'transaction_count': 1, '_edge_case': 'DQ-AB-X01'
    })
    
    trans_rows.append({
        'client': c, 'asset_id': 'ORPHAN_TRANS', 'depr_book_id': 'FINBOOK',
        'trans_type': 'CA', 'trans_date': TODAY.isoformat(), 'at_trans_date': TODAY.isoformat(),
        'fiscal_year': TODAY.year, 'amount': 1000.0, 'dc_flag': 1,
        'row_type': 'INDIVIDUAL', '_edge_case': 'DQ-AM-R01'
    })

    # Return DataFrames with guaranteed column order matching SQL
    cols_m = ['client', 'asset_id', 'asset_group', 'description', 'short_info', 'status', 'wf_state', 'cap_date_from', 'cap_period_from', 'date_from', 'date_to', 'apar_id', 'parent_asset', 'grant_flag', 'org_amount', 'org_amt_date', 'base_amount', 'std_amount', 'ins_amount', 'dim_1', 'dim_2', 'dim_3', 'dim_4', 'dim_5', 'dim_6', 'dim_7', 'last_update', 'user_id', '_edge_case']
    cols_d = ['client', 'asset_id', 'depr_book_id', 'status', 'depr_method', 'depr_percent', 'lifetime', 'res_value', 'res_val_flag', 'salvage_amount', 'cap_date_from', 'cap_period_from', 'cap_flag', 'date_from', 'date_to', 'depr_period', 'depr_limit', 'depr_max_perc', 'nbv_rounding', 'switch', 'period_exact', 'frequency', 'index_id', 'index_code', 'repl_amount', 'dim_1', 'dim_2', 'dim_3', 'dim_4', 'dim_5', 'dim_6', 'dim_7', 'last_update', 'user_id', '_edge_case']
    cols_b = ['client', 'asset_id', 'depr_book_id', 'trans_type', 'total_amount', 'total_cur_amount', 'max_trans_date', 'min_trans_date', 'transaction_count', '_edge_case']
    cols_t = ['client', 'asset_id', 'depr_book_id', 'trans_type', 'trans_date', 'at_trans_date', 'fiscal_year', 'amount', 'dc_flag', 'row_type', '_edge_case']
    
    return (
        pd.DataFrame(master_rows)[cols_m],
        pd.DataFrame(depr_rows)[cols_d],
        pd.DataFrame(bal_rows)[cols_b],
        pd.DataFrame(trans_rows)[cols_t]
    )


def main():
    print("Generating Fixed Asset dummy data...\n")
    
    for house, clients, n_base in [('HOC', HOC_CLIENTS, 60), ('HOL', HOL_CLIENTS, 30)]:
        print(f"[{house}] Building dataset...")
        df_master, df_depr, df_bal, df_trans = generate_house_data(house, clients, n_base)
        
        out_master = os.path.join(OUTPUT_DIR, f"asset_master_{house}.csv")
        out_depr   = os.path.join(OUTPUT_DIR, f"asset_depreciation_{house}.csv")
        out_bal    = os.path.join(OUTPUT_DIR, f"asset_balances_{house}.csv")
        out_trans  = os.path.join(OUTPUT_DIR, f"asset_trans_flags_{house}.csv")
        
        df_master.to_csv(out_master, index=False)
        df_depr.to_csv(out_depr, index=False)
        df_bal.to_csv(out_bal, index=False)
        df_trans.to_csv(out_trans, index=False)
        
        print(f"  -> {len(df_master)} master rows")
        print(f"  -> {len(df_depr)} depreciation rows")
        print(f"  -> {len(df_bal)} balance rows")
        print(f"  -> {len(df_trans)} trans flags rows")

    print("\nDone. Files written to ./data/")

if __name__ == '__main__':
    main()
