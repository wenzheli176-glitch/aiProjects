# -*- coding: utf-8 -*-
"""合作方 × 数据源超时解析。"""
from config import cfg

from intel.matcher import partner_search_keywords


def _default_for_source(source_id):
    sid = (source_id or '').strip().lower()
    if sid == 'xhs':
        return max(60, int(cfg('xhs', 'keyword_timeout_sec', default=3600) or 3600))
    if sid == 'heimao':
        return max(60, int(cfg('heimao', 'partner_timeout_sec', default=3600) or 3600))
    return max(60, int(cfg('monitor', 'min_crawl_timeout_sec', default=1800) or 1800))


def partners_for_keyword(keyword, partners):
    kw = (keyword or '').strip()
    if not kw:
        return []
    matched = []
    for p in partners or []:
        if kw in partner_search_keywords(p):
            matched.append(p)
    return matched


def resolve_source_timeout_sec(source_id, partners, keyword=None, partner=None, default=None):
    """
    解析单 keyword / 单合作方在某源上的最大 wall-clock 超时（秒）。
    多合作方共享 keyword 时取各源配置的最大值。
    """
    base = default if default is not None else _default_for_source(source_id)
    best = int(base)
    candidates = []
    if partner:
        candidates.append(partner)
    if keyword:
        candidates.extend(partners_for_keyword(keyword, partners))
    seen = set()
    for p in candidates:
        pid = p.get('id')
        if pid in seen:
            continue
        seen.add(pid)
        st = p.get('source_timeouts') or {}
        val = st.get(source_id)
        if val is None:
            continue
        try:
            best = max(best, int(val))
        except (TypeError, ValueError):
            pass
    return max(60, best)
