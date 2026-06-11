# -*- coding: utf-8 -*-
"""各数据源 CrawlProfile / NormalizeProfile 可视化编辑白名单。"""
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


def filter_profile_patch(source_id, data):
    allowed = SOURCE_PROFILE_KEYS.get(source_id) or []
    if not isinstance(data, dict):
        return {}
    return {k: data[k] for k in allowed if k in data}


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
