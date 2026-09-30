import pandas as pd
from datetime import date


def _os_capitalised_asset_ids(df, frames):
    """
    Asset IDs whose only real capitalisation-type record is OS (historical,
    pre-migration capitalisation, always £0 in aattrans) — i.e. no CA/PC/VN
    transaction with a non-zero amount exists for the asset. House is taken
    from the current chunk of df, since df is always single-house by the
    time a check lambda runs.
    """
    ab = frames.get('asset_balances', pd.DataFrame())
    if ab.empty or 'house' not in ab.columns or df.empty:
        return set()
    house = df['house'].iloc[0]
    h = ab[ab['house'] == house]
    if h.empty:
        return set()
    os_assets = set(h.loc[h['trans_type'] == 'OS', 'asset_id'])
    if not os_assets:
        return set()
    real_cap = h[h['trans_type'].isin(['CA', 'PC', 'VN'])].copy()
    real_cap['total_amount'] = pd.to_numeric(real_cap['total_amount'], errors='coerce').fillna(0)
    real_cap_assets = set(real_cap.loc[real_cap['total_amount'] != 0, 'asset_id'])
    return os_assets - real_cap_assets


def _os_assets_with_real_depreciation(df, frames):
    """
    Asset IDs with a non-zero total ND/ED/FD/SA amount posted in aattrans —
    real depreciation or disposal activity recorded since migration.
    """
    ab = frames.get('asset_balances', pd.DataFrame())
    if ab.empty or 'house' not in ab.columns or df.empty:
        return set()
    house = df['house'].iloc[0]
    h = ab[ab['house'] == house]
    if h.empty:
        return set()
    depr = h[h['trans_type'].isin(['ND', 'ED', 'FD', 'SA'])].copy()
    if depr.empty:
        return set()
    depr['total_amount'] = pd.to_numeric(depr['total_amount'], errors='coerce').fillna(0)
    totals = depr.groupby('asset_id')['total_amount'].sum()
    return set(totals[totals != 0].index)


