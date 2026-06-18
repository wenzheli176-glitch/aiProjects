# -*- coding: utf-8 -*-
"""Worker 池与 stop 广播单元测试（无 Chrome）。"""
import os
import sys
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.environ.setdefault('MINIMAX_API_KEY', '')


def _temp_db():
    import intel.db as db_mod

    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    orig_path = db_mod._db_path
    db_mod._conn = None
    db_mod._db_path = lambda: path
    db_mod.init_schema()
    return db_mod, path, orig_path


def _cleanup(db_mod, path, orig_path):
    db_mod._db_path = orig_path
    db_mod._conn = None
    try:
        os.remove(path)
    except Exception:
        pass


def test_parallel_source_claim():
    """heimao 与 xhs Worker 各认领各自 source 的 queue item。"""
    import config
    import intel.db as db_mod
    from intel.crawl_queue import claim_next, clear_run_queue, enqueue_item, mark_done, run_queue_counts

    config._config = None
    db_mod, path, orig_path = _temp_db()
    try:
        conn = db_mod.get_connection()
        conn.execute(
            """
            INSERT INTO monitor_tasks(id, name, status, max_pages, fetch_detail, created_at, updated_at)
            VALUES (1, 't', 'idle', 2, 1, datetime('now'), datetime('now'))
            """
        )
        conn.commit()
        run_id = db_mod.create_task_run(1, 'manual', 'incremental', status='running')
        clear_run_queue(run_id)
        enqueue_item(run_id, 1, 'heimao', 'legacy_crawl', {'partner_id': 1}, 10)
        enqueue_item(run_id, 1, 'xhs', 'list_crawl', {'keyword_batch': {'keywords': ['a']}}, 10)

        hm = claim_next(run_id, 'heimao', 'heimao-0')
        xhs = claim_next(run_id, 'xhs', 'xhs-0')
        assert hm and hm['source_id'] == 'heimao'
        assert xhs and xhs['source_id'] == 'xhs'
        mark_done(hm['id'])
        mark_done(xhs['id'])
        counts = run_queue_counts(run_id)
        assert counts['done'] == 2 and counts['pending'] == 0
        print('OK test_parallel_source_claim')
    finally:
        _cleanup(db_mod, path, orig_path)


def test_stop_requested_blocks_barrier():
    """stop_requested 时 wait_routine_barrier 应退出。"""
    import config
    import intel.db as db_mod
    from intel.crawl_queue import clear_run_queue, enqueue_item, wait_routine_barrier

    config._config = None
    db_mod, path, orig_path = _temp_db()
    try:
        conn = db_mod.get_connection()
        conn.execute(
            """
            INSERT INTO monitor_tasks(id, name, status, max_pages, fetch_detail, created_at, updated_at)
            VALUES (1, 't', 'idle', 2, 1, datetime('now'), datetime('now'))
            """
        )
        conn.commit()
        run_id = db_mod.create_task_run(1, 'manual', 'incremental', status='running')
        clear_run_queue(run_id)
        enqueue_item(run_id, 1, 'xhs', 'list_crawl', {'keyword_batch': {'keywords': ['a']}}, 10)
        db_mod.set_run_stop_requested(run_id, True)

        ok = wait_routine_barrier(
            run_id,
            timeout_check=lambda: db_mod.is_run_stop_requested(run_id),
            poll_sec=0.2,
        )
        assert ok is False
        print('OK test_stop_requested_blocks_barrier')
    finally:
        _cleanup(db_mod, path, orig_path)


def test_aggregate_worker_login_waits():
    from intel.run_state import aggregate_worker_login_waits

    state = {
        'heimao-0': {
            'source_id': 'heimao',
            'status': 'waiting_login',
            'login_wait': {'site': 'heimao', 'message': '等待登录', 'elapsed_sec': 5},
        },
        'xhs-0': {'source_id': 'xhs', 'status': 'running'},
    }
    waits = aggregate_worker_login_waits(state)
    assert len(waits) == 1
    assert waits[0]['instance_id'] == 'heimao-0'
    print('OK test_aggregate_worker_login_waits')


if __name__ == '__main__':
    test_parallel_source_claim()
    test_stop_requested_blocks_barrier()
    test_aggregate_worker_login_waits()
    print('All worker pool tests passed.')
