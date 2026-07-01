# -*- coding: utf-8 -*-
"""Orchestrator：spawn Worker 并等待 queue barrier。"""
import threading
import time

from intel.crawl_queue import (
    clear_run_queue,
    enqueue_investigation_work_items,
    enqueue_routine_for_task,
    wait_queue_barrier,
)
from intel.worker import spawn_worker_process
from intel.worker_config import instances_for_sources, validate_worker_instances

_worker_procs_lock = threading.Lock()
_worker_procs_by_run = {}


def _register_worker_procs(run_id, entries):
    if not run_id or not entries:
        return
    with _worker_procs_lock:
        bucket = _worker_procs_by_run.setdefault(int(run_id), [])
        for entry in entries:
            if entry not in bucket:
                bucket.append(entry)


def _unregister_worker_procs(run_id, entries):
    if not run_id:
        return
    with _worker_procs_lock:
        bucket = _worker_procs_by_run.get(int(run_id), [])
        for entry in entries or []:
            if entry in bucket:
                bucket.remove(entry)
        if not bucket:
            _worker_procs_by_run.pop(int(run_id), None)


def _procs_from_entries(entries):
    return [e['proc'] for e in (entries or []) if e.get('proc')]


def register_worker_proc(run_id, source_id, proc):
    if not run_id or not proc:
        return
    _register_worker_procs(run_id, [{'proc': proc, 'source_id': source_id or ''}])


