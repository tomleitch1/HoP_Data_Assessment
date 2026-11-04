"""
Duplicate matching, generic over any object.

Confirmed duplicates: records sharing any strong key (VAT, company number,
bank details, name + postcode) are joined into groups (union-find, so A=B on
VAT and B=C on bank puts A, B, C in one group).

Possible duplicates: similar names that aren't already in the same group.
These never change a classification on their own; a steward confirms or
rejects them.
"""
from difflib import SequenceMatcher
import numpy as np
import pandas as pd

try:
    from rapidfuzz import fuzz as _fuzz, process as _process
    _HAS_RAPIDFUZZ = True

    def similarity(a, b):
        return _fuzz.token_sort_ratio(a, b)
except ImportError:  # rapidfuzz isn't installed on every machine
    _HAS_RAPIDFUZZ = False

    def similarity(a, b):
        a, b = ' '.join(sorted(a.split())), ' '.join(sorted(b.split()))
        return SequenceMatcher(None, a, b).ratio() * 100


class _UnionFind:
    def __init__(self, items):
        self.parent = {i: i for i in items}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            # Keep the smallest key as root so group ids are stable run to run
            self.parent[max(ra, rb)] = min(ra, rb)


def key_matches(keys: pd.DataFrame, key_cols, scope_col=None):
    """Pairs of records sharing a non-blank key value.

    keys: one row per record, columns 'key' plus key_cols (and scope_col).
    Returns DataFrame(a, b, key_type, value), each pair once (a < b).
    """
    out = []
    for col in key_cols:
        sub = keys[keys[col].astype(str) != ''][['key', col] + ([scope_col] if scope_col else [])]
        grp_cols = [col] + ([scope_col] if scope_col else [])
        sub = sub.drop_duplicates(['key', col])
        multi = sub[sub.duplicated(grp_cols, keep=False)]
        if multi.empty:
            continue
        m = multi.merge(multi, on=grp_cols, suffixes=('_a', '_b'))
        m = m[m['key_a'] < m['key_b']]
        out.append(pd.DataFrame({'a': m['key_a'], 'b': m['key_b'], 'key_type': col, 'value': m[col]}))
    if not out:
        return pd.DataFrame(columns=['a', 'b', 'key_type', 'value'])
    return pd.concat(out, ignore_index=True)


def build_groups(record_keys, pairs: pd.DataFrame, extra_pairs=(), prefix='G'):
    """Union-find over pairs. Returns {record_key: group_id} for grouped records only."""
    uf = _UnionFind(record_keys)
    for a, b in list(zip(pairs['a'], pairs['b'])) + list(extra_pairs):
        if a in uf.parent and b in uf.parent:
            uf.union(a, b)
    roots = {}
    for k in record_keys:
        roots.setdefault(uf.find(k), []).append(k)
    groups = {}
    n = 0
    for root in sorted(roots):
        members = roots[root]
        if len(members) < 2:
            continue
        n += 1
        house = root.split('|')[0]
        gid = f'{prefix}-{house}-{n:04d}'
        for m in members:
            groups[m] = gid
    return groups


def possible_pairs(names: pd.DataFrame, threshold, exclude_pairs=frozenset(), same_group=None):
    """Similar names within a house. names: key, house, name_core.
    Blocks on house + first two letters to keep comparisons small."""
    same_group = same_group or {}
    out = []
    df = names[names['name_core'] != ''].copy()
    df['block'] = df['house'] + '|' + df['name_core'].str[:2]
    for _, blk in df.groupby('block'):
        if len(blk) < 2:
            continue
        keys, vals = blk['key'].tolist(), blk['name_core'].tolist()
        for i, j, score in _similar(vals, threshold):
            a, b = min(keys[i], keys[j]), max(keys[i], keys[j])
            if (a, b) in exclude_pairs:
                continue
            g = same_group.get(a)
            if g and g == same_group.get(b):
                continue
            out.append((a, b, round(score)))
    return pd.DataFrame(out, columns=['a', 'b', 'score'])


def _similar(vals, threshold):
    """(i, j, score) for every pair i < j at or above the threshold."""
    if _HAS_RAPIDFUZZ:
        m = _process.cdist(vals, vals, scorer=_fuzz.token_sort_ratio, score_cutoff=threshold)
        for i, j in zip(*np.nonzero(np.triu(m, k=1))):
            yield int(i), int(j), float(m[i, j])
        return
    for i in range(len(vals)):
        for j in range(i + 1, len(vals)):
            score = similarity(vals[i], vals[j])
            if score >= threshold:
                yield i, j, score
