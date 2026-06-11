# -*- coding: utf-8 -*-
"""黑猫投诉会话 sid：详情页 URL 需携带 sid 查询参数。"""
import re
from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse

from config import get_config
from auth_utils import get_context_cookies_for_site, has_weibo_session


def _sid_from_cookies(cookies):
    for c in cookies or []:
        name = (c.get('name') or '').lower()
        if name == 'sid' and c.get('value'):
            return str(c['value']).strip()
    return ''


def extract_heimao_sid(page, ctx=None):
    """从 Cookie、当前 URL、页面链接或前端变量读取 sid。"""
    sid = ''
    if ctx is not None:
        sid = _sid_from_cookies(get_context_cookies_for_site(ctx, 'heimao'))
    if sid:
        return sid

    try:
        sid = page.evaluate(
            '''() => {
                try {
                    const u = new URL(location.href);
                    const q = u.searchParams.get('sid');
                    if (q) return q;
                } catch (e) {}
                try {
                    const m = document.cookie.match(/(?:^|;\\s*)sid=([^;]+)/i);
                    if (m) return decodeURIComponent(m[1]);
                } catch (e) {}
                const sel = 'a[href*="complaint/view"]';
                for (const a of document.querySelectorAll(sel)) {
                    const h = a.getAttribute('href') || '';
                    const mm = h.match(/[?&]sid=([^&"#]+)/);
                    if (mm) return decodeURIComponent(mm[1]);
                }
                for (const k of ['sid', 'SID', 'heimaoSid', 'heimao_sid']) {
                    try {
                        const v = localStorage.getItem(k) || sessionStorage.getItem(k);
                        if (v) return v;
                    } catch (e) {}
                }
                if (window.__INITIAL_STATE__ && window.__INITIAL_STATE__.sid) {
                    return String(window.__INITIAL_STATE__.sid);
                }
                return '';
            }'''
        ) or ''
    except Exception:
        sid = ''

    sid = str(sid).strip()
    if sid:
        return sid

    try:
        url = page.url or ''
        m = re.search(r'[?&]sid=([^&"#]+)', url)
        if m:
            return m.group(1)
    except Exception:
        pass

    try:
        html = page.content()
        m = re.search(
            r'complaint/view/[^"\'?\s]+[?&]sid=([^&"\'#\s]+)',
            html,
        )
        if m:
            return m.group(1)
        m = re.search(
            r'["\']sid["\']\s*:\s*["\']([a-zA-Z0-9_\-]{6,64})["\']',
            html,
        )
        if m:
            return m.group(1)
        m = re.search(r'(?:\?|&)sid=([a-zA-Z0-9_\-]{6,64})', html)
        if m:
            return m.group(1)
    except Exception:
        pass

    return ''


def heimao_listing_has_sid_in_links(html):
    return bool(re.search(
        r'complaint/view/[^"\'?\s]*[?&]sid=',
        html or '',
        re.I,
    ))


def heimao_browser_has_weibo_session(ctx):
    """浏览器内未过期的微博 SUB/SUBP（不读配置文件）。"""
    import time
    now = time.time()
    for c in get_context_cookies_for_site(ctx, 'heimao'):
        if c.get('name') not in ('SUB', 'SUBP') or not (c.get('value') or '').strip():
            continue
        exp = c.get('expires')
        if exp is not None and exp > 0 and exp < now:
            continue
        return True
    return False


def build_heimao_weibo_login_url(return_url=None):
    """
    黑猫 PC 端实际使用的微博登录地址（来自 tousu 前端 JS，非 passport.weibo.cn/signin）。
    """
    ac = get_config().get('auth', {}).get('heimao', {})
    home = (return_url or ac.get('login_url') or 'https://tousu.sina.com.cn/').strip()
    default = (
        'https://passport.weibo.com/sso/signin?entry=general&source=heimao&url='
        + quote(home, safe='')
    )
    custom = (ac.get('weibo_login_url') or '').strip()
    if not custom:
        return default
    if 'passport.weibo.cn/signin' in custom or 'entry=tousu' in custom:
        return default
    if '{url}' in custom:
        return custom.replace('{url}', quote(home, safe=''))
    return custom


def _weibo_login_page_ok(page):
    try:
        title = (page.title() or '')
        if '404' in title:
            return False
        body = (page.inner_text('body') or '')[:1200]
        if '404 Not Found' in body or 'nginx' in body and '404' in body:
            return False
        if any(k in body for k in ('扫描二维码', '账号密码登录', '短信验证', '验证码登录')):
            return True
    except Exception:
        pass
    url = (page.url or '').lower()
    return 'passport.weibo.com/sso/signin' in url or 'login.sina.com.cn' in url


