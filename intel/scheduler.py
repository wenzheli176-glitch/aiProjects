# -*- coding: utf-8 -*-
"""监测任务 Cron 调度（APScheduler）。"""
import threading

from config import cfg
from intel.time_util import app_tz

_scheduler = None
_scheduler_lock = threading.Lock()


def _job_id(task_id):
    return 'monitor-task-%d' % int(task_id)


def get_scheduler():
    global _scheduler
    with _scheduler_lock:
        if _scheduler is None:
            from apscheduler.schedulers.background import BackgroundScheduler
            _scheduler = BackgroundScheduler()
        return _scheduler


def _fire_scheduled_task(task_id):
    from crawler_web import log
    from intel.run_state import is_monitor_busy
    from intel.db import create_task_run, finish_task_run, get_monitor_task
    from intel.runner import run_monitor_task

    task = get_monitor_task(task_id)
    if not task:
        return
    sched = task.get('schedule') or {}
    if not sched.get('enabled') or not (sched.get('cron') or '').strip():
        return
    if is_monitor_busy() and sched.get('skip_if_running', True):
        run_id = create_task_run(task_id, 'schedule', 'incremental', status='skipped_overlap')
        finish_task_run(run_id, 'skipped_overlap', error_message='任务进行中，跳过本次定时')
        log('[scheduler] 任务 #%d 定时跳过（运行中）' % task_id, 'WARN')
        return

    def _run():
        try:
            run_monitor_task(
                task_id,
                log_fn=log,
                trigger='schedule',
                analyze_mode='incremental',
                crawl_only=bool(task.get('crawl_only')),
            )
        except Exception as e:
            log('[scheduler] 任务 #%d 失败: %s' % (task_id, str(e)[:100]), 'ERROR')

    threading.Thread(target=_run, daemon=True).start()


def reload_task_job(task_id):
    if not cfg('monitor', 'scheduler_enabled', default=True):
        return
    from intel.db import get_monitor_task

    sched_obj = get_scheduler()
    job_id = _job_id(task_id)
    try:
        sched_obj.remove_job(job_id)
    except Exception:
        pass

    task = get_monitor_task(task_id)
    if not task:
        return
    sched = task.get('schedule') or {}
    if not sched.get('enabled'):
        return
    cron = (sched.get('cron') or '').strip()
    if not cron:
        return
    parts = cron.split()
    if len(parts) != 5:
        return
    tz_name = sched.get('timezone') or cfg('monitor', 'scheduler_timezone', default='Asia/Shanghai')
    try:
        from apscheduler.triggers.cron import CronTrigger
        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
            timezone=tz_name,
        )
        sched_obj.add_job(
            _fire_scheduled_task,
            trigger=trigger,
            id=job_id,
            args=[task_id],
            replace_existing=True,
        )
    except Exception:
        pass


def reload_all_jobs():
    if not cfg('monitor', 'scheduler_enabled', default=True):
        return
    from intel.db import list_monitor_tasks

    sched_obj = get_scheduler()
    for task in list_monitor_tasks(limit=500):
        reload_task_job(task['id'])


def init_scheduler():
    if not cfg('monitor', 'scheduler_enabled', default=True):
        return
    sched_obj = get_scheduler()
    if not sched_obj.running:
        sched_obj.start()
    reload_all_jobs()


def get_next_run_at(task_id):
    sched_obj = get_scheduler()
    if not sched_obj.running:
        return None
    job = sched_obj.get_job(_job_id(task_id))
    if not job or not job.next_run_time:
        return None
    return job.next_run_time.astimezone(app_tz()).strftime('%Y-%m-%dT%H:%M:%S')
