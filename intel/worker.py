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
from intel.run_state import is_halt_requested, is_stop_requested


def _worker_log(run_id, instance_id, msg, level='INFO'):
    append_run_log(run_id, msg, level=level, worker_instance_id=instance_id)


def _task_partners(task):
    partner_ids = task.get('partner_ids') or []
    partners = [get_partner(pid) for pid in partner_ids]
    return [p for p in partners if p and p.get('enabled', True)]


def _execute_xhs_keyword_pipeline_item(item, task, partners, crawl_ctx, run_metrics, payload, worker_session=None):
    from intel.db import create_keyword_run, sync_task_subtask_progress, update_keyword_run
    from intel.keyword_pipeline import run_xhs_keyword_pipeline
    from intel.source_timeout import resolve_source_timeout_sec

    keyword = payload.get('keyword') or ''
    cohort = payload.get('cohort') or ''
    keyword_run_id = payload.get('keyword_run_id')
    run_id = item['run_id']
    task_id = item['task_id']
    timeout_sec = int(payload.get('timeout_sec') or 0) or None
    if not timeout_sec:
        timeout_sec = resolve_source_timeout_sec('xhs', partners, keyword=keyword)
    if not keyword_run_id:
        keyword_run_id = create_keyword_run(
            run_id, task_id, 'xhs', keyword, cohort, timeout_sec=timeout_sec,
        )
        sync_task_subtask_progress(task_id, run_id)
    log_fn = (crawl_ctx or {}).get('log')

    account = None
    if worker_session is not None:
        from intel.xhs_credentials import try_pick_and_bind_xhs
        instance_cfg = (crawl_ctx or {}).get('worker_instance_cfg') or {}
        account = try_pick_and_bind_xhs(worker_session, instance_cfg, log_fn=log_fn)
        if not account:
            err = '无可用 xhs 账号（全部诊断失败或未配置）'
            from intel.keyword_pipeline import now_iso
            update_keyword_run(
                keyword_run_id,
                status='failed',
                phase='pending',
                error_message=err,
                finished_at=now_iso(),
            )
            sync_task_subtask_progress(task_id, run_id)
            if log_fn:
                log_fn('[worker:xhs] keyword 失败 %s: %s' % (keyword[:40], err), 'ERROR')
            return

    if account and keyword_run_id:
        from intel.db import get_keyword_run
        kr = get_keyword_run(keyword_run_id) or {}
        stats = dict(kr.get('stats') or {})
        stats['account_id'] = account.get('id')
        stats['account_label'] = account.get('label') or ''
        update_keyword_run(keyword_run_id, stats_json=stats)

    if log_fn:
        who = (' · ' + account.get('label')) if account else ''
        log_fn('[worker:xhs] keyword 流水线 [%s] %s%s' % (cohort or '-', keyword[:40], who))
    run_xhs_keyword_pipeline(
        crawl_ctx, task, partners, keyword, cohort=cohort,
        keyword_run_id=keyword_run_id, run_metrics=run_metrics,
        timeout_sec=timeout_sec,
    )


def _execute_xhs_list_batch_as_pipeline(item, task, crawl_ctx, run_metrics, worker_session=None):
    """兼容旧 list_crawl 入队：按 keyword 逐条走 list→triage→同页勘察。"""
    payload = item['payload'] or {}
    batch = payload.get('keyword_batch') or {}
    cohort = payload.get('cohort') or batch.get('cohort') or ''
    partners = _task_partners(task)
    log_fn = (crawl_ctx or {}).get('log')
    keywords = batch.get('keywords') or []
    if log_fn and keywords:
        log_fn('[worker:xhs] 旧 list_crawl 批次转 keyword 流水线（%d 个关键词）' % len(keywords))
    for kw in keywords:
        if not kw:
            continue
        tc = (crawl_ctx or {}).get('timeout_check')
        if tc and tc():
            break
        _execute_xhs_keyword_pipeline_item(
            item, task, partners, crawl_ctx, run_metrics,
            {'keyword': kw, 'cohort': cohort},
            worker_session=worker_session,
        )


