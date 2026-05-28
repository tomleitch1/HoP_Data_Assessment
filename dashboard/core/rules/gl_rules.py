import pandas as pd


def get_gl_checks():
    return []


# =============================================================================
# GL DQ CHECK CATALOGUE — planned checks, to be rebuilt against real data
# =============================================================================
# Chart of Accounts (aglaccounts)
#   GL_ACC_DESC_MISSING   Active account has no description
#   GL_ACC_GRP_MISSING    Active account not assigned to a reporting group
#   GL_ACC_RESBAL_MISSING Missing Balance Sheet/P&L classification
#   GL_ACC_RULE_MISSING   Active account missing its posting rule ID
#   GL_ACC_PERIOD_MISSING Active account missing valid-from period
#   GL_ACC_RESBAL_INVALID res_bal contains invalid code (must be R or B)
#   GL_ACC_TYPE_INVALID   account_type not a valid GL/AP/AR code
#   GL_ACC_PERIOD_INV     Valid-from period is after the valid-to period
#   GL_ACC_STALE_N        Account is active (status N) but validity period has expired
#   GL_ACC_BFLAG_CON      Reconciliation account (bflag 7) not flagged as AP or AR type
#   GL_ACC_DUP_CODE       Duplicate account code within the same House
#   GL_ACC_STALE_MOD      Stale account: not updated in over 3 years
#
# Dimension Values (agldimvalue)
#   GL_DIM_DESC_MISSING   Active dimension value has no description
#   GL_DIM_PERIOD_MISSING Active dimension value missing valid-from period
#   GL_DIM_PERIOD_INV     Dimension valid-from period is after the valid-to period
#   GL_DIM_WF_STUCK       Dimension value stuck in a non-approved workflow state
#   GL_DIM_ORPHAN_REL     Hierarchy link to a parent that is missing or inactive
#   GL_DIM_DUP            Duplicate dimension code within the same attribute and House
#
# Opening Balances / Period Balances (aglperiodic → frame key aglyearend)
#   GL_BAL_AMT_MISSING    Opening balance record has no amount
#   GL_BAL_FX_MISSING     Foreign currency balance missing transaction currency amount
#   GL_BAL_PL_NONZERO     P&L account carries a non-zero balance at year end
#   GL_BAL_TOTAL_NET      General Ledger is out of balance (Total Debits <> Credits)
#   GL_BAL_ORPHAN_ACC     Balance refers to an account code not in the chart of accounts
#
# Transactions (agltransact)
#   GL_TRA_ORPHAN_DIM1    Transaction coded to a dimension value that does not exist or is inactive
#
# Journals (gl_journals — agltransact filtered to current FY)
#   DQ-GJ-C01  Journal line has no voucher number
#   DQ-GJ-C02  Journal line has no account code
#   DQ-GJ-C03  Journal line has no amount
#   DQ-GJ-C04  Journal line has no transaction date
#   DQ-GJ-C05  Journal line has no voucher entry date
#   DQ-GJ-C06  Journal line has no voucher type
#   DQ-GJ-C07  Manual journal line (JRNL type) has no description
#   DQ-GJ-C08  Journal line has no user ID
#   DQ-GJ-V01  update_flag contains an invalid debit/credit code
#   DQ-GJ-V02  Journal trans_date is in the future
#   DQ-GJ-V03  Journal voucher_date is in the future
#   DQ-GJ-V04  trans_date and voucher_date differ by more than one GL period (~60 days)
#   DQ-GJ-V05  Journal line has no currency code
#   DQ-GJ-V06  Non-GBP journal line is missing its transaction currency amount
#   DQ-GJ-V07  Period is outside the expected fiscal year range (202601–202615)
#   DQ-GJ-V08  Sub-ledger reference (apar_id) on a non-control account line
#   DQ-GJ-K01  Voucher does not balance — debits do not equal credits
#   DQ-GJ-K02  trans_date falls in a different period to the period field
#   DQ-GJ-K03  apar_id and apar_type are not both present or both absent
#   DQ-GJ-K04  Voucher contains lines posted to different periods
#   DQ-GJ-K05  tax_code and tax_system are not both present or both absent
#   DQ-GJ-D01  Duplicate composite primary key (client, voucher_no, sequence_no)
#   DQ-GJ-D02  Potential duplicate posting — same client, voucher, account, amount, and date
#   DQ-GJ-S02  Journal line is in a year-end adjustment period (13, 14, or 15)
#   DQ-GJ-S04  Non-GBP journal line — FX population for target system planning
#   DQ-GJ-S05  Journal line carries a sub-ledger reference (apar_id populated)
#   DQ-GJ-X01  Journal account code does not exist in the chart of accounts
#   DQ-GJ-X02  Journal posts to a closed or inactive account
#   DQ-GJ-X03  Journal dim_1 value does not exist as an active dimension in master data
