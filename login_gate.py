# -*- coding: utf-8 -*-
"""爬取任务登录门禁：等待用户登录后自动续跑（黑猫 / 小红书）。"""
import time

from config import get_config, build_heimao_detail_js
from heimao_session import (
    ensure_heimao_detail_url,
    extract_heimao_sid,
    find_heimao_detail_href_in_html,
    heimao_browser_has_weibo_session,
    heimao_on_weibo_login_page,
    heimao_page_shows_login_prompt,
    open_heimao_login_page,
    count_heimao_complaint_links,
)
from auth_utils import (
    apply_cookies_to_context,
    check_login_on_page,
    export_cookies_from_context,
    save_site_cookies,
    get_context_cookies_for_site,
    has_weibo_session,
    has_xhs_session,
    page_has_login_wall,
    page_has_login_fail_text,
    _page_has_login_fail_text,
)


def _auth_cfg(site):
    return get_config().get('auth', {}).get(site, {})


def site_label(site):
    return {'heimao': '黑猫投诉', 'xhs': '小红书'}.get(site, site)


def _weibo_sub_value(cookies):
    for c in cookies:
        if c.get('name') == 'SUB' and c.get('value'):
            return c.get('value')
    return ''


def _xhs_session_fingerprint(cookies):
    parts = []
    for name in ('web_session', 'webId'):
        for c in cookies:
            if c.get('name') == name and c.get('value'):
                parts.append('%s=%s' % (name, c.get('value')[:24]))
    return '|'.join(parts)


def _set_login_wait_ui(runtime, site, message):
    ac = _auth_cfg(site)
    with runtime.lock:
        runtime.phase = 'waiting_login'
        runtime.login_wait = {
            'site': site,
            'started_at': time.time(),
            'timeout_sec': int(ac.get('wait_timeout_sec', 300)),
            'message': message,
            'elapsed_sec': 0,
        }


def _clear_login_wait_ui(runtime):
    with runtime.lock:
        runtime.phase = ''
        runtime.login_wait = None


def check_site_logged_in(ctx, page, site, poll_only=False):
    if not poll_only:
        apply_cookies_to_context(ctx, site, None)
    return check_login_on_page(page, site, poll_only=poll_only)


def _heimao_detail_has_body(detail):
    detail = detail or {}
    return any((detail.get(k) or '').strip() for k in (
        'content', 'merchant', 'problem', 'demand',
    ))


def _goto_heimao_check_page(page, log_fn=None):
    ac = _auth_cfg('heimao')
    url = ac.get('login_check_url') or ac.get('login_url', '')
    if not url:
        return
    try:
        page.goto(url, timeout=int(ac.get('check_timeout_ms', 20000)), wait_until='domcontentloaded')
        time.sleep(0.8)
    except Exception as e:
        if log_fn:
            log_fn('[heimao] 打开黑猫首页失败: %s' % str(e)[:60], 'WARN')


def _heimao_login_ok_after_wait(ctx, page):
    """等待登录轮询：不跳转页面，避免打断微博扫码。"""
    if heimao_on_weibo_login_page(page):
        return False, '请在当前微博页完成扫码'

    if not heimao_browser_has_weibo_session(ctx):
        return False, '未发现微博 SUB，请完成扫码'

    url = (page.url or '').lower()
    if 'tousu.sina.com.cn' not in url:
        try:
            _goto_heimao_check_page(page)
        except Exception:
            pass

    if page_has_login_fail_text(page, 'heimao') or heimao_page_shows_login_prompt(page):
        return False, '尚未登录成功，请继续扫码'

    sid = extract_heimao_sid(page, ctx)
    ac = _auth_cfg('heimao')
    if sid and ac.get('detail_probe_enabled', True) is not False:
        probe = probe_heimao_detail_access(ctx, page, None, sid=sid)
        if probe is True:
            return True, '详情页探测通过，可继续爬取'
        if probe is False:
            return False, '请跳回黑猫首页后再试'

    if sid:
        return True, '已登录且已获取 sid'
    return True, '微博已登录，将继续搜索'


