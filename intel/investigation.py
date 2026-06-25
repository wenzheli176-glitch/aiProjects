# -*- coding: utf-8 -*-
"""重点勘察队列构建与执行调度。"""
from config import cfg

from intel.db import (
    clear_investigation_queue,
    enqueue_investigation,
    get_raw_analysis_state,
    list_investigation_queue,
    list_raw_records,
    merge_raw_payload,
    update_investigation_status,
)
from intel.matcher import match_all_partners, partner_search_keywords
from intel.registry import registry

_RELEVANCE_RANK = {'high': 3, 'medium': 2, 'low': 1, 'noise': 0}
_RISK_RANK = {'severe': 2, 'elevated': 1, 'none': 0}
_HEIMAO_DETAIL_BODY_MIN = 80


def _heimao_routine_has_detail(row, task=None):
    """heimao legacy 且 routine 已 fetch_detail 并有有效 body 时跳过 investigation。"""
    if row.get('source') != 'heimao':
        return False
    if (row.get('crawl_phase') or 'legacy') != 'legacy':
        return False
    fetch_detail = bool((task or {}).get('fetch_detail', True))
    if not fetch_detail:
        return False
    payload = row.get('payload') or {}
    body = (
        payload.get('content') or payload.get('body') or payload.get('text') or ''
    )
    return len(str(body).strip()) >= _HEIMAO_DETAIL_BODY_MIN


def _threshold():
    lt = (cfg('analysis') or {}).get('list_triage') or {}
    th = lt.get('investigation_threshold') or {}
    return th.get('min_relevance') or 'medium', th.get('min_risk_hint') or 'elevated'


def _p0_partners(partners):
    return [p for p in partners if (p.get('priority_tier') or 'P1') == 'P0']


def _force_p0_investigation(normalized, p0_partners):
    text = '%s\n%s' % (normalized.get('title') or '', normalized.get('body') or '')
    text_lower = text.lower()
    for p in p0_partners:
        for kw in partner_search_keywords(p):
            if kw and (kw.lower() in text_lower or kw in text):
                return True
    return False


def _meets_threshold(triage, min_rel, min_risk):
    rel = triage.get('triage_relevance') or 'medium'
    risk = triage.get('triage_risk_hint') or 'none'
    if _RELEVANCE_RANK.get(rel, 0) < _RELEVANCE_RANK.get(min_rel, 2):
        return False
    if _RISK_RANK.get(risk, 0) < _RISK_RANK.get(min_risk, 1):
        return False
    return True


def row_needs_investigation(row, partners, business_spec=None, task=None):
    """判断单条 raw 是否需勘察（供 keyword 流水线增量使用）。"""
    business_spec = business_spec or {}
    if row.get('crawl_phase') == 'detail':
        return False
    if _heimao_routine_has_detail(row, task=task):
        return False
    triage = row.get('list_triage') or {}
    if not triage.get('triage_relevance'):
        return False

    min_rel, min_risk = _threshold()
    if business_spec.get('min_triage_relevance'):
        min_rel = business_spec['min_triage_relevance']
    force_ids = set(business_spec.get('force_investigation_partner_ids') or [])
    p0s = _p0_partners(partners)
    if force_ids:
        p0s = [p for p in partners if p['id'] in force_ids] or p0s

    try:
        from intel.registry import registry
        normalizer = registry.get_normalizer(row['source'])
        normalized = normalizer.normalize(row['payload'])
    except KeyError:
        normalized = {'title': '', 'body': ''}

    p0_hit = _force_p0_investigation(normalized, p0s)
    force = bool(force_ids and match_all_partners(
        normalized, [p for p in partners if p['id'] in force_ids],
    ))
    needs = bool(triage.get('needs_investigation')) or p0_hit or force
    if not needs:
        return False
    if not p0_hit and not force and not _meets_threshold(triage, min_rel, min_risk):
        return False
    return True


def _priority_score(triage, p0_hit):
    rel = _RELEVANCE_RANK.get(triage.get('triage_relevance') or 'medium', 0)
    risk = _RISK_RANK.get(triage.get('triage_risk_hint') or 'none', 0)
    score = rel * 10 + risk * 5
    if p0_hit:
        score += 50
    if triage.get('needs_investigation'):
        score += 3
    return score


