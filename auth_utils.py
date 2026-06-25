# -*- coding: utf-8 -*-
"""站点 Cookie 凭证加载、注入与导出。"""
import json
import os
import re
import time

from config import BASE_DIR, get_config

REQUIRED_COOKIE_FIELDS = ('name', 'value', 'domain')


def _auth_cfg(site):
    return get_config().get('auth', {}).get(site, {})


def _resolve_cookies_file(path):
    if not path:
        return ''
    if os.path.isabs(path):
        return path
    return os.path.join(BASE_DIR, path)


def normalize_cookie(c):
    if not isinstance(c, dict) or not c.get('name'):
        return None
    out = {
        'name': str(c['name']),
        'value': str(c.get('value', '')),
        'domain': str(c.get('domain', '')),
        'path': c.get('path') or '/',
    }
    if c.get('expires') is not None:
        out['expires'] = c['expires']
    if c.get('httpOnly') is not None:
        out['httpOnly'] = bool(c['httpOnly'])
    if c.get('secure') is not None:
        out['secure'] = bool(c['secure'])
    if c.get('sameSite') is not None:
        out['sameSite'] = c['sameSite']
    return out


def parse_cookies_text(text):
    """支持 Playwright JSON 数组，或 name=value 每行（需配合 domain 在配置中）。"""
    text = (text or '').strip()
    if not text:
        return []
    if text.startswith('['):
        raw = json.loads(text)
        if not isinstance(raw, list):
            raise ValueError('Cookie JSON 须为数组')
        out = []
        for item in raw:
            c = normalize_cookie(item)
            if c:
                out.append(c)
        return out
    domain = ''
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.lower().startswith('domain:'):
            domain = line.split(':', 1)[1].strip()
            continue
        if '=' not in line:
            continue
        name, value = line.split('=', 1)
        out.append(normalize_cookie({'name': name.strip(), 'value': value.strip(), 'domain': domain, 'path': '/'}))
    return out


