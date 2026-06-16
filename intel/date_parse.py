# -*- coding: utf-8 -*-
"""发布时间文本 → 日期级 ISO（YYYY-MM-DD）。"""
import re
from datetime import datetime, timedelta

from intel.time_util import anchor_date


_DATE_RE = re.compile(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})')
_MD_RE = re.compile(r'(?<!\d)(\d{1,2})[-/](\d{1,2})(?!\d)')
_REL_DAYS_RE = re.compile(r'(\d+)\s*天前')
_REL_HOURS_RE = re.compile(r'(\d+)\s*小时前')
_REL_MINUTES_RE = re.compile(r'(\d+)\s*分钟前')


def _parse_anchor(anchor_date_text):
    return anchor_date(anchor_date_text)


def _fmt_date(d):
    return d.strftime('%Y-%m-%d')


def parse_published_date(text, anchor_date=None):
    """
    解析发布时间为 YYYY-MM-DD。
    返回 (date_str, quality) 其中 quality 为 absolute|relative|missing。
    """
    raw = (text or '').strip()
    if not raw:
        return '', 'missing'

    anchor = _parse_anchor(anchor_date)

    m = _DATE_RE.search(raw)
    if m:
        try:
            d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
            return _fmt_date(d), 'absolute'
        except ValueError:
            pass

    m = _MD_RE.search(raw)
    if m:
        try:
            month, day = int(m.group(1)), int(m.group(2))
            year = anchor.year
            d = datetime(year, month, day).date()
            if d > anchor:
                d = datetime(year - 1, month, day).date()
            return _fmt_date(d), 'absolute'
        except ValueError:
            pass

    if raw in ('今天', '刚刚', '刚才'):
        return _fmt_date(anchor), 'relative'
    if raw == '昨天':
        return _fmt_date(anchor - timedelta(days=1)), 'relative'
    if raw == '前天':
        return _fmt_date(anchor - timedelta(days=2)), 'relative'

    m = _REL_DAYS_RE.search(raw)
    if m:
        days = int(m.group(1))
        return _fmt_date(anchor - timedelta(days=days)), 'relative'

    m = _REL_HOURS_RE.search(raw)
    if m:
        hours = int(m.group(1))
        if hours >= 24:
            return _fmt_date(anchor - timedelta(days=hours // 24)), 'relative'
        return _fmt_date(anchor), 'relative'

    m = _REL_MINUTES_RE.search(raw)
    if m:
        return _fmt_date(anchor), 'relative'

    return '', 'missing'


def age_days(published_at, anchor_date=None):
    """published_at (YYYY-MM-DD) 距 anchor 的天数；无法解析返回 None。"""
    pub, _ = parse_published_date(published_at, anchor_date)
    if not pub:
        pub = (published_at or '').strip()
    if not pub or len(pub) < 10:
        return None
    try:
        pub_d = datetime.strptime(pub[:10], '%Y-%m-%d').date()
    except ValueError:
        return None
    anchor = _parse_anchor(anchor_date)
    return (anchor - pub_d).days
