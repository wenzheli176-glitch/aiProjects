# -*- coding: utf-8 -*-
"""小红书详情：在搜索页点击笔记打开弹窗后抓取（避免直接 goto explore 触发 App 墙）。"""
import json
import random
import time

from config import get_config


def _xhs_cfg():
    return get_config().get('xhs', {})


def _detail_cfg():
    x = _xhs_cfg()
    d = dict(x.get('detail') or {})
    d['modal_root_selectors'] = x.get('detail_modal_root_selectors') or [
        '#noteContainer',
        '.note-detail-mask',
        '[class*="note-detail"]',
        '.reds-modal',
        '[class*="NoteDetail"]',
    ]
    d['modal_scroll_selectors'] = x.get('detail_modal_scroll_selectors') or [
        '#noteContainer .note-scroller',
        '.note-detail .note-scroller',
        '.interaction-container',
        '[class*="note-detail"] [class*="scroll"]',
    ]
    d['modal_close_selectors'] = x.get('detail_modal_close_selectors') or [
        '.close-circle',
        '.close-box',
        '[class*="close"]',
        'div.close',
    ]
    d['app_open_texts'] = x.get('detail_app_open_texts') or [
        'App 内打开', 'APP内打开', '在 App 内打开', '在APP中打开',
        '打开小红书', '前往 App', '扫码下载', '下载小红书',
    ]
    return d


def xhs_page_shows_open_in_app(page):
    texts = _detail_cfg().get('app_open_texts') or []
    try:
        body = (page.inner_text('body') or '')[:12000]
    except Exception:
        body = ''
    for t in texts:
        if t and t in body:
            return True, t
    return False, ''


def xhs_modal_visible(page):
    for sel in _detail_cfg().get('modal_root_selectors') or []:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                return True, sel
        except Exception:
            pass
    return False, ''


def close_xhs_note_modal(page):
    for sel in _detail_cfg().get('modal_close_selectors') or []:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click(timeout=3000)
                time.sleep(0.4)
                return True
        except Exception:
            pass
    try:
        page.keyboard.press('Escape')
        time.sleep(0.3)
        return True
    except Exception:
        return False


def scroll_xhs_modal_content(page):
    sels = _detail_cfg().get('modal_scroll_selectors') or []
    try:
        page.evaluate(
            '''(selectors) => {
            for (var i = 0; i < selectors.length; i++) {
                var el = document.querySelector(selectors[i]);
                if (el) {
                    el.scrollTop = el.scrollHeight;
                    return selectors[i];
                }
            }
            var modal = document.querySelector('#noteContainer')
                || document.querySelector('[class*="note-detail"]');
            if (modal) {
                var nodes = modal.querySelectorAll('[style*="overflow"], .note-scroller');
                for (var j = 0; j < nodes.length; j++) {
                    nodes[j].scrollTop = nodes[j].scrollHeight;
                }
            }
            return '';
        }''',
            sels,
        )
    except Exception:
        pass


