# -*- coding: utf-8 -*-
"""小红书勘察弹窗：URL 解析与 href 匹配单元测试（无浏览器）。"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from xhs_detail import parse_xhs_note_id, xhs_href_contains_note_id


def test_parse_explore_url():
    nid = '65a1b2c3d4e5f6789012345'
    url = 'https://www.xiaohongshu.com/explore/%s' % nid
    assert parse_xhs_note_id(url) == nid
    print('OK test_parse_explore_url')


def test_parse_relative_explore():
    nid = 'abc123def456'
    assert parse_xhs_note_id('/explore/%s?x=1' % nid) == nid
    print('OK test_parse_relative_explore')


def test_parse_discovery_item():
    nid = 'deadbeef1234'
    assert parse_xhs_note_id('https://www.xiaohongshu.com/discovery/item/%s' % nid) == nid
    print('OK test_parse_discovery_item')


def test_parse_query_param():
    assert parse_xhs_note_id('https://x.com/?note_id=note999') == 'note999'
    print('OK test_parse_query_param')


def test_parse_invalid():
    assert parse_xhs_note_id('') == ''
    assert parse_xhs_note_id('https://example.com/no-note') == ''
    print('OK test_parse_invalid')


def test_href_match_absolute():
    nid = '65a1b2c3d4e5f6789012345'
    href = 'https://www.xiaohongshu.com/explore/%s' % nid
    assert xhs_href_contains_note_id(href, nid)
    assert not xhs_href_contains_note_id(href, 'other')
    print('OK test_href_match_absolute')


def test_href_match_relative_host():
    nid = 'abc123'
    host = 'https://www.xiaohongshu.com'
    assert xhs_href_contains_note_id('/explore/%s' % nid, nid, host)
    print('OK test_href_match_relative_host')


if __name__ == '__main__':
    test_parse_explore_url()
    test_parse_relative_explore()
    test_parse_discovery_item()
    test_parse_query_param()
    test_parse_invalid()
    test_href_match_absolute()
    test_href_match_relative_host()
    print('All xhs_investigation_modal unit tests passed.')
