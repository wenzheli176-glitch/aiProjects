# -*- coding: utf-8 -*-
"""crawl_work_queue 单元测试。"""
import json
import os
import sys
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.environ.setdefault('MINIMAX_API_KEY', '')


def test_claim_and_reclaim():
    import config
    import intel.db as db_mod

    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    try:
        config._config = None
        db_mod._conn = None
        orig_path = db_mod._db_path
        db_mod._db_path = lambda: path
        try:
            db_mod.init_schema()
        except Exception:
            db_mod._db_path = orig_path
            raise

        from intel.crawl_queue import (
            claim_next,
            clear_run_queue,
            enqueue_item,
            mark_done,
            reclaim_stale,
            run_queue_counts,
        )

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
        enqueue_item(run_id, 1, 'heimao', 'legacy_crawl', {'partner_id': 1, 'keyword': 'p'}, 5)

        item = claim_next(run_id, 'xhs', 'xhs-0')
        assert item and item['source_id'] == 'xhs'
        item2 = claim_next(run_id, 'xhs', 'xhs-0')
        assert item2 is None

        hm = claim_next(run_id, 'heimao', 'heimao-0')
        assert hm and hm['source_id'] == 'heimao'

        mark_done(item['id'])
        counts = run_queue_counts(run_id)
        assert counts['done'] == 1
        assert counts['claimed'] == 1

        conn = db_mod.get_connection()
        conn.execute(
            "UPDATE crawl_work_queue SET heartbeat_at='2000-01-01T00:00:00+00:00' WHERE id=?",
            (hm['id'],),
        )
        conn.commit()
        n = reclaim_stale(run_id)
        assert n >= 1
        hm2 = claim_next(run_id, 'heimao', 'heimao-0')
        assert hm2 and hm2['id'] == hm['id']
        print('OK test_claim_and_reclaim')
    finally:
        db_mod._db_path = orig_path
        db_mod._conn = None
        try:
            os.remove(path)
        except Exception:
            pass


def test_enqueue_routine():
    import config
    import intel.db as db_mod

    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    orig_path = db_mod._db_path
    try:
        config._config = None
        db_mod._conn = None
        db_mod._db_path = lambda: path
        db_mod.init_schema()

        conn = db_mod.get_connection()
        conn.execute(
            """
            INSERT INTO monitor_tasks(id, name, status, max_pages, fetch_detail, created_at, updated_at)
            VALUES (1, 't', 'idle', 2, 1, datetime('now'), datetime('now'))
            """
        )
        conn.execute(
            """
            INSERT INTO partners(id, name, enabled, created_at, updated_at)
            VALUES (1, '小鹏', 1, datetime('now'), datetime('now'))
            """
        )
        conn.commit()

        from intel.crawl_queue import clear_run_queue, enqueue_routine_for_task, run_queue_counts

        run_id = db_mod.create_task_run(1, 'manual', 'incremental', status='running')
        clear_run_queue(run_id)
        task = {
            'sources': ['heimao', 'xhs'],
            'fetch_detail': True,
            'max_pages': 2,
        }
        partners = [{'id': 1, 'name': '小鹏', 'priority_tier': 'P1', 'monitor_keywords': [], 'aliases': []}]
        n = enqueue_routine_for_task(run_id, 1, task, partners, task['sources'])
        assert n >= 2
        counts = run_queue_counts(run_id)
        assert counts['pending'] == n
        print('OK test_enqueue_routine')
    finally:
        db_mod._db_path = orig_path
        db_mod._conn = None
        try:
            os.remove(path)
        except Exception:
            pass


if __name__ == '__main__':
    test_claim_and_reclaim()
    test_enqueue_routine()
    print('All crawl queue tests passed.')
