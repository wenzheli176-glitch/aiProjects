# -*- coding: utf-8 -*-
"""按 industry_cohort 合并监测关键词并分批。"""
from config import cfg

from intel.matcher import partner_search_keywords

_TIER_ORDER = {'P0': 0, 'P1': 1, 'P2': 2}


def _partner_cohort(partner):
    cohort = (partner.get('industry_cohort') or '').strip()
    if cohort:
        return cohort
    return 'partner:%s' % partner.get('id')


def build_keyword_batches(partners, max_keywords=None):
    max_kw = max_keywords
    if max_kw is None:
        max_kw = int(cfg('monitor', 'industry_batch_max_keywords', default=5) or 5)
    max_kw = max(1, int(max_kw))

    cohort_map = {}
    for p in partners:
        cohort = _partner_cohort(p)
        cohort_map.setdefault(cohort, {'cohort': cohort, 'partners': [], 'keywords': []})
        cohort_map[cohort]['partners'].append(p)
        seen = set(cohort_map[cohort]['keywords'])
        for kw in partner_search_keywords(p):
            if kw and kw not in seen:
                seen.add(kw)
                cohort_map[cohort]['keywords'].append(kw)

    batches = []
    for cohort, info in sorted(cohort_map.items(), key=lambda x: _cohort_sort_key(x[1]['partners'])):
        kws = info['keywords']
        if not kws:
            continue
        for i in range(0, len(kws), max_kw):
            batches.append({
                'cohort': cohort,
                'keywords': kws[i:i + max_kw],
                'partners': info['partners'],
                'priority_tier': _cohort_tier(info['partners']),
            })
    return batches


def _cohort_tier(partners):
    tiers = [p.get('priority_tier') or 'P1' for p in partners]
    for t in ('P0', 'P1', 'P2'):
        if t in tiers:
            return t
    return 'P1'


def _cohort_sort_key(partners):
    tier = _cohort_tier(partners)
    return (_TIER_ORDER.get(tier, 1), min(p.get('id') or 0 for p in partners))


def sort_batches_by_quota(batches):
    quota = cfg('monitor', 'priority_quota', default={}) or {}
    p0 = float(quota.get('P0', 0.5))
    p1 = float(quota.get('P1', 0.3))
    p2 = float(quota.get('P2', 0.2))
    total = p0 + p1 + p2
    if total <= 0:
        p0, p1, p2, total = 0.5, 0.3, 0.2, 1.0
    p0, p1, p2 = p0 / total, p1 / total, p2 / total

    by_tier = {'P0': [], 'P1': [], 'P2': []}
    for b in batches:
        tier = b.get('priority_tier') or 'P1'
        if tier not in by_tier:
            tier = 'P1'
        by_tier[tier].append(b)

    out = []
    pools = [
        ('P0', by_tier['P0'], p0),
        ('P1', by_tier['P1'], p1),
        ('P2', by_tier['P2'], p2),
    ]
    idx = {t: 0 for t, _, _ in pools}
    while any(idx[t] < len(items) for t, items, _ in pools):
        for tier, items, _weight in pools:
            if idx[tier] < len(items):
                out.append(items[idx[tier]])
                idx[tier] += 1
    return out
