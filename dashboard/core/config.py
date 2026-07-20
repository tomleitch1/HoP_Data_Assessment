import os
from enum import IntEnum
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class EnvConfig:
    DEBUG: bool = os.getenv('DEBUG', 'true').lower() == 'true'
    HOST: str = os.getenv('HOST', '127.0.0.1')
    PORT: int = int(os.getenv('PORT', '8050'))
    CACHE_TIMEOUT: int = int(os.getenv('CACHE_TIMEOUT', '300'))
    CACHE_TYPE: str = os.getenv('CACHE_TYPE', 'SimpleCache')
    CACHE_DIR: str = os.getenv('CACHE_DIR', '.cache')
    VIEWER_MODE: bool = os.getenv('VIEWER_MODE', 'false').lower() == 'true'

env = EnvConfig()

class Scope(IntEnum):
    SUPPLIERS = 10
    CUSTOMERS = 11
    AR_HISTORY = 12
    AP_INVOICES = 16
    AR_OPEN_TRANSACTIONS = 17
    ASSETS = 19
    GL_ACCOUNTS = 20
    GL_DIMENSIONS = 21
    GL_BALANCES = 22
    GL_TRANSACTIONS = 23
    PO_ORDERS = 15
    PBF = 25
    ATAMIS_CONTRACTS = 30
    ATAMIS_COMMITMENTS = 31
    ATAMIS_SPEND = 32
    ATAMIS_SUPPLIERS = 33

class SupplierConfig:
    BACS_PAYMENT_METHODS = ['BACS']
    ZERO_RATE_TAX_CODES = []
    ALLOWED_TAX_CODES = []
    ALLOWED_TERMS_IDS = []
    STALE_SUPPLIER_DAYS = 730
    STALE_LAST_MODIFIED_DAYS = 1095
    ACTIVE_STATUSES = ['N']
    INACTIVE_STATUSES = ['C']
    HOC_CLIENTS = ['CA', 'CM']  # Only these client codes are in scope for HOC
    HOL_CLIENTS = ['LA']        # Only this client code is in scope for HOL

class CustomerConfig:
    ACTIVE_STATUSES = ['N']
    INACTIVE_STATUSES = ['C']

class APConfig:
    CLOSED_STATUS = 'C'
    OPEN_TRANSACTION_STATUSES = ['N', 'R', 'I', 'P']
    WORKFLOW_PENDING_STATUSES = ['W', 'R', 'U']

class ARConfig:
    CLOSED_STATUS = 'C'
    OPEN_TRANSACTION_STATUSES = ['N', 'R', 'I', 'P', 'H']
    WORKFLOW_PENDING_STATUSES = ['W', 'R', 'U']

class GLConfig:
    ACTIVE_STATUSES = ['N']
    INACTIVE_STATUSES = ['C', 'P', 'T']
    VALID_RES_BAL = ['R', 'B']
    VALID_ACCOUNT_TYPES = ['GL', 'AP', 'AR']
    RECON_BFLAG = 7
    STALE_DAYS = 1095
    WF_STUCK_STATES = ['W']
    WF_APPROVED_STATES = ['', 'T']
    DC_DEBIT = 1
    DC_CREDIT = -1
    BASE_CURRENCY = 'GBP'
    HIERARCHY_DIM_TYPES = ['COSTC', 'SUBJ']
    DIM_TYPES_IN_SCOPE = []
    FISCAL_YEAR = None
    YEAR_END_PERIOD = None

HIST_CREDIT_NOTE_VOUCHER_TYPES = []
ALLOWED_PAYMENT_METHODS = ['BACS', 'CHQ', 'TRF', 'DD', 'CARD']

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
CLIENTS = ['HOC', 'HOL']

COLUMN_MAP = {
    'client'             : 'client',
    'apar_id'            : 'apar_id',
    'name'               : 'apar_name',
    'supplier_group'     : 'apar_gr_id',
    'status'             : 'status',
    'apar_once'          : 'apar_once',
    'vat_reg_no'         : 'vat_reg_no',
    'comp_reg_no'        : 'comp_reg_no',
    'country_code'       : 'country_code',
    'tax_code'           : 'tax_code',
    'terms_id'           : 'terms_id',
    'pay_method'         : 'pay_method',
    'currency_code'      : 'currency',
    'sort_code'          : 'clearing_code',
    'bank_account'       : 'bank_account',
    'iban'               : 'iban',
    'swift'              : 'swift',
    'expired_date'       : 'expired_date',
    'wf_state'           : 'wf_state',
    'address'            : 'address',
    'place'              : 'place',
    'zip_code'           : 'zip_code',
    'province'           : 'province',
    'contact_name'       : 'contact_name',
    'email'              : 'email',
    'credit_limit'       : 'credit_limit',
    'voucher_no'         : 'voucher_no',
    'sequence_no'        : 'sequence_no',
    'voucher_type'       : 'voucher_type',
    'voucher_date'       : 'voucher_date',
    'trans_date'         : 'trans_date',
    'due_date'           : 'due_date',
    'description'        : 'description',
    'amount'             : 'amount',
    'cur_amount'         : 'cur_amount',
    'currency'           : 'currency',
    'rest_amount'        : 'rest_amount',
    'rest_curr'          : 'rest_curr',
    'exch_rate'          : 'exch_rate',
    'pay_flag'           : 'pay_flag',
    'ext_inv_ref'        : 'ext_inv_ref',
    'orig_reference'     : 'orig_reference',
    'order_id'           : 'order_id',
    'contract_id'        : 'contract_id',
    'period'             : 'period',
}

