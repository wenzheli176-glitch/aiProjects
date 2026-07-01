# -*- coding: utf-8 -*-
"""监测 Run 活跃状态与停止/暂停请求（替代仅依赖 S.running）。"""
ACTIVE_TASK_STATUSES = ('crawling', 'analyzing')
HALT_TASK_STATUSES = ('paused', 'stopped')


def has_active_monitor_run():
    """是否存在进行中的监测任务（DB 任务状态或未结束的 run 记录）。"""
    from intel.db import (
        get_connection,
        reclaim_orphaned_task_runs,
        reclaim_stale_task_runs,
        reclaim_zombie_task_runs,
    )

    reclaim_stale_task_runs()
    reclaim_orphaned_task_runs()
    reclaim_zombie_task_runs()
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
          AND COALESCE(pause_requested, 0) = 0
          AND COALESCE(stop_requested, 0) = 0
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


def is_reanalyze_allowed(task_id, analyze_mode='incremental'):
    """是否允许 reanalyze：本任务 crawling/analyzing 时 incremental 放行（含 crawl_only）。"""
    from intel.db import count_raw_records, get_monitor_task

    task = get_monitor_task(task_id)
    if not task:
        return False, '任务不存在'
    if count_raw_records(task_id) <= 0:
        return False, '无原始数据，请先执行完整监测'
    if analyze_mode == 'full_replace':
        if task.get('status') in ('crawling', 'analyzing'):
            return False, '任务运行中不可全量重分析'
        if is_monitor_busy():
            return False, '已有其他任务进行中'
        return True, ''
    if task.get('status') in ('crawling', 'analyzing'):
        return True, ''
    if is_monitor_busy():
        return False, '已有任务进行中'
    return True, ''


def is_pause_requested(run_id, source_id=None):
    if not run_id:
        return False
    from intel.db import get_source_halt_kind, is_run_pause_requested

    if is_run_pause_requested(run_id):
        return True
    if source_id:
        return get_source_halt_kind(run_id, source_id) == 'pause'
    return False


def is_stop_requested(run_id, source_id=None):
    if not run_id:
        return False
    from intel.db import get_source_halt_kind, is_run_stop_requested

    if is_run_stop_requested(run_id):
        return True
    if source_id:
        return get_source_halt_kind(run_id, source_id) == 'stop'
    return False


def is_halt_requested(run_id, source_id=None):
    return is_pause_requested(run_id, source_id) or is_stop_requested(run_id, source_id)


def is_task_halted(task_id):
    from intel.db import get_monitor_task

    task = get_monitor_task(task_id)
    return bool(task and task.get('status') in HALT_TASK_STATUSES)


def _sync_source_halt_progress(task_id, run_id, task, status=None):
    from intel.db import get_source_halt_map, update_task_status

    halts = get_source_halt_map(run_id)
    cur_status = status or (task or {}).get('status') or 'crawling'
    update_task_status(
        task_id,
        cur_status,
        progress={
            'run_id': run_id,
            'resume_run_id': run_id,
            'source_halt': halts,
            'phase': 'crawl',
        },
    )


def _all_sources_paused(task, run_id):
    sources = (task or {}).get('sources') or []
    if not sources:
        return False
    from intel.db import get_source_halt_map

    halts = get_source_halt_map(run_id)
    return all(halts.get(s) == 'pause' for s in sources)


def _apply_source_halt(run_id, source_id, kind, task_id=None, task=None):
    from intel.crawl_queue import reclaim_claimed_for_source, skip_pending_queue_for_source
    from intel.db import append_run_log, reset_interrupted_keyword_runs_for_source, set_source_halt
    from intel.worker_pool import terminate_workers_for_source

    set_source_halt(run_id, source_id, kind)
    reset_interrupted_keyword_runs_for_source(run_id, source_id)
    if kind == 'pause':
        reclaim_claimed_for_source(run_id, source_id)
    elif kind == 'stop':
        skip_pending_queue_for_source(run_id, source_id, '用户终止')
    killed = terminate_workers_for_source(run_id, source_id)
    append_run_log(
        run_id,
        '已请求%s数据源 %s（终止 Worker %d 个）' % (
            '暂停' if kind == 'pause' else '终止', source_id, killed,
        ),
        level='INFO',
    )
    if task_id and task:
        if _all_sources_paused(task, run_id):
            _apply_global_halt(task_id, run_id, 'pause')
        else:
            _sync_source_halt_progress(task_id, run_id, task)


