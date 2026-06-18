# -*- coding: utf-8 -*-
"""监测任务编排：legacy partner×source 或 Stage2 list_first 共享池。"""
import hashlib
import time

from config import cfg
from intel.analyze import analyze_candidates
from intel.db import (
    clear_intel_for_task,
    create_analysis_job,
    create_task_run,
    fail_running_analysis_jobs,
    finish_task_run,
    get_monitor_task,
    get_partner,
    get_raw_analysis_state,
    insert_raw_records,
    list_raw_records,
    update_task_status,
)
from intel.error_util import format_exception
from intel.investigation import (
    build_investigation_queue,
    run_investigation_crawl,
    sync_investigation_run_metrics,
)
from intel.keyword_batch import build_keyword_batches, sort_batches_by_quota
from intel.matcher import export_tier_for_match, match_all_partners, match_best_partner
from intel.priority import refresh_auto_priorities
from intel.registry import registry
from intel.run_metrics import RunMetrics
from intel.triage import run_list_triage
from intel.run_state import is_monitor_busy, is_stop_requested
from intel.source_diagnose import filter_sources_after_diagnose
from intel.timeout_budget import monitor_timeout_config_from_cfg, warn_if_analysis_timeout_clamped
from intel.worker_config import workers_enabled
from intel.worker_pool import run_investigation_crawl_with_workers, run_routine_crawl_with_workers
from source_profiles import crawl_modes_for_task, task_uses_shared_pool


def _merge_worker_state_metrics(run_id, run_metrics):
    """Worker 子进程结束后，将 worker_state_json 汇总进 RunMetrics。"""
    from intel.db import get_task_run

    run = get_task_run(run_id)
    if not run:
        return
    degraded = 0
    for instance_id, inst in (run.get('worker_state') or {}).items():
        if not isinstance(inst, dict):
            continue
        source_id = inst.get('source_id') or ''
        status = inst.get('status') or ''
        diag_ok = status != 'diagnose_failed'
        run_metrics.record_worker_instance(source_id, instance_id, status, diagnose_ok=diag_ok)
        if not diag_ok:
            degraded += 1
    if degraded:
        run_metrics.set_sources_degraded(degraded)


def _dedup_key(normalized):
    ext = normalized.get('external_id') or ''
    url = normalized.get('url') or ''
    source = normalized.get('source') or ''
    if ext:
        return '%s:%s' % (source, ext)
    if url:
        return '%s:%s' % (source, hashlib.md5(url.encode('utf-8')).hexdigest()[:16])
    body = (normalized.get('title') or '') + (normalized.get('body') or '')
    return '%s:%s' % (source, hashlib.md5(body.encode('utf-8')).hexdigest()[:16])


def _get_enabled_partners(task):
    partner_ids = task.get('partner_ids') or []
    partners = [get_partner(pid) for pid in partner_ids]
    return [p for p in partners if p and p.get('enabled', True)]


def _should_analyze_raw(row, shared_pool=False):
    if not shared_pool:
        return True
    phase = row.get('crawl_phase') or 'legacy'
    if phase == 'detail':
        return True
    triage = row.get('list_triage') or {}
    rel = triage.get('triage_relevance') or ''
    if phase == 'list' and rel == 'noise':
        return False
    if phase == 'list' and not triage:
        return False
    return phase in ('legacy', 'detail')


