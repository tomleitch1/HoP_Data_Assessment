"""
Standardised layer: cleaned formats used for matching and testing.
Never overwrites raw values; every function returns a new series.
"""
import re
import pandas as pd

_LEGAL_SUFFIXES = {
    'LIMITED': 'LTD', 'LTD': 'LTD', 'PLC': 'PLC', 'PUBLIC LIMITED COMPANY': 'PLC',
    'LLP': 'LLP', 'INCORPORATED': 'INC', 'INC': 'INC', 'COMPANY': 'CO', 'CO': 'CO',
    'CORPORATION': 'CORP', 'CORP': 'CORP', 'AND': '&',
}
ORG_MARKERS = ('LTD', 'PLC', 'LLP', 'INC', 'CORP')


def blank(s: pd.Series) -> pd.Series:
    """True where a value is missing or whitespace only."""
    return s.isna() | s.astype(str).str.strip().isin(['', 'nan', 'None', 'NaT'])


def text(s: pd.Series) -> pd.Series:
    out = s.astype(str).str.strip()
    return out.where(~blank(s), '')


def name(s: pd.Series) -> pd.Series:
    """Upper case, punctuation removed, legal suffixes unified
    ('Acme Limited.' and 'ACME LTD' both become 'ACME LTD')."""
    def one(v):
        v = re.sub(r'[^A-Z0-9& ]+', ' ', v.upper())
        words = [_LEGAL_SUFFIXES.get(w, w) for w in v.split()]
        if words[:1] == ['THE']:
            words = words[1:]
        return ' '.join(words)
    return text(s).map(lambda v: one(v) if v else '')


def name_core(s: pd.Series) -> pd.Series:
    """Standardised name without the legal suffix, for similarity matching."""
    return name(s).map(lambda v: ' '.join(w for w in v.split() if w not in ORG_MARKERS + ('CO', '&')))


def postcode(s: pd.Series) -> pd.Series:
    return text(s).str.upper().str.replace(r'\s+', '', regex=True)


def digits(s: pd.Series) -> pd.Series:
    return text(s).str.replace(r'\D', '', regex=True)


def vat(s: pd.Series) -> pd.Series:
    """GB VAT: strip prefix and spaces, keep the 9 or 12 digits."""
    v = text(s).str.upper().str.replace(r'[^A-Z0-9]', '', regex=True)
    return v.str.replace(r'^GB', '', regex=True)


def company_no(s: pd.Series) -> pd.Series:
    """Upper case, spaces and punctuation removed. Never padded: the extract holds
    leading zeros correctly, so a short number is a real data issue."""
    return text(s).str.upper().str.replace(r'[^A-Z0-9]', '', regex=True)


def iban(s: pd.Series) -> pd.Series:
    return text(s).str.upper().str.replace(r'\s+', '', regex=True)


def is_organisation_name(std_name: pd.Series) -> pd.Series:
    return std_name.str.split().map(lambda ws: any(w in ORG_MARKERS for w in ws) if isinstance(ws, list) else False)
