# -*- coding: utf-8 -*-
"""Run 状态机单元测试。"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from intel.db import create_task_run, finish_task_run, get_connection, is_run_stop_requested
from intel.run_state import has_active_monitor_run, is_monitor_busy, request_stop_active_runs
from scripts.test_support import force_delete_monitor_task


def test_stop_requested():
    conn = get_connection()
    conn.execute(
        "INSERT INTO monitor_tasks(id, name, status, max_pages, fetch_detail, created_at, updated_at) "
        "VALUES (99999, 'test', 'idle', 2, 0, datetime('now'), datetime('now')) "
        "ON CONFLICT(id) DO UPDATE SET status='idle'"
    )
    conn.commit()
    run_id = create_task_run(99999, 'manual', 'incremental', status='running')
    assert not is_run_stop_requested(run_id)
    from intel.db import set_run_stop_requested
    set_run_stop_requested(run_id, True)
    assert is_run_stop_requested(run_id)
    finish_task_run(run_id, 'failed', error_message='test')
    print('OK test_stop_requested')


def test_has_active_via_task_status():
    conn = get_connection()
    conn.execute("UPDATE monitor_tasks SET status='crawling' WHERE id=99999")
    conn.commit()
    assert has_active_monitor_run()
    conn.execute("UPDATE monitor_tasks SET status='idle' WHERE id=99999")
    conn.commit()
    print('OK test_has_active_via_task_status')


def test_orphan_run_unblocks_busy():
    from intel.db import (
        create_task_run,
        finish_task_run,
        get_monitor_task,
        reclaim_orphaned_task_runs,
    )

    conn = get_connection()
    conn.execute(
        "INSERT INTO monitor_tasks(id, name, status, max_pages, fetch_detail, created_at, updated_at, error_message) "
        "VALUES (99998, 'orphan-test', 'failed', 2, 0, datetime('now'), datetime('now'), '用户停止') "
        "ON CONFLICT(id) DO UPDATE SET status='failed', error_message='用户停止'"
    )
    conn.commit()
    run_id = create_task_run(99998, 'manual', 'incremental', status='running')
    n = reclaim_orphaned_task_runs()
    assert n >= 1
    assert not has_active_monitor_run()
    print('OK test_orphan_run_unblocks_busy')


def _cleanup_run_state_fixtures():
    for tid in (99998, 99999):
        force_delete_monitor_task(tid)


if __name__ == '__main__':
    try:
        test_stop_requested()
        test_has_active_via_task_status()
        test_orphan_run_unblocks_busy()
        print('All run_state tests passed.')
    finally:
        _cleanup_run_state_fixtures()
