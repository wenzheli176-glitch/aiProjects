# -*- coding: utf-8 -*-
"""小红书搜索页 keyword 切换逻辑单元测试。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from login_gate import xhs_current_search_keyword, xhs_need_goto_search
from intel.worker_config import validate_worker_instances


class _Page:
    def __init__(self, url):
        self.url = url


def test_need_goto_when_keyword_changes():
    url = 'https://www.xiaohongshu.com/search_result?keyword=%E5%B0%8F%E7%B1%B3&type=1'
    page = _Page(url)
    assert xhs_current_search_keyword(page) == '小米'
    assert xhs_need_goto_search(page, '小米') is False
    assert xhs_need_goto_search(page, '蔚来汽车') is True
    print('OK test_need_goto_when_keyword_changes')


def test_need_goto_when_not_on_search():
    page = _Page('https://www.xiaohongshu.com/explore')
    assert xhs_need_goto_search(page, '小米') is True
    print('OK test_need_goto_when_not_on_search')


def test_validate_unique_cookies():
    clean = validate_worker_instances([
        {'source_id': 'xhs', 'instance_id': 'xhs-0', 'cookies_file': '/a.json'},
        {'source_id': 'xhs', 'instance_id': 'xhs-1', 'cookies_file': '/b.json'},
    ])
    assert clean == []
    dup = validate_worker_instances([
        {'source_id': 'xhs', 'instance_id': 'xhs-0', 'cookies_file': '/same.json'},
        {'source_id': 'xhs', 'instance_id': 'xhs-1', 'cookies_file': '/same.json'},
    ])
    assert dup
    print('OK test_validate_unique_cookies')


if __name__ == '__main__':
    test_need_goto_when_keyword_changes()
    test_need_goto_when_not_on_search()
    test_validate_unique_cookies()
    print('ALL OK')