SCOPE_CONFIG = {
    'ap': {
        'label':     'AP',
        'tab_value': 'ap',
        'scope_ids': [Scope.SUPPLIERS, Scope.AP_INVOICES],
        'tables':    ['asuheader', 'asutrans', 'asuhistr'],
        'aging':     'AP',
    },
    'ar': {
        'label':     'AR',
        'tab_value': 'ar',
        'scope_ids': [Scope.CUSTOMERS, Scope.AR_OPEN_TRANSACTIONS, Scope.AR_HISTORY],
        'tables':    ['acuheader', 'acutrans', 'acuhistr'],
        'aging':     'AR',
    },
    'gl': {
        'label':     'GL',
        'tab_value': 'gl',
        'scope_ids': [Scope.GL_ACCOUNTS, Scope.GL_DIMENSIONS, Scope.GL_BALANCES, Scope.GL_TRANSACTIONS],
        'tables':    ['gl_coa', 'gl_dim_values', 'gl_opening_balances', 'gl_transact_dims'],
        'aging':     None,
    },
    'assets': {
        'label':     'Assets',
        'tab_value': 'assets',
        'scope_ids': [Scope.ASSETS],
        'tables':    ['asset_master', 'asset_depreciation', 'asset_balances', 'asset_trans_flags'],
        'aging':     None,
    },
    'po': {
        'label':     'Purchase Orders',
        'tab_value': 'po',
        'scope_ids': [Scope.PO_ORDERS],
        'tables':    ['apoheader', 'apodetail'],
        'aging':     None,
    },
    'pbf': {
        'label':     'PBF',
        'tab_value': 'pbf',
        'scope_ids': [Scope.PBF],
        'tables':    ['pbf_data'],
        'aging':     None,
    },
    'atamis': {
        'label':     'Atamis',
        'tab_value': 'atamis',
        'scope_ids': [Scope.ATAMIS_CONTRACTS, Scope.ATAMIS_COMMITMENTS, Scope.ATAMIS_SPEND, Scope.ATAMIS_SUPPLIERS],
        'tables':    ['atamis_contracts', 'atamis_commitments', 'atamis_spend', 'atamis_suppliers'],
        'aging':     None,
    },
}

SCOPE_LABELS = {
    Scope.SUPPLIERS: 'Suppliers',
    Scope.CUSTOMERS: 'Customers',
    Scope.AR_HISTORY: 'AR History',
    Scope.AP_INVOICES: 'AP Invoices',
    Scope.AR_OPEN_TRANSACTIONS: 'AR Open Transactions',
    Scope.GL_ACCOUNTS: 'GL Accounts',
    Scope.GL_DIMENSIONS: 'GL Dimensions',
    Scope.GL_BALANCES: 'GL Balances',
    Scope.GL_TRANSACTIONS: 'GL Transactions',
    Scope.ASSETS: 'Assets',
    Scope.PO_ORDERS: 'Purchase Orders',
    Scope.PBF: 'Planning, Budgeting & Forecasting',
    Scope.ATAMIS_CONTRACTS: 'Atamis Contracts',
    Scope.ATAMIS_COMMITMENTS: 'Contract Commitments',
    Scope.ATAMIS_SPEND: 'Contract Spend',
    Scope.ATAMIS_SUPPLIERS: 'Atamis Suppliers',
}

SCOPE_TABLES = {
    Scope.SUPPLIERS: 'asuheader',
    Scope.CUSTOMERS: 'acuheader',
    Scope.AR_HISTORY: 'acuhistr',
    Scope.AP_INVOICES: 'asutrans',
    Scope.AR_OPEN_TRANSACTIONS: 'acutrans',
    Scope.GL_ACCOUNTS: 'gl_coa',
    Scope.GL_DIMENSIONS: 'gl_dim_values',
    Scope.GL_BALANCES: 'gl_opening_balances',
    Scope.GL_TRANSACTIONS: 'gl_transact_dims',
    Scope.ASSETS: 'asset_master',
    Scope.PBF: 'pbf_data',
}

SCOPE_TO_TAB = {}
for _cfg in SCOPE_CONFIG.values():
    for _sid in _cfg['scope_ids']:
        SCOPE_TO_TAB[_sid] = _cfg['label']

ALL_TABLES = [
    'asuheader', 'asutrans', 'asuhistr',
    'acuheader', 'acutrans', 'acuhistr',
    'gl_coa', 'gl_dim_values', 'gl_opening_balances', 'gl_transact_dims',
    'asset_master', 'asset_depreciation', 'asset_balances', 'asset_trans_flags',
    'apoheader', 'apodetail', 'pbf_data',
    'atamis_contracts', 'atamis_commitments', 'atamis_spend', 'atamis_suppliers',
]

# Per-severity RAG thresholds (error rate %). Green = below first value, Amber = below second, Red = above.
RAG_THRESHOLDS = {
    'Critical': (1,  5),
    'High':     (3,  10),
    'Medium':   (5,  15),
    'Low':      (10, 25),
}

SEV_ORDER  = ['Critical', 'High', 'Medium', 'Low']
SEV_WEIGHT = {'Critical': 1, 'High': 2, 'Medium': 3, 'Low': 4}
RAG_ORDER  = ['Red', 'Amber', 'Green']

AGING_BUCKETS = [
    'Not Yet Due', '0-30 Days', '31-60 Days',
    '61-90 Days',  '91-180 Days', '180+ Days',
]