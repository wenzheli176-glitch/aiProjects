# -*- coding: utf-8 -*-
"""Crawl 工作队列：list_crawl / legacy_crawl / investigation。"""
import json
import time
from datetime import datetime, timezone

from config import cfg
from intel.db import get_connection, get_partner, _utc_now
from intel.worker_config import run_state_cfg
from source_profiles import crawl_modes_for_task


def _now():
    return _utc_now()


def list_queue_items_for_run(run_id, source_id=None):
    """列出 Run 下队列子任务（含 pending/claimed/done 等）。"""
    conn = get_connection()
    sql = """
        SELECT * FROM crawl_work_queue
        WHERE run_id=?
    """
    params = [run_id]
    if source_id:
        sql += ' AND source_id=?'
        params.append(source_id)
    sql += ' ORDER BY priority_score DESC, id ASC'
    rows = conn.execute(sql, params).fetchall()
    return [_row_work_item(r) for r in rows if r]


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


def enqueue_list_crawl_batches(run_id, task_id, source_id, partners):
    """为 list_first 源（非 xhs keyword）入队 keyword 批次。"""
    from intel.keyword_batch import build_keyword_batches, sort_batches_by_quota
    from intel.priority import refresh_auto_priorities

    refresh_auto_priorities()
    batches = sort_batches_by_quota(build_keyword_batches(partners))
    tier_rank = {'P0': 3, 'P1': 2, 'P2': 1}
    count = 0
    for batch in batches:
        score = tier_rank.get(batch.get('priority_tier') or 'P1', 2) * 10.0
        enqueue_item(
            run_id, task_id, source_id, 'list_crawl',
            {'keyword_batch': batch, 'cohort': batch.get('cohort') or ''},
            priority_score=score,
        )
        count += 1
    return count


def enqueue_routine_for_task(run_id, task_id, task, partners, sources, xhs_keyword_items=None):
    """
    xhs_keyword_items: 预创建的 keyword 子任务列表
      [{keyword, cohort, keyword_run_id}, ...]；为 None 时自动展开全部 keyword。
    """
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
    xhs_list = [s for s in list_sources if s == 'xhs']
    other_list = [s for s in list_sources if s != 'xhs']

    if xhs_list:
        from intel.db import create_keyword_run
        from intel.keyword_pipeline import collect_xhs_keywords
        from intel.source_timeout import resolve_source_timeout_sec

        if xhs_keyword_items is None:
            xhs_keyword_items = []
            for spec in collect_xhs_keywords(partners):
                timeout_sec = resolve_source_timeout_sec(
                    'xhs', partners, keyword=spec['keyword'],
                )
                kr_id = create_keyword_run(
                    run_id, task_id, 'xhs', spec['keyword'], spec.get('cohort') or '',
                    timeout_sec=timeout_sec,
                )
                xhs_keyword_items.append({
                    'keyword': spec['keyword'],
                    'cohort': spec.get('cohort') or '',
                    'keyword_run_id': kr_id,
                    'timeout_sec': timeout_sec,
                })
        for spec in xhs_keyword_items:
            score = tier_rank.get('P1', 2) * 10.0
            enqueue_item(
                run_id, task_id, 'xhs', 'keyword_pipeline',
                {
                    'keyword': spec['keyword'],
                    'cohort': spec.get('cohort') or '',
                    'keyword_run_id': spec.get('keyword_run_id'),
                    'timeout_sec': spec.get('timeout_sec') or 0,
                },
                priority_score=score,
            )
            count += 1

    if other_list:
        for source_id in other_list:
            count += enqueue_list_crawl_batches(run_id, task_id, source_id, partners)

    if xhs_list:
        from intel.db import sync_task_subtask_progress
        sync_task_subtask_progress(task_id, run_id)
    return count


