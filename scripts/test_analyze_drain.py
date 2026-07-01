# -*- coding: utf-8 -*-
"""analyze_drain：detail-only 过滤、busy 规则、mock drain。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intel.analyze_drain import drain_analyze_ready, should_drain_analyze
from intel.db import get_connection, init_schema, insert_raw_records, list_raw_records
from intel.runner import _should_analyze_raw
from intel.run_state import is_reanalyze_allowed
from scripts.test_support import TestScope


def test_should_analyze_raw_detail_only():
    list_row = {'crawl_phase': 'list', 'source': 'xhs', 'list_triage': {'triage_relevance': 'high'}}
    detail_row = {'crawl_phase': 'detail', 'source': 'xhs'}
    heimao_legacy = {
        'crawl_phase': 'legacy',
        'source': 'heimao',
        'payload': {'content': 'x' * 100},
    }
    task = {'fetch_detail': True}
    assert _should_analyze_raw(list_row, detail_only=True) is False
    assert _should_analyze_raw(detail_row, detail_only=True) is True
    assert _should_analyze_raw(heimao_legacy, detail_only=True, task=task) is True
    print('OK test_should_analyze_raw_detail_only')


def test_build_candidates_detail_only_skips_list():
    import intel.db as db_mod

    db_mod.reset_db_connection()
    init_schema(get_connection())
    scope = TestScope()
    partner = scope.create_partner({'name': 'drain_p', 'aliases': [], 'enabled': True})
    task = scope.create_task({'name': 'drain_t', 'partner_ids': [partner['id']], 'sources': ['xhs']})
    task_id = task['id']
    insert_raw_records(
        task_id, partner['id'], 'xhs', 'drain_p', [
            {'link': 'https://xhs/list1', 'title': 'drain_p list', 'content': 'body'},
        ],
        crawl_phase='list',
    )
    insert_raw_records(
        task_id, partner['id'], 'xhs', 'drain_p', [
            {'link': 'https://xhs/detail1', 'title': 'drain_p detail', 'content': 'body detail'},
        ],
        crawl_phase='detail',
    )
    from intel.db import list_raw_records
    rows = list_raw_records(task_id)
    detail_rows = [r for r in rows if _should_analyze_raw(r, detail_only=True, task=task)]
    assert len(rows) == 2, len(rows)
    assert len(detail_rows) == 1, detail_rows
    from intel.runner import _count_pending_analyze_raw
    pending = _count_pending_analyze_raw(
        task_id, [partner], analyze_mode='incremental', detail_only=True, task=task,
    )
    assert pending >= 0
    scope.cleanup()
    print('OK test_build_candidates_detail_only_skips_list')


def test_drain_mock_skips_when_crawl_only():
    import intel.db as db_mod

    db_mod.reset_db_connection()
    init_schema(get_connection())
    scope = TestScope()
    task = scope.create_task({'name': 'drain_co', 'partner_ids': [], 'sources': ['xhs'], 'crawl_only': True})
    assert should_drain_analyze(task, trigger='batch') is False
    assert should_drain_analyze(task, trigger='manual') is True
    scope.cleanup()
    print('OK test_drain_mock_skips_when_crawl_only')


def test_reanalyze_crawl_only_during_crawl():
    import intel.db as db_mod

    db_mod.reset_db_connection()
    init_schema(get_connection())
    scope = TestScope()
    task = scope.create_task({'name': 'busy_co', 'partner_ids': [], 'sources': ['xhs'], 'crawl_only': True})
    task_id = task['id']
    insert_raw_records(task_id, None, 'xhs', 'kw', [
        {'link': 'https://xhs/t1', 'title': 't', 'content': 'body'},
    ])
    from intel.db import update_task_status
    update_task_status(task_id, 'crawling', progress={'phase': 'crawl'})
    ok_inc, _ = is_reanalyze_allowed(task_id, 'incremental')
    assert ok_inc is True
    scope.cleanup()
    print('OK test_reanalyze_crawl_only_during_crawl')


def test_reanalyze_busy_rules():
    import intel.db as db_mod

    db_mod.reset_db_connection()
    init_schema(get_connection())
    scope = TestScope()
    task = scope.create_task({'name': 'busy_t', 'partner_ids': [], 'sources': ['xhs']})
    task_id = task['id']
    insert_raw_records(task_id, None, 'xhs', 'kw', [
        {'link': 'https://xhs/t1', 'title': 't', 'content': 'body'},
    ])
    from intel.db import update_task_status
    update_task_status(task_id, 'crawling', progress={'phase': 'crawl'})
    ok_inc, _ = is_reanalyze_allowed(task_id, 'incremental')
    ok_full, full_msg = is_reanalyze_allowed(task_id, 'full_replace')
    assert ok_inc is True, (ok_inc, full_msg)
    assert ok_full is False, full_msg
    assert '全量' in full_msg or '运行' in full_msg
    scope.cleanup()
    print('OK test_reanalyze_busy_rules')


def test_drain_empty_candidates():
    import intel.db as db_mod

    db_mod.reset_db_connection()
    init_schema(get_connection())
    scope = TestScope()
    task = scope.create_task({'name': 'drain_empty', 'partner_ids': [], 'sources': ['xhs']})
    task_id = task['id']
    from intel.db import create_task_run
    run_id = create_task_run(task_id)
    n = drain_analyze_ready(task_id, run_id, task, partners=[], trigger='batch')
    assert n == 0
    scope.cleanup()
    print('OK test_drain_empty_candidates')


if __name__ == '__main__':
    test_should_analyze_raw_detail_only()
    test_build_candidates_detail_only_skips_list()
    test_drain_mock_skips_when_crawl_only()
    test_reanalyze_crawl_only_during_crawl()
    test_reanalyze_busy_rules()
    test_drain_empty_candidates()
    print('All analyze_drain tests passed.')
