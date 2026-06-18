# -*- coding: utf-8 -*-
"""单进程 Run 前 Cookie 诊断单元测试。"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.environ.setdefault('MINIMAX_API_KEY', '')


def test_diagnose_source_login_ok():
    from intel.source_diagnose import diagnose_source_login_ok

    assert diagnose_source_login_ok('heimao', {'has_sub_in_browser': True})
    assert not diagnose_source_login_ok('heimao', {})
    assert diagnose_source_login_ok('xhs', {'has_xhs_in_config': True})
    assert not diagnose_source_login_ok('xhs', {})
    print('OK test_diagnose_source_login_ok')


def test_filter_partial_failure():
    from intel.run_metrics import RunMetrics
    import intel.source_diagnose as sd

    calls = []

    def fake_filter(sources, run_metrics=None, log_fn=None):
        out = []
        for s in sources:
            if s == 'heimao':
                if run_metrics:
                    run_metrics.record_worker_instance('heimao', 'heimao-0', 'diagnose_failed', diagnose_ok=False)
                continue
            out.append(s)
        if run_metrics:
            run_metrics.set_sources_degraded(1)
        return out

    orig = sd.filter_sources_after_diagnose
    sd.filter_sources_after_diagnose = fake_filter
    try:
        rm = RunMetrics()
        ok = sd.filter_sources_after_diagnose(['heimao', 'xhs'], run_metrics=rm)
        assert ok == ['xhs']
        assert rm.stats['cookie_diagnose_failed'] == 1
        assert rm.stats['sources_degraded'] == 1
    finally:
        sd.filter_sources_after_diagnose = orig
    print('OK test_filter_partial_failure')


if __name__ == '__main__':
    test_diagnose_source_login_ok()
    test_filter_partial_failure()
    print('All source diagnose tests passed.')
