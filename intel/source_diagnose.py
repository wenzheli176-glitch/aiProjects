# -*- coding: utf-8 -*-
"""单进程 Run 前各源 Cookie 诊断。"""
from auth_utils import apply_cookies_to_context, diagnose_login


def diagnose_source_login_ok(site, diag):
    if site == 'heimao':
        return bool(diag.get('has_sub_in_browser') or diag.get('has_sub_in_config'))
    if site == 'xhs':
        return bool(diag.get('has_xhs_in_browser') or diag.get('has_xhs_in_config'))
    return bool(diag.get('ok'))


def filter_sources_after_diagnose(sources, run_metrics=None, log_fn=None):
    """诊断各源登录；返回可继续爬取的 source 列表。"""
    sources = list(sources or [])
    if not sources:
        return []

    from crawler_web import connect_cdp, prepare_browser_for_crawl

    if not prepare_browser_for_crawl():
        if log_fn:
            log_fn('[monitor] Chrome 未就绪，无法诊断 Cookie', 'ERROR')
        return []

    ctx = connect_cdp()
    ok_sources = []
    failed = 0
    for site in sources:
        if site not in ('heimao', 'xhs'):
            ok_sources.append(site)
            continue
        apply_cookies_to_context(ctx, site, log_fn)
        diag = diagnose_login(ctx, site)
        if diagnose_source_login_ok(site, diag):
            ok_sources.append(site)
            if run_metrics:
                run_metrics.record_worker_instance(site, '%s-0' % site, 'diagnose_ok', diagnose_ok=True)
            if log_fn:
                log_fn('[monitor] %s Cookie 诊断通过' % site)
        else:
            failed += 1
            if run_metrics:
                run_metrics.record_worker_instance(site, '%s-0' % site, 'diagnose_failed', diagnose_ok=False)
            if log_fn:
                log_fn('[monitor] %s Cookie 诊断失败，跳过该源' % site, 'WARN')
    if failed and run_metrics:
        run_metrics.set_sources_degraded(failed)
    return ok_sources