def _build_candidates_from_raw(
    task_id,
    partners,
    analyze_mode='incremental',
    run_metrics=None,
    shared_pool=False,
):
    candidates_by_partner = {}
    raw_rows = list_raw_records(task_id)
    analysis_state = get_raw_analysis_state(task_id) if analyze_mode == 'incremental' else {}

    for row in raw_rows:
        if shared_pool and not _should_analyze_raw(row, shared_pool=True):
            continue
        if analyze_mode == 'incremental':
            st = analysis_state.get(row['id']) or {}
            if st.get('has_intel'):
                raw_upd = row.get('updated_at') or row.get('created_at') or ''
                intel_at = st.get('analyzed_at') or ''
                if raw_upd <= intel_at:
                    if run_metrics:
                        run_metrics.record_intel_skipped(1)
                    continue

        source_id = row['source']
        try:
            normalizer = registry.get_normalizer(source_id)
        except KeyError:
            continue
        payload = dict(row.get('payload') or {})
        payload['_anchor_at'] = row.get('updated_at') or row.get('created_at') or ''
        normalized = normalizer.normalize(payload)

        if shared_pool and not row.get('partner_id'):
            matches = match_all_partners(normalized, partners)
            if not matches:
                matches = [match_best_partner(normalized, partners)]
        else:
            partner = get_partner(row['partner_id']) if row['partner_id'] else partners[0]
            matches = [match_best_partner(normalized, [partner], default_partner_id=row['partner_id'])]

        replace_intel = False
        if analyze_mode == 'incremental':
            st = analysis_state.get(row['id']) or {}
            if st.get('has_intel'):
                raw_upd = row.get('updated_at') or row.get('created_at') or ''
                intel_at = st.get('analyzed_at') or ''
                if raw_upd > intel_at:
                    replace_intel = True

        for match in matches:
            if not match.get('partner_id'):
                continue
            partner = get_partner(match['partner_id']) or partners[0]
            tier = export_tier_for_match(match)
            cand = {
                'id': row['id'],
                'raw_record_id': row['id'],
                'source': normalized.get('source'),
                'url': normalized.get('url'),
                'title': normalized.get('title'),
                'body': normalized.get('body'),
                'published_at': normalized.get('published_at'),
                'captured_at': row.get('created_at') or '',
                'partner_id': match.get('partner_id'),
                'partner_name': match.get('partner_name'),
                'subject_hits': match.get('subject_hits'),
                'export_tier': tier,
                'dedup_key': _dedup_key(normalized),
                'extra': normalized.get('extra') or {},
                'replace_intel': replace_intel,
            }
            pid = match.get('partner_id') or 0
            group = candidates_by_partner.setdefault(pid, {'partner': partner, 'items': []})
            group['partner'] = partner
            group['items'].append(cand)
    return candidates_by_partner


def _timeout_message(phase, crawl_budget_sec=0, task_timeout_sec=7200):
    if phase == 'crawl':
        return '爬取阶段超时（crawl_budget_sec=%d）' % int(crawl_budget_sec)
    if phase == 'analyze':
        return '分析阶段超时（task_timeout_sec=%d）' % int(task_timeout_sec)
    return '任务超时（task_timeout_sec=%d）' % int(task_timeout_sec)


def _timeout_progress_reason(timed_out, timeout_phase):
    if not timed_out:
        return 'stopped'
    if timeout_phase == 'crawl':
        return 'crawl_timeout'
    return 'timeout'


def _fail_task(task_id, run_id, err_msg, log_fn=None, phase=''):
    update_task_status(task_id, 'failed', error_message=err_msg)
    fail_running_analysis_jobs(task_id, run_id=run_id, error_message=err_msg)
    if log_fn:
        head = err_msg.splitlines()[0] if err_msg else 'unknown'
        log_fn('监测任务失败%s: %s' % ((' (%s)' % phase if phase else ''), head), 'ERROR')
        if '\n' in err_msg:
            log_fn(err_msg, 'ERROR')


def _fail_from_exception(task_id, run_id, exc, log_fn=None, phase=''):
    err_msg = format_exception(exc)
    _fail_task(task_id, run_id, err_msg, log_fn=log_fn, phase=phase)
    return err_msg


def _run_analysis_phase(
    task_id,
    partners,
    analyze_mode='incremental',
    run_id=None,
    run_metrics=None,
    log_fn=None,
    timeout_check=None,
    shared_pool=False,
):
    if analyze_mode == 'full_replace':
        clear_intel_for_task(task_id)
        if log_fn:
            log_fn('[monitor] 全量重分析：已清除旧情报')
    candidates_by_partner = _build_candidates_from_raw(
        task_id,
        partners,
        analyze_mode=analyze_mode,
        run_metrics=run_metrics,
        shared_pool=shared_pool,
    )
    ac = cfg('analysis') or {}
    job_id = create_analysis_job(
        task_id,
        ac.get('model') or '',
        ac.get('prompt_version') or 'v1-high-recall',
        run_id=run_id,
    )
    total_written = 0
    analyze_start = time.monotonic()
    for pid, group in candidates_by_partner.items():
        partner = group['partner']
        seen_keys = set()
        items = []
        for c in group['items']:
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
        if timeout_check and timeout_check():
            break
        total_written += analyze_candidates(
            task_id,
            job_id,
            items,
            partner,
            log_fn=log_fn,
            run_metrics=run_metrics,
        )
    if run_metrics and analyze_start:
        elapsed = int((time.monotonic() - analyze_start) * 1000)
        if run_metrics.analyze_duration_ms < elapsed:
            run_metrics.analyze_duration_ms = elapsed
    return total_written


