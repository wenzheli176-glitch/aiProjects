# -*- coding: utf-8 -*-
"""小红书登录账号池：文件索引、迁移、round-robin、登录会话。"""
import json
import os
import re
import shutil
import threading
import time
from datetime import datetime, timezone

from config import load_config, save_config
import config as _config


def _base_dir():
    return _config.BASE_DIR


_ACCOUNTS_DIR = os.path.join(_base_dir(), 'credentials', 'xhs')
_ACCOUNTS_FILE = os.path.join(_ACCOUNTS_DIR, 'accounts.json')
_LEGACY_COOKIE = os.path.join(_base_dir(), 'credentials', 'xhs_cookies.json')
_LEGACY_PROFILE = os.path.join(_base_dir(), 'chrome_profiles', 'xhs_0')
_PROFILE_ROOT = os.path.join(_base_dir(), 'chrome_profiles', 'xhs')

_lock = threading.Lock()
_login_sessions = {}


def _utc_now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _parse_utc_iso(value):
    t = str(value or '').strip()
    if not t:
        return None
    if t.endswith('Z'):
        t = t[:-1] + '+00:00'
    try:
        dt = datetime.fromisoformat(t)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def pool_config():
    block = _config.cfg('monitor', 'xhs_credential_pool') or {}
    return {
        'min_accounts': int(block.get('min_accounts') or 2),
        'login_cdp_port_base': int(block.get('login_cdp_port_base') or 9250),
        'login_wait_timeout_sec': int(block.get('login_wait_timeout_sec') or 600),
    }


def _rel_path(abs_path):
    try:
        return os.path.relpath(abs_path, _base_dir()).replace('\\', '/')
    except Exception:
        return abs_path


def resolve_pool_path(path):
    if not path:
        return ''
    if os.path.isabs(path):
        return os.path.realpath(path)
    return os.path.realpath(os.path.join(_base_dir(), path))


def validate_xhs_pool_path(path, kind='cookies'):
    """kind: cookies | profile"""
    if not path or '..' in str(path).replace('\\', '/'):
        return False, '非法路径'
    resolved = resolve_pool_path(path)
    base = os.path.realpath(_base_dir())
    if not resolved.startswith(base):
        return False, '路径越界'
    rel = os.path.relpath(resolved, base).replace('\\', '/')
    if kind == 'cookies':
        if not rel.startswith('credentials/xhs/'):
            return False, 'Cookie 须位于 credentials/xhs/'
    elif kind == 'profile':
        if not rel.startswith('chrome_profiles/xhs/'):
            return False, 'Profile 须位于 chrome_profiles/xhs/'
    return True, resolved


def _default_accounts_doc():
    return {
        'version': 1,
        'accounts': [],
        'rotation': {
            'policy': 'round_robin_per_keyword',
            'cursor': 0,
        },
    }


