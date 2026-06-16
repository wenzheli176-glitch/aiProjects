# -*- coding: utf-8 -*-
"""AI relevance 时效后处理降档。"""
from config import cfg

from intel.date_parse import age_days

_RELEVANCE_ORDER = ['noise', 'low', 'medium', 'high']


def recency_cfg():
    ac = cfg('analysis') or {}
    rc = dict(ac.get('recency') or {})
    rc.setdefault('enabled', True)
    rc.setdefault('downgrade_days_high_to_medium', 30)
    rc.setdefault('downgrade_days_medium_to_low', 90)
    rc.setdefault('confidence_downgrade_threshold', 0.4)
    return rc


def _downgrade_one(rel):
    rel = (rel or 'medium').strip().lower()
    if rel not in _RELEVANCE_ORDER:
        rel = 'medium'
    idx = _RELEVANCE_ORDER.index(rel)
    if idx <= 0:
        return rel
    return _RELEVANCE_ORDER[idx - 1]


def apply_recency_relevance(relevance, confidence, published_at, captured_at, config=None):
    """
    对 LLM relevance 应用时效与 confidence 降档。
    返回 (final_relevance, relevance_llm)。
    """
    rc = config or recency_cfg()
    rel = (relevance or 'medium').strip().lower()
    if rel not in _RELEVANCE_ORDER:
        rel = 'medium'
    relevance_llm = rel

    if not rc.get('enabled', True):
        return rel, relevance_llm

    days = age_days(published_at, captured_at)
    if days is not None:
        hi_med = int(rc.get('downgrade_days_high_to_medium', 30))
        med_low = int(rc.get('downgrade_days_medium_to_low', 90))
        if days > hi_med and rel == 'high':
            rel = 'medium'
        if days > med_low and rel == 'medium':
            rel = 'low'

    try:
        conf = float(confidence)
    except (TypeError, ValueError):
        conf = 0.5
    threshold = float(rc.get('confidence_downgrade_threshold', 0.4))
    if conf < threshold and rel != 'noise':
        rel = _downgrade_one(rel)

    return rel, relevance_llm


def clamp_confidence(value, default=0.5):
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = default
    return max(0.0, min(1.0, v))
