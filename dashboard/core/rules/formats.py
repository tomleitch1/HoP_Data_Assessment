"""
Shared identifier formats used by more than one rule file (and by the Migration Scope engine,
which runs the supplier rules unchanged). Change a format here and every test picks it up.
"""
import pandas as pd

# Companies House number prefixes. Each is followed by 6 digits (e.g. SC123456).
#   OC/SO/NC  LLPs (England & Wales / Scotland / NI)       SC/NI  Scottish / Northern Ireland companies
#   LP/SL/NL  limited partnerships                         FC/SF/NF  overseas companies
#   RC/SR/NR  royal charter bodies                         ZC/SZ/NZ  unregistered companies
#   IP/SP/NP  industrial & provident societies              RS  registered societies
#   GE/GS/GN  European economic interest groupings          SE/ES  European public companies
#   CE/CS     charitable incorporated organisations        AC/SA/NA  assurance companies
#   IC/SI/NV  investment companies                          OE  overseas entities
#   FE/SG     other overseas / Scottish qualifying partnerships
COMPANY_NO_PREFIXES = (
    'OC', 'SO', 'NC', 'SC', 'NI', 'LP', 'SL', 'NL', 'FC', 'SF', 'NF', 'RC', 'SR', 'NR',
    'ZC', 'SZ', 'NZ', 'IP', 'SP', 'NP', 'RS', 'GE', 'GS', 'GN', 'SE', 'ES', 'CE', 'CS',
    'AC', 'SA', 'NA', 'IC', 'SI', 'NV', 'OE', 'FE', 'SG',
)

_PREFIXES = '|'.join(COMPANY_NO_PREFIXES)
COMPANY_NO_PATTERN = (
    r'^(?:'
    r'\d{8}'                       # 8 digits, most UK companies (01234567)
    rf'|(?:{_PREFIXES})\d{{6}}'    # 2-letter prefix + 6 digits (SC123456, OC301234)
    r'|(?:RS|IP|SP|NP)\d{4,5}[A-Z]{1,3}'  # registered societies / mutuals (RS12345C)
    r'|R\d{7}'                     # pre-1922 Northern Ireland companies (R0000123)
    r')$'
)
COMPANY_NO_DESCRIPTION = ('8 digits (01234567), a 2-letter Companies House prefix and 6 digits '
                          '(SC123456, OC301234, NI012345), or a registered society number (RS12345C)')


def company_no_valid(s: pd.Series) -> pd.Series:
    """True where a company number matches a Companies House format.
    Case and spaces are ignored ('sc 123456' is valid). Blank values return False."""
    v = s.astype('string').str.upper().str.replace(r'\s+', '', regex=True)
    return v.str.match(COMPANY_NO_PATTERN, na=False).astype(bool)