def get_asset_checks():
    """Returns a list of Asset DQ check definitions."""
    today = pd.Timestamp(date.today())

    checks = [
        # ======================================================================
        # ASSET GROUPS & CONFIGURATION (DQ-AG-)
        # ======================================================================
        ('DQ-AG-C01', 19, 'Asset Groups', 'Completeness', 'Critical',
         'asset_group is null or blank',
         'Flags asset group records with no group code. without a primary key, the record cannot be referenced and all assets linked to it become unresolvable.',
         'Populate asset_group.', 'asset_groups', None, 
         'asset_group IS NULL',
         lambda df: df['asset_group'].isna() | (df['asset_group'] == '')),

        ('DQ-AG-C02', 19, 'Asset Groups', 'Completeness', 'High',
         'description missing for active group',
         'Finds active asset groups with no description. users and administrators cannot identify the group without a human-readable label.',
         'Populate description.', 'asset_groups', None, 
         'grp_status = N AND description IS NULL',
         lambda df: (df['grp_status'] == 'N') & (df['description'].isna() | (df['description'] == ''))),


        ('DQ-AG-V04', 19, 'Asset Groups', 'Validity', 'High',
         'depr_percent exceeds 100%',
         'Flags groups where the depreciation rate exceeds 100%. a rate above 100 is mathematically invalid and would fully depreciate an asset in less than one period.',
         'Correct depr_percent.', 'asset_groups', None, 
         'depr_percent > 100',
         lambda df: pd.to_numeric(df['depr_percent'], errors='coerce') > 100),

        ('DQ-AG-V05', 19, 'Asset Groups', 'Validity', 'High',
         'lifetime <= 0 for LNA method',
         'Finds LNA (net book value divided by lifetime) groups where the useful life is zero or negative. LNA requires a positive lifetime to calculate the periodic depreciation charge.',
         'Correct lifetime.', 'asset_groups', None,
         'lifetime <= 0 AND method = LNA',
         lambda df: (df['depr_method'] == 'LNA') & (pd.to_numeric(df['lifetime'], errors='coerce').fillna(0) <= 0)),

        ('DQ-AG-C03', 19, 'Asset Groups', 'Completeness', 'High',
         'depr_percent missing for LNB method',
         'Finds LNB (capitalised amount multiplied by fixed percentage) groups where the depreciation rate is missing or zero. LNB requires a positive depr_percent to calculate the charge. LNB is only used by HoC.',
         'Populate depr_percent.', 'asset_groups', None,
         'depr_percent <= 0 AND method = LNB',
         lambda df: (df['depr_method'] == 'LNB') & (pd.to_numeric(df['depr_percent'], errors='coerce').fillna(0) <= 0)),

        ('DQ-AG-K01', 19, 'Asset Groups', 'Consistency', 'High',
         'Active book on inactive group',
         'Identifies groups where an active depreciation book exists on an inactive group. if the group is inactive, any asset inheriting its settings cannot be processed.',
         'Align grp_status and book_status.', 'asset_groups', None, 
         'book_status = N AND grp_status != N',
         lambda df: (df['book_status'] == 'N') & (df['grp_status'] != 'N')),

        ('DQ-AG-D02', 19, 'Asset Groups', 'Uniqueness', 'Medium',
         'Duplicate group description',
         'Finds duplicate group descriptions within the same House. while not a hard block, duplicate names create ambiguity when users assign assets to groups.',
         'Review descriptions.', 'asset_groups', None,
         'unique groups with COUNT(*) OVER(PARTITION BY description) > 1',
         lambda df: df['asset_group'].isin(
             df.drop_duplicates(subset=['house', 'asset_group'])
             .loc[lambda x: x.duplicated(subset=['house', 'description'], keep=False)]
             ['asset_group']
         )),

        ('DQ-AG-X01', 19, 'Asset Master', 'Referential Integrity', 'Critical',
         'Asset assigned to non-existent group',
         'Finds asset master records assigned to a group code that does not exist in the asset_groups table. the asset has no valid configuration to inherit.',
         'Correct asset_group in master.', 'asset_master', 'asset_groups', 
         'asset_master.asset_group NOT IN asset_groups',
         lambda df, frames: ~df['asset_group'].str.upper().isin(frames.get('asset_groups', pd.DataFrame())['asset_group'].str.upper()) if 'asset_groups' in frames else pd.Series(False, index=df.index)),


        # ======================================================================
        # ASSET MASTER (DQ-AM-)
        # ======================================================================
        ('DQ-AM-C01', 19, 'Asset Master', 'Completeness', 'Critical',
         'asset_id is null or blank',
         'Flags asset records with no asset ID. without a primary key, the record cannot be migrated or linked to depreciation books and balance transactions.',
         'Populate asset_id.', 'asset_master', None, 
         'asset_id IS NULL OR asset_id = ""',
         lambda df: df['asset_id'].isna() | (df['asset_id'] == '')),
         
        ('DQ-AM-C02', 19, 'Asset Master', 'Completeness', 'High',
         'description is null or blank for active asset',
         'Finds active assets with no description. required for users to identify the asset in the system.',
         'Populate description.', 'asset_master', None, 
         'description IS NULL',
         lambda df: df['description'].isna() | (df['description'] == '')),
         
        ('DQ-AM-C03', 19, 'Asset Master', 'Completeness', 'High',
         'asset_group is null or blank for active asset',
         'Identifies active assets with no asset group. the group drives the depreciation method and GL mapping, so this field is mandatory.',
         'Populate asset_group.', 'asset_master', None, 
         'asset_group IS NULL',
         lambda df: df['asset_group'].isna() | (df['asset_group'] == '')),
         
        ('DQ-AM-C04', 19, 'Asset Master', 'Completeness', 'High',
         'date_from is null for active asset',
         'Flags active assets missing an ownership start date. the system cannot determine when depreciation should begin without this.',
         'Populate date_from.', 'asset_master', None, 
         'date_from IS NULL',
         lambda df: df['date_from'].isna()),
         

        ('DQ-AM-C06', 19, 'Asset Master', 'Completeness', 'Medium',
         'cap_date_from is null where cap_flag is expected to be true',
         'Identifies assets flagged as capitalised but missing the capitalisation date. needed to calculate the correct depreciation start point.',
         'Populate cap_date_from.', 'asset_master', 'asset_depreciation', 
         'cap_date_from IS NULL AND cap_flag=1',
         lambda df, frames: df['cap_date_from'].isna() & df['asset_id'].isin(frames.get('asset_depreciation', pd.DataFrame()).query('cap_flag == 1')['asset_id']) if 'asset_depreciation' in frames else pd.Series(False, index=df.index)),



        ('DQ-AM-V01', 19, 'Asset Master', 'Validity', 'Critical',
         'status not in valid list',
         'Finds assets with a status code outside the valid set (N, P, C, T). invalid status codes are unrecognised by the target system.',
         'Correct status.', 'asset_master', None, 
         'status NOT IN (N,P,C,T)',
         lambda df: ~df['status'].isin(['N', 'P', 'C', 'T'])),


        ('DQ-AM-V03', 19, 'Asset Master', 'Validity', 'High',
         'base_amount is negative',
         'Identifies assets where the base amount is negative. Negative cost is not a valid value for a physical or intangible asset.',
         'Correct base_amount.', 'asset_master', None,
         'base_amount < 0',
         lambda df: (df['status'] != 'C') & (pd.to_numeric(df['base_amount'], errors='coerce').fillna(0) < 0)),

        ('DQ-AM-V04', 19, 'Asset Master', 'Timeliness', 'High',
         'date_from is after date_to',
         'Finds assets where the ownership end date is before the start date. a logical impossibility that indicates a data entry error.',
         'Correct dates.', 'asset_master', None, 
         'date_from > date_to',
         lambda df: pd.to_datetime(df['date_from'], errors='coerce').notna() & pd.to_datetime(df['date_to'], errors='coerce').notna() & (pd.to_datetime(df['date_from'], errors='coerce') > pd.to_datetime(df['date_to'], errors='coerce'))),

        ('DQ-AM-V05', 19, 'Asset Master', 'Timeliness', 'Medium',
         'cap_date_from is before date_from',
         'Flags assets where the capitalisation date is earlier than the ownership start date. an asset cannot be capitalised before it was acquired.',
         'Correct dates.', 'asset_master', None, 
         'cap_date_from < date_from',
         lambda df: pd.to_datetime(df['cap_date_from'], errors='coerce').notna() & pd.to_datetime(df['date_from'], errors='coerce').notna() & (pd.to_datetime(df['cap_date_from'], errors='coerce') < pd.to_datetime(df['date_from'], errors='coerce'))),

        ('DQ-AM-V06', 19, 'Asset Master', 'Timeliness', 'Medium',
         'org_amt_date differs from cap_date_from by > 365 days',
         'Finds assets where the cost recording date differs from the capitalisation date by more than a year. a large gap suggests one of the dates may be incorrect.',
         'Review dates.', 'asset_master', None,
         'status != C AND ABS(org_amt_date - cap_date_from) > 365',
         lambda df: (df['status'] != 'C') & pd.to_datetime(df['org_amt_date'], errors='coerce').notna() & pd.to_datetime(df['cap_date_from'], errors='coerce').notna() & ((pd.to_datetime(df['org_amt_date'], errors='coerce') - pd.to_datetime(df['cap_date_from'], errors='coerce')).dt.days.abs() > 365)),

        ('DQ-AM-T01', 19, 'Asset Master', 'Timeliness', 'Medium',
         'last_update is in the future',
         'Flags assets with a last-update timestamp in the future. indicates a system clock error or bad data entry.',
         'Correct date.', 'asset_master', None, 
         'last_update > TODAY',
         lambda df: pd.to_datetime(df['last_update'], errors='coerce').notna() & (pd.to_datetime(df['last_update'], errors='coerce') > today)),

        ('DQ-AM-K01', 19, 'Asset Master', 'Consistency', 'High',
         'date_to is populated but status is active',
         'Finds assets marked as active but with an ownership end date populated. contradictory fields that need resolution before migration.',
         'Review status.', 'asset_master', None, 
         'date_to IS NOT NULL AND status="N"',
         lambda df: df['date_to'].notna() & (df['status'] == 'N')),


        ('DQ-AM-K03', 19, 'Asset Master', 'Consistency', 'Medium',
         'org_amt_date is null but org_amount populated',
         'Flags assets where a cost amount exists but no cost date. the date is needed to anchor the cost to a financial period.',
         'Populate org_amt_date.', 'asset_master', None, 
         'org_amt_date IS NULL AND org_amount IS NOT NULL',
         lambda df: df['org_amt_date'].isna() & df['org_amount'].notna()),

        ('DQ-AM-K04', 19, 'Asset Master', 'Consistency', 'Medium',
         'grant_flag = 1 but no grant dim value',
         'Finds assets flagged as grant-funded but missing the analytical dimension (dim_1) needed to track grant usage.',
         'Populate dim_1.', 'asset_master', None, 
         'grant_flag = 1 AND dim_1 IS NULL',
         lambda df: (pd.to_numeric(df['grant_flag'], errors='coerce') == 1) & df['dim_1'].isna()),

        ('DQ-AM-D01', 19, 'Asset Master', 'Uniqueness', 'Critical',
         'Duplicate asset_id within client',
         'Detects duplicate asset IDs among non-closed records within the same House. a primary key violation that will block migration.',
         'Resolve duplicate.', 'asset_master', None,
         'status != C AND COUNT > 1',
         lambda df: df.index.isin(
             df[df['status'] != 'C']
             .loc[lambda x: x.duplicated(subset=['house', 'asset_id'], keep=False)]
             .index
         )),


        ('DQ-AM-R01', 19, 'Asset Master', 'Referential Integrity', 'Critical',
         'Transaction with no matching master record',
         'Finds balance transactions referencing an asset ID that does not exist in the asset master. orphaned financial data with no parent record.',
         'Create master record.', 'asset_balances', 'asset_master', 
         'asset_id NOT IN master',
         lambda df, frames: ~df['asset_id'].isin(frames.get('asset_master', pd.DataFrame())['asset_id']) if 'asset_master' in frames else pd.Series(False, index=df.index)),

        ('DQ-AM-R02', 19, 'Asset Master', 'Referential Integrity', 'Critical',
         'Depreciation book with no matching master record',
         'Finds depreciation books referencing an asset ID that does not exist in the asset master. the book cannot be migrated without a parent asset.',
         'Create master record.', 'asset_depreciation', 'asset_master', 
         'asset_id NOT IN master',
         lambda df, frames: ~df['asset_id'].isin(frames.get('asset_master', pd.DataFrame())['asset_id']) if 'asset_master' in frames else pd.Series(False, index=df.index)),


        ('DQ-AM-R04', 19, 'Asset Master', 'Referential Integrity', 'High',
         'parent_asset does not match active asset in extract',
         'Finds non-closed assets referencing a parent asset ID that either does not exist or is closed. If the parent is not migrating, the child will arrive in the new system with a broken hierarchy reference.',
         'Review parent_asset.', 'asset_master', 'asset_master',
         'status != C AND parent_asset NOT IN active master',
         lambda df, frames: (
             (df['status'] != 'C') &
             df['parent_asset'].notna() &
             (df['parent_asset'].astype(str).str.strip() != '') &
             ~df['parent_asset'].isin(
                 frames.get('asset_master', pd.DataFrame())
                 .query('status != "C"')['asset_id']
             )
         ) if 'asset_master' in frames else pd.Series(False, index=df.index)),

        ('DQ-AM-R05', 19, 'Asset Master', 'Referential Integrity', 'Medium',
         'apar_id does not match supplier master',
         'Flags assets linked to a supplier ID that does not exist in the supplier master. the procurement reference is broken.',
         'Review apar_id.', 'asset_master', 'asuheader', 
         'apar_id NOT IN asuheader',
         lambda df, frames: df['apar_id'].notna() & ~df['apar_id'].isin(frames.get('asuheader', pd.DataFrame())['apar_id']) if 'asuheader' in frames else pd.Series(False, index=df.index)),

        # ======================================================================
        # --- ASSET DEPRECIATION (asset_depreciation) ---
        # ======================================================================
        ('DQ-AD-C01', 19, 'Asset Depreciation', 'Completeness', 'Critical',
         'asset_id is null or blank',
         'Flags depreciation book records with no asset ID. without this key, the book cannot be linked to its parent asset.',
         'Populate asset_id.', 'asset_depreciation', None, 
         'asset_id IS NULL',
         lambda df: df['asset_id'].isna() | (df['asset_id'] == '')),

        ('DQ-AD-C02', 19, 'Asset Depreciation', 'Completeness', 'Critical',
         'depr_book_id is null or blank',
         'Finds depreciation books with no book ID. a primary key component; without it, the record cannot be uniquely identified.',
         'Populate depr_book_id.', 'asset_depreciation', None, 
         'depr_book_id IS NULL',
         lambda df: df['depr_book_id'].isna() | (df['depr_book_id'] == '')),

        ('DQ-AD-C03', 19, 'Asset Depreciation', 'Completeness', 'High',
         'depr_method is null or blank',
         'Identifies active depreciation books with no depreciation method. the method is required before any charge can be calculated.',
         'Populate depr_method.', 'asset_depreciation', None, 
         'depr_method IS NULL',
         lambda df: df['depr_method'].isna() | (df['depr_method'] == '')),


        ('DQ-AD-C05', 19, 'Asset Depreciation', 'Completeness', 'High',
         'depr_percent is null or zero for LNB',
         'Flags LNB (capitalised amount multiplied by fixed percentage) books with no depreciation rate. LNB requires a positive depr_percent to calculate the charge. LNB is only used by HoC.',
         'Populate depr_percent.', 'asset_depreciation', None,
         'depr_percent <= 0 AND method = LNB',
         lambda df: (df['depr_method'] == 'LNB') & (pd.to_numeric(df['depr_percent'], errors='coerce').fillna(0) <= 0)),

        ('DQ-AD-C06', 19, 'Asset Depreciation', 'Completeness', 'Medium',
         'cap_date_from is null but cap_flag = 1',
         'Finds capitalised depreciation books missing the capitalisation date. needed to determine when depreciation should start.',
         'Populate cap_date_from.', 'asset_depreciation', None, 
         'cap_date_from IS NULL AND cap_flag=1',
         lambda df: df['cap_date_from'].isna() & (pd.to_numeric(df['cap_flag'], errors='coerce') == 1)),

        ('DQ-AD-C07', 19, 'Asset Depreciation', 'Completeness', 'Medium',
         'depr_period is null for active book',
         'Identifies books where the last depreciation period is null. suggests depreciation has never been run for this asset.',
         'Review depr_period.', 'asset_depreciation', None, 
         'depr_period IS NULL',
         lambda df: df['depr_period'].isna()),


        ('DQ-AD-V02', 19, 'Asset Depreciation', 'Validity', 'Critical',
         'status invalid',
         'Flags depreciation books with an unrecognised status code. only N, P, C, and T are valid.',
         'Correct status.', 'asset_depreciation', None, 
         'status NOT IN (N,P,C,T)',
         lambda df: ~df['status'].isin(['N', 'P', 'C', 'T'])),

        ('DQ-AD-V03', 19, 'Asset Depreciation', 'Validity', 'High',
         'depr_percent > 100',
         'Finds books where the depreciation rate exceeds 100%. mathematically invalid for any depreciation calculation.',
         'Correct depr_percent.', 'asset_depreciation', None,
         'status != C AND depr_percent > 100',
         lambda df: (df['status'] != 'C') & (pd.to_numeric(df['depr_percent'], errors='coerce').fillna(0) > 100)),

        ('DQ-AD-V04', 19, 'Asset Depreciation', 'Validity', 'High',
         'lifetime <= 0 for LNA method',
         'Finds LNA (net book value divided by lifetime) books where lifetime is zero or negative. LNA requires a positive lifetime to calculate the periodic charge. NOD assets have no depreciation. LNB uses a percentage rate, not lifetime. MAN is calculated manually.',
         'Correct lifetime.', 'asset_depreciation', None,
         'lifetime <= 0 AND method = LNA',
         lambda df: (df['depr_method'] == 'LNA') & (pd.to_numeric(df['lifetime'], errors='coerce').fillna(0) <= 0)),

        ('DQ-AD-V05', 19, 'Asset Depreciation', 'Timeliness', 'High',
         'date_from is after date_to',
         'Finds books where the ownership end date is before the start date. a logical impossibility indicating a data entry error.',
         'Correct dates.', 'asset_depreciation', None,
         'status != C AND date_from > date_to',
         lambda df: (df['status'] != 'C') & pd.to_datetime(df['date_from'], errors='coerce').notna() & pd.to_datetime(df['date_to'], errors='coerce').notna() & (pd.to_datetime(df['date_from'], errors='coerce') > pd.to_datetime(df['date_to'], errors='coerce'))),

        ('DQ-AD-V06', 19, 'Asset Depreciation', 'Timeliness', 'Medium',
         'cap_date_from is before date_from',
         'Flags books where the capitalisation date is before the ownership start date. an asset cannot be capitalised before it was acquired.',
         'Correct dates.', 'asset_depreciation', None, 
         'cap_date_from < date_from',
         lambda df: pd.to_datetime(df['cap_date_from'], errors='coerce').notna() & pd.to_datetime(df['date_from'], errors='coerce').notna() & (pd.to_datetime(df['cap_date_from'], errors='coerce') < pd.to_datetime(df['date_from'], errors='coerce'))),

        ('DQ-AD-V07', 19, 'Asset Depreciation', 'Validity', 'Medium',
         'depr_percent is negative',
         'Identifies books with a negative depreciation rate. a negative rate is mathematically invalid.',
         'Correct depr_percent.', 'asset_depreciation', None, 
         'depr_percent < 0',
         lambda df: pd.to_numeric(df['depr_percent'], errors='coerce').fillna(0) < 0),

        ('DQ-AD-T01', 19, 'Asset Depreciation', 'Timeliness', 'Medium',
         'last_update is in the future',
         'Flags books with a last-update timestamp in the future. indicates a system clock or data entry error.',
         'Correct date.', 'asset_depreciation', None, 
         'last_update > TODAY',
         lambda df: pd.to_datetime(df['last_update'], errors='coerce').notna() & (pd.to_datetime(df['last_update'], errors='coerce') > today)),

        ('DQ-AD-K01', 19, 'Asset Depreciation', 'Consistency', 'High',
         'date_to is populated but status is N',
         'Finds active depreciation books with an ownership end date populated. contradictory; an active book should not have a close date.',
         'Review status.', 'asset_depreciation', None, 
         'date_to IS NOT NULL AND status=N',
         lambda df: df['date_to'].notna() & (df['status'] == 'N')),




        ('DQ-AD-K05', 19, 'Asset Depreciation', 'Consistency', 'Medium',
         'res_value > base_amount on master',
         'Flags books where the residual value exceeds the asset base amount. a residual cannot be greater than what the asset cost to acquire.',
         'Review res_value.', 'asset_depreciation', 'asset_master',
         'status != C AND res_value > base_amount',
         lambda df, frames: (df['status'] != 'C') & (pd.to_numeric(df['res_value'], errors='coerce').fillna(0) > pd.to_numeric(df['asset_id'].map(frames.get('asset_master', pd.DataFrame()).drop_duplicates('asset_id').set_index('asset_id')['base_amount']), errors='coerce').fillna(float('inf'))) if 'asset_master' in frames else pd.Series(False, index=df.index)),

        ('DQ-AD-D01', 19, 'Asset Depreciation', 'Uniqueness', 'Critical',
         'Duplicate composite key',
         'Detects duplicate (client, asset_id, depr_book_id) keys among non-closed books. a primary key violation that will block migration.',
         'Resolve duplicate.', 'asset_depreciation', None,
         'status != C AND COUNT > 1',
         lambda df: df.index.isin(
             df[df['status'] != 'C']
             .loc[lambda x: x.duplicated(subset=['client', 'asset_id', 'depr_book_id'], keep=False)]
             .index
         )),

        ('DQ-AD-X01', 19, 'Asset Depreciation', 'Referential Integrity', 'Critical',
         'Orphaned depreciation book',
         'Finds depreciation books with no matching record in the asset master. an orphaned book that cannot be migrated.',
         'Create master record.', 'asset_depreciation', 'asset_master', 
         'asset_id NOT IN master',
         lambda df, frames: ~df['asset_id'].isin(frames.get('asset_master', pd.DataFrame())['asset_id']) if 'asset_master' in frames else pd.Series(False, index=df.index)),

        ('DQ-AD-X02', 19, 'Asset Depreciation', 'Referential Integrity', 'High',
         'Active asset with no depreciation book',
         'Identifies active assets with no depreciation book. without a book, the system cannot calculate or post any depreciation charges.',
         'Create depr book.', 'asset_master', 'asset_depreciation', 
         'asset_id NOT IN depr',
         lambda df, frames: (df['status'] == 'N') & ~df['asset_id'].isin(frames.get('asset_depreciation', pd.DataFrame())['asset_id']) if 'asset_depreciation' in frames else pd.Series(False, index=df.index)),

        ('DQ-AD-X03', 19, 'Asset Depreciation', 'Referential Integrity', 'High',
         'cap_date_from mismatch',
         'Finds books where the capitalisation date disagrees with the asset master record. the two tables must be consistent for accurate depreciation.',
         'Align dates.', 'asset_depreciation', 'asset_master',
         'status NOT IN (C,T) AND master.status NOT IN (C,T) AND depr.cap_date_from != master.cap_date_from',
         lambda df, frames: (~df['status'].isin(['C', 'T'])) & (~df['asset_id'].map(frames.get('asset_master', pd.DataFrame()).drop_duplicates('asset_id').set_index('asset_id')['status']).isin(['C', 'T'])) & (df['cap_date_from'] != df['asset_id'].map(frames.get('asset_master', pd.DataFrame()).drop_duplicates('asset_id').set_index('asset_id')['cap_date_from'])) if 'asset_master' in frames else pd.Series(False, index=df.index)),

        ('DQ-AD-X04', 19, 'Asset Depreciation', 'Referential Integrity', 'Medium',
         'res_value > org_amount',
         'Placeholder check. logic covered by DQ-AD-K05.',
         'Review values.', 'asset_depreciation', 'asset_master', 
         'res_value > org_amount',
         lambda df: pd.Series(False, index=df.index)),

        ('DQ-AD-X05', 19, 'Asset Depreciation', 'Referential Integrity', 'High',
         'Active book with no transactions',
         'Finds active depreciation books with no associated balance transactions. the asset appears to have never been capitalised or posted.',
         'Review activity.', 'asset_depreciation', 'asset_balances',
         'status != C AND key NOT IN balances',
         lambda df, frames: (df['status'] != 'C') & ~df.set_index(['house', 'asset_id', 'depr_book_id']).index.isin(frames.get('asset_balances', pd.DataFrame()).set_index(['house', 'asset_id', 'depr_book_id']).index if 'asset_balances' in frames else [])),

        # ======================================================================
        # --- ASSET BALANCES (asset_balances) ---
        # ======================================================================
        ('DQ-AB-C01', 19, 'Asset Balances', 'Completeness', 'Critical',
         'asset_id is null',
         'Flags balance records with no asset ID. without this key, the transaction cannot be linked to any asset.',
         'Populate asset_id.', 'asset_balances', None, 
         'asset_id IS NULL',
         lambda df: df['asset_id'].isna() | (df['asset_id'] == '')),

        ('DQ-AB-C02', 19, 'Asset Balances', 'Completeness', 'Critical',
         'depr_book_id is null',
         'Finds balance records with no depreciation book ID. required to attribute the balance to the correct depreciation stream.',
         'Populate depr_book_id.', 'asset_balances', None, 
         'depr_book_id IS NULL',
         lambda df: df['depr_book_id'].isna() | (df['depr_book_id'] == '')),

        ('DQ-AB-C03', 19, 'Asset Balances', 'Completeness', 'Critical',
         'trans_type is null',
         'Identifies balance records with no transaction type. the type determines how the amount is treated in NBV calculations.',
         'Populate trans_type.', 'asset_balances', None, 
         'trans_type IS NULL',
         lambda df: df['trans_type'].isna() | (df['trans_type'] == '')),

        ('DQ-AB-C04', 19, 'Asset Balances', 'Completeness', 'High',
         'total_amount is null',
         'Flags balance records with no total amount. a financial record without a value cannot contribute to any calculation.',
         'Review aggregation.', 'asset_balances', None, 
         'total_amount IS NULL',
         lambda df: df['total_amount'].isna()),


        ('DQ-AB-V02', 19, 'Asset Balances', 'Validity', 'High',
         'total_amount = 0 for CA',
         'Finds capitalisation (CA) records with a zero amount. a zero-cost capitalisation adds nothing to the asset net book value.',
         'Review amount.', 'asset_balances', None, 
         'trans_type=CA AND total_amount=0',
         lambda df: (df['trans_type'] == 'CA') & (pd.to_numeric(df['total_amount'], errors='coerce').fillna(0) == 0)),

        ('DQ-AB-V03', 19, 'Asset Balances', 'Timeliness', 'Medium',
         'max_trans_date in future',
         'Flags balance records with a maximum transaction date in the future. indicates a data entry or system clock error.',
         'Correct date.', 'asset_balances', None, 
         'max_trans_date > TODAY',
         lambda df: pd.to_datetime(df.get('max_trans_date', pd.Series(index=df.index)), errors='coerce').notna() & (pd.to_datetime(df.get('max_trans_date', pd.Series(index=df.index)), errors='coerce') > today)),


        ('DQ-AB-K02', 19, 'Asset Balances', 'Consistency', 'High',
         'Disposal without capitalisation',
         'Finds assets that have a disposal (SA) transaction but no capitalisation (CA or OS). OS indicates an asset capitalised in a prior system before migration and is treated as equivalent to CA.',
         'Review history.', 'asset_balances', None,
         'SA exists, CA/OS missing',
         lambda df: df.index.isin(df.groupby(['house', 'asset_id', 'depr_book_id']).filter(lambda g: ('SA' in g['trans_type'].values) and not g['trans_type'].isin(['CA', 'OS']).any()).index)),

        ('DQ-AB-K03', 19, 'Asset Balances', 'Consistency', 'High',
         'Depreciation without capitalisation',
         'Identifies assets with depreciation transactions (ND, ED, FD) but no capitalisation (CA or OS). OS indicates an asset capitalised in a prior system before migration and is treated as equivalent to CA. For HoL, TC is also treated as a capitalisation type.',
         'Review history.', 'asset_balances', None,
         'Depr exists, CA/OS/TC(HoL) missing',
         lambda df: df.index.isin(df.groupby(['house', 'asset_id', 'depr_book_id']).filter(lambda g: g['trans_type'].isin(['ND','ED','FD']).any() and not g['trans_type'].isin(['CA', 'OS'] + (['TC'] if (g['house'] == 'HOL').all() else [])).any()).index)),


        ('DQ-AB-X01', 19, 'Asset Balances', 'Referential Integrity', 'Critical',
         'Orphaned balance',
         'Finds balance records referencing an asset ID with no matching master record. orphaned financial data.',
         'Create master.', 'asset_balances', 'asset_master', 
         'asset_id NOT IN master',
         lambda df, frames: ~df['asset_id'].isin(frames.get('asset_master', pd.DataFrame())['asset_id']) if 'asset_master' in frames else pd.Series(False, index=df.index)),

        ('DQ-AB-X02', 19, 'Asset Balances', 'Referential Integrity', 'Critical',
         'Balance for missing book',
         'Finds balance records referencing a depreciation book that does not exist. the balance cannot be attributed to a valid book.',
         'Create depr book.', 'asset_balances', 'asset_depreciation', 
         'key NOT IN depr',
         lambda df, frames: ~df.set_index(['house', 'asset_id', 'depr_book_id']).index.isin(frames.get('asset_depreciation', pd.DataFrame()).set_index(['house', 'asset_id', 'depr_book_id']).index if 'asset_depreciation' in frames else []),),

        ('DQ-AB-X03', 19, 'Asset Balances', 'Referential Integrity', 'High',
         'Active asset with no balances',
         'Identifies active assets with no balance transactions. the asset has never been capitalised and has no financial history.',
         'Review history.', 'asset_master', 'asset_balances', 
         'asset_id NOT IN balances',
         lambda df, frames: (df['status'] == 'N') & ~df['asset_id'].isin(frames.get('asset_balances', pd.DataFrame())['asset_id']) if 'asset_balances' in frames else pd.Series(False, index=df.index)),



        # ======================================================================
        # --- ASSET TRANS FLAGS (asset_trans_flags) ---
        # ======================================================================
        ('DQ-AF-X01', 19, 'Asset Trans Flags', 'Referential Integrity', 'High',
         'SA transaction on active asset',
         'Finds disposal (SA) transactions against assets still marked as active in the master. the asset should have been closed when the disposal was posted.',
         'Update master.', 'asset_trans_flags', 'asset_master', 
         'trans_type=SA AND master.status=N',
         lambda df, frames: (df['trans_type'] == 'SA') & df['asset_id'].isin(frames.get('asset_master', pd.DataFrame()).query('status == "N"')['asset_id']) if 'asset_master' in frames else pd.Series(False, index=df.index)),

        ('DQ-AF-X02', 19, 'Asset Trans Flags', 'Referential Integrity', 'High',
         'Depreciation posted after date_to',
         'Identifies depreciation transactions (ND, ED, FD) posted after the asset ownership end date. charges should not be posted once the asset has been disposed of.',
         'Review dates.', 'asset_trans_flags', 'asset_master', 
         'trans_type IN (ND,ED,FD) AND trans_date > master.date_to',
         lambda df, frames: (df['trans_type'].isin(['ND', 'ED', 'FD'])) & pd.to_datetime(df['trans_date'], errors='coerce').notna() & (pd.to_datetime(df['trans_date'], errors='coerce') > pd.to_datetime(df['asset_id'].map(frames.get('asset_master', pd.DataFrame()).drop_duplicates('asset_id').set_index('asset_id')['date_to']), errors='coerce')) if 'asset_master' in frames else pd.Series(False, index=df.index)),

        ('DQ-AF-X03', 19, 'Asset Trans Flags', 'Consistency', 'High',
         'CA transaction with zero amount',
         'Flags capitalisation (CA) transactions with a zero amount. a zero-cost capitalisation has no financial effect and is likely a data error.',
         'Review amount.', 'asset_trans_flags', None, 
         'trans_type=CA AND amount=0',
         lambda df: (df['trans_type'] == 'CA') & (pd.to_numeric(df['amount'], errors='coerce').fillna(0) == 0)),

        ('DQ-AF-X04', 19, 'Asset Trans Flags', 'Timeliness', 'High',
         'trans_date in future',
         'Finds transactions with a date in the future. indicates a data entry or system clock error.',
         'Correct trans_date.', 'asset_trans_flags', None,
         'trans_date > TODAY',
         lambda df: pd.to_datetime(df['trans_date'], errors='coerce').notna() & (pd.to_datetime(df['trans_date'], errors='coerce') > today)),


        # ======================================================================
        # --- OS (LEGACY PRE-MIGRATION CAPITALISATION) ASSESSMENT (DQ-OS-) ---
        # Added September 2026. OS is a historical capitalisation record for
        # assets migrated from the predecessor system — confirmed always £0
        # in aattrans. These three checks test where, if anywhere, an
        # OS-capitalised asset's real original cost is actually recorded.
        # ======================================================================
        ('DQ-OS-C01', 19, 'Asset Master', 'Completeness', 'High',
         'OS-capitalised asset with no cost recorded anywhere',
         'Every asset capitalised through the historical OS migration record must have its original cost recorded somewhere in Unit4. The OS transaction itself always carries a zero amount, so the cost must exist elsewhere if it exists at all. Without it, this asset has no recoverable cost basis and cannot be valued for migration.',
         'Confirm with the source system owner whether the original cost exists elsewhere. If not, treat this asset as having no captured financial value.', 'asset_master', 'asset_balances',
         'OS-only capitalised AND org_amount IS NULL/0',
         lambda df, frames: (df['status'] == 'N') & df['asset_id'].isin(_os_capitalised_asset_ids(df, frames)) & (pd.to_numeric(df['org_amount'], errors='coerce').fillna(0) == 0)),

        ('DQ-OS-K01', 19, 'Asset Master', 'Consistency', 'Critical',
         'OS-capitalised asset has real depreciation but no recorded cost',
         'An asset with real depreciation, extraordinary depreciation, final depreciation, or disposal activity must have a cost basis somewhere to justify that activity. This asset was capitalised only through the OS migration record, which carries a zero amount, and has no populated cost on the asset master either. Depreciation is being posted against a value this dataset cannot see.',
         "Trace the cost basis actually used to calculate this asset's depreciation and confirm where it is held.", 'asset_master', 'asset_balances',
         'OS-only capitalised AND real ND/ED/FD/SA activity AND org_amount IS NULL/0',
         lambda df, frames: (df['status'] == 'N') & df['asset_id'].isin(_os_capitalised_asset_ids(df, frames)) & df['asset_id'].isin(_os_assets_with_real_depreciation(df, frames)) & (pd.to_numeric(df['org_amount'], errors='coerce').fillna(0) == 0)),

        ('DQ-OS-K02', 19, 'Asset Master', 'Consistency', 'Medium',
         'OS-capitalised asset has a recorded cost that never reached the transaction history',
         'An OS-capitalised asset with a populated org_amount on the asset master has a real recorded cost. That cost was never reflected as a transaction in the transaction history, where the OS record itself always shows zero. Migration valuation for this asset should use the master record, not the transaction history.',
         'Use org_amount on the asset master as the cost basis for this asset instead of the transaction history.', 'asset_master', 'asset_balances',
         'OS-only capitalised AND org_amount > 0',
         lambda df, frames: (df['status'] == 'N') & df['asset_id'].isin(_os_capitalised_asset_ids(df, frames)) & (pd.to_numeric(df['org_amount'], errors='coerce').fillna(0) > 0)),


        # ======================================================================
        # --- NET BOOK VALUE (asset_nbv) — HoC only (DQ-NBV-) ---
        # asset_nbv is built by dashboard/core/asset_nbv.py: one row per asset,
        # CURR and HIST side by side, using the confirmed account rule. Each
        # check's population lives in nbv_population(), not in the lambda.
        # ======================================================================
        ('DQ-NBV-C01', 19, 'Asset NBV', 'Completeness', 'High',
         'Active asset has transactions but no NBV account',
         'Every active asset with transaction history must post to a cost account (starting 1, ending 00) or an accumulated depreciation account (starting 1, ending 15). Without one, the asset has no net book value that can be migrated, even though it has financial activity.',
         'Identify which accounts this asset posts to and confirm with the asset team where its cost and depreciation are held.', 'asset_nbv', None,
         "no account LIKE '1%00' OR '1%15' for the asset",
         lambda df: ~df['has_nbv_account'].astype(bool)),

        ('DQ-NBV-V01', 19, 'Asset NBV', 'Validity', 'High',
         'Negative NBV in the CURR or HIST book',
         'Net book value must not fall below zero. A negative NBV means accumulated depreciation exceeds the recorded cost, which would carry a negative asset balance into the new system.',
         'Review the depreciation charged against this asset and correct any over-depreciation or missing cost.', 'asset_nbv', None,
         'curr_nbv < -1 OR hist_nbv < -1',
         lambda df: (pd.to_numeric(df['curr_nbv'], errors='coerce').fillna(0) < -1) | (pd.to_numeric(df['hist_nbv'], errors='coerce').fillna(0) < -1)),

        ('DQ-NBV-K01', 19, 'Asset NBV', 'Consistency', 'Medium',
         'Active asset with zero NBV and no disposal',
         'An active asset with no remaining value and no disposal is fully depreciated but still on the register. Each one needs a decision on whether it is still in use or should be disposed of before migration.',
         'Send to the asset team to confirm whether the asset is still in use or should be formally disposed.', 'asset_nbv', None,
         'ABS(curr_nbv) < 1 AND no SA transaction',
         lambda df: pd.to_numeric(df['curr_nbv'], errors='coerce').fillna(0).abs() < 1),

        ('DQ-NBV-K02', 19, 'Asset NBV', 'Consistency', 'High',
         'Revaluation reserve does not reconcile to HIST minus CURR NBV',
         'The revaluation reserve (account 70000) must equal the historical book NBV minus the current book NBV for every asset. A difference means the two depreciation books and the reserve disagree, so at least one of the three figures migrated would be wrong.',
         'Reconcile the revaluation reserve postings against the CURR and HIST book values for this asset.', 'asset_nbv', None,
         'ABS(reserve_70000 - (hist_nbv - curr_nbv)) > 1',
         lambda df: pd.to_numeric(df['reval_variance'], errors='coerce').fillna(0).abs() > 1),

        ('DQ-NBV-K03', 19, 'Asset NBV', 'Consistency', 'Medium',
         "Asset's postings do not net to zero across accounts",
         "Every fixed asset posting has an equal and opposite entry, so an asset's postings across all accounts must net to zero in each book. A non-zero total means one side of a posting is missing from the asset module.",
         'Trace the unbalanced postings for this asset and confirm the missing side of the entry.', 'asset_nbv', None,
         'ABS(SUM(amount) across all accounts) > 1 in CURR or HIST',
         lambda df: (pd.to_numeric(df['curr_net_all_accounts'], errors='coerce').fillna(0).abs() > 1) | (pd.to_numeric(df['hist_net_all_accounts'], errors='coerce').fillna(0).abs() > 1)),

        ('DQ-NBV-K04', 19, 'Asset NBV', 'Consistency', 'Medium',
         'Disposal posted but NBV not cleared',
         'A disposal must remove the remaining value of the asset. An asset with a disposal transaction that still carries a net book value will migrate with a balance for something no longer owned.',
         'Confirm whether this was a partial disposal. If not, correct the disposal posting.', 'asset_nbv', None,
         'SA transaction exists AND ABS(curr_nbv) >= 1',
         lambda df: pd.to_numeric(df['curr_nbv'], errors='coerce').fillna(0).abs() >= 1),

        ('DQ-NBV-K05', 19, 'Asset NBV', 'Consistency', 'Low',
         'Depreciating asset has no accumulated depreciation',
         'An asset set to depreciate (method LNA or LNB) with a recorded cost must build up accumulated depreciation over time. None at all means the depreciation run has not been applied to it, unless it was capitalised very recently.',
         'Check the capitalisation date and confirm whether depreciation should have started.', 'asset_nbv', None,
         'curr_depr_method IN (LNA, LNB) AND curr_cost > 0 AND curr_depreciation = 0',
         lambda df: pd.to_numeric(df['curr_depreciation'], errors='coerce').fillna(0).abs() < 1),

    ]
    return checks
