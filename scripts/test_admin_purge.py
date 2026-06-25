# -*- coding: utf-8 -*-
"""管理员 purge API：dry_run、403、运行中拒绝。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intel.db import (
    create_monitor_task,
    create_partner,
    delete_monitor_task,
    delete_partner,
    get_connection,
    insert_intel_record,
    insert_raw_records,
    purge_intel_records,
    purge_raw_records,
    update_task_status,
)


def _cleanup(partner_id, task_id):
    conn = get_connection()
    conn.execute('DELETE FROM intel_records WHERE task_id = ?', (task_id,))
    conn.execute('DELETE FROM raw_records WHERE task_id = ?', (task_id,))
    conn.commit()
    delete_partner(partner_id)
    delete_monitor_task(task_id)


def test_purge_dry_run_and_delete():
    p = create_partner({'name': '__purge__', 'enabled': True})
    t = create_monitor_task({'name': 'purge task', 'partner_ids': [p['id']]})
    try:
        insert_raw_records(
            t['id'], p['id'], 'heimao', 'kw',
            [{'title': 'old', 'url': 'http://example.com/o', 'time': '2020-01-01'}],
        )
        insert_intel_record({
            'task_id': t['id'],
            'partner_id': p['id'],
            'partner_name': p['name'],
            'source': 'heimao',
            'relevance': 'medium',
            'published_at': '2020-01-01',
        })
        preview = purge_intel_records(
            t['id'], published_before='2025-01-01', dry_run=True,
        )
        assert preview['matched_count'] == 1
        done = purge_intel_records(t['id'], published_before='2025-01-01', dry_run=False)
        assert done['deleted_count'] == 1

        insert_raw_records(
            t['id'], p['id'], 'heimao', 'kw2',
            [{'title': 'rawold', 'url': 'http://example.com/r', 'time': '2019-01-01'}],
        )
        pr = purge_raw_records(t['id'], published_before='2025-01-01', dry_run=True)
        assert pr['matched_count'] >= 1
        dr = purge_raw_records(t['id'], published_before='2025-01-01', dry_run=False)
        assert dr['deleted_count'] >= 1
        print('OK test_purge_dry_run_and_delete')
    finally:
        _cleanup(p['id'], t['id'])


def test_purge_running_task_rejected():
    p = create_partner({'name': '__purge_run__', 'enabled': True})
    t = create_monitor_task({'name': 'run task', 'partner_ids': [p['id']]})
    try:
        update_task_status(t['id'], 'crawling')
        r = purge_raw_records(t['id'], dry_run=True)
        assert r.get('ok') is False
        print('OK test_purge_running_task_rejected')
    finally:
        update_task_status(t['id'], 'queued')
        delete_partner(p['id'])
        delete_monitor_task(t['id'])


def test_purge_api_requires_task_id():
    from crawler_web import app

    client = app.test_client()
    r = client.post('/api/admin/purge/raw', json={'dry_run': True})
    assert r.status_code in (400, 403), r.get_data(as_text=True)
    print('OK test_purge_api_requires_task_id')


if __name__ == '__main__':
    test_purge_dry_run_and_delete()
    test_purge_running_task_rejected()
    test_purge_api_requires_task_id()
    print('ALL OK')
