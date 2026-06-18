# -*- coding: utf-8 -*-
"""各数据源 CrawlProfile / NormalizeProfile 可视化编辑白名单。"""
from config import cfg

SOURCE_CRAWL_DEFAULTS = {
    'heimao': 'legacy',
    'xhs': 'list_first',
}

SOURCE_ALLOWED_CRAWL_MODES = {
    'heimao': ('legacy', 'list_first'),
    'xhs': ('list_first',),
}

SOURCE_PROFILE_KEYS = {
    'heimao': [
        'source_name',
        'default_keyword',
        'default_max_pages',
        'default_fetch_detail',
        'base_url',
        'search_url_template',
        'search_input_selector',
        'page_timeout_ms',
        'after_goto_wait',
        'after_search_wait',
        'page_wait_min',
        'page_wait_max',
        'between_pages_min',
        'between_pages_max',
        'detail_wait_min',
        'detail_wait_max',
        'min_link_text_len',
        'min_html_len',
        'title_max_len',
        'early_stop',
    ],
    'xhs': [
        'source_name',
        'default_keyword',
        'default_max_pages',
        'default_fetch_detail',
        'search_url_template',
        'link_host',
        'note_item_selector',
        'link_selector',
        'title_selector',
        'text_selector',
        'time_selector',
        'author_selector',
        'likes_selector',
        'page_timeout_ms',
        'after_goto_wait',
        'scroll_times_per_page',
        'scroll_pixels',
        'scroll_wait_seconds',
        'between_pages_min',
        'between_pages_max',
        'title_max_len',
        'early_stop',
        'investigation_detail',
    ],
}

NORMALIZE_PROFILE_KEYS = {
    'heimao': [
        'include_reply_in_body',
        'include_merchant_in_body',
        'include_problem_in_body',
        'body_max_chars',
        'strip_whitespace',
    ],
    'xhs': [
        'body_max_chars',
        'fallback_title_from_body',
        'include_likes_in_extra',
        'strip_whitespace',
    ],
}

SOURCES_NOTICE = '新增数据源需在代码中注册 CrawlAdapter/NormalizeAdapter，无法仅靠配置添加。'

INVESTIGATION_DETAIL_KEYS = (
    'dom_miss_skip',
    'dom_miss_research_threshold',
    'research_max_scroll_rounds',
    'between_detail_min',
    'between_detail_max',
    'max_modal_per_run',
)


def filter_profile_patch(source_id, data):
    allowed = SOURCE_PROFILE_KEYS.get(source_id) or []
    if not isinstance(data, dict):
        return {}
    out = {k: data[k] for k in allowed if k in data}
    if 'investigation_detail' in data and isinstance(data.get('investigation_detail'), dict):
        inv = data['investigation_detail']
        filtered = {k: inv[k] for k in INVESTIGATION_DETAIL_KEYS if k in inv}
        if filtered:
            out['investigation_detail'] = filtered
    return out


def filter_normalize_patch(source_id, data):
    allowed = NORMALIZE_PROFILE_KEYS.get(source_id) or []
    if not isinstance(data, dict):
        return {}
    return {k: data[k] for k in allowed if k in data}


def extract_profile(source_id, config_node):
    allowed = SOURCE_PROFILE_KEYS.get(source_id) or []
    node = config_node if isinstance(config_node, dict) else {}
    return {k: node.get(k) for k in allowed if k in node}


def extract_normalize_profile(source_id, config_node):
    allowed = NORMALIZE_PROFILE_KEYS.get(source_id) or []
    node = config_node if isinstance(config_node, dict) else {}
    norm = node.get('normalize') if isinstance(node.get('normalize'), dict) else {}
    return {k: norm.get(k) for k in allowed if k in norm}


def resolve_source_crawl_mode(source_id, task=None):
    """源级 crawl_mode；xhs 强制 list_first。仅 heimao 单源任务可读 task.crawl_mode fallback。"""
    allowed = SOURCE_ALLOWED_CRAWL_MODES.get(source_id, ('legacy', 'list_first'))
    if source_id == 'xhs':
        return 'list_first'
    if task and source_id == 'heimao':
        sources = task.get('sources') or []
        if len(sources) == 1 and sources[0] == 'heimao':
            task_mode = task.get('crawl_mode')
            if task_mode in allowed:
                return task_mode
    src = cfg('sources', source_id) or {}
    mode = src.get('crawl_mode')
    if mode in allowed:
        return mode
    return SOURCE_CRAWL_DEFAULTS.get(source_id, 'legacy')


def crawl_modes_for_task(task):
    sources = task.get('sources') or []
    return {sid: resolve_source_crawl_mode(sid, task) for sid in sources}


def task_uses_shared_pool(task):
    return any(m == 'list_first' for m in crawl_modes_for_task(task).values())


def validate_crawl_mode_patch(source_id, crawl_mode):
    if source_id == 'xhs' and crawl_mode != 'list_first':
        return False, '小红书仅支持 list_first'
    allowed = SOURCE_ALLOWED_CRAWL_MODES.get(source_id, ('legacy', 'list_first'))
    if crawl_mode not in allowed:
        return False, '无效 crawl_mode: %s' % crawl_mode
    return True, ''