def load_site_cookies(site):
    ac = _auth_cfg(site)
    cookies = []
    inline = ac.get('cookies') or []
    if isinstance(inline, list):
        for item in inline:
            c = normalize_cookie(item)
            if c:
                cookies.append(c)
    text = (ac.get('cookies_text') or '').strip()
    if text:
        cookies.extend(parse_cookies_text(text))
    path = _resolve_cookies_file(ac.get('cookies_file', ''))
    if path and os.path.isfile(path):
        with open(path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        if isinstance(raw, list):
            for item in raw:
                c = normalize_cookie(item)
                if c:
                    cookies.append(c)
    default_domain = ac.get('domain', '')
    seen = set()
    deduped = []
    for c in cookies:
        if not c.get('domain') and default_domain:
            c['domain'] = default_domain
        if not c.get('domain'):
            continue
        key = (c['name'], c['domain'], c['path'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    return deduped


def save_site_cookies(site, cookies):
    ac = _auth_cfg(site)
    path = _resolve_cookies_file(ac.get('cookies_file', ''))
    if not path:
        path = os.path.join(BASE_DIR, 'credentials', '%s_cookies.json' % site)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    return path


def load_cookies_from_file(path, site=None):
    path = _resolve_cookies_file(path)
    if not path or not os.path.isfile(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    if not isinstance(raw, list):
        return []
    default_domain = ''
    if site:
        default_domain = _auth_cfg(site).get('domain', '')
    out = []
    for item in raw:
        c = normalize_cookie(item)
        if not c:
            continue
        if not c.get('domain') and default_domain:
            c['domain'] = default_domain
        if c.get('domain'):
            out.append(c)
    return out


def source_startup_url(site):
    """按数据源返回 Chrome 启动/导航 URL（避免 xhs Worker 误开黑猫首页）。"""
    ac = _auth_cfg(site) if site else {}
    if site == 'xhs':
        return ac.get('login_url') or 'https://www.xiaohongshu.com/'
    if site == 'heimao':
        from config import cfg
        return ac.get('login_url') or cfg('chrome', 'startup_url') or 'https://tousu.sina.com.cn/'
    from config import cfg
    return cfg('chrome', 'startup_url') or 'https://tousu.sina.com.cn/'


def _pool_xhs_cookies_file():
    """Worker 账号池当前绑定的 Cookie 文件（绝对路径）。"""
    try:
        from crawler_web import S
        raw = getattr(S, 'xhs_pool_cookies_file', None) or ''
    except Exception:
        raw = ''
    if not raw:
        return ''
    if os.path.isabs(raw):
        return raw if os.path.isfile(raw) else ''
    resolved = os.path.join(BASE_DIR, raw)
    return resolved if os.path.isfile(resolved) else ''


def _page_is_usable(page):
    if page is None:
        return False
    try:
        if page.is_closed():
            return False
        _ = page.url
        return True
    except Exception:
        return False


def get_active_page(ctx, site=None, log_fn=None):
    """取可用标签页；若用户关闭了所有页则复用/新建并尽量打开站点首页。"""
    if not ctx:
        return None
    for page in ctx.pages:
        if _page_is_usable(page):
            return page
    page = ctx.new_page()
    url = source_startup_url(site) if site else ''
    if url:
        timeout = int(_auth_cfg(site).get('page_timeout_ms') or 45000) if site else 45000
        try:
            if log_fn:
                log_fn('[%s] 重新打开 %s' % (site, url))
            page.goto(url, wait_until='domcontentloaded', timeout=timeout)
        except Exception as e:
            if log_fn:
                log_fn('[%s] 打开页面失败: %s' % (site or 'browser', str(e)[:80]), 'WARN')
    return page


def close_extra_pages(ctx, keep_page=None):
    """关闭多余空白/详情标签，避免用户手动关页后反复弹出空白页。"""
    if not ctx:
        return
    keep = keep_page
    for page in list(ctx.pages):
        if keep is not None and page is keep:
            continue
        if not _page_is_usable(page):
            continue
        try:
            page.close()
        except Exception:
            pass


def ensure_site_page(ctx, site, log_fn=None):
    """确保浏览器当前在目标站点（Cookie 注入与登录诊断前）。"""
    if not ctx:
        return None
    url = source_startup_url(site)
    markers = {'xhs': 'xiaohongshu.com', 'heimao': 'sina.com.cn'}
    marker = markers.get(site) or ''
    page = get_active_page(ctx, site=site, log_fn=log_fn)
    try:
        cur = page.url or ''
    except Exception:
        cur = ''
    if marker and marker in cur:
        return page
    timeout = int(_auth_cfg(site).get('page_timeout_ms') or _auth_cfg(site).get('check_timeout_ms') or 45000)
    if log_fn:
        log_fn('[%s] 打开 %s' % (site, url))
    page.goto(url, wait_until='domcontentloaded', timeout=timeout)
    return page


def apply_cookies_from_file(ctx, site, cookies_file, log_fn=None):
    cookies = load_cookies_from_file(cookies_file, site=site)
    if not cookies:
        if log_fn:
            log_fn('[%s] Cookie 文件为空或不存在: %s' % (site, cookies_file), 'WARN')
        return 0
    try:
        ctx.add_cookies(cookies)
    except Exception as e:
        if log_fn:
            log_fn('[%s] Cookie 注入失败: %s' % (site, str(e)[:80]), 'WARN')
        return 0
    if log_fn:
        log_fn('[%s] 已从文件注入 %d 条 Cookie' % (site, len(cookies)))
    return len(cookies)


def apply_cookies_to_context(ctx, site, log_fn=None):
    ac = _auth_cfg(site)
    if ac.get('use_profile_only'):
        if log_fn:
            log_fn('[%s] 使用 Chrome 用户目录登录态，跳过 Cookie 注入' % site)
        return 0

    pool_xhs = _pool_xhs_cookies_file() if site == 'xhs' else ''
    if site == 'xhs' and pool_xhs:
        browser_cookies = get_context_cookies_for_site(ctx, 'xhs')
        if has_xhs_session(browser_cookies):
            if log_fn:
                log_fn('[xhs] 浏览器已有账号池会话，跳过默认 Cookie 覆盖')
            return 0
        return apply_cookies_from_file(ctx, 'xhs', pool_xhs, log_fn=log_fn)

    if site == 'heimao' and ac.get('skip_inject_if_browser_logged_out', True):
        browser_cookies = get_context_cookies_for_site(ctx, 'heimao')
        file_cookies = load_site_cookies(site)
        if file_cookies and has_weibo_session(file_cookies) and not has_weibo_session(browser_cookies):
            if log_fn:
                log_fn(
                    '[%s] 浏览器未登录，已跳过注入配置文件中的过期 Cookie（避免误判已登录）' % site,
                    'WARN',
                )
            return 0
    if site == 'xhs' and ac.get('skip_inject_if_browser_logged_out', True):
        browser_cookies = get_context_cookies_for_site(ctx, 'xhs')
        file_cookies = load_site_cookies(site)
        if file_cookies and has_xhs_session(file_cookies) and not has_xhs_session(browser_cookies):
            if log_fn:
                log_fn(
                    '[%s] 浏览器未登录，已跳过注入配置文件中的过期 Cookie（避免误判已登录）' % site,
                    'WARN',
                )
            return 0
    cookies = load_site_cookies(site)
    if not cookies:
        if log_fn:
            log_fn('[%s] 未配置 Cookie，将依赖 Chrome 用户目录中的登录态' % site, 'WARN')
        return 0
    if site == 'heimao' and not has_weibo_session(cookies):
        if log_fn:
            log_fn(
                '[%s] 配置的 Cookie 缺少微博 SUB/SUBP，注入后可能无法登录。请重新导出 Cookie' % site,
                'WARN',
            )
    try:
        ctx.add_cookies(cookies)
        if log_fn:
            log_fn('[%s] 已注入 %d 条 Cookie（含微博=%s）' % (
                site, len(cookies), '是' if has_weibo_session(cookies) else '否',
            ))
        return len(cookies)
    except Exception as e:
        if log_fn:
            log_fn('[%s] Cookie 注入失败: %s' % (site, str(e)[:80]), 'ERROR')
        return 0


def _cookie_matches_domains(cookie, domains):
    if not domains:
        return True
    cd = (cookie.get('domain') or '').lstrip('.').lower()
    for d in domains:
        dd = str(d).lstrip('.').lower()
        if not dd:
            continue
        if cd == dd or cd.endswith('.' + dd) or dd in cd:
            return True
    return False


def export_cookies_from_context(ctx, site):
    """导出登录相关 Cookie。黑猫经微博 SSO，必须包含 weibo / passport 域名。"""
    ac = _auth_cfg(site)
    urls = ac.get('cookie_export_urls') or [ac.get('login_url', '')]
    urls = [u for u in urls if u]
    cookies = ctx.cookies(urls) if urls else ctx.cookies()
    domains = ac.get('cookie_export_domains') or []
    if not domains and site == 'heimao':
        domains = ['.sina.com.cn', '.weibo.com', '.weibo.cn', '.passport.weibo.com', '.passport.weibo.cn']
    if domains:
        filtered = [c for c in cookies if _cookie_matches_domains(c, domains)]
        if filtered:
            cookies = filtered
    seen = set()
    out = []
    for c in cookies:
        key = (c.get('name'), c.get('domain'), c.get('path'))
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def has_weibo_session(cookies):
    for c in cookies:
        if c.get('name') in ('SUB', 'SUBP') and c.get('value'):
            return True
    return False


def get_context_cookies_for_site(ctx, site):
    """从 CDP 上下文读取站点相关 Cookie（含微博等 SSO 域名）。"""
    ac = _auth_cfg(site)
    urls = list(ac.get('cookie_export_urls') or [])
    if not urls:
        for key in ('login_check_url', 'login_url'):
            u = ac.get(key, '')
            if u and u not in urls:
                urls.append(u)
    if site == 'heimao':
        for u in ('https://weibo.com/', 'https://passport.weibo.cn/', 'https://passport.weibo.com/'):
            if u not in urls:
                urls.append(u)
    urls = [u for u in urls if u]
    try:
        return ctx.cookies(urls) if urls else ctx.cookies()
    except Exception:
        return []


def has_xhs_session(cookies):
    ac = _auth_cfg('xhs')
    names = ac.get('required_cookie_names') or ['web_session', 'webId']
    found = set()
    for c in cookies:
        if c.get('name') in names and c.get('value'):
            found.add(c.get('name'))
    return len(found) >= min(2, len(names)) if names else bool(found)


def page_has_login_wall(page, site):
    ac = _auth_cfg(site)
    try:
        body = page.inner_text('body')[:8000]
    except Exception:
        body = ''
    for t in ac.get('login_fail_texts') or []:
        if t and t in body:
            return True
    return False


def xhs_page_logged_in(page):
    """页面元素判断小红书是否已登录（profile 登录时 Cookie API 可能读不到 web_session）。"""
    if page is None:
        return False
    if page_has_login_wall(page, 'xhs'):
        return False
    sel = (_auth_cfg('xhs').get('login_ok_selector') or '').strip()
    if not sel:
        return False
    try:
        return bool(page.query_selector(sel))
    except Exception:
        return False


def xhs_session_ok(ctx, log_fn=None, cookies_file=None):
    """
    判断 xhs 是否可用：优先页面元素 / 浏览器 Cookie，其次 Cookie 文件注入。
    返回 (ok, info_dict)。
    """
    if not ctx:
        return False, {'error': 'no_context'}
    ac = _auth_cfg('xhs')
    check_url = ac.get('login_check_url') or ac.get('login_url') or source_startup_url('xhs')
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    timeout = int(ac.get('page_timeout_ms') or ac.get('check_timeout_ms') or 45000)
    try:
        cur = page.url or ''
    except Exception:
        cur = ''
    if 'xiaohongshu.com' not in cur:
        if log_fn:
            log_fn('[xhs] 打开 %s' % check_url)
        page.goto(check_url, wait_until='domcontentloaded', timeout=timeout)
        time.sleep(float(ac.get('after_goto_wait', 2) or 2))

    browser_cookies = get_context_cookies_for_site(ctx, 'xhs')
    if has_xhs_session(browser_cookies):
        return True, {
            'login_source': 'browser_cookies',
            'browser_cookie_count': len(browser_cookies),
        }
    if xhs_page_logged_in(page):
        return True, {'login_source': 'page_selector'}

    resolved = ''
    if cookies_file:
        resolved = cookies_file if os.path.isabs(cookies_file) else os.path.join(BASE_DIR, cookies_file)
    if resolved and os.path.isfile(resolved):
        file_cookies = load_cookies_from_file(resolved, site='xhs')
        if has_xhs_session(file_cookies):
            apply_cookies_from_file(ctx, 'xhs', resolved, log_fn=log_fn)
            try:
                page.goto(check_url, wait_until='domcontentloaded', timeout=timeout)
                time.sleep(float(ac.get('after_goto_wait', 2) or 2))
            except Exception:
                pass
            browser_cookies = get_context_cookies_for_site(ctx, 'xhs')
            if has_xhs_session(browser_cookies):
                return True, {'login_source': 'cookies_file'}
            if xhs_page_logged_in(page):
                return True, {'login_source': 'cookies_file+page'}

    return False, {
        'error': 'not_logged_in',
        'browser_cookie_count': len(browser_cookies),
        'has_login_wall': page_has_login_wall(page, 'xhs'),
        'page_url': (page.url or '')[:120],
    }


def switch_xhs_account(ctx, cookies_file, log_fn=None):
    """Worker 账号轮换：清空上下文 Cookie 后注入指定账号文件，不重启 Chrome。"""
    if not ctx:
        return False, {'error': 'no_context'}
    resolved = cookies_file if os.path.isabs(cookies_file or '') else os.path.join(BASE_DIR, cookies_file or '')
    if not resolved or not os.path.isfile(resolved):
        return False, {'error': 'cookies_file_missing'}
    file_cookies = load_cookies_from_file(resolved, site='xhs')
    if not has_xhs_session(file_cookies):
        return False, {'error': 'cookies_file_invalid'}

    try:
        ctx.clear_cookies()
    except Exception as e:
        if log_fn:
            log_fn('[xhs] 清空 Cookie 失败: %s' % str(e)[:80], 'WARN')

    n = apply_cookies_from_file(ctx, 'xhs', resolved, log_fn=log_fn)
    if n <= 0:
        return False, {'error': 'cookie_inject_failed'}

    ac = _auth_cfg('xhs')
    check_url = ac.get('login_check_url') or ac.get('login_url') or source_startup_url('xhs')
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    timeout = int(ac.get('page_timeout_ms') or ac.get('check_timeout_ms') or 45000)
    try:
        page.goto(check_url, wait_until='domcontentloaded', timeout=timeout)
        time.sleep(float(ac.get('after_goto_wait', 2) or 2))
    except Exception as e:
        return False, {'error': 'goto_failed', 'detail': str(e)[:120]}

    browser_cookies = get_context_cookies_for_site(ctx, 'xhs')
    if has_xhs_session(browser_cookies):
        return True, {'login_source': 'cookie_switch'}
    if xhs_page_logged_in(page):
        return True, {'login_source': 'cookie_switch+page'}
    return False, {
        'error': 'not_logged_in',
        'has_login_wall': page_has_login_wall(page, 'xhs'),
        'page_url': (page.url or '')[:120],
    }


def diagnose_login(ctx, site):
    """返回登录诊断信息，便于排查微博扫码后仍无效的问题。"""
    ac = _auth_cfg(site)
    urls = ac.get('cookie_export_urls') or [ac.get('login_url', '')]
    urls = [u for u in urls if u]
    try:
        all_cookies = ctx.cookies(urls) if urls else ctx.cookies()
    except Exception as e:
        return {'ok': False, 'error': str(e)[:120]}

    names = {}
    for c in all_cookies:
        d = c.get('domain', '')
        names.setdefault(d, []).append(c.get('name', ''))

    loaded = load_site_cookies(site)
    info = {
        'ok': True,
        'site': site,
        'browser_cookie_count': len(all_cookies),
        'config_cookie_count': len(loaded),
        'has_sub_in_browser': has_weibo_session(all_cookies),
        'has_sub_in_config': has_weibo_session(loaded),
        'domains_in_browser': {k: len(v) for k, v in names.items()},
        'use_profile_only': ac.get('use_profile_only', False),
        'hints': [],
    }

    if site == 'heimao':
        if not info['has_sub_in_browser']:
            info['hints'].append(
                '浏览器中未发现微博 SUB/SUBP Cookie。扫码后请等待跳回黑猫首页，再点「导出 Cookie」。'
            )
        if info['has_sub_in_browser'] and not info['has_sub_in_config']:
            info['hints'].append(
                '浏览器已登录但配置文件无微博 Cookie。请立即点击「导出 Cookie」并保存配置。'
            )
        if info['config_cookie_count'] and not info['has_sub_in_config']:
            info['hints'].append(
                '已保存的 Cookie 可能只有 sina 域名、缺少 weibo 域名（旧版导出逻辑会导致此问题）。请重新导出。'
            )
    if site == 'xhs':
        info['has_xhs_in_browser'] = has_xhs_session(all_cookies)
        info['has_xhs_in_config'] = has_xhs_session(loaded)
        if not info['has_xhs_in_browser']:
            info['hints'].append('浏览器中未发现 web_session/webId，请在 Chrome 完成登录后再导出或等待自动续跑。')
    return info


def page_has_login_fail_text(page, site):
    """页面是否出现未登录类文案。"""
    return _page_has_login_fail_text(page, site)[0]


def _page_has_login_fail_text(page, site):
    ac = _auth_cfg(site)
    fail_texts = ac.get('login_fail_texts') or []
    try:
        body = page.inner_text('body')[:8000]
    except Exception:
        body = ''
    for t in fail_texts:
        if t and t in body:
            return True, '页面包含未登录提示: %s' % t
    return False, ''


def check_login_on_page(page, site, poll_only=False):
    """
    poll_only=True：等待登录轮询时使用，不跳转页面（避免打断扫码），仅查全域名 Cookie。
    poll_only=False：任务开始前完整检测，会打开检测页并校验页面文案。
    """
    ac = _auth_cfg(site)
    timeout = int(ac.get('check_timeout_ms', 15000))
    check_url = ac.get('login_check_url') or ac.get('login_url', '')
    ctx = page.context
    ctx_cookies = get_context_cookies_for_site(ctx, site)

    if poll_only:
        if site == 'heimao':
            if has_weibo_session(ctx_cookies):
                return True, '已检测到微博登录 Cookie (SUB/SUBP)'
            return False, '未发现微博 SUB/SUBP（请在 Chrome 完成微博扫码并跳回黑猫）'
        if site == 'xhs':
            if has_xhs_session(ctx_cookies):
                return True, '已检测到小红书会话 Cookie'
            return False, '未检测到小红书登录 Cookie (web_session/webId)'
        return has_weibo_session(ctx_cookies), '轮询检测'

    if not check_url:
        return True, '未配置登录检测 URL'
    try:
        page.goto(check_url, timeout=timeout, wait_until='domcontentloaded')
    except Exception as e:
        return False, '打开检测页失败: %s' % str(e)[:60]

    ctx_cookies = get_context_cookies_for_site(ctx, site)
    has_fail, fail_msg = _page_has_login_fail_text(page, site)
    if has_fail:
        return False, fail_msg

    if site == 'heimao':
        if has_weibo_session(ctx_cookies):
            return True, '已检测到微博登录 Cookie (SUB/SUBP)'
        sel = ac.get('login_ok_selector', '')
        if sel:
            try:
                if page.query_selector(sel):
                    return False, '页面有搜索框但未发现微博 SUB Cookie（请扫码登录）'
            except Exception:
                pass
        return False, '未检测到微博 SUB/SUBP，扫码后请确认已跳回黑猫首页'

    sel = ac.get('login_ok_selector', '')
    if sel:
        try:
            if page.query_selector(sel):
                if site == 'xhs' and not has_xhs_session(ctx_cookies):
                    return False, '页面已打开但未发现小红书会话 Cookie'
                return True, '已检测到登录成功元素'
        except Exception:
            pass

    required = ac.get('required_cookie_names') or []
    if required:
        names = set(c.get('name', '') for c in ctx_cookies)
        missing = [n for n in required if n not in names]
        if missing:
            return False, '缺少关键 Cookie: %s' % ','.join(missing)

    if site == 'xhs':
        if has_xhs_session(ctx_cookies):
            return True, '已检测到小红书会话 Cookie'
        return False, '未检测到小红书登录 Cookie (web_session/webId)'

    return True, '未触发未登录检测（建议仍导出 Cookie 备份）'


def extract_complaint_id(link):
    if not link:
        return ''
    m = re.search(r'/complaint/view/([^/?#]+)', link)
    return m.group(1) if m else ''
