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
    get_task_run,
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
from intel.run_state import (
    HALT_TASK_STATUSES,
    is_halt_requested,
    is_monitor_busy,
    is_pause_requested,
    is_stop_requested,
    is_task_halted,
    resolve_run_halt_after_crawl,
)
from intel.source_diagnose import filter_sources_after_diagnose
from intel.timeout_budget import monitor_timeout_config_from_cfg, warn_if_analysis_timeout_clamped
from intel.worker_config import workers_enabled
from intel.worker_pool import (
    run_investigation_crawl_with_workers,
    run_resume_crawl_with_workers,
    run_routine_crawl_with_workers,
)
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


def _should_skip_ignore_before(published_at, ignore_before):
    cutoff = (ignore_before or '').strip()
    if not cutoff:
        return False
    pub = (published_at or '').strip()
    if not pub:
        return False
    pub_day = pub[:10]
    cutoff_day = cutoff[:10]
    if len(pub_day) < 10 or len(cutoff_day) < 10:
        return False
    return pub_day < cutoff_day


def _build_candidates_from_raw(
    task_id,
    partners,
    analyze_mode='incremental',
    run_metrics=None,
    shared_pool=False,
    ignore_before=None,
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

        if _should_skip_ignore_before(normalized.get('published_at'), ignore_before):
            if run_metrics:
                run_metrics.record_intel_skipped_ignore_before(1)
            continue

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


def _apply_failure_halt(task_id, run_id, run_metrics, err_msg, progress_phase='crawl', reason='failed'):
    """超时/失败：保留子任务用时、回退 running keyword，并标记可继续。"""
    from intel.db import (
        reset_interrupted_keyword_runs,
        sync_task_subtask_progress,
    )

    reset_interrupted_keyword_runs(run_id)
    sync_task_subtask_progress(task_id, run_id)
    update_task_status(
        task_id,
        'failed',
        error_message=err_msg,
        progress={
            'phase': progress_phase,
            'reason': reason,
            'run_id': run_id,
            'resume_run_id': run_id,
        },
    )
    _finish_run(run_id, run_metrics, status='failed', error_message=err_msg)


def _apply_user_halt(task_id, run_id, halt_kind, run_metrics, progress_phase='crawl'):
    from intel.db import (
        clear_run_halt_flags,
        reset_interrupted_keyword_runs,
        sync_task_subtask_progress,
    )

    msg = '任务已暂停' if halt_kind == 'paused' else '用户终止'
    reset_interrupted_keyword_runs(run_id)
    sync_task_subtask_progress(task_id, run_id)
    update_task_status(
        task_id,
        halt_kind,
        error_message=msg,
        progress={
            'phase': progress_phase,
            'halt': halt_kind,
            'run_id': run_id,
            'resume_run_id': run_id,
        },
    )
    _finish_run(run_id, run_metrics, status=halt_kind, error_message=msg)
    clear_run_halt_flags(run_id)


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


def _ensure_monitor_task_settled(task_id, run_id, run_metrics, final_status, err_msg, halt_handled):
    """分析/爬取异常退出时，避免任务或 Run 长期卡在 running/analyzing。"""
    if halt_handled or not run_id:
        return
    from intel.db import get_monitor_task, get_task_run

    task = get_monitor_task(task_id) or {}
    run = get_task_run(run_id) or {}
    status = final_status or 'failed'
    msg = err_msg or ''
    if task.get('status') in ('crawling', 'analyzing'):
        update_task_status(
            task_id,
            'failed' if status != 'done' or msg else 'done',
            error_message=msg,
            progress={'phase': 'done' if status == 'done' and not msg else status, 'run_id': run_id},
        )
    if run.get('status') == 'running':
        _finish_run(run_id, run_metrics, status=status, error_message=msg)


def _run_analysis_phase(
    task_id,
    partners,
    analyze_mode='incremental',
    run_id=None,
    run_metrics=None,
    log_fn=None,
    timeout_check=None,
    shared_pool=False,
    task=None,
):
    ignore_before = None
    if task and isinstance(task.get('business_spec'), dict):
        ignore_before = task['business_spec'].get('ignore_before')
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
        ignore_before=ignore_before,
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
        from intel.db import merge_run_metrics_from_subtasks

        merge_run_metrics_from_subtasks(run_id, run_metrics)
        finish_task_run(run_id, status=status, error_message=error_message, metrics=run_metrics)


def _list_phase_raw_rows(task_id):
    return [r for r in list_raw_records(task_id) if (r.get('crawl_phase') or '') == 'list']


def _post_list_crawl_sources(sources, task):
    """list_first 源中已由 keyword 流水线处理的源（如 xhs）不再走批量 post 阶段。"""
    modes = crawl_modes_for_task(task)
    return [s for s in sources if modes.get(s) == 'list_first' and s != 'xhs']


def _run_post_list_crawl_phases(
    task_id, task, partners, crawl_ctx, run_metrics, run_id, log_fn, timeout_check,
    use_workers=False, sources=None,
):
    """list_triage → investigation → 返回是否成功（xhs 已在 keyword 流水线完成则跳过）。"""
    post_sources = _post_list_crawl_sources(sources or task.get('sources') or [], task)
    if not post_sources:
        if log_fn:
            log_fn('[monitor] 无待批量 post 的 list 源（xhs 已 keyword 流水线处理）')
        return True
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
            run_id, task_id, post_sources,
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


def _run_xhs_keyword_pipelines(
    task_id, task, partners, crawl_ctx, run_metrics, run_id, log_fn, timeout_check,
    xhs_keyword_items=None,
):
    from crawler_web import S
    from intel.db import create_keyword_run, get_keyword_run, sync_task_subtask_progress, update_keyword_run
    from intel.keyword_pipeline import collect_xhs_keywords, run_xhs_keyword_pipeline
    from intel.source_timeout import resolve_source_timeout_sec
    from intel.worker_config import worker_block

    xhs_worker = (worker_block('xhs').get('instances') or [{}])[0]
    xhs_cdp_port = int(xhs_worker.get('cdp_port') or 9230)

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

    total = len(xhs_keyword_items)
    if not total:
        return True

    update_task_status(
        task_id, 'crawling',
        progress={'phase': 'keyword_pipeline', 'done': 0, 'total': total, 'run_id': run_id},
    )
    sync_task_subtask_progress(task_id, run_id)

    for i, spec in enumerate(xhs_keyword_items):
        if timeout_check() or not S.running:
            return False
        if log_fn:
            log_fn('[monitor] keyword 流水线 [%s] %s' % (spec.get('cohort') or '-', spec['keyword'][:40]))
        update_task_status(
            task_id, 'crawling',
            progress={
                'phase': 'keyword_pipeline',
                'done': i,
                'total': total,
                'current_keyword': spec['keyword'],
                'run_id': run_id,
            },
        )
        from intel.xhs_credentials import try_pick_and_bind_xhs_orchestrator
        account = try_pick_and_bind_xhs_orchestrator(xhs_cdp_port, log_fn=log_fn)
        if not account:
            from intel.keyword_pipeline import now_iso
            kr_id = spec.get('keyword_run_id')
            if kr_id:
                update_keyword_run(
                    kr_id,
                    status='failed',
                    phase='pending',
                    error_message='无可用 xhs 账号',
                    finished_at=now_iso(),
                )
            sync_task_subtask_progress(task_id, run_id)
            continue
        kr_id = spec.get('keyword_run_id')
        if kr_id:
            kr = get_keyword_run(kr_id) or {}
            stats = dict(kr.get('stats') or {})
            stats['account_id'] = account.get('id')
            stats['account_label'] = account.get('label') or ''
            update_keyword_run(kr_id, stats_json=stats)
        if log_fn:
            log_fn('[monitor] 账号 %s (%s)' % (account.get('label') or '', account.get('id')))
        t0 = time.monotonic()
        try:
            run_xhs_keyword_pipeline(
                crawl_ctx, task, partners,
                spec['keyword'],
                cohort=spec.get('cohort') or '',
                keyword_run_id=spec.get('keyword_run_id'),
                run_metrics=run_metrics,
                timeout_sec=spec.get('timeout_sec') or None,
            )
        except Exception as e:
            if log_fn:
                log_fn('[monitor] keyword 失败 %s: %s' % (
                    spec['keyword'][:40], str(e)[:200],
                ), 'ERROR')
        run_metrics.add_crawl_ms('xhs', int((time.monotonic() - t0) * 1000))

    sync_task_subtask_progress(task_id, run_id)
    return True


def _run_list_crawl_only(
    task_id, task, partners, sources, crawl_ctx, run_metrics, run_id, log_fn, timeout_check,
    xhs_keyword_items=None,
):
    from crawler_web import S

    refresh_auto_priorities()
    batches = sort_batches_by_quota(build_keyword_batches(partners))
    list_sources = [
        s for s in sources
        if crawl_modes_for_task(task).get(s) == 'list_first' and s != 'xhs'
    ]
    has_xhs = 'xhs' in sources and crawl_modes_for_task(task).get('xhs') == 'list_first'

    if has_xhs:
        if not _run_xhs_keyword_pipelines(
            task_id, task, partners, crawl_ctx, run_metrics, run_id, log_fn, timeout_check,
            xhs_keyword_items=xhs_keyword_items,
        ):
            return False

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
            task=task,
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


def _keyword_subtask_error(run_id):
    from intel.db import keyword_run_counts
    counts = keyword_run_counts(run_id)
    failed = counts.get('failed', 0)
    if failed <= 0:
        return ''
    return '%d/%d 个 keyword 子任务失败' % (failed, counts.get('total', 0))


def run_monitor_task(
    task_id,
    log_fn=None,
    trigger='manual',
    analyze_mode='incremental',
    run_id=None,
    business_spec=None,
    retry_keyword_run_ids=None,
    resume_from_run_id=None,
    resume_sources=None,
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

    progress_patch = {
        'phase': 'list_crawl' if shared_pool else 'crawl',
        'done': 0,
        'total': 0,
        'run_id': run_id,
    }
    if trigger == 'resume' and resume_from_run_id:
        progress_patch['resume_run_id'] = resume_from_run_id

    sources = task.get('sources') or []
    budget = monitor_timeout_config_from_cfg(cfg)
    warn_if_analysis_timeout_clamped(budget, log_fn=log_fn)
    timeout_unlimited = bool(budget.get('unlimited'))
    timeout_sec = budget['task_timeout_sec']
    crawl_budget_sec = budget['crawl_budget_sec']
    analysis_reserve_sec = budget['analysis_reserve_sec']
    task_started = time.monotonic()
    task_deadline = float('inf') if timeout_unlimited else task_started + timeout_sec
    crawl_deadline = float('inf') if timeout_unlimited else task_started + crawl_budget_sec
    timed_out = False
    timeout_phase = ''
    final_status = 'done'
    err_msg = ''
    user_halt = ''
    halt_handled = False

    def should_abort():
        nonlocal user_halt, err_msg
        if is_task_halted(task_id):
            cur = get_monitor_task(task_id) or {}
            user_halt = cur.get('status') or 'stopped'
            err_msg = cur.get('error_message') or (
                '任务已暂停' if user_halt == 'paused' else '用户终止'
            )
            S.running = False
            return True
        if is_pause_requested(run_id):
            user_halt = 'paused'
            err_msg = '任务已暂停'
            S.running = False
            return True
        if is_stop_requested(run_id):
            user_halt = 'stopped'
            err_msg = '用户终止'
            S.running = False
            return True
        return False

    def timeout_check(phase='crawl'):
        nonlocal timed_out, err_msg, timeout_phase
        if should_abort():
            return True
        if timeout_unlimited:
            return False
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
        'run_metrics': run_metrics,
    }

    S.running = True
    S.running_type = 'monitor'
    update_task_status(
        task_id,
        'crawling',
        progress=progress_patch,
    )

    try:
        use_workers = workers_enabled()
        ok = False
        resume_mode = trigger == 'resume' and bool(resume_sources or resume_from_run_id)
        retry_mode = bool(retry_keyword_run_ids) or resume_mode
        if retry_mode and log_fn:
            if resume_mode:
                log_fn('[monitor] 继续任务，源: %s' % (resume_sources or []))
            else:
                log_fn('[monitor] 重跑 keyword 子任务: %s' % retry_keyword_run_ids)

        if use_workers:
            post_list_state = {'ran': False, 'ok': True}
            if retry_mode:
                from intel.crawl_queue import (
                    clear_run_queue,
                    enqueue_keyword_retry_run,
                    enqueue_resume_crawl,
                    prepare_retry_keyword_items,
                )
                from intel.worker_pool import run_keyword_retry_with_workers

                clear_run_queue(run_id)
                if resume_mode:
                    n = enqueue_resume_crawl(
                        run_id, task_id, task, partners,
                        resume_from_run_id, resume_sources or [],
                        keyword_run_ids=retry_keyword_run_ids,
                    )
                    if n <= 0:
                        raise ValueError('无可继续的子任务')
                    ok = run_resume_crawl_with_workers(
                        run_id, task_id, resume_sources or [],
                        log_fn=log_fn,
                        timeout_check=lambda: timeout_check('crawl'),
                    )
                else:
                    xhs_items = prepare_retry_keyword_items(
                        retry_keyword_run_ids, run_id, task_id,
                    )
                    if not xhs_items:
                        raise ValueError('无有效 keyword 子任务可重跑')
                    enqueue_keyword_retry_run(run_id, task_id, xhs_items)
                    ok = run_keyword_retry_with_workers(
                        run_id, task_id, log_fn=log_fn,
                        timeout_check=lambda: timeout_check('crawl'),
                    )
            else:
                if log_fn:
                    log_fn('[monitor] Worker 池 routine crawl（heimao ∥ xhs keyword）')

                def _maybe_run_post_list_during_crawl():
                    if post_list_state['ran'] or retry_mode or not has_list_first:
                        return
                    if timeout_check('crawl'):
                        return
                    from intel.crawl_queue import source_queue_idle
                    if crawl_modes_for_task(task).get('heimao') != 'list_first':
                        return
                    if not source_queue_idle(run_id, 'heimao'):
                        return
                    if log_fn:
                        log_fn('[monitor] 黑猫 list 已完成，开始初筛/勘察（不阻塞小红书 keyword）')
                    post_ok = _run_post_list_crawl_phases(
                        task_id, task, partners, crawl_ctx, run_metrics, run_id, log_fn, timeout_check,
                        use_workers=True, sources=sources,
                    )
                    post_list_state['ran'] = True
                    post_list_state['ok'] = post_ok
                    run_metrics.stats['_post_list_ran'] = True

                ok = run_routine_crawl_with_workers(
                    run_id, task_id, task, partners, sources, log_fn=log_fn,
                    timeout_check=lambda: timeout_check('crawl'),
                    on_poll=_maybe_run_post_list_during_crawl,
                )
            _merge_worker_state_metrics(run_id, run_metrics)
            from intel.db import sync_task_subtask_progress
            sync_task_subtask_progress(task_id, run_id)
            sub_err = _keyword_subtask_error(run_id)
            if sub_err and log_fn:
                log_fn('[monitor] %s' % sub_err, 'WARN')
            if has_list_first and not retry_mode:
                if not post_list_state.get('ran'):
                    ok = _run_post_list_crawl_phases(
                        task_id, task, partners, crawl_ctx, run_metrics, run_id, log_fn, timeout_check,
                        use_workers=True, sources=sources,
                    ) and ok
                elif not post_list_state.get('ok', True):
                    ok = False
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
            if retry_mode:
                from intel.crawl_queue import prepare_retry_keyword_items
                xhs_items = prepare_retry_keyword_items(
                    retry_keyword_run_ids, run_id, task_id,
                )
                if not xhs_items:
                    raise ValueError('无有效 keyword 子任务可重跑')
                ok = _run_xhs_keyword_pipelines(
                    task_id, task, partners, crawl_ctx, run_metrics, run_id, log_fn, timeout_check,
                    xhs_keyword_items=xhs_items,
                )
            elif has_list_first and has_legacy:
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

        from intel.db import sync_task_subtask_progress
        sync_task_subtask_progress(task_id, run_id)

        if not ok:
            if user_halt:
                halt_handled = True
                _apply_user_halt(
                    task_id, run_id, user_halt, run_metrics,
                    progress_phase='analyze' if timeout_phase == 'analyze' else 'crawl',
                )
                return
            if timed_out:
                halt_handled = True
                _apply_failure_halt(
                    task_id, run_id, run_metrics, err_msg,
                    progress_phase='crawl',
                    reason=_timeout_progress_reason(True, timeout_phase),
                )
                return
            final_status = 'failed'
            if not err_msg:
                err_msg = '任务已停止'
            halt_handled = True
            _apply_failure_halt(
                task_id, run_id, run_metrics, err_msg,
                progress_phase='crawl',
                reason='stopped',
            )
            return

        sub_err = _keyword_subtask_error(run_id)
        if sub_err and log_fn:
            log_fn('[monitor] %s' % sub_err, 'WARN')

        partial_halt = resolve_run_halt_after_crawl(run_id)
        if partial_halt and not user_halt:
            user_halt = partial_halt
            err_msg = '任务已暂停' if partial_halt == 'paused' else '用户终止'
            halt_handled = True
            _apply_user_halt(task_id, run_id, user_halt, run_metrics, progress_phase='crawl')
            return

        if is_task_halted(task_id):
            halt_handled = True
            cur = get_monitor_task(task_id) or {}
            run = get_task_run(run_id)
            if run and run.get('status') == 'running':
                _apply_user_halt(
                    task_id, run_id, cur.get('status') or 'stopped', run_metrics,
                    progress_phase='crawl',
                )
            return

        remaining = float('inf') if timeout_unlimited else max(0, task_deadline - time.monotonic())
        if timeout_unlimited:
            analysis_budget = int(analysis_reserve_sec or budget.get('analysis_timeout_sec') or 3600)
        else:
            analysis_budget = min(analysis_reserve_sec, remaining)
            if remaining >= 300:
                analysis_budget = max(300, analysis_budget)
            else:
                analysis_budget = max(60, min(analysis_budget, remaining))
        timed_out = False
        timeout_phase = ''
        S.running = True
        if log_fn and not timeout_unlimited and time.monotonic() - task_started >= timeout_sec - 120:
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
            task=task,
        )
        if timed_out:
            if user_halt:
                halt_handled = True
                _apply_user_halt(task_id, run_id, user_halt, run_metrics, progress_phase='analyze')
                return
            halt_handled = True
            if not err_msg:
                err_msg = _timeout_message('analyze', task_timeout_sec=timeout_sec)
            _apply_failure_halt(
                task_id, run_id, run_metrics, err_msg,
                progress_phase='analyze',
                reason=_timeout_progress_reason(True, timeout_phase),
            )
            return

        sub_err = _keyword_subtask_error(run_id)
        if sub_err:
            final_status = 'failed'
            err_msg = sub_err

        update_task_status(
            task_id,
            'failed' if sub_err else 'done',
            error_message=err_msg if sub_err else '',
            progress={'phase': 'done', 'intel_count': total_written, 'run_id': run_id},
        )
        if log_fn:
            if sub_err:
                log_fn('监测完成（含失败子任务）：情报 %d 条；%s' % (total_written, sub_err), 'WARN')
            else:
                log_fn('监测任务完成，情报 %d 条' % total_written)
    except Exception as e:
        if user_halt and not halt_handled:
            halt_handled = True
            _apply_user_halt(task_id, run_id, user_halt, run_metrics)
        else:
            final_status = 'failed'
            err_msg = _fail_from_exception(task_id, run_id, e, log_fn=log_fn)
    finally:
        try:
            if not halt_handled:
                if is_task_halted(task_id):
                    cur = get_monitor_task(task_id) or {}
                    run = get_task_run(run_id)
                    if run and run.get('status') == 'running':
                        _apply_user_halt(
                            task_id, run_id, cur.get('status') or 'stopped', run_metrics,
                        )
                else:
                    _finish_run(run_id, run_metrics, status=final_status, error_message=err_msg)
            _ensure_monitor_task_settled(
                task_id, run_id, run_metrics, final_status, err_msg, halt_handled,
            )
        finally:
            S.running = False
            S.running_type = ''
            try:
                close_cdp()
            except Exception:
                pass
