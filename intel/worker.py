# -*- coding: utf-8 -*-
"""Crawl Worker 子进程：认领 queue 并执行 adapter。"""
import multiprocessing
import time

from config import load_config
from intel.crawl_queue import (
    claim_next,
    mark_done,
    mark_failed,
    run_queue_counts,
    touch_heartbeat,
)
from intel.db import (
    append_run_log,
    get_monitor_task,
    get_partner,
    insert_raw_records,
    update_run_worker_state,
)
from intel.investigation import process_investigation_batch
from intel.registry import register_default_sources, registry
from intel.run_state import is_stop_requested


def _worker_log(run_id, instance_id, msg, level='INFO'):
    append_run_log(run_id, msg, level=level, worker_instance_id=instance_id)


def _execute_work_item(item, task, instance, crawl_ctx, run_metrics):
    source_id = item['source_id']
    phase = item['phase']
    payload = item['payload'] or {}
    task_id = item['task_id']
    crawler = registry.get_crawler(source_id)
    t0 = time.monotonic()

    if phase == 'legacy_crawl':
        partner = get_partner(payload.get('partner_id'))
        if not partner:
            raise ValueError('合作方不存在: %s' % payload.get('partner_id'))
        keyword = payload.get('keyword') or partner.get('name') or ''
        raw_list = crawler.crawl(crawl_ctx, task, partner, {
            'max_pages': task.get('max_pages'),
            'fetch_detail': task.get('fetch_detail'),
        })
        crawl_ms = int((time.monotonic() - t0) * 1000)
        if run_metrics:
            run_metrics.add_crawl_ms(source_id, crawl_ms)
        insert_raw_records(
            task_id, partner['id'], source_id, keyword, raw_list or [],
            run_metrics=run_metrics, crawl_phase='legacy',
        )
        return

    if phase == 'list_crawl':
        batch = payload.get('keyword_batch') or {}
        kw_label = ','.join((batch.get('keywords') or [])[:2])
        raw_list = crawler.crawl_list_batch(crawl_ctx, task, batch, {
            'max_pages': task.get('max_pages'),
        })
        crawl_ms = int((time.monotonic() - t0) * 1000)
        if run_metrics:
            run_metrics.add_crawl_ms(source_id, crawl_ms)
        insert_raw_records(
            task_id, None, source_id, kw_label, raw_list or [],
            run_metrics=run_metrics, crawl_phase='list',
        )
        return

    if phase == 'investigation':
        batch_items = payload.get('items') or []
        process_investigation_batch(
            source_id, batch_items, task, crawl_ctx, run_metrics=run_metrics,
        )
        return

    raise ValueError('Worker 未支持的 phase: %s' % phase)


def run_worker_loop(run_id, task_id, source_id, instance_cfg):
    """Worker 主循环（在子进程中运行）。"""
    load_config(force=True)
    register_default_sources()
    from crawler_web import S, close_cdp
    from intel.worker_runtime import WorkerSession, WorkerRuntime

    instance_id = instance_cfg.get('instance_id') or ('%s-0' % source_id)

    def log_fn(msg, level='INFO'):
        _worker_log(run_id, instance_id, msg, level=level)

    worker_rt = WorkerRuntime(run_id, instance_id, source_id, log_fn)
    worker_rt.attach_to_global_s()
    task = get_monitor_task(task_id)
    if not task:
        _worker_log(run_id, instance_id, '任务不存在', 'ERROR')
        return

    S.running = True
    S.running_type = 'worker:%s' % source_id

    def timeout_check():
        return is_stop_requested(run_id)

    crawl_ctx = {
        'log': log_fn,
        'monitor_active': True,
        'timeout_check': timeout_check,
        'worker_instance_id': instance_id,
        'run_id': run_id,
    }

    from intel.run_metrics import RunMetrics
    run_metrics = RunMetrics()

    update_run_worker_state(run_id, {
        instance_id: {'source_id': source_id, 'status': 'starting'},
    })

    try:
        with WorkerSession(instance_cfg, log_fn=log_fn) as session:
            from auth_utils import apply_cookies_from_file, diagnose_login, load_cookies_from_file

            ctx = session.ctx
            cookies_file = instance_cfg.get('cookies_file') or ''
            if cookies_file:
                apply_cookies_from_file(ctx, source_id, cookies_file, log_fn=log_fn)
            else:
                from auth_utils import apply_cookies_to_context
                apply_cookies_to_context(ctx, source_id, log_fn=log_fn)

            diag = diagnose_login(ctx, source_id)
            diag_ok = True
            if source_id == 'heimao':
                diag_ok = bool(diag.get('has_sub_in_browser') or diag.get('has_sub_in_config'))
            elif source_id == 'xhs':
                diag_ok = bool(diag.get('has_xhs_in_browser') or diag.get('has_xhs_in_config'))
            if not diag_ok:
                update_run_worker_state(run_id, {
                    instance_id: {'source_id': source_id, 'status': 'diagnose_failed', 'diag': diag},
                })
                _worker_log(run_id, instance_id, 'Cookie 诊断失败，Worker 退出', 'ERROR')
                return

            update_run_worker_state(run_id, {
                instance_id: {'source_id': source_id, 'status': 'running', 'cdp_port': instance_cfg.get('cdp_port')},
            })
            worker_rt._worker_status = 'running'
            worker_rt.attach_to_global_s()
            log_fn('[worker:%s] 就绪 port=%s' % (instance_id, instance_cfg.get('cdp_port')))

            idle_rounds = 0
            while not timeout_check():
                item = claim_next(run_id, source_id, instance_id)
                if not item:
                    counts = run_queue_counts(run_id)
                    pending = counts.get('pending', 0)
                    if pending == 0:
                        idle_rounds += 1
                        if idle_rounds >= 3:
                            break
                    else:
                        idle_rounds = 0
                    time.sleep(1)
                    continue
                idle_rounds = 0
                try:
                    touch_heartbeat(item['id'])
                    log_fn('[worker:%s] 执行 %s #%d' % (instance_id, item['phase'], item['id']))
                    _execute_work_item(item, task, instance_cfg, crawl_ctx, run_metrics)
                    mark_done(item['id'])
                except Exception as e:
                    mark_failed(item['id'], str(e))
                    log_fn('[worker:%s] 失败: %s' % (instance_id, str(e)[:200]), 'ERROR')
                if timeout_check():
                    break

            update_run_worker_state(run_id, {
                instance_id: {'source_id': source_id, 'status': 'done'},
            })
    finally:
        S.running = False
        close_cdp(shutdown_browser=False, force=True)


def worker_process_entry(run_id, task_id, source_id, instance_cfg):
    try:
        run_worker_loop(run_id, task_id, source_id, instance_cfg)
    except Exception as e:
        append_run_log(
            run_id, 'Worker 崩溃: %s' % str(e)[:300], level='ERROR',
            worker_instance_id=instance_cfg.get('instance_id') or source_id,
        )


def spawn_worker_process(run_id, task_id, source_id, instance_cfg):
    p = multiprocessing.Process(
        target=worker_process_entry,
        args=(run_id, task_id, source_id, instance_cfg),
        daemon=True,
        name='crawl-worker-%s-%s' % (source_id, instance_cfg.get('instance_id')),
    )
    p.start()
    return p