def build_xhs_detail_modal_js():
    """在弹窗根节点内提取字段。"""
    d = _detail_cfg()
    roots = json.dumps(d.get('modal_root_selectors') or ['#noteContainer'], ensure_ascii=False)

    def _arr(key, default):
        return json.dumps(d.get(key, default), ensure_ascii=False)

    return (
        '''() => {
    var modalRoots = %s;
    function getRoot() {
        for (var i = 0; i < modalRoots.length; i++) {
            var el = document.querySelector(modalRoots[i]);
            if (el && el.offsetParent !== null) return el;
        }
        return document.body;
    }
    function pick(selectors) {
        var root = getRoot();
        for (var i = 0; i < selectors.length; i++) {
            var el = root.querySelector(selectors[i]);
            if (el) {
                var t = (el.innerText || el.textContent || '').trim();
                if (t) return t;
            }
        }
        return '';
    }
    var result = {
        title: '', content: '', author: '', time: '',
        likes: '', collects: '', comments: '', tags: ''
    };
    var sTitle = %s;
    var sContent = %s;
    var sAuthor = %s;
    var sTime = %s;
    var sLikes = %s;
    var sCollects = %s;
    var sComments = %s;
    var sTags = %s;
    result.title = pick(sTitle);
    result.content = pick(sContent);
    result.author = pick(sAuthor);
    result.time = pick(sTime);
    result.likes = pick(sLikes);
    result.collects = pick(sCollects);
    result.comments = pick(sComments);
    var tags = [];
    var root = getRoot();
    for (var j = 0; j < sTags.length; j++) {
        root.querySelectorAll(sTags[j]).forEach(function(el) {
            var t = (el.innerText || '').trim();
            if (t && tags.indexOf(t) < 0) tags.push(t);
        });
    }
    result.tags = tags.slice(0, 20).join(' ');
    if (!result.title && result.content) result.title = result.content.slice(0, 80);
    return result;
}'''
        % (
            roots,
            _arr('title_selectors', ['#detail-title', '.note-content .title', '.title', 'h1']),
            _arr('content_selectors', ['#detail-desc', '.note-text', '.desc', '.content']),
            _arr('author_selectors', ['.username', '.author-wrapper .name', '.user-name']),
            _arr('time_selectors', ['.date', '.publish-date', '.bottom-container .time']),
            _arr('likes_selectors', ['.like-wrapper .count', '[class*="like"] .count']),
            _arr('collects_selectors', ['.collect-wrapper .count']),
            _arr('comments_selectors', ['.chat-wrapper .count', '[class*="comment"] .count']),
            _arr('tags_selectors', ['#hash-tag', '.tag', 'a.tag']),
        )
    )


def open_xhs_note_modal(page, item, link_selector, open_wait_ms=3500):
    """在列表项上点击打开详情弹窗。"""
    close_xhs_note_modal(page)
    click_el = None
    try:
        click_el = item.query_selector('a.cover, a[href*="/explore/"], ' + link_selector)
    except Exception:
        pass
    if not click_el:
        try:
            click_el = item.query_selector(link_selector) or item
        except Exception:
            click_el = item
    try:
        click_el.scroll_into_view_if_needed(timeout=5000)
    except Exception:
        pass
    time.sleep(0.2)
    try:
        click_el.click(timeout=8000)
    except Exception:
        try:
            item.click(timeout=8000)
        except Exception as e:
            return False, '点击笔记失败: %s' % str(e)[:50]

    deadline = time.time() + open_wait_ms / 1000.0
    while time.time() < deadline:
        app_hit, app_t = xhs_page_shows_open_in_app(page)
        if app_hit:
            return False, '页面提示: %s' % app_t
        vis, sel = xhs_modal_visible(page)
        if vis:
            return True, sel
        time.sleep(0.25)
    app_hit, app_t = xhs_page_shows_open_in_app(page)
    if app_hit:
        return False, '页面提示: %s' % app_t
    return False, '未检测到详情弹窗'


def fetch_xhs_detail_via_modal(page, item, link, log_fn=None):
    """
    从搜索页点击打开弹窗并提取详情。
    返回 (detail_dict, error_msg)；error_msg 非空表示失败。
    """
    x = _xhs_cfg()
    link_selector = x.get('link_selector', 'a[href*="explore"]')
    open_ms = int(x.get('detail_open_wait_ms', 3500))
    wait_min = float(x.get('detail_wait_min', 4))
    wait_max = float(x.get('detail_wait_max', 7))

    ok, info = open_xhs_note_modal(page, item, link_selector, open_ms)
    if not ok:
        if log_fn:
            log_fn('  弹窗打开失败: %s' % info, 'WARN')
        return {}, info

    time.sleep(random.uniform(wait_min, wait_max))
    scroll_xhs_modal_content(page)
    time.sleep(0.5)

    js = build_xhs_detail_modal_js().replace('\r', '')
    try:
        detail = page.evaluate(js) or {}
    except Exception as e:
        close_xhs_note_modal(page)
        return {}, '提取详情失败: %s' % str(e)[:60]

    content_len = len((detail.get('content') or detail.get('title') or '').strip())
    app_hit, app_t = xhs_page_shows_open_in_app(page)

    close_xhs_note_modal(page)

    if app_hit and content_len < 20:
        return detail, '详情为 App 打开提示: %s' % app_t
    if content_len < 10:
        return detail, '弹窗正文过短'
    return detail, ''