def _finish_run(run_id, run_metrics, status='done', error_message=''):
    if run_id:
        finish_task_run(run_id, status=status, error_message=error_message, metrics=run_metrics)


def _list_phase_raw_rows(task_id):
    return [r for r in list_raw_records(task_id) if (r.get('crawl_phase') or '') == 'list']


def _run_post_list_crawl_phases(
    task_id, task, partners, crawl_ctx, run_metrics, run_id, log_fn, timeout_check,
    use_workers=False, sources=None,
):
    """list_triage → investigation → 返回是否成功。"""
    update_task_status(task_id, 'analyzing', progress={'phase': 'list_triage', 'run_id': run_id})
    list_raw_rows = _list_phase_raw_rows(task_id)
    triage_result = run_list_triage(
        task_id, list_raw_rows, partners, log_fn=log_fn, run_metrics=run_metrics,
    )
    if log_fn:
        log_fn('[monitor] 列表初筛 %d 条' % triage_result.get('processed', 0))

    business_spec = task.get('business_spec') or {}
    queued = build_investigation_queue(
        task_id, partners, business_spec=business_spec, log_fn=log_fn, task=task,
    )
    run_metrics.stats['investigation_queued'] = queued

    update_task_status(
        task_id, 'crawling',
        progress={'phase': 'investigation_crawl', 'queued': queued, 'run_id': run_id},
    )
    if use_workers:
        if log_fn:
            log_fn('[monitor] Worker 池 investigation crawl（按源回派）')
        ok = run_investigation_crawl_with_workers(
            run_id, task_id, sources or task.get('sources') or [],
            log_fn=log_fn, timeout_check=timeout_check,
        )
        if not ok:
            return False
        inv_result = sync_investigation_run_metrics(task_id, run_metrics, run_id=run_id)
    else:
        inv_result = run_investigation_crawl(
            task_id, crawl_ctx, task, run_metrics=run_metrics,
            log_fn=log_fn, timeout_check=timeout_check,
        )
        from intel.modal_quota import sync_modal_quota_to_run_metrics
        sync_modal_quota_to_run_metrics(run_id, run_metrics)
    if log_fn:
        log_fn('[monitor] 勘察完成 %d / 失败 %d / 配额跳过 %d' % (
            inv_result.get('done', 0),
            inv_result.get('failed', 0),
            run_metrics.stats.get('investigation_skipped_quota', 0),
        ))
    return True


def _run_list_crawl_only(
    task_id, task, partners, sources, crawl_ctx, run_metrics, run_id, log_fn, timeout_check,
):
    from crawler_web import S

    refresh_auto_priorities()
    batches = sort_batches_by_quota(build_keyword_batches(partners))
    list_sources = [
        s for s in sources
        if crawl_modes_for_task(task).get(s) == 'list_first'
    ]
    if not list_sources:
        return True

    total_steps = len(batches) * len(list_sources)
    step = 0
    update_task_status(
        task_id, 'crawling',
        progress={'phase': 'list_crawl', 'done': 0, 'total': total_steps, 'run_id': run_id},
    )

    for batch in batches:
        for source_id in list_sources:
            if timeout_check() or not S.running:
                return False
            step += 1
            update_task_status(
                task_id, 'crawling',
                progress={
                    'phase': 'list_crawl',
                    'done': step - 1,
                    'total': total_steps,
                    'current': source_id,
                    'cohort': batch.get('cohort'),
                    'run_id': run_id,
                },
            )
            try:
                crawler = registry.get_crawler(source_id)
            except KeyError as e:
                if log_fn:
                    log_fn(str(e), 'WARN')
                continue
            if not hasattr(crawler, 'crawl_list_batch'):
                if log_fn:
                    log_fn('[monitor] %s 无 crawl_list_batch，跳过' % source_id, 'WARN')
                continue
            kw_label = ','.join((batch.get('keywords') or [])[:2])
            if log_fn:
                log_fn('[monitor] list %s / %s [%s]' % (batch.get('cohort'), source_id, kw_label))
            t0 = time.monotonic()
            raw_list = crawler.crawl_list_batch(crawl_ctx, task, batch, {
                'max_pages': task.get('max_pages'),
            })
            crawl_ms = int((time.monotonic() - t0) * 1000)
            run_metrics.add_crawl_ms(source_id, crawl_ms)
            insert_raw_records(
                task_id, None, source_id, kw_label, raw_list or [],
                run_metrics=run_metrics, crawl_phase='list',
            )
    return True


