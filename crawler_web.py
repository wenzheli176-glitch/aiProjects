#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舆情爬虫 v9 - 新标签页详情提取 + 精确正文提取（配置化）
"""
from __future__ import print_function
import sys, os, time, json, random, re, threading, subprocess, socket
from urllib.parse import parse_qs, urlparse
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from flask import Flask, jsonify, request, send_file, send_from_directory, redirect
from patchright.sync_api import sync_playwright
from admin_auth import register_admin_routes, require_admin
from config import get_config, save_config, cfg, build_heimao_detail_js, load_config
from auth_utils import (
    apply_cookies_to_context,
    diagnose_login,
    export_cookies_from_context,
    has_weibo_session,
    has_xhs_session,
    load_site_cookies,
    save_site_cookies,
    parse_cookies_text,
)
from login_gate import (
    ensure_login_for_detail,
    heimao_wait_if_search_empty,
    is_heimao_detail_auth_failure,
    is_xhs_detail_auth_failure,
    wait_for_site_login,
    xhs_wait_if_search_blocked,
)
from xhs_detail import fetch_xhs_detail_via_modal
from heimao_session import (
    count_heimao_complaint_links,
    ensure_heimao_detail_url,
    extract_heimao_sid,
    heimao_listing_has_sid_in_links,
    open_heimao_login_page,
)
from reports import (
    structure_heimao_record,
    structure_heimao_list,
    build_heimao_report_html,
    build_heimao_report_csv_rows,
)

app = Flask(__name__, template_folder='templates', static_folder='static')

class S:
    browser = None; pw = None; ctx = None; browser_launched = False
    running = False; running_type = ''
    phase = ''
    login_wait = None
    heimao_sid = ''
    xhs_pending_keyword = ''
    results_heimao = []; results_xhs = []
    logs = []; lock = threading.Lock()

def _c():
    return get_config()

def log(msg, level='INFO'):
    ts = time.strftime('%H:%M:%S')
    max_logs = int(cfg('logging', 'max_logs', default=300))
    with S.lock:
        S.logs.append({'time': ts, 'level': level, 'msg': msg})
        if len(S.logs) > max_logs:
            S.logs = S.logs[-max_logs:]
    print('[%s][%s] %s' % (ts, level, msg))

S.log = log

def ensure_chrome():
    c = _c()['chrome']
    cdp_url = c['cdp_url']
    cdp_port = int(c['cdp_port'])
    profile_dir = c['profile_dir_resolved']
    timeout = float(c.get('cdp_check_timeout', 3))
    http_timeout = float(c.get('cdp_http_timeout', 2))

    try:
        import urllib.request
        req = urllib.request.Request(cdp_url + '/json/version', headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=timeout)
        if resp.status == 200:
            S.browser_launched = True
            return True
    except Exception:
        pass

    if c.get('kill_all_chrome_before_start', False):
        kill_name = c.get('kill_process_name', 'chrome.exe')
        try:
            os.system('taskkill /F /IM %s >nul 2>&1' % kill_name)
            time.sleep(float(c.get('kill_wait_seconds', 3)))
            log('已结束已有 Chrome 进程以便使用专用配置启动')
        except Exception:
            pass

    for f in ['SingletonLock', 'SingletonCookie', 'SingletonSocket']:
        try:
            os.remove(os.path.join(profile_dir, f))
        except Exception:
            pass

    log('启动Chrome (CDP port %d)...' % cdp_port)
    cmd = [
        c['exe_path'],
        '--remote-debugging-port=%d' % cdp_port,
        '--user-data-dir=' + profile_dir,
    ] + list(c.get('extra_args', [])) + [c.get('startup_url', 'https://tousu.sina.com.cn/')]
    log('Chrome路径: ' + c['exe_path'])
    try:
        subprocess.Popen(cmd, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    except Exception as e:
        log('Chrome启动失败: ' + str(e), 'ERROR')
        return False

    wait_sec = int(c.get('startup_wait_seconds', 30))
    for i in range(wait_sec):
        time.sleep(1)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            if s.connect_ex(('127.0.0.1', cdp_port)) == 0:
                s.close()
                try:
                    urllib.request.urlopen(cdp_url + '/json/version', timeout=http_timeout)
                    S.browser_launched = True
                    log('Chrome已启动! CDP 就绪')
                    time.sleep(float(c.get('ready_extra_wait_seconds', 2)))
                    return True
                except Exception:
                    pass
            s.close()
        except Exception:
            pass
        log('等待Chrome启动... (%d/%d)' % (i + 1, wait_sec))
    log('Chrome启动失败! CDP端口%d未就绪' % cdp_port, 'ERROR')
    return False

def connect_cdp():
    cdp_url = _c()['chrome']['cdp_url']
    if S.pw is None:
        S.pw = sync_playwright().start()
    if S.browser is None:
        S.browser = S.pw.chromium.connect_over_cdp(cdp_url)
        S.ctx = S.browser.contexts[0]
    return S.ctx

def close_cdp(shutdown_browser=False, force=False):
    """断开 Playwright。CDP 模式下默认不关闭用户 Chrome，避免扫码登录态丢失。"""
    if S.running and not shutdown_browser and not force:
        return
    try:
        if S.browser:
            if shutdown_browser:
                try:
                    S.browser.close()
                except Exception:
                    pass
            S.browser = None
            S.ctx = None
        if S.pw:
            S.pw.stop()
            S.pw = None
    except Exception:
        pass


def _cdp_http_ready():
    c = _c()['chrome']
    try:
        import urllib.request
        req = urllib.request.Request(
            c['cdp_url'] + '/json/version',
            headers={'User-Agent': 'Mozilla/5.0'},
        )
        resp = urllib.request.urlopen(req, timeout=float(c.get('cdp_http_timeout', 2)))
        return resp.status == 200
    except Exception:
        return False


def _cdp_port_open():
    cdp_port = int(_c()['chrome']['cdp_port'])
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        ok = s.connect_ex(('127.0.0.1', cdp_port)) == 0
        s.close()
        return ok
    except Exception:
        return False


def _reset_playwright_session():
    try:
        if S.browser:
            S.browser = None
            S.ctx = None
        if S.pw:
            S.pw.stop()
            S.pw = None
    except Exception:
        pass


def prepare_browser_for_crawl():
    """爬取前确保 CDP 可用；监测任务长跑后优先复用/重连，失败再重启 Chrome。"""
    if S.browser is not None:
        try:
            if _cdp_http_ready():
                _ = S.browser.contexts
                return True
        except Exception:
            pass
        log('Playwright 连接已失效，正在重连 CDP…', 'WARN')
        _reset_playwright_session()

    if _cdp_http_ready():
        S.browser_launched = True
        return True

    if not _cdp_port_open():
        log('CDP 端口未就绪，正在自动启动 Chrome…')

    if ensure_chrome():
        return True

    if S.running:
        log('Chrome 首次启动失败，尝试强制重置浏览器会话后重试…', 'WARN')
        close_cdp(shutdown_browser=True, force=True)
        _reset_playwright_session()
        if ensure_chrome():
            return True
    return False

def crawl_heimao(keyword, max_pages, fetch_detail=True, managed_session=False):
    h = _c()['heimao']
    if not managed_session:
        S.running = True
        S.running_type = 'heimao'
    log('开始爬取黑猫投诉: %s %d页 详情=%s' % (keyword, max_pages, fetch_detail))
    results = []
    seen = set()
    timeout = int(h.get('page_timeout_ms', 30000))
    js_detail = build_heimao_detail_js()

    try:
        if not prepare_browser_for_crawl():
            log('Chrome 未就绪，爬取已取消', 'ERROR')
            return results
        ctx = connect_cdp()
        main_page = ctx.pages[0] if ctx.pages else ctx.new_page()
        if not ensure_login_for_detail(ctx, main_page, 'heimao', fetch_detail, S):
            log('黑猫登录未完成，爬取已取消', 'ERROR')
            return results

        main_page.goto(h['base_url'], timeout=timeout, wait_until='domcontentloaded')
        time.sleep(float(h.get('after_goto_wait', 2)))
        S.heimao_sid = extract_heimao_sid(main_page, ctx) or S.heimao_sid
        if fetch_detail and not S.heimao_sid:
            log('[heimao] 未获取到 sid，搜索后将尝试从结果页链接读取', 'WARN')
        sb = main_page.query_selector(h['search_input_selector'])
        if not sb:
            log('找不到搜索框!', 'ERROR')
            if not managed_session:
                S.running = False
            return results
        sb.click()
        time.sleep(0.3)
        sb.fill('')
        time.sleep(0.2)
        sb.type(keyword, delay=random.randint(
            int(h.get('typing_delay_min', 80)),
            int(h.get('typing_delay_max', 150)),
        ))
        time.sleep(0.5)
        sb.press('Enter')
        time.sleep(float(h.get('after_search_wait', 5)))
        if fetch_detail:
            sid_new = extract_heimao_sid(main_page, ctx)
            if sid_new:
                S.heimao_sid = sid_new

        def _redo_heimao_search():
            main_page.goto(h['base_url'], timeout=timeout, wait_until='domcontentloaded')
            time.sleep(float(h.get('after_goto_wait', 2)))
            box = main_page.query_selector(h['search_input_selector'])
            if not box:
                return ''
            box.click()
            time.sleep(0.3)
            box.fill('')
            box.type(keyword, delay=random.randint(
                int(h.get('typing_delay_min', 80)),
                int(h.get('typing_delay_max', 150)),
            ))
            time.sleep(0.5)
            box.press('Enter')
            time.sleep(float(h.get('after_search_wait', 5)))
            sid_new = extract_heimao_sid(main_page, ctx)
            if sid_new:
                S.heimao_sid = sid_new
            return main_page.content()

        first_html = main_page.content()
        if not heimao_wait_if_search_empty(
            ctx, main_page, first_html, keyword, S, redo_search=_redo_heimao_search,
        ):
            log('黑猫登录未完成，爬取已取消', 'ERROR')
            return results
        if count_heimao_complaint_links(
            first_html, h['link_regex'], int(h.get('min_link_text_len', 15)),
        ) == 0:
            first_html = _redo_heimao_search() or first_html

        for p in range(1, max_pages + 1):
            if not S.running:
                log('已停止', 'WARN')
                break
            log('黑猫第 %d/%d 页' % (p, max_pages))
            try:
                if p > 1:
                    url = h['search_url_template'].format(keyword=keyword, page=p)
                    main_page.goto(url, timeout=timeout, wait_until='domcontentloaded')
                    time.sleep(random.uniform(
                        float(h.get('page_wait_min', 3)),
                        float(h.get('page_wait_max', 5)),
                    ))

                html = main_page.content()
                if len(html) < int(h.get('min_html_len', 1000)):
                    log('页面过短', 'WARN')
                    continue

                if fetch_detail:
                    sid_new = extract_heimao_sid(main_page, ctx)
                    if sid_new:
                        S.heimao_sid = sid_new
                    elif heimao_listing_has_sid_in_links(html):
                        for href, _raw in re.findall(h['link_regex'], html, re.DOTALL):
                            u = href
                            if u.startswith('//'):
                                u = 'https:' + u
                            elif u.startswith('/'):
                                u = 'https://tousu.sina.com.cn' + u
                            qs = parse_qs(urlparse(u).query)
                            if qs.get('sid') and qs['sid'][0]:
                                S.heimao_sid = qs['sid'][0]
                                break

                a_tags = re.findall(h['link_regex'], html, re.DOTALL)
                new_count = 0
                min_text = int(h.get('min_link_text_len', 15))
                preview_len = int(h.get('list_title_preview_len', 40))

                for href, raw_text in a_tags:
                    if href in seen:
                        continue
                    seen.add(href)
                    text = re.sub(r'<[^>]+>', '', raw_text).strip()
                    if len(text) < min_text:
                        continue

                    r = parse_heimao_link(text, href)
                    r['page'] = p
                    if fetch_detail and r.get('link') and not S.heimao_sid:
                        u = r['link']
                        qs = parse_qs(urlparse(u).query)
                        if qs.get('sid') and qs['sid'][0]:
                            S.heimao_sid = qs['sid'][0]

                    if fetch_detail and r.get('link'):
                        sid = S.heimao_sid or extract_heimao_sid(main_page, ctx)
                        detail_link = ensure_heimao_detail_url(r['link'], sid)
                        if 'complaint/view' in detail_link and sid and 'sid=' not in detail_link:
                            log('  跳过详情: 无法附加 sid', 'WARN')
                            continue
                        if sid and 'sid=' in detail_link:
                            S.heimao_sid = sid
                        try:
                            log('  详情: %s' % detail_link[-36:])
                            detail_page = ctx.new_page()
                            detail_page.goto(detail_link, timeout=timeout, wait_until='domcontentloaded')
                            time.sleep(random.uniform(
                                float(h.get('detail_wait_min', 5)),
                                float(h.get('detail_wait_max', 8)),
                            ))
                            detail = detail_page.evaluate(js_detail.replace(chr(13), ''))
                            if is_heimao_detail_auth_failure(detail_page, detail):
                                detail_page.close()
                                log('  详情页未登录或内容为空，等待登录后重试…', 'WARN')
                                if not wait_for_site_login(ctx, main_page, 'heimao', S):
                                    S.running = False
                                    break
                                detail_page = ctx.new_page()
                                sid = S.heimao_sid or extract_heimao_sid(main_page, ctx)
                                detail_link = ensure_heimao_detail_url(r['link'], sid)
                                detail_page.goto(detail_link, timeout=timeout, wait_until='domcontentloaded')
                                time.sleep(random.uniform(
                                    float(h.get('detail_wait_min', 5)),
                                    float(h.get('detail_wait_max', 8)),
                                ))
                                detail = detail_page.evaluate(js_detail.replace(chr(13), ''))
                            for k in ['title', 'content', 'demand', 'merchant', 'problem', 'amount', 'reply', 'author', 'time', 'status', 'comments']:
                                if detail.get(k):
                                    r[k] = detail[k]
                            log('  -> %s' % (
                                r['title'][:preview_len]
                                if r.get('title') and len(r['title']) > 5
                                else r.get('problem') or r.get('merchant')
                            ))
                            detail_page.close()
                        except Exception as e:
                            log('  详情错误: %s' % str(e)[:60], 'ERROR')
                            try:
                                for pg in ctx.pages:
                                    if pg != main_page:
                                        pg.close()
                            except Exception:
                                pass

                    sr = structure_heimao_record(r, len(results) + 1)
                    r['structured'] = sr
                    results.append(r)
                    new_count += 1
                    if not fetch_detail:
                        log('黑猫: %s %s' % (
                            r['time'][:10] if r.get('time') else '',
                            (r.get('title') or '')[:preview_len],
                        ))

                log('本页: %d (累计: %d)' % (new_count, len(results)))
                if new_count == 0 and p > 1:
                    break
            except Exception as e:
                log('页面错误: %s' % str(e)[:100], 'ERROR')
                time.sleep(3)
                continue
            time.sleep(random.uniform(
                float(h.get('between_pages_min', 3)),
                float(h.get('between_pages_max', 6)),
            ))

        with S.lock:
            if not managed_session:
                S.results_heimao = results
        log('黑猫完成! %d 条' % len(results))
    except Exception as e:
        log('异常: %s' % str(e)[:100], 'ERROR')
    finally:
        if not managed_session:
            S.running = False
            S.running_type = ''
            with S.lock:
                S.phase = ''
                S.login_wait = None
                S.heimao_sid = ''
            close_cdp()
    return results

def parse_heimao_link(text, href):
    h = _c()['heimao']
    title_max = int(h.get('title_max_len', 100))
    r = {
        'title': '', 'time': '', 'content': '', 'demand': '', 'merchant': '', 'author': '',
        'status': '', 'problem': '', 'amount': '', 'reply': '', 'comments': '', 'link': '',
        'source': h.get('source_name', '黑猫投诉'),
    }
    href = href or ''
    if href.startswith('//'):
        href = 'https:' + href
    elif href.startswith('/'):
        href = 'https://tousu.sina.com.cn' + href
    r['link'] = href
    m = re.search(r'(\d{4}-\d{2}-\d{2})', text)
    if m:
        r['time'] = m.group(1)
    strip_pat = r'\s*%s\s*' % re.escape(h.get('parse_strip_text', '于黑猫投诉平台发起'))
    tc = re.sub(strip_pat, ' ', text).strip()
    parts = tc.split()
    if len(parts) >= 3:
        r['content'] = ' '.join(parts[3:])
    elif len(parts) >= 2:
        r['content'] = ' '.join(parts[1:])
    dm = re.search(h.get('parse_demand_pattern', r'\[投诉要求\]([^\[]+)'), text)
    if dm:
        r['demand'] = dm.group(1).strip()
    r['title'] = r['content'][:title_max]
    return r

def crawl_xhs(keyword, max_pages, fetch_detail=True, managed_session=False):
    x = _c()['xhs']
    if not managed_session:
        S.running = True
        S.running_type = 'xhs'
    S.xhs_pending_keyword = keyword
    log('开始爬取小红书: %s %d页' % (keyword, max_pages))
    results = []
    seen = set()
    timeout = int(x.get('page_timeout_ms', 30000))
    title_max = int(x.get('title_max_len', 100))
    preview_len = int(x.get('title_preview_len', 40))

    try:
        if not prepare_browser_for_crawl():
            log('Chrome 未就绪，爬取已取消', 'ERROR')
            return results
        ctx = connect_cdp()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        if not ensure_login_for_detail(ctx, page, 'xhs', fetch_detail, S, search_keyword=keyword):
            log('小红书登录未完成，爬取已取消', 'ERROR')
            return results

        search_url = x['search_url_template'].format(keyword=keyword)
        after_wait = float(x.get('after_goto_wait', 5))
        if 'search_result' not in (page.url or ''):
            page.goto(search_url, timeout=timeout, wait_until='domcontentloaded')
            time.sleep(after_wait)
        if not xhs_wait_if_search_blocked(ctx, page, S, search_url, timeout, after_wait):
            log('小红书登录未完成，爬取已取消', 'ERROR')
            return results

        for p in range(1, max_pages + 1):
            if not S.running:
                log('已停止', 'WARN')
                break
            log('XHS第 %d/%d 页' % (p, max_pages))
            try:
                for _ in range(int(x.get('scroll_times_per_page', 3))):
                    page.evaluate('window.scrollBy(0, %d)' % int(x.get('scroll_pixels', 1500)))
                    time.sleep(float(x.get('scroll_wait_seconds', 2)))

                items = page.query_selector_all(x['note_item_selector'])
                log('找到 %d 个note-item' % len(items))

                for item in items:
                    try:
                        le = item.query_selector(x['link_selector'])
                        if not le:
                            continue
                        link = le.get_attribute('href') or ''
                        host = x.get('link_host', 'https://www.xiaohongshu.com')
                        if link and not link.startswith('http'):
                            link = host + link
                        if not link or link in seen:
                            continue
                        seen.add(link)

                        def _text(sel):
                            el = item.query_selector(sel)
                            return el.inner_text().strip() if el else ''

                        r = {
                            'title': _text(x['title_selector'])[:title_max],
                            'content': _text(x['text_selector']),
                            'time': _text(x['time_selector']),
                            'author': _text(x['author_selector']),
                            'likes': _text(x['likes_selector']),
                            'collects': '',
                            'comments': '',
                            'tags': '',
                            'link': link,
                            'page': p,
                            'source': x.get('source_name', '小红书'),
                        }

                        if fetch_detail and link:
                            try:
                                log('  XHS详情(弹窗): %s' % link[-28:])
                                detail, err = fetch_xhs_detail_via_modal(page, item, link, log)
                                if err and is_xhs_detail_auth_failure(page, detail or {}):
                                    log('  详情未登录或内容为空，等待登录后重试…', 'WARN')
                                    if not wait_for_site_login(ctx, page, 'xhs', S):
                                        S.running = False
                                        break
                                    detail, err = fetch_xhs_detail_via_modal(page, item, link, log)
                                if err:
                                    log('  详情: %s' % err[:80], 'WARN')
                                for k in ['title', 'content', 'author', 'time', 'likes', 'collects', 'comments', 'tags']:
                                    if detail.get(k):
                                        r[k] = detail[k]
                                if r.get('title'):
                                    r['title'] = r['title'][:title_max]
                            except Exception as e:
                                log('  XHS详情错误: %s' % str(e)[:60], 'ERROR')

                        if r['title'] or r['content']:
                            results.append(r)
                            log('XHS: %s' % (
                                r['title'][:preview_len] if r['title'] else r['content'][:preview_len]
                            ))
                    except Exception:
                        pass

                log('累计: %d' % len(results))
            except Exception as e:
                log('错误: %s' % str(e)[:100], 'ERROR')
                time.sleep(3)
                continue
            time.sleep(random.uniform(
                float(x.get('between_pages_min', 5)),
                float(x.get('between_pages_max', 10)),
            ))

        with S.lock:
            if not managed_session:
                S.results_xhs = results
        log('小红书完成! %d 条' % len(results))
    except Exception as e:
        log('异常: %s' % str(e)[:100], 'ERROR')
    finally:
        if not managed_session:
            S.running = False
            S.running_type = ''
            S.xhs_pending_keyword = ''
            with S.lock:
                S.phase = ''
                S.login_wait = None
            close_cdp()
    return results

@app.route('/')
def index_page():
    return send_from_directory('templates', 'app.html')

@app.route('/dashboard')
def dashboard_page():
    return redirect('/?tab=home', code=302)

@app.route('/legacy/crawl')
def legacy_crawl_page():
    return redirect('/?tab=crawl', code=302)

@app.route('/api/config', methods=['GET'])
def api_config_get():
    c = get_config()
    plain = json.loads(json.dumps(c, ensure_ascii=False))
    plain['chrome'].pop('profile_dir_resolved', None)
    plain['chrome'].pop('cdp_url', None)
    plain['paths'].pop('output_dir_resolved', None)
    if isinstance(plain.get('database'), dict):
        plain['database'].pop('path_resolved', None)
    ac = plain.get('analysis')
    if isinstance(ac, dict) and ac.get('api_key'):
        ac['api_key'] = '***已配置***'
    return jsonify(plain)

@app.route('/api/config', methods=['POST'])
@require_admin
def api_config_post():
    if S.running:
        return jsonify({'ok': False, 'msg': '爬取进行中，请先停止再保存配置'})
    data = request.get_json() or {}
    save_config(data)
    load_config(force=True)
    log('配置已保存')
    return jsonify({'ok': True})

@app.route('/api/status')
def api_status():
    log_count = int(cfg('logging', 'status_log_count', default=30))
    with S.lock:
        payload = {
            'browser_launched': S.browser_launched,
            'running': S.running,
            'running_type': S.running_type,
            'phase': S.phase or '',
            'login_wait': dict(S.login_wait) if S.login_wait else None,
            'count_heimao': len(S.results_heimao),
            'count_xhs': len(S.results_xhs),
            'logs': S.logs[-log_count:],
        }
    return jsonify(payload)

@app.route('/api/logs')
def api_logs():
    return jsonify(S.logs)

@app.route('/api/launch', methods=['POST'])
def api_launch():
    threading.Thread(target=lambda: (log('启动Chrome...'), ensure_chrome())).start()
    return jsonify({'ok': True})

@app.route('/api/crawl_heimao', methods=['POST'])
def api_crawl_heimao():
    if S.running:
        return jsonify({'ok': False, 'msg': '进行中'})
    h = _c()['heimao']
    d = request.get_json() or {}
    threading.Thread(
        target=crawl_heimao,
        args=(
            d.get('keyword', h.get('default_keyword', '小米')),
            int(d.get('max_pages', h.get('default_max_pages', 2))),
            d.get('fetch_detail', h.get('default_fetch_detail', True)),
        ),
    ).start()
    return jsonify({'ok': True})

@app.route('/api/crawl_xhs', methods=['POST'])
def api_crawl_xhs():
    if S.running:
        return jsonify({'ok': False, 'msg': '进行中'})
    x = _c()['xhs']
    d = request.get_json() or {}
    threading.Thread(
        target=crawl_xhs,
        args=(
            d.get('keyword', x.get('default_keyword', '小米')),
            int(d.get('max_pages', x.get('default_max_pages', 3))),
            d.get('fetch_detail', x.get('default_fetch_detail', True)),
        ),
    ).start()
    return jsonify({'ok': True})

@app.route('/api/stop', methods=['POST'])
def api_stop():
    S.running = False
    log('停止')
    return jsonify({'ok': True})

@app.route('/api/results_heimao')
def api_results_heimao():
    return jsonify(S.results_heimao)

@app.route('/api/results_xhs')
def api_results_xhs():
    return jsonify(S.results_xhs)

@app.route('/api/export_heimao')
def api_export_heimao():
    with S.lock:
        data = list(S.results_heimao)
    return _export(data, 'heimao')

@app.route('/api/export_xhs')
def api_export_xhs():
    with S.lock:
        data = list(S.results_xhs)
    return _export(data, 'xhs')

@app.route('/api/export_all')
def api_export_all():
    with S.lock:
        data = list(S.results_heimao) + list(S.results_xhs)
    return _export(data, 'all')

def _export(data, name):
    ex = _c()['export']
    output_dir = _c()['paths']['output_dir_resolved']
    fmt = request.args.get('format', 'txt')
    ts = time.strftime('%Y%m%d_%H%M%S')
    content_max = int(ex.get('content_max_len', 500))
    reply_max = int(ex.get('reply_max_len', 300))

    if fmt == 'json':
        path = os.path.join(output_dir, '%s_%s.json' % (name, ts))
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    elif fmt == 'csv':
        path = os.path.join(output_dir, '%s_%s.csv' % (name, ts))
        with open(path, 'w', encoding='utf-8-sig') as f:
            f.write(ex.get('csv_header', '') + '\n')
            for i, r in enumerate(data, 1):
                f.write('%d,"%s","%s","%s","%s",%s,"%s","%s","%s","%s",%s\n' % (
                    i, (r.get('title') or '').replace('"', '""'),
                    (r.get('merchant') or '').replace('"', '""'),
                    (r.get('problem') or '').replace('"', '""'),
                    (r.get('amount') or '').replace('"', '""'),
                    r.get('time', ''), r.get('status', ''),
                    (r.get('demand') or '').replace('"', '""'),
                    (r.get('content') or '').replace('"', '""')[:content_max],
                    (r.get('reply') or '').replace('"', '""')[:reply_max],
                    r.get('link', '')))
    else:
        path = os.path.join(output_dir, '%s_%s.txt' % (name, ts))
        txt_fields = ex.get('txt_fields', [])
        with open(path, 'w', encoding='utf-8') as f:
            f.write('舆情爬取详细结果 | %s | 共%d条\n%s\n' % (
                time.strftime('%Y-%m-%d %H:%M'), len(data), '=' * 60))
            for i, r in enumerate(data, 1):
                f.write('\n【%d】[%s] %s\n' % (i, r.get('source', ''), r.get('title', '')))
                for k in txt_fields:
                    v = r.get(k, '')
                    if v:
                        f.write('%s: %s\n' % (k, v))
                if r.get('likes'):
                    f.write('点赞: %s\n' % r['likes'])
                if r.get('comments'):
                    f.write('评论数: %s\n' % r['comments'])
                if r.get('link'):
                    f.write('链接: %s\n' % r['link'])
                f.write('\n' + '-' * 40 + '\n')
    return send_file(path, as_attachment=True)

@app.route('/api/auth/status')
def api_auth_status():
    out = {}
    for site in ('heimao', 'xhs'):
        ac = _c().get('auth', {}).get(site, {})
        cookies = load_site_cookies(site)
        out[site] = {
            'cookie_count': len(cookies),
            'cookies_file': ac.get('cookies_file', ''),
            'use_profile_only': ac.get('use_profile_only', False),
            'has_weibo_sub': has_weibo_session(cookies) if site == 'heimao' else None,
            'has_xhs_session': has_xhs_session(cookies) if site == 'xhs' else None,
        }
    return jsonify(out)


@app.route('/api/auth/diagnose', methods=['POST'])
def api_auth_diagnose():
    site = (request.get_json() or {}).get('site', 'heimao')
    if site not in ('heimao', 'xhs'):
        return jsonify({'ok': False, 'msg': '无效站点'})

    def _run():
        if not prepare_browser_for_crawl():
            log('Chrome 未就绪，无法诊断', 'ERROR')
            return
        try:
            ctx = connect_cdp()
            info = diagnose_login(ctx, site)
            for h in info.get('hints', []):
                log('[%s] %s' % (site, h), 'WARN' if not info.get('has_sub_in_browser') else 'INFO')
            if site == 'heimao':
                log('[%s] 诊断: 浏览器Cookie=%d 配置Cookie=%d 浏览器SUB=%s 配置SUB=%s' % (
                    site,
                    info.get('browser_cookie_count', 0),
                    info.get('config_cookie_count', 0),
                    info.get('has_sub_in_browser'),
                    info.get('has_sub_in_config'),
                ))
        except Exception as e:
            log('登录诊断失败: %s' % str(e)[:80], 'ERROR')
        finally:
            close_cdp(shutdown_browser=False)

    threading.Thread(target=_run).start()
    return jsonify({'ok': True})


@app.route('/api/auth/open_login', methods=['POST'])
def api_auth_open_login():
    site = (request.get_json() or {}).get('site', 'heimao')
    if site not in ('heimao', 'xhs'):
        return jsonify({'ok': False, 'msg': '无效站点'})
    url = _c().get('auth', {}).get(site, {}).get('login_url', '')

    def _run():
        if not prepare_browser_for_crawl():
            return
        try:
            ctx = connect_cdp()
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            if site == 'heimao':
                open_heimao_login_page(page, log)
                log('[%s] 扫码后跳回黑猫首页，可点「导出 Cookie」' % site)
            else:
                page.goto(url, timeout=30000, wait_until='domcontentloaded')
                log('[%s] 请在 Chrome 中完成登录，然后点击「导出 Cookie」' % site)
        except Exception as e:
            log('打开登录页失败: %s' % str(e)[:80], 'ERROR')

    threading.Thread(target=_run).start()
    return jsonify({'ok': True, 'url': url})


@app.route('/api/auth/export', methods=['POST'])
def api_auth_export():
    site = (request.get_json() or {}).get('site', 'heimao')
    if site not in ('heimao', 'xhs'):
        return jsonify({'ok': False, 'msg': '无效站点'})

    def _run():
        if not prepare_browser_for_crawl():
            return
        try:
            ctx = connect_cdp()
            cookies = export_cookies_from_context(ctx, site)
            path = save_site_cookies(site, cookies)
            if site == 'heimao':
                if has_weibo_session(cookies):
                    log('[%s] 已导出 %d 条 Cookie（含微博 SUB）-> %s' % (site, len(cookies), path))
                else:
                    log(
                        '[%s] 已导出 %d 条 Cookie，但未发现微博 SUB/SUBP！请确认扫码后已跳回黑猫再导出' % (
                            site, len(cookies),
                        ),
                        'WARN',
                    )
            else:
                log('[%s] 已导出 %d 条 Cookie -> %s' % (site, len(cookies), path))
        except Exception as e:
            log('导出 Cookie 失败: %s' % str(e)[:80], 'ERROR')
        finally:
            close_cdp(shutdown_browser=False)

    threading.Thread(target=_run).start()
    return jsonify({'ok': True})


@app.route('/api/auth/save', methods=['POST'])
@require_admin
def api_auth_save():
    if S.running:
        return jsonify({'ok': False, 'msg': '爬取进行中'})
    d = request.get_json() or {}
    site = d.get('site', 'heimao')
    if site not in ('heimao', 'xhs'):
        return jsonify({'ok': False, 'msg': '无效站点'})
    try:
        text = d.get('cookies_text', '')
        cookies = parse_cookies_text(text) if text.strip() else []
        if not cookies and isinstance(d.get('cookies'), list):
            cookies = d.get('cookies')
        if not cookies:
            return jsonify({'ok': False, 'msg': 'Cookie 为空'})
        path = save_site_cookies(site, cookies)
        cfg_updates = {'auth': {site: {'cookies_text': text}}}
        if isinstance(d.get('cookies_file'), str) and d.get('cookies_file'):
            cfg_updates['auth'][site]['cookies_file'] = d['cookies_file']
        save_config(cfg_updates)
        load_config(force=True)
        log('[%s] 已保存 %d 条 Cookie' % (site, len(cookies)))
        return jsonify({'ok': True, 'path': path, 'count': len(cookies)})
    except Exception as e:
        return jsonify({'ok': False, 'msg': str(e)[:120]})


@app.route('/api/report/heimao')
def api_report_heimao():
    with S.lock:
        data = list(S.results_heimao)
    if not data:
        return jsonify({'ok': False, 'msg': '暂无黑猫数据'})
    fmt = request.args.get('format', 'html')
    ts = time.strftime('%Y%m%d_%H%M%S')
    output_dir = _c()['paths']['output_dir_resolved']

    if fmt == 'json':
        structured = structure_heimao_list(data)
        path = os.path.join(output_dir, 'heimao_report_%s.json' % ts)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(structured, f, ensure_ascii=False, indent=2)
        return send_file(path, as_attachment=True)

    if fmt == 'csv':
        structured, rows = build_heimao_report_csv_rows(data)
        path = os.path.join(output_dir, 'heimao_report_%s.csv' % ts)
        with open(path, 'w', encoding='utf-8-sig') as f:
            for row in rows:
                f.write(','.join('"%s"' % str(c).replace('"', '""') for c in row) + '\n')
        return send_file(path, as_attachment=True)

    html_doc = build_heimao_report_html(data)
    path = os.path.join(output_dir, 'heimao_report_%s.html' % ts)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html_doc)
    if request.args.get('download') == '1':
        return send_file(path, as_attachment=True)
    return html_doc, 200, {'Content-Type': 'text/html; charset=utf-8'}


@app.route('/api/results_heimao/structured')
def api_results_heimao_structured():
    with S.lock:
        data = structure_heimao_list(S.results_heimao)
    return jsonify(data)


@app.route('/docs/credentials')
def docs_credentials():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'docs', '如何获取登录凭证.md')
    if os.path.isfile(path):
        return send_file(path, mimetype='text/markdown; charset=utf-8')
    return '文档不存在', 404


@app.route('/docs/intel-api')
def docs_intel_api():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'docs', 'API对接说明.md')
    if os.path.isfile(path):
        return send_file(path, mimetype='text/markdown; charset=utf-8')
    return '文档不存在', 404


@app.route('/api/clear', methods=['POST'])
def api_clear():
    with S.lock:
        S.results_heimao = []
        S.results_xhs = []
        S.logs = []
    return jsonify({'ok': True})

from intel.db import get_connection
from intel.api import register_intel_routes

get_connection()
register_intel_routes(app)
register_admin_routes(app)

if __name__ == '__main__':
    load_config()
    srv = _c()['server']
    print('\n' + '=' * 50 + '\n  舆情爬虫 v9 (配置化)\n' + '=' * 50 + '\n')
    app.run(host=srv.get('host', '0.0.0.0'), port=int(srv.get('port', 5000)), debug=False)
