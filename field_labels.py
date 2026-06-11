# -*- coding: utf-8 -*-
"""全站配置字段中文标签注册表。UI 展示「中文（english_key）」。"""

# group: crawl | normalize | analysis | auth | server | intel | monitor | monitor_run


def _entry(label, group='crawl', field_type='text', help_text=''):
    return {'label': label, 'group': group, 'type': field_type, 'help': help_text}


FIELD_LABELS = {
    # --- crawl / heimao & xhs shared ---
    'source_name': _entry('来源名称', 'crawl'),
    'default_keyword': _entry('默认关键词', 'crawl'),
    'default_max_pages': _entry('默认采集页数', 'crawl', 'number'),
    'default_fetch_detail': _entry('默认抓取详情', 'crawl', 'checkbox'),
    'page_timeout_ms': _entry('页面超时', 'crawl', 'number', '毫秒'),
    'after_goto_wait': _entry('打开页等待', 'crawl', 'number', '秒'),
    'after_search_wait': _entry('搜索后等待', 'crawl', 'number', '秒'),
    'page_wait_min': _entry('翻页等待下限', 'crawl', 'number', '秒'),
    'page_wait_max': _entry('翻页等待上限', 'crawl', 'number', '秒'),
    'between_pages_min': _entry('页间间隔下限', 'crawl', 'number', '秒'),
    'between_pages_max': _entry('页间间隔上限', 'crawl', 'number', '秒'),
    'title_max_len': _entry('标题最大长度', 'crawl', 'number'),
    'base_url': _entry('首页 URL', 'crawl'),
    'search_url_template': _entry('搜索 URL 模板', 'crawl', 'text', '占位符: {keyword} {page}'),
    'search_input_selector': _entry('搜索框选择器', 'crawl'),
    'link_regex': _entry('列表链接正则', 'crawl'),
    'detail_wait_min': _entry('详情等待下限', 'crawl', 'number', '秒'),
    'detail_wait_max': _entry('详情等待上限', 'crawl', 'number', '秒'),
    'min_link_text_len': _entry('链接最短文本', 'crawl', 'number'),
    'min_html_len': _entry('HTML 最短长度', 'crawl', 'number'),
    'link_host': _entry('链接域名', 'crawl'),
    'note_item_selector': _entry('笔记项选择器', 'crawl'),
    'link_selector': _entry('链接选择器', 'crawl'),
    'title_selector': _entry('标题选择器', 'crawl'),
    'text_selector': _entry('正文选择器', 'crawl'),
    'time_selector': _entry('时间选择器', 'crawl'),
    'author_selector': _entry('作者选择器', 'crawl'),
    'likes_selector': _entry('点赞选择器', 'crawl'),
    'scroll_times_per_page': _entry('每页滚动次数', 'crawl', 'number'),
    'scroll_pixels': _entry('每次滚动像素', 'crawl', 'number'),
    'scroll_wait_seconds': _entry('滚动后等待', 'crawl', 'number', '秒'),
    # --- normalize ---
    'include_reply_in_body': _entry('正文含回复', 'normalize', 'checkbox'),
    'include_merchant_in_body': _entry('正文含商户', 'normalize', 'checkbox'),
    'include_problem_in_body': _entry('正文含问题描述', 'normalize', 'checkbox'),
    'body_max_chars': _entry('正文最大字符', 'normalize', 'number', '0 表示不截断'),
    'strip_whitespace': _entry('合并空行', 'normalize', 'checkbox'),
    'fallback_title_from_body': _entry('无标题时用正文前缀', 'normalize', 'checkbox'),
    'include_likes_in_extra': _entry('extra 含点赞数', 'normalize', 'checkbox'),
    # --- analysis ---
    'provider': _entry('服务商', 'analysis'),
    'endpoint': _entry('API Endpoint（国内）', 'analysis'),
    'endpoint_intl': _entry('API Endpoint（国际）', 'analysis'),
    'model': _entry('模型名称', 'analysis'),
    'prompt_version': _entry('Prompt 版本标识', 'analysis'),
    'api_key_env': _entry('API Key 环境变量', 'analysis'),
    'api_key': _entry('API Key', 'analysis', 'password'),
    'batch_size': _entry('批大小', 'analysis', 'number'),
    'max_body_chars': _entry('正文最大字符', 'analysis', 'number'),
    'max_retries': _entry('失败重试次数', 'analysis', 'number'),
    'retry_delay_sec': _entry('重试间隔', 'analysis', 'number', '秒'),
    'temperature': _entry('Temperature', 'analysis', 'number'),
    'timeout_sec': _entry('请求超时', 'analysis', 'number', '秒'),
    'mock_without_key': _entry('无 Key 时 Mock', 'analysis', 'checkbox'),
    'mock_default_relevance': _entry('Mock 默认相关度', 'analysis'),
    'extra_body': _entry('扩展参数 extra_body', 'analysis'),
    'system_prompt': _entry('System Prompt', 'analysis'),
    'active_prompt_id': _entry('活跃 Prompt 模板', 'analysis'),
    # --- server / chrome ---
    'host': _entry('Web 监听地址', 'server'),
    'port': _entry('Web 端口', 'server', 'number'),
    'exe_path': _entry('Chrome 路径', 'server'),
    'cdp_port': _entry('CDP 调试端口', 'server', 'number'),
    'profile_dir': _entry('Chrome 用户目录', 'server'),
    'startup_url': _entry('Chrome 启动页', 'server'),
    'output_dir': _entry('导出目录', 'server'),
    'max_logs': _entry('日志保留条数', 'server', 'number'),
    # --- intel table headers ---
    'published_at': _entry('发布时间', 'intel'),
    'captured_at': _entry('采集时间', 'intel'),
    'analyzed_at': _entry('生成时间', 'intel'),
    'partner_name': _entry('合作方', 'intel'),
    'relevance': _entry('相关度', 'intel'),
    'sentiment_label': _entry('情感', 'intel'),
    'risk_types': _entry('风险类型', 'intel'),
    'summary': _entry('摘要', 'intel'),
    'url': _entry('链接', 'intel'),
    # --- monitor ---
    'task_timeout_sec': _entry('任务超时', 'monitor', 'number', '秒'),
    'default_sources': _entry('默认来源', 'monitor'),
    'scheduler_enabled': _entry('启用调度器', 'monitor', 'boolean'),
    'scheduler_timezone': _entry('调度时区', 'monitor'),
    'schedule_enabled': _entry('启用定时', 'monitor', 'boolean'),
    'schedule_frequency': _entry('执行频率', 'monitor'),
    'schedule_time': _entry('执行时间', 'monitor'),
    'schedule_weekdays': _entry('执行星期', 'monitor'),
    # --- monitor_run (monitor_task_runs) ---
    'trigger': _entry('触发方式', 'monitor_run', 'text', 'manual=手动执行，schedule=定时触发'),
    'analyze_mode': _entry('分析模式', 'monitor_run', 'text', 'incremental=增量，full_replace=全量重分析'),
    'status': _entry('Run 状态', 'monitor_run', 'text', 'running/done/failed/skipped_overlap'),
    'started_at': _entry('开始时间', 'monitor_run'),
    'finished_at': _entry('结束时间', 'monitor_run'),
    'crawl_duration_ms': _entry('爬取阶段耗时', 'monitor_run', 'number', '毫秒，各 source crawl 之和的 wall time'),
    'analyze_duration_ms': _entry('分析阶段耗时', 'monitor_run', 'number', '毫秒，LLM 批次 wall time'),
    'error_message': _entry('错误信息', 'monitor_run', 'text', '失败或跳过时摘要'),
    'raw_new': _entry('新增 Raw', 'monitor_run', 'number', '本次 run 新入库的 raw 条数'),
    'raw_updated': _entry('更新 Raw', 'monitor_run', 'number', 'payload 变化导致更新的 raw 条数'),
    'raw_unchanged': _entry('未变 Raw', 'monitor_run', 'number', 'content 未变跳过的 raw 条数'),
    'intel_written': _entry('写入情报', 'monitor_run', 'number', '新写入 intel 条数'),
    'intel_replaced': _entry('覆盖情报', 'monitor_run', 'number', 'payload 更新后覆盖重写的 intel 条数'),
    'intel_skipped': _entry('跳过情报', 'monitor_run', 'number', 'dedup 等原因未写入的条数'),
    'crawl_ms': _entry('爬取耗时', 'monitor_run', 'number', '该 source 爬取 wall time（毫秒）'),
    'analyze_ms': _entry('分析耗时', 'monitor_run', 'number', '该 source 分摊的分析 wall time（毫秒）'),
    'prompt_tokens': _entry('Prompt Tokens', 'monitor_run', 'number', '输入 token 数'),
    'completion_tokens': _entry('Completion Tokens', 'monitor_run', 'number', '输出 token 数'),
    'total_tokens': _entry('Total Tokens', 'monitor_run', 'number', '本 run 或 source 合计 token'),
}

