# -*- coding: utf-8 -*-
"""Run 内 investigation 与 AI analyze 重叠：批完成 + 定时 drain。"""
import threading
import time

from config import cfg

from intel.db import (
    _utc_now,
    count_detail_pending_analyze,
    create_analysis_job,
    get_monitor_task,
    update_task_status,
)
from intel.run_metrics import RunMetrics

_run_analyze_locks = {}
_last_drain_at = {}
_lock_registry = threading.Lock()


def _get_run_lock(run_id):
    with _lock_registry:
        if run_id not in _run_analyze_locks:
            _run_analyze_locks[run_id] = threading.Lock()
        return _run_analyze_locks[run_id]


def analyze_during_crawl_enabled():
    return bool(cfg('monitor', 'analyze_during_crawl', default=True))


def analyze_drain_interval_sec():
    return max(5, int(cfg('monitor', 'analyze_drain_interval_sec', default=60) or 60))


def _resolve_crawl_only(task, crawl_only=None):
    if crawl_only is not None:
        return bool(crawl_only)
    return bool((task or {}).get('crawl_only'))


def should_drain_analyze(task, crawl_only=None, trigger='batch'):
    """自动 drain 尊重 crawl_only；手动 incremental 不受 crawl_only 限制。"""
    if trigger == 'manual':
        return True
    if _resolve_crawl_only(task, crawl_only):
        return False
    return analyze_during_crawl_enabled()


def _load_partners(task):
    from intel.runner import _get_enabled_partners

    return _get_enabled_partners(task)


def _shared_pool(task):
    from source_profiles import task_uses_shared_pool

    return task_uses_shared_pool(task)


def _update_analyze_drain_progress(task_id, run_id, trigger, drained_count, run_metrics=None):
    task = get_monitor_task(task_id) or {}
    status = task.get('status') or 'crawling'
    progress = dict(task.get('progress') or {})
    analyze_drain = dict(progress.get('analyze_drain') or {})
    if drained_count:
        analyze_drain['done'] = int(analyze_drain.get('done') or 0) + int(drained_count)
    analyze_drain['pending_detail'] = count_detail_pending_analyze(task_id)
    analyze_drain['last_trigger'] = trigger
    analyze_drain['last_at'] = _utc_now()
    progress['analyze_drain'] = analyze_drain
    progress['run_id'] = run_id
    update_task_status(task_id, status, progress=progress)
    if run_metrics:
        run_metrics.stats['analyze_drained_count'] = (
            int(run_metrics.stats.get('analyze_drained_count') or 0) + int(drained_count or 0)
        )
        if trigger == 'timer':
            run_metrics.stats['analyze_drain_timer_runs'] = (
                int(run_metrics.stats.get('analyze_drain_timer_runs') or 0) + 1
            )


