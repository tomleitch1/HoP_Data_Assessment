"""
Employee Master DQ checks — Royal Mail HR & Payroll bid-demo dashboard.

Tuple format (mirrors the Parliament finance dashboard's rule tuples):
  (check_id, Scope, object, dimension, severity, description, intent,
   remediation, source_table, joined_table_or_None, sql_equivalent, lambda)

The lambda receives the employee_master DataFrame already filtered to this
check's population (active-only for most completeness/validity checks; full
population for uniqueness and the manager-hierarchy check). It returns a
boolean mask of FAILING records.
"""

import pandas as pd

from hr_dashboard.core.config import Scope

# Checks that apply to active employees only — a leaver's blank tax code or
# missing bank details is expected once they've left, not a data issue.
ACTIVE_ONLY_CHECKS = {
    'EMP_NI_MISSING', 'EMP_NI_FORMAT', 'EMP_BANK_MISSING',
    'EMP_DOB_MISSING', 'EMP_DOB_INVALID', 'EMP_EMAIL_MISSING',
    'EMP_POSTCODE_FORMAT', 'EMP_TAX_CODE_MISSING',
}

_INVALID_NI_PREFIXES = {'BG', 'GB', 'NK', 'KN', 'TN', 'NT', 'ZZ'}
_NI_REGEX = r'^[A-Za-z]{2}\d{6}[A-Za-z]$'
_POSTCODE_REGEX = r'^[A-Za-z]{1,2}\d[A-Za-z\d]?\s?\d[A-Za-z]{2}$'


def _ni_malformed(series: pd.Series) -> pd.Series:
    present = series.notna() & (series.astype(str).str.strip() != '')
    matches_shape = series.astype(str).str.strip().str.match(_NI_REGEX, na=False)
    bad_prefix = series.astype(str).str.strip().str.upper().str[:2].isin(_INVALID_NI_PREFIXES)
    return present & (~matches_shape | bad_prefix)