def probe_heimao_detail_access(ctx, page, log_fn=None, sid=None):
    """
    打开一条真实投诉详情探测是否可读。
    返回 True=可读, False=需登录, None=无法探测（回退 Cookie 判断）。
    """
    ac = _auth_cfg('heimao')
    if ac.get('detail_probe_enabled', True) is False:
        return None

    timeout = int(ac.get('check_timeout_ms', 20000))
    probe_url = (ac.get('detail_probe_url') or '').strip()
    wait_sec = float(ac.get('detail_probe_wait_sec', 2))
    sid = (sid or extract_heimao_sid(page, ctx) or '').strip()

    if not probe_url:
        try:
            html = page.content()
            probe_url = find_heimao_detail_href_in_html(html)
            if not probe_url:
                if log_fn:
                    log_fn('[heimao] 首页暂无投诉链接，跳过详情探测', 'WARN')
                return None
        except Exception as e:
            if log_fn:
                log_fn('[heimao] 解析探测链接失败: %s' % str(e)[:60], 'WARN')
            return None

    probe_url = ensure_heimao_detail_url(probe_url, sid)
    if 'complaint/view' in probe_url and sid and 'sid=' not in probe_url:
        if log_fn:
            log_fn('[heimao] 无法为详情链接附加 sid', 'WARN')
        return None

    dp = None
    try:
        js = build_heimao_detail_js()
        dp = ctx.new_page()
        if sid:
            try:
                dp.goto(
                    ac.get('login_check_url') or ac.get('login_url', 'https://tousu.sina.com.cn/'),
                    timeout=timeout,
                    wait_until='domcontentloaded',
                )
            except Exception:
                pass
        dp.goto(probe_url, timeout=timeout, wait_until='domcontentloaded')
        time.sleep(wait_sec)
        detail = dp.evaluate(js.replace('\r', ''))
        if _heimao_detail_has_body(detail):
            if log_fn:
                log_fn('[heimao] 详情探测通过: %s' % probe_url[-40:])
            return True
        if page_has_login_wall(dp, 'heimao') or page_has_login_fail_text(dp, 'heimao'):
            if log_fn:
                log_fn('[heimao] 详情页需登录（探测未通过，url=%s）' % probe_url[-50:], 'WARN')
            return False
        if log_fn:
            log_fn(
                '[heimao] 详情页无正文（非登录墙，跳过探测） sid=%s url=%s' % (
                    '有' if sid else '无',
                    probe_url[-55:],
                ),
                'WARN',
            )
        return None
    except Exception as e:
        if log_fn:
            log_fn('[heimao] 详情探测异常: %s' % str(e)[:80], 'WARN')
        return None
    finally:
        if dp:
            try:
                dp.close()
            except Exception:
                pass


def heimao_is_logged_in_live(ctx, page, navigate=True):
    """以浏览器会话 + 页面是否仍要求登录为准。"""
    ac = _auth_cfg('heimao')
    check_url = ac.get('login_check_url') or ac.get('login_url', '')
    url_now = (page.url or '').lower()
    on_heimao = 'tousu.sina.com.cn' in url_now
    if navigate and check_url and not (on_heimao and 'passport.weibo' not in url_now):
        try:
            page.goto(check_url, timeout=int(ac.get('check_timeout_ms', 20000)), wait_until='domcontentloaded')
            time.sleep(0.5)
        except Exception as e:
            return False, '打开黑猫页失败: %s' % str(e)[:60]

    fail_text, fail_msg = _page_has_login_fail_text(page, 'heimao')
    show_login = heimao_page_shows_login_prompt(page)
    has_sub = heimao_browser_has_weibo_session(ctx)
    if fail_text or show_login:
        return False, '黑猫页面提示需要登录，请微博扫码'

    if not has_sub:
        return False, '浏览器未登录（无有效微博 SUB），请扫码登录'

    return True, '浏览器已登录'