def ensure_migrated_acc_default():
    """旧 xhs_cookies.json → acc-default（仅当 accounts.json 不存在）。"""
    os.makedirs(_ACCOUNTS_DIR, exist_ok=True)
    os.makedirs(_PROFILE_ROOT, exist_ok=True)
    if os.path.isfile(_ACCOUNTS_FILE):
        return False
    if not os.path.isfile(_LEGACY_COOKIE):
        doc = _default_accounts_doc()
        with open(_ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        return False

    dest_cookie = os.path.join(_ACCOUNTS_DIR, 'acc_default_cookies.json')
    dest_profile = os.path.join(_PROFILE_ROOT, 'acc_default')
    shutil.copy2(_LEGACY_COOKIE, dest_cookie)
    if os.path.isdir(_LEGACY_PROFILE):
        if not os.path.isdir(dest_profile):
            shutil.copytree(_LEGACY_PROFILE, dest_profile)
    else:
        os.makedirs(dest_profile, exist_ok=True)

    doc = _default_accounts_doc()
    doc['accounts'] = [{
        'id': 'acc-default',
        'label': '默认账号（自旧配置迁移）',
        'cookies_file': _rel_path(dest_cookie),
        'user_data_dir': _rel_path(dest_profile),
        'enabled': True,
        'cooldown_until': None,
        'ban_note': '',
        'migrated_from': 'legacy',
        'created_at': _utc_now_iso(),
        'last_used_at': None,
    }]
    with open(_ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    _sync_auth_to_default()
    return True


def load_accounts():
    with _lock:
        ensure_migrated_acc_default()
        if not os.path.isfile(_ACCOUNTS_FILE):
            return _default_accounts_doc()
        try:
            with open(_ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else _default_accounts_doc()
        except Exception:
            return _default_accounts_doc()


def save_accounts(data):
    os.makedirs(_ACCOUNTS_DIR, exist_ok=True)
    with open(_ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data or _default_accounts_doc(), f, ensure_ascii=False, indent=2)


def list_accounts(enriched=True):
    data = load_accounts()
    out = []
    for acc in data.get('accounts') or []:
        item = dict(acc)
        if enriched:
            cf = resolve_pool_path(item.get('cookies_file') or '')
            exists = bool(cf and os.path.isfile(cf))
            item['cookies_file_exists'] = exists
            item['cookie_count'] = 0
            if exists:
                from auth_utils import load_cookies_from_file
                item['cookie_count'] = len(load_cookies_from_file(cf, site='xhs'))
            item['last_diagnose'] = _load_diagnose_cache(item.get('id'))
        out.append(item)
    enabled = [a for a in out if a.get('enabled', True) and not _is_cooled(a)]
    return {
        'accounts': out,
        'enabled_count': len(enabled),
        'min_accounts': pool_config()['min_accounts'],
        'below_min': len(enabled) < pool_config()['min_accounts'],
        'rotation': data.get('rotation') or {},
    }


def get_account(account_id):
    for acc in load_accounts().get('accounts') or []:
        if acc.get('id') == account_id:
            return dict(acc)
    return None


def _is_cooled(acc):
    cu = acc.get('cooldown_until')
    if not cu:
        return False
    dt = _parse_utc_iso(cu)
    if not dt:
        return False
    return datetime.now(timezone.utc) < dt


def eligible_accounts(data=None):
    if data is None:
        data = load_accounts()
    out = []
    for acc in data.get('accounts') or []:
        if not acc.get('enabled', True):
            continue
        if _is_cooled(acc):
            continue
        out.append(acc)
    return out


def _next_account_id():
    data = load_accounts()
    used = {a.get('id') for a in data.get('accounts') or []}
    n = 2
    while True:
        aid = 'acc-%02d' % n
        if aid not in used and aid != 'acc-default':
            return aid
        n += 1


def create_account(label, enabled=True):
    label = (label or '').strip() or '新账号'
    aid = _next_account_id()
    cookie_rel = 'credentials/xhs/%s_cookies.json' % aid.replace('-', '_')
    profile_rel = 'chrome_profiles/xhs/%s' % aid.replace('-', '_')
    cookie_abs = resolve_pool_path(cookie_rel)
    profile_abs = resolve_pool_path(profile_rel)
    os.makedirs(os.path.dirname(cookie_abs), exist_ok=True)
    os.makedirs(profile_abs, exist_ok=True)
    if not os.path.isfile(cookie_abs):
        with open(cookie_abs, 'w', encoding='utf-8') as f:
            json.dump([], f)
    data = load_accounts()
    acc = {
        'id': aid,
        'label': label,
        'cookies_file': cookie_rel,
        'user_data_dir': profile_rel,
        'enabled': bool(enabled),
        'cooldown_until': None,
        'ban_note': '',
        'created_at': _utc_now_iso(),
        'last_used_at': None,
    }
    data.setdefault('accounts', []).append(acc)
    save_accounts(data)
    return acc


def update_account(account_id, **fields):
    allowed = {'label', 'enabled', 'cooldown_until', 'ban_note'}
    data = load_accounts()
    found = None
    for acc in data.get('accounts') or []:
        if acc.get('id') == account_id:
            for k, v in fields.items():
                if k in allowed:
                    acc[k] = v
            found = dict(acc)
            break
    if not found:
        raise ValueError('账号不存在')
    save_accounts(data)
    if account_id == 'acc-default':
        _sync_auth_to_default()
    return found


def delete_account(account_id):
    if account_id == 'acc-default':
        raise ValueError('默认账号不可删除，可禁用')
    data = load_accounts()
    before = len(data.get('accounts') or [])
    data['accounts'] = [a for a in (data.get('accounts') or []) if a.get('id') != account_id]
    if len(data['accounts']) == before:
        raise ValueError('账号不存在')
    save_accounts(data)


def _touch_last_used(account_id):
    data = load_accounts()
    for acc in data.get('accounts') or []:
        if acc.get('id') == account_id:
            acc['last_used_at'] = _utc_now_iso()
            break
    save_accounts(data)


def _advance_cursor(eligible_count, picked_index):
    data = load_accounts()
    rot = data.setdefault('rotation', {})
    rot['cursor'] = (picked_index + 1) % max(1, eligible_count)
    save_accounts(data)


def diagnose_account_on_ctx(ctx, account, log_fn=None):
    from auth_utils import xhs_session_ok

    cookies_file = resolve_pool_path(account.get('cookies_file') or '')
    ok_path, resolved = validate_xhs_pool_path(account.get('cookies_file'), 'cookies')
    if not ok_path or not os.path.isfile(resolved):
        return False, {'error': 'cookies_missing', 'account_id': account.get('id')}
    ok, info = xhs_session_ok(ctx, log_fn=log_fn, cookies_file=resolved)
    info['account_id'] = account.get('id')
    if not ok and log_fn:
        log_fn('[xhs-pool] 账号 %s 诊断失败: %s' % (account.get('id'), info), 'WARN')
    return ok, info


def pick_account_for_keyword(diagnose_fn=None, log_fn=None):
    """Round-robin 选取账号；diagnose_fn(account) -> bool，失败则跳过。"""
    data = load_accounts()
    eligible = eligible_accounts(data)
    if not eligible:
        return None
    cursor = int((data.get('rotation') or {}).get('cursor') or 0) % len(eligible)
    for attempt in range(len(eligible)):
        idx = (cursor + attempt) % len(eligible)
        acc = eligible[idx]
        if diagnose_fn is None or diagnose_fn(acc):
            _advance_cursor(len(eligible), idx)
            _touch_last_used(acc['id'])
            return acc
        if log_fn:
            log_fn('[xhs-pool] 跳过账号 %s（诊断未通过）' % (acc.get('label') or acc.get('id')), 'WARN')
    return None


def _diagnose_cache_path():
    return os.path.join(_ACCOUNTS_DIR, '.account_diagnose_cache.json')


def _load_diagnose_cache(account_id):
    path = _diagnose_cache_path()
    if not os.path.isfile(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get(account_id)
    except Exception:
        return None


def _store_diagnose_cache(account_id, result):
    path = _diagnose_cache_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {}
    if os.path.isfile(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f) or {}
        except Exception:
            data = {}
    data[account_id] = result
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_account_cookies(account_id, cookies_text):
    acc = get_account(account_id)
    if not acc:
        raise ValueError('账号不存在')
    ok, resolved = validate_xhs_pool_path(acc.get('cookies_file'), 'cookies')
    if not ok:
        raise ValueError(resolved)
    from auth_utils import parse_cookies_text
    cookies = parse_cookies_text(cookies_text)
    if not cookies:
        raise ValueError('Cookie 内容无效或为空')
    os.makedirs(os.path.dirname(resolved), exist_ok=True)
    with open(resolved, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    if account_id == 'acc-default':
        _sync_auth_to_default()
    return {'cookies_file': _rel_path(resolved), 'cookie_count': len(cookies)}


def diagnose_account(account_id):
    acc = get_account(account_id)
    if not acc:
        raise ValueError('账号不存在')
    from crawler_web import close_cdp, connect_cdp, prepare_browser_for_crawl

    if not prepare_browser_for_crawl():
        result = {'diagnose_ok': False, 'error': 'chrome_not_ready', 'at': _utc_now_iso()}
        _store_diagnose_cache(account_id, result)
        return result
    try:
        ctx = connect_cdp()
        ok, info = diagnose_account_on_ctx(ctx, acc)
        result = {
            'diagnose_ok': ok,
            'info': {
                'has_xhs_in_browser': (info or {}).get('has_xhs_in_browser'),
                'has_xhs_in_config': (info or {}).get('has_xhs_in_config'),
                'hints': (info or {}).get('hints') or [],
            },
            'at': _utc_now_iso(),
        }
        if not ok and isinstance(info, dict) and info.get('error'):
            result['error'] = info.get('error')
    except Exception as e:
        result = {'diagnose_ok': False, 'error': str(e)[:200], 'at': _utc_now_iso()}
    finally:
        close_cdp(shutdown_browser=False)
    _store_diagnose_cache(account_id, result)
    return result


def _sync_auth_to_default():
    acc = get_account('acc-default')
    if not acc:
        return
    rel = acc.get('cookies_file')
    if rel:
        save_config({'auth': {'xhs': {'cookies_file': rel}}})
        load_config(force=True)


def _login_port_for_account(account_id):
    base = pool_config()['login_cdp_port_base']
    h = sum(ord(c) for c in (account_id or '')) % 50
    return base + h


def _close_login_chrome(session):
    port = session.get('cdp_port')
    if port:
        try:
            from crawler_web import release_worker_port, shutdown_cdp_browser
            shutdown_cdp_browser(port)
            release_worker_port(port)
        except Exception:
            pass


def _login_cookies_from_port(cdp_port):
    from auth_utils import has_xhs_session
    from crawler_web import ephemeral_cdp_context

    with ephemeral_cdp_context(cdp_port) as ctx:
        cookies = ctx.cookies() if ctx else []
        return cookies if has_xhs_session(cookies) else None


def _export_login_cookies_from_port(cdp_port, site='xhs'):
    from auth_utils import export_cookies_from_context, has_xhs_session
    from crawler_web import ephemeral_cdp_context

    with ephemeral_cdp_context(cdp_port) as ctx:
        cookies = ctx.cookies() if ctx else []
        if not has_xhs_session(cookies):
            return None
        return export_cookies_from_context(ctx, site)


def login_start(account_id):
    from intel.run_state import is_monitor_busy
    if is_monitor_busy():
        raise RuntimeError('监测任务进行中，请稍后再登录')
    acc = get_account(account_id)
    if not acc:
        raise ValueError('账号不存在')
    with _lock:
        if account_id in _login_sessions:
            _close_login_chrome(_login_sessions[account_id])
            del _login_sessions[account_id]

    profile = resolve_pool_path(acc.get('user_data_dir') or '')
    ok, _ = validate_xhs_pool_path(acc.get('user_data_dir'), 'profile')
    if not ok:
        raise ValueError('profile 路径无效')
    os.makedirs(profile, exist_ok=True)

    port = _login_port_for_account(account_id)
    from config import get_config
    auth = (get_config().get('auth') or {}).get('xhs') or {}
    login_url = auth.get('login_url') or 'https://www.xiaohongshu.com'

    from crawler_web import prepare_worker_browser, reserve_worker_port
    reserve_worker_port(port)
    if not prepare_worker_browser(port, profile, log_fn=None, startup_url=login_url):
        release_worker_port(port)
        raise RuntimeError('登录 Chrome 启动失败')

    session = {
        'account_id': account_id,
        'cdp_port': port,
        'started_at': time.time(),
        'status': 'waiting',
    }
    with _lock:
        _login_sessions[account_id] = session
    return {
        'account_id': account_id,
        'session_id': account_id,
        'status': 'waiting',
        'cdp_port': port,
        'message': '请在打开的 Chrome 窗口完成小红书登录',
    }


def login_status(account_id):
    with _lock:
        session = _login_sessions.get(account_id)
    if not session:
        return {'status': 'idle', 'account_id': account_id}
    elapsed = time.time() - session.get('started_at', time.time())
    timeout_sec = pool_config()['login_wait_timeout_sec']
    if elapsed > timeout_sec:
        _close_login_chrome(session)
        with _lock:
            _login_sessions.pop(account_id, None)
        return {'status': 'timeout', 'account_id': account_id}

    from auth_utils import has_xhs_session

    try:
        cookies = _login_cookies_from_port(session['cdp_port'])
        if cookies:
            session['status'] = 'logged_in'
            return {'status': 'logged_in', 'account_id': account_id, 'elapsed_sec': int(elapsed)}
    except Exception as e:
        return {'status': 'error', 'account_id': account_id, 'error': str(e)[:200]}
    return {'status': 'waiting', 'account_id': account_id, 'elapsed_sec': int(elapsed)}


def login_finish(account_id):
    with _lock:
        session = _login_sessions.get(account_id)
    if not session:
        raise ValueError('无进行中的登录会话')
    acc = get_account(account_id)
    if not acc:
        raise ValueError('账号不存在')

    from auth_utils import load_cookies_from_file, has_xhs_session

    cookies = _export_login_cookies_from_port(session['cdp_port'], 'xhs')
    if not cookies:
        raise ValueError('尚未检测到登录态，请完成登录后再保存')

    ok_path, resolved = validate_xhs_pool_path(acc.get('cookies_file'), 'cookies')
    if not ok_path:
        raise ValueError(resolved)
    os.makedirs(os.path.dirname(resolved), exist_ok=True)
    with open(resolved, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    _close_login_chrome(session)
    with _lock:
        _login_sessions.pop(account_id, None)
    diag = {
        'diagnose_ok': has_xhs_session(load_cookies_from_file(resolved, site='xhs')),
        'at': _utc_now_iso(),
    }
    _store_diagnose_cache(account_id, diag)
    if account_id == 'acc-default':
        _sync_auth_to_default()
    return {
        'ok': True,
        'cookies_file': acc.get('cookies_file'),
        'diagnose': diag,
    }


def login_cancel(account_id):
    with _lock:
        session = _login_sessions.pop(account_id, None)
    if session:
        _close_login_chrome(session)
    return {'ok': True, 'account_id': account_id}


def try_pick_and_bind_xhs(session, instance_cfg, log_fn=None):
    """Worker：为 keyword 选取账号并 rebind session；返回 account 或 None。"""

    def _bind_and_diagnose(acc):
        try:
            session.rebind_account(acc, log_fn=log_fn)
            return True
        except Exception as e:
            if log_fn:
                log_fn('[xhs-pool] 跳过账号 %s: %s' % (acc.get('id'), str(e)[:200]), 'WARN')
            return False

    acc = pick_account_for_keyword(diagnose_fn=_bind_and_diagnose, log_fn=log_fn)
    if acc and log_fn:
        log_fn('[xhs-pool] keyword 使用账号 %s (%s)' % (acc.get('label') or '', acc.get('id')))
    return acc


def rebind_xhs_browser_for_account(account, cdp_port, log_fn=None):
    """单进程路径：优先 Cookie 轮换，失败再关闭并换 profile 重启 Chrome。"""
    from auth_utils import source_startup_url, switch_xhs_account, xhs_session_ok
    from crawler_web import (
        S,
        close_cdp,
        connect_cdp,
        kill_cdp_browser_on_port,
        prepare_worker_browser,
        reserve_worker_port,
        release_worker_port,
    )

    profile = resolve_pool_path(account.get('user_data_dir') or '')
    cookies_file = resolve_pool_path(account.get('cookies_file') or '')

    ctx = getattr(S, 'ctx', None)
    if ctx is not None and cookies_file:
        ok, info = switch_xhs_account(ctx, cookies_file, log_fn=log_fn)
        if ok:
            from crawler_web import S
            S.xhs_pool_cookies_file = cookies_file or ''
            if log_fn:
                log_fn(
                    '[xhs-pool] 账号 %s 已绑定 (%s)'
                    % (account.get('id'), info.get('login_source') or 'cookie_switch'),
                )
            return ctx
        if log_fn:
            log_fn(
                '[xhs-pool] Cookie 轮换失败 (%s)，尝试切换 profile…'
                % (info.get('error') or 'unknown'),
                'WARN',
            )

    close_cdp(shutdown_browser=True, force=True)
    kill_cdp_browser_on_port(cdp_port, log_fn=log_fn)
    try:
        release_worker_port(cdp_port)
    except Exception:
        pass
    reserve_worker_port(cdp_port)
    if not prepare_worker_browser(
        cdp_port, profile, log_fn=log_fn, force_restart=True,
        startup_url=source_startup_url('xhs'),
    ):
        raise RuntimeError('Chrome 重启失败')
    ctx = connect_cdp(cdp_port=cdp_port, reset=True)
    from crawler_web import S
    S.xhs_pool_cookies_file = cookies_file or ''
    from auth_utils import xhs_session_ok
    ok, info = xhs_session_ok(ctx, log_fn=log_fn, cookies_file=cookies_file)
    if not ok:
        raise RuntimeError('账号 %s 诊断失败: %s' % (account.get('id'), info.get('error') or info))
    return ctx


def try_pick_and_bind_xhs_orchestrator(cdp_port, log_fn=None):
    """Runner 单进程：pick + rebind，返回 account。"""

    def _diag(acc):
        try:
            rebind_xhs_browser_for_account(acc, cdp_port, log_fn=log_fn)
            return True
        except Exception as e:
            if log_fn:
                log_fn('[xhs-pool] 跳过账号 %s: %s' % (acc.get('id'), str(e)[:120]), 'WARN')
            return False

    return pick_account_for_keyword(diagnose_fn=_diag, log_fn=log_fn)