def _xhs_uses_keyword_pipeline(task=None):
    """小红书 list_first 已在 keyword 流水线内完成同页勘察，不走批量 investigation。"""
    from source_profiles import resolve_source_crawl_mode
    return resolve_source_crawl_mode('xhs', task) == 'list_first'


def build_investigation_queue(task_id, partners, business_spec=None, log_fn=None, task=None):
    business_spec = business_spec or {}
    min_rel, min_risk = _threshold()
    if business_spec.get('min_triage_relevance'):
        min_rel = business_spec['min_triage_relevance']
    force_ids = set(business_spec.get('force_investigation_partner_ids') or [])

    clear_investigation_queue(task_id)
    p0s = _p0_partners(partners)
    if force_ids:
        p0s = [p for p in partners if p['id'] in force_ids] or p0s

    analysis_state = get_raw_analysis_state(task_id)
    raw_rows = list_raw_records(task_id)
    queued = 0

    for row in raw_rows:
        if row.get('crawl_phase') == 'detail':
            continue
        if _heimao_routine_has_detail(row, task=task):
            continue
        triage = row.get('list_triage') or {}
        if not triage.get('triage_relevance'):
            continue

        try:
            normalizer = registry.get_normalizer(row['source'])
            normalized = normalizer.normalize(row['payload'])
        except KeyError:
            normalized = {'title': '', 'body': ''}

        p0_hit = _force_p0_investigation(normalized, p0s)
        force = bool(force_ids and match_all_partners(normalized, [p for p in partners if p['id'] in force_ids]))
        needs = bool(triage.get('needs_investigation')) or p0_hit or force
        if not needs:
            continue
        if not p0_hit and not force and not _meets_threshold(triage, min_rel, min_risk):
            continue

        st = analysis_state.get(row['id']) or {}
        if st.get('has_intel') and row.get('crawl_phase') != 'list':
            raw_upd = row.get('updated_at') or row.get('created_at') or ''
            intel_at = st.get('analyzed_at') or ''
            if raw_upd <= intel_at:
                continue

        url = normalized.get('url') or (row.get('payload') or {}).get('link') or ''
        if row.get('source') == 'xhs' and _xhs_uses_keyword_pipeline(task):
            continue
        score = _priority_score(triage, p0_hit or force)
        enqueue_investigation(task_id, row['id'], url, row['source'], score)
        queued += 1

    if log_fn:
        log_fn('[investigation] 队列 %d 条' % queued)
    return queued


def skip_investigation_batch_for_quota(run_id, batch_items, run_metrics=None):
    """配额用尽时批量 skip investigation 项。"""
    from intel.modal_quota import record_skipped_quota

    n = 0
    for item in batch_items or []:
        qid = item.get('queue_id')
        if not qid:
            continue
        update_investigation_status(qid, 'skipped', 'modal_quota_exceeded')
        n += 1
    if run_id and n:
        record_skipped_quota(run_id, n)
    if run_metrics and n:
        run_metrics.stats['investigation_skipped_quota'] = (
            int(run_metrics.stats.get('investigation_skipped_quota') or 0) + n
        )
    return n