def drain_analyze_ready(
    task_id,
    run_id,
    task,
    partners=None,
    *,
    trigger='batch',
    run_metrics=None,
    log_fn=None,
    timeout_check=None,
    crawl_only=None,
):
    """对 detail-ready raw 做 incremental analyze drain。"""
    if not task_id or not run_id:
        return 0
    task = task or get_monitor_task(task_id)
    if not task or not should_drain_analyze(task, crawl_only=crawl_only, trigger=trigger):
        return 0
    if not partners:
        partners = _load_partners(task)
    if not partners:
        return 0

    from intel.runner import _build_candidates_from_raw

    shared = _shared_pool(task)
    candidates_by_partner = _build_candidates_from_raw(
        task_id,
        partners,
        analyze_mode='incremental',
        run_metrics=run_metrics,
        shared_pool=shared,
        detail_only=True,
        task=task,
    )
    total_items = sum(len(g.get('items') or []) for g in candidates_by_partner.values())
    if total_items <= 0:
        _update_analyze_drain_progress(task_id, run_id, trigger, 0, run_metrics=run_metrics)
        return 0

    lock = _get_run_lock(run_id)
    if not lock.acquire(blocking=False):
        if log_fn:
            log_fn('[analyze_drain] 跳过（同 Run 分析进行中）trigger=%s' % trigger, 'INFO')
        return 0

    drained = 0
    drain_start = time.monotonic()
    try:
        from intel.analyze import analyze_candidates
        from intel.runner import _dedup_key

        ac = cfg('analysis') or {}
        batch_size = max(1, int(ac.get('batch_size') or 15))
        max_batches = cfg('monitor', 'analyze_drain_max_batches_per_tick', default=None)
        max_items = None
        if max_batches is not None:
            max_items = max(1, int(max_batches)) * batch_size

        job_id = create_analysis_job(
            task_id,
            ac.get('model') or '',
            ac.get('prompt_version') or 'v1-high-recall',
            run_id=run_id,
        )
        if log_fn:
            log_fn(
                '[analyze_drain] %s · 候选 %d 条（detail-only）' % (trigger, total_items),
                'INFO',
            )

        items_left = max_items
        for _pid, group in candidates_by_partner.items():
            partner = group['partner']
            seen_keys = set()
            items = []
            for c in group.get('items') or []:
                if c.get('export_tier') == 'exclude':
                    continue
                dk = c.get('dedup_key') or ''
                if dk and dk in seen_keys:
                    continue
                if dk:
                    seen_keys.add(dk)
                items.append(c)
            if not items:
                continue
            if items_left is not None and len(items) > items_left:
                items = items[:items_left]
            if timeout_check and timeout_check():
                break
            drained += analyze_candidates(
                task_id,
                job_id,
                items,
                partner,
                log_fn=log_fn,
                run_metrics=run_metrics,
                during_crawl=True,
            )
            if items_left is not None:
                items_left = max(0, items_left - len(items))
                if items_left <= 0:
                    break

        elapsed_ms = int((time.monotonic() - drain_start) * 1000)
        if run_metrics:
            run_metrics.stats['analyze_during_crawl_ms'] = (
                int(run_metrics.stats.get('analyze_during_crawl_ms') or 0) + elapsed_ms
            )
            run_metrics.analyze_duration_ms += elapsed_ms
        _update_analyze_drain_progress(task_id, run_id, trigger, drained, run_metrics=run_metrics)
        if log_fn and drained:
            log_fn('[analyze_drain] %s 完成 · 写入 %d 条' % (trigger, drained), 'INFO')
        return drained
    except Exception as e:
        if log_fn:
            log_fn('[analyze_drain] %s 失败: %s' % (trigger, str(e)[:200]), 'ERROR')
        return drained
    finally:
        lock.release()


def maybe_batch_drain_analyze(
    task_id,
    run_id,
    task=None,
    partners=None,
    run_metrics=None,
    log_fn=None,
    crawl_only=None,
    timeout_check=None,
):
    if not run_id:
        return 0
    task = task or get_monitor_task(task_id)
    if not should_drain_analyze(task, crawl_only=crawl_only, trigger='batch'):
        return 0
    _last_drain_at[run_id] = time.monotonic()
    return drain_analyze_ready(
        task_id,
        run_id,
        task,
        partners=partners,
        trigger='batch',
        run_metrics=run_metrics,
        log_fn=log_fn,
        timeout_check=timeout_check,
        crawl_only=crawl_only,
    )


def maybe_timer_drain_analyze(
    task_id,
    run_id,
    task=None,
    partners=None,
    run_metrics=None,
    log_fn=None,
    crawl_only=None,
    timeout_check=None,
):
    if not run_id:
        return 0
    task = task or get_monitor_task(task_id)
    if not should_drain_analyze(task, crawl_only=crawl_only, trigger='batch'):
        return 0
    interval = analyze_drain_interval_sec()
    now = time.monotonic()
    last = _last_drain_at.get(run_id, 0.0)
    if now - last < interval:
        return 0
    _last_drain_at[run_id] = now
    return drain_analyze_ready(
        task_id,
        run_id,
        task,
        partners=partners,
        trigger='timer',
        run_metrics=run_metrics,
        log_fn=log_fn,
        timeout_check=timeout_check,
        crawl_only=crawl_only,
    )