def enqueue_keyword_retry_run(run_id, task_id, keyword_items):
    """仅重跑指定 keyword 子任务（不含 legacy/list_crawl）。"""
    count = 0
    for spec in keyword_items or []:
        enqueue_item(
            run_id, task_id, 'xhs', 'keyword_pipeline',
            {
                'keyword': spec['keyword'],
                'cohort': spec.get('cohort') or '',
                'keyword_run_id': spec.get('keyword_run_id'),
                'timeout_sec': spec.get('timeout_sec') or 0,
            },
            priority_score=10.0,
        )
        count += 1
    return count


def prepare_retry_keyword_items(retry_keyword_run_ids, new_run_id, task_id):
    """从既有失败子任务创建新 run 的 keyword 队列项。"""
    from intel.db import create_keyword_run, get_keyword_run

    items = []
    for old_id in retry_keyword_run_ids or []:
        old = get_keyword_run(int(old_id))
        if not old:
            continue
        kr_id = create_keyword_run(
            new_run_id, task_id, old['source_id'], old['keyword'], old.get('cohort') or '',
            timeout_sec=old.get('timeout_sec') or 0,
        )
        items.append({
            'keyword': old['keyword'],
            'cohort': old.get('cohort') or '',
            'keyword_run_id': kr_id,
            'timeout_sec': old.get('timeout_sec') or 0,
        })
    return items


def claim_next(run_id, source_id, worker_instance_id):
    from intel.run_state import is_halt_requested

    if is_halt_requested(run_id, source_id):
        return None
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


def mark_done(item_id, phase_timing_ms=None):
    conn = get_connection()
    now = _now()
    if phase_timing_ms:
        row = conn.execute(
            'SELECT payload_json FROM crawl_work_queue WHERE id=?', (item_id,),
        ).fetchone()
        payload = {}
        if row:
            try:
                payload = json.loads(row['payload_json'] or '{}')
            except Exception:
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            payload['_phase_timing_ms'] = phase_timing_ms
            conn.execute(
                """
                UPDATE crawl_work_queue
                SET status='done', updated_at=?, payload_json=?
                WHERE id=?
                """,
                (now, json.dumps(payload, ensure_ascii=False), item_id),
            )
            conn.commit()
            return
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


def update_work_item_progress(item_id, progress_patch):
    """合并勘察等工作项 payload 内的进度字段（progress_done 等）。"""
    if not item_id or not isinstance(progress_patch, dict):
        return
    conn = get_connection()
    row = conn.execute(
        'SELECT payload_json FROM crawl_work_queue WHERE id=?', (item_id,),
    ).fetchone()
    if not row:
        return
    try:
        payload = json.loads(row['payload_json'] or '{}')
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.update(progress_patch)
    conn.execute(
        'UPDATE crawl_work_queue SET payload_json=?, updated_at=? WHERE id=?',
        (json.dumps(payload, ensure_ascii=False), _now(), item_id),
    )
    conn.commit()


def _investigation_batch_size():
    return max(1, int(cfg('monitor', 'investigation_batch_size', default=20) or 20))


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


