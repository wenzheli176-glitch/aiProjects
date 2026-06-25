# -*- coding: utf-8 -*-
"""任务暂停/终止/继续 单元测试。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.test_support import TestScope, force_delete_monitor_task
from intel.db import (
    create_keyword_run,
    create_task_run,
    count_incomplete_keyword_runs,
    count_incomplete_work,
    get_connection,
    get_monitor_task,
    init_schema,
    is_run_pause_requested,
    is_run_stop_requested,
    list_incomplete_keyword_runs,
    reset_interrupted_keyword_runs,
    set_run_pause_requested,
    set_run_stop_requested,
    update_keyword_run,
    update_task_status,
)


_scope = TestScope()

_LEGACY_TASK_NAMES = ('t', 't2', 't3', 't4', 't5', 't6', 't7', 't8', 't9')


def _cleanup_legacy_task_control_fixtures():
    from intel.db import get_connection

    conn = get_connection()
    placeholders = ','.join('?' * len(_LEGACY_TASK_NAMES))
    rows = conn.execute(
        'SELECT id FROM monitor_tasks WHERE name IN (' + placeholders + ')',
        list(_LEGACY_TASK_NAMES),
    ).fetchall()
    for row in rows:
        force_delete_monitor_task(row['id'])


def _fresh_conn():
    global _conn
    import intel.db as db_mod
    db_mod.reset_db_connection()
    conn = get_connection()
    init_schema(conn)
    return conn


def test_halt_flags():
    _fresh_conn()
    task = _scope.create_task({'name': 't', 'partner_ids': [], 'sources': ['xhs']})
    run_id = create_task_run(task['id'])
    assert not is_run_stop_requested(run_id)
    set_run_stop_requested(run_id, True)
    assert is_run_stop_requested(run_id)
    set_run_pause_requested(run_id, True)
    assert is_run_pause_requested(run_id)
    print('OK test_halt_flags')


def test_incomplete_keywords():
    _fresh_conn()
    task = _scope.create_task({'name': 't2', 'partner_ids': [], 'sources': ['xhs']})
    run_id = create_task_run(task['id'])
    k1 = create_keyword_run(run_id, task['id'], 'xhs', 'kw1')
    k2 = create_keyword_run(run_id, task['id'], 'xhs', 'kw2')
    update_keyword_run(k1, status='done', phase='done')
    update_keyword_run(k2, status='running', phase='list')
    reset_interrupted_keyword_runs(run_id)
    incomplete = list_incomplete_keyword_runs(task['id'], run_id=run_id)
    assert len(incomplete) == 1
    assert incomplete[0]['keyword'] == 'kw2'
    assert incomplete[0]['status'] == 'pending'
    assert count_incomplete_keyword_runs(task['id'], run_id=run_id) == 1
    print('OK test_incomplete_keywords')


def test_task_halt_status():
    _fresh_conn()
    task = _scope.create_task({'name': 't3', 'partner_ids': [], 'sources': ['xhs']})
    update_task_status(
        task['id'], 'stopped',
        error_message='用户终止',
        progress={'resume_run_id': 1, 'halt': 'stopped'},
    )
    t = get_monitor_task(task['id'])
    assert t['status'] == 'stopped'
    print('OK test_task_halt_status')


def test_source_halt():
    _fresh_conn()
    from intel.crawl_queue import enqueue_item, skip_pending_queue_for_source
    from intel.db import (
        build_run_subtasks_by_source,
        get_source_halt_kind,
        set_source_halt,
    )
    from intel.run_state import is_halt_requested

    task = _scope.create_task({'name': 't4', 'partner_ids': [], 'sources': ['xhs', 'heimao']})
    run_id = create_task_run(task['id'])
    update_task_status(task['id'], 'crawling')
    enqueue_item(run_id, task['id'], 'xhs', 'keyword_pipeline', {'keyword': 'k1'})
    enqueue_item(run_id, task['id'], 'heimao', 'legacy_crawl', {'partner_id': 1})
    set_source_halt(run_id, 'xhs', 'pause')
    assert get_source_halt_kind(run_id, 'xhs') == 'pause'
    assert is_halt_requested(run_id, 'xhs')
    assert not is_halt_requested(run_id, 'heimao')
    skip_pending_queue_for_source(run_id, 'xhs', '用户终止')
    subs = build_run_subtasks_by_source(run_id, ['xhs', 'heimao'])
    assert len(subs) == 2
    xhs = next(s for s in subs if s['source_id'] == 'xhs')
    assert xhs['halt'] == 'pause'
    print('OK test_source_halt')


def test_resume_sources():
    _fresh_conn()
    from intel.crawl_queue import enqueue_item
    from intel.db import list_resume_sources

    task = _scope.create_task({'name': 't5', 'partner_ids': [], 'sources': ['heimao', 'xhs']})
    run_id = create_task_run(task['id'])
    k1 = create_keyword_run(run_id, task['id'], 'xhs', 'kw1')
    update_keyword_run(k1, status='pending', phase='pending')
    enqueue_item(run_id, task['id'], 'heimao', 'legacy_crawl', {'partner_id': 1, 'keyword': 'p1'})
    sources = list_resume_sources(task['id'], run_id, task)
    assert 'xhs' in sources
    assert 'heimao' in sources
    print('OK test_resume_sources')


def test_stop_completes_run():
    _fresh_conn()
    from intel.crawl_queue import enqueue_item
    from intel.db import (
        get_task_run,
        count_incomplete_work,
    )
    from intel.run_state import request_task_halt

    task = _scope.create_task({'name': 't6', 'partner_ids': [], 'sources': ['xhs', 'heimao']})
    run_id = create_task_run(task['id'])
    update_task_status(task['id'], 'crawling', progress={'run_id': run_id})
    k1 = create_keyword_run(run_id, task['id'], 'xhs', 'kw1')
    update_keyword_run(k1, status='pending', phase='pending')
    enqueue_item(run_id, task['id'], 'heimao', 'legacy_crawl', {'partner_id': 1})
    ok, msg = request_task_halt(task['id'], 'stop')
    assert ok, msg
    t = get_monitor_task(task['id'])
    assert t['status'] == 'stopped'
    run = get_task_run(run_id)
    assert run['status'] == 'stopped'
    assert run.get('finished_at')
    assert count_incomplete_work(task['id'], run_id=run_id) == 0
    print('OK test_stop_completes_run')


def test_pause_finishes_run():
    _fresh_conn()
    from intel.run_state import request_task_halt, has_active_monitor_run
    from intel.db import get_task_run

    task = _scope.create_task({'name': 't7', 'partner_ids': [], 'sources': ['xhs']})
    run_id = create_task_run(task['id'])
    update_task_status(task['id'], 'crawling', progress={'run_id': run_id})
    ok, msg = request_task_halt(task['id'], 'pause')
    assert ok, msg
    run = get_task_run(run_id)
    assert run['status'] == 'paused', run
    assert run.get('finished_at')
    t = get_monitor_task(task['id'])
    assert t['status'] == 'paused'
    print('OK test_pause_finishes_run')


def test_find_resumable_run_id():
    _fresh_conn()
    from intel.db import find_resumable_run_id, finish_task_run, create_task_run

    task = _scope.create_task({'name': 't8', 'partner_ids': [], 'sources': ['xhs']})
    run_old = create_task_run(task['id'])
    run_new = create_task_run(task['id'])
    k1 = create_keyword_run(run_old, task['id'], 'xhs', 'kw-old')
    update_keyword_run(k1, status='running', phase='triage')
    finish_task_run(run_old, 'failed', error_message='timeout test')
    finish_task_run(run_new, 'done')
    update_task_status(task['id'], 'done', progress={'run_id': run_new})
    rid = find_resumable_run_id(task['id'])
    assert rid == run_old, rid
    print('OK test_find_resumable_run_id')


def test_aggregate_subtask_timing():
    _fresh_conn()
    from intel.db import aggregate_subtask_timing_by_source, build_run_subtasks_by_source

    task = _scope.create_task({'name': 't9', 'partner_ids': [], 'sources': ['xhs', 'heimao']})
    run_id = create_task_run(task['id'])
    k1 = create_keyword_run(run_id, task['id'], 'xhs', 'kw1')
    update_keyword_run(
        k1, status='done', phase='done',
        stats_json={'phase_timing_ms': {'list_crawl_ms': 1000, 'analyze_ms': 2000, 'investigation_ms': 500}},
    )
    by_source = aggregate_subtask_timing_by_source(run_id)
    assert by_source['xhs']['crawl_ms'] == 1000
    assert by_source['xhs']['analyze_ms'] == 2000
    subs = build_run_subtasks_by_source(run_id, task.get('sources'))
    xhs = next(s for s in subs if s['source_id'] == 'xhs')
    assert xhs['timing']['crawl_ms'] == 1000
    assert xhs['timing']['analyze_ms'] == 2000
    print('OK test_aggregate_subtask_timing')


def test_timeout_unlimited():
    from intel.timeout_budget import compute_monitor_deadlines

    budget = compute_monitor_deadlines(0, 3600, 1800)
    assert budget.get('unlimited') is True
    assert budget['task_timeout_sec'] == 0
    print('OK test_timeout_unlimited')


if __name__ == '__main__':
    try:
        _cleanup_legacy_task_control_fixtures()
        test_halt_flags()
        test_incomplete_keywords()
        test_task_halt_status()
        test_source_halt()
        test_resume_sources()
        test_stop_completes_run()
        test_pause_finishes_run()
        test_find_resumable_run_id()
        test_aggregate_subtask_timing()
        test_timeout_unlimited()
        print('ALL OK')
    finally:
        _scope.cleanup()
