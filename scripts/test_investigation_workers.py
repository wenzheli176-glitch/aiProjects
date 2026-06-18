# -*- coding: utf-8 -*-
"""Phase B2：investigation 按源入队与 Worker 路由单元测试。"""
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


def test_enqueue_investigation_by_source():
    import config
    import intel.db as db_mod
    from intel.crawl_queue import clear_run_queue, enqueue_investigation_work_items

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
        conn.execute(
            """
            INSERT INTO raw_records(
                id, task_id, partner_id, source, keyword, dedup_key, payload_json,
                crawl_phase, created_at, updated_at
            ) VALUES
            (10, 1, NULL, 'xhs', 'kw', 'x1', '{"link":"http://x/1","_search_keyword":"小鹏"}', 'list', datetime('now'), datetime('now')),
            (11, 1, NULL, 'heimao', 'kw', 'h1', '{"link":"http://h/1"}', 'list', datetime('now'), datetime('now'))
            """
        )
        conn.execute(
            """
            INSERT INTO investigation_queue(
                id, task_id, raw_id, url, source, priority_score, status, created_at, updated_at
            ) VALUES
            (1, 1, 10, 'http://x/1', 'xhs', 20, 'pending', datetime('now'), datetime('now')),
            (2, 1, 11, 'http://h/1', 'heimao', 15, 'pending', datetime('now'), datetime('now'))
            """
        )
        conn.commit()

        run_id = db_mod.create_task_run(1, 'manual', 'incremental', status='running')
        clear_run_queue(run_id)
        n, source_ids = enqueue_investigation_work_items(run_id, 1)
        assert n == 2
        assert set(source_ids) == {'xhs', 'heimao'}

        rows = conn.execute(
            "SELECT id, source_id, phase, payload_json FROM crawl_work_queue WHERE run_id=? ORDER BY id",
            (run_id,),
        ).fetchall()
        assert len(rows) == 2
        phases = {r['source_id']: json.loads(r['payload_json']) for r in rows}
        assert phases['xhs']['items'][0]['keyword'] == '小鹏'
        assert phases['heimao']['urls'] == ['http://h/1']
        print('OK test_enqueue_investigation_by_source')
    finally:
        _cleanup(db_mod, path, orig_path)


def test_worker_claim_investigation_phase():
    import config
    import intel.db as db_mod
    from intel.crawl_queue import claim_next, clear_run_queue, enqueue_item

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
        enqueue_item(
            run_id, 1, 'xhs', 'investigation',
            {'items': [{'queue_id': 1, 'raw_id': 10, 'url': 'http://x/1', 'keyword': 'a'}]},
            10,
        )
        item = claim_next(run_id, 'xhs', 'xhs-0')
        assert item and item['phase'] == 'investigation'
        hm = claim_next(run_id, 'heimao', 'heimao-0')
        assert hm is None
        print('OK test_worker_claim_investigation_phase')
    finally:
        _cleanup(db_mod, path, orig_path)


def test_process_investigation_batch_unknown_source():
    from intel.investigation import process_investigation_batch

    result = process_investigation_batch(
        'unknown',
        [{'queue_id': 1, 'raw_id': 10, 'url': 'http://x/1', 'keyword': 'kw'}],
        {},
        {'log': lambda *a, **k: None},
    )
    assert result == {'done': 0, 'failed': 1, 'skipped': 0}
    print('OK test_process_investigation_batch_unknown_source')


if __name__ == '__main__':
    test_enqueue_investigation_by_source()
    test_worker_claim_investigation_phase()
    test_process_investigation_batch_unknown_source()
    print('All investigation worker tests passed.')