def get_employee_checks():
    return [

        ('EMP_NI_MISSING',
         Scope.EMPLOYEE, 'Employee Master', 'Completeness', 'Critical',
         'Active employee has no National Insurance number',
         'Every active employee must have a National Insurance number recorded. '
         'Payroll cannot calculate NI contributions or submit HMRC Real Time Information without it. '
         'A missing NI number will cause that employee\'s payslip to fail processing on the next run.',
         'Obtain the employee\'s NI number from HR records or ask the employee directly, and update the record before the next payroll run.',
         'employee_master', None,
         "WHERE employment_status = 'Active' AND (ni_number IS NULL OR TRIM(ni_number) = '')",
         lambda df: df['ni_number'].isna() | (df['ni_number'].astype(str).str.strip() == '')),

        ('EMP_NI_FORMAT',
         Scope.EMPLOYEE, 'Employee Master', 'Validity', 'High',
         'Active employee\'s National Insurance number is not a valid format',
         'A National Insurance number must follow the standard two-letter, six-digit, one-letter pattern and must not use a reserved invalid prefix. '
         'HMRC will reject RTI submissions that carry a malformed NI number. '
         'An invalid NI number at the next filing deadline puts the whole payroll submission at risk, not just this one employee\'s record.',
         'Correct the NI number against the employee\'s official documentation (P45, payslip, or NI card).',
         'employee_master', None,
         "WHERE employment_status = 'Active' AND ni_number NOT LIKE valid pattern",
         lambda df: _ni_malformed(df['ni_number'])),

        ('EMP_BANK_MISSING',
         Scope.EMPLOYEE, 'Employee Master', 'Completeness', 'Critical',
         'Active employee is missing bank account or sort code details',
         'Every active employee must have both a bank account number and sort code recorded for BACS payment. '
         'Without both fields, payroll has no way to pay that employee on the scheduled pay date. '
         'This is one of the highest-impact gaps in the whole dataset because it directly stops a payment.',
         'Collect the employee\'s current bank details and update the record before the next payroll cut-off.',
         'employee_master', None,
         "WHERE employment_status = 'Active' AND (bank_account IS NULL OR sort_code IS NULL)",
         lambda df: df['bank_account'].isna() | (df['bank_account'].astype(str).str.strip() == '')
                    | df['sort_code'].isna() | (df['sort_code'].astype(str).str.strip() == '')),

        ('EMP_DOB_MISSING',
         Scope.EMPLOYEE, 'Employee Master', 'Completeness', 'Medium',
         'Active employee has no date of birth recorded',
         'Every active employee must have a date of birth on file. '
         'Payroll uses date of birth to apply the correct National Insurance and pension auto-enrolment rules by age band. '
         'A missing date of birth means those age-driven calculations default incorrectly rather than failing loudly.',
         'Obtain the employee\'s date of birth from HR onboarding records and update the record.',
         'employee_master', None,
         "WHERE employment_status = 'Active' AND dob IS NULL",
         lambda df: df['dob'].isna()),

        ('EMP_DOB_INVALID',
         Scope.EMPLOYEE, 'Employee Master', 'Validity', 'Medium',
         'Active employee\'s date of birth implies an age outside the plausible working range (under 16 or over 75)',
         'An active employee\'s calculated age should fall within a plausible working range. '
         'A date of birth outside this range almost always indicates a data entry error rather than a genuine employee of that age. '
         'Age-driven payroll calculations such as NI category and pension auto-enrolment will be wrong for as long as this is uncorrected.',
         'Verify the correct date of birth against the employee\'s personnel file and correct the record.',
         'employee_master', None,
         "WHERE employment_status = 'Active' AND (age(dob) < 16 OR age(dob) > 75)",
         lambda df: df['dob'].notna() & (
             ((pd.Timestamp.now() - df['dob']).dt.days / 365.25 < 16) |
             ((pd.Timestamp.now() - df['dob']).dt.days / 365.25 > 75)
         )),

        ('EMP_START_AFTER_LEAVE',
         Scope.EMPLOYEE, 'Employee Master', 'Validity', 'High',
         'Employee\'s start date is after their leaving date',
         'A leaver\'s start date must be on or before their leaving date. '
         'A start date recorded after the leaving date means the employment period is logically impossible and cannot be relied on for continuous service calculations. '
         'Length-of-service figures (pension, redundancy, statutory entitlement) built on this record will be wrong.',
         'Check both dates against the employee\'s contract and correct whichever one was entered in error.',
         'employee_master', None,
         'WHERE leaving_date IS NOT NULL AND start_date > leaving_date',
         lambda df: df['start_date'].notna() & df['leaving_date'].notna() & (df['start_date'] > df['leaving_date'])),

        ('EMP_DUP_NI',
         Scope.EMPLOYEE, 'Employee Master', 'Uniqueness', 'Critical',
         'Duplicate National Insurance number across employee records',
         'Each National Insurance number must belong to exactly one employee. '
         'Two employee records sharing the same NI number means either a duplicate record exists or the number was mistyped from a genuinely different employee. '
         'HMRC will reject or misattribute RTI submissions where the same NI number appears against more than one payroll record.',
         'Investigate both records. Correct the mistyped NI number, or merge the records if this is a genuine duplicate employee.',
         'employee_master', None,
         'WHERE ni_number appears more than once (excluding blanks)',
         lambda df: df['ni_number'].notna() & (df['ni_number'].astype(str).str.strip() != '')
                    & df.duplicated(subset=['ni_number'], keep=False)),

        ('EMP_DUP_EMPID',
         Scope.EMPLOYEE, 'Employee Master', 'Uniqueness', 'Critical',
         'Duplicate employee ID',
         'Employee ID is the primary key of the employee master and must be unique. '
         'A duplicate employee ID means the same person has two conflicting records, or two different people have been assigned the same identifier. '
         'Any system loading this data by employee ID will either reject the load or silently overwrite one record with the other.',
         'Investigate each duplicate pair and merge or renumber the records so each employee has exactly one ID.',
         'employee_master', None,
         'WHERE employee_id appears more than once',
         lambda df: df.duplicated(subset=['employee_id'], keep=False)),

        ('EMP_MANAGER_ORPHAN',
         Scope.EMPLOYEE, 'Employee Master', 'Consistency', 'High',
         'Employee\'s manager ID does not resolve to another employee record',
         'Where an employee has a manager assigned, that manager ID must exist as a valid employee record in the same dataset. '
         'An orphaned manager reference breaks the reporting line for org charts, approval routing, and management-layer headcount reporting. '
         'This typically happens when a manager leaves and their direct reports are not reassigned.',
         'Reassign the affected employees to a valid, current manager, or clear the manager_id if the role is temporarily vacant.',
         'employee_master', None,
         'WHERE manager_id IS NOT NULL AND manager_id NOT IN (SELECT employee_id FROM employee_master)',
         lambda df: (
             df['manager_id'].notna() & (df['manager_id'].astype(str).str.strip() != '')
             & ~df['manager_id'].isin(df['employee_id'])
         )),

        ('EMP_EMAIL_MISSING',
         Scope.EMPLOYEE, 'Employee Master', 'Completeness', 'Low',
         'Active employee has no email address on file',
         'Every active employee should have a work email address recorded. '
         'HR and payroll use email as the primary channel for payslip notifications and policy communications. '
         'An employee with no email on file will not receive these notifications and may raise avoidable queries.',
         'Obtain the employee\'s work email address from IT provisioning records and update the record.',
         'employee_master', None,
         "WHERE employment_status = 'Active' AND (email IS NULL OR TRIM(email) = '')",
         lambda df: df['email'].isna() | (df['email'].astype(str).str.strip() == '')),

        ('EMP_POSTCODE_FORMAT',
         Scope.EMPLOYEE, 'Employee Master', 'Validity', 'Low',
         'Active employee\'s postcode is not a valid UK postcode format',
         'Where a postcode is populated it must follow standard UK postcode formatting. '
         'HR correspondence and statutory postal communications sent to a malformed postcode may not be delivered. '
         'A malformed postcode usually means the address was entered as free text rather than validated at capture.',
         'Correct the postcode against the employee\'s current address on file.',
         'employee_master', None,
         "WHERE employment_status = 'Active' AND postcode NOT LIKE valid UK postcode pattern",
         lambda df: df['postcode'].notna() & (df['postcode'].astype(str).str.strip() != '')
                    & ~df['postcode'].astype(str).str.strip().str.match(_POSTCODE_REGEX, na=False)),

        ('EMP_TAX_CODE_MISSING',
         Scope.EMPLOYEE, 'Employee Master', 'Completeness', 'High',
         'Active employee has no tax code recorded',
         'Every active employee must have a current tax code on file. '
         'Payroll defaults to an emergency tax basis when no tax code is present, which almost always over-taxes the employee. '
         'This directly affects take-home pay on the next payslip, not just a back-office reporting field.',
         'Obtain the employee\'s current tax code from their P45/P6 notice or HMRC and update the record before the next pay run.',
         'employee_master', None,
         "WHERE employment_status = 'Active' AND (tax_code IS NULL OR TRIM(tax_code) = '')",
         lambda df: df['tax_code'].isna() | (df['tax_code'].astype(str).str.strip() == '')),

    ]