def process_investigation_batch(source_id, batch_items, task, crawl_ctx, run_metrics=None):
    """执行单源 investigation 批次（Worker 与单进程共用）。"""
    import time

    if not batch_items:
        return {'done': 0, 'failed': 0, 'skipped': 0}

    if source_id == 'xhs' and _xhs_uses_keyword_pipeline(task):
        n = 0
        for item in batch_items:
            qid = item.get('queue_id')
            if not qid:
                continue
            update_investigation_status(qid, 'skipped', 'xhs_keyword_pipeline')
            n += 1
        if (crawl_ctx or {}).get('log'):
            crawl_ctx['log'](
                '[xhs] 跳过批量勘察 %d 条（已在 keyword 流水线同页勘察）' % n,
                'INFO',
            )
        return {'done': 0, 'failed': 0, 'skipped': n}

    run_id = (crawl_ctx or {}).get('run_id')
    if source_id == 'xhs' and run_id:
        from intel.modal_quota import is_quota_exhausted
        if is_quota_exhausted(run_id):
            skipped = skip_investigation_batch_for_quota(run_id, batch_items, run_metrics)
            return {'done': 0, 'failed': 0, 'skipped': skipped}

    try:
        crawler = registry.get_crawler(source_id)
    except KeyError:
        return {'done': 0, 'failed': len(batch_items), 'skipped': 0}

    urls = [it.get('url') for it in batch_items if it.get('url')]
    if not urls:
        return {'done': 0, 'failed': len(batch_items), 'skipped': 0}

    if not hasattr(crawler, 'crawl_investigation'):
        return {'done': 0, 'failed': len(batch_items), 'skipped': 0}

    options = {}
    if source_id == 'xhs':
        options = {
            'items': [
                {'url': it.get('url') or '', 'keyword': it.get('keyword') or ''}
                for it in batch_items
            ],
        }

    t0 = time.monotonic()
    results = crawler.crawl_investigation(crawl_ctx, task, urls, options)
    crawl_ms = int((time.monotonic() - t0) * 1000)
    if run_metrics:
        run_metrics.add_investigation_crawl_ms(source_id, crawl_ms)

    url_map = {r.get('link') or r.get('url'): r for r in (results or []) if isinstance(r, dict)}
    done = 0
    failed = 0
    skipped = 0
    for item in batch_items:
        url = item.get('url') or ''
        payload = url_map.get(url)
        if payload and payload.get('ok') is not False and (
            payload.get('content') or payload.get('title')
        ):
            merge_raw_payload(item['raw_id'], payload, crawl_phase='detail')
            update_investigation_status(item['queue_id'], 'done')
            done += 1
            if run_metrics:
                run_metrics.record_investigation_done(1)
        else:
            err = (payload or {}).get('error') or 'no detail payload'
            if err == 'modal_quota_exceeded':
                update_investigation_status(item['queue_id'], 'skipped', err)
                skipped += 1
            else:
                update_investigation_status(item['queue_id'], 'failed', err)
                failed += 1
                if run_metrics:
                    run_metrics.record_investigation_failed(1)
    if run_id and source_id == 'xhs':
        from intel.modal_quota import sync_modal_quota_to_run_metrics
        sync_modal_quota_to_run_metrics(run_id, run_metrics)
    return {'done': done, 'failed': failed, 'skipped': skipped}


def sync_investigation_run_metrics(task_id, run_metrics, run_id=None):
    """从 investigation_queue 状态汇总 metrics（Worker 路径）。"""
    if not run_metrics:
        return {'done': 0, 'failed': 0, 'skipped': 0}
    done = failed = skipped = 0
    for item in list_investigation_queue(task_id, status=None):
        st = item.get('status')
        if st == 'done':
            done += 1
        elif st == 'failed':
            failed += 1
        elif st == 'skipped':
            skipped += 1
    run_metrics.stats['investigation_done'] = done
    run_metrics.stats['investigation_failed'] = failed
    run_metrics.stats['investigation_skipped_quota'] = skipped
    if run_id:
        from intel.modal_quota import sync_modal_quota_to_run_metrics
        sync_modal_quota_to_run_metrics(run_id, run_metrics)
    return {'done': done, 'failed': failed, 'skipped': skipped}


def run_investigation_crawl(task_id, crawl_ctx, task, run_metrics=None, log_fn=None, timeout_check=None):
    queue = list_investigation_queue(task_id, status='pending')
    if not queue:
        return {'done': 0, 'failed': 0}

    by_source = {}
    for item in queue:
        by_source.setdefault(item['source'], []).append(item)

    done = 0
    failed = 0
    raw_by_id = {r['id']: r for r in list_raw_records(task_id)}
    for source_id, items in by_source.items():
        if timeout_check and timeout_check():
            break
        batch_items = [{
            'queue_id': it['id'],
            'raw_id': it.get('raw_id'),
            'url': it.get('url') or '',
            'keyword': '',
        } for it in items]
        if source_id == 'xhs':
            for bi in batch_items:
                raw = raw_by_id.get(bi.get('raw_id')) or {}
                payload = raw.get('payload') or {}
                bi['keyword'] = (payload.get('_search_keyword') or raw.get('keyword') or '').strip()
        result = process_investigation_batch(
            source_id, batch_items, task, crawl_ctx, run_metrics=run_metrics,
        )
        done += result.get('done', 0)
        failed += result.get('failed', 0)

    run_id = (crawl_ctx or {}).get('run_id')
    if run_id:
        from intel.modal_quota import sync_modal_quota_to_run_metrics
        sync_modal_quota_to_run_metrics(run_id, run_metrics)
    return {'done': done, 'failed': failed}
