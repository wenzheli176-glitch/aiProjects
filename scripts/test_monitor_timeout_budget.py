# -*- coding: utf-8 -*-
"""monitor 爬取/分析超时预算单元测试。"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intel.timeout_budget import compute_monitor_deadlines


def test_7200_7200_not_300():
    b = compute_monitor_deadlines(7200, 7200, 1800)
    assert b['crawl_budget_sec'] >= 1800, b
    assert b['crawl_budget_sec'] != 300, b
    print('OK test_7200_7200_not_300', b)


def test_7200_3600_typical():
    b = compute_monitor_deadlines(7200, 3600, 1800)
    assert b['crawl_budget_sec'] == 3600, b
    assert b['analysis_reserve_sec'] == 3600, b
    print('OK test_7200_3600_typical', b)


def test_short_task_crawl_floor():
    b = compute_monitor_deadlines(120, 3600, 60)
    assert b['crawl_budget_sec'] >= 60, b
    assert b['task_timeout_sec'] == 120, b
    print('OK test_short_task_crawl_floor', b)


def test_timeout_messages():
    from intel.runner import _timeout_message

    crawl_msg = _timeout_message('crawl', crawl_budget_sec=3600, task_timeout_sec=7200)
    assert '爬取阶段超时' in crawl_msg
    assert 'crawl_budget_sec=3600' in crawl_msg
    analyze_msg = _timeout_message('analyze', task_timeout_sec=7200)
    assert '分析阶段超时' in analyze_msg
    print('OK test_timeout_messages')


def test_progress_reason():
    from intel.runner import _timeout_progress_reason

    assert _timeout_progress_reason(True, 'crawl') == 'crawl_timeout'
    assert _timeout_progress_reason(True, 'analyze') == 'timeout'
    assert _timeout_progress_reason(False, '') == 'stopped'
    print('OK test_progress_reason')


if __name__ == '__main__':
    test_7200_7200_not_300()
    test_7200_3600_typical()
    test_short_task_crawl_floor()
    test_timeout_messages()
    test_progress_reason()
    print('All monitor timeout budget tests passed.')
