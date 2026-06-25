# -*- coding: utf-8 -*-
"""配置加载、保存与路径解析。"""
import copy
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')
LOCAL_CONFIG_PATH = os.path.join(BASE_DIR, 'config.local.json')

DEFAULT_CONFIG = {
    'server': {
        'host': '0.0.0.0',
        'port': 5000,
    },
    'app': {
        'timezone': 'Asia/Shanghai',
    },
    'chrome': {
        'exe_path': r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        'cdp_port': 9222,
        'profile_dir': 'chrome_heimao_profile',
        'startup_url': 'https://tousu.sina.com.cn/',
        'extra_args': [
            '--remote-allow-origins=*',
            '--no-first-run',
            '--no-default-browser-check',
        ],
        'kill_all_chrome_before_start': False,
        'kill_process_name': 'chrome.exe',
        'kill_wait_seconds': 3,
        'startup_wait_seconds': 30,
        'ready_extra_wait_seconds': 2,
        'cdp_check_timeout': 3,
        'cdp_http_timeout': 2,
    },
    'paths': {
        'output_dir': '',
    },
    'logging': {
        'max_logs': 300,
        'status_log_count': 30,
    },
    'auth': {
        'heimao': {
            'login_url': 'https://tousu.sina.com.cn/',
            'weibo_login_url': (
                'https://passport.weibo.com/sso/signin?entry=general&source=heimao&url='
                'https%3A%2F%2Ftousu.sina.com.cn%2F'
            ),
            'login_check_url': 'https://tousu.sina.com.cn/',
            'login_ok_selector': 'input[placeholder*="搜索"]',
            'login_fail_texts': ['请登录', '登录后查看', '立即登录'],
            'cookies_file': 'credentials/heimao_cookies.json',
            'cookies': [],
            'cookies_text': '',
            'domain': '.sina.com.cn',
            'use_profile_only': False,
            'cookie_export_urls': [
                'https://tousu.sina.com.cn/',
                'https://weibo.com/',
                'https://passport.weibo.cn/',
                'https://passport.weibo.com/',
            ],
            'cookie_export_domains': [
                '.sina.com.cn',
                '.weibo.com',
                '.weibo.cn',
                '.passport.weibo.com',
                '.passport.weibo.cn',
            ],
            'required_cookie_names': [],
            'check_timeout_ms': 20000,
            'require_login': False,
            'wait_timeout_sec': 300,
            'poll_interval_sec': 3,
            'auto_export_after_login': True,
            'detail_probe_enabled': True,
            'detail_probe_url': '',
            'detail_probe_wait_sec': 2,
            'skip_inject_if_browser_logged_out': True,
        },
        'xhs': {
            'login_url': 'https://www.xiaohongshu.com/',
            'login_check_url': 'https://www.xiaohongshu.com/explore',
            'login_ok_selector': '#global > div.header-container',
            'login_fail_texts': [
                '登录后查看', '扫码登录', '手机号登录', '马上登录',
                '登录探索', '立即登录', '请先登录', '登录解锁',
            ],
            'cookies_file': 'credentials/xhs_cookies.json',
            'cookies': [],
            'cookies_text': '',
            'domain': '.xiaohongshu.com',
            'use_profile_only': False,
            'cookie_export_urls': [
                'https://www.xiaohongshu.com/',
            ],
            'required_cookie_names': ['web_session', 'webId'],
            'check_timeout_ms': 20000,
            'require_login': False,
            'skip_inject_if_browser_logged_out': True,
            'wait_timeout_sec': 300,
            'poll_interval_sec': 3,
            'auto_export_after_login': True,
            'detail_probe_min_content_len': 20,
        },
    },
    'heimao': {
        'source_name': '黑猫投诉',
        'default_keyword': '小米',
        'default_max_pages': 2,
        'default_fetch_detail': True,
        'base_url': 'https://tousu.sina.com.cn/',
        'search_url_template': 'https://tousu.sina.com.cn/index/search/?keywords={keyword}&t={page}',
        'search_input_selector': 'input[placeholder*="搜索"]',
        'link_regex': r'<a\s+[^>]*href="([^"]*tousu\.sina\.com\.cn/complaint/view/[^"]*)"[^>]*>(.*?)</a>',
        'min_link_text_len': 15,
        'min_html_len': 1000,
        'page_timeout_ms': 30000,
        'after_goto_wait': 2,
        'after_search_wait': 5,
        'page_wait_min': 3,
        'page_wait_max': 5,
        'between_pages_min': 3,
        'between_pages_max': 6,
        'detail_wait_min': 5,
        'detail_wait_max': 8,
        'partner_timeout_sec': 3600,
        'typing_delay_min': 80,
        'typing_delay_max': 150,
        'title_max_len': 100,
        'list_title_preview_len': 40,
        'normalize': {
            'include_reply_in_body': True,
            'include_merchant_in_body': True,
            'include_problem_in_body': True,
            'body_max_chars': 0,
            'strip_whitespace': True,
        },
        'parse_strip_text': '于黑猫投诉平台发起',
        'parse_demand_pattern': r'\[投诉要求\]([^\[]+)',
        'early_stop': {
            'enabled': True,
            'min_pages': 1,
            'empty_pages_threshold': 1,
            'protect_first_page': True,
            'empty_page_retry': 0,
        },
        'empty_search': {
            'login_on_missing_sid': False,
        },
        'detail': {
            'author_cats': ['机灵喵', '洞察喵', '友爱喵', '正义喵', '勇敢喵', '诚实喵'],
            'time_keyword': '发布于',
            'time_slice_len': 30,
            'get_after_max_len': 200,
            'merchant_keyword': '投诉对象',
            'problem_keyword': '投诉问题',
            'demand_keyword': '投诉要求',
            'amount_keyword': '涉诉金额',
            'status_done': '投诉已完成',
            'status_done_label': '已完成',
            'status_replied': '已回复',
            'status_replied_label': '已回复',
            'status_processing': '处理中',
            'status_processing_label': '处理中',
            'content_start': '于黑猫投诉平台发起',
            'content_start_offset': 15,
            'content_end_markers': ['声明', '未经授权'],
            'content_max_fallback': 3000,
            'reply_start': '解决方案',
            'reply_end': '申请完成',
            'reply_max_fallback': 500,
            'reply_trim_prefix': 3,
        },
    },
    'xhs': {
        'source_name': '小红书',
        'default_keyword': '小米',
        'default_max_pages': 3,
        'default_fetch_detail': True,
        'search_url_template': 'https://www.xiaohongshu.com/search_result?keyword={keyword}&type=1',
        'link_host': 'https://www.xiaohongshu.com',
        'note_item_selector': '.note-item',
        'link_selector': 'a[href*="explore"]',
        'title_selector': '.title',
        'text_selector': '.text',
        'time_selector': '.author .time',
        'author_selector': '.author .name',
        'likes_selector': '.count',
        'scroll_times_per_page': 3,
        'scroll_pixels': 1500,
        'scroll_wait_seconds': 2,
        'page_timeout_ms': 30000,
        'after_goto_wait': 5,
        'search_results_wait_ms': 12000,
        'between_pages_min': 5,
        'between_pages_max': 10,
        'title_max_len': 100,
        'title_preview_len': 40,
        'normalize': {
            'body_max_chars': 0,
            'fallback_title_from_body': True,
            'include_likes_in_extra': True,
            'strip_whitespace': True,
        },
        'detail_wait_min': 4,
        'detail_wait_max': 7,
        'investigation_detail': {
            'dom_miss_skip': True,
            'dom_miss_research_threshold': 3,
            'research_max_scroll_rounds': 2,
            'between_detail_min': 4,
            'between_detail_max': 7,
            'max_modal_per_run': 200,
        },
        'keyword_timeout_sec': 3600,
        'early_stop': {
            'enabled': True,
            'min_pages': 1,
            'protect_first_page': True,
            'end_texts': ['- THE END -', 'THE END'],
            'end_selectors': [],
            'saturation_rounds': 2,
        },
        'detail_open_wait_ms': 3500,
        'detail_modal_root_selectors': [
            '#noteContainer', '.note-detail-mask', '[class*="note-detail"]', '.reds-modal',
        ],
        'detail_modal_scroll_selectors': [
            '#noteContainer .note-scroller', '.interaction-container',
        ],
        'detail_modal_close_selectors': ['.close-circle', '.close-box'],
        'detail_app_open_texts': [
            'App 内打开', '在 App 内打开', '打开小红书', '前往 App', '扫码下载',
        ],
        'detail': {
            'title_selectors': ['#detail-title', '.note-content .title', '.title', 'h1'],
            'content_selectors': ['#detail-desc', '.note-text', '.desc', '.content'],
            'author_selectors': ['.username', '.author-wrapper .name', '.user-name'],
            'time_selectors': ['.date', '.publish-date', '.bottom-container .time'],
            'likes_selectors': ['.like-wrapper .count', '[class*="like"] .count'],
            'collects_selectors': ['.collect-wrapper .count'],
            'comments_selectors': ['.chat-wrapper .count', '[class*="comment"] .count'],
            'tags_selectors': ['#hash-tag', '.tag', 'a.tag'],
        },
    },
    'export': {
        'csv_header': '序号,标题,商家,问题,金额,时间,状态,诉求,投诉内容,商家回复,链接',
        'content_max_len': 500,
        'reply_max_len': 300,
        'txt_fields': ['merchant', 'problem', 'amount', 'time', 'status', 'demand', 'author', 'content', 'reply'],
    },
    'database': {
        'path': 'data/intel.db',
    },
    'sources': {
        'heimao': {
            'enabled': True,
            'label': '黑猫投诉',
            'crawl_mode': 'list_first',
            'allowed_crawl_modes': ['legacy', 'list_first'],
        },
        'xhs': {
            'enabled': True,
            'label': '小红书',
            'crawl_mode': 'list_first',
            'allowed_crawl_modes': ['list_first'],
        },
    },
    'monitor': {
        'default_sources': ['heimao', 'xhs'],
        'default_max_pages': 2,
        'task_timeout_sec': 7200,
        'analysis_timeout_sec': 3600,
        'min_crawl_timeout_sec': 1800,
        'scheduler_enabled': True,
        'scheduler_timezone': 'Asia/Shanghai',
        'crawl_mode': 'list_first',
        'industry_batch_max_keywords': 5,
        'priority_quota': {'P0': 0.5, 'P1': 0.3, 'P2': 0.2},
        'run_state': {
            'claim_timeout_sec': 600,
            'heartbeat_interval_sec': 30,
        },
        'workers': {
            'enabled': False,
            'max_workers_total': 4,
            'heimao': {
                'instances': [{
                    'instance_id': 'heimao-0',
                    'cdp_port': 9222,
                    'user_data_dir': 'chrome_heimao_profile',
                    'cookies_file': 'credentials/heimao_cookies.json',
                }],
            },
            'xhs': {
                'max_instances': 1,
                'instances': [{
                    'instance_id': 'xhs-0',
                    'cdp_port': 9230,
                    'user_data_dir': 'chrome_profiles/xhs_0',
                    'cookies_file': 'credentials/xhs_cookies.json',
                }],
            },
        },
        'xhs_credential_pool': {
            'min_accounts': 2,
            'login_cdp_port_base': 9250,
            'login_wait_timeout_sec': 600,
        },
    },
    'analysis': {
        'provider': 'minimax',
        'endpoint': 'https://api.minimaxi.com/v1/chat/completions',
        'endpoint_intl': 'https://api.minimax.io/v1/chat/completions',
        'model': 'MiniMax-M3',
        'api_key_env': 'MINIMAX_API_KEY',
        'api_key': '',
        'prompt_version': 'v1-high-recall-minimax-m3',
        'active_prompt_id': 'default-high-recall',
        'batch_size': 10,
        'parallel_batches': 5,
        'max_body_chars': 2000,
        'max_retries': 2,
        'retry_delay_sec': 2,
        'temperature': 0.3,
        'timeout_sec': 180,
        'mock_without_key': False,
        'mock_default_relevance': 'medium',
        'recency': {
            'enabled': True,
            'downgrade_days_high_to_medium': 30,
            'downgrade_days_medium_to_low': 90,
            'confidence_downgrade_threshold': 0.4,
        },
        'system_prompt': '',
        'extra_body': {
            'reasoning_split': True,
        },
        'list_triage': {
            'enabled': True,
            'model': 'MiniMax-M3',
            'batch_size': 20,
            'max_body_chars': 400,
            'investigation_threshold': {
                'min_relevance': 'medium',
                'min_risk_hint': 'elevated',
            },
        },
        'partner_cohort_suggest': {
            'enabled': True,
            'model': 'MiniMax-M3',
            'max_candidates': 5,
            'web_search_enabled': True,
            'web_search_max_results': 3,
            'mock_without_key': False,
            'timeout_sec': 60,
        },
    },
    'intel': {
        'schema_version': '1.1',
    },
    'admin': {
        'enabled': True,
        'password_env': 'ADMIN_PASSWORD',
        'password_hash': '',
        'session_secret_env': 'ADMIN_SESSION_SECRET',
        'session_secret': '',
        'session_ttl_hours': 8,
    },
}

