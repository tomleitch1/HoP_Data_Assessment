# ═══════════════════════════════════════════════════════════════════════════════
# theme.py  —  All visual design tokens: colours, styles, chart config.
#
#  Nothing in here affects data logic — it is purely cosmetic.
#  Change values here to restyle the dashboard without touching any data code.
#
#  Imported by: components.py, charts.py, tabs/, callbacks.py
#  Never imported by: dq_engine/, data_loader.py, scoring.py
# ═══════════════════════════════════════════════════════════════════════════════

# ── Display font ──────────────────────────────────────────────────────────────
#
# Used for large numeric KPIs and scores throughout the dashboard.
# Inter at weight 800/900 gives blocky, highly legible numerals.
# To change the display font across the whole dashboard, edit this one line.

DISPLAY_FONT = "'Inter', sans-serif"

# ── RAG colours ───────────────────────────────────────────────────────────────

RAG_HEX = {
    'Red':   '#c0392b',
    'Amber': '#d4820a',
    'Green': '#1a7a4a',
}

# ── Severity colours ──────────────────────────────────────────────────────────

SEV_HEX = {
    'Critical': '#c0392b',
    'High':     '#d4820a',
    'Medium':   '#e6a817',
    'Low':      '#7c5cbf',
}

# ── House colours ─────────────────────────────────────────────────────────────

HOUSE_HEX = {
    'HOC':       '#00703c',
    'HOC_LIGHT': '#28a367',
    'HOL':       '#9b2335',
    'HOL_LIGHT': '#c0392b',
    'Joint':     '#1e3a5f',   # navy — spans both houses, used only by Atamis contracts (Organisation field)
    'Unknown':   '#64748b',   # slate — Atamis rows that couldn't be matched to a Unit4 house
    'All':       '#7c3aed',   # violet — Unit4 Commitments/Spend checks that are house-independent by nature
}

# ── Parliament UI palette ─────────────────────────────────────────────────────

UI = {
    # Page structure
    'page_bg':        '#ebebf2',  # light purple-grey — lighter band in the header screenshot
    'card_bg':        '#ffffff',
    'card_bg_dark':   '#ebebf2',  # section card backgrounds — matches page_bg
    'border':         '#d0cce0',

    # Header
    'header_start':   '#392e4e',  # dark purple — darker band in the header screenshot
    'header_end':     '#3a2f4f',
    'header_subtitle':'#c8b8e8',
    'header_muted':   '#a0a0cc',

    # Text
    'text_primary':   '#1a1523',
    'text_secondary': '#5c5470',
    'text_accent':    '#f4f3f7',

    # Tabs
    'tab_unselected': '#a0a0cc',
    'tab_indicator':  '#2d2d5e',
    'tab_action':     '#c0392b',

    # Purple accents
    'purple_mid':     '#7c5cbf',
    'purple_light':   '#e8e4f3',

    # Modal chrome (header bar, footer bar)
    'modal_chrome_bg':   '#ebebf2',  # light — matches page_bg / card_bg_dark
    'modal_border':      '#2a0f52',

    # Modal body — failing records table
    'modal_cell_bg':     '#ffffff',  # white rows
    'modal_cell_text':   '#1a1523',  # near-black text
    'modal_cell_border': '#d0cce0',  # matches page border token
    'modal_header_bg':   '#392e4e',  # dark — matches header_start
    'modal_header_text': '#ffffff',  # white text on dark header
    'modal_table_border':'#392e4e',  # outer border — matches header_start
    'modal_txn_bg':      '#f5f3fb',  # transaction columns — soft purple tint
    'modal_mst_bg':      '#f0f4f8',  # master data columns — soft blue-grey tint
    'modal_div_bg':      '#c8bfe8',  # divider column between transaction and master data
}

# ── Aging chart colours ───────────────────────────────────────────────────────

AGING_COLOURS = {
    'Not Yet Due': '#10B981',
    '0-30 Days':   '#34D399',
    '31-60 Days':  '#FBBF24',
    '61-90 Days':  '#F59E0B',
    '91-180 Days': '#E8334A',
    '180+ Days':   '#991B1B',
}

# ── Chart base layout ─────────────────────────────────────────────────────────

CHART_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(family="'Source Sans Pro', sans-serif", color='#5c5470', size=12),
)

# ── Plotly interaction configs ────────────────────────────────────────────────

PLOTLY_STATIC_CONFIG = {'displayModeBar': False, 'scrollZoom': False, 'staticPlot': True}
PLOTLY_HOVER_CONFIG  = {'displayModeBar': False, 'scrollZoom': False, 'staticPlot': False}
PLOTLY_EXEC_CONFIG   = PLOTLY_STATIC_CONFIG  # legacy alias

# ── App meta ──────────────────────────────────────────────────────────────────

