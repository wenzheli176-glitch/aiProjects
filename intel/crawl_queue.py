# -*- coding: utf-8 -*-
"""Crawl 工作队列：list_crawl / legacy_crawl / investigation。"""
import json
import time
from datetime import datetime, timezone

from config import cfg
from intel.db import get_connection, get_partner, _utc_now
from intel.keyword_batch import build_keyword_batches, sort_batches_by_quota
from intel.worker_config import run_state_cfg
from source_profiles import crawl_modes_for_task


def _now():
    return _utc_now()


def _row_work_item(row):
    if not row:
        return None
    keys = row.keys()
    try:
        payload = json.loads(row['payload_json'] or '{}')
    except Exception:
        payload = {}
    return {
        'id': row['id'],
        'run_id': row['run_id'],
        'task_id': row['task_id'],
        'source_id': row['source_id'],
        'phase': row['phase'],
        'payload': payload,
        'priority_score': row['priority_score'],
        'worker_instance_id': row['worker_instance_id'] if 'worker_instance_id' in keys else '',
        'status': row['status'],
        'claimed_at': row['claimed_at'] if 'claimed_at' in keys else None,
        'heartbeat_at': row['heartbeat_at'] if 'heartbeat_at' in keys else None,
        'skip_reason': row['skip_reason'] if 'skip_reason' in keys else '',
        'error_message': row['error_message'] if 'error_message' in keys else '',
    }


def clear_run_queue(run_id):
    conn = get_connection()
    conn.execute('DELETE FROM crawl_work_queue WHERE run_id=?', (run_id,))
    conn.commit()


def enqueue_item(run_id, task_id, source_id, phase, payload, priority_score=0):
    conn = get_connection()
    now = _now()
    cur = conn.execute(
        """
        INSERT INTO crawl_work_queue(
            run_id, task_id, source_id, phase, payload_json, priority_score,
            status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        """,
        (
            run_id, task_id, source_id, phase,
            json.dumps(payload or {}, ensure_ascii=False),
            float(priority_score or 0), now, now,
        ),
    )
    conn.commit()
    return cur.lastrowid


def enqueue_routine_for_task(run_id, task_id, task, partners, sources):
    modes = crawl_modes_for_task(task)
    count = 0
    tier_rank = {'P0': 3, 'P1': 2, 'P2': 1}

    legacy_sources = [s for s in sources if modes.get(s) == 'legacy']
    for source_id in legacy_sources:
        for partner in partners:
            score = tier_rank.get(partner.get('priority_tier') or 'P1', 2) * 10.0
            enqueue_item(
                run_id, task_id, source_id, 'legacy_crawl',
                {'partner_id': partner['id'], 'keyword': partner.get('name') or ''},
                priority_score=score,
            )
            count += 1

    list_sources = [s for s in sources if modes.get(s) == 'list_first']
    if list_sources:
        batches = sort_batches_by_quota(build_keyword_batches(partners))
        for batch in batches:
            score = tier_rank.get(batch.get('priority_tier') or 'P1', 2) * 10.0
            for source_id in list_sources:
                enqueue_item(
                    run_id, task_id, source_id, 'list_crawl',
                    {'keyword_batch': batch, 'cohort': batch.get('cohort') or ''},
                    priority_score=score,
                )
                count += 1
    return count


def claim_next(run_id, source_id, worker_instance_id):
    conn = get_connection()
    row = conn.execute(
        """
        SELECT id FROM crawl_work_queue
        WHERE run_id=? AND source_id=? AND status='pending'
        ORDER BY priority_score DESC, id ASC
        LIMIT 1
        """,
        (run_id, source_id),
    ).fetchone()
    if not row:
        return None
    now = _now()
    cur = conn.execute(
        """
        UPDATE crawl_work_queue
        SET status='claimed', worker_instance_id=?, claimed_at=?, heartbeat_at=?, updated_at=?
        WHERE id=? AND status='pending'
        """,
        (worker_instance_id, now, now, now, row['id']),
    )
    conn.commit()
    if cur.rowcount != 1:
        return claim_next(run_id, source_id, worker_instance_id)
    return get_work_item(row['id'])


def get_work_item(item_id):
    conn = get_connection()
    row = conn.execute('SELECT * FROM crawl_work_queue WHERE id=?', (item_id,)).fetchone()
    return _row_work_item(row)


def touch_heartbeat(item_id):
    conn = get_connection()
    now = _now()
    conn.execute(
        'UPDATE crawl_work_queue SET heartbeat_at=?, updated_at=? WHERE id=?',
        (now, now, item_id),
    )
    conn.commit()


def mark_done(item_id):
    conn = get_connection()
    now = _now()
    conn.execute(
        "UPDATE crawl_work_queue SET status='done', updated_at=? WHERE id=?",
        (now, item_id),
    )
    conn.commit()


