# -*- coding: utf-8 -*-
"""Web 控制台管理员 Session 鉴权。"""
import hashlib
import hmac
import os
import secrets
import time
from functools import wraps

from flask import jsonify, request

from config import cfg

SESSION_COOKIE = 'admin_session'
SESSION_MAX_AGE = 86400


def _admin_cfg():
    return cfg('admin') or {}


def admin_auth_enabled():
    return bool(_admin_cfg().get('enabled', True))


def _session_secret():
    env_name = _admin_cfg().get('session_secret_env') or 'ADMIN_SESSION_SECRET'
    secret = os.environ.get(env_name) or _admin_cfg().get('session_secret') or ''
    if not secret:
        secret = 'dev-insecure-change-me'
    return secret


def _password_ok(password):
    if not password:
        return False
    stored_hash = _admin_cfg().get('password_hash') or ''
    if stored_hash:
        return _verify_password_hash(password, stored_hash)
    env_name = _admin_cfg().get('password_env') or 'ADMIN_PASSWORD'
    expected = os.environ.get(env_name) or _admin_cfg().get('password') or ''
    if not expected:
        return False
    return hmac.compare_digest(str(password), str(expected))


def _verify_password_hash(password, stored):
    try:
        algo, salt, digest = stored.split('$', 2)
        if algo != 'pbkdf2':
            return False
        check = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 120000)
        return hmac.compare_digest(check.hex(), digest)
    except Exception:
        return False


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 120000).hex()
    return 'pbkdf2$%s$%s' % (salt, digest)


def _sign_token(payload):
    ts = str(int(time.time()))
    body = '%s:%s' % (payload, ts)
    sig = hmac.new(_session_secret().encode('utf-8'), body.encode('utf-8'), hashlib.sha256).hexdigest()
    return '%s:%s' % (body, sig)


def _verify_token(token):
    if not token or token.count(':') < 2:
        return False
    body, sig = token.rsplit(':', 1)
    expected = hmac.new(_session_secret().encode('utf-8'), body.encode('utf-8'), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return False
    try:
        payload, ts_str = body.rsplit(':', 1)
        ts = int(ts_str)
    except ValueError:
        return False
    if payload != 'admin':
        return False
    ttl_hours = float(_admin_cfg().get('session_ttl_hours') or 8)
    if time.time() - ts > ttl_hours * 3600:
        return False
    return True


def is_admin_request():
    if not admin_auth_enabled():
        return True
    token = request.cookies.get(SESSION_COOKIE) or ''
    return _verify_token(token)


def session_info():
    logged_in = is_admin_request()
    return {
        'logged_in': logged_in,
        'role': 'admin' if logged_in else 'operator',
        'auth_enabled': admin_auth_enabled(),
    }


def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not admin_auth_enabled():
            return fn(*args, **kwargs)
        if not is_admin_request():
            return jsonify({'ok': False, 'msg': '需要管理员登录'}), 403
        return fn(*args, **kwargs)

    return wrapper


def register_admin_routes(app):
    @app.route('/api/admin/login', methods=['POST'])
    def api_admin_login():
        if not admin_auth_enabled():
            return jsonify({'ok': True, 'role': 'admin', 'msg': '鉴权已关闭'})
        data = request.get_json(force=True, silent=True) or {}
        password = data.get('password') or ''
        if not _password_ok(password):
            return jsonify({'ok': False, 'msg': '口令错误'}), 401
        token = _sign_token('admin')
        resp = jsonify({'ok': True, 'role': 'admin'})
        resp.set_cookie(
            SESSION_COOKIE,
            token,
            max_age=int(_admin_cfg().get('session_ttl_hours') or 8) * 3600,
            httponly=True,
            samesite='Lax',
        )
        return resp

    @app.route('/api/admin/logout', methods=['POST'])
    def api_admin_logout():
        resp = jsonify({'ok': True})
        resp.set_cookie(SESSION_COOKIE, '', max_age=0, httponly=True, samesite='Lax')
        return resp

    @app.route('/api/admin/session', methods=['GET'])
    def api_admin_session():
        return jsonify({'ok': True, **session_info()})