def heimao_ready_for_detail_crawl(ctx, page, runtime, navigate=True, run_probe=True):
    """黑猫爬详情前：浏览器会话 + 页面文案（可选详情探测）。"""
    apply_cookies_to_context(ctx, 'heimao', runtime.log)
    ok, msg = heimao_is_logged_in_live(ctx, page, navigate=navigate)
    if not ok:
        return False, msg

    ac = _auth_cfg('heimao')
    sid = extract_heimao_sid(page, ctx)
    if run_probe and sid and ac.get('detail_probe_enabled', True) is not False:
        probe = probe_heimao_detail_access(ctx, page, runtime.log, sid=sid)
        if probe is False:
            return False, '当前会话无法查看投诉详情，请重新扫码登录'
        if probe is True:
            return True, '详情页探测通过，可爬取详情'

    if sid:
        return True, '已登录且已获取 sid'
    if heimao_browser_has_weibo_session(ctx):
        return True, '微博已登录，将在搜索后获取 sid'
    return False, '未登录，请微博扫码'


def is_heimao_detail_auth_failure(page, detail):
    detail = detail or {}
    has_body = _heimao_detail_has_body(detail)
    if has_body:
        return False
    fail_wall = page_has_login_wall(page, 'heimao')
    fail_text, fail_msg = _page_has_login_fail_text(page, 'heimao')
    has_sub = False
    try:
        has_sub = has_weibo_session(get_context_cookies_for_site(page.context, 'heimao'))
    except Exception:
        pass
    return bool(fail_wall or fail_text or not has_sub)


def is_xhs_detail_auth_failure(page, detail):
    detail = detail or {}
    min_len = int(_auth_cfg('xhs').get('detail_probe_min_content_len', 20))
    content = (detail.get('content') or detail.get('title') or '').strip()
    if len(content) >= min_len:
        return False
    try:
        from xhs_detail import xhs_page_shows_open_in_app
        app_hit, _ = xhs_page_shows_open_in_app(page)
        if app_hit:
            return True
    except Exception:
        pass
    if page_has_login_wall(page, 'xhs') or page_has_login_fail_text(page, 'xhs'):
        return True
    try:
        cookies = get_context_cookies_for_site(page.context, 'xhs')
        if not has_xhs_session(cookies):
            return True
    except Exception:
        return True
    return False


def xhs_count_note_items(page):
    """登录门禁与爬取主循环：仅以 note-item 计数（避免页眉 explore 链接触发误判）。"""
    x = get_config().get('xhs', {})
    sel = x.get('note_item_selector', '.note-item')
    try:
        return len(page.query_selector_all(sel))
    except Exception:
        return 0


def xhs_count_search_items(page):
    """诊断用：在 note-item 为 0 时尝试更宽的选择器。"""
    n = xhs_count_note_items(page)
    if n > 0:
        return n
    x = get_config().get('xhs', {})
    for sel in x.get('search_item_selectors') or (
        'section .note-item',
        'div.feeds-container a[href*="/explore/"]',
    ):
        try:
            n = max(n, len(page.query_selector_all(sel)))
        except Exception:
            pass
    return n


def _xhs_wait_note_items(page, wait_ms=12000):
    x = get_config().get('xhs', {})
    sel = x.get('note_item_selector', '.note-item')
    try:
        page.wait_for_selector(sel, timeout=int(wait_ms), state='attached')
    except Exception:
        pass
    return xhs_count_note_items(page)