_config = None
_config_lock = None


def _get_lock():
    global _config_lock
    if _config_lock is None:
        import threading
        _config_lock = threading.RLock()
    return _config_lock


def _deep_merge(base, override):
    out = copy.deepcopy(base)
    if not isinstance(override, dict):
        return out
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _resolve_paths(cfg):
    c = copy.deepcopy(cfg)
    profile = c['chrome'].get('profile_dir') or 'chrome_heimao_profile'
    if not os.path.isabs(profile):
        profile = os.path.join(BASE_DIR, profile)
    c['chrome']['profile_dir_resolved'] = profile

    out = c['paths'].get('output_dir') or ''
    if not out:
        out = BASE_DIR
    elif not os.path.isabs(out):
        out = os.path.join(BASE_DIR, out)
    c['paths']['output_dir_resolved'] = out

    db_path = c.get('database', {}).get('path') or 'data/intel.db'
    if not os.path.isabs(db_path):
        db_path = os.path.join(BASE_DIR, db_path)
    c.setdefault('database', {})['path_resolved'] = db_path

    port = int(c['chrome'].get('cdp_port', 9222))
    c['chrome']['cdp_url'] = 'http://127.0.0.1:%d' % port
    return c


def load_config(force=False):
    global _config
    with _get_lock():
        if _config is not None and not force:
            return _config
        merged = copy.deepcopy(DEFAULT_CONFIG)
        if os.path.isfile(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    file_cfg = json.load(f)
                merged = _deep_merge(merged, file_cfg)
            except Exception:
                pass
        if os.path.isfile(LOCAL_CONFIG_PATH):
            try:
                with open(LOCAL_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    local_cfg = json.load(f)
                merged = _deep_merge(merged, local_cfg)
            except Exception:
                pass
        _config = _resolve_paths(merged)
        return _config


def save_config(updates):
    with _get_lock():
        current = load_config(force=True)
        plain = copy.deepcopy(current)
        for key in ('profile_dir_resolved',):
            plain['chrome'].pop(key, None)
        plain['paths'].pop('output_dir_resolved', None)
        plain['chrome'].pop('cdp_url', None)
        if isinstance(plain.get('database'), dict):
            plain['database'].pop('path_resolved', None)

        merged = _deep_merge(plain, updates or {})
        os.makedirs(os.path.dirname(CONFIG_PATH) or BASE_DIR, exist_ok=True)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)

        global _config
        _config = _resolve_paths(merged)
        return _config


def get_config():
    return load_config()


def cfg(*keys, default=None):
    """按点分路径取值，例如 cfg('heimao', 'base_url')"""
    node = load_config()
    for k in keys:
        if not isinstance(node, dict) or k not in node:
            return default
        node = node[k]
    return node


def build_heimao_detail_js():
    d = cfg('heimao', 'detail') or {}
    cats = json.dumps(d.get('author_cats', []), ensure_ascii=False)
    tpl = """() => {
    var body = document.body.innerText;
    var result = {title:'',content:'',demand:'',merchant:'',problem:'',amount:'',reply:'',author:'',time:'',status:'',comments:''};
    var cats = __CATS__;
    for (var i=0; i<cats.length; i++) {
        if (body.indexOf(cats[i]) >= 0) { result.author = cats[i]; break; }
    }
    function getAfter(kw) {
        var idx = body.indexOf(kw);
        if (idx < 0) return '';
        var s = idx + kw.length;
        var e = body.indexOf('\\n', s);
        if (e < 0) e = s + __GET_AFTER_MAX__;
        return body.substring(s, e).trim();
    }
    var tIdx = body.indexOf('__TIME_KW__');
    if (tIdx >= 0) result.time = body.substring(tIdx, tIdx+__TIME_SLICE__).trim();
    result.merchant = getAfter('__MERCHANT__');
    result.problem = getAfter('__PROBLEM__');
    result.demand = getAfter('__DEMAND__');
    result.amount = getAfter('__AMOUNT__');
    if (body.indexOf('__STATUS_DONE__') >= 0) result.status = '__STATUS_DONE_LABEL__';
    else if (body.indexOf('__STATUS_REPLIED__') >= 0) result.status = '__STATUS_REPLIED_LABEL__';
    else if (body.indexOf('__STATUS_PROC__') >= 0) result.status = '__STATUS_PROC_LABEL__';
    var cIdx = body.indexOf('__CONTENT_START__');
    if (cIdx >= 0) {
        var cEnd = body.indexOf('__CONTENT_END0__', cIdx+__CONTENT_OFFSET__);
        if (cEnd < 0) cEnd = body.indexOf('__CONTENT_END1__', cIdx+__CONTENT_OFFSET__);
        if (cEnd < 0) cEnd = Math.min(cIdx+__CONTENT_MAX__, body.length);
        result.content = body.substring(cIdx+__CONTENT_OFFSET__, cEnd).trim();
    }
    var rIdx = body.indexOf('__REPLY_START__');
    if (rIdx >= 0) {
        var rEnd = body.indexOf('__REPLY_END__', rIdx);
        if (rEnd < 0) rEnd = Math.min(rIdx+__REPLY_MAX__, body.length);
        result.reply = body.substring(rIdx, rEnd).trim().substring(__REPLY_TRIM__);
    }
    return result;
}"""
    ends = d.get('content_end_markers', ['声明', '未经授权'])
    replacements = {
        '__CATS__': cats,
        '__GET_AFTER_MAX__': str(int(d.get('get_after_max_len', 200))),
        '__TIME_KW__': d.get('time_keyword', '发布于'),
        '__TIME_SLICE__': str(int(d.get('time_slice_len', 30))),
        '__MERCHANT__': d.get('merchant_keyword', '投诉对象'),
        '__PROBLEM__': d.get('problem_keyword', '投诉问题'),
        '__DEMAND__': d.get('demand_keyword', '投诉要求'),
        '__AMOUNT__': d.get('amount_keyword', '涉诉金额'),
        '__STATUS_DONE__': d.get('status_done', '投诉已完成'),
        '__STATUS_DONE_LABEL__': d.get('status_done_label', '已完成'),
        '__STATUS_REPLIED__': d.get('status_replied', '已回复'),
        '__STATUS_REPLIED_LABEL__': d.get('status_replied_label', '已回复'),
        '__STATUS_PROC__': d.get('status_processing', '处理中'),
        '__STATUS_PROC_LABEL__': d.get('status_processing_label', '处理中'),
        '__CONTENT_START__': d.get('content_start', '于黑猫投诉平台发起'),
        '__CONTENT_OFFSET__': str(int(d.get('content_start_offset', 15))),
        '__CONTENT_END0__': ends[0] if len(ends) > 0 else '声明',
        '__CONTENT_END1__': ends[1] if len(ends) > 1 else '未经授权',
        '__CONTENT_MAX__': str(int(d.get('content_max_fallback', 3000))),
        '__REPLY_START__': d.get('reply_start', '解决方案'),
        '__REPLY_END__': d.get('reply_end', '申请完成'),
        '__REPLY_MAX__': str(int(d.get('reply_max_fallback', 500))),
        '__REPLY_TRIM__': str(int(d.get('reply_trim_prefix', 3))),
    }
    for k, v in replacements.items():
        tpl = tpl.replace(k, v)
    return tpl


def build_xhs_detail_js():
    d = cfg('xhs', 'detail') or {}

    def _arr(key, default):
        return json.dumps(d.get(key, default), ensure_ascii=False)

    tpl = """() => {
    function pick(selectors) {
        for (var i = 0; i < selectors.length; i++) {
            var el = document.querySelector(selectors[i]);
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
    var sTitle = __TITLE_SEL__;
    var sContent = __CONTENT_SEL__;
    var sAuthor = __AUTHOR_SEL__;
    var sTime = __TIME_SEL__;
    var sLikes = __LIKES_SEL__;
    var sCollects = __COLLECTS_SEL__;
    var sComments = __COMMENTS_SEL__;
    var sTags = __TAGS_SEL__;
    result.title = pick(sTitle);
    result.content = pick(sContent);
    result.author = pick(sAuthor);
    result.time = pick(sTime);
    result.likes = pick(sLikes);
    result.collects = pick(sCollects);
    result.comments = pick(sComments);
    var tags = [];
    for (var j = 0; j < sTags.length; j++) {
        document.querySelectorAll(sTags[j]).forEach(function(el) {
            var t = (el.innerText || '').trim();
            if (t && tags.indexOf(t) < 0) tags.push(t);
        });
    }
    result.tags = tags.slice(0, 20).join(' ');
    if (!result.content) {
        var meta = document.querySelector('meta[name="description"]');
        if (meta && meta.content) result.content = meta.content.trim();
    }
    if (!result.title && result.content) result.title = result.content.slice(0, 80);
    return result;
}"""
    replacements = {
        '__TITLE_SEL__': _arr('title_selectors', ['#detail-title', '.title']),
        '__CONTENT_SEL__': _arr('content_selectors', ['#detail-desc', '.note-text', '.desc']),
        '__AUTHOR_SEL__': _arr('author_selectors', ['.username', '.author-wrapper .name']),
        '__TIME_SEL__': _arr('time_selectors', ['.date', '.publish-date']),
        '__LIKES_SEL__': _arr('likes_selectors', ['.like-wrapper .count']),
        '__COLLECTS_SEL__': _arr('collects_selectors', ['.collect-wrapper .count']),
        '__COMMENTS_SEL__': _arr('comments_selectors', ['.chat-wrapper .count']),
        '__TAGS_SEL__': _arr('tags_selectors', ['#hash-tag', '.tag']),
    }
    for k, v in replacements.items():
        tpl = tpl.replace(k, v)
    return tpl