def _click_heimao_header_login(page, log_fn=None):
    """黑猫顶部「登录」为 javascript:，需模拟点击触发 SSO。"""
    selectors = [
        '.head-login',
        '.head-login a',
        '.header a:has-text("登录")',
        'a:has-text("登录")',
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible(timeout=2000):
                loc.click(timeout=8000)
                page.wait_for_timeout(2500)
                if _weibo_login_page_ok(page) or heimao_on_weibo_login_page(page):
                    return True
        except Exception:
            continue
    try:
        ok = page.evaluate(
            '''() => {
                const nodes = Array.from(document.querySelectorAll('a, span, div, button'));
                for (const el of nodes) {
                    const t = (el.innerText || '').trim();
                    if (t === '登录' || t === '立即登录') {
                        el.click();
                        return true;
                    }
                }
                return false;
            }'''
        )
        if ok:
            page.wait_for_timeout(2500)
            return _weibo_login_page_ok(page) or heimao_on_weibo_login_page(page)
    except Exception as e:
        if log_fn:
            log_fn('[heimao] 触发登录按钮失败: %s' % str(e)[:50], 'WARN')
    return False


def open_heimao_login_page(page, log_fn=None):
    """打开微博扫码登录页（passport.weibo.com，非已下线的 weibo.cn/signin）。"""
    ac = get_config().get('auth', {}).get('heimao', {})
    timeout = int(ac.get('check_timeout_ms', 20000))
    home = ac.get('login_url') or 'https://tousu.sina.com.cn/'
    weibo_login = build_heimao_weibo_login_url(home)

    try:
        page.goto(weibo_login, timeout=timeout, wait_until='domcontentloaded')
        page.wait_for_timeout(1500)
        if _weibo_login_page_ok(page):
            if log_fn:
                log_fn('[heimao] 已打开微博登录页（扫码后自动跳回黑猫）', 'INFO')
            return True
        if log_fn:
            log_fn('[heimao] 直达登录 URL 异常，尝试从黑猫首页点击登录…', 'WARN')
    except Exception as e:
        if log_fn:
            log_fn('[heimao] 打开微博登录页失败: %s，尝试首页登录…' % str(e)[:60], 'WARN')

    try:
        page.goto(home, timeout=timeout, wait_until='domcontentloaded')
        page.wait_for_timeout(1200)
        if _click_heimao_header_login(page, log_fn):
            if log_fn:
                log_fn('[heimao] 已从黑猫首页进入微博登录页', 'INFO')
            return True
    except Exception as e:
        if log_fn:
            log_fn('[heimao] 黑猫首页登录入口失败: %s' % str(e)[:60], 'WARN')

    try:
        page.goto(weibo_login, timeout=timeout, wait_until='domcontentloaded')
        page.wait_for_timeout(1500)
        if _weibo_login_page_ok(page):
            if log_fn:
                log_fn('[heimao] 已打开微博登录页', 'INFO')
            return True
    except Exception as e:
        if log_fn:
            log_fn('[heimao] 打开微博登录页失败: %s' % str(e)[:80], 'ERROR')
    return False


def heimao_on_weibo_login_page(page):
    if _weibo_login_page_ok(page):
        return True
    url = (page.url or '').lower()
    return any(x in url for x in (
        'passport.weibo.com/sso',
        'weibo.com/signin',
        'weibo.com/login',
        'login.sina.com.cn',
    ))


def heimao_page_shows_login_prompt(page):
    """页面上是否明显要求登录（比 Cookie 更可靠）。"""
    try:
        return page.evaluate(
            '''() => {
                const t = (document.body && document.body.innerText) || '';
                if (/请登录|登录后查看|立即登录|微博登录|扫码登录|登录\\/注册|请先登录/.test(t)) {
                    return true;
                }
                const sel = document.querySelector(
                    '.header a[href*="login"], .head-wrap a[href*="login"], a.login, [class*="login-btn"]'
                );
                if (sel) {
                    const r = sel.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0 && /登录/.test(sel.innerText || '')) {
                        return true;
                    }
                }
                return false;
            }'''
        )
    except Exception:
        return False


def count_heimao_complaint_links(html, link_regex, min_text_len=15):
    if not html:
        return 0
    n = 0
    for _href, raw in re.findall(link_regex, html, re.DOTALL):
        text = re.sub(r'<[^>]+>', '', raw or '').strip()
        if len(text) >= min_text_len:
            n += 1
    return n




def ensure_heimao_detail_url(url, sid):
    """为投诉详情 URL 补上 sid 查询参数。"""
    if not url:
        return url
    sid = (sid or '').strip()
    if not sid:
        return url

    if url.startswith('//'):
        url = 'https:' + url
    elif url.startswith('/'):
        url = 'https://tousu.sina.com.cn' + url

    parsed = urlparse(url)
    if 'complaint/view' not in parsed.path:
        return url

    qs = parse_qs(parsed.query, keep_blank_values=True)
    if qs.get('sid') and (qs['sid'][0] or '').strip():
        return url

    qs['sid'] = [sid]
    new_query = urlencode(qs, doseq=True)
    return urlunparse((
        parsed.scheme or 'https',
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment,
    ))


def find_heimao_detail_href_in_html(html):
    """优先取已带 sid 的详情链接。"""
    if not html:
        return ''
    m = re.search(
        r'href="([^"]*tousu\.sina\.com\.cn/complaint/view/[^"]*sid=[^"]+)"',
        html,
        re.I,
    )
    if m:
        return m.group(1)
    m = re.search(
        r'href="([^"]*tousu\.sina\.com\.cn/complaint/view/[^"]+)"',
        html,
        re.I,
    )
    return m.group(1) if m else ''