def xhs_search_page_needs_login(page, ctx=None):
    """搜索页：登录文案 / 无笔记（含过期 Cookie 空结果）。"""
    if page_has_login_wall(page, 'xhs'):
        return True, '搜索页提示需要登录'
    fail, msg = _page_has_login_fail_text(page, 'xhs')
    if fail:
        return True, msg

    url = (page.url or '').lower()
    on_search = 'search_result' in url
    if not on_search:
        return False, ''

    n = _xhs_wait_note_items(page, int(get_config().get('xhs', {}).get('search_results_wait_ms', 12000)))
    if n > 0:
        return False, ''

    try:
        page.evaluate('window.scrollBy(0, Math.min(1200, document.body.scrollHeight || 1200))')
        time.sleep(2)
    except Exception:
        pass
    n = xhs_count_note_items(page)
    if n > 0:
        return False, ''

    cookies = []
    if ctx is not None:
        try:
            cookies = get_context_cookies_for_site(ctx, 'xhs')
        except Exception:
            pass
    elif getattr(page, 'context', None):
        try:
            cookies = get_context_cookies_for_site(page.context, 'xhs')
        except Exception:
            pass

    if not has_xhs_session(cookies):
        return True, '未登录且搜索页无笔记'
    return True, '搜索页无笔记（会话可能已过期，请重新登录）'


def _xhs_login_ok_after_wait(ctx, page):
    cookies = get_context_cookies_for_site(ctx, 'xhs')
    if not has_xhs_session(cookies):
        return False, '未检测到小红书会话 Cookie'
    if page_has_login_wall(page, 'xhs'):
        return False, '页面仍提示需要登录'
    fail, msg = _page_has_login_fail_text(page, 'xhs')
    if fail:
        return False, msg
    url = (page.url or '').lower()
    if 'search_result' in url:
        needs, reason = xhs_search_page_needs_login(page, ctx)
        if needs:
            return False, reason
    return True, '已登录'


def xhs_check_logged_in_on_search(ctx, page, keyword, runtime):
    """在真实搜索页检测登录（避免 explore 页 + 过期 Cookie 误判）。"""
    apply_cookies_to_context(ctx, 'xhs', runtime.log)
    x = get_config().get('xhs', {})
    ac = _auth_cfg('xhs')
    search_url = x.get('search_url_template', '').format(keyword=keyword)
    if not search_url:
        return check_site_logged_in(ctx, page, 'xhs')
    timeout = int(ac.get('check_timeout_ms', 20000))
    try:
        page.goto(search_url, timeout=timeout, wait_until='domcontentloaded')
        time.sleep(float(x.get('after_goto_wait', 5)))
    except Exception as e:
        return False, '打开搜索页失败: %s' % str(e)[:60]
    _xhs_wait_note_items(page, int(x.get('search_results_wait_ms', 12000)))
    needs, reason = xhs_search_page_needs_login(page, ctx)
    if needs:
        return False, reason
    if not has_xhs_session(get_context_cookies_for_site(ctx, 'xhs')):
        return False, '未检测到小红书会话 Cookie'
    return True, '搜索页可访问'


def xhs_wait_if_search_blocked(ctx, page, runtime, search_url, timeout_ms, after_wait_sec):
    """搜索页出现登录墙时等待登录并重新打开搜索。"""
    needs, reason = xhs_search_page_needs_login(page, ctx)
    if not needs:
        return True
    runtime.log('[xhs] %s，进入等待登录…' % reason, 'WARN')
    if not wait_for_site_login(ctx, page, 'xhs', runtime):
        return False
    runtime.log('[xhs] 登录成功，重新打开搜索页…')
    try:
        page.goto(search_url, timeout=timeout_ms, wait_until='domcontentloaded')
        time.sleep(after_wait_sec)
    except Exception as e:
        runtime.log('[xhs] 重新打开搜索页失败: %s' % str(e)[:60], 'ERROR')
        return False
    needs2, reason2 = xhs_search_page_needs_login(page, ctx)
    if needs2:
        runtime.log('[xhs] 登录后搜索页仍不可用: %s' % reason2, 'WARN')
    return True