def _run_mixed_source_pipeline(
    task_id, task, partners, sources, crawl_ctx, run_metrics, run_id, log_fn, timeout_check,
):
    modes = crawl_modes_for_task(task)
    legacy_sources = [s for s in sources if modes.get(s) == 'legacy']
    list_sources = [s for s in sources if modes.get(s) == 'list_first']

    if legacy_sources:
        if not _run_legacy_crawl(
            task_id, task, partners, legacy_sources, crawl_ctx, run_metrics, run_id,
            log_fn, timeout_check,
        ):
            return False
    if list_sources:
        if not _run_list_crawl_only(
            task_id, task, partners, sources, crawl_ctx, run_metrics, run_id,
            log_fn, timeout_check,
        ):
            return False
    if list_sources:
        return _run_post_list_crawl_phases(
            task_id, task, partners, crawl_ctx, run_metrics, run_id, log_fn, timeout_check,
        )
    return True


def _run_legacy_crawl(task_id, task, partners, sources, crawl_ctx, run_metrics, run_id, log_fn, timeout_check):
    from crawler_web import S

    modes = crawl_modes_for_task(task)
    crawl_sources = [s for s in sources if modes.get(s) == 'legacy']
    if not crawl_sources:
        return True

    total_steps = len(partners) * len(crawl_sources)
    step = 0
    for partner in partners:
        for source_id in crawl_sources:
            if timeout_check():
                return False
            if not S.running:
                return False
            step += 1
            update_task_status(
                task_id,
                'crawling',
                progress={
                    'phase': 'crawl',
                    'done': step - 1,
                    'total': total_steps,
                    'current': source_id,
                    'run_id': run_id,
                },
            )
            try:
                crawler = registry.get_crawler(source_id)
            except KeyError as e:
                if log_fn:
                    log_fn(str(e), 'WARN')
                continue
            keyword = partner.get('name') or ''
            if log_fn:
                log_fn('[monitor] %s / %s' % (partner.get('name'), source_id))
            t0 = time.monotonic()
            raw_list = crawler.crawl(crawl_ctx, task, partner, {
                'max_pages': task.get('max_pages'),
                'fetch_detail': task.get('fetch_detail'),
            })
            crawl_ms = int((time.monotonic() - t0) * 1000)
            run_metrics.add_crawl_ms(source_id, crawl_ms)
            ins = insert_raw_records(
                task_id, partner['id'], source_id, keyword, raw_list or [],
                run_metrics=run_metrics, crawl_phase='legacy',
            )
            if log_fn and any(ins.get(k) for k in ('inserted', 'updated', 'unchanged')):
                parts = []
                if ins.get('inserted'):
                    parts.append('新增 %d' % ins['inserted'])
                if ins.get('updated'):
                    parts.append('更新 %d' % ins['updated'])
                if ins.get('unchanged'):
                    parts.append('未变 %d' % ins['unchanged'])
                log_fn('[monitor] raw %s' % ' · '.join(parts))
    return True


def _run_list_first_pipeline(
    task_id, task, partners, sources, crawl_ctx, run_metrics, run_id, log_fn, timeout_check,
):
    if not _run_list_crawl_only(
        task_id, task, partners, sources, crawl_ctx, run_metrics, run_id, log_fn, timeout_check,
    ):
        return False
    return _run_post_list_crawl_phases(
        task_id, task, partners, crawl_ctx, run_metrics, run_id, log_fn, timeout_check,
    )


