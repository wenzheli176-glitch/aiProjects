# -*- coding: utf-8 -*-
"""keyword 子任务与流水线单元测试。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intel.db import (
    create_keyword_run,
    create_monitor_task,
    create_partner,
    create_task_run,
    delete_monitor_task,
    delete_partner,
    get_connection,
    keyword_run_counts,
    list_keyword_runs,
    update_keyword_run,
)
from intel.investigation import row_needs_investigation
from intel.keyword_pipeline import collect_xhs_keywords, make_keyword_timeout_check
from intel.registry import register_default_sources


def test_keyword_run_crud():
    p = create_partner({'name': '__kw_crud__', 'monitor_keywords': ['__kw_crud__']})
    t = create_monitor_task({'name': 'kw test', 'partner_ids': [p['id']]})
    run_id = create_task_run(t['id'])
    try:
        kr_id = create_keyword_run(run_id, t['id'], 'xhs', '__kw_crud__', 'cohort1')
        assert kr_id > 0
        update_keyword_run(kr_id, status='done', phase='done')
        items = list_keyword_runs(run_id=run_id)
        assert len(items) == 1
        assert items[0]['status'] == 'done'
        counts = keyword_run_counts(run_id)
        assert counts['done'] == 1
        conn = get_connection()
        conn.execute('DELETE FROM monitor_keyword_runs WHERE run_id=?', (run_id,))
        conn.commit()
        print('test_keyword_run_crud OK')
    finally:
        delete_monitor_task(t['id'])
        delete_partner(p['id'])


def test_row_needs_investigation():
    register_default_sources()
    row = {
        'id': 1,
        'crawl_phase': 'list',
        'source': 'xhs',
        'payload': {'title': '投诉', 'link': 'http://x/1'},
        'list_triage': {
            'triage_relevance': 'medium',
            'triage_risk_hint': 'elevated',
            'needs_investigation': True,
        },
    }
    partners = [{'id': 1, 'name': '测试', 'aliases': [], 'priority_tier': 'P1'}]
    assert row_needs_investigation(row, partners) is True
    row2 = dict(row, list_triage={'triage_relevance': 'noise', 'needs_investigation': False})
    assert row_needs_investigation(row2, partners) is False
    print('test_row_needs_investigation OK')


def test_collect_xhs_keywords():
    partners = [
        {'id': 1, 'name': 'A', 'monitor_keywords': ['A'], 'industry_cohort': 'c1', 'priority_tier': 'P1'},
        {'id': 2, 'name': 'B', 'monitor_keywords': ['B'], 'industry_cohort': 'c1', 'priority_tier': 'P1'},
    ]
    kws = collect_xhs_keywords(partners)
    assert len(kws) >= 2
    print('test_collect_xhs_keywords OK')


def test_keyword_timeout_check():
    import time
    started = time.monotonic()
    check = make_keyword_timeout_check({}, None, started - 4000)
    assert check() is True
    check2 = make_keyword_timeout_check({}, None, time.monotonic())
    assert check2() is False
    print('test_keyword_timeout_check OK')


def test_resolve_source_timeout():
    from intel.source_timeout import resolve_source_timeout_sec
    partners = [{
        'id': 1, 'name': '大数据公司', 'aliases': [], 'monitor_keywords': [],
        'source_timeouts': {'xhs': 7200},
    }]
    assert resolve_source_timeout_sec('xhs', partners, keyword='大数据公司') == 7200
    assert resolve_source_timeout_sec('xhs', partners, keyword='其他') >= 3600
    print('test_resolve_source_timeout OK')


def test_keyword_timeout_no_recursion():
    import time
    calls = {'n': 0}

    def parent_check():
        calls['n'] += 1
        return False

    ctx = {'run_id': None, 'timeout_check': parent_check, 'keyword_timeout_sec': 3600}
    check = make_keyword_timeout_check(ctx, None, time.monotonic(), timeout_sec=3600)
    ctx['timeout_check'] = check
    for _ in range(5):
        check()
    assert calls['n'] == 5
    print('OK test_keyword_timeout_no_recursion')


if __name__ == '__main__':
    test_keyword_run_crud()
    test_row_needs_investigation()
    test_collect_xhs_keywords()
    test_keyword_timeout_check()
    test_keyword_timeout_no_recursion()
    test_resolve_source_timeout()
    print('ALL OK')