APP_TITLE = 'Parliament DQA | Veran Performance'

# ── Column display labels ─────────────────────────────────────────────────────
COLUMN_LABELS: dict[str, str] = {
    'apar_id':           'Supplier / Customer ID',
    'name':              'Name',
    'status':            'Status',
    'client':            'House',
    'bank_account':      'Bank Account',
    'clearing_code':     'Sort Code',
    'iban':              'IBAN',
    'swift':             'SWIFT / BIC',
    'pay_method':        'Payment Method',
    'vat_reg_no':        'VAT Number',
    'comp_reg_no':       'Company Reg. No.',
    'tax_code':          'Tax Code',
    'currency_code':     'Default Currency',
    'currency':          'Currency',
    'country_code':      'Country',
    'terms_id':          'Payment Terms',
    'supplier_group':    'Supplier Group',
    'apar_gr_id':        'Supplier Group',
    'address1':          'Address Line 1',
    'postcode':          'Postcode',
    'contact_name':      'Contact Name',
    'email':             'Email',
    'last_modified_date':'Last Modified',
    'expired_date':      'Expired Date',
    'apar_once':         'Sundry Supplier',
    'wf_state':          'Workflow State',
    'voucher_no':        'Voucher No.',
    'voucher_type':      'Voucher Type',
    'trans_date':        'Transaction Date',
    'due_date':          'Due Date',
    'amount':            'Amount (GBP)',
    'rest_amount':       'Outstanding Balance (GBP)',
    'cur_amount':        'Amount (Foreign CCY)',
    'rest_curr':         'Outstanding (Foreign CCY)',
    'exch_rate':         'Exchange Rate',
    'invoice_no':        'Invoice No.',
    'ext_inv_ref':       'Supplier Invoice Ref.',
    'orig_reference':    'Original Invoice Ref.',
    'order_id':          'Purchase Order',
    'contract_id':       'Contract Ref.',
    'period':            'Period',
    'pay_flag':          'Payment on Account',
    'status_supplier':   'Supplier Status',
    'status_customer':   'Customer Status',
    'days_overdue':      'Days Overdue',
    'collect_status':    'Collection Status',
    'collect_agency':    'Collection Agency',
    'rem_level':         'Reminder Level',
    'sequence_no':       'Sequence No.',
    'apar_name':         'Customer / Supplier Name',
    'credit_limit':      'Credit Limit',
    'expected_paid':     'Expected Paid (GBP)',
    'hist_total':        'History Total (GBP)',
    'recon_diff':        'Discrepancy (GBP)',
    # ── GL columns ────────────────────────────────────────────────────────────
    'account':           'Account Code',
    'account_grp':       'Account Group',
    'account_type':      'Account Type',
    'res_bal':           'P&L / Balance Sheet',
    'bflag':             'Account Behaviour',
    'account_rule':      'Account Rule',
    'head_account':      'Head Account',
    'attribute_id':      'Dimension Type',
    'dim_value':         'Dimension Code',
    'rel_value':         'Parent Code',
    'period_from':       'Valid From (Period)',
    'period_to':         'Valid To (Period)',
    'last_update':       'Last Updated',
    'fiscal_year':       'Fiscal Year',
    'dc_flag':           'Debit / Credit',
    'apar_type':         'AP/AR Type',
    'dim_1':             'Dimension 1',
    'dim_2':             'Dimension 2',
    'dim_3':             'Dimension 3',
    'dim_4':             'Dimension 4',
    'dim_5':             'Dimension 5',
    'dim_6':             'Dimension 6',
    'dim_7':             'Dimension 7',
    # ── Referential integrity enrichment columns ──────────────────────────
    # Auto-injected by callbacks.py for RI checks — display-friendly names
    'found_in_asuheader':       'Found in Supplier Master table?',
    'found_in_acuheader':       'Found in Customer Master table?',
    'found_in_gl_coa':          'Found in Chart of Accounts table?',
    'found_in_gl_dim_values':   'Found in Dimension Values table?',
}

# ── Table display names ───────────────────────────────────────────────────────
TABLE_DISPLAY_NAMES: dict[str, str] = {
    'asuheader':            'Master Data',
    'asutrans':             'Transaction',
    'asuhistr':             'History',
    'acuheader':            'Master Data',
    'acutrans':             'Transaction',
    'gl_coa':               'Chart of Accounts',
    'gl_dim_values':        'Dimension Values',
    'gl_opening_balances':  'Opening Balances',
    'gl_transact_dims':     'Transaction Dimensions',
    'asset_register':       'Asset Register',
    'pbf_data':             'PBF Data',
}

# ── Master data tables ────────────────────────────────────────────────────────
MASTER_DATA_TABLES = {'asuheader', 'acuheader', 'gl_coa', 'gl_dim_values'}