def _apply_global_halt(task_id, run_id, kind):
    from intel.crawl_queue import reclaim_claimed_for_run, skip_pending_queue_for_run
    from intel.db import (
        append_run_log,
        cancel_incomplete_keyword_runs,
        clear_run_halt_flags,
        fail_running_analysis_jobs,
        reset_interrupted_keyword_runs,
        set_run_pause_requested,
        set_run_stop_requested,
        sync_task_subtask_progress,
        update_task_status,
        finish_task_run,
    )
    from intel.worker_pool import terminate_workers_for_run

    msg = '任务已暂停' if kind == 'pause' else '用户终止'
    status = 'paused' if kind == 'pause' else 'stopped'
    if kind == 'pause':
        set_run_pause_requested(run_id, True)
        reclaim_claimed_for_run(run_id)
        reset_interrupted_keyword_runs(run_id)
    else:
        set_run_stop_requested(run_id, True)
        skip_pending_queue_for_run(run_id, '用户终止')
        cancel_incomplete_keyword_runs(run_id, reason=msg)
        fail_running_analysis_jobs(task_id, run_id=run_id, error_message=msg)
    update_task_status(
        task_id,
        status,
        error_message=msg,
        progress={
            'phase': 'crawl',
            'halt': status,
            'run_id': run_id,
            'resume_run_id': run_id if kind == 'pause' else None,
        },
    )
    terminate_workers_for_run(run_id)
    if kind == 'pause':
        finish_task_run(run_id, 'paused', error_message=msg)
        clear_run_halt_flags(run_id)
        append_run_log(run_id, '任务已暂停，Run 已挂起', level='INFO')
    elif kind == 'stop':
        finish_task_run(run_id, 'stopped', error_message=msg)
        clear_run_halt_flags(run_id)
        append_run_log(run_id, '任务已终止，Run 已结束', level='INFO')
    try:
        sync_task_subtask_progress(task_id, run_id)
    except Exception:
        pass
    try:
        from crawler_web import S
        S.running = False
    except Exception:
        pass


def resolve_run_halt_after_crawl(run_id):
    """爬取阶段结束后，根据 per-source halt 推断任务级 halt（无全局 halt 时）。"""
    from intel.db import get_source_halt_map, is_run_pause_requested, is_run_stop_requested

    if is_run_pause_requested(run_id):
        return 'paused'
    if is_run_stop_requested(run_id):
        return 'stopped'
    halts = get_source_halt_map(run_id)
    if not halts:
        return ''
    if any(v == 'pause' for v in halts.values()):
        return 'paused'
    if any(v == 'stop' for v in halts.values()):
        return 'stopped'
    return ''


def request_task_halt(task_id, kind, source_id='all'):
    """
    请求暂停或终止指定任务。kind: 'pause' | 'stop'。
    source_id: 'all' 表示全部数据源，否则为单个 source_id（仅 pause 生效；stop 始终结束整任务）。
    """
    from intel.db import append_run_log, get_monitor_task, resolve_active_run_id, sync_task_subtask_progress

    task = get_monitor_task(task_id)
    if not task:
        return False, '任务不存在'
    if task['status'] not in ACTIVE_TASK_STATUSES:
        return False, '任务未在运行中'
    run_id = resolve_active_run_id(task_id, task)
    if not run_id:
        return False, '无活跃 Run'
    src = (source_id or 'all').strip()
    if kind not in ('pause', 'stop'):
        return False, '无效操作'
    if kind == 'stop':
        _apply_global_halt(task_id, run_id, 'stop')
        if src not in ('', 'all', '*'):
            append_run_log(run_id, '用户从数据源 %s 发起终止（整任务已结束）' % src, level='INFO')
        return True, ''
    if src in ('', 'all', '*'):
        _apply_global_halt(task_id, run_id, kind)
    else:
        sources = task.get('sources') or []
        if src not in sources:
            return False, '该任务未包含数据源: %s' % src
        _apply_source_halt(run_id, src, kind, task_id=task_id, task=task)
        try:
            sync_task_subtask_progress(task_id, run_id)
        except Exception:
            pass
    return True, ''


def request_stop_active_runs():
    """停止当前活跃 run（全局停止按钮）。"""
    from intel.crawl_queue import skip_pending_queue_for_run
    from intel.db import (
        finish_task_run,
        get_connection,
        mark_active_runs_stop_requested,
        sync_task_subtask_progress,
        update_task_status,
    )
    from intel.db import cancel_incomplete_keyword_runs
    from intel.worker_pool import terminate_workers_for_run

    try:
        from crawler_web import S
        S.running = False
    except Exception:
        pass
    mark_active_runs_stop_requested()
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, task_id FROM monitor_task_runs
        WHERE status='running' AND (finished_at IS NULL OR finished_at = '')
        """
    ).fetchall()
    for row in rows:
        skip_pending_queue_for_run(row['id'], '用户终止')
        cancel_incomplete_keyword_runs(row['id'], reason='用户终止')
        terminate_workers_for_run(row['id'])
        sync_task_subtask_progress(row['task_id'], row['id'])
        finish_task_run(row['id'], 'stopped', error_message='用户终止')
        update_task_status(
            row['task_id'],
            'stopped',
            error_message='用户终止',
            progress={
                'phase': 'crawl',
                'halt': 'stopped',
                'run_id': row['id'],
                'resume_run_id': row['id'],
            },
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
