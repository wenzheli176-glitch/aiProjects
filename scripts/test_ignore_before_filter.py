# -*- coding: utf-8 -*-
"""任务 ignore_before 分析过滤。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intel.db import (
    create_monitor_task,
    create_partner,
    delete_monitor_task,
    delete_partner,
    get_connection,
    insert_raw_records,
    update_monitor_task,
)
from intel.ignore_before import should_skip_ignore_before
from intel.registry import register_default_sources
from intel.runner import _build_candidates_from_raw


def test_should_skip_helper():
    assert not should_skip_ignore_before('', '2025-01-01')
    assert not should_skip_ignore_before('2024-06-01', '')
    assert should_skip_ignore_before('2024-01-01', '2025-01-01')
    assert not should_skip_ignore_before('2025-06-01', '2025-01-01')
    print('OK test_should_skip_helper')


def test_build_candidates_respects_ignore():
    register_default_sources()
    p = create_partner({'name': '__ignore_before__', 'enabled': True})
    t = create_monitor_task({'name': 'ignore task', 'partner_ids': [p['id']]})
    update_monitor_task(t['id'], {
        'business_spec': {'ignore_before': '2025-01-01'},
    })
    try:
        insert_raw_records(
            t['id'], p['id'], 'heimao', 'kw',
            [
                {'title': 'old', 'url': 'http://example.com/old', 'time': '2024-01-01', 'link': 'http://example.com/old'},
                {'title': 'new', 'url': 'http://example.com/new', 'time': '2026-01-01', 'link': 'http://example.com/new'},
                {'title': 'nodate', 'url': 'http://example.com/nodate', 'link': 'http://example.com/nodate'},
            ],
        )
        task, _err = update_monitor_task(t['id'], {'name': t['name']})
        ignore = task['business_spec']['ignore_before']
        groups = _build_candidates_from_raw(
            t['id'], [p], analyze_mode='full_replace', ignore_before=ignore,
        )
        items = groups.get(p['id'], {}).get('items', [])
        titles = {it['title'] for it in items}
        assert 'old' not in titles
        assert 'new' in titles
        assert 'nodate' in titles
        print('OK test_build_candidates_respects_ignore', titles)
    finally:
        conn = get_connection()
        conn.execute('DELETE FROM raw_records WHERE task_id = ?', (t['id'],))
        conn.commit()
        delete_partner(p['id'])
        delete_monitor_task(t['id'])


def test_row_needs_investigation_respects_ignore():
    register_default_sources()
    p = create_partner({'name': '__ignore_inv__', 'enabled': True})
    row = {
        'source': 'heimao',
        'crawl_phase': 'list',
        'payload': {'title': 'old', 'time': '2024-01-01', 'link': 'http://x/old'},
        'list_triage': {
            'triage_relevance': 'high',
            'triage_risk_hint': 'elevated',
            'needs_investigation': True,
        },
    }
    task = {'business_spec': {'ignore_before': '2025-01-01'}}
    from intel.investigation import row_needs_investigation
    assert not row_needs_investigation(row, [p], task=task)
    row['payload']['time'] = '2026-01-01'
    assert row_needs_investigation(row, [p], task=task)
    row['payload']['time'] = ''
    assert row_needs_investigation(row, [p], task=task)
    delete_partner(p['id'])
    print('OK test_row_needs_investigation_respects_ignore')


def test_insert_raw_skips_old_at_list():
    register_default_sources()
    p = create_partner({'name': '__ignore_list__', 'enabled': True})
    t = create_monitor_task({'name': 'ignore list', 'partner_ids': [p['id']]})
    update_monitor_task(t['id'], {
        'business_spec': {'ignore_before': '2025-01-01'},
    })
    try:
        ins = insert_raw_records(
            t['id'], p['id'], 'heimao', 'kw',
            [
                {'title': 'old', 'link': 'http://example.com/o1', 'time': '2024-06-01'},
                {'title': 'new', 'link': 'http://example.com/n1', 'time': '2026-06-01'},
                {'title': 'nodate', 'link': 'http://example.com/nd1'},
            ],
            ignore_before='2025-01-01',
        )
        assert ins['skipped_ignore_before'] == 1
        assert ins['inserted'] == 2
        from intel.db import count_raw_records
        assert count_raw_records(t['id']) == 2
        print('OK test_insert_raw_skips_old_at_list')
    finally:
        conn = get_connection()
        conn.execute('DELETE FROM raw_records WHERE task_id = ?', (t['id'],))
        conn.commit()
        delete_partner(p['id'])
        delete_monitor_task(t['id'])


if __name__ == '__main__':
    test_should_skip_helper()
    test_build_candidates_respects_ignore()
    test_row_needs_investigation_respects_ignore()
    test_insert_raw_skips_old_at_list()
    print('ALL OK')