def run_queue_counts_by_source(run_id):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT source_id, status, COUNT(*) AS cnt FROM crawl_work_queue
        WHERE run_id=? GROUP BY source_id, status
        """,
        (run_id,),
    ).fetchall()
    out = {}
    for row in rows:
        sid = row['source_id'] or ''
        out.setdefault(sid, {'pending': 0, 'claimed': 0, 'done': 0, 'failed': 0, 'skipped': 0, 'total': 0})
        st = row['status'] or 'pending'
        if st not in out[sid]:
            out[sid][st] = 0
        out[sid][st] = int(row['cnt'])
        out[sid]['total'] += int(row['cnt'])
    return out


def skip_pending_queue_for_source(run_id, source_id, skip_reason=''):
    conn = get_connection()
    now = _now()
    conn.execute(
        """
        UPDATE crawl_work_queue
        SET status='skipped', skip_reason=?, updated_at=?
        WHERE run_id=? AND source_id=? AND status IN ('pending', 'claimed')
        """,
        ((skip_reason or '')[:500], now, run_id, source_id),
    )
    conn.commit()


def skip_pending_queue_for_run(run_id, skip_reason=''):
    """终止时跳过尚未完成的队列项（含 claimed，避免 Worker 被杀死后 barrier 卡住）。"""
    conn = get_connection()
    now = _now()
    conn.execute(
        """
        UPDATE crawl_work_queue
        SET status='skipped', skip_reason=?, updated_at=?
        WHERE run_id=? AND status IN ('pending', 'claimed')
        """,
        ((skip_reason or '')[:500], now, run_id),
    )
    conn.commit()


def reclaim_claimed_for_source(run_id, source_id):
    """暂停时将被占用队列项释放回 pending，便于继续。"""
    conn = get_connection()
    now = _now()
    conn.execute(
        """
        UPDATE crawl_work_queue
        SET status='pending', worker_instance_id='', claimed_at=NULL,
            heartbeat_at=NULL, updated_at=?
        WHERE run_id=? AND source_id=? AND status='claimed'
        """,
        (now, run_id, source_id),
    )
    conn.commit()


def reclaim_claimed_for_run(run_id):
    conn = get_connection()
    now = _now()
    conn.execute(
        """
        UPDATE crawl_work_queue
        SET status='pending', worker_instance_id='', claimed_at=NULL,
            heartbeat_at=NULL, updated_at=?
        WHERE run_id=? AND status='claimed'
        """,
        (now, run_id),
    )
    conn.commit()


def count_incomplete_queue_by_source(run_id):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT source_id, COUNT(*) AS cnt FROM crawl_work_queue
        WHERE run_id=? AND status IN ('pending', 'claimed')
        GROUP BY source_id
        """,
        (run_id,),
    ).fetchall()
    out = {}
    for row in rows:
        out[row['source_id'] or ''] = int(row['cnt'])
    return out


def copy_incomplete_queue_for_source(old_run_id, new_run_id, task_id, source_id):
    """将旧 Run 中未完成的队列项复制到新 Run（用于继续黑猫等 legacy 源）。"""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT phase, payload_json, priority_score FROM crawl_work_queue
        WHERE run_id=? AND source_id=? AND status IN ('pending', 'claimed')
        ORDER BY id ASC
        """,
        (old_run_id, source_id),
    ).fetchall()
    count = 0
    for row in rows:
        try:
            payload = json.loads(row['payload_json'] or '{}')
        except Exception:
            payload = {}
        enqueue_item(
            new_run_id, task_id, source_id, row['phase'], payload,
            priority_score=row['priority_score'],
        )
        count += 1
    return count


def enqueue_resume_crawl(
    new_run_id, task_id, task, partners, old_run_id, resume_sources, keyword_run_ids=None,
):
    """继续任务：按源入队未完成子任务（xhs keyword + 其他源 queue）。"""
    count = 0
    sources = list(resume_sources or [])
    if 'xhs' in sources and keyword_run_ids:
        items = prepare_retry_keyword_items(keyword_run_ids, new_run_id, task_id)
        count += enqueue_keyword_retry_run(new_run_id, task_id, items)
        sources = [s for s in sources if s != 'xhs']
    for source_id in sources:
        if not source_id:
            continue
        copied = copy_incomplete_queue_for_source(old_run_id, new_run_id, task_id, source_id)
        if copied == 0:
            modes = crawl_modes_for_task(task)
            mode = modes.get(source_id) or 'legacy'
            if source_id == 'heimao' and mode == 'legacy':
                for partner in partners:
                    enqueue_item(
                        new_run_id, task_id, 'heimao', 'legacy_crawl',
                        {'partner_id': partner['id'], 'keyword': partner.get('name') or ''},
                        priority_score=10.0,
                    )
                    count += 1
                continue
            if mode == 'list_first' and source_id != 'xhs':
                count += enqueue_list_crawl_batches(
                    new_run_id, task_id, source_id, partners,
                )
                continue
        count += copied
    return count


def routine_barrier_done(run_id):
    from intel.db import get_source_halt_map, is_run_pause_requested, is_run_stop_requested

    global_halt = is_run_pause_requested(run_id) or is_run_stop_requested(run_id)
    halts = get_source_halt_map(run_id)
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT source_id, status, COUNT(*) AS cnt FROM crawl_work_queue
        WHERE run_id=? AND status IN ('pending', 'claimed')
        GROUP BY source_id, status
        """,
        (run_id,),
    ).fetchall()
    for row in rows:
        sid = row['source_id'] or ''
        if global_halt or halts.get(sid) in ('pause', 'stop'):
            continue
        if int(row['cnt']) > 0:
            return False
    return True


