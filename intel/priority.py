# -*- coding: utf-8 -*-
"""合作方 P0/P1/P2 自动定级。"""
import json
from datetime import datetime, timedelta

from intel.db import get_connection, get_partner, update_partner_priority
from intel.time_util import app_tz

_RELEVANCE_RANK = {'high': 3, 'medium': 2, 'low': 1, 'noise': 0}
_SEVERE_RISK = {'监管', '欺诈', '重大质量', '法律诉讼', '财务风险'}


def refresh_auto_priorities(days_high=7, days_quiet=30, high_threshold=2):
    conn = get_connection()
    now = datetime.now(app_tz())
    since_high = (now - timedelta(days=days_high)).strftime('%Y-%m-%dT%H:%M:%S')
    since_quiet = (now - timedelta(days=days_quiet)).strftime('%Y-%m-%dT%H:%M:%S')
    partners = conn.execute(
        "SELECT id, priority_source FROM partners WHERE enabled=1"
    ).fetchall()
    updated = []
    for prow in partners:
        if (prow['priority_source'] or 'auto') == 'business':
            continue
        pid = prow['id']
        high_rows = conn.execute(
            """
            SELECT COUNT(*) AS c FROM intel_records
            WHERE partner_id=? AND is_duplicate=0 AND relevance='high'
              AND created_at >= ?
            """,
            (pid, since_high),
        ).fetchone()
        severe_rows = conn.execute(
            """
            SELECT risk_types_json FROM intel_records
            WHERE partner_id=? AND is_duplicate=0 AND created_at >= ?
            """,
            (pid, since_high),
        ).fetchall()
        severe_count = 0
        for sr in severe_rows:
            try:
                risks = json.loads(sr['risk_types_json'] or '[]')
            except Exception:
                risks = []
            if any(r in _SEVERE_RISK for r in risks):
                severe_count += 1
        medium_plus_recent = conn.execute(
            """
            SELECT COUNT(*) AS c FROM intel_records
            WHERE partner_id=? AND is_duplicate=0
              AND relevance IN ('high','medium') AND created_at >= ?
            """,
            (pid, since_quiet),
        ).fetchone()
        new_tier = 'P1'
        reason = 'auto default'
        if int(high_rows['c'] or 0) >= high_threshold or severe_count >= 1:
            new_tier = 'P0'
            reason = 'recent high/severe intel'
        elif int(medium_plus_recent['c'] or 0) == 0:
            new_tier = 'P2'
            reason = 'no medium+ in %dd' % days_quiet
        p = get_partner(pid)
        if p and (p.get('priority_tier') or 'P1') != new_tier:
            update_partner_priority(pid, new_tier, source='auto', reason=reason)
            updated.append({'partner_id': pid, 'tier': new_tier, 'reason': reason})
    return updated
