# -*- coding: utf-8 -*-
"""监测任务编排：partner × source 爬取 → 归一化 → 匹配 → AI 分析。"""
import hashlib
import time

from config import cfg
from intel.analyze import analyze_candidates
from intel.db import (
    clear_intel_for_task,
    create_analysis_job,
    create_task_run,
    finish_task_run,
    get_monitor_task,
    get_partner,
    get_raw_analysis_state,
    insert_raw_records,
    list_raw_records,
    update_task_status,
)
from intel.matcher import export_tier_for_match, match_best_partner
from intel.registry import registry
from intel.run_metrics import RunMetrics


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


def _build_candidates_from_raw(task_id, partners, analyze_mode='incremental', run_metrics=None):
    candidates_by_partner = {}
    raw_rows = list_raw_records(task_id)
    analysis_state = get_raw_analysis_state(task_id) if analyze_mode == 'incremental' else {}
    for row in raw_rows:
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
        normalized = normalizer.normalize(row['payload'])
        partner = get_partner(row['partner_id']) if row['partner_id'] else partners[0]
        match = match_best_partner(normalized, [partner], default_partner_id=row['partner_id'])
        tier = export_tier_for_match(match)
        replace_intel = False
        if analyze_mode == 'incremental':
            st = analysis_state.get(row['id']) or {}
            if st.get('has_intel'):
                raw_upd = row.get('updated_at') or row.get('created_at') or ''
                intel_at = st.get('analyzed_at') or ''
                if raw_upd > intel_at:
                    replace_intel = True
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
        candidates_by_partner.setdefault(pid, {'partner': partner, 'items': []})
        candidates_by_partner[pid]['items'].append(cand)
    return candidates_by_partner


def _check_task_timeout(task_id, deadline, timeout_sec, log_fn=None):
    from crawler_web import S

    if time.monotonic() < deadline:
        return False
    S.running = False
    msg = '任务超时（task_timeout_sec=%d）' % int(timeout_sec)
    update_task_status(
        task_id,
        'failed',
        error_message=msg,
        progress={'reason': 'timeout', 'phase': 'timeout'},
    )
    if log_fn:
        log_fn('[monitor] %s' % msg, 'WARN')
    return True


def _run_analysis_phase(
    task_id,
    partners,
    analyze_mode='incremental',
    run_id=None,
    run_metrics=None,
    log_fn=None,
    timeout_check=None,
):
    if analyze_mode == 'full_replace':
        clear_intel_for_task(task_id)
        if log_fn:
            log_fn('[monitor] 全量重分析：已清除旧情报')
    candidates_by_partner = _build_candidates_from_raw(
        task_id, partners, analyze_mode=analyze_mode, run_metrics=run_metrics,
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


def reanalyze_monitor_task(
    task_id,
    log_fn=None,
    replace=True,
    analyze_mode=None,
    trigger='manual',
    run_id=None,
):
    """仅基于已有 raw_records 重新 AI 分析，不重新爬取。"""
    from crawler_web import S

    if analyze_mode is None:
        analyze_mode = 'full_replace' if replace else 'incremental'

    task = get_monitor_task(task_id)
    if not task:
        raise ValueError('任务不存在: %s' % task_id)
    if S.running:
        raise RuntimeError('已有任务进行中')
    if not list_raw_records(task_id):
        raise ValueError('无原始数据，请先执行完整监测')

    partners = _get_enabled_partners(task)
    if not partners:
        update_task_status(task_id, 'failed', error_message='无有效合作方')
        return 0

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
        err_msg = str(e)[:200]
        update_task_status(task_id, 'failed', error_message=err_msg)
        if log_fn:
            log_fn('AI 分析失败: %s' % str(e)[:120], 'ERROR')
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
):
    from crawler_web import S, close_cdp, prepare_browser_for_crawl

    task = get_monitor_task(task_id)
    if not task:
        raise ValueError('任务不存在: %s' % task_id)

    if S.running:
        raise RuntimeError('已有爬取/监测任务进行中')

    partners = _get_enabled_partners(task)
    if not partners:
        update_task_status(task_id, 'failed', error_message='无有效合作方')
        return

    run_metrics = RunMetrics()
    if not run_id:
        run_id = create_task_run(task_id, trigger=trigger, analyze_mode=analyze_mode)

    sources = task.get('sources') or []
    crawl_ctx = {'log': log_fn, 'monitor_active': True}
    timeout_sec = int(cfg('monitor', 'task_timeout_sec', default=7200) or 7200)
    deadline = time.monotonic() + timeout_sec
    timed_out = False
    final_status = 'done'
    err_msg = ''

    def timeout_check():
        nonlocal timed_out
        if _check_task_timeout(task_id, deadline, timeout_sec, log_fn):
            timed_out = True
            return True
        return False

    S.running = True
    S.running_type = 'monitor'
    update_task_status(
        task_id,
        'crawling',
        progress={'phase': 'crawl', 'done': 0, 'total': 0, 'run_id': run_id},
    )

    try:
        if not prepare_browser_for_crawl():
            final_status = 'failed'
            err_msg = 'Chrome 未就绪'
            update_task_status(task_id, 'failed', error_message=err_msg)
            return

        total_steps = len(partners) * len(sources)
        step = 0
        for partner in partners:
            for source_id in sources:
                if timeout_check():
                    break
                if not S.running:
                    break
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
                    run_metrics=run_metrics,
                )
                if log_fn:
                    parts = []
                    if ins.get('inserted'):
                        parts.append('新增 %d' % ins['inserted'])
                    if ins.get('updated'):
                        parts.append('更新 %d' % ins['updated'])
                    if ins.get('unchanged'):
                        parts.append('未变 %d' % ins['unchanged'])
                    if parts:
                        log_fn('[monitor] raw %s' % ' · '.join(parts))
            if timed_out:
                break

        if timed_out:
            final_status = 'failed'
            err_msg = '任务超时'
            return
        if not S.running:
            final_status = 'failed'
            err_msg = '任务已停止'
            update_task_status(task_id, 'failed', error_message=err_msg)
            return

        update_task_status(task_id, 'analyzing', progress={'phase': 'normalize', 'run_id': run_id})
        total_written = _run_analysis_phase(
            task_id,
            partners,
            analyze_mode=analyze_mode,
            run_id=run_id,
            run_metrics=run_metrics,
            log_fn=log_fn,
            timeout_check=timeout_check,
        )
        if timed_out:
            final_status = 'failed'
            err_msg = '任务超时'
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
        err_msg = str(e)[:200]
        update_task_status(task_id, 'failed', error_message=err_msg)
        if log_fn:
            log_fn('监测任务失败: %s' % str(e)[:120], 'ERROR')
    finally:
        _finish_run(run_id, run_metrics, status=final_status, error_message=err_msg)
        S.running = False
        S.running_type = ''
        close_cdp()
