# -*- coding: utf-8 -*-
"""Run 级 xhs investigation 弹窗配额（多 Worker 共享）。"""
import json

from config import cfg


def get_max_modal_per_run():
    inv = (cfg('xhs') or {}).get('investigation_detail') or {}
    try:
        return int(inv.get('max_modal_per_run') or 0)
    except (TypeError, ValueError):
        return 0


def _read_run_stats(conn, run_id):
    row = conn.execute(
        'SELECT stats_json FROM monitor_task_runs WHERE id=?', (run_id,),
    ).fetchone()
    if not row:
        return {}
    try:
        stats = json.loads(row['stats_json'] or '{}')
    except Exception:
        stats = {}
    return stats if isinstance(stats, dict) else {}


def _write_run_stats(conn, run_id, stats):
    conn.execute(
        'UPDATE monitor_task_runs SET stats_json=? WHERE id=?',
        (json.dumps(stats, ensure_ascii=False), run_id),
    )


def get_modal_quota_state(run_id):
    from intel.db import get_connection

    stats = _read_run_stats(get_connection(), run_id)
    return {
        'max_modal_per_run': get_max_modal_per_run(),
        'investigation_modal_done': int(stats.get('investigation_modal_done') or 0),
        'investigation_skipped_quota': int(stats.get('investigation_skipped_quota') or 0),
    }


def is_quota_exhausted(run_id):
    max_m = get_max_modal_per_run()
    if max_m <= 0:
        return False
    state = get_modal_quota_state(run_id)
    return state['investigation_modal_done'] >= max_m


def reserve_modal_slot(run_id):
    """原子预占弹窗配额（打开弹窗前调用）；成功弹窗后保留计数，失败需 release。"""
    max_m = get_max_modal_per_run()
    if max_m <= 0:
        return True
    from intel.db import get_connection

    conn = get_connection()
    conn.execute('BEGIN IMMEDIATE')
    try:
        stats = _read_run_stats(conn, run_id)
        done = int(stats.get('investigation_modal_done') or 0)
        if done >= max_m:
            conn.execute('ROLLBACK')
            return False
        stats['investigation_modal_done'] = done + 1
        _write_run_stats(conn, run_id, stats)
        conn.commit()
        return True
    except Exception:
        try:
            conn.execute('ROLLBACK')
        except Exception:
            pass
        raise


def release_modal_slot(run_id):
    """弹窗尝试失败时回滚预占。"""
    max_m = get_max_modal_per_run()
    if max_m <= 0:
        return
    from intel.db import get_connection

    conn = get_connection()
    conn.execute('BEGIN IMMEDIATE')
    try:
        stats = _read_run_stats(conn, run_id)
        done = int(stats.get('investigation_modal_done') or 0)
        stats['investigation_modal_done'] = max(0, done - 1)
        _write_run_stats(conn, run_id, stats)
        conn.commit()
    except Exception:
        try:
            conn.execute('ROLLBACK')
        except Exception:
            pass
        raise


def record_skipped_quota(run_id, count=1):
    if not run_id or count <= 0:
        return
    from intel.db import get_connection

    conn = get_connection()
    conn.execute('BEGIN IMMEDIATE')
    try:
        stats = _read_run_stats(conn, run_id)
        skipped = int(stats.get('investigation_skipped_quota') or 0)
        stats['investigation_skipped_quota'] = skipped + int(count)
        _write_run_stats(conn, run_id, stats)
        conn.commit()
    except Exception:
        try:
            conn.execute('ROLLBACK')
        except Exception:
            pass
        raise


def sync_modal_quota_to_run_metrics(run_id, run_metrics):
    """将 DB 中 Run 级弹窗配额 stats 合并进 RunMetrics。"""
    if not run_metrics or not run_id:
        return
    state = get_modal_quota_state(run_id)
    run_metrics.stats['investigation_modal_done'] = state['investigation_modal_done']
    run_metrics.stats['investigation_skipped_quota'] = state['investigation_skipped_quota']
