# -*- coding: utf-8 -*-
"""Phase A：混合源 crawl_mode 路由与 investigation 过滤。"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.environ.setdefault('MINIMAX_API_KEY', '')

from intel.investigation import _heimao_routine_has_detail, build_investigation_queue
from intel.runner import _list_phase_raw_rows
from source_profiles import (
    crawl_modes_for_task,
    resolve_source_crawl_mode,
    task_uses_shared_pool,
    validate_crawl_mode_patch,
)


def test_xhs_forced_list_first():
    assert resolve_source_crawl_mode('xhs') == 'list_first'
    assert resolve_source_crawl_mode('xhs', {'crawl_mode': 'legacy', 'sources': ['xhs']}) == 'list_first'
    ok, msg = validate_crawl_mode_patch('xhs', 'legacy')
    assert not ok
    print('OK test_xhs_forced_list_first')


def test_mixed_task_modes():
    task = {'sources': ['heimao', 'xhs'], 'crawl_mode': 'legacy', 'fetch_detail': True}
    modes = crawl_modes_for_task(task)
    assert modes['heimao'] == 'legacy'
    assert modes['xhs'] == 'list_first'
    assert task_uses_shared_pool(task)
    print('OK test_mixed_task_modes')


def test_heimao_single_task_fallback():
    task = {'sources': ['heimao'], 'crawl_mode': 'list_first'}
    assert resolve_source_crawl_mode('heimao', task) == 'list_first'
    task2 = {'sources': ['heimao'], 'crawl_mode': 'legacy'}
    assert resolve_source_crawl_mode('heimao', task2) == 'legacy'
    print('OK test_heimao_single_task_fallback')


def test_heimao_skip_investigation():
    task = {'fetch_detail': True}
    row = {
        'id': 1,
        'source': 'heimao',
        'crawl_phase': 'legacy',
        'payload': {'content': 'x' * 100},
        'list_triage': {'triage_relevance': 'high', 'needs_investigation': True},
    }
    assert _heimao_routine_has_detail(row, task)

    xhs_row = {
        'id': 2,
        'source': 'xhs',
        'crawl_phase': 'list',
        'payload': {'title': 't', 'link': 'http://example.com/x'},
        'list_triage': {
            'triage_relevance': 'high',
            'needs_investigation': True,
            'triage_risk_hint': 'elevated',
        },
    }

    class FakeRegistry:
        @staticmethod
        def get_normalizer(source_id):
            class N:
                def normalize(self, payload):
                    return {
                        'title': payload.get('title') or '',
                        'body': payload.get('content') or payload.get('body') or '',
                        'url': payload.get('link') or '',
                    }
            return N()

    import intel.investigation as inv_mod
    old_reg = inv_mod.registry
    orig_list = inv_mod.list_raw_records
    orig_clear = inv_mod.clear_investigation_queue
    orig_enqueue = inv_mod.enqueue_investigation
    orig_state = inv_mod.get_raw_analysis_state
    enqueued_sources = []
    inv_mod.registry = FakeRegistry()
    try:
        inv_mod.list_raw_records = lambda tid: [row, xhs_row]
        inv_mod.clear_investigation_queue = lambda tid: None
        inv_mod.enqueue_investigation = lambda task_id, raw_id, url, source, score: (
            enqueued_sources.append(source) or 1
        )
        inv_mod.get_raw_analysis_state = lambda tid: {}
        n = build_investigation_queue(1, [{'id': 1, 'priority_tier': 'P1'}], task=task)
        assert n == 1, 'expected 1 queued, got %d sources=%s' % (n, enqueued_sources)
        assert enqueued_sources == ['xhs']
    finally:
        inv_mod.registry = old_reg
        inv_mod.list_raw_records = orig_list
        inv_mod.clear_investigation_queue = orig_clear
        inv_mod.enqueue_investigation = orig_enqueue
        inv_mod.get_raw_analysis_state = orig_state
    print('OK test_heimao_skip_investigation')


def test_list_phase_filter():
    rows = [
        {'id': 1, 'crawl_phase': 'list'},
        {'id': 2, 'crawl_phase': 'legacy'},
        {'id': 3, 'crawl_phase': 'detail'},
    ]
    import intel.runner as runner_mod
    import intel.db as db_mod
    orig = db_mod.list_raw_records
    db_mod.list_raw_records = lambda tid: rows
    runner_mod.list_raw_records = lambda tid: rows
    try:
        out = runner_mod._list_phase_raw_rows(1)
        assert len(out) == 1 and out[0]['id'] == 1
    finally:
        db_mod.list_raw_records = orig
        runner_mod.list_raw_records = orig
    print('OK test_list_phase_filter')


if __name__ == '__main__':
    test_xhs_forced_list_first()
    test_mixed_task_modes()
    test_heimao_single_task_fallback()
    test_heimao_skip_investigation()
    test_list_phase_filter()
    print('All mixed source routing tests passed.')
