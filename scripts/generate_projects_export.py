"""
Projects SI extract (Seq 22).

Writes trackers/projects/projects_scope.xlsx: project headers, tasks, the
opening position per project and per task, the annual history and a
reconciliation. Same content as the Projects tab's download button.

Usage:
    python scripts/generate_projects_export.py                       # all listed codes, all cost types
    python scripts/generate_projects_export.py --projects-only       # exclude Annual Requirements
    python scripts/generate_projects_export.py --expenditure-only    # exclude income / recharge cost types

DQ findings go through the standard tracker:
    python scripts/generate_tracker.py projects HOC
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.data_engine import load_data
from dashboard.core.projects_export import build_sheets, write_workbook


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--projects-only', action='store_true', help='exclude Annual Requirements Units')
    ap.add_argument('--expenditure-only', action='store_true', help='exclude income and recharge cost types')
    args = ap.parse_args()

    frames = load_data(tab='projects')
    if 'project_lines' not in frames:
        sys.exit('No project data found. Place project_list.csv and project_financials.csv in data/projects/.')

    sheets = build_sheets(frames, include_annual=not args.projects_only, expenditure_only=args.expenditure_only)
    out_dir = os.path.join('trackers', 'projects')
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, 'projects_scope.xlsx')
    write_workbook(sheets, path)
    print(f'Written {path}')
    for name, df in sheets.items():
        print(f'  {name:18s} {len(df):,} rows')


if __name__ == '__main__':
    main()
