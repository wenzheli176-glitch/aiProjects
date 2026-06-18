# -*- coding: utf-8 -*-
"""Run 级 xhs 弹窗配额单元测试。"""
import json
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


def _patch_max_modal(n):
    import config
    c = config.load_config(force=True)
    xhs = dict(c.get('xhs') or {})
    inv = dict(xhs.get('investigation_detail') or {})
    inv['max_modal_per_run'] = n
    xhs['investigation_detail'] = inv
    config.save_config({'xhs': xhs})
    config.load_config(force=True)


def test_shared_quota_across_reserves():
    import config
    import intel.db as db_mod
    from intel.modal_quota import (
        get_modal_quota_state,
        is_quota_exhausted,
        record_skipped_quota,
        release_modal_slot,
        reserve_modal_slot,
    )

    config._config = None
    _patch_max_modal(2)
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

        assert reserve_modal_slot(run_id) is True
        assert reserve_modal_slot(run_id) is True
        assert reserve_modal_slot(run_id) is False
        assert is_quota_exhausted(run_id) is True

        release_modal_slot(run_id)
        assert reserve_modal_slot(run_id) is True

        record_skipped_quota(run_id, 3)
        state = get_modal_quota_state(run_id)
        assert state['investigation_skipped_quota'] == 3
        print('OK test_shared_quota_across_reserves')
    finally:
        _cleanup(db_mod, path, orig_path)


def test_skip_investigation_batch():
    import config
    import intel.db as db_mod
    from intel.investigation import skip_investigation_batch_for_quota
    from intel.modal_quota import get_modal_quota_state

    config._config = None
    _patch_max_modal(1)
    db_mod, path, orig_path = _temp_db()
    try:
        conn = db_mod.get_connection()
        conn.execute(
            """
            INSERT INTO monitor_tasks(id, name, status, max_pages, fetch_detail, created_at, updated_at)
            VALUES (1, 't', 'idle', 2, 1, datetime('now'), datetime('now'))
            """
        )
        conn.execute(
            """
            INSERT INTO raw_records(
                id, task_id, partner_id, source, keyword, dedup_key, payload_json,
                crawl_phase, created_at, updated_at
            ) VALUES (10, 1, NULL, 'xhs', 'kw', 'x1', '{}', 'list', datetime('now'), datetime('now'))
            """
        )
        conn.execute(
            """
            INSERT INTO investigation_queue(
                id, task_id, raw_id, url, source, priority_score, status, created_at, updated_at
            ) VALUES (1, 1, 10, 'http://x/1', 'xhs', 1, 'pending', datetime('now'), datetime('now'))
            """
        )
        conn.commit()
        run_id = db_mod.create_task_run(1, 'manual', 'incremental', status='running')

        from intel.run_metrics import RunMetrics
        rm = RunMetrics()
        n = skip_investigation_batch_for_quota(
            run_id,
            [{'queue_id': 1, 'raw_id': 10, 'url': 'http://x/1', 'keyword': 'a'}],
            rm,
        )
        assert n == 1
        row = conn.execute('SELECT status, error_message FROM investigation_queue WHERE id=1').fetchone()
        assert row['status'] == 'skipped'
        assert 'modal_quota' in row['error_message']
        assert get_modal_quota_state(run_id)['investigation_skipped_quota'] == 1
        print('OK test_skip_investigation_batch')
    finally:
        _cleanup(db_mod, path, orig_path)


def test_process_batch_quota_exhausted():
    import config
    import intel.db as db_mod
    from intel.investigation import process_investigation_batch
    from intel.modal_quota import reserve_modal_slot

    config._config = None
    _patch_max_modal(1)
    db_mod, path, orig_path = _temp_db()
    try:
        conn = db_mod.get_connection()
        conn.execute(
            """
            INSERT INTO monitor_tasks(id, name, status, max_pages, fetch_detail, created_at, updated_at)
            VALUES (1, 't', 'idle', 2, 1, datetime('now'), datetime('now'))
            """
        )
        conn.execute(
            """
            INSERT INTO raw_records(
                id, task_id, partner_id, source, keyword, dedup_key, payload_json,
                crawl_phase, created_at, updated_at
            ) VALUES
            (10, 1, NULL, 'xhs', 'kw', 'x1', '{}', 'list', datetime('now'), datetime('now')),
            (11, 1, NULL, 'xhs', 'kw', 'x2', '{}', 'list', datetime('now'), datetime('now'))
            """
        )
        conn.execute(
            """
            INSERT INTO investigation_queue(
                id, task_id, raw_id, url, source, priority_score, status, created_at, updated_at
            ) VALUES
            (1, 1, 10, 'http://x/1', 'xhs', 1, 'pending', datetime('now'), datetime('now')),
            (2, 1, 11, 'http://x/2', 'xhs', 1, 'pending', datetime('now'), datetime('now'))
            """
        )
        conn.commit()
        run_id = db_mod.create_task_run(1, 'manual', 'incremental', status='running')
        reserve_modal_slot(run_id)

        batch = [
            {'queue_id': 1, 'raw_id': 10, 'url': 'http://x/1', 'keyword': 'a'},
            {'queue_id': 2, 'raw_id': 11, 'url': 'http://x/2', 'keyword': 'a'},
        ]
        result = process_investigation_batch(
            'xhs', batch, {}, {'run_id': run_id, 'log': lambda *a, **k: None},
        )
        assert result['skipped'] == 2
        assert result['failed'] == 0
        print('OK test_process_batch_quota_exhausted')
    finally:
        _cleanup(db_mod, path, orig_path)


def test_unlimited_quota():
    import config
    import intel.db as db_mod
    from intel.modal_quota import get_max_modal_per_run, is_quota_exhausted, reserve_modal_slot

    config._config = None
    _patch_max_modal(0)
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
        assert get_max_modal_per_run() == 0
        for _ in range(5):
            assert reserve_modal_slot(run_id) is True
        assert is_quota_exhausted(run_id) is False
        print('OK test_unlimited_quota')
    finally:
        _cleanup(db_mod, path, orig_path)


if __name__ == '__main__':
    test_shared_quota_across_reserves()
    test_skip_investigation_batch()
    test_process_batch_quota_exhausted()
    test_unlimited_quota()
    print('All modal quota tests passed.')
