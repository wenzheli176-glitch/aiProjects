# -*- coding: utf-8 -*-
"""Worker Cookie 实例列表、路径校验、上传与诊断。"""
import json
import os
import time

from config import BASE_DIR, load_config, save_config
from intel.source_diagnose import diagnose_source_login_ok
from intel.worker_config import list_instances


def _cache_path():
    return os.path.join(BASE_DIR, 'credentials', '.cookie_diagnose_cache.json')


def _load_cache():
    path = _cache_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_cache(data):
    path = _cache_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data or {}, f, ensure_ascii=False, indent=2)


def _cache_key(source_id, instance_id):
    return '%s:%s' % (source_id, instance_id)


def validate_cookies_path(path):
    """拒绝路径穿越；仅允许项目内 credentials/ 下文件。"""
    if not path or '..' in str(path).replace('\\', '/'):
        return False, '非法路径'
    if os.path.isabs(path):
        resolved = os.path.realpath(path)
    else:
        resolved = os.path.realpath(os.path.join(BASE_DIR, path))
    base = os.path.realpath(BASE_DIR)
    if not resolved.startswith(base):
        return False, '路径越界'
    rel = os.path.relpath(resolved, base).replace('\\', '/')
    if not rel.startswith('credentials/'):
        return False, 'Cookie 文件须位于 credentials/ 目录'
    return True, resolved


def _rel_path(abs_path):
    try:
        return os.path.relpath(abs_path, BASE_DIR).replace('\\', '/')
    except Exception:
        return abs_path


def get_instance(source_id, instance_id):
    for inst in list_instances(source_id):
        if inst.get('source_id') == source_id and inst.get('instance_id') == instance_id:
            return inst
    return None


def _diagnose_ok_from_info(source_id, info):
    if not isinstance(info, dict):
        return False
    if info.get('ok') is False:
        return False
    return diagnose_source_login_ok(source_id, info)


def list_cookie_instances():
    cache = _load_cache()
    out = []
    has_failures = False
    for inst in list_instances():
        source_id = inst.get('source_id') or ''
        instance_id = inst.get('instance_id') or ''
        cookies_file = inst.get('cookies_file') or ''
        rel_file = _rel_path(cookies_file) if cookies_file else ''
        exists = bool(cookies_file and os.path.isfile(cookies_file))
        cookie_count = 0
        if exists:
            from auth_utils import load_cookies_from_file
            cookie_count = len(load_cookies_from_file(cookies_file, site=source_id))
        last = cache.get(_cache_key(source_id, instance_id)) or {}
        diagnose_ok = last.get('diagnose_ok')
        if diagnose_ok is False:
            has_failures = True
        if exists and diagnose_ok is None and cookie_count == 0:
            has_failures = True
        if not exists:
            has_failures = True
        out.append({
            'source_id': source_id,
            'instance_id': instance_id,
            'cdp_port': inst.get('cdp_port'),
            'user_data_dir': _rel_path(inst.get('user_data_dir') or ''),
            'cookies_file': rel_file,
            'cookies_file_exists': exists,
            'cookie_count': cookie_count,
            'last_diagnose': last or None,
        })
    return {
        'instances': out,
        'has_diagnose_failures': has_failures,
    }


def save_instance_cookies(source_id, instance_id, cookies_text):
    inst = get_instance(source_id, instance_id)
    if not inst:
        raise ValueError('实例不存在')
    cookies_file = inst.get('cookies_file') or ''
    ok, resolved = validate_cookies_path(cookies_file)
    if not ok:
        raise ValueError(resolved)
    from auth_utils import parse_cookies_text
    cookies = parse_cookies_text(cookies_text)
    if not cookies:
        raise ValueError('Cookie 内容无效或为空')
    os.makedirs(os.path.dirname(resolved), exist_ok=True)
    with open(resolved, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    rel = _rel_path(resolved)
    _sync_auth_cookies_file(source_id, instance_id, rel)
    return {'cookies_file': rel, 'cookie_count': len(cookies)}


def _sync_auth_cookies_file(source_id, instance_id, rel_path):
    """首个 instance 的 cookies_file 与 config.auth 对齐。"""
    insts = list_instances(source_id)
    if not insts:
        return
    first = insts[0]
    if first.get('instance_id') != instance_id:
        return
    save_config({'auth': {source_id: {'cookies_file': rel_path}}})
    load_config(force=True)


def diagnose_instance(source_id, instance_id):
    inst = get_instance(source_id, instance_id)
    if not inst:
        raise ValueError('实例不存在')
    cookies_file = inst.get('cookies_file') or ''
    ok_path, resolved = validate_cookies_path(cookies_file)
    if not ok_path:
        result = {
            'diagnose_ok': False,
            'error': resolved,
            'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        }
        _store_diagnose(source_id, instance_id, result)
        return result

    if not os.path.isfile(resolved):
        result = {
            'diagnose_ok': False,
            'error': 'cookies_file_missing',
            'cookies_file': _rel_path(resolved),
            'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        }
        _store_diagnose(source_id, instance_id, result)
        return result

    from auth_utils import apply_cookies_from_file, diagnose_login
    from crawler_web import close_cdp, connect_cdp, prepare_browser_for_crawl

    if not prepare_browser_for_crawl():
        result = {
            'diagnose_ok': False,
            'error': 'chrome_not_ready',
            'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        }
        _store_diagnose(source_id, instance_id, result)
        return result

    try:
        ctx = connect_cdp()
        apply_cookies_from_file(ctx, source_id, resolved)
        info = diagnose_login(ctx, source_id)
        diagnose_ok = _diagnose_ok_from_info(source_id, info)
        result = {
            'diagnose_ok': diagnose_ok,
            'info': {
                'browser_cookie_count': info.get('browser_cookie_count'),
                'config_cookie_count': info.get('config_cookie_count'),
                'has_sub_in_browser': info.get('has_sub_in_browser'),
                'has_sub_in_config': info.get('has_sub_in_config'),
                'has_xhs_in_browser': info.get('has_xhs_in_browser'),
                'has_xhs_in_config': info.get('has_xhs_in_config'),
                'hints': info.get('hints') or [],
            },
            'cookies_file': _rel_path(resolved),
            'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        }
    except Exception as e:
        result = {
            'diagnose_ok': False,
            'error': str(e)[:200],
            'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        }
    finally:
        close_cdp(shutdown_browser=False)

    _store_diagnose(source_id, instance_id, result)
    return result


def _store_diagnose(source_id, instance_id, result):
    cache = _load_cache()
    cache[_cache_key(source_id, instance_id)] = result
    _save_cache(cache)
