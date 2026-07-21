"""
Payroll Transactions DQ checks — Royal Mail HR & Payroll bid-demo dashboard.

Same tuple format as employee_rules.py. Two checks (PAY_ORPHAN_EMPLOYEE,
PAY_BANK_MISMATCH) join against the employee_master frame, so their lambda
takes (df, frames) instead of just (df) — same convention as every join
check in the Parliament finance dashboard's rule files.
"""

import pandas as pd

from hr_dashboard.core.config import Scope, PayrollConfig


def _bank_mismatch(df, frames):
    emp = frames.get('employee_master')
    if emp is None or emp.empty:
        return pd.Series(False, index=df.index)

    emp_bank = (
        emp.drop_duplicates(subset=['employee_id'])
        .set_index('employee_id')[['bank_account', 'sort_code']]
    )
    joined = df.join(emp_bank, on='employee_id', rsuffix='_master')

    both_populated = (
        joined['bank_account'].notna() & joined['bank_account_master'].notna()
        & joined['sort_code'].notna() & joined['sort_code_master'].notna()
    )
    differs = (
        (joined['bank_account'].astype(str).str.strip() != joined['bank_account_master'].astype(str).str.strip())
        | (joined['sort_code'].astype(str).str.strip() != joined['sort_code_master'].astype(str).str.strip())
    )
    return both_populated & differs


