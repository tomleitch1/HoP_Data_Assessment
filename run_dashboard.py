"""
Parliament Finance Systems Programme
Unit4 Data Quality Assessment Dashboard
Veran Performance | Technology & Data Workstream

Run all tabs:         python run_dashboard.py
Run one tab only:     python run_dashboard.py suppliers
                      python run_dashboard.py gl
                      python run_dashboard.py customers
                      python run_dashboard.py assets

Versioned data run:   python run_dashboard.py suppliers v2
                      python run_dashboard.py assets v2

  When a version (e.g. v2) is supplied, the loader looks for files named
  supplier_master_HOL_v2.csv etc. before falling back to the standard name.
  This lets you load refreshed HOL data alongside unchanged HOC data in the
  same dashboard run — useful for before/after comparison after data cleansing.
  Run on a different port to keep the baseline available side by side:
      python run_dashboard.py suppliers v2 --port 8051
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Parse optional tab and version arguments before importing app
_VALID_TABS = {
    'suppliers': 'suppliers', 'ap': 'suppliers',
    'customers': 'customers', 'ar': 'customers',
    'gl':        'gl',
    'assets':    'assets',
    'po':        'po',
    'atamis':    'atamis',
}
_tab_label = None
_version    = None
_port       = 8050

_args = sys.argv[1:]
_i = 0
while _i < len(_args):
    _arg = _args[_i]
    if _arg.startswith('--port='):
        try:
            _port = int(_arg.split('=', 1)[1])
        except ValueError:
            pass
        _i += 1
    elif _arg == '--port':
        if _i + 1 < len(_args):
            try:
                _port = int(_args[_i + 1])
            except ValueError:
                pass
            _i += 2  # consume both --port and the value
        else:
            _i += 1
    elif _arg.lower() in _VALID_TABS:
        os.environ['DASHBOARD_TAB'] = _VALID_TABS[_arg.lower()]
        _tab_label = _VALID_TABS[_arg.lower()]
        _i += 1
    elif not _arg.startswith('--'):
        _version = _arg.lower()
        os.environ['DASHBOARD_VERSION'] = _version
        _i += 1
    else:
        _i += 1

from dashboard.app import app

if __name__ == '__main__':
    print('\n' + '='*60)
    print('  PARLIAMENT DQA DASHBOARD - VERAN PERFORMANCE')
    print('  Modular Analytics Engine | Unit4 Current State')
    if _tab_label:
        print(f'  Mode: {_tab_label.upper()} tab only')
    if _version:
        print(f'  Data version: {_version} (falls back to standard if versioned file not found)')
    print(f'  URL: http://127.0.0.1:{_port}')
    print('='*60 + '\n')

    app.run(debug=True, host='0.0.0.0', port=_port)
