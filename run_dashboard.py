"""
Parliament Finance Systems Programme
Unit4 Data Quality Assessment Dashboard
Veran Performance | Technology & Data Workstream

Run all tabs:       python run_dashboard.py
Run one tab only:   python run_dashboard.py suppliers
                    python run_dashboard.py gl
                    python run_dashboard.py customers
                    python run_dashboard.py assets
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Parse optional tab argument before importing app (app loads data at import time)
_VALID_TABS = {
    'suppliers': 'suppliers', 'ap': 'suppliers',
    'customers': 'customers', 'ar': 'customers',
    'gl':        'gl',
    'assets':    'assets',
}
_tab_label = None
if len(sys.argv) > 1:
    _arg = sys.argv[1].lower()
    if _arg in _VALID_TABS:
        os.environ['DASHBOARD_TAB'] = _VALID_TABS[_arg]
        _tab_label = _VALID_TABS[_arg]
    else:
        print(f"Unknown tab '{_arg}'. Valid options: {', '.join(_VALID_TABS)}. Loading all tabs.")

from dashboard.app import app

if __name__ == '__main__':
    print('\n' + '='*60)
    print('  PARLIAMENT DQA DASHBOARD - VERAN PERFORMANCE')
    print('  Modular Analytics Engine | Unit4 Current State')
    if _tab_label:
        print(f'  Mode: {_tab_label.upper()} tab only')
    print('  URL: http://127.0.0.1:8050')
    print('='*60 + '\n')

    app.run(debug=True, host='0.0.0.0', port=8050)
