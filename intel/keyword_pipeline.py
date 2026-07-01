# -*- coding: utf-8 -*-
"""小红书单 keyword 流水线：列表爬取 → 初筛 → 同页勘察。"""
import time

from config import cfg
from intel.time_util import now_iso

from intel.db import (
    get_keyword_run,
    insert_raw_records,
    list_raw_records_by_ids,
    merge_raw_payload,
    sync_task_subtask_progress,
    update_keyword_run,
)


def _merge_keyword_stats(existing_stats, stats):
    """保留轮换写入的账号字段，避免流水线初始化 stats 时覆盖。"""
    for key in ('account_id', 'account_label'):
        val = (existing_stats or {}).get(key)
        if val:
            stats[key] = val
    return stats
from intel.investigation import row_needs_investigation
from intel.ignore_before import resolve_ignore_before
from intel.triage import run_list_triage


def _log(crawl_ctx, msg, level='INFO'):
    log_fn = (crawl_ctx or {}).get('log')
    if log_fn:
        log_fn(msg, level)


def _keyword_timeout_sec():
    return max(60, int(cfg('xhs', 'keyword_timeout_sec', default=3600) or 3600))


def make_keyword_timeout_check(crawl_ctx, keyword_run_id, started_mono, timeout_sec=None):
    run_id = (crawl_ctx or {}).get('run_id')
    source_id = (crawl_ctx or {}).get('source_id') or 'xhs'
    limit = timeout_sec or (crawl_ctx or {}).get('keyword_timeout_sec') or _keyword_timeout_sec()
    deadline = started_mono + int(limit)
    # 必须在覆盖 ctx['timeout_check'] 之前捕获父级检查，否则会递归调用自身。
    parent_timeout_check = (crawl_ctx or {}).get('timeout_check')

    def _check():
        from intel.run_state import is_halt_requested
        if run_id and is_halt_requested(run_id, source_id):
            return True
        if parent_timeout_check and parent_timeout_check is not _check:
            if parent_timeout_check():
                return True
        if time.monotonic() >= deadline:
            return True
        return False

    return _check


def run_inpage_xhs_investigation(page, ctx, items_by_link, rows, partners, task, crawl_ctx, run_metrics=None):
    """在当前搜索页对需勘察条目弹窗抓详情（不重搜）。"""
    from crawler_web import S
    from login_gate import is_xhs_detail_auth_failure, wait_for_site_login
    from xhs_detail import (
        fetch_xhs_detail_via_modal,
        find_note_item_for_url,
        parse_xhs_note_id,
        scroll_search_for_note,
    )

    x = cfg('xhs') or {}
    inv = dict(x.get('investigation_detail') or {})
    run_id = (crawl_ctx or {}).get('run_id')
    business_spec = (task or {}).get('business_spec') or {}
    done = failed = skipped = 0

    for row in rows:
        if not S.running:
            break
        tc = (crawl_ctx or {}).get('timeout_check')
        if tc and tc():
            break
        if not row_needs_investigation(row, partners, business_spec=business_spec, task=task):
            continue

        payload = row.get('payload') or {}
        link = payload.get('link') or ''
        if not link:
            failed += 1
            continue

        if run_id:
            from intel.modal_quota import (
                is_quota_exhausted,
                record_skipped_quota,
                release_modal_slot,
                reserve_modal_slot,
            )
            if is_quota_exhausted(run_id):
                record_skipped_quota(run_id, 1)
                skipped += 1
                continue
            if not reserve_modal_slot(run_id):
                record_skipped_quota(run_id, 1)
                skipped += 1
                continue
            reserved = True
        else:
            reserved = False

        note_id = parse_xhs_note_id(link)
        item = items_by_link.get(link)
        if not item:
            item, _reason = find_note_item_for_url(page, link, note_id)
        if not item:
            scroll_rounds = int(x.get('scroll_times_per_page', 3))
            item, _reason = scroll_search_for_note(page, note_id, scroll_rounds)

        if not item:
            _log(crawl_ctx, '  keyword 勘察 dom_not_found %s' % link[-28:], 'WARN')
            if reserved and run_id:
                release_modal_slot(run_id)
            failed += 1
            if run_metrics:
                run_metrics.record_investigation_failed(1)
            continue

        _log(crawl_ctx, '  XHS keyword 勘察(同页): %s' % link[-28:])
        detail, err = fetch_xhs_detail_via_modal(page, item, link, crawl_ctx.get('log'))
        if err and is_xhs_detail_auth_failure(page, detail or {}):
            _log(crawl_ctx, '  详情未登录，等待登录…', 'WARN')
            if not wait_for_site_login(ctx, page, 'xhs', S):
                if reserved and run_id:
                    release_modal_slot(run_id)
                failed += 1
                break
            item, _ = find_note_item_for_url(page, link, note_id)
            if item:
                detail, err = fetch_xhs_detail_via_modal(page, item, link, crawl_ctx.get('log'))

        if run_id and reserved:
            release_modal_slot(run_id)

        if err or not (detail.get('content') or detail.get('title')):
            failed += 1
            if run_metrics:
                run_metrics.record_investigation_failed(1)
            continue

        merge_raw_payload(row['id'], detail, crawl_phase='detail')
        done += 1
        if run_metrics:
            run_metrics.record_investigation_done(1)
            run_metrics.stats['investigation_modal_done'] = (
                int(run_metrics.stats.get('investigation_modal_done') or 0) + 1
            )

        time.sleep(__import__('random').uniform(
            float(inv.get('between_detail_min', 4)),
            float(inv.get('between_detail_max', 7)),
        ))

    if run_id:
        from intel.modal_quota import sync_modal_quota_to_run_metrics
        sync_modal_quota_to_run_metrics(run_id, run_metrics)

    return {'done': done, 'failed': failed, 'skipped': skipped}