def maybe_export_after_login(ctx, site, log_fn):
    if not _auth_cfg(site).get('auto_export_after_login', True):
        return
    try:
        cookies = export_cookies_from_context(ctx, site)
        path = save_site_cookies(site, cookies)
        if log_fn:
            if site == 'heimao':
                sub = has_weibo_session(cookies)
                log_fn('[%s] 登录成功，已保存 %d 条 Cookie（含微博SUB=%s）-> %s' % (
                    site, len(cookies), sub, path,
                ))
            elif site == 'xhs':
                log_fn('[%s] 登录成功，已保存 %d 条 Cookie -> %s' % (site, len(cookies), path))
            else:
                log_fn('[%s] 登录成功，已保存 Cookie -> %s' % (site, path))
    except Exception as e:
        if log_fn:
            log_fn('[%s] 登录后导出 Cookie 失败: %s' % (site, str(e)[:80]), 'WARN')


def wait_for_site_login(ctx, page, site, runtime):
    """
    runtime: 具 running, phase, login_wait, lock 与 log(msg, level='INFO') 的对象（如 crawler_web.S）
    """
    ac = _auth_cfg(site)
    timeout = int(ac.get('wait_timeout_sec', 300))
    interval = float(ac.get('poll_interval_sec', 3))
    label = site_label(site)
    started = time.time()
    baseline_fp = ''
    if site == 'xhs':
        baseline_fp = _xhs_session_fingerprint(get_context_cookies_for_site(ctx, site))

    _set_login_wait_ui(runtime, site, '等待%s登录…' % label)

    if site == 'heimao':
        open_heimao_login_page(page, runtime.log)
        runtime.log('[%s] 请用微博扫码，跳回黑猫首页后将自动继续（勿关闭 Chrome）' % site)
    else:
        login_url = ac.get('login_url') or ac.get('login_check_url', '')
        if login_url:
            try:
                page.goto(login_url, timeout=int(ac.get('check_timeout_ms', 20000)), wait_until='domcontentloaded')
                runtime.log('[%s] 已打开登录页，请在此 Chrome 窗口完成登录' % site)
            except Exception as e:
                runtime.log('[%s] 打开登录页失败: %s（请手动切换 Chrome）' % (site, str(e)[:60]), 'WARN')
        if site == 'xhs':
            runtime.log('[%s] 请在 Chrome 中完成小红书登录，完成后将自动继续' % site)
    runtime.log('[%s] 等待超时 %d 秒；可点「%s：打开登录页」' % (site, timeout, label))

    last_warn = -1
    while runtime.running:
        elapsed = time.time() - started
        with runtime.lock:
            if runtime.login_wait:
                runtime.login_wait['elapsed_sec'] = int(elapsed)
                runtime.login_wait['message'] = '等待%s登录…' % label

        if elapsed >= timeout:
            runtime.log('[%s] 等待登录超时 (%d 秒)，任务中止' % (site, timeout), 'ERROR')
            _clear_login_wait_ui(runtime)
            return False

        if site == 'heimao':
            ok, msg = _heimao_login_ok_after_wait(ctx, page)
        elif site == 'xhs':
            ok, msg = _xhs_login_ok_after_wait(ctx, page)
            cookies = get_context_cookies_for_site(ctx, site)
            fp = _xhs_session_fingerprint(cookies) if has_xhs_session(cookies) else ''
            if not ok and baseline_fp and fp and fp != baseline_fp and has_xhs_session(cookies):
                ok, msg = True, '会话 Cookie 已更新'
        else:
            ok, msg = check_site_logged_in(ctx, page, site, poll_only=True)

        if ok and site == 'xhs':
            kw = getattr(runtime, 'xhs_pending_keyword', None) or ''
            if kw:
                xcfg = get_config().get('xhs', {})
                su = xcfg.get('search_url_template', '').format(keyword=kw)
                if su:
                    try:
                        page.goto(su, timeout=int(ac.get('check_timeout_ms', 20000)), wait_until='domcontentloaded')
                        time.sleep(float(xcfg.get('after_goto_wait', 5)))
                        _xhs_wait_note_items(page, int(xcfg.get('search_results_wait_ms', 12000)))
                        needs_s, reason_s = xhs_search_page_needs_login(page, ctx)
                        if needs_s:
                            ok, msg = False, reason_s
                    except Exception as e:
                        ok, msg = False, '登录后打开搜索页失败: %s' % str(e)[:60]

        if ok:
            runtime.log('[%s] 登录成功: %s' % (site, msg))
            maybe_export_after_login(ctx, site, runtime.log)
            _clear_login_wait_ui(runtime)
            return True

        sec = int(elapsed)
        if sec >= 5 and sec // 15 > last_warn:
            last_warn = sec // 15
            runtime.log('[%s] 仍在等待登录… (%s)' % (site, msg), 'WARN')

        time.sleep(interval)

    _clear_login_wait_ui(runtime)
    return False