def _execute_work_item(item, task, instance, crawl_ctx, run_metrics, worker_session=None):
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
        from intel.source_timeout import resolve_source_timeout_sec
        import time as _time
        partner_timeout = resolve_source_timeout_sec(
            source_id, [], partner=partner,
        )
        started = _time.monotonic()
        base_tc = crawl_ctx.get('timeout_check')
        local_ctx = dict(crawl_ctx)

        def _partner_timeout_check():
            if base_tc and base_tc():
                return True
            return _time.monotonic() - started >= partner_timeout

        local_ctx['timeout_check'] = _partner_timeout_check
        raw_list = crawler.crawl(local_ctx, task, partner, {
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

    if phase == 'keyword_pipeline':
        partners = _task_partners(task)
        _execute_xhs_keyword_pipeline_item(
            item, task, partners, crawl_ctx, run_metrics, payload,
            worker_session=worker_session,
        )
        return

    if phase == 'list_crawl':
        if source_id == 'xhs':
            _execute_xhs_list_batch_as_pipeline(
                item, task, crawl_ctx, run_metrics, worker_session=worker_session,
            )
            return
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
    import os

    load_config(force=True)
    register_default_sources()
    from crawler_web import S, close_cdp
    from intel.worker_runtime import WorkerSession, WorkerRuntime

    instance_id = instance_cfg.get('instance_id') or ('%s-0' % source_id)

    def log_fn(msg, level='INFO'):
        _worker_log(run_id, instance_id, msg, level=level)

    worker_rt = WorkerRuntime(run_id, instance_id, source_id, log_fn, instance_cfg=instance_cfg)
    worker_rt.attach_to_global_s()
    task = get_monitor_task(task_id)
    if not task:
        _worker_log(run_id, instance_id, '任务不存在', 'ERROR')
        return

    S.running = True
    S.running_type = 'worker:%s' % source_id

    def timeout_check():
        return is_halt_requested(run_id, source_id)

    from intel.run_metrics import RunMetrics
    run_metrics = RunMetrics()

    crawl_ctx = {
        'log': log_fn,
        'monitor_active': True,
        'timeout_check': timeout_check,
        'worker_instance_id': instance_id,
        'run_id': run_id,
        'run_metrics': run_metrics,
        'source_id': source_id,
        'worker_instance_cfg': instance_cfg,
    }

    update_run_worker_state(run_id, {
        instance_id: {'source_id': source_id, 'status': 'starting', 'pid': os.getpid()},
    })

    try:
        with WorkerSession(instance_cfg, log_fn=log_fn) as session:
            from auth_utils import apply_cookies_from_file, diagnose_login

            if source_id == 'xhs':
                from intel.xhs_credentials import eligible_accounts, load_accounts
                if not eligible_accounts(load_accounts()):
                    from intel.crawl_queue import skip_pending_queue_for_source
                    skip_pending_queue_for_source(run_id, 'xhs', '无可用 xhs 账号')
                    update_run_worker_state(run_id, {
                        instance_id: {'source_id': source_id, 'status': 'diagnose_failed', 'diag': {}},
                    })
                    _worker_log(run_id, instance_id, 'xhs 账号池无可用账号', 'ERROR')
                    return
            else:
                ctx = session.ctx
                from auth_utils import ensure_site_page
                cookies_file = instance_cfg.get('cookies_file') or ''
                if cookies_file:
                    apply_cookies_from_file(ctx, source_id, cookies_file, log_fn=log_fn)
                else:
                    from auth_utils import apply_cookies_to_context
                    apply_cookies_to_context(ctx, source_id, log_fn=log_fn)
                ensure_site_page(ctx, source_id, log_fn=log_fn)

                diag = diagnose_login(ctx, source_id)
                diag_ok = bool(diag.get('has_sub_in_browser') or diag.get('has_sub_in_config'))
                if not diag_ok:
                    from intel.crawl_queue import skip_pending_queue_for_source
                    skip_pending_queue_for_source(run_id, source_id, 'Cookie 诊断失败')
                    update_run_worker_state(run_id, {
                        instance_id: {'source_id': source_id, 'status': 'diagnose_failed', 'diag': diag},
                    })
                    _worker_log(run_id, instance_id, 'Cookie 诊断失败，Worker 退出', 'ERROR')
                    return

            update_run_worker_state(run_id, {
                instance_id: {
                    'source_id': source_id,
                    'status': 'running',
                    'cdp_port': instance_cfg.get('cdp_port'),
                    'pid': os.getpid(),
                },
            })
            worker_rt._worker_status = 'running'
            worker_rt.attach_to_global_s()
            log_fn('[worker:%s] 就绪 port=%s' % (instance_id, instance_cfg.get('cdp_port')))

            idle_rounds = 0
            while not timeout_check():
                item = claim_next(run_id, source_id, instance_id)
                if not item:
                    from intel.crawl_queue import run_queue_counts_by_source
                    src_counts = run_queue_counts_by_source(run_id).get(source_id) or {}
                    src_open = src_counts.get('pending', 0) + src_counts.get('claimed', 0)
                    if src_open == 0:
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
                    t0 = time.monotonic()
                    _execute_work_item(
                        item, task, instance_cfg, crawl_ctx, run_metrics,
                        worker_session=session,
                    )
                    crawl_ms = max(0, int((time.monotonic() - t0) * 1000))
                    phase_timing = {
                        'list_crawl_ms': 0,
                        'analyze_ms': 0,
                        'investigation_ms': 0,
                    }
                    phase = item.get('phase') or ''
                    if phase in ('legacy_crawl', 'list_crawl', 'keyword_pipeline'):
                        phase_timing['list_crawl_ms'] = crawl_ms
                    elif phase == 'investigation':
                        phase_timing['investigation_ms'] = crawl_ms
                    mark_done(item['id'], phase_timing_ms=phase_timing)
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
        try:
            from intel.crawl_queue import run_queue_counts_by_source, skip_pending_queue_for_source
            qc = run_queue_counts_by_source(run_id).get(source_id) or {}
            if qc.get('pending') or qc.get('claimed'):
                skip_pending_queue_for_source(run_id, source_id, 'Worker 已退出')
        except Exception:
            pass


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
    try:
        from intel.worker_pool import register_worker_proc
        register_worker_proc(run_id, source_id, p)
    except Exception:
        pass
    return p
