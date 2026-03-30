"""
Parliament Finance Systems Programme
Asset Group & Configuration Dummy Data Generator
================================================
Generates asset_groups_HOC.csv and asset_groups_HOL.csv based on sql/asset_groups.sql
"""

import os
import random
from datetime import timedelta, date
import pandas as pd

OUTPUT_DIR = 'data'
os.makedirs(OUTPUT_DIR, exist_ok=True)

HOC_CLIENTS = ['CA', 'CF', 'CM']
HOL_CLIENTS = ['LA']

ASSET_GROUPS = {
    'BUILD': {'desc': 'Buildings & Land', 'life': 50, 'method': 'LIN'},
    'EQUIP': {'desc': 'Plant & Equipment', 'life': 10, 'method': 'LIN'},
    'IT':    {'desc': 'IT Hardware & Software', 'life': 5, 'method': 'LIN'},
    'VEH':   {'desc': 'Motor Vehicles', 'life': 7, 'method': 'BAL'},
    'FURN':  {'desc': 'Furniture & Fittings', 'life': 10, 'method': 'LIN'},
    'ART':   {'desc': 'Heritage Assets & Art', 'life': 99, 'method': 'LIN'},
    'INT':   {'desc': 'Intangible Assets', 'life': 3, 'method': 'LIN'},
    'LEASE': {'desc': 'Leasehold Improvements', 'life': 15, 'method': 'LIN'}
}

BOOKS = ['FIN', 'TAX', 'GRP']

def generate_data(house, clients):
    rows = []
    
    for client in clients:
        for group_code, config in ASSET_GROUPS.items():
            # Create 1-2 books per group
            num_books = 1 if group_code == 'ART' else 2
            for i in range(num_books):
                book_id = BOOKS[i]
                
                # Standard Clean Record
                row = {
                    'client': client,
                    'asset_group': group_code,
                    'description': config['desc'],
                    'grp_status': 'N',
                    'depr_method': config['method'],
                    'depr_percent': 25.0 if config['method'] == 'BAL' else 0,
                    'lifetime': config['life'],
                    'res_value': 0,
                    'res_val_flag': '0',
                    'salvage_amount': 0,
                    'depr_start': 'C',
                    'depr_limit': 0,
                    'depr_max_perc': 0,
                    'frequency': 'M',
                    'switch': '0',
                    'period_exact': '1',
                    'nbv_rounding': '1',
                    'index_id': '',
                    'index_code': '',
                    'ins_table_id': 'STD',
                    'insurance_mode': '1',
                    'dim_1': f'CC{random.randint(100, 150)}',
                    'dim_2': '', 'dim_3': '', 'dim_4': '', 'dim_5': '', 'dim_6': '', 'dim_7': '',
                    'grp_last_update': date.today().isoformat(),
                    'grp_user_id': 'SYSTEM',
                    'depr_book_id': book_id,
                    'book_status': 'N',
                    'book_depr_method': '',
                    'book_depr_percent': 0,
                    'book_lifetime': 0,
                    'book_res_value': 0,
                    'book_res_val_flag': '',
                    'book_salvage_amount': 0,
                    'book_depr_start': '',
                    'book_depr_limit': 0,
                    'book_depr_max_perc': 0,
                    'book_frequency': '',
                    'book_switch': '',
                    'book_period_exact': '',
                    'book_nbv_rounding': '',
                    'book_index_id': '',
                    'book_index_code': '',
                    'book_last_update': date.today().isoformat(),
                    'book_user_id': 'SYSTEM'
                }
                rows.append(row)

        # ── DATA QUALITY EDGE CASES ───────────────────────────────────────
        # DQ-AG-C01: Missing asset_group
        bad_row = rows[-1].copy()
        bad_row['asset_group'] = ''
        rows.append(bad_row)
        
        # DQ-AG-C02: Missing description for active group
        bad_row = rows[-2].copy()
        bad_row['asset_group'] = 'GHOST'
        bad_row['description'] = ''
        rows.append(bad_row)
        
        # DQ-AG-V01: Invalid Method
        bad_row = rows[-3].copy()
        bad_row['asset_group'] = 'INVALID_M'
        bad_row['depr_method'] = 'XXX'
        rows.append(bad_row)
        
        # DQ-AG-V04: Depr Percent > 100
        bad_row = rows[-4].copy()
        bad_row['asset_group'] = 'HIGH_PCT'
        bad_row['depr_method'] = 'BAL'
        bad_row['depr_percent'] = 150.0
        rows.append(bad_row)
        
        # DQ-AG-V05: Lifetime <= 0 for LIN
        bad_row = rows[-5].copy()
        bad_row['asset_group'] = 'NO_LIFE'
        bad_row['depr_method'] = 'LIN'
        bad_row['lifetime'] = 0
        rows.append(bad_row)
        
        # DQ-AG-K01: Active book on inactive group
        bad_row = rows[-6].copy()
        bad_row['asset_group'] = 'INACTIVE_G'
        bad_row['grp_status'] = 'C'
        bad_row['book_status'] = 'N'
        rows.append(bad_row)
        
        # DQ-AG-D02: Duplicate description
        bad_row = rows[-7].copy()
        bad_row['asset_group'] = 'DUP_DESC'
        bad_row['description'] = rows[0]['description']
        rows.append(bad_row)

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUTPUT_DIR, f'asset_groups_{house}.csv'), index=False)
    print(f"Generated data/asset_groups_{house}.csv with {len(df)} records.")

if __name__ == "__main__":
    generate_data('HOC', HOC_CLIENTS)
    generate_data('HOL', HOL_CLIENTS)
