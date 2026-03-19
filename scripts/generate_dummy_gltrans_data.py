import pandas as pd
import random

random.seed(42)

# ============================================================
# CONFIGURATION
# Mirrors the attribute_ids used in generate_gl_dummy_data.py
# ============================================================

CLIENTS = ['HOC', 'HOL']

# Active dimension values - mirrors what was generated in gl_dimension_values.csv
# In real data these come from agldimvalue
CC_CODES  = [f"CC{str(i).zfill(3)}" for i in range(100, 130)]
SUBJ_CODES = [f"S{str(i).zfill(3)}" for i in range(100, 125)]
ANL1_CODES = [f"A1{str(i).zfill(2)}" for i in range(10, 30)]
ANL2_CODES = [f"A2{str(i).zfill(2)}" for i in range(10, 25)]


# ============================================================
# GENERATE DISTINCT DIMENSION COMBINATIONS — agltransact
# ============================================================

def generate_agltransact_dimensions(n=120):

    rows = []
    seen = set()  # track combinations to ensure distinct rows

    attempts = 0
    while len(rows) < n and attempts < 10000:
        attempts += 1

        client = random.choice(CLIENTS)
        dim_1 = random.choice(CC_CODES)
        dim_2 = random.choice(SUBJ_CODES)
        dim_3 = random.choice(ANL1_CODES) if random.random() > 0.4 else None
        dim_4 = random.choice(ANL2_CODES) if random.random() > 0.6 else None
        dim_5 = None
        dim_6 = None
        dim_7 = None

        key = (client, dim_1, dim_2, dim_3, dim_4)
        if key in seen:
            continue

        seen.add(key)
        rows.append({
            'client': client,
            'dim_1': dim_1,
            'dim_2': dim_2,
            'dim_3': dim_3,
            'dim_4': dim_4,
            'dim_5': dim_5,
            'dim_6': dim_6,
            'dim_7': dim_7
        })

    # --- Edge cases ---
    # These deliberately reference dimension values that are
    # inactive or non-existent in gl_dimension_values.csv
    # to trigger the backward compatibility tests

    edge_cases = [

        # BACKWARD COMPAT: dim_1 references inactive dimension value EC_D010
        {'client': 'HOC', 'dim_1': 'EC_D010', 'dim_2': 'S100',
         'dim_3': None, 'dim_4': None,
         'dim_5': None, 'dim_6': None, 'dim_7': None},

        # BACKWARD COMPAT: dim_1 references non-existent dimension value
        {'client': 'HOC', 'dim_1': 'CC_GHOST', 'dim_2': 'S100',
         'dim_3': None, 'dim_4': None,
         'dim_5': None, 'dim_6': None, 'dim_7': None},

        # BACKWARD COMPAT: dim_2 references non-existent subjective
        {'client': 'HOL', 'dim_1': 'CC100', 'dim_2': 'S_GHOST',
         'dim_3': None, 'dim_4': None,
         'dim_5': None, 'dim_6': None, 'dim_7': None},

        # BACKWARD COMPAT: Both dim_1 and dim_2 non-existent
        {'client': 'HOC', 'dim_1': 'CC_MISSING', 'dim_2': 'S_MISSING',
         'dim_3': None, 'dim_4': None,
         'dim_5': None, 'dim_6': None, 'dim_7': None},
    ]

    return pd.DataFrame(rows + edge_cases)


# ============================================================
# GENERATE AND SAVE
# ============================================================

df_agltransact = generate_agltransact_dimensions(n=120)

df_agltransact.to_csv('gl_transact_dimensions.csv', index=False)

print(f"agltransact dimensions: {len(df_agltransact)} rows -> gl_transact_dimensions.csv")

print("\n--- Split by client ---")
print(df_agltransact['client'].value_counts())

print("\n--- Null counts per dimension column ---")
print(df_agltransact.isnull().sum())

print("\n--- Edge cases ---")
ec = df_agltransact[
    df_agltransact['dim_1'].str.contains('GHOST|MISSING|EC_', na=False) |
    df_agltransact['dim_2'].str.contains('GHOST|MISSING|EC_', na=False)
]
print(ec)