# cfg-* / ai-* element id → registry key
ELEMENT_ID_TO_KEY = {
    'aiProvider': 'provider',
    'aiEndpoint': 'endpoint',
    'aiEndpointIntl': 'endpoint_intl',
    'aiModel': 'model',
    'aiPromptVer': 'prompt_version',
    'aiKeyEnv': 'api_key_env',
    'aiKey': 'api_key',
    'aiBatch': 'batch_size',
    'aiBodyMax': 'max_body_chars',
    'aiRetries': 'max_retries',
    'aiRetryDelay': 'retry_delay_sec',
    'aiTemp': 'temperature',
    'aiTimeout': 'timeout_sec',
    'aiExtraBody': 'extra_body',
    'aiSystemPrompt': 'system_prompt',
    'cfg-server-host': 'host',
    'cfg-server-port': 'port',
    'cfg-chrome-exe': 'exe_path',
    'cfg-chrome-port': 'cdp_port',
    'cfg-chrome-profile': 'profile_dir',
    'cfg-chrome-startup': 'startup_url',
    'cfg-output-dir': 'output_dir',
    'cfg-max-logs': 'max_logs',
    'cfg-h-kw': 'default_keyword',
    'cfg-h-pages': 'default_max_pages',
    'cfg-h-source': 'source_name',
    'cfg-h-base': 'base_url',
    'cfg-h-search-tpl': 'search_url_template',
    'cfg-h-search-sel': 'search_input_selector',
    'cfg-h-timeout': 'page_timeout_ms',
    'cfg-x-kw': 'default_keyword',
    'cfg-x-pages': 'default_max_pages',
    'cfg-x-source': 'source_name',
    'cfg-x-search-tpl': 'search_url_template',
    'cfg-x-note-sel': 'note_item_selector',
    'cfg-x-link-sel': 'link_selector',
    'cfg-x-title-sel': 'title_selector',
    'cfg-x-text-sel': 'text_selector',
    'cfg-x-scroll-px': 'scroll_pixels',
    'cfg-x-scroll-times': 'scroll_times_per_page',
    'monDefaultPages': 'default_max_pages',
    'monTaskTimeout': 'task_timeout_sec',
}


def field_label(key):
    meta = FIELD_LABELS.get(key)
    if meta:
        return '%s (%s)' % (meta['label'], key)
    return key


def field_meta(key):
    return FIELD_LABELS.get(key) or {
        'label': key,
        'group': 'crawl',
        'type': 'text',
        'help': '',
    }


def export_field_labels_json():
    import json
    return json.dumps({
        'fields': FIELD_LABELS,
        'elementIds': ELEMENT_ID_TO_KEY,
    }, ensure_ascii=False, indent=2)
