# -*- coding: utf-8 -*-
"""parallel-crawl-workers-selective-xhs 可自动化验证项。"""
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.environ.setdefault('MINIMAX_API_KEY', '')


def test_cookie_instances_api():
    from crawler_web import app

    client = app.test_client()
    r = client.get('/api/cookie-instances')
    assert r.status_code == 200, r.data
    data = r.get_json()
    assert data.get('ok') is True
    assert 'instances' in data
    assert 'has_diagnose_failures' in data

    r2 = client.post(
        '/api/cookie-instances/heimao/heimao-0/upload',
        json={'cookies': '[{"name":"a","value":"b"}]'},
    )
    assert r2.status_code == 403, r2.data
    print('OK test_cookie_instances_api')


def test_status_worker_fields():
    from crawler_web import app

    client = app.test_client()
    r = client.get('/api/status')
    assert r.status_code == 200
    data = r.get_json()
    assert 'worker_states' in data
    assert 'login_wait' in data
    print('OK test_status_worker_fields')


def test_field_labels_new_stats():
    from field_labels import FIELD_LABELS

    for key in (
        'investigation_modal_done',
        'investigation_skipped_quota',
    ):
        assert key in FIELD_LABELS, key
    print('OK test_field_labels_new_stats')


def test_xhs_crawl_mode_forced():
    from source_profiles import resolve_source_crawl_mode

    assert resolve_source_crawl_mode('xhs') == 'list_first'
    print('OK test_xhs_crawl_mode_forced')


def test_workers_config_default_off():
    from intel.worker_config import workers_enabled

    assert workers_enabled() is False
    print('OK test_workers_config_default_off')


if __name__ == '__main__':
    test_cookie_instances_api()
    test_status_worker_fields()
    test_field_labels_new_stats()
    test_xhs_crawl_mode_forced()
    test_workers_config_default_off()
    print('All parallel-crawl automated verification passed.')
