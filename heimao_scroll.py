# -*- coding: utf-8 -*-
"""黑猫投诉搜索结果：下拉滚动加载更多。"""
import time


def _log(log_fn, msg, level='INFO'):
    if log_fn:
        log_fn(msg, level)


def heimao_scroll_load_batch(page, h, log_fn=None):
    """在当前搜索结果页滚动若干次，触发下拉加载。返回滚动次数。"""
    times = max(1, int(h.get('scroll_times_per_page', 3) or 3))
    wait = float(h.get('scroll_wait_seconds', 2) or 2)
    pixels = int(h.get('scroll_pixels', 1500) or 1500)
    to_bottom = h.get('scroll_to_bottom', True)
    container = (h.get('scroll_container_selector') or '').strip()

    for _ in range(times):
        if container:
            page.evaluate(
                '''(sel) => {
                    const el = document.querySelector(sel);
                    if (el) { el.scrollTop = el.scrollHeight; }
                    else { window.scrollTo(0, document.body.scrollHeight); }
                }''',
                container,
            )
        elif to_bottom:
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        else:
            page.evaluate('window.scrollBy(0, %d)' % pixels)
        time.sleep(wait)

    _log(log_fn, '黑猫下拉加载: %d 次滚动' % times)
    return times