def reanalyze_monitor_task(
    task_id,
    log_fn=None,
    replace=True,
    analyze_mode=None,
    trigger='manual',
    run_id=None,
):
    from crawler_web import S

    if analyze_mode is None:
        analyze_mode = 'full_replace' if replace else 'incremental'

    task = get_monitor_task(task_id)
    if not task:
        raise ValueError('任务不存在: %s' % task_id)
    if is_monitor_busy():
        raise RuntimeError('已有任务进行中')
    if not list_raw_records(task_id):
        raise ValueError('无原始数据，请先执行完整监测')

    partners = _get_enabled_partners(task)
    if not partners:
        update_task_status(task_id, 'failed', error_message='无有效合作方')
        return 0

    shared = task_uses_shared_pool(task)
    run_metrics = RunMetrics()
    if not run_id:
        run_id = create_task_run(task_id, trigger=trigger, analyze_mode=analyze_mode)

    S.running = True
    S.running_type = 'reanalyze'
    final_status = 'done'
    err_msg = ''
    try:
        if log_fn:
            mode_label = '全量覆盖' if analyze_mode == 'full_replace' else '增量'
            log_fn('[monitor] %s AI 分析（原始 %d 条）' % (
                mode_label, len(list_raw_records(task_id)),
            ))
        update_task_status(task_id, 'analyzing', progress={'phase': 'reanalyze', 'run_id': run_id})
        total_written = _run_analysis_phase(
            task_id,
            partners,
            analyze_mode=analyze_mode,
            run_id=run_id,
            run_metrics=run_metrics,
            log_fn=log_fn,
            shared_pool=shared,
        )
        update_task_status(
            task_id,
            'done',
            progress={'phase': 'done', 'intel_count': total_written, 'run_id': run_id},
        )
        if log_fn:
            log_fn('AI 分析完成，情报 %d 条' % total_written)
        return total_written
    except Exception as e:
        final_status = 'failed'
        err_msg = format_exception(e)
        update_task_status(task_id, 'failed', error_message=err_msg)
        fail_running_analysis_jobs(task_id, run_id=run_id, error_message=err_msg)
        if log_fn:
            log_fn('AI 分析失败: %s' % err_msg.splitlines()[0], 'ERROR')
            if '\n' in err_msg:
                log_fn(err_msg, 'ERROR')
        raise
    finally:
        _finish_run(run_id, run_metrics, status=final_status, error_message=err_msg)
        S.running = False
        S.running_type = ''


