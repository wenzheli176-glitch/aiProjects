# -*- coding: utf-8 -*-
"""对外 REST API 密钥鉴权（合作方 / 监测任务 / 情报）。"""
import hmac
import os
from functools import wraps

from flask import jsonify, request

from config import cfg

# 合作方、任务、情报及关联 Run / 导出 / 清理
PROTECTED_API_PREFIXES = (
    '/api/partners',
    '/api/monitor',
    '/api/intel',
    '/api/dashboard/summary',
    '/api/admin/purge/intel',
)


def api_auth_cfg():
    return cfg('api_auth') or {}


def api_auth_enabled():
    return bool(api_auth_cfg().get('enabled', False))


def extract_api_key():
    auth = (request.headers.get('Authorization') or '').strip()
    if auth.lower().startswith('bearer '):
        return auth[7:].strip()
    x_key = (request.headers.get('X-API-Key') or '').strip()
    if x_key:
        return x_key
    if request.method == 'GET':
        q = (request.args.get('api_key') or '').strip()
        if q:
            return q
    return ''


def configured_api_keys():
    keys = set()
    ac = api_auth_cfg()
    for k in ac.get('keys') or []:
        s = str(k or '').strip()
        if s:
            keys.add(s)
    env_name = ac.get('key_env') or 'INTEL_API_KEY'
    env_val = (os.environ.get(env_name) or '').strip()
    if env_val:
        keys.add(env_val)
    keys_env = ac.get('keys_env') or 'INTEL_API_KEYS'
    multi = os.environ.get(keys_env) or ''
    for part in multi.replace('\n', ',').split(','):
        part = part.strip()
        if part:
            keys.add(part)
    return keys


def has_valid_api_key():
    key = extract_api_key()
    if not key:
        return False
    valid_keys = configured_api_keys()
    if not valid_keys:
        return False
    for vk in valid_keys:
        if hmac.compare_digest(key, vk):
            return True
    return False


def is_api_authenticated():
    if has_valid_api_key():
        return True
    ac = api_auth_cfg()
    if not ac.get('allow_admin_session', True):
        return False
    from admin_auth import admin_auth_enabled, is_admin_request
    if admin_auth_enabled() and is_admin_request():
        return True
    return False


def is_protected_api_path(path):
    path = path or ''
    for prefix in PROTECTED_API_PREFIXES:
        if path == prefix or path.startswith(prefix + '/'):
            return True
    return False


def check_intel_api_auth():
    """Blueprint before_request：未授权时返回 (response, status)，否则 None。"""
    if not api_auth_enabled():
        return None
    path = request.path or ''
    if not is_protected_api_path(path):
        return None
    if is_api_authenticated():
        return None
    return jsonify({
        'ok': False,
        'msg': '需要有效的 API Key（Header: Authorization: Bearer <key> 或 X-API-Key）',
    }), 401


def register_intel_api_auth(bp):
    """已弃用：请在 intel_bp 模块加载时用 @bp.before_request 注册 check_intel_api_auth。"""
    if getattr(bp, '_api_auth_hook_registered', False):
        return

    @bp.before_request
    def _intel_api_auth_guard():
        return check_intel_api_auth()

    bp._api_auth_hook_registered = True


def require_api_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not api_auth_enabled():
            return fn(*args, **kwargs)
        if is_api_authenticated():
            return fn(*args, **kwargs)
        return jsonify({
            'ok': False,
            'msg': '需要有效的 API Key 或管理员 Session',
        }), 401
    return wrapper


def register_api_auth_routes(app):
    if any(getattr(r, 'rule', None) == '/api/integration/auth/status' for r in app.url_map.iter_rules()):
        return
    @app.route('/api/integration/auth/status', methods=['GET'])
    def api_integration_auth_status():
        via = 'none'
        if has_valid_api_key():
            via = 'api_key'
        elif is_api_authenticated():
            via = 'admin_session'
        return jsonify({
            'ok': True,
            'api_auth_enabled': api_auth_enabled(),
            'authenticated': is_api_authenticated() if api_auth_enabled() else True,
            'via': via,
            'keys_configured': len(configured_api_keys()) if api_auth_enabled() else None,
        })
