# -*- coding: utf-8 -*-
"""合作方别名匹配与 subject_hits。"""
import re


def partner_search_keywords(partner):
    words = [partner.get('name') or '']
    words.extend(partner.get('aliases') or [])
    words.extend(partner.get('monitor_keywords') or [])
    seen = set()
    out = []
    for w in words:
        w = (w or '').strip()
        if w and w not in seen:
            seen.add(w)
            out.append(w)
    return out


def match_partner(normalized, partner, task_partner_id=None):
    """返回 subject_hits 列表与是否命中排除词。"""
    text = '%s\n%s' % (normalized.get('title') or '', normalized.get('body') or '')
    text_lower = text.lower()
    hits = []
    for kw in partner_search_keywords(partner):
        if not kw:
            continue
        if kw.lower() in text_lower or kw in text:
            hits.append(kw)
    excluded = False
    for ex in partner.get('exclude_words') or []:
        ex = (ex or '').strip()
        if ex and (ex.lower() in text_lower or ex in text):
            excluded = True
            break
    return {
        'partner_id': partner['id'],
        'partner_name': partner['name'],
        'subject_hits': hits,
        'excluded': excluded,
        'matched': bool(hits) or (task_partner_id == partner['id']),
    }


def match_best_partner(normalized, partners, default_partner_id=None):
    best = None
    best_len = -1
    for p in partners:
        m = match_partner(normalized, p)
        if m['excluded'] and not m['subject_hits']:
            continue
        longest = max((len(h) for h in m['subject_hits']), default=0)
        if m['subject_hits'] and longest > best_len:
            best_len = longest
            best = m
    if best:
        return best
    if default_partner_id:
        for p in partners:
            if p['id'] == default_partner_id:
                return {
                    'partner_id': p['id'],
                    'partner_name': p['name'],
                    'subject_hits': [],
                    'excluded': False,
                    'matched': True,
                }
    if partners:
        p = partners[0]
        return {
            'partner_id': p['id'],
            'partner_name': p['name'],
            'subject_hits': [],
            'excluded': False,
            'matched': False,
        }
    return {
        'partner_id': None,
        'partner_name': '',
        'subject_hits': [],
        'excluded': False,
        'matched': False,
    }


def export_tier_for_match(match_result):
    if match_result.get('excluded') and not match_result.get('subject_hits'):
        return 'exclude'
    if match_result.get('subject_hits'):
        return 'include'
    return 'review'
