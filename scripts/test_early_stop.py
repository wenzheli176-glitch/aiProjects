# -*- coding: utf-8 -*-
"""早停逻辑单元测试（无浏览器）。"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from crawl_early_stop import (
    early_stop_cfg,
    heimao_should_stop_after_page,
    xhs_body_has_end_marker,
    xhs_update_saturation,
)


def test_heimao_default_empty_page_retry_zero():
    es = early_stop_cfg('heimao', {})
    assert es.get('empty_page_retry') == 0
    print('OK test_heimao_default_empty_page_retry_zero')


def test_heimao_empty_page_stop():
    es = early_stop_cfg('heimao', {'early_stop': {'enabled': True, 'empty_pages_threshold': 1, 'min_pages': 1}})
    stop, reason, c = heimao_should_stop_after_page(es, 2, 5, 0, 0)
    assert stop and reason == 'empty_page'
    assert c == 1
    print('OK test_heimao_empty_page_stop')


def test_heimao_first_page_protect_stop():
    es = early_stop_cfg('heimao', {'early_stop': {'enabled': True, 'protect_first_page': True}})
    stop, reason, _ = heimao_should_stop_after_page(es, 1, 5, 0, 0)
    assert stop and reason == 'empty_page'
    print('OK test_heimao_first_page_protect_stop')


def test_heimao_disabled_no_stop():
    es = early_stop_cfg('heimao', {'early_stop': {'enabled': False}})
    stop, reason, c = heimao_should_stop_after_page(es, 3, 5, 0, 2)
    assert not stop and reason is None
    print('OK test_heimao_disabled_no_stop')


def test_heimao_page_too_short_skips():
    es = early_stop_cfg('heimao', {'early_stop': {'enabled': True}})
    stop, reason, c = heimao_should_stop_after_page(es, 2, 5, 0, 1, page_too_short=True)
    assert not stop
    assert c == 1
    print('OK test_heimao_page_too_short_skips')


def test_xhs_end_marker_text():
    es = early_stop_cfg('xhs', {})
    assert xhs_body_has_end_marker('scroll down\n- THE END -\n', es)
    assert not xhs_body_has_end_marker('no marker here', es)
    print('OK test_xhs_end_marker_text')


def test_xhs_saturation_stop():
    es = early_stop_cfg('xhs', {'early_stop': {'enabled': True, 'saturation_rounds': 2, 'min_pages': 1}})
    state = {'saturation_rounds': 0, 'prev_item_count': 10}
    stop, _ = xhs_update_saturation(es, state, 2, 5, 0, 10)
    assert not stop
    stop, reason = xhs_update_saturation(es, state, 3, 5, 0, 10)
    assert stop and reason == 'scroll_saturated'
    print('OK test_xhs_saturation_stop')


if __name__ == '__main__':
    test_heimao_default_empty_page_retry_zero()
    test_heimao_empty_page_stop()
    test_heimao_first_page_protect_stop()
    test_heimao_disabled_no_stop()
    test_heimao_page_too_short_skips()
    test_xhs_end_marker_text()
    test_xhs_saturation_stop()
    print('All early_stop unit tests passed.')
