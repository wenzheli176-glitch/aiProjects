# -*- coding: utf-8 -*-
"""黑猫下拉加载与早停单元测试。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawl_early_stop import heimao_should_stop_after_page, early_stop_cfg, xhs_update_saturation
from heimao_scroll import heimao_scroll_load_batch


def test_heimao_scroll_to_bottom():
    calls = []

    class FakePage:
        def evaluate(self, script, *args):
            calls.append(script)

    heimao_scroll_load_batch(
        FakePage(),
        {'scroll_times_per_page': 2, 'scroll_wait_seconds': 0, 'scroll_to_bottom': True},
    )
    assert any('scrollHeight' in c for c in calls)
    print('OK test_heimao_scroll_to_bottom')


def test_heimao_first_page_empty_stop():
    es = early_stop_cfg('heimao', {'early_stop': {'enabled': True, 'protect_first_page': True}})
    stop, reason, _ = heimao_should_stop_after_page(es, 1, 5, 0, 0)
    assert stop and reason == 'empty_page'
    stop, reason, _ = heimao_should_stop_after_page(es, 2, 5, 0, 0)
    assert not stop
    print('OK test_heimao_first_page_empty_stop')


def test_heimao_scroll_saturation_stop():
    es = early_stop_cfg('heimao', {'early_stop': {'enabled': True, 'saturation_rounds': 2, 'min_pages': 1}})
    state = {'saturation_rounds': 0, 'prev_item_count': 10}
    stop, _ = xhs_update_saturation(es, state, 2, 100, 0, 10)
    assert not stop
    stop, reason = xhs_update_saturation(es, state, 3, 100, 0, 10)
    assert stop and reason == 'scroll_saturated'
    print('OK test_heimao_scroll_saturation_stop')


def test_heimao_default_end_text():
    es = early_stop_cfg('heimao', {})
    assert '暂无更多' in (es.get('end_texts') or [])
    print('OK test_heimao_default_end_text')


def test_heimao_end_marker_body():
    es = early_stop_cfg('heimao', {})
    from crawl_early_stop import xhs_body_has_end_marker
    assert xhs_body_has_end_marker('列表底部\n暂无更多\n', es)
    assert not xhs_body_has_end_marker('无结束标志', es)
    print('OK test_heimao_end_marker_body')


if __name__ == '__main__':
    test_heimao_scroll_to_bottom()
    test_heimao_first_page_empty_stop()
    test_heimao_scroll_saturation_stop()
    test_heimao_default_end_text()
    test_heimao_end_marker_body()
    print('All heimao scroll tests passed.')
