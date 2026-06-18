# -*- coding: utf-8 -*-
"""Orchestrator：spawn Worker 并等待 queue barrier。"""
import time

from intel.crawl_queue import (
    clear_run_queue,
    enqueue_investigation_work_items,
    enqueue_routine_for_task,
    wait_queue_barrier,
)
from intel.worker import spawn_worker_process
from intel.worker_config import instances_for_sources


def _join_worker_processes(procs, join_sec=15):
    deadline = time.monotonic() + join_sec
    for p in procs:
        p.join(timeout=max(0, deadline - time.monotonic()))
    for p in procs:
        if p.is_alive():
            p.terminate()
            p.join(timeout=3)


def _spawn_workers(run_id, task_id, source_ids, log_fn=None):
    instances = instances_for_sources(source_ids)
    procs = []
    for inst in instances:
        sid = inst.get('source_id')
        if sid not in source_ids:
            continue
        p = spawn_worker_process(run_id, task_id, sid, inst)
        procs.append(p)
        if log_fn:
            log_fn('[orchestrator] 启动 Worker %s port=%s' % (
                inst.get('instance_id'), inst.get('cdp_port'),
            ))
    return procs


def run_routine_crawl_with_workers(
    run_id,
    task_id,
    task,
    partners,
    sources,
    log_fn=None,
    timeout_check=None,
):
    clear_run_queue(run_id)
    n = enqueue_routine_for_task(run_id, task_id, task, partners, sources)
    if log_fn:
        log_fn('[orchestrator] 入队 routine 工作项 %d 个' % n)

    if n == 0:
        return True

    procs = _spawn_workers(run_id, task_id, sources, log_fn=log_fn)
    if not procs:
        if log_fn:
            log_fn('[orchestrator] 无 Worker 实例配置', 'ERROR')
        return False

    try:
        return wait_queue_barrier(run_id, timeout_check=timeout_check, log_fn=log_fn)
    finally:
        _join_worker_processes(procs)


def run_investigation_crawl_with_workers(
    run_id,
    task_id,
    sources,
    log_fn=None,
    timeout_check=None,
):
    n, source_ids = enqueue_investigation_work_items(run_id, task_id)
    if log_fn:
        log_fn('[orchestrator] 入队 investigation 工作项 %d 个（源: %s）' % (
            n, ','.join(source_ids) or '-',
        ))
    if n == 0:
        return True

    procs = _spawn_workers(run_id, task_id, source_ids, log_fn=log_fn)
    if not procs:
        if log_fn:
            log_fn('[orchestrator] investigation 无可用 Worker', 'ERROR')
        return False

    try:
        return wait_queue_barrier(run_id, timeout_check=timeout_check, log_fn=log_fn)
    finally:
        _join_worker_processes(procs)
