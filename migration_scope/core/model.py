"""
Core vocabulary shared by every object: layers, classifications, issue types,
decision types and the Rule definition.
"""
from dataclasses import dataclass, field

# Pipeline layers, in order. Every record passes through each; each is kept.
LAYERS = ['Population', 'Categorised', 'Duplicates', 'Scoped', 'Open items', 'Data quality']

# Classifications
KEEP, FIX, MONITOR, CLOSE = 'Keep', 'Fix', 'Monitor', 'Close'
HOLD_NONCOMMERCIAL = 'Held: non-commercial'
HOLD_POLICY = 'Held: policy decision'
OUT_OF_SCOPE = 'Not in scope (closed in Unit4)'
NOT_IN_EXTRACT = 'Not in latest extract'

CLASSIFICATIONS = [KEEP, FIX, MONITOR, CLOSE, HOLD_NONCOMMERCIAL, HOLD_POLICY, OUT_OF_SCOPE, NOT_IN_EXTRACT]
IN_SCOPE = [KEEP, FIX, MONITOR]          # what we'd hand the SI today
EXCLUDED = [CLOSE, OUT_OF_SCOPE, NOT_IN_EXTRACT]
HELD = [HOLD_NONCOMMERCIAL, HOLD_POLICY]

# Issue types (DQ tags on records)
ISSUE_TYPES = ['Completeness', 'Validity', 'Consistency', 'Duplicate']

# Decision types. family groups decisions that supersede each other.
DECISIONS = {
    # value: (label, family, applies_to)
    'AGREE':             ('Agree with recommendation', 'scope', 'record'),
    'KEEP':              ('Keep: include in scope', 'scope', 'record'),
    'CLOSE':             ('Close: exclude from scope', 'scope', 'record'),
    'WILL_FIX':          ('Will fix in Unit4', 'scope', 'record'),
    'ACCEPT_AS_IS':      ('Accept as is (no fix needed)', 'scope', 'record'),
    'CONFIRM_PREFERRED': ('Confirm as preferred record', 'dup', 'record'),
    'NOT_DUPLICATE':     ('Not a duplicate', 'dup', 'record'),
    'SAME_SUPPLIER':     ('Same supplier', 'pair', 'pair'),
    'DIFFERENT_SUPPLIER': ('Different supplier', 'pair', 'pair'),
    'MIGRATE':           ('Migrate this item', 'item', 'item'),
    'DONT_MIGRATE':      ("Don't migrate this item", 'item', 'item'),
}
DECISION_BY_LABEL = {v[0]: k for k, v in DECISIONS.items()}

# Decision status shown on each record
NO_DECISION_NEEDED = 'No decision needed'
AWAITING = 'Awaiting decision'
DECIDED = 'Decided'
OVERRIDDEN = 'Overridden by steward'


# Plain-English names for parameter values shown to stewards
FRIENDLY = {'vat': 'VAT number', 'company_no': 'company number', 'bank': 'bank details',
            'name_postcode': 'name and postcode'}


@dataclass
class Rule:
    """One configurable rule. The description is plain English with {param}
    placeholders, filled from the current parameters when shown."""
    id: str
    name: str
    description: str
    object: str
    layer: str
    params: list = field(default_factory=list)   # parameter keys this rule uses
    version: str = '1.0'
    active: bool = True
    outcome: str = ''                            # classification or tag it produces

    def text(self, params):
        def show(x):
            if isinstance(x, dict):
                return ', '.join(f'{k} ({v})' for k, v in x.items())
            if isinstance(x, list):
                return ', '.join(FRIENDLY.get(i, str(i)) for i in x)
            return str(x)

        values = {}
        for k in self.params:
            v = params.get(k)
            if isinstance(v, dict) and all(h in ('HOC', 'HOL') for h in v):
                v = '; '.join(f"{'HoC' if h == 'HOC' else 'HoL'}: {show(x)}" for h, x in v.items() if x)
            else:
                v = show(v)
            values[k] = v
        try:
            return self.description.format(**values)
        except (KeyError, IndexError):
            return self.description
