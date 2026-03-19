import pandas as pd
from datetime import date

def get_asset_checks():
    """Returns a list of Fixed Asset DQ check definitions."""
    today = pd.Timestamp(date.today())

    checks = [
        # ======================================================================
        # --- COMPLETENESS (Active assets only — status = 'N') ---
        # ======================================================================

        ('AT_MISSING_DESCRIPTION', 19, 'Asset Register', 'Completeness', 'High',
         'Active asset is missing a description',
         'Assets with no description cannot be reviewed or mapped by the business during migration.',
         'Populate asset_register.description for all active assets.',
         'asset_register', None,
         'asset_register.description IS NULL WHERE status = "N"',
         lambda df: df['description'].isna()),

        ('AT_MISSING_ASSET_GROUP', 19, 'Asset Register', 'Completeness', 'Critical',
         'Active asset has no asset group assigned',
         'All assets must belong to a group — asset groups drive depreciation rules in the new system.',
         'Assign an asset group to all active assets.',
         'asset_register', None,
         'asset_register.asset_group IS NULL WHERE status = "N"',
         lambda df: df['asset_group'].isna()),

        ('AT_MISSING_CAP_DATE', 19, 'Asset Register', 'Completeness', 'High',
         'Active asset has no capitalisation date',
         'Assets without a capitalisation date cannot have depreciation correctly calculated in the new system.',
         'Confirm capitalisation date with Finance and populate asset_register.cap_date_from.',
         'asset_register', None,
         'asset_register.cap_date_from IS NULL WHERE status = "N"',
         lambda df: df['cap_date_from'].isna()),

        ('AT_MISSING_BASE_AMOUNT', 19, 'Asset Register', 'Completeness', 'Critical',
         'Active asset has no base (depreciable) amount',
         'Depreciable cost must be populated for any asset subject to depreciation calculations.',
         'Review asset and populate asset_register.base_amount.',
         'asset_register', None,
         'asset_register.base_amount IS NULL WHERE status = "N"',
         lambda df: df['base_amount'].isna()),

        ('AT_MISSING_ORG_AMOUNT', 19, 'Asset Register', 'Completeness', 'Medium',
         'Active asset has no original (historical cost) amount',
         'Original cost should always be populated — a blank value indicates incomplete asset setup.',
         'Investigate asset and populate asset_register.org_amount from procurement records.',
         'asset_register', None,
         'asset_register.org_amount IS NULL WHERE status = "N"',
         lambda df: df['org_amount'].isna()),

        ('AT_MISSING_DIM1', 19, 'Asset Register', 'Completeness', 'High',
         'Active asset has no cost centre (dim_1) assigned',
         'Assets must have a cost centre so that depreciation can be posted correctly in the new system.',
         'Assign a valid cost centre to all active assets before migration.',
         'asset_register', None,
         'asset_register.dim_1 IS NULL WHERE status = "N"',
         lambda df: df['dim_1'].isna()),

        # ======================================================================
        # --- VALIDITY (Active assets only) ---
        # ======================================================================

        ('AT_DATE_FROM_AFTER_DATE_TO', 19, 'Asset Register', 'Validity', 'High',
         'Asset date_from is after date_to — invalid ownership period',
         'Ownership cannot end before it starts; this indicates a data entry error.',
         'Correct asset_register.date_from or date_to to reflect the actual ownership period.',
         'asset_register', None,
         'asset_register.date_from > asset_register.date_to',
         lambda df: df['date_from'].notna() & df['date_to'].notna() & (
             pd.to_datetime(df['date_from'], errors='coerce') >
             pd.to_datetime(df['date_to'],   errors='coerce')
         )),

        ('AT_CAP_BEFORE_DATE_FROM', 19, 'Asset Register', 'Validity', 'Medium',
         'Asset was capitalised before the ownership start date',
         'Capitalisation date preceding ownership start is likely a data entry error.',
         'Verify the capitalisation and ownership dates against source documentation.',
         'asset_register', None,
         'asset_register.cap_date_from < asset_register.date_from',
         lambda df: df['cap_date_from'].notna() & df['date_from'].notna() & (
             pd.to_datetime(df['cap_date_from'], errors='coerce') <
             pd.to_datetime(df['date_from'],     errors='coerce')
         )),

        ('AT_BASE_EXCEEDS_ORG', 19, 'Asset Register', 'Validity', 'Medium',
         'Depreciable base amount exceeds original cost',
         'Base amount should not exceed original cost — may be valid after revaluation but warrants review.',
         'Confirm with Finance whether a revaluation explains the difference; correct if in error.',
         'asset_register', None,
         'asset_register.base_amount > asset_register.org_amount',
         lambda df: df['base_amount'].notna() & df['org_amount'].notna() & (
             df['base_amount'] > df['org_amount']
         )),

        ('AT_NEGATIVE_BASE_AMOUNT', 19, 'Asset Register', 'Validity', 'High',
         'Depreciable base amount is negative',
         'A negative depreciable cost is not valid and will cause depreciation calculation errors.',
         'Investigate and correct asset_register.base_amount.',
         'asset_register', None,
         'asset_register.base_amount < 0',
         lambda df: df['base_amount'].notna() & (df['base_amount'] < 0)),

        ('AT_WF_STUCK', 19, 'Asset Register', 'Validity', 'High',
         'Active asset is still in workflow (wf_state = W) — not yet approved',
         'Assets not yet approved in workflow cannot be migrated to the new system.',
         'Resolve the outstanding workflow action to bring the asset to approved status.',
         'asset_register', None,
         'asset_register.wf_state = "W"',
         lambda df: df['wf_state'] == 'W'),

        ('AT_ACTIVE_WITH_DATE_TO', 19, 'Asset Register', 'Validity', 'High',
         'Asset status is Active (N) but an ownership end date (date_to) is populated',
         'An active asset should not have an end date — this is a contradictory record.',
         'Either clear asset_register.date_to or update status to reflect the correct asset state.',
         'asset_register', None,
         'asset_register.status = "N" AND asset_register.date_to IS NOT NULL',
         lambda df: (df['status'] == 'N') & df['date_to'].notna()),

        # ======================================================================
        # --- CONSISTENCY / REFERENTIAL INTEGRITY (some require cross-table joins) ---
        # ======================================================================

        ('AT_ORPHANED_ASSET_GROUP', 19, 'Asset Register', 'Consistency', 'High',
         'Asset group code does not match any known group in the reference list',
         'An unrecognised asset group means depreciation rules cannot be applied in the new system.',
         'Correct asset_register.asset_group to a valid code confirmed by Parliament.',
         'asset_register', None,
         'asset_register.asset_group NOT IN (valid asset group list)',
         lambda df: df['asset_group'].notna() & ~df['asset_group'].isin(
             ['LAND', 'BLDG', 'FURN', 'IT_HW', 'IT_SW', 'PLANT', 'VEHICLE', 'IFRS16']
         )),

        ('AT_PARENT_NOT_FOUND', 19, 'Asset Register', 'Referential Integrity', 'High',
         'Component asset references a parent_asset that does not exist in the register',
         'A child asset pointing to a non-existent parent will cause structural errors during migration.',
         'Verify asset_register.parent_asset and correct or clear it.',
         'asset_register', 'asset_register',
         'asset_register.parent_asset NOT IN (SELECT asset_id FROM asset_register)',
         lambda df, frames: df['parent_asset'].notna() & ~df['parent_asset'].isin(
             frames.get('asset_register', pd.DataFrame())['asset_id']
         ) if 'asset_register' in frames else pd.Series([False] * len(df))),

        ('AT_PARENT_INACTIVE', 19, 'Asset Register', 'Referential Integrity', 'Medium',
         'Component asset references a parent_asset that is closed or terminated',
         'Loading a child asset against an inactive parent may be rejected by the new system.',
         'Review parent asset status — either reactivate the parent or reassign the child.',
         'asset_register', 'asset_register',
         'asset_register.parent_asset IN (SELECT asset_id FROM asset_register WHERE status != "N")',
         lambda df, frames: df['parent_asset'].notna() & df['parent_asset'].isin(
             frames.get('asset_register', pd.DataFrame())[
                 frames.get('asset_register', pd.DataFrame())['status'] != 'N'
             ]['asset_id']
         ) if 'asset_register' in frames else pd.Series([False] * len(df))),

        ('AT_SUPPLIER_NOT_FOUND', 19, 'Asset Register', 'Referential Integrity', 'Medium',
         'Asset references a purchasing supplier (apar_id) with no matching supplier master record',
         'A supplier link with no master record will break the asset-to-procurement audit trail.',
         'Verify asset_register.apar_id against the supplier master and correct or clear if unknown.',
         'asset_register', 'asuheader',
         'asset_register.apar_id NOT IN (SELECT apar_id FROM asuheader)',
         lambda df, frames: df['apar_id'].notna() & ~df['apar_id'].isin(
             frames.get('asuheader', pd.DataFrame())['apar_id']
         ) if 'asuheader' in frames else pd.Series([False] * len(df))),

        ('AT_SUPPLIER_INACTIVE', 19, 'Asset Register', 'Referential Integrity', 'Low',
         'Asset references a purchasing supplier (apar_id) that is inactive or closed',
         'Linking an asset to an inactive supplier may cause referential issues in the new system.',
         'Confirm with Finance whether the supplier link is still relevant; clear or update as appropriate.',
         'asset_register', 'asuheader',
         'asset_register.apar_id IN (SELECT apar_id FROM asuheader WHERE status != "N")',
         lambda df, frames: df['apar_id'].notna() & df['apar_id'].isin(
             frames.get('asuheader', pd.DataFrame())[
                 frames.get('asuheader', pd.DataFrame())['status'] != 'N'
             ]['apar_id']
         ) if 'asuheader' in frames else pd.Series([False] * len(df))),

        ('AT_DIM1_INVALID', 19, 'Asset Register', 'Referential Integrity', 'High',
         'Cost centre (dim_1) references an inactive or non-existent dimension value',
         'An invalid cost centre code means depreciation postings will fail in the new system.',
         'Correct asset_register.dim_1 to a valid, active cost centre in the dimension values register.',
         'asset_register', 'agldimvalue',
         'asset_register.dim_1 NOT IN (SELECT dim_value FROM agldimvalue WHERE status = "N")',
         lambda df, frames: df['dim_1'].notna() & ~df['dim_1'].isin(
             frames.get('agldimvalue', pd.DataFrame())[
                 frames.get('agldimvalue', pd.DataFrame())['status'] == 'N'
             ]['dim_value']
         ) if 'agldimvalue' in frames else pd.Series([False] * len(df))),

        # ======================================================================
        # --- UNIQUENESS (Full population) ---
        # ======================================================================

        ('AT_DUP_ASSET_ID', 19, 'Asset Register', 'Uniqueness', 'Critical',
         'Duplicate asset_id found within the same House',
         'asset_id must be unique per client — duplicates will cause primary key conflicts on migration.',
         'Investigate duplicate asset IDs and consolidate or remove the redundant records.',
         'asset_register', None,
         'COUNT(*) OVER(PARTITION BY client, asset_id) > 1',
         lambda df: df.duplicated(subset=['house', 'asset_id'], keep=False)),

        ('AT_DUP_DESC_GROUP', 19, 'Asset Register', 'Uniqueness', 'Medium',
         'Assets with identical description and asset_group within the same House',
         'Assets with the same name and group may be duplicate registrations of the same physical asset.',
         'Review matching records with the business to confirm whether they represent the same asset.',
         'asset_register', None,
         'COUNT(*) OVER(PARTITION BY client, description, asset_group) > 1',
         lambda df: df.duplicated(subset=['house', 'description', 'asset_group'], keep=False)),

        # ======================================================================
        # --- REFERENTIAL INTEGRITY (continued) ---
        # ======================================================================

        ('AT_COMPONENT_ASSET', 19, 'Asset Register', 'Referential Integrity', 'Low',
         'Component asset with parent_asset populated — load ordering required',
         'Parent-child asset structures require careful load ordering in the new system.',
         'Ensure all parent assets are loaded before their child components during migration.',
         'asset_register', None,
         'asset_register.parent_asset IS NOT NULL',
         lambda df: df['parent_asset'].notna()),

        # ======================================================================
        # --- COMPLETENESS (continued) ---
        # ======================================================================

        ('AT_GRANT_FUNDED', 19, 'Asset Register', 'Completeness', 'Medium',
         'Asset is grant-funded (grant_flag = 1) — migration treatment unconfirmed',
         'Grant-funded assets may require separate migration treatment or business sign-off.',
         'Flag grant-funded assets for business review and confirm migration approach.',
         'asset_register', None,
         'asset_register.grant_flag = 1',
         lambda df: df['grant_flag'] == 1),

        # ======================================================================
        # --- TIMELINESS (Active assets) ---
        # ======================================================================

        ('AT_STALE', 19, 'Asset Register', 'Timeliness', 'Low',
         'Active asset has not been updated in over 3 years',
         'Stale records may indicate assets never actively maintained or retired assets not yet closed.',
         'Review stale assets with Finance to confirm active status before migration.',
         'asset_register', None,
         'asset_register.last_update < (TODAY - 3 years)',
         lambda df: pd.to_datetime(df['last_update'], errors='coerce') < (today - pd.Timedelta(days=3*365))),
    ]
    return checks