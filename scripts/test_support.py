# -*- coding: utf-8 -*-
"""脚本测试公共资源：登记并在测试结束后自动清理任务/合作方。"""
import atexit

_registry = {'tasks': set(), 'partners': set()}
_registered_atexit = False


def _ensure_atexit():
    global _registered_atexit
    if not _registered_atexit:
        atexit.register(cleanup_all)
        _registered_atexit = True


def track_task(task_or_id):
    _ensure_atexit()
    tid = task_or_id['id'] if isinstance(task_or_id, dict) else int(task_or_id)
    _registry['tasks'].add(tid)
    return tid


def track_partner(partner_or_id):
    _ensure_atexit()
    pid = partner_or_id['id'] if isinstance(partner_or_id, dict) else int(partner_or_id)
    _registry['partners'].add(pid)
    return pid


def force_delete_monitor_task(task_id):
    from intel.db import delete_monitor_task, get_monitor_task, update_task_status

    task = get_monitor_task(task_id)
    if not task:
        return
    if task['status'] in ('crawling', 'analyzing', 'queued'):
        update_task_status(task_id, 'stopped', error_message='test cleanup')
    delete_monitor_task(task_id)


def force_delete_partner(partner_id):
    from intel.db import delete_partner

    delete_partner(partner_id)


def cleanup_all():
    for tid in list(_registry['tasks']):
        try:
            force_delete_monitor_task(tid)
        except Exception:
            pass
        _registry['tasks'].discard(tid)
    for pid in list(_registry['partners']):
        try:
            force_delete_partner(pid)
        except Exception:
            pass
        _registry['partners'].discard(pid)


class TestScope:
    """测试作用域：退出时自动清理本 scope 内创建的资源。"""

    def __init__(self):
        self._tasks = []
        self._partners = []

    def create_task(self, data):
        from intel.db import create_monitor_task

        task = create_monitor_task(data)
        self._tasks.append(task['id'])
        track_task(task['id'])
        return task

    def create_partner(self, data):
        from intel.db import create_partner

        partner = create_partner(data)
        self._partners.append(partner['id'])
        track_partner(partner['id'])
        return partner

    def track_task(self, task_or_id):
        tid = track_task(task_or_id)
        if tid not in self._tasks:
            self._tasks.append(tid)
        return tid

    def track_partner(self, partner_or_id):
        pid = track_partner(partner_or_id)
        if pid not in self._partners:
            self._partners.append(pid)
        return pid

    def cleanup(self):
        for tid in self._tasks:
            try:
                force_delete_monitor_task(tid)
            except Exception:
                pass
            _registry['tasks'].discard(tid)
        for pid in self._partners:
            try:
                force_delete_partner(pid)
            except Exception:
                pass
            _registry['partners'].discard(pid)
        self._tasks.clear()
        self._partners.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.cleanup()
        return False
