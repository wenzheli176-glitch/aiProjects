# -*- coding: utf-8 -*-
"""analysis.parallel_batches 单元测试。"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.environ.setdefault('MINIMAX_API_KEY', '')


def test_parallel_batches_config_default():
    from config import DEFAULT_CONFIG
    assert int((DEFAULT_CONFIG.get('analysis') or {}).get('parallel_batches') or 0) == 5
    print('OK test_parallel_batches_config_default')


def test_parallel_batches_mock():
    import config
    import intel.analyze as az

    config.save_config({
        'analysis': {
            'mock_without_key': True,
            'batch_size': 2,
            'parallel_batches': 3,
        },
    })
    config.load_config(force=True)

    candidates = [
        {'id': i, 'source': 'xhs', 'title': 't%d' % i, 'body': '投诉维权 %d' % i}
        for i in range(1, 7)
    ]
    partner = {'id': 1, 'name': '小鹏', 'aliases': []}

    import intel.db as db_mod

    orig_insert_intel = az.insert_intel_record
    orig_insert_log = az.insert_analysis_log
    orig_update_usage = az.update_analysis_job_usage
    orig_update_job = az.update_analysis_job
    orig_get_job = db_mod.get_analysis_job

    az.insert_intel_record = lambda *a, **k: True
    az.insert_analysis_log = lambda *a, **k: None
    az.update_analysis_job_usage = lambda *a, **k: None
    az.update_analysis_job = lambda *a, **k: None
    db_mod.get_analysis_job = lambda *a, **k: {'usage': {}}

    try:
        written = az.analyze_candidates(1, 99, candidates, partner, log_fn=None)
        assert written == 6
    finally:
        az.insert_intel_record = orig_insert_intel
        az.insert_analysis_log = orig_insert_log
        az.update_analysis_job_usage = orig_update_usage
        az.update_analysis_job = orig_update_job
        db_mod.get_analysis_job = orig_get_job

    print('OK test_parallel_batches_mock')


if __name__ == '__main__':
    test_parallel_batches_config_default()
    test_parallel_batches_mock()
    print('All analyze parallel tests passed.')