def source_queue_idle(run_id, source_id):
    """指定源 routine 队列是否已全部完成（无 pending/claimed）。"""
    qc = run_queue_counts_by_source(run_id).get(source_id) or {}
    open_count = int(qc.get('pending', 0)) + int(qc.get('claimed', 0))
    return open_count == 0 and int(qc.get('total', 0)) > 0


def wait_routine_barrier(run_id, timeout_check=None, poll_sec=2, log_fn=None, on_poll=None):
    while True:
        reclaim_stale(run_id)
        if on_poll:
            try:
                on_poll()
            except Exception as e:
                if log_fn:
                    log_fn('[queue] on_poll 异常: %s' % str(e)[:200], 'WARN')
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


def wait_queue_barrier(run_id, timeout_check=None, poll_sec=2, log_fn=None, on_poll=None):
    """等待 run 内 crawl_work_queue 全部完成（routine 或 investigation）。"""
    return wait_routine_barrier(
        run_id, timeout_check=timeout_check, poll_sec=poll_sec, log_fn=log_fn, on_poll=on_poll,
    )


def enqueue_investigation_work_items(run_id, task_id, source_ids=None):
    """将 investigation_queue 按 source 分组、按批次写入 crawl_work_queue。"""
    from intel.db import list_investigation_queue, list_raw_records

    allowed = set(source_ids or [])
    queue = list_investigation_queue(task_id, status='pending')
    if not queue:
        return 0, []

    raw_by_id = {r['id']: r for r in list_raw_records(task_id)}
    by_source = {}
    for item in queue:
        sid = item.get('source') or ''
        if allowed and sid not in allowed:
            continue
        by_source.setdefault(sid, []).append(item)

    batch_size = _investigation_batch_size()
    count = 0
    source_ids = []
    for source_id, items in by_source.items():
        payload_items_all = []
        for it in items:
            raw = raw_by_id.get(it.get('raw_id')) or {}
            payload = raw.get('payload') or {}
            kw = (payload.get('_search_keyword') or raw.get('keyword') or '').strip()
            payload_items_all.append({
                'queue_id': it['id'],
                'raw_id': it.get('raw_id'),
                'url': it.get('url') or '',
                'keyword': kw,
            })
        inv_total = len(payload_items_all)
        batch_total = (inv_total + batch_size - 1) // batch_size if inv_total else 0
        for bi in range(batch_total):
            chunk_items = items[bi * batch_size:(bi + 1) * batch_size]
            chunk = []
            for it in chunk_items:
                raw = raw_by_id.get(it.get('raw_id')) or {}
                payload = raw.get('payload') or {}
                kw = (payload.get('_search_keyword') or raw.get('keyword') or '').strip()
                chunk.append({
                    'queue_id': it['id'],
                    'raw_id': it.get('raw_id'),
                    'url': it.get('url') or '',
                    'keyword': kw,
                })
            if not chunk:
                continue
            priority = max((float(it.get('priority_score') or 0) for it in chunk_items), default=0)
            enqueue_item(
                run_id, task_id, source_id, 'investigation',
                {
                    'items': chunk,
                    'queue_item_ids': [it['queue_id'] for it in chunk],
                    'urls': [it.get('url') or '' for it in chunk],
                    'batch_index': bi + 1,
                    'batch_total': batch_total,
                    'investigation_total': inv_total,
                    'progress_done': 0,
                    'progress_total': len(chunk),
                },
                priority_score=priority,
            )
            count += 1
        source_ids.append(source_id)
    return count, source_ids
