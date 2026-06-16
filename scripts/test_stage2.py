# -*- coding: utf-8 -*-
"""Stage2 单元测试：keyword_batch、matcher、triage 阈值逻辑。"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.environ.setdefault('MINIMAX_API_KEY', '')

from intel.keyword_batch import build_keyword_batches, sort_batches_by_quota
from intel.matcher import match_all_partners


def test_keyword_batch_merge():
    partners = [
        {'id': 1, 'name': '蔚来', 'aliases': ['NIO'], 'monitor_keywords': [], 'industry_cohort': '新能源'},
        {'id': 2, 'name': '小鹏', 'aliases': [], 'monitor_keywords': ['小鹏汽车'], 'industry_cohort': '新能源'},
    ]
    batches = build_keyword_batches(partners, max_keywords=5)
    assert len(batches) == 1
    assert batches[0]['cohort'] == '新能源'
    kws = batches[0]['keywords']
    assert '蔚来' in kws and '小鹏' in kws and 'NIO' in kws
    print('OK test_keyword_batch_merge')


def test_match_all_partners():
    normalized = {'title': '蔚来汽车质量问题', 'body': ''}
    partners = [
        {'id': 1, 'name': '蔚来', 'aliases': ['NIO'], 'exclude_words': [], 'monitor_keywords': []},
        {'id': 2, 'name': '小鹏', 'aliases': [], 'exclude_words': [], 'monitor_keywords': []},
    ]
    hits = match_all_partners(normalized, partners)
    assert len(hits) == 1
    assert hits[0]['partner_id'] == 1
    print('OK test_match_all_partners')


def test_sort_batches_by_quota():
    batches = [
        {'priority_tier': 'P2', 'keywords': ['b']},
        {'priority_tier': 'P0', 'keywords': ['a']},
        {'priority_tier': 'P1', 'keywords': ['c']},
    ]
    out = sort_batches_by_quota(batches)
    assert out[0]['priority_tier'] == 'P0'
    print('OK test_sort_batches_by_quota')


if __name__ == '__main__':
    test_keyword_batch_merge()
    test_match_all_partners()
    test_sort_batches_by_quota()
    print('All stage2 unit tests passed.')
