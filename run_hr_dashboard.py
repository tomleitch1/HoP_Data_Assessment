"""
Royal Mail HR & Payroll Data Quality Assessment — Bid Demonstration
Veran Performance

One-off demo build, entirely separate from the Parliament finance dashboard
(run_dashboard.py). Uses its own package (hr_dashboard/), its own dummy data
(data/hr/), and its own port by default so both can run side by side without
any interference.

First-time setup:
    python scripts/generate_hr_dummy_data.py

Run:
    python run_hr_dashboard.py
    python run_hr_dashboard.py --port 8060
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

_port = 8060
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
            _i += 2
        else:
            _i += 1
    else:
        _i += 1

from hr_dashboard.app import app

if __name__ == '__main__':
    print('\n' + '=' * 60)
    print('  ROYAL MAIL HR & PAYROLL DQA — VERAN PERFORMANCE')
    print('  Bid Demonstration | Synthetic Data Only')
    print(f'  URL: http://127.0.0.1:{_port}')
    print('=' * 60 + '\n')

    app.run(debug=True, host='0.0.0.0', port=_port)
