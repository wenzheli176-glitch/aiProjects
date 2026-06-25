# -*- coding: utf-8 -*-
"""合作方钻取 context API：默认 task、计数、无任务空态。"""
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


def test_no_tasks():
    p = create_partner({'name': '__drilldown_no_task__', 'enabled': True})
    try:
        ctx = get_partner_drilldown_context(p['id'])
        assert ctx['default_task_id'] is None
        assert ctx['tasks'] == []
        assert ctx['counts']['raw_total'] == 0
        assert ctx['counts']['intel_total'] == 0
        assert ctx['counts']['intel_medium_plus'] == 0

        from crawler_web import app

        r = app.test_client().get('/api/partners/%d/context' % p['id'])
        assert r.status_code == 200
        data = r.get_json()
        assert data['ok'] is True
        assert data['default_task_id'] is None
        print('OK test_no_tasks')
    finally:
        _cleanup(p['id'], [])


def test_default_task_and_counts():
    p = create_partner({'name': '__drilldown_ctx__', 'enabled': True})
    t_old = create_monitor_task({'name': 'old task', 'partner_ids': [p['id']]})
    t_new = create_monitor_task({'name': 'new task', 'partner_ids': [p['id']]})
    conn = get_connection()
    conn.execute(
        'UPDATE monitor_tasks SET updated_at = ? WHERE id = ?',
        ('2020-01-01T00:00:00', t_old['id']),
    )
    conn.execute(
        'UPDATE monitor_tasks SET updated_at = ? WHERE id = ?',
        ('2026-06-01T12:00:00', t_new['id']),
    )
    conn.commit()
    try:
        insert_raw_records(
            t_new['id'], p['id'], 'heimao', 'kw',
            [{'title': 'r1', 'url': 'http://example.com/1'}],
        )
        insert_raw_records(
            t_old['id'], p['id'], 'heimao', 'kw',
            [{'title': 'r2', 'url': 'http://example.com/2'}],
        )
        insert_intel_record({
            'task_id': t_new['id'],
            'partner_id': p['id'],
            'partner_name': p['name'],
            'source': 'heimao',
            'relevance': 'high',
        })
        insert_intel_record({
            'task_id': t_old['id'],
            'partner_id': p['id'],
            'partner_name': p['name'],
            'source': 'heimao',
            'relevance': 'low',
        })

        ctx = get_partner_drilldown_context(p['id'])
        assert ctx['default_task_id'] == t_new['id']
        assert len(ctx['tasks']) == 2
        assert ctx['tasks'][0]['id'] == t_new['id']
        assert ctx['counts']['intel_total'] == 2
        assert ctx['counts']['intel_medium_plus'] == 1
        assert ctx['counts']['raw_total'] == 1

        from crawler_web import app

        r = app.test_client().get('/api/partners/%d/context' % p['id'])
        assert r.status_code == 200
        data = r.get_json()
        assert data['counts']['intel_medium_plus'] == 1
        assert data['counts']['raw_total'] == 1
        print('OK test_default_task_and_counts')
    finally:
        _cleanup(p['id'], [t_old['id'], t_new['id']])


def test_missing_partner_404():
    from crawler_web import app

    r = app.test_client().get('/api/partners/999999999/context')
    assert r.status_code == 404
    print('OK test_missing_partner_404')


if __name__ == '__main__':
    test_no_tasks()
    test_default_task_and_counts()
    test_missing_partner_404()
    print('ALL OK')
