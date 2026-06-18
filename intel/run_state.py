# -*- coding: utf-8 -*-
"""监测 Run 活跃状态与停止请求（替代仅依赖 S.running）。"""
ACTIVE_TASK_STATUSES = ('crawling', 'analyzing')


def has_active_monitor_run():
    """是否存在进行中的监测任务（DB 任务状态或未结束的 run 记录）。"""
    from intel.db import get_connection, reclaim_stale_task_runs

    reclaim_stale_task_runs()
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM monitor_tasks WHERE status IN (?, ?) LIMIT 1",
        ACTIVE_TASK_STATUSES,
    ).fetchone()
    if row:
        return True
    row = conn.execute(
        """
        SELECT 1 FROM monitor_task_runs
        WHERE status = 'running'
          AND (finished_at IS NULL OR finished_at = '')
        LIMIT 1
        """
    ).fetchone()
    return bool(row)


def is_monitor_busy():
    """监测 Run 或 Flask 内手动爬取占用。"""
    try:
        from crawler_web import S
        if S.running:
            return True
    except Exception:
        pass
    return has_active_monitor_run()


def is_stop_requested(run_id):
    if not run_id:
        return False
    from intel.db import is_run_stop_requested
    return is_run_stop_requested(run_id)


def request_stop_active_runs():
    """停止当前活跃 run（DB 标记 + S.running）。"""
    from intel.db import get_connection, mark_active_runs_stop_requested
    try:
        from crawler_web import S
        S.running = False
    except Exception:
        pass
    mark_active_runs_stop_requested()
    conn = get_connection()
    conn.execute(
        "UPDATE monitor_tasks SET status='failed', error_message=? "
        "WHERE status IN (?, ?)",
        ('用户停止', 'crawling', 'analyzing'),
    )
    conn.commit()


def get_active_run_id():
    """返回当前 running 的 monitor_task_run id，无则 None。"""
    from intel.db import get_connection

    conn = get_connection()
    row = conn.execute(
        """
        SELECT id FROM monitor_task_runs
        WHERE status = 'running'
          AND (finished_at IS NULL OR finished_at = '')
        ORDER BY id DESC LIMIT 1
        """
    ).fetchone()
    return row['id'] if row else None


def get_active_run_worker_states():
    """读取活跃 run 的 worker_state_json（Orchestrator /api/status 聚合用）。"""
    run_id = get_active_run_id()
    if not run_id:
        return run_id, {}
    from intel.db import get_connection
    import json

    conn = get_connection()
    row = conn.execute(
        'SELECT worker_state_json FROM monitor_task_runs WHERE id=?', (run_id,),
    ).fetchone()
    if not row:
        return run_id, {}
    try:
        state = json.loads(row['worker_state_json'] or '{}')
    except Exception:
        state = {}
    return run_id, state if isinstance(state, dict) else {}


def aggregate_worker_login_waits(worker_state):
    """从 worker_state 提取各实例 login_wait 列表。"""
    waits = []
    for instance_id, inst in (worker_state or {}).items():
        if not isinstance(inst, dict):
            continue
        lw = inst.get('login_wait')
        if not lw:
            continue
        item = dict(lw)
        item['instance_id'] = instance_id
        item['source_id'] = inst.get('source_id') or ''
        waits.append(item)
    return waits
