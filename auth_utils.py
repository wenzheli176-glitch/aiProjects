# -*- coding: utf-8 -*-
"""站点 Cookie 凭证加载、注入与导出。"""
import json
import os
import re

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


def apply_cookies_to_context(ctx, site, log_fn=None):
    ac = _auth_cfg(site)
    if ac.get('use_profile_only'):
        if log_fn:
            log_fn('[%s] 使用 Chrome 用户目录登录态，跳过 Cookie 注入' % site)
        return 0
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
