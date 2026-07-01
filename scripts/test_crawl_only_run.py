# -*- coding: utf-8 -*-
"""crawl_only Run 模式单元测试。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intel.timeout_budget import compute_monitor_deadlines
from intel.runner import _resolve_crawl_only, _count_pending_analyze_raw
from intel.db import create_task_run, get_task_run, init_schema, get_connection


def test_crawl_only_timeout_budget():
    b = compute_monitor_deadlines(7200, 3600, 1800, crawl_only=True)
    assert b['analysis_reserve_sec'] == 0, b
    assert b['crawl_budget_sec'] == 7200, b
    b2 = compute_monitor_deadlines(7200, 3600, 1800, crawl_only=False)
    assert b2['analysis_reserve_sec'] > 0, b2
    assert b2['crawl_budget_sec'] < 7200, b2
    print('OK test_crawl_only_timeout_budget')


def test_resolve_crawl_only():
    task = {'crawl_only': True}
    assert _resolve_crawl_only(task, crawl_only=None) is True
    assert _resolve_crawl_only(task, crawl_only=False) is False
    task2 = {'crawl_only': False}
    assert _resolve_crawl_only(task2, crawl_only=None) is False
    print('OK test_resolve_crawl_only')


def test_create_task_run_crawl_only_flag():
    import intel.db as db_mod
    from scripts.test_support import TestScope

    db_mod.reset_db_connection()
    init_schema(get_connection())
    scope = TestScope()
    task = scope.create_task({'name': 'crawl_only_t', 'partner_ids': [], 'sources': ['xhs']})
    run_id = create_task_run(task['id'], crawl_only=True)
    run = get_task_run(run_id)
    assert run.get('crawl_only') is True, run
    run_id2 = create_task_run(task['id'], crawl_only=False)
    run2 = get_task_run(run_id2)
    assert run2.get('crawl_only') is False, run2
    scope.cleanup()
    print('OK test_create_task_run_crawl_only_flag')


def test_count_pending_analyze_raw_empty():
    import intel.db as db_mod
    from scripts.test_support import TestScope

    db_mod.reset_db_connection()
    init_schema(get_connection())
    scope = TestScope()
    task = scope.create_task({'name': 'count_t', 'partner_ids': [], 'sources': ['xhs']})
    n = _count_pending_analyze_raw(task['id'], [], analyze_mode='incremental', shared_pool=False)
    assert n == 0
    scope.cleanup()
    print('OK test_count_pending_analyze_raw_empty')


if __name__ == '__main__':
    test_crawl_only_timeout_budget()
    test_resolve_crawl_only()
    test_create_task_run_crawl_only_flag()
    test_count_pending_analyze_raw_empty()
    print('All crawl_only tests passed.')
