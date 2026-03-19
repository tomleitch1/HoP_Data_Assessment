"""
Parliament Finance Systems Programme
Unit4 Data Quality Assessment Dashboard
Veran Performance | Technology & Data Workstream

Run: python run_dashboard.py
"""

import sys
import os

# Add the current directory to sys.path so 'dashboard' package can be found
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dashboard.app import app

if __name__ == '__main__':
    print('\n' + '═'*60)
    print('  PARLIAMENT DQA DASHBOARD — VERAN PERFORMANCE')
    print('  Modular Analytics Engine | Unit4 Current State')
    print('  URL: http://127.0.0.1:8050')
    print('═'*60 + '\n')
    
    app.run(debug=True, host='0.0.0.0', port=8050)
