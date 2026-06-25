# -*- coding: utf-8 -*-
"""合作方列表 stats 与 context 计数一致。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intel.db import (
    create_monitor_task,
    create_partner,
    delete_monitor_task,
    delete_partner,
    get_connection,
    get_partner_drilldown_context,
    insert_intel_record,
    insert_raw_records,
    list_partners_with_stats,
)


def _cleanup(partner_id, task_ids):
    conn = get_connection()
    if partner_id:
        conn.execute('DELETE FROM intel_records WHERE partner_id = ?', (partner_id,))
        conn.execute('DELETE FROM raw_records WHERE partner_id = ?', (partner_id,))
        conn.commit()
        delete_partner(partner_id)
    for tid in task_ids or []:
        delete_monitor_task(tid)


def test_list_stats_matches_context():
    p = create_partner({'name': '__list_stats__', 'enabled': True})
    t = create_monitor_task({'name': 'stats task', 'partner_ids': [p['id']]})
    try:
        insert_raw_records(
            t['id'], p['id'], 'heimao', 'kw',
            [{'title': 'r1', 'url': 'http://example.com/1', 'time': '2026-01-01'}],
        )
        insert_intel_record({
            'task_id': t['id'],
            'partner_id': p['id'],
            'partner_name': p['name'],
            'source': 'heimao',
            'relevance': 'high',
        })
        insert_intel_record({
            'task_id': t['id'],
            'partner_id': p['id'],
            'partner_name': p['name'],
            'source': 'heimao',
            'relevance': 'low',
        })
        ctx = get_partner_drilldown_context(p['id'])
        rows = list_partners_with_stats()
        row = next(x for x in rows if x['id'] == p['id'])
        st = row['stats']
        assert st['default_task_id'] == ctx['default_task_id'] == t['id']
        assert st['intel_total'] == ctx['counts']['intel_total'] == 2
        assert st['intel_medium_plus'] == ctx['counts']['intel_medium_plus'] == 1
        assert st['raw_total'] == ctx['counts']['raw_total'] == 1

        from crawler_web import app

        r = app.test_client().get('/api/partners')
        assert r.status_code == 200
        data = r.get_json()
        api_row = next(x for x in data['partners'] if x['id'] == p['id'])
        assert api_row['stats']['intel_medium_plus'] == 1
        print('OK test_list_stats_matches_context')
    finally:
        _cleanup(p['id'], [t['id']])


if __name__ == '__main__':
    test_list_stats_matches_context()
    print('ALL OK')
