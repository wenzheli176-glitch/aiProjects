# -*- coding: utf-8 -*-
"""Cookie 实例路径校验与上传安全单元测试。"""
import json
import os
import sys
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.environ.setdefault('MINIMAX_API_KEY', '')


def test_validate_cookies_path():
    from intel.cookie_instances import validate_cookies_path

    ok, resolved = validate_cookies_path('credentials/test_cookies.json')
    assert ok, resolved
    assert resolved.endswith('credentials' + os.sep + 'test_cookies.json') or resolved.replace('\\', '/').endswith('credentials/test_cookies.json')

    ok, msg = validate_cookies_path('credentials/../config.json')
    assert not ok
    assert '非法' in msg or '越界' in msg or '须位于' in msg

    ok, msg = validate_cookies_path('/etc/passwd')
    assert not ok

    ok, msg = validate_cookies_path('data/secret.json')
    assert not ok
    assert 'credentials' in msg
    print('OK test_validate_cookies_path')


def test_save_rejects_bad_path(monkeypatch=None):
    from intel import cookie_instances as ci

    def fake_get_instance(source_id, instance_id):
        return {
            'source_id': source_id,
            'instance_id': instance_id,
            'cookies_file': os.path.join('credentials', '..', 'evil.json'),
        }

    orig = ci.get_instance
    ci.get_instance = fake_get_instance
    try:
        try:
            ci.save_instance_cookies('heimao', 'heimao-0', '[{"name":"a","value":"b"}]')
            assert False, 'expected ValueError'
        except ValueError as e:
            assert '非法' in str(e) or '越界' in str(e) or '须位于' in str(e)
    finally:
        ci.get_instance = orig
    print('OK test_save_rejects_bad_path')


def test_save_valid_cookies(tmp_dir=None):
    from intel import cookie_instances as ci

    cred_dir = os.path.join(BASE, 'credentials')
    os.makedirs(cred_dir, exist_ok=True)
    target = os.path.join(cred_dir, '_test_cookie_upload.json')
    rel = 'credentials/_test_cookie_upload.json'
    if os.path.isfile(target):
        os.remove(target)

    def fake_get_instance(source_id, instance_id):
        return {
            'source_id': source_id,
            'instance_id': instance_id,
            'cookies_file': target,
        }

    synced = []
    orig_get = ci.get_instance
    orig_sync = ci._sync_auth_cookies_file
    ci.get_instance = fake_get_instance
    ci._sync_auth_cookies_file = lambda sid, iid, rp: synced.append((sid, iid, rp))
    try:
        cookies_text = json.dumps([{'name': 'test', 'value': '1', 'domain': '.example.com'}])
        result = ci.save_instance_cookies('xhs', 'xhs-0', cookies_text)
        assert result['cookie_count'] == 1
        assert os.path.isfile(target)
        with open(target, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert len(data) == 1
        assert result['cookies_file'].replace('\\', '/').endswith('_test_cookie_upload.json')
    finally:
        ci.get_instance = orig_get
        ci._sync_auth_cookies_file = orig_sync
        if os.path.isfile(target):
            os.remove(target)
    print('OK test_save_valid_cookies')


def test_list_cookie_instances_shape():
    from intel.cookie_instances import list_cookie_instances

    data = list_cookie_instances()
    assert 'instances' in data
    assert 'has_diagnose_failures' in data
    assert isinstance(data['instances'], list)
    if data['instances']:
        inst = data['instances'][0]
        for key in ('source_id', 'instance_id', 'cookies_file', 'cookies_file_exists', 'cookie_count'):
            assert key in inst
    print('OK test_list_cookie_instances_shape')


if __name__ == '__main__':
    test_validate_cookies_path()
    test_save_rejects_bad_path()
    test_save_valid_cookies()
    test_list_cookie_instances_shape()
    print('All cookie instance tests passed.')
