# -*- coding: utf-8 -*-
"""黑猫空搜索分类单元测试（无浏览器）。"""
import os
import sys
from unittest.mock import MagicMock, patch

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)


def _mock_page():
    page = MagicMock()
    page.url = 'https://tousu.sina.com.cn/'
    page.evaluate.return_value = False
    return page


def _html_with_link():
    return (
        '<a href="https://tousu.sina.com.cn/complaint/view/123/?sid=abc">'
        '这是一条足够长的投诉标题用于测试链接计数'
        '</a>'
    )


def _html_empty():
    return '<html><body><div>暂无相关投诉</div></body></html>' * 50


@patch('login_gate.heimao_page_shows_login_prompt', return_value=False)
@patch('login_gate._page_has_login_fail_text', return_value=(False, ''))
@patch('login_gate.heimao_browser_has_weibo_session', return_value=True)
@patch('login_gate.extract_heimao_sid', return_value='')
def test_empty_uncertain_sub_ok_no_login(_sid, _sub, _fail, _prompt):
    from login_gate import heimao_classify_empty_search

    kind = heimao_classify_empty_search(MagicMock(), _mock_page(), _html_empty())
    assert kind == 'empty_uncertain'
    print('OK test_empty_uncertain_sub_ok_no_login')


@patch('login_gate.heimao_page_shows_login_prompt', return_value=False)
@patch('login_gate._page_has_login_fail_text', return_value=(False, ''))
@patch('login_gate.heimao_browser_has_weibo_session', return_value=False)
@patch('login_gate.extract_heimao_sid', return_value='')
def test_auth_required_no_sub(_sid, _sub, _fail, _prompt):
    from login_gate import heimao_classify_empty_search

    kind = heimao_classify_empty_search(MagicMock(), _mock_page(), _html_empty())
    assert kind == 'auth_required'
    print('OK test_auth_required_no_sub')


@patch('login_gate.extract_heimao_sid', return_value='sess123')
def test_no_results_with_sid(_sid):
    from login_gate import heimao_classify_empty_search

    kind = heimao_classify_empty_search(MagicMock(), _mock_page(), _html_empty())
    assert kind == 'no_results'
    print('OK test_no_results_with_sid')


@patch('login_gate.heimao_empty_search_cfg', return_value={'login_on_missing_sid': True})
@patch('login_gate.heimao_page_shows_login_prompt', return_value=False)
@patch('login_gate._page_has_login_fail_text', return_value=(False, ''))
@patch('login_gate.heimao_browser_has_weibo_session', return_value=True)
@patch('login_gate.extract_heimao_sid', return_value='')
def test_login_on_missing_sid_legacy(_sid, _sub, _fail, _prompt, _cfg):
    from login_gate import heimao_classify_empty_search

    kind = heimao_classify_empty_search(MagicMock(), _mock_page(), _html_empty())
    assert kind == 'auth_required'
    print('OK test_login_on_missing_sid_legacy')


@patch('login_gate.wait_for_site_login')
def test_skip_path_no_wait(mock_wait):
    from login_gate import heimao_wait_if_search_empty

    runtime = MagicMock()
    runtime.log = lambda msg, level='INFO': None
    with patch('login_gate.heimao_classify_empty_search', return_value='empty_uncertain'):
        ok = heimao_wait_if_search_empty(MagicMock(), _mock_page(), _html_empty(), '测试公司', runtime)
    assert ok is True
    mock_wait.assert_not_called()
    print('OK test_skip_path_no_wait')


def test_has_results():
    from login_gate import heimao_classify_empty_search

    kind = heimao_classify_empty_search(MagicMock(), _mock_page(), _html_with_link())
    assert kind == 'has_results'
    print('OK test_has_results')


if __name__ == '__main__':
    test_has_results()
    test_empty_uncertain_sub_ok_no_login()
    test_auth_required_no_sub()
    test_no_results_with_sid()
    test_login_on_missing_sid_legacy()
    test_skip_path_no_wait()
    print('All heimao empty search classify tests passed.')
