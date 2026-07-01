# -*- coding: utf-8 -*-
"""API Key 鉴权：合作方 / 任务 / 情报接口。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['INTEL_API_KEY'] = 'test-api-key-for-unit-tests'

from config import load_config

load_config(force=True)

from crawler_web import app


def _client():
    app.config['TESTING'] = True
    return app.test_client()


def test_intel_records_requires_key_when_enabled():
    c = _client()
    r = c.get('/api/intel/records')
    assert r.status_code == 401, r.get_json()
    r2 = c.get('/api/intel/records', headers={'X-API-Key': 'test-api-key-for-unit-tests'})
    assert r2.status_code == 200, r2.get_json()
    print('OK test_intel_records_requires_key_when_enabled')


def test_partners_crud_with_bearer():
    c = _client()
    headers = {'Authorization': 'Bearer test-api-key-for-unit-tests', 'Content-Type': 'application/json'}
    r = c.post('/api/partners', json={'name': '__api_auth_test__', 'aliases': ['aat']}, headers=headers)
    assert r.status_code == 200, r.get_json()
    pid = r.get_json()['partner']['id']
    r2 = c.get('/api/partners/%d' % pid, headers=headers)
    assert r2.status_code == 200
    r3 = c.put('/api/partners/%d' % pid, json={'name': '__api_auth_test2__'}, headers=headers)
    assert r3.status_code == 200
    r4 = c.delete('/api/partners/%d' % pid, headers=headers)
    assert r4.status_code == 200
    print('OK test_partners_crud_with_bearer')


def test_monitor_tasks_list_with_key():
    c = _client()
    r = c.get('/api/monitor/tasks', headers={'X-API-Key': 'test-api-key-for-unit-tests'})
    assert r.status_code == 200
    print('OK test_monitor_tasks_list_with_key')


def test_unprotected_sources_still_open():
    c = _client()
    r = c.get('/api/sources')
    assert r.status_code == 200
    print('OK test_unprotected_sources_still_open')


def test_auth_status():
    c = _client()
    r = c.get('/api/integration/auth/status', headers={'X-API-Key': 'test-api-key-for-unit-tests'})
    body = r.get_json()
    assert body.get('ok') and body.get('authenticated')
    assert body.get('via') == 'api_key'
    print('OK test_auth_status')


if __name__ == '__main__':
    test_intel_records_requires_key_when_enabled()
    test_partners_crud_with_bearer()
    test_monitor_tasks_list_with_key()
    test_unprotected_sources_still_open()
    test_auth_status()
    print('All api_auth tests passed.')
