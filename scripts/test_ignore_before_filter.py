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
from intel.registry import register_default_sources
from intel.runner import _build_candidates_from_raw, _should_skip_ignore_before


def test_should_skip_helper():
    assert not _should_skip_ignore_before('', '2025-01-01')
    assert not _should_skip_ignore_before('2024-06-01', '')
    assert _should_skip_ignore_before('2024-01-01', '2025-01-01')
    assert not _should_skip_ignore_before('2025-06-01', '2025-01-01')
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


if __name__ == '__main__':
    test_should_skip_helper()
    test_build_candidates_respects_ignore()
    print('ALL OK')