def mark_failed(item_id, error_message=''):
    conn = get_connection()
    now = _now()
    conn.execute(
        """
        UPDATE crawl_work_queue SET status='failed', error_message=?, updated_at=?
        WHERE id=?
        """,
        ((error_message or '')[:2000], now, item_id),
    )
    conn.commit()


def mark_skipped(item_id, skip_reason=''):
    conn = get_connection()
    now = _now()
    conn.execute(
        """
        UPDATE crawl_work_queue SET status='skipped', skip_reason=?, updated_at=?
        WHERE id=?
        """,
        ((skip_reason or '')[:500], now, item_id),
    )
    conn.commit()


def _parse_ts(iso_s):
    if not iso_s:
        return None
    try:
        s = str(iso_s).strip()
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp()
    except Exception:
        return None


def reclaim_stale(run_id=None):
    timeout = run_state_cfg()['claim_timeout_sec']
    conn = get_connection()
    now = _now()
    rows = conn.execute(
        """
        SELECT id, claimed_at, heartbeat_at FROM crawl_work_queue
        WHERE status='claimed' AND (? IS NULL OR run_id=?)
        """,
        (run_id, run_id),
    ).fetchall()
    reclaimed = 0
    for row in rows:
        ref = row['heartbeat_at'] or row['claimed_at']
        ref_ts = _parse_ts(ref)
        if ref_ts is None:
            continue
        if (time.time() - ref_ts) > timeout:
            conn.execute(
                """
                UPDATE crawl_work_queue
                SET status='pending', worker_instance_id='', claimed_at=NULL,
                    heartbeat_at=NULL, updated_at=?
                WHERE id=? AND status='claimed'
                """,
                (now, row['id']),
            )
            reclaimed += 1
    conn.commit()
    return reclaimed


def run_queue_counts(run_id):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT status, COUNT(*) AS cnt FROM crawl_work_queue
        WHERE run_id=? GROUP BY status
        """,
        (run_id,),
    ).fetchall()
    counts = {'pending': 0, 'claimed': 0, 'done': 0, 'failed': 0, 'skipped': 0}
    for row in rows:
        counts[row['status']] = int(row['cnt'])
    counts['total'] = sum(counts.values())
    return counts


def routine_barrier_done(run_id):
    counts = run_queue_counts(run_id)
    pending = counts.get('pending', 0) + counts.get('claimed', 0)
    return pending == 0


def wait_routine_barrier(run_id, timeout_check=None, poll_sec=2, log_fn=None):
    while True:
        reclaim_stale(run_id)
        if routine_barrier_done(run_id):
            return True
        if timeout_check and timeout_check():
            return False
        if log_fn:
            c = run_queue_counts(run_id)
            log_fn('[queue] 进度 pending=%d claimed=%d done=%d failed=%d' % (
                c.get('pending', 0), c.get('claimed', 0), c.get('done', 0), c.get('failed', 0),
            ))
        time.sleep(max(0.5, float(poll_sec)))


def wait_queue_barrier(run_id, timeout_check=None, poll_sec=2, log_fn=None):
    """等待 run 内 crawl_work_queue 全部完成（routine 或 investigation）。"""
    return wait_routine_barrier(run_id, timeout_check=timeout_check, poll_sec=poll_sec, log_fn=log_fn)


def enqueue_investigation_work_items(run_id, task_id):
    """将 investigation_queue 按 source 分组写入 crawl_work_queue。"""
    from intel.db import list_investigation_queue, list_raw_records

    queue = list_investigation_queue(task_id, status='pending')
    if not queue:
        return 0, []

    raw_by_id = {r['id']: r for r in list_raw_records(task_id)}
    by_source = {}
    for item in queue:
        by_source.setdefault(item['source'], []).append(item)

    count = 0
    source_ids = []
    for source_id, items in by_source.items():
        payload_items = []
        for it in items:
            raw = raw_by_id.get(it.get('raw_id')) or {}
            payload = raw.get('payload') or {}
            kw = (payload.get('_search_keyword') or raw.get('keyword') or '').strip()
            payload_items.append({
                'queue_id': it['id'],
                'raw_id': it.get('raw_id'),
                'url': it.get('url') or '',
                'keyword': kw,
            })
        priority = max((float(it.get('priority_score') or 0) for it in items), default=0)
        enqueue_item(
            run_id, task_id, source_id, 'investigation',
            {
                'items': payload_items,
                'queue_item_ids': [it['id'] for it in items],
                'urls': [it.get('url') or '' for it in items],
            },
            priority_score=priority,
        )
        count += 1
        source_ids.append(source_id)
    return count, source_ids