def run_monitor_task(
    task_id,
    log_fn=None,
    trigger='manual',
    analyze_mode='incremental',
    run_id=None,
    business_spec=None,
):
    from config import load_config
    from crawler_web import S, close_cdp, prepare_browser_for_crawl

    load_config(force=True)
    task = get_monitor_task(task_id)
    if not task:
        raise ValueError('任务不存在: %s' % task_id)

    if is_monitor_busy():
        raise RuntimeError('已有爬取/监测任务进行中')

    partners = _get_enabled_partners(task)
    if not partners:
        update_task_status(task_id, 'failed', error_message='无有效合作方')
        return

    if business_spec and isinstance(business_spec, dict):
        task = dict(task)
        merged = dict(task.get('business_spec') or {})
        merged.update(business_spec)
        task['business_spec'] = merged

    modes = crawl_modes_for_task(task)
    has_list_first = any(m == 'list_first' for m in modes.values())
    has_legacy = any(m == 'legacy' for m in modes.values())
    shared_pool = has_list_first

    run_metrics = RunMetrics()
    if not run_id:
        run_id = create_task_run(task_id, trigger=trigger, analyze_mode=analyze_mode)

    sources = task.get('sources') or []
    budget = monitor_timeout_config_from_cfg(cfg)
    warn_if_analysis_timeout_clamped(budget, log_fn=log_fn)
    timeout_sec = budget['task_timeout_sec']
    crawl_budget_sec = budget['crawl_budget_sec']
    analysis_reserve_sec = budget['analysis_reserve_sec']
    task_started = time.monotonic()
    task_deadline = task_started + timeout_sec
    crawl_deadline = task_started + crawl_budget_sec
    timed_out = False
    timeout_phase = ''
    final_status = 'done'
    err_msg = ''

    def should_abort():
        if is_stop_requested(run_id):
            S.running = False
            return True
        return False

    def timeout_check(phase='crawl'):
        nonlocal timed_out, err_msg, timeout_phase
        if should_abort():
            if not err_msg:
                err_msg = '任务已停止'
            return True
        dl = crawl_deadline if phase == 'crawl' else task_deadline
        if time.monotonic() < dl:
            return False
        S.running = False
        timed_out = True
        timeout_phase = phase
        if phase == 'crawl':
            err_msg = _timeout_message('crawl', crawl_budget_sec=crawl_budget_sec)
            if log_fn:
                log_fn('[monitor] %s' % err_msg, 'WARN')
        else:
            err_msg = _timeout_message('analyze', task_timeout_sec=timeout_sec)
            if log_fn:
                log_fn('[monitor] %s' % err_msg, 'WARN')
        return True

    crawl_ctx = {
        'log': log_fn,
        'monitor_active': True,
        'timeout_check': lambda: timeout_check('crawl'),
        'run_id': run_id,
    }

    S.running = True
    S.running_type = 'monitor'
    update_task_status(
        task_id,
        'crawling',
        progress={'phase': 'list_crawl' if shared_pool else 'crawl', 'done': 0, 'total': 0, 'run_id': run_id},
    )

    try:
        use_workers = workers_enabled()
        ok = False
        if use_workers:
            if log_fn:
                log_fn('[monitor] Worker 池 routine crawl（heimao ∥ xhs）')
            ok = run_routine_crawl_with_workers(
                run_id, task_id, task, partners, sources, log_fn=log_fn,
                timeout_check=lambda: timeout_check('crawl'),
            )
            _merge_worker_state_metrics(run_id, run_metrics)
            if ok and has_list_first:
                ok = _run_post_list_crawl_phases(
                    task_id, task, partners, crawl_ctx, run_metrics, run_id, log_fn, timeout_check,
                    use_workers=True, sources=sources,
                )
                _merge_worker_state_metrics(run_id, run_metrics)
        else:
            if len(sources) > 1 and log_fn:
                log_fn(
                    '[monitor] 单进程模式：多数据源将顺序执行（黑猫 legacy 完成后才跑小红书）。'
                    ' 并行请启用 monitor.workers.enabled 并保存配置',
                    'WARN',
                )
            if not prepare_browser_for_crawl():
                final_status = 'failed'
                err_msg = 'Chrome 未就绪'
                update_task_status(task_id, 'failed', error_message=err_msg)
                return
            sources = filter_sources_after_diagnose(sources, run_metrics, log_fn=log_fn)
            if not sources:
                final_status = 'failed'
                err_msg = '全部数据源 Cookie 诊断失败'
                update_task_status(task_id, 'failed', error_message=err_msg)
                return
            if has_list_first and has_legacy:
                ok = _run_mixed_source_pipeline(
                    task_id, task, partners, sources, crawl_ctx, run_metrics, run_id, log_fn, timeout_check,
                )
            elif has_list_first:
                ok = _run_list_first_pipeline(
                    task_id, task, partners, sources, crawl_ctx, run_metrics, run_id, log_fn, timeout_check,
                )
            else:
                ok = _run_legacy_crawl(
                    task_id, task, partners, sources, crawl_ctx, run_metrics, run_id, log_fn, timeout_check,
                )

        if not ok:
            final_status = 'failed'
            if not err_msg:
                err_msg = '任务超时' if timed_out else '任务已停止'
            update_task_status(
                task_id, 'failed', error_message=err_msg,
                progress={
                    'reason': _timeout_progress_reason(timed_out, timeout_phase),
                    'phase': 'crawl',
                },
            )
            return

        remaining = max(0, task_deadline - time.monotonic())
        analysis_budget = min(analysis_reserve_sec, remaining)
        if remaining >= 300:
            analysis_budget = max(300, analysis_budget)
        else:
            analysis_budget = max(60, min(analysis_budget, remaining))
        timed_out = False
        timeout_phase = ''
        err_msg = ''
        S.running = True
        if log_fn and time.monotonic() - task_started >= timeout_sec - 120:
            log_fn('[monitor] 爬取完成，预留 %ds 用于 AI 分析' % analysis_budget, 'INFO')

        update_task_status(task_id, 'analyzing', progress={'phase': 'analyze', 'run_id': run_id})
        total_written = _run_analysis_phase(
            task_id,
            partners,
            analyze_mode=analyze_mode,
            run_id=run_id,
            run_metrics=run_metrics,
            log_fn=log_fn,
            timeout_check=lambda: timeout_check('analyze'),
            shared_pool=shared_pool,
        )
        if timed_out:
            final_status = 'failed'
            if not err_msg:
                err_msg = _timeout_message('analyze', task_timeout_sec=timeout_sec)
            update_task_status(
                task_id, 'failed', error_message=err_msg,
                progress={
                    'reason': _timeout_progress_reason(timed_out, timeout_phase),
                    'phase': 'analyze',
                },
            )
            return

        update_task_status(
            task_id,
            'done',
            progress={'phase': 'done', 'intel_count': total_written, 'run_id': run_id},
        )
        if log_fn:
            log_fn('监测任务完成，情报 %d 条' % total_written)
    except Exception as e:
        final_status = 'failed'
        err_msg = _fail_from_exception(task_id, run_id, e, log_fn=log_fn)
    finally:
        _finish_run(run_id, run_metrics, status=final_status, error_message=err_msg)
        S.running = False
        S.running_type = ''
        close_cdp()
