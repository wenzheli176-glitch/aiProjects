# -*- coding: utf-8 -*-
"""发布时间解析单元测试。"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from intel.date_parse import age_days, parse_published_date


def test_absolute_date():
    d, q = parse_published_date('2024-03-15 12:00', '2026-06-12')
    assert d == '2024-03-15' and q == 'absolute'
    print('OK test_absolute_date')


def test_relative_yesterday():
    d, q = parse_published_date('昨天', '2026-06-12')
    assert d == '2026-06-11' and q == 'relative'
    print('OK test_relative_yesterday')


def test_relative_days_ago():
    d, q = parse_published_date('3天前', '2026-06-12')
    assert d == '2026-06-09' and q == 'relative'
    print('OK test_relative_days_ago')


def test_empty():
    d, q = parse_published_date('', '2026-06-12')
    assert d == '' and q == 'missing'
    print('OK test_empty')


def test_age_days():
    assert age_days('2026-06-01', '2026-06-12') == 11
    assert age_days('', '2026-06-12') is None
    print('OK test_age_days')


def test_md_only():
    d, q = parse_published_date('03-27', '2026-06-12')
    assert d == '2026-03-27' and q == 'absolute'
    d2, _ = parse_published_date('编辑于 05-29 浙江', '2026-06-12')
    assert d2 == '2026-05-29'
    print('OK test_md_only')


def test_recency_downgrade():
    from intel.recency import apply_recency_relevance
    rel, llm = apply_recency_relevance('high', 0.8, '2026-01-01', '2026-06-12')
    assert rel == 'low' and llm == 'high'
    rel2, _ = apply_recency_relevance('high', 0.8, '', '2026-06-12')
    assert rel2 == 'high'
    rel3, _ = apply_recency_relevance('medium', 0.2, '2026-06-01', '2026-06-12')
    assert rel3 == 'low'
    print('OK test_recency_downgrade')


if __name__ == '__main__':
    test_absolute_date()
    test_relative_yesterday()
    test_relative_days_ago()
    test_empty()
    test_age_days()
    test_md_only()
    test_recency_downgrade()
    print('All date_parse unit tests passed.')
