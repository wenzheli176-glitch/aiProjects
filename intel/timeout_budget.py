# -*- coding: utf-8 -*-
"""监测任务爬取/分析 wall-clock 预算分配。"""


def compute_monitor_deadlines(task_timeout_sec, analysis_timeout_sec, min_crawl_timeout_sec):
    """返回 task_timeout / analysis_reserve / crawl_budget（秒）。

    task_timeout_sec <= 0 表示关闭整体超时限制（unlimited=True）。
    """
    raw_task = int(task_timeout_sec if task_timeout_sec is not None else 7200)
    if raw_task <= 0:
        return {
            'task_timeout_sec': 0,
            'analysis_reserve_sec': 0,
            'crawl_budget_sec': 0,
            'unlimited': True,
        }
    task = max(60, raw_task)
    analysis_cfg = int(analysis_timeout_sec or 3600)
    min_crawl = max(60, int(min_crawl_timeout_sec or 1800))

    min_crawl = min(min_crawl, max(60, task - 60))
    room_for_analysis = max(0, task - min_crawl)

    analysis_reserve = min(analysis_cfg, room_for_analysis)
    if task >= min_crawl + 300:
        analysis_reserve = max(300, analysis_reserve)
    analysis_reserve = min(analysis_reserve, room_for_analysis)

    crawl_budget = task - analysis_reserve
    crawl_budget = max(min_crawl, crawl_budget)
    if crawl_budget + analysis_reserve > task:
        crawl_budget = max(min_crawl, task - analysis_reserve)

    return {
        'task_timeout_sec': task,
        'analysis_reserve_sec': analysis_reserve,
        'crawl_budget_sec': crawl_budget,
        'unlimited': False,
    }


def monitor_timeout_config_from_cfg(cfg_fn):
    """从 config.cfg('monitor', ...) 读取并计算预算。"""
    task = cfg_fn('monitor', 'task_timeout_sec', default=7200)
    analysis = cfg_fn('monitor', 'analysis_timeout_sec', default=3600)
    min_crawl = cfg_fn('monitor', 'min_crawl_timeout_sec', default=1800)
    budget = compute_monitor_deadlines(task, analysis, min_crawl)
    budget['analysis_timeout_sec'] = int(analysis or 3600)
    budget['min_crawl_timeout_sec'] = int(min_crawl or 1800)
    return budget


def warn_if_analysis_timeout_clamped(budget, log_fn=None):
    """analysis_timeout 过大时 WARN（已按公式 clamp）。"""
    analysis_cfg = budget.get('analysis_timeout_sec') or 0
    task = budget.get('task_timeout_sec') or 0
    min_crawl = budget.get('min_crawl_timeout_sec') or 0
    max_allowed = max(0, task - min_crawl)
    if analysis_cfg <= max_allowed:
        return
    msg = (
        '[monitor] analysis_timeout_sec=%d 超过可分配上限 %d '
        '(task_timeout=%d - min_crawl=%d)，已 clamp 为 analysis_reserve=%d'
    ) % (
        analysis_cfg, max_allowed, task, min_crawl,
        budget.get('analysis_reserve_sec', 0),
    )
    if log_fn:
        log_fn(msg, 'WARN')