def _kill_pid_tree(pid):
    import os
    import sys

    if not pid:
        return False
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    try:
        if sys.platform == 'win32':
            import subprocess
            subprocess.run(
                ['taskkill', '/F', '/T', '/PID', str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )
        else:
            import signal
            os.kill(pid, signal.SIGKILL)
        return True
    except Exception:
        return False


def _kill_workers_from_state(run_id, source_id=None):
    from intel.db import get_task_run

    run = get_task_run(run_id)
    if not run:
        return 0
    state = run.get('worker_state') or {}
    killed = 0
    for inst in state.values():
        if not isinstance(inst, dict):
            continue
        sid = inst.get('source_id') or ''
        if source_id and sid != source_id:
            continue
        pid = inst.get('pid')
        if pid and _kill_pid_tree(pid):
            killed += 1
    return killed


def terminate_workers_for_source(run_id, source_id):
    """终止指定 Run 中某一数据源的 Worker 子进程。"""
    if not run_id or not source_id:
        return 0
    with _worker_procs_lock:
        bucket = _worker_procs_by_run.get(int(run_id), [])
        targets = [e for e in bucket if e.get('source_id') == source_id]
    killed = 0
    for entry in targets:
        p = entry.get('proc')
        if not p:
            continue
        if p.is_alive():
            try:
                if hasattr(p, 'kill'):
                    p.kill()
                else:
                    p.terminate()
                killed += 1
            except Exception:
                pass
    if targets:
        deadline = time.monotonic() + 5
        for entry in targets:
            p = entry.get('proc')
            if p:
                p.join(timeout=max(0, deadline - time.monotonic()))
    _unregister_worker_procs(run_id, targets)
    killed += _kill_workers_from_state(run_id, source_id)
    return killed


def terminate_workers_for_run(run_id, reason='用户终止'):
    """终止指定 Run 的全部 Worker 子进程。"""
    if not run_id:
        return 0
    with _worker_procs_lock:
        targets = list(_worker_procs_by_run.get(int(run_id), []))
    killed = 0
    for entry in targets:
        p = entry.get('proc')
        if not p:
            continue
        if p.is_alive():
            try:
                if hasattr(p, 'kill'):
                    p.kill()
                else:
                    p.terminate()
                killed += 1
            except Exception:
                pass
    if targets:
        deadline = time.monotonic() + 5
        for entry in targets:
            p = entry.get('proc')
            if p:
                p.join(timeout=max(0, deadline - time.monotonic()))
    _unregister_worker_procs(run_id, targets)
    killed += _kill_workers_from_state(run_id)
    return killed


def _join_worker_processes(entries, join_sec=15):
    procs = _procs_from_entries(entries)
    deadline = time.monotonic() + join_sec
    for p in procs:
        p.join(timeout=max(0, deadline - time.monotonic()))
    for p in procs:
        if p.is_alive():
            p.terminate()
            p.join(timeout=3)


def _spawn_workers(run_id, task_id, source_ids, log_fn=None):
    instances = instances_for_sources(source_ids)
    errs = validate_worker_instances(instances)
    if errs:
        for e in errs:
            if log_fn:
                log_fn('[orchestrator] Worker 配置错误: %s' % e, 'ERROR')
        return []
    entries = []
    for inst in instances:
        sid = inst.get('source_id')
        if sid not in source_ids:
            continue
        p = spawn_worker_process(run_id, task_id, sid, inst)
        entries.append({'proc': p, 'source_id': sid})
        if log_fn:
            log_fn('[orchestrator] 启动 Worker %s port=%s' % (
                inst.get('instance_id'), inst.get('cdp_port'),
            ))
    return entries


def run_routine_crawl_with_workers(
    run_id,
    task_id,
    task,
    partners,
    sources,
    log_fn=None,
    timeout_check=None,
    on_poll=None,
):
    from intel.db import sync_task_subtask_progress

    clear_run_queue(run_id)
    n = enqueue_routine_for_task(run_id, task_id, task, partners, sources)
    sync_task_subtask_progress(task_id, run_id)
    if log_fn:
        log_fn('[orchestrator] 入队 routine 工作项 %d 个' % n)

    if n == 0:
        return True

    entries = _spawn_workers(run_id, task_id, sources, log_fn=log_fn)
    if not entries:
        if log_fn:
            log_fn('[orchestrator] 无 Worker 实例配置', 'ERROR')
        return False

    _register_worker_procs(run_id, entries)
    try:
        return wait_queue_barrier(
            run_id, timeout_check=timeout_check, log_fn=log_fn, on_poll=on_poll,
        )
    finally:
        _join_worker_processes(entries)
        _unregister_worker_procs(run_id, entries)


def run_resume_crawl_with_workers(
    run_id,
    task_id,
    source_ids,
    log_fn=None,
    timeout_check=None,
):
    """继续执行：仅为指定数据源启动 Worker（队列项需已入队）。"""
    from intel.crawl_queue import run_queue_counts
    from intel.db import sync_task_subtask_progress

    sync_task_subtask_progress(task_id, run_id)
    n = run_queue_counts(run_id).get('total', 0)
    if log_fn:
        log_fn('[orchestrator] 继续爬取入队 %d 个（源: %s）' % (
            n, ','.join(source_ids or []) or '-',
        ))
    if n == 0:
        return True

    entries = _spawn_workers(run_id, task_id, source_ids, log_fn=log_fn)
    if not entries:
        if log_fn:
            log_fn('[orchestrator] 继续执行无可用 Worker', 'ERROR')
        return False

    _register_worker_procs(run_id, entries)
    try:
        return wait_queue_barrier(run_id, timeout_check=timeout_check, log_fn=log_fn)
    finally:
        _join_worker_processes(entries)
        _unregister_worker_procs(run_id, entries)


def run_keyword_retry_with_workers(
    run_id,
    task_id,
    log_fn=None,
    timeout_check=None,
):
    """仅重跑 xhs keyword_pipeline 子任务。"""
    return run_resume_crawl_with_workers(
        run_id, task_id, ['xhs'], log_fn=log_fn, timeout_check=timeout_check,
    )


def run_investigation_crawl_with_workers(
    run_id,
    task_id,
    sources,
    log_fn=None,
    timeout_check=None,
    run_metrics=None,
    crawl_only=None,
):
    from intel.db import get_monitor_task, sync_task_subtask_progress

    task = get_monitor_task(task_id)
    partners = None
    if task:
        from intel.runner import _get_enabled_partners
        partners = _get_enabled_partners(task)

    n, source_ids = enqueue_investigation_work_items(run_id, task_id, source_ids=sources)
    sync_task_subtask_progress(task_id, run_id)
    if log_fn:
        log_fn('[orchestrator] 入队 investigation 工作项 %d 个（源: %s）' % (
            n, ','.join(source_ids) or '-',
        ))
    if n == 0:
        return True

    entries = _spawn_workers(run_id, task_id, source_ids, log_fn=log_fn)
    if not entries:
        if log_fn:
            log_fn('[orchestrator] investigation 无可用 Worker', 'ERROR')
        return False

    def on_poll():
        sync_task_subtask_progress(task_id, run_id)
        from intel.analyze_drain import maybe_timer_drain_analyze
        maybe_timer_drain_analyze(
            task_id, run_id, task=task, partners=partners, run_metrics=run_metrics,
            log_fn=log_fn, crawl_only=crawl_only, timeout_check=timeout_check,
        )

    _register_worker_procs(run_id, entries)
    try:
        return wait_queue_barrier(
            run_id, timeout_check=timeout_check, log_fn=log_fn, on_poll=on_poll,
        )
    finally:
        _join_worker_processes(entries)
        _unregister_worker_procs(run_id, entries)
        sync_task_subtask_progress(task_id, run_id)
