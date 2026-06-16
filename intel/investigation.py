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


def _priority_score(triage, p0_hit):
    rel = _RELEVANCE_RANK.get(triage.get('triage_relevance') or 'medium', 0)
    risk = _RISK_RANK.get(triage.get('triage_risk_hint') or 'none', 0)
    score = rel * 10 + risk * 5
    if p0_hit:
        score += 50
    if triage.get('needs_investigation'):
        score += 3
    return score


def build_investigation_queue(task_id, partners, business_spec=None, log_fn=None):
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
        score = _priority_score(triage, p0_hit or force)
        enqueue_investigation(task_id, row['id'], url, row['source'], score)
        queued += 1

    if log_fn:
        log_fn('[investigation] 队列 %d 条' % queued)
    return queued


def run_investigation_crawl(task_id, crawl_ctx, task, run_metrics=None, log_fn=None, timeout_check=None):
    queue = list_investigation_queue(task_id, status='pending')
    if not queue:
        return {'done': 0, 'failed': 0}

    raw_by_id = {r['id']: r for r in list_raw_records(task_id)}

    by_source = {}
    for item in queue:
        by_source.setdefault(item['source'], []).append(item)

    done = 0
    failed = 0
    for source_id, items in by_source.items():
        if timeout_check and timeout_check():
            break
        try:
            crawler = registry.get_crawler(source_id)
        except KeyError:
            failed += len(items)
            continue
        urls = [it['url'] for it in items if it.get('url')]
        if not urls:
            failed += len(items)
            continue
        if not hasattr(crawler, 'crawl_investigation'):
            failed += len(items)
            continue
        options = {}
        if source_id == 'xhs':
            crawl_items = []
            for it in items:
                raw = raw_by_id.get(it.get('raw_id')) or {}
                payload = raw.get('payload') or {}
                kw = (payload.get('_search_keyword') or raw.get('keyword') or '').strip()
                crawl_items.append({'url': it.get('url') or '', 'keyword': kw})
            options = {'items': crawl_items}
        import time
        t0 = time.monotonic()
        results = crawler.crawl_investigation(crawl_ctx, task, urls, options)
        crawl_ms = int((time.monotonic() - t0) * 1000)
        if run_metrics:
            run_metrics.add_investigation_crawl_ms(source_id, crawl_ms)
        url_map = {r.get('link') or r.get('url'): r for r in (results or []) if isinstance(r, dict)}
        for item in items:
            url = item.get('url') or ''
            payload = url_map.get(url)
            if payload and payload.get('ok') is not False and (
                payload.get('content') or payload.get('title')
            ):
                merge_raw_payload(item['raw_id'], payload, crawl_phase='detail')
                update_investigation_status(item['id'], 'done')
                done += 1
                if run_metrics:
                    run_metrics.record_investigation_done(1)
            else:
                err = (payload or {}).get('error') or 'no detail payload'
                update_investigation_status(item['id'], 'failed', err)
                failed += 1
                if run_metrics:
                    run_metrics.record_investigation_failed(1)

    return {'done': done, 'failed': failed}