def get_payroll_checks():
    return [

        ('PAY_NET_EXCEEDS_GROSS',
         Scope.PAYROLL, 'Payroll Transactions', 'Validity', 'Critical',
         'Net pay is greater than gross pay on a payroll transaction',
         'Net pay can never exceed gross pay once tax, National Insurance, and pension deductions are applied. '
         'A transaction where net exceeds gross means the payslip has been calculated incorrectly, or a deduction has been applied with the wrong sign. '
         'Paying this employee as calculated would overpay them and create a payroll error that has to be clawed back later.',
         'Recalculate the payslip from basic pay, overtime, and deductions, and correct the transaction before payment is released.',
         'payroll_transactions', None,
         'WHERE net_pay > gross_pay',
         lambda df: df['net_pay'] > df['gross_pay']),

        ('PAY_NEGATIVE_GROSS',
         Scope.PAYROLL, 'Payroll Transactions', 'Validity', 'High',
         'Payroll transaction has a negative gross pay figure',
         'Gross pay on a standard payroll transaction should never be negative. '
         'A negative gross figure usually means a correction or clawback was posted as a normal pay transaction instead of through the proper adjustment process. '
         'Left uncorrected, this transaction will distort payroll cost reporting for the period it falls in.',
         'Confirm whether this is a genuine correction; if so, re-post it through the correct adjustment transaction type rather than a standard pay line.',
         'payroll_transactions', None,
         'WHERE gross_pay < 0',
         lambda df: df['gross_pay'] < 0),

        ('PAY_MISSING_TAX_CODE',
         Scope.PAYROLL, 'Payroll Transactions', 'Completeness', 'High',
         'Payroll transaction has no tax code recorded',
         'Every payroll transaction must carry the tax code that was applied to calculate the deduction. '
         'Without it, the deduction on this payslip cannot be verified or reconciled against HMRC guidance. '
         'A missing tax code on a processed transaction is a strong signal the payslip may already be using an incorrect default.',
         'Trace the transaction back to the employee\'s current tax code and populate the field, then verify the tax deducted was calculated correctly.',
         'payroll_transactions', None,
         "WHERE tax_code IS NULL OR TRIM(tax_code) = ''",
         lambda df: df['tax_code'].isna() | (df['tax_code'].astype(str).str.strip() == '')),

        ('PAY_NI_CAT_MISSING',
         Scope.PAYROLL, 'Payroll Transactions', 'Completeness', 'High',
         'Payroll transaction has no National Insurance category recorded',
         'Every payroll transaction must carry the NI category used to calculate the employee and employer National Insurance contributions. '
         'Without it, the NI deduction on this transaction cannot be verified as correct. '
         'HMRC RTI submissions require an NI category on every reported payment.',
         'Trace the transaction back to the employee\'s current NI category and populate the field.',
         'payroll_transactions', None,
         "WHERE ni_category IS NULL OR TRIM(ni_category) = ''",
         lambda df: df['ni_category'].isna() | (df['ni_category'].astype(str).str.strip() == '')),

        ('PAY_ORPHAN_EMPLOYEE',
         Scope.PAYROLL, 'Payroll Transactions', 'Consistency', 'High',
         'Payroll transaction references an employee ID not found in the employee master',
         'Every payroll transaction must belong to an employee that exists in the employee master. '
         'A transaction with no matching employee record cannot be reconciled to headcount, cost centre, or org structure reporting. '
         'This usually means the employee ID was mistyped, or the employee record was deleted after the transaction was posted.',
         'Trace the transaction to the correct employee ID and correct it, or investigate why the employee record is missing.',
         'payroll_transactions', 'employee_master',
         'WHERE employee_id NOT IN (SELECT employee_id FROM employee_master)',
         lambda df, frames: (
             ~df['employee_id'].isin(frames['employee_master']['employee_id'])
             if 'employee_master' in frames else pd.Series(False, index=df.index)
         )),

        ('PAY_DUP_TRANSACTION',
         Scope.PAYROLL, 'Payroll Transactions', 'Uniqueness', 'Critical',
         'Duplicate payroll transaction for the same employee and pay period',
         'Each employee should have exactly one payroll transaction per pay period. '
         'A duplicate transaction for the same employee and period means that employee has been paid, or is about to be paid, twice for the same work. '
         'This is a direct overpayment risk and should be resolved before the payment file is released to the bank.',
         'Investigate both transactions, confirm which one is correct, and void or reverse the duplicate before payment.',
         'payroll_transactions', None,
         'WHERE (employee_id, pay_period) appears more than once',
         lambda df: df.duplicated(subset=['employee_id', 'pay_period'], keep=False)),

        ('PAY_OVERTIME_NO_HOURS',
         Scope.PAYROLL, 'Payroll Transactions', 'Consistency', 'Medium',
         'Payroll transaction has overtime pay but zero overtime hours recorded',
         'Where overtime pay has been applied, the corresponding overtime hours should also be recorded on the same transaction. '
         'A transaction with overtime pay but no hours means the pay component cannot be traced back to worked time. '
         'This breaks the audit trail auditors and payroll assurance reviews rely on to justify overtime cost.',
         'Trace the overtime pay back to the timesheet or clocking system and populate the correct overtime hours.',
         'payroll_transactions', None,
         'WHERE overtime_pay > 0 AND overtime_hours = 0',
         lambda df: (df['overtime_pay'] > 0) & (df['overtime_hours'].fillna(0) == 0)),

        ('PAY_GROSSNET_CALC_MISMATCH',
         Scope.PAYROLL, 'Payroll Transactions', 'Validity', 'Medium',
         'Gross pay minus recorded deductions does not equal net pay',
         'Net pay must equal gross pay minus tax, National Insurance, pension, and other deductions, within normal rounding tolerance. '
         'A transaction outside this tolerance means one of the component figures was overwritten or calculated independently of the others. '
         'The payslip shown to the employee will not add up, which is one of the most common sources of employee payroll queries.',
         'Recalculate the transaction from its component figures and correct whichever field does not reconcile.',
         'payroll_transactions', None,
         'WHERE ABS(gross_pay - (tax_deducted + ni_deducted + pension_deducted + other_deductions) - net_pay) > 1.00',
         lambda df: (
             (df['gross_pay'] - (df['tax_deducted'] + df['ni_deducted'] + df['pension_deducted'] + df['other_deductions'].fillna(0)) - df['net_pay']).abs()
             > PayrollConfig.CALC_TOLERANCE_GBP
         )),

        ('PAY_BANK_MISMATCH',
         Scope.PAYROLL, 'Payroll Transactions', 'Consistency', 'Medium',
         'Payroll transaction\'s bank details differ from the employee master record',
         'Where both the payroll transaction and the employee master have bank details populated, they should match. '
         'A mismatch means either the transaction was paid to an out-of-date account, or the employee master was updated after this transaction was already processed. '
         'Either way, the payment may not have reached the employee\'s current account.',
         'Confirm which bank details are current with the employee, and correct whichever record is out of date.',
         'payroll_transactions', 'employee_master',
         'WHERE bank_account/sort_code differ from the matching employee_master record',
         lambda df, frames: _bank_mismatch(df, frames)),

        ('PAY_ZERO_NET_ACTIVE',
         Scope.PAYROLL, 'Payroll Transactions', 'Validity', 'Medium',
         'Payroll transaction has a positive gross pay but a net pay of zero or less',
         'A transaction with meaningful gross pay should not result in a net pay of zero or less once normal deductions are applied. '
         'This pattern usually means a deduction was set too high, entered as the wrong figure, or duplicated across two fields. '
         'An employee who worked and earned gross pay but receives nothing will raise this as an urgent payroll query.',
         'Review the individual deduction components on this transaction and correct whichever one is inflated.',
         'payroll_transactions', None,
         'WHERE gross_pay > 0 AND net_pay <= 0',
         lambda df: (df['gross_pay'] > 0) & (df['net_pay'] <= 0)),

        ('PAY_STALE_PENDING',
         Scope.PAYROLL, 'Payroll Transactions', 'Timeliness', 'Medium',
         'Payroll transaction has been stuck in Pending status for more than a week past its pay date',
         'A payroll transaction should move out of Pending status at or shortly after its scheduled pay date. '
         'A transaction still Pending more than a week later suggests the payment failed, was held, or was never released to the bank. '
         'The longer this goes unresolved, the more likely the affected employee has genuinely not been paid.',
         'Investigate why the transaction did not process and either release the payment or escalate to payroll operations.',
         'payroll_transactions', None,
         "WHERE status = 'Pending' AND pay_date < today - 7 days",
         lambda df: (df['status'] == 'Pending') & (df['pay_date'] < (pd.Timestamp.now() - pd.Timedelta(days=PayrollConfig.STALE_PENDING_DAYS)))),

        ('PAY_FUTURE_PAYDATE',
         Scope.PAYROLL, 'Payroll Transactions', 'Validity', 'Low',
         'Payroll transaction has a pay date in the future',
         'A processed or pending payroll transaction should not carry a pay date beyond the current pay cycle. '
         'A future pay date on an already-created transaction usually means it was set up against the wrong pay period. '
         'Left unnoticed, this transaction could be missed entirely by the run it was actually meant for.',
         'Confirm the intended pay period with payroll operations and correct the pay date.',
         'payroll_transactions', None,
         'WHERE pay_date > today',
         lambda df: df['pay_date'] > pd.Timestamp.now()),

    ]