def run_xhs_keyword_pipeline(
    crawl_ctx,
    task,
    partners,
    keyword,
    cohort='',
    keyword_run_id=None,
    run_metrics=None,
    timeout_sec=None,
):
    """单 keyword：list → triage → 同页 investigation。"""
    from crawler_web import crawl_xhs_list_with_dom
    from intel.source_timeout import resolve_source_timeout_sec

    task_id = task['id']
    if timeout_sec is None:
        timeout_sec = resolve_source_timeout_sec('xhs', partners, keyword=keyword)
    ctx = dict(crawl_ctx or {})
    ctx['keyword_timeout_sec'] = int(timeout_sec)
    started_mono = time.monotonic()
    kw_check = make_keyword_timeout_check(ctx, keyword_run_id, started_mono, timeout_sec=timeout_sec)
    ctx['timeout_check'] = kw_check

    stats = {
        'list_count': 0,
        'triage_processed': 0,
        'investigation_done': 0,
        'investigation_failed': 0,
        'investigation_skipped': 0,
        'phase_timing_ms': {
            'list_crawl_ms': 0,
            'triage_ms': 0,
            'investigation_ms': 0,
        },
    }
    if keyword_run_id:
        existing = get_keyword_run(keyword_run_id) or {}
        _merge_keyword_stats(existing.get('stats') or {}, stats)

    def _mark_phase_start(phase_name):
        stats['_current_phase'] = phase_name
        stats['_phase_started_at'] = now_iso()

    def _flush_phase_timing(timing_key, started_mono):
        if started_mono is None:
            return None
        ms = max(0, int((time.monotonic() - started_mono) * 1000))
        stats['phase_timing_ms'][timing_key] = int(
            stats['phase_timing_ms'].get(timing_key) or 0
        ) + ms
        return time.monotonic()

    if keyword_run_id:
        update_keyword_run(
            keyword_run_id,
            status='running',
            phase='list',
            started_at=now_iso(),
            error_message='',
            stats_json=stats,
        )
        sync_task_subtask_progress(task_id, ctx.get('run_id'))

    phase_started = time.monotonic()
    _mark_phase_start('list')

    try:
        max_pages = int(task.get('max_pages') or 2)
        dom = crawl_xhs_list_with_dom(
            keyword,
            max_pages,
            managed_session=True,
            timeout_check=kw_check,
            log_fn=ctx.get('log'),
        )
        if dom.get('error'):
            raise RuntimeError(dom['error'])

        records = dom.get('records') or []
        for rec in records:
            rec['_search_keyword'] = keyword
            rec['_cohort'] = cohort or ''

        insert_result = insert_raw_records(
            task_id, None, 'xhs', keyword, records,
            run_metrics=run_metrics, crawl_phase='list',
            ignore_before=resolve_ignore_before(task=task),
        )
        skip_ib = int(insert_result.get('skipped_ignore_before') or 0)
        if skip_ib:
            ib = resolve_ignore_before(task=task)
            _log(ctx, '[xhs] 列表忽略早于 %s 跳过 %d 条（未入库）' % (ib, skip_ib))
        raw_ids = insert_result.get('ids') or []
        stats['list_count'] = len(raw_ids)

        phase_started = _flush_phase_timing('list_crawl_ms', phase_started)

        if keyword_run_id:
            _mark_phase_start('triage')
            update_keyword_run(keyword_run_id, phase='triage', stats_json=stats)
            sync_task_subtask_progress(task_id, ctx.get('run_id'))
        _log(ctx, '[xhs] keyword 列表完成 %s → 初筛（%d 条）' % (keyword[:30], len(raw_ids)))

        phase_started = time.monotonic()
        raw_rows = list_raw_records_by_ids(task_id, raw_ids)
        triage_result = run_list_triage(
            task_id, raw_rows, partners,
            log_fn=ctx.get('log'), run_metrics=run_metrics, run_id=ctx.get('run_id'),
        )
        stats['triage_processed'] = triage_result.get('processed', 0)
        raw_rows = list_raw_records_by_ids(task_id, raw_ids)

        phase_started = _flush_phase_timing('triage_ms', phase_started)

        if keyword_run_id:
            _mark_phase_start('investigation')
            update_keyword_run(keyword_run_id, phase='investigation', stats_json=stats)
            sync_task_subtask_progress(task_id, ctx.get('run_id'))
        need_inv = sum(1 for r in raw_rows if row_needs_investigation(
            r, partners, business_spec=(task or {}).get('business_spec'), task=task,
        ))
        _log(ctx, '[xhs] keyword 初筛完成 → 同页勘察（待勘察 %d 条）' % need_inv)

        inv = run_inpage_xhs_investigation(
            dom.get('page'),
            dom.get('ctx'),
            dom.get('items_by_link') or {},
            raw_rows,
            partners,
            task,
            ctx,
            run_metrics=run_metrics,
        )
        stats['investigation_done'] = inv.get('done', 0)
        stats['investigation_failed'] = inv.get('failed', 0)
        stats['investigation_skipped'] = inv.get('skipped', 0)

        phase_started = _flush_phase_timing('investigation_ms', phase_started)

        run_id_val = ctx.get('run_id')
        if run_id_val and task_id:
            from intel.analyze_drain import maybe_batch_drain_analyze
            maybe_batch_drain_analyze(
                task_id, run_id_val, task=task, run_metrics=run_metrics,
                log_fn=lambda msg, level='INFO': _log(ctx, msg, level),
            )

        if kw_check() and time.monotonic() >= started_mono + int(
            ctx.get('keyword_timeout_sec') or _keyword_timeout_sec()
        ):
            limit = int(ctx.get('keyword_timeout_sec') or _keyword_timeout_sec())
            raise RuntimeError('keyword 超时（timeout_sec=%d）' % limit)

        if keyword_run_id:
            stats.pop('_current_phase', None)
            stats.pop('_phase_started_at', None)
            update_keyword_run(
                keyword_run_id,
                status='done',
                phase='done',
                finished_at=now_iso(),
                stats_json=stats,
                error_message='',
            )
        return stats

    except Exception as e:
        from intel.run_state import is_halt_requested
        msg = str(e)[:500]
        run_id_val = (crawl_ctx or {}).get('run_id')
        if keyword_run_id and phase_started is not None:
            phase = stats.get('_current_phase') or 'list'
            key_map = {'list': 'list_crawl_ms', 'triage': 'triage_ms', 'investigation': 'investigation_ms'}
            _flush_phase_timing(key_map.get(phase, 'list_crawl_ms'), phase_started)
        if keyword_run_id and run_id_val and is_halt_requested(run_id_val):
            update_keyword_run(
                keyword_run_id,
                status='pending',
                phase='pending',
                finished_at=None,
                stats_json=stats,
                error_message='',
            )
            return stats
        if keyword_run_id:
            stats.pop('_current_phase', None)
            stats.pop('_phase_started_at', None)
            update_keyword_run(
                keyword_run_id,
                status='failed',
                phase='failed',
                finished_at=now_iso(),
                stats_json=stats,
                error_message=msg,
            )
        raise
    finally:
        if keyword_run_id and ctx.get('run_id'):
            sync_task_subtask_progress(task_id, ctx.get('run_id'))


def collect_xhs_keywords(partners):
    """从合作方批次展开为 keyword 列表（含 partner_ids）。"""
    from intel.keyword_batch import build_keyword_batches, sort_batches_by_quota
    from intel.matcher import partner_search_keywords

    out = []
    seen = set()
    kw_partners = {}
    for p in partners or []:
        for kw in partner_search_keywords(p):
            kw_partners.setdefault(kw, set()).add(p['id'])

    for batch in sort_batches_by_quota(build_keyword_batches(partners)):
        cohort = batch.get('cohort') or ''
        for kw in batch.get('keywords') or []:
            key = (kw, cohort)
            if kw and key not in seen:
                seen.add(key)
                out.append({
                    'keyword': kw,
                    'cohort': cohort,
                    'partner_ids': sorted(kw_partners.get(kw) or []),
                })
    return out