def heimao_wait_if_search_empty(ctx, page, html, keyword, runtime, redo_search=None):
    """
    搜索无投诉链接时：无 sid 一律等待登录（忽略可能过期的 SUB）。
    redo_search: 登录成功后的回调 () -> html，用于重新搜索。
    """
    h = get_config().get('heimao', {})
    link_regex = h.get('link_regex', '')
    min_text = int(h.get('min_link_text_len', 15))

    def _count(htm):
        return count_heimao_complaint_links(htm, link_regex, min_text)

    n = _count(html)
    sid = extract_heimao_sid(page, ctx) or ''

    if n > 0:
        return True

    if sid and n == 0:
        runtime.log(
            '[heimao] 搜索「%s」无投诉链接（已有 sid，可能关键词无结果）' % keyword,
            'WARN',
        )
        return True

    runtime.log(
        '[heimao] 搜索无结果且无 sid（会话无效或未登录），进入等待登录…',
        'WARN',
    )
    if not wait_for_site_login(ctx, page, 'heimao', runtime):
        return False

    if callable(redo_search):
        runtime.log('[heimao] 登录成功，重新搜索…')
        html = redo_search() or page.content()
        if _count(html) > 0:
            runtime.log('[heimao] 重新搜索后已发现投诉链接', 'INFO')
            return True
        runtime.log('[heimao] 登录后仍无搜索结果，请检查关键词或页面', 'WARN')
    return True


def ensure_login_for_detail(ctx, page, site, fetch_detail, runtime, search_keyword=None):
    """勾选详情或 require_login 时需登录；仅列表且未勾选 require_login 时不阻塞。"""
    need = bool(fetch_detail) or _auth_cfg(site).get('require_login')
    if not need:
        apply_cookies_to_context(ctx, site, runtime.log)
        return True

    if site == 'heimao' and fetch_detail:
        _set_login_wait_ui(runtime, 'heimao', '正在检测黑猫登录与详情访问…')
        runtime.log('[heimao] 正在检测是否可爬取详情（约数秒）…')
        ready, msg = heimao_ready_for_detail_crawl(ctx, page, runtime)
        if ready:
            _clear_login_wait_ui(runtime)
            runtime.log('[%s] %s' % (site, msg))
            return True
        _clear_login_wait_ui(runtime)
        runtime.log('[%s] 需要登录才能爬取详情: %s' % (site, msg), 'WARN')
        return wait_for_site_login(ctx, page, site, runtime)

    if site == 'xhs' and need and search_keyword:
        ok, msg = xhs_check_logged_in_on_search(ctx, page, search_keyword, runtime)
    elif site == 'xhs' and need:
        ok, msg = check_site_logged_in(ctx, page, 'xhs')
    else:
        ok, msg = check_site_logged_in(ctx, page, site)
    if ok:
        runtime.log('[%s] %s' % (site, msg))
        return True

    runtime.log('[%s] 需要登录才能爬取详情: %s' % (site, msg), 'WARN')
    return wait_for_site_login(ctx, page, site, runtime